"""Heart-rate targets and conservative calendar heuristics, not fitness estimates."""

from training_planner.domain.models import Activity, Session, Status

HARD_RUNS = {
    Activity.INTERVAL_RUN,
    Activity.TEMPO_RUN,
    Activity.HARD_ENDURANCE_RUN,
    Activity.RACE,
}


def validate_zone_target(low: int | None, high: int | None) -> None:
    """Require either an ordered pair of zones 1-5 or two unknown values."""
    if (low is None) != (high is None):
        raise ValueError("Supply both heart-rate zone limits, or leave both unknown")
    if low is not None and high is not None and not 1 <= low <= high <= 5:
        raise ValueError("Heart-rate zones must satisfy 1 <= minimum <= maximum <= 5")


def is_demanding(session: Session) -> bool:
    """Count intensity and long endurance across sports; skipped work has no load."""
    if session.status == Status.SKIPPED or session.activity == Activity.REST:
        return False
    return (
        session.activity in HARD_RUNS
        or (session.hr_zone_max or 0) >= 4
        or (session.effort or 0) >= 7
        or (
            session.activity
            in {
                Activity.RECOVERY_RUN,
                Activity.EASY_RUN,
                Activity.LONG_RUN,
                Activity.HIKE,
                Activity.CYCLE,
            }
            and (session.duration_min or 0) >= 90
        )
    )


def recovery_days(session: Session) -> int:
    """Use larger calendar buffers for performance events and long demanding outings."""
    if not is_demanding(session):
        return 0
    return (
        3
        if session.activity == Activity.RACE or (session.duration_min or 0) >= 120
        else 2
    )
