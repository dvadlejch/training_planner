"""Protect leg gym work from neighboring endurance without losing gym capacity."""

from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta

import pytest

from training_planner.domain.models import (
    Activity,
    GymSplit,
    MuscleGroup,
    Session,
    Status,
    TrainingTargets,
)
from training_planner.domain.running import leg_endurance_conflict
from training_planner.planner.gym import assign_gym_targets
from training_planner.planner.rules import recovery_conflict, suggest_week

START = date(2026, 10, 5)


@pytest.mark.parametrize("offset", [-2, -1, 0, 1, 2])
@pytest.mark.parametrize(
    ("activity", "minutes", "zone", "effort", "protect"),
    [
        (Activity.HIKE, None, None, None, True),
        (Activity.CYCLE, 15, None, None, True),
        (Activity.INTERVAL_RUN, 30, None, None, True),
        (Activity.TEMPO_RUN, None, None, None, True),
        (Activity.HARD_ENDURANCE_RUN, 40, None, None, True),
        (Activity.RACE, None, None, None, True),
        (Activity.EASY_RUN, 20, 4, None, True),
        (Activity.RECOVERY_RUN, 20, 2, 7, True),
        (Activity.EASY_RUN, 90, 2, None, True),
        (Activity.LONG_RUN, 45, 2, None, False),
        (Activity.EASY_RUN, 20, 2, None, False),
        (Activity.REST, None, None, None, False),
    ],
)
def test_leg_endurance_spacing_is_symmetric(
    activity: Activity,
    minutes: int | None,
    zone: int | None,
    effort: int | None,
    protect: bool,
    offset: int,
) -> None:
    """Require a full intervening day on both sides of hikes, cycling and hard runs.

    Short or unspecified hikes and rides still count. Running intensity follows
    category, HR target, RPE and long-duration rules; ordinary easy runs do not
    acquire a leg constraint. A hard Monday run must not use the easy exception.
    """
    legs = Session(
        START, Activity.GYM, muscle_groups=[MuscleGroup.LEGS, MuscleGroup.ABS]
    )
    endurance = Session(
        START + timedelta(days=offset),
        activity,
        duration_min=minutes,
        hr_zone_min=zone,
        hr_zone_max=zone,
        effort=effort,
    )
    expected = protect and abs(offset) < 2
    assert leg_endurance_conflict(legs, endurance) == expected
    assert leg_endurance_conflict(endurance, legs) == expected
    if expected:
        assert recovery_conflict(legs, endurance)
        assert recovery_conflict(endurance, legs)


@pytest.mark.parametrize("skip_legs", [False, True])
def test_skipped_work_has_no_leg_constraint(skip_legs: bool) -> None:
    """Ignore a skipped entry on either side of the leg/endurance comparison."""
    legs = Session(START, Activity.GYM, muscle_groups=[MuscleGroup.LEGS])
    hike = Session(START + timedelta(days=1), Activity.HIKE, duration_min=180)
    if skip_legs:
        legs.status = Status.SKIPPED
    else:
        hike.status = Status.SKIPPED
    assert not leg_endurance_conflict(legs, hike)
    assert not recovery_conflict(legs, hike)
    assert not recovery_conflict(hike, legs)


@pytest.mark.parametrize("groups", [[], [MuscleGroup.BACK], [MuscleGroup.ABS]])
def test_unknown_and_upper_body_gyms_remain_compatible(
    groups: list[MuscleGroup],
) -> None:
    """Do not infer leg load from unspecified or upper-body gym selections."""
    gym = Session(START, Activity.GYM, muscle_groups=groups)
    hike = Session(START + timedelta(days=1), Activity.HIKE, duration_min=180)
    assert not leg_endurance_conflict(gym, hike)
    assert not recovery_conflict(hike, gym)


def test_default_legs_move_to_thursday_before_saturday_hike() -> None:
    """Bring leg targets forward to Thursday while keeping all three gym dates."""
    split = GymSplit(legs=(MuscleGroup.TRICEPS, MuscleGroup.ABS))
    proposed = suggest_week(START, [], not_before=START, gym_split=split)
    first_week = [s for s in proposed if s.day < START + timedelta(days=7)]
    gyms = [s for s in first_week if s.activity == Activity.GYM]
    assert [s.day for s in gyms] == [START + timedelta(days=i) for i in (1, 3, 4)]
    legs = next(s for s in gyms if MuscleGroup.LEGS in s.muscle_groups)
    assert legs.day == START + timedelta(days=3)
    assert legs.muscle_groups == [MuscleGroup.LEGS, MuscleGroup.TRICEPS, MuscleGroup.ABS]
    hikes = [s for s in proposed if s.activity == Activity.HIKE]
    assert len(hikes) == 4
    assert all(not leg_endurance_conflict(gym, hike) for gym in gyms for hike in hikes)


def test_unsafe_legs_are_deferred_without_advancing_their_turn() -> None:
    """Use upper-body substitutes, then give legs priority at the next safe date."""
    previous = Session(
        START - timedelta(days=1), Activity.GYM, muscle_groups=[MuscleGroup.BACK]
    )
    cycle = Session(START + timedelta(days=2), Activity.CYCLE)
    slots = [Session(START + timedelta(days=i), Activity.GYM) for i in (1, 3, 7)]
    original = deepcopy(slots)
    proposed = assign_gym_targets(slots, [previous, cycle], GymSplit(), start=START)
    assert [s.muscle_groups[0] for s in proposed] == [
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.LEGS,
    ]
    assert [s.day for s in proposed] == [s.day for s in slots]
    assert slots == original


@pytest.mark.parametrize("offset", [0, 2, 6])
@pytest.mark.parametrize("reverse", [False, True])
def test_spacing_survives_confirmation_with_saved_cycling(
    offset: int, reverse: bool
) -> None:
    """Retain safe muscle targets after each confirmation around saved bike rides."""
    start = START + timedelta(days=offset)
    saved = [
        Session(start + timedelta(days=i), Activity.CYCLE, duration_min=30)
        for i in (4, 11, 18, 25)
    ]
    original = deepcopy(saved)
    targets = TrainingTargets(gym=3, runs=3, intervals=1)
    preview = suggest_week(start, saved, not_before=start, targets=targets)
    legs = [s for s in preview if MuscleGroup.LEGS in s.muscle_groups]
    # Dense endurance weeks may have no safe leg slot; upper-body work remains.
    assert any(s.activity == Activity.GYM for s in preview)
    assert all(
        not leg_endurance_conflict(gym, other)
        for gym in legs
        for other in saved + preview
    )
    remaining = list(preview)
    for session in reversed(preview) if reverse else preview:
        saved.append(replace(session, status=Status.CONFIRMED))
        remaining.remove(session)
        assert suggest_week(start, saved, not_before=start, targets=targets) == remaining
    assert saved[: len(original)] == original


@pytest.mark.parametrize("offset", [-1, 4, 27, 28])
@pytest.mark.parametrize("status", [Status.PLANNED, Status.CONFIRMED, Status.COMPLETED])
def test_saved_legs_protect_neighboring_hikes_without_changes(
    offset: int, status: Status
) -> None:
    """Honor saved leg work, including just outside the horizon, in hike placement."""
    gym = Session(
        START + timedelta(days=offset),
        Activity.GYM,
        status,
        muscle_groups=[MuscleGroup.LEGS],
    )
    original = deepcopy(gym)
    proposed = suggest_week(
        START, [gym], not_before=START, targets=TrainingTargets(gym=0, runs=0)
    )
    assert all(not leg_endurance_conflict(gym, s) for s in proposed)
    if offset == 4:
        assert not any(s.day == START + timedelta(days=5) for s in proposed)
    assert gym == original


def test_completed_actual_run_duration_controls_leg_spacing() -> None:
    """Use recorded run duration when the completed result overrides its plan."""
    legs = Session(START, Activity.GYM, muscle_groups=[MuscleGroup.LEGS])
    run = Session(
        START + timedelta(days=1),
        Activity.EASY_RUN,
        Status.COMPLETED,
        duration_min=20,
        actual_duration_min=95,
    )
    assert leg_endurance_conflict(legs, run)
    assert not leg_endurance_conflict(legs, replace(run, actual_duration_min=20))
