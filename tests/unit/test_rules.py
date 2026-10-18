from datetime import date, timedelta

import pytest

from training_planner.domain.models import Activity, Session, Status
from training_planner.planner.rules import recovery_conflict, suggest_week


def test_keeps_existing_and_blocked_days_unchanged():
    """Suggestions preserve existing sessions and blocked dates."""
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=1), Activity.GYM, Status.COMPLETED)]
    blocked = {monday + timedelta(days=3)}
    proposed = suggest_week(monday, existing, blocked, not_before=monday)
    assert all(s.day not in blocked for s in proposed)
    assert all(s.day != existing[0].day for s in proposed)
    assert all(s.status == Status.PLANNED for s in proposed)


@pytest.mark.parametrize("start_offset", range(7))
@pytest.mark.parametrize("weeks", [1, 2, 3, 4])
def test_rolling_horizon_preserves_weekdays_and_bounds(start_offset, weeks):
    """Any start weekday covers exactly 7-28 days without shifting activity weekdays."""
    start = date(2026, 10, 26) + timedelta(days=start_offset)
    proposed = suggest_week(start, [], not_before=start, weeks=weeks)
    assert proposed
    assert all(start <= s.day < start + timedelta(days=7 * weeks) for s in proposed)
    assert len({s.day for s in proposed}) == len(proposed)
    assert all(
        s.day.weekday() in (1, 2, 4) for s in proposed if s.activity == Activity.GYM
    )
    assert all(s.day.weekday() == 5 for s in proposed if s.activity == Activity.HIKE)
    assert all(s.day.weekday() == 0 for s in proposed if s.activity == Activity.EASY_RUN)


def test_sunday_start_includes_next_wednesday_and_friday():
    """Starting October 18 includes October 21/23 with Tuesday and Thursday blocked."""
    start = date(2026, 10, 18)
    blocked = {date(2026, 10, 20), date(2026, 10, 22)}
    proposed = suggest_week(start, [], blocked, not_before=start)
    gym_dates = {s.day for s in proposed if s.activity == Activity.GYM}
    assert gym_dates == {date(2026, 10, 21), date(2026, 10, 23)}
    assert all(s.day not in blocked for s in proposed)
    assert all(start <= s.day <= date(2026, 10, 24) for s in proposed)


def test_hard_saturday_skips_sunday_run():
    """A demanding Saturday suppresses the default Sunday long run."""
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=5), Activity.HIKE, effort=8)]
    proposed = suggest_week(monday, existing, not_before=monday)
    assert not any(s.activity == Activity.LONG_RUN for s in proposed)


@pytest.mark.parametrize(
    ("cutoff_offset", "expected_offsets"),
    [
        (-1, [0, 1, 2, 4, 5]),
        (0, [0, 1, 2, 4, 5]),
        (2, [2, 4, 5]),
        (7, []),
    ],
)
def test_date_cutoff_is_inclusive_and_keeps_future_weeks(
    cutoff_offset, expected_offsets
):
    """Exclude elapsed dates while retaining today and later dates."""
    monday = date(2026, 10, 5)
    proposed = suggest_week(
        monday, [], not_before=monday + timedelta(days=cutoff_offset)
    )
    assert [session.day for session in proposed] == [
        monday + timedelta(days=offset) for offset in expected_offsets
    ]


def test_proposed_long_hike_prevents_back_to_back_endurance():
    monday = date(2026, 10, 5)
    proposed = suggest_week(monday, [], not_before=monday)
    assert any(s.activity == Activity.HIKE for s in proposed)
    assert not any(s.activity == Activity.LONG_RUN for s in proposed)


def test_long_run_has_easy_zone_when_saturday_is_unavailable():
    monday = date(2026, 10, 5)
    proposed = suggest_week(monday, [], {monday + timedelta(days=5)}, not_before=monday)
    run = next(s for s in proposed if s.activity == Activity.LONG_RUN)
    assert run.hr_zone_min == run.hr_zone_max == 2
    assert run.duration_min == 45


@pytest.mark.parametrize(
    "status,expect_long", [(Status.PLANNED, False), (Status.SKIPPED, True)]
)
def test_interval_load_without_rpe_and_skipped_work(status, expect_long):
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=5), Activity.INTERVAL_RUN, status)]
    proposed = suggest_week(monday, existing, not_before=monday)
    assert any(s.activity == Activity.LONG_RUN for s in proposed) == expect_long


def test_future_week_race_protects_sunday():
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=7), Activity.RACE)]
    proposed = suggest_week(
        monday, existing, {monday + timedelta(days=5)}, not_before=monday
    )
    assert not any(s.activity == Activity.LONG_RUN for s in proposed)


@pytest.mark.parametrize(
    "activity", [Activity.RECOVERY_RUN, Activity.EASY_RUN, Activity.LONG_RUN]
)
@pytest.mark.parametrize(
    ("minutes", "expect_sunday_run"), [(90, True), (119, True), (120, False)]
)
def test_long_friday_runs_protect_weekend_regardless_of_label(
    activity, minutes, expect_sunday_run
):
    monday = date(2026, 10, 5)
    existing = [
        Session(
            monday + timedelta(days=4),
            activity,
            duration_min=minutes,
            hr_zone_min=2,
            hr_zone_max=2,
        )
    ]
    proposed = suggest_week(monday, existing, not_before=monday)
    assert not any(s.activity == Activity.HIKE for s in proposed)
    # A saved long run also satisfies the rolling long-run frequency target.
    expected = expect_sunday_run and activity != Activity.LONG_RUN
    assert any(s.activity == Activity.LONG_RUN for s in proposed) == expected


@pytest.mark.parametrize("offset", [6, 7])
def test_saved_long_run_prevents_hike_even_across_week_boundary(offset):
    monday = date(2026, 10, 5)
    existing = [
        Session(monday + timedelta(days=offset), Activity.LONG_RUN, duration_min=45)
    ]
    proposed = suggest_week(monday, existing, not_before=monday)
    assert not any(s.activity == Activity.HIKE for s in proposed)


def test_blocked_sunday_moves_long_run_to_next_monday():
    monday = date(2026, 10, 5)
    blocked = {monday + timedelta(days=i) for i in (5, 6)}
    proposed = suggest_week(monday, [], blocked, not_before=monday, weeks=2)
    runs = [s for s in proposed if s.activity == Activity.LONG_RUN]
    assert [s.day for s in runs] == [monday + timedelta(days=7)]
    assert not any(s.day in blocked for s in proposed)
    assert len({s.day for s in proposed}) == len(proposed)
    assert all(s.day.weekday() == 5 for s in proposed if s.activity == Activity.HIKE)


def test_blocked_monday_counts_as_recovery_before_tuesday_fallback():
    monday = date(2026, 10, 5)
    blocked = {monday + timedelta(days=7)}
    proposed = suggest_week(monday, [], blocked, not_before=monday, weeks=2)
    assert any(
        s.activity == Activity.HIKE and s.day == monday + timedelta(days=5)
        for s in proposed
    )
    assert any(
        s.activity == Activity.LONG_RUN and s.day == monday + timedelta(days=8)
        for s in proposed
    )
    assert not any(s.day in blocked for s in proposed)


def test_free_monday_is_not_used_before_hike_recovery_is_complete():
    monday = date(2026, 10, 5)
    proposed = suggest_week(monday, [], not_before=monday, weeks=2)
    assert not any(
        s.activity == Activity.LONG_RUN and s.day == monday + timedelta(days=7)
        for s in proposed
    )
    assert any(
        s.activity == Activity.LONG_RUN and s.day == monday + timedelta(days=8)
        for s in proposed
    )


def test_fully_blocked_horizon_does_not_spill_or_move_hikes():
    monday = date(2026, 10, 5)
    blocked = {monday + timedelta(days=i) for i in range(14)}
    assert suggest_week(monday, [], blocked, not_before=monday, weeks=2) == []


def test_fallback_respects_bookings_and_next_week_demanding_work():
    monday = date(2026, 10, 5)
    existing = [
        Session(monday + timedelta(days=7), Activity.CYCLE),
        Session(monday + timedelta(days=9), Activity.RACE),
    ]
    proposed = suggest_week(monday, existing, not_before=monday, weeks=2)
    assert not any(s.day in {x.day for x in existing} for s in proposed)
    assert all(
        abs((s.day - existing[1].day).days) >= 3
        for s in proposed
        if s.activity in {Activity.HIKE, Activity.LONG_RUN}
    )


def test_saved_deferred_run_does_not_create_another_makeup_run():
    monday = date(2026, 10, 5)
    saved = Session(monday + timedelta(days=8), Activity.LONG_RUN, duration_min=45)
    proposed = suggest_week(monday, [saved], not_before=monday, weeks=2)
    assert not any(s.activity == Activity.LONG_RUN for s in proposed)


@pytest.mark.parametrize("weeks", [0, 5])
def test_invalid_horizon_is_rejected(weeks):
    monday = date(2026, 10, 5)
    with pytest.raises(ValueError, match="weeks"):
        suggest_week(monday, [], not_before=monday, weeks=weeks)


@pytest.mark.parametrize("status", [Status.PLANNED, Status.COMPLETED, Status.SKIPPED])
def test_sunday_long_run_status_controls_hike_recovery(status):
    monday = date(2026, 10, 5)
    saved = Session(
        monday + timedelta(days=6), Activity.LONG_RUN, status, duration_min=45
    )
    proposed = suggest_week(monday, [saved], not_before=monday)
    assert any(s.activity == Activity.HIKE for s in proposed) == (
        status == Status.SKIPPED
    )


@pytest.mark.parametrize("weeks", [1, 2, 3, 4])
def test_proposed_endurance_has_recovery_spacing_across_entire_horizon(weeks):
    monday = date(2026, 10, 5)
    proposed = suggest_week(monday, [], not_before=monday, weeks=weeks)
    endurance = [s for s in proposed if s.activity in {Activity.HIKE, Activity.LONG_RUN}]
    assert all(
        abs((a.day - b.day).days)
        >= (3 if Activity.HIKE in {a.activity, b.activity} else 7)
        for i, a in enumerate(endurance)
        for b in endurance[i + 1 :]
    )
    assert all(monday <= s.day < monday + timedelta(days=7 * weeks) for s in proposed)


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
