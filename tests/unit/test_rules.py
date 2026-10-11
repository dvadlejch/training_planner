from datetime import date, timedelta

import pytest

from training_planner.domain.models import Activity, Session, Status
from training_planner.planner.rules import suggest_week


def test_keeps_existing_and_blocked_days_unchanged():
    """Suggestions preserve existing sessions and blocked dates."""
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=1), Activity.GYM, Status.COMPLETED)]
    blocked = {monday + timedelta(days=3)}
    proposed = suggest_week(monday, existing, blocked, not_before=monday)
    assert all(s.day not in blocked for s in proposed)
    assert all(s.day != existing[0].day for s in proposed)
    assert all(s.status == Status.PLANNED for s in proposed)


def test_hard_saturday_skips_sunday_run():
    """A demanding Saturday suppresses the default Sunday long run."""
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=5), Activity.HIKE, effort=8)]
    proposed = suggest_week(monday, existing, not_before=monday)
    assert not any(s.activity == Activity.LONG_RUN for s in proposed)


@pytest.mark.parametrize(
    ("cutoff_offset", "expected_offsets"),
    [
        (-1, [0, 1, 2, 4, 5, 6]),
        (0, [0, 1, 2, 4, 5, 6]),
        (2, [2, 4, 5, 6]),
        (7, []),
    ],
)
def test_date_cutoff_is_inclusive_and_keeps_future_weeks(cutoff_offset, expected_offsets):
    """Exclude elapsed dates while retaining today and later dates."""
    monday = date(2026, 10, 5)
    proposed = suggest_week(monday, [], not_before=monday + timedelta(days=cutoff_offset))
    assert [session.day for session in proposed] == [
        monday + timedelta(days=offset) for offset in expected_offsets
    ]
