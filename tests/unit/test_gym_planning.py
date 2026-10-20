"""Verify configurable gym rotation, chronology and preservation of saved work."""

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta

import pytest

from training_planner.domain.models import (
    GYM_PRIMARY_GROUPS,
    Activity,
    GymSplit,
    MuscleGroup,
    Session,
    Status,
    TrainingTargets,
)
from training_planner.planner.rules import suggest_week

START = date(2026, 10, 5)
CUSTOM = GymSplit(
    chest=(MuscleGroup.BICEPS,),
    back=(MuscleGroup.SHOULDERS, MuscleGroup.ABS),
    legs=(MuscleGroup.TRICEPS,),
)


@pytest.mark.parametrize("offset", [0, 2, 6])
@pytest.mark.parametrize("gym_count", [1, 2, 3, 7])
def test_default_rotation_follows_dates_across_periods(
    offset: int, gym_count: int
) -> None:
    """Rotate all three default combinations by date, without resetting each week."""
    start = START + timedelta(days=offset)
    proposed = suggest_week(
        start,
        [],
        not_before=start,
        targets=TrainingTargets(gym=gym_count, runs=0),
        excluded={(start + timedelta(days=i), Activity.HIKE) for i in range(28)},
    )
    gyms = [s for s in proposed if s.activity == Activity.GYM]
    assert gyms
    expected = [
        [MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.ABS],
        [MuscleGroup.BACK, MuscleGroup.TRICEPS, MuscleGroup.ABS],
        [MuscleGroup.LEGS, MuscleGroup.BICEPS, MuscleGroup.ABS],
    ]
    assert [s.muscle_groups for s in gyms] == [
        expected[index % 3] for index in range(len(gyms))
    ]
    assert all(not s.muscle_groups for s in proposed if s.activity != Activity.GYM)


@pytest.mark.parametrize("reverse", [False, True])
def test_custom_split_survives_individual_confirmations(reverse: bool) -> None:
    """Retain custom accessories on every original draft after partial confirmation.

    Blocking preferred dates exercises fallback placement. Accepting latest-first
    ensures a future saved target cannot rewrite earlier drafts. A two-session
    weekly target also exercises rotation across seven-day boundaries.
    """
    blocked = {START + timedelta(days=i) for i in (1, 9, 17)}
    targets = TrainingTargets(gym=2, runs=1)
    preview = suggest_week(
        START, [], blocked, not_before=START, targets=targets, gym_split=CUSTOM
    )
    gyms = [s for s in preview if s.activity == Activity.GYM]
    assert {s.muscle_groups[0] for s in gyms} == set(GYM_PRIMARY_GROUPS)
    assert all(s.muscle_groups == CUSTOM.groups_for(s.muscle_groups[0]) for s in gyms)
    saved = []
    remaining = list(preview)
    for proposal in reversed(preview) if reverse else preview:
        saved.append(replace(proposal, status=Status.CONFIRMED))
        remaining.remove(proposal)
        assert (
            suggest_week(
                START,
                saved,
                blocked,
                not_before=START,
                targets=targets,
                gym_split=CUSTOM,
            )
            == remaining
        )


@pytest.mark.parametrize(
    ("groups", "status", "expected"),
    [
        ([MuscleGroup.BACK], Status.COMPLETED, MuscleGroup.LEGS),
        ([MuscleGroup.CHEST], Status.CONFIRMED, MuscleGroup.BACK),
        ([MuscleGroup.LEGS], Status.PLANNED, MuscleGroup.CHEST),
        ([MuscleGroup.BACK], Status.SKIPPED, MuscleGroup.CHEST),
        ([], Status.COMPLETED, MuscleGroup.CHEST),
        ([MuscleGroup.ABS], Status.COMPLETED, MuscleGroup.CHEST),
        ([MuscleGroup.CHEST, MuscleGroup.BACK], Status.COMPLETED, MuscleGroup.LEGS),
    ],
)
def test_saved_targets_anchor_rotation_without_mutation(
    groups: list[MuscleGroup], status: Status, expected: MuscleGroup
) -> None:
    """Continue after known primary groups while ignoring skipped or unknown targets."""
    saved = [
        Session(START - timedelta(days=1), Activity.GYM, status, muscle_groups=groups)
    ]
    original = deepcopy(saved)
    proposed = suggest_week(START, saved, not_before=START, gym_split=CUSTOM)
    first = next(s for s in proposed if s.activity == Activity.GYM)
    assert first.muscle_groups == CUSTOM.groups_for(expected)
    assert saved == original


def test_accessories_can_be_empty_or_include_every_small_group() -> None:
    """Permit a primary-only session and independently combine multiple accessories."""
    split = GymSplit(
        chest=(),
        back=(MuscleGroup.BICEPS, MuscleGroup.TRICEPS, MuscleGroup.SHOULDERS),
        legs=(MuscleGroup.ABS,),
    )
    proposed = suggest_week(
        START,
        [],
        not_before=START,
        gym_split=split,
        excluded={(START + timedelta(days=i), Activity.HIKE) for i in range(28)},
    )
    gyms = [s for s in proposed if s.activity == Activity.GYM]
    assert gyms[0].muscle_groups == [MuscleGroup.CHEST]
    assert gyms[1].muscle_groups == [MuscleGroup.BACK, *split.back]
    assert gyms[2].muscle_groups == [MuscleGroup.LEGS, MuscleGroup.ABS]


@pytest.mark.parametrize(
    "accessories",
    [(MuscleGroup.CHEST,), (MuscleGroup.ABS, MuscleGroup.ABS), ("unknown",)],
)
def test_domain_split_rejects_invalid_accessories(accessories) -> None:
    """Reject primary muscles, repeated accessories and unknown values in split rows."""
    with pytest.raises(ValueError):
        GymSplit(chest=accessories)
