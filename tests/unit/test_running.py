"""Verify duration-based recovery independently of an endurance activity's label."""

from datetime import date

import pytest

from training_planner.domain.models import Activity, Session, Status
from training_planner.domain.running import is_demanding, recovery_days


@pytest.mark.parametrize(
    "activity",
    [
        Activity.RECOVERY_RUN,
        Activity.EASY_RUN,
        Activity.LONG_RUN,
        Activity.HIKE,
        Activity.CYCLE,
    ],
)
@pytest.mark.parametrize(
    ("minutes", "expected_days"),
    [(None, 0), (89, 0), (90, 2), (119, 2), (120, 3)],
)
def test_endurance_duration_recovery_boundaries(activity, minutes, expected_days):
    session = Session(
        date(2026, 10, 9),
        activity,
        duration_min=minutes,
        hr_zone_min=2,
        hr_zone_max=2,
    )
    assert is_demanding(session) == (expected_days > 0)
    assert recovery_days(session) == expected_days


@pytest.mark.parametrize(
    "activity", [Activity.RECOVERY_RUN, Activity.EASY_RUN, Activity.LONG_RUN]
)
def test_skipped_long_runs_have_no_recovery_load(activity):
    session = Session(date(2026, 10, 9), activity, Status.SKIPPED, duration_min=120)
    assert not is_demanding(session)
    assert recovery_days(session) == 0
