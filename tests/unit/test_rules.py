"""Verify target scheduling, same-day pairing and recovery across 28 days."""

from datetime import date, timedelta

import pytest

from training_planner.domain.models import Activity, Session, Status, TrainingTargets
from training_planner.planner.rules import (
    RUN_ACTIVITIES,
    recovery_conflict,
    suggest_week,
)

START = date(2026, 10, 5)


@pytest.mark.parametrize("offset", range(7))
def test_fixed_horizon_from_any_weekday(offset):
    """Every start weekday produces four bounded seven-day target periods."""
    start = START + timedelta(days=offset)
    proposed = suggest_week(start, [], not_before=start)
    assert proposed
    assert all(start <= s.day < start + timedelta(days=28) for s in proposed)
    assert len({(s.day, s.activity) for s in proposed}) == len(proposed)
    for week in range(4):
        first = start + timedelta(days=7 * week)
        gym = [
            s
            for s in proposed
            if first <= s.day < first + timedelta(days=7) and s.activity == Activity.GYM
        ]
        assert len(gym) == 3


def test_saved_work_satisfies_targets_and_skipped_work_does_not():
    """Completed and confirmed work count; skipped work neither counts nor blocks."""
    saved = [
        Session(START + timedelta(days=1), Activity.GYM, Status.COMPLETED),
        Session(START + timedelta(days=2), Activity.GYM, Status.CONFIRMED),
        Session(START + timedelta(days=4), Activity.GYM, Status.SKIPPED),
        Session(START, Activity.EASY_RUN, Status.COMPLETED, duration_min=20),
    ]
    original = list(saved)
    proposed = suggest_week(
        START, saved, not_before=START, targets=TrainingTargets(gym=3, runs=1)
    )
    first = [s for s in proposed if s.day < START + timedelta(days=7)]
    assert [s.day for s in first if s.activity == Activity.GYM] == [
        START + timedelta(days=4)
    ]
    assert not any(s.activity in RUN_ACTIVITIES for s in first)
    assert saved == original


def test_zero_targets_disable_gym_and_running():
    """Zero targets preserve only the independent outdoor suggestions."""
    proposed = suggest_week(
        START, [], not_before=START, targets=TrainingTargets(gym=0, runs=0)
    )
    assert len(proposed) == 4
    assert all(s.activity == Activity.HIKE for s in proposed)


def test_busy_days_trigger_gym_fallback():
    """Unavailable preferred gym dates trigger alternatives in the same period."""
    blocked = {START + timedelta(days=i) for i in (1, 2, 4)}
    proposed = suggest_week(START, [], blocked, not_before=START)
    first = [
        s
        for s in proposed
        if s.activity == Activity.GYM and s.day < START + timedelta(days=7)
    ]
    assert len(first) == 3
    assert all(s.day not in blocked for s in proposed)


def test_easy_run_and_gym_can_share_a_day():
    """One free day per period can receive both an easy run and gym suggestion."""
    blocked = {START + timedelta(days=i) for i in range(28) if i % 7 != 0}
    proposed = suggest_week(
        START, [], blocked, not_before=START, targets=TrainingTargets(gym=1, runs=1)
    )
    assert len(proposed) == 8
    for offset in range(0, 28, 7):
        assert {
            s.activity for s in proposed if s.day == START + timedelta(days=offset)
        } == {Activity.GYM, Activity.EASY_RUN}


def test_high_targets_do_not_overfill_days():
    """Automatic suggestions allow at most two events and one run per day."""
    proposed = suggest_week(
        START, [], not_before=START, targets=TrainingTargets(gym=7, runs=7, intervals=2)
    )
    for offset in range(28):
        same_day = [s for s in proposed if s.day == START + timedelta(days=offset)]
        assert len(same_day) <= 2
        assert sum(s.activity in RUN_ACTIVITIES for s in same_day) <= 1


def test_rest_booking_blocks_suggestions():
    """An explicit rest day receives no automatic training."""
    proposed = suggest_week(START, [Session(START, Activity.REST)], not_before=START)
    assert all(s.day != START for s in proposed)


def test_interval_target_is_within_run_total():
    """One requested interval uses part of the three-run quota each period."""
    # Block outdoor slots to isolate the running mix from hike recovery.
    blocked = {START + timedelta(days=i) for i in range(28) if i % 7 in (5, 6)}
    proposed = suggest_week(
        START,
        [],
        blocked,
        not_before=START,
        targets=TrainingTargets(gym=0, runs=3, intervals=1),
    )
    for week in range(4):
        first = START + timedelta(days=7 * week)
        runs = [
            s
            for s in proposed
            if first <= s.day < first + timedelta(days=7)
            and s.activity in RUN_ACTIVITIES
        ]
        assert len(runs) == 3
        assert sum(s.activity == Activity.INTERVAL_RUN for s in runs) == 1


def test_exclusion_does_not_block_another_activity():
    """Excluding an easy run leaves a gym suggestion on the same available day."""
    blocked = {START + timedelta(days=i) for i in range(28) if i % 7 != 0}
    proposed = suggest_week(
        START,
        [],
        blocked,
        not_before=START,
        targets=TrainingTargets(gym=1, runs=1),
        excluded={(START, Activity.EASY_RUN)},
    )
    assert not any(s.day == START and s.activity == Activity.EASY_RUN for s in proposed)
    assert any(s.day == START and s.activity == Activity.GYM for s in proposed)


def test_fully_blocked_horizon_has_no_spillover():
    """Twenty-eight unavailable dates produce no workouts."""
    blocked = {START + timedelta(days=i) for i in range(28)}
    assert suggest_week(START, [], blocked, not_before=START) == []


@pytest.mark.parametrize("offset", [0, 2, 7, 27, 28])
def test_cutoff_is_inclusive(offset):
    """Today and later dates are eligible within the original fixed horizon."""
    cutoff = START + timedelta(days=offset)
    proposed = suggest_week(START, [], not_before=cutoff)
    assert all(cutoff <= s.day < START + timedelta(days=28) for s in proposed)
    assert bool(proposed) == (offset < 28)


@pytest.mark.parametrize("status", [Status.PLANNED, Status.COMPLETED, Status.SKIPPED])
def test_saved_sunday_run_controls_hike(status):
    """Active Sunday endurance suppresses Saturday's hike, unlike skipped work."""
    saved = Session(
        START + timedelta(days=6), Activity.LONG_RUN, status, duration_min=45
    )
    proposed = suggest_week(START, [saved], not_before=START)
    assert any(
        s.day == START + timedelta(days=5) and s.activity == Activity.HIKE
        for s in proposed
    ) == (status == Status.SKIPPED)


@pytest.mark.parametrize("minutes,buffer", [(90, 2), (119, 2), (120, 3)])
@pytest.mark.parametrize(
    "activity", [Activity.EASY_RUN, Activity.RECOVERY_RUN, Activity.LONG_RUN]
)
def test_long_saved_running_protects_recovery(activity, minutes, buffer):
    """Long running protects nearby endurance regardless of its category label."""
    saved = Session(START + timedelta(days=4), activity, duration_min=minutes)
    proposed = suggest_week(START, [saved], not_before=START)
    assert not any(
        s.day == START + timedelta(days=5) and s.activity == Activity.HIKE
        for s in proposed
    )
    assert all(
        abs((s.day - saved.day).days) >= buffer
        for s in proposed
        if s.activity in {Activity.HIKE, Activity.LONG_RUN}
    )


def test_outside_race_protects_horizon_boundary():
    """A race just outside the horizon blocks nearby endurance suggestions."""
    race = Session(START + timedelta(days=28), Activity.RACE)
    proposed = suggest_week(START, [race], not_before=START)
    assert all(
        abs((s.day - race.day).days) >= 3
        for s in proposed
        if s.activity in {Activity.HIKE, Activity.LONG_RUN}
    )


def test_deferred_runs_do_not_accumulate():
    """Deferred long runs stay seven days apart and respect other endurance."""
    blocked = {START + timedelta(days=5), START + timedelta(days=6)}
    proposed = suggest_week(START, [], blocked, not_before=START)
    runs = [s for s in proposed if s.activity == Activity.LONG_RUN]
    assert runs
    assert all((b.day - a.day).days >= 7 for a, b in zip(runs, runs[1:]))
    endurance = [s for s in proposed if s.activity in {Activity.HIKE, Activity.LONG_RUN}]
    assert all(
        not recovery_conflict(a, b)
        for i, a in enumerate(endurance)
        for b in endurance[i + 1 :]
    )


@pytest.mark.parametrize(
    "values",
    [
        {"gym": True},
        {"runs": 1.5},
        {"gym": -1},
        {"gym": 8},
        {"runs": -1},
        {"runs": 8},
        {"runs": 0, "intervals": 1},
        {"intervals": 3},
    ],
)
def test_invalid_targets(values):
    """Domain callers cannot use unsupported counts or inconsistent run mixes."""
    with pytest.raises(ValueError):
        TrainingTargets(**values)


@pytest.mark.parametrize(
    ("day", "minutes", "zone", "effort", "expected_conflict"),
    [
        (date(2026, 10, 12), 20, 2, None, False),
        (date(2026, 10, 12), 21, 2, None, True),
        (date(2026, 10, 12), None, 2, None, True),
        (date(2026, 10, 12), 20, 4, None, True),
        (date(2026, 10, 12), 20, 2, 7, True),
        (date(2026, 10, 11), 20, 2, None, True),
    ],
)
def test_monday_recovery_exception_respects_duration_and_load(
    day: date,
    minutes: int | None,
    zone: int,
    effort: int | None,
    expected_conflict: bool,
) -> None:
    """Exempt only short, non-demanding Monday easy runs in either comparison order.

    Longer or unknown durations, explicit hard intensity, high RPE, and other
    weekdays retain the hike's recovery buffer. The exception uses workout data,
    so it must behave identically when the easy run is the saved session.
    """
    hike = Session(date(2026, 10, 10), Activity.HIKE, duration_min=180)
    easy = Session(
        day,
        Activity.EASY_RUN,
        duration_min=minutes,
        effort=effort,
        hr_zone_min=zone,
        hr_zone_max=zone,
    )
    assert recovery_conflict(hike, easy) == expected_conflict
    assert recovery_conflict(easy, hike) == expected_conflict


@pytest.mark.parametrize("offset", [0, 3, 6])
@pytest.mark.parametrize(
    "targets",
    [
        TrainingTargets(gym=3, runs=3, intervals=1),
        TrainingTargets(gym=1, runs=1),
        TrainingTargets(gym=0, runs=4, intervals=2),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("busy", [False, True])
def test_custom_targets_preserve_remaining_drafts_after_each_confirmation(
    offset, targets, reverse, busy
):
    """Confirming custom-target drafts in either order preserves all other drafts.

    Exercise starts on different weekdays, with and without unavailable days.
    The original preview is retained while individual confirmed sessions become
    existing bookings, matching the calendar's per-card confirmation workflow.
    """
    start = START + timedelta(days=offset)
    blocked = {start + timedelta(days=i) for i in (2, 6, 10, 17)} if busy else set()
    preview = suggest_week(start, [], blocked, not_before=start, targets=targets)
    remaining = list(preview)
    saved = []
    for proposal in reversed(preview) if reverse else preview:
        saved.append(proposal)
        remaining.remove(proposal)
        regenerated = suggest_week(
            start, saved, blocked, not_before=start, targets=targets
        )
        assert regenerated == remaining
