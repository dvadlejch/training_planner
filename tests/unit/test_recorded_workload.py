"""Verify the impact of recorded time on duration-based recovery heuristics."""

from datetime import date
from pathlib import Path

import pytest

from training_planner.application.services import create_session
from training_planner.domain.models import Activity, Session, Status
from training_planner.domain.running import recovery_days
from training_planner.planner.rules import recovery_conflict


@pytest.mark.parametrize(
    ("status", "actual", "expected"),
    [
        (Status.COMPLETED, 130, 3),
        (Status.COMPLETED, 95, 2),
        (Status.COMPLETED, 0, 0),
        (Status.COMPLETED, None, 0),
        (Status.PLANNED, 130, 0),
        (Status.SKIPPED, 130, 0),
    ],
)
def test_completed_workload_uses_recorded_time(
    status: Status, actual: float | None, expected: int
) -> None:
    """Use actual time only for completed work, preserving missing/zero semantics."""
    session = Session(
        date(2026, 10, 5),
        Activity.HIKE,
        status=status,
        duration_min=30,
        actual_duration_min=actual,
    )
    assert recovery_days(session) == expected


def test_monday_recovery_exception_uses_recorded_time() -> None:
    """A completed run longer than its short plan loses the recovery exception."""
    run = Session(
        date(2026, 10, 5),
        Activity.EASY_RUN,
        status=Status.COMPLETED,
        duration_min=20,
        actual_duration_min=45,
    )
    hike = Session(date(2026, 10, 4), Activity.HIKE, duration_min=180)
    assert recovery_conflict(run, hike)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actual_duration_min", -1),
        ("actual_duration_min", 1441),
        ("distance_km", float("nan")),
        ("distance_km", -1),
        ("elevation_gain_m", float("inf")),
        ("active_calories_kcal", -1),
        ("average_hr_bpm", 301),
    ],
)
def test_service_rejects_invalid_results(
    tmp_path: Path, field: str, value: float
) -> None:
    """Validate recorded results even when callers bypass HTTP validation."""
    session = Session(date(2026, 10, 5), Activity.HIKE)
    setattr(session, field, value)
    with pytest.raises(ValueError):
        create_session(tmp_path / "stats.db", session)
