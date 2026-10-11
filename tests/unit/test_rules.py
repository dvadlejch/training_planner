from datetime import date, timedelta

from training_planner.domain.models import Activity, Session, Status
from training_planner.planner.rules import suggest_week


def test_keeps_existing_and_blocked_days_unchanged():
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=1), Activity.GYM, Status.COMPLETED)]
    blocked = {monday + timedelta(days=3)}
    proposed = suggest_week(monday, existing, blocked)
    assert all(s.day not in blocked for s in proposed)
    assert all(s.day != existing[0].day for s in proposed)
    assert all(s.status == Status.PLANNED for s in proposed)


def test_hard_saturday_skips_sunday_run():
    monday = date(2026, 10, 5)
    existing = [Session(monday + timedelta(days=5), Activity.HIKE, effort=8)]
    assert not any(s.activity == Activity.LONG_RUN for s in suggest_week(monday, existing))
