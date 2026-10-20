"""Application operations shared by HTTP routes and future interfaces."""

from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from math import isfinite
from pathlib import Path

from training_planner.domain.models import (
    Activity,
    ActivityWeekdays,
    ProposalMove,
    Session,
    Status,
    TrainingTargets,
)
from training_planner.domain.running import validate_zone_target
from training_planner.planner.rules import suggest_week
from training_planner.storage.db import (
    connect,
    delete_session,
    list_sessions,
    save_session,
    set_session_status,
)


class ProposalConflict(ValueError):
    """Indicate that selected proposals no longer match the available calendar."""


def _planning_date() -> date:
    """Return the backend host's local calendar date.

    Returns
    -------
    date
        Inclusive date cutoff for saving upcoming workouts and suggestions.
    """
    return date.today()


def get_sessions(path: Path, start: date, end: date) -> list[Session]:
    """Read the saved calendar for an inclusive date range.

    Parameters
    ----------
    path : Path
        Database file location.
    start : date
        First included date.
    end : date
        Last included date.

    Returns
    -------
    list[Session]
        Sessions ordered by date and identifier.

    Raises
    ------
    ValueError
        If end precedes start or stored session values are invalid.
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database operation fails.
    """
    if end < start:
        raise ValueError("end must be on or after start")
    with closing(connect(path)) as conn:
        return list_sessions(conn, start, end)


def create_session(path: Path, session: Session) -> Session:
    """Store a new manually entered workout.

    Parameters
    ----------
    path : Path
        Database file location.
    session : Session
        New workout with no database identifier and optional metrics.

    Returns
    -------
    Session
        Committed workout with its generated identifier.

    Raises
    ------
    ValueError
        If an identifier is supplied, metrics are invalid, or an upcoming workout
        is dated before today.
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database operation fails.
    """
    _validate_session(session)
    if session.id is not None:
        raise ValueError("A new session must not have an id")
    with closing(connect(path)) as conn, conn:
        return save_session(conn, session)


def _validate_planning_day(day: date, status: Status) -> None:
    """Allow upcoming workouts only from the host's current local date onward."""
    if status in (Status.PLANNED, Status.CONFIRMED) and day < _planning_date():
        raise ValueError("Planned and confirmed activities must be dated today or later")


def _validate_session(session: Session) -> None:
    """Validate workout dates and optional metrics for creation and editing."""
    _validate_planning_day(session.day, session.status)
    validate_zone_target(session.hr_zone_min, session.hr_zone_max)
    for name, value in (
        ("actual_duration_min", session.actual_duration_min),
        ("distance_km", session.distance_km),
        ("elevation_gain_m", session.elevation_gain_m),
        ("active_calories_kcal", session.active_calories_kcal),
    ):
        if value is not None and (not isfinite(value) or value < 0):
            raise ValueError(f"{name} must be a finite nonnegative number")
    if session.actual_duration_min is not None and session.actual_duration_min > 1440:
        raise ValueError("actual_duration_min must be between 0 and 1440")
    if session.average_hr_bpm is not None and not 1 <= session.average_hr_bpm <= 300:
        raise ValueError("average_hr_bpm must be between 1 and 300")
    if session.duration_min is not None and not 0 <= session.duration_min <= 1440:
        raise ValueError("duration_min must be between 0 and 1440")
    if session.effort is not None and not 1 <= session.effort <= 10:
        raise ValueError("effort must be between 1 and 10")


def update_session(path: Path, session_id: int, session: Session) -> Session:
    """Replace a saved workout, preserving its identifier and all other records.

    Raise LookupError for missing records and ValueError for invalid dates, metrics
    or a body-supplied identifier. The update is committed in one transaction.
    """
    _validate_session(session)
    if session.id is not None:
        raise ValueError("The session identifier must be supplied separately")
    with closing(connect(path)) as conn, conn:
        return save_session(conn, replace(session, id=session_id))


def change_session_status(path: Path, session_id: int, status: Status) -> Session:
    """Update status, rejecting past upcoming workouts and missing identifiers."""
    with closing(connect(path)) as conn, conn:
        # Validate while the write lock is held; failures roll back the status change.
        session = set_session_status(conn, session_id, status)
        _validate_planning_day(session.day, session.status)
        return session


def remove_session(path: Path, session_id: int) -> None:
    """Commit deletion of a saved workout, raising LookupError if it is missing."""
    with closing(connect(path)) as conn, conn:
        if not delete_session(conn, session_id):
            raise LookupError(f"Session {session_id} does not exist")


def _suggest_with_moves(
    week_start: date,
    existing: list[Session],
    blocked: set[date],
    weeks: int,
    not_before: date,
    moves: list[ProposalMove],
    dismissed: set[date],
    targets: TrainingTargets,
    weekdays: ActivityWeekdays,
    excluded: set[tuple[date, Activity]],
) -> list[Session]:
    """Reserve explicit draft positions and plan around them without saving them.

    Manual draft positions follow the same user control as manually added sessions;
    they may override preferred weekdays and recovery spacing. Other suggestions
    still account for their workload. Both original and destination dates must be
    inside the planning horizon. Destinations must be future and available; another
    activity on the same date is allowed. Recurring allowed weekdays still apply.
    """
    end = week_start + timedelta(days=7 * weeks - 1)
    origins: set[tuple[date, Activity]] = set()
    occupied = {(s.day, s.activity) for s in existing if s.status != Status.SKIPPED}
    pinned: list[Session] = []
    for move in moves:
        session = move.session
        if (
            (move.original_day, session.activity) in origins
            or not week_start <= move.original_day <= end
            or not max(week_start, not_before) <= session.day <= end
            or session.day in blocked
            or not weekdays.allows(session.day, session.activity)
            or (session.day, session.activity) in occupied
            or session.status != Status.PLANNED
            or session.id is not None
        ):
            raise ProposalConflict(
                "A moved suggestion is unavailable; change its date or start a new plan"
            )
        origins.add((move.original_day, session.activity))
        occupied.add((session.day, session.activity))
        pinned.append(session)
    generated = suggest_week(
        week_start,
        existing + pinned,
        blocked | dismissed,
        not_before=not_before,
        targets=targets,
        weekdays=weekdays,
        excluded=origins | excluded,
    )
    return sorted(
        pinned + generated, key=lambda session: (session.day, session.activity.value)
    )


def generate_proposals(
    path: Path,
    week_start: date,
    blocked: set[date],
    weeks: int = 4,
    moves: list[ProposalMove] | None = None,
    dismissed: set[date] | None = None,
    targets: TrainingTargets = TrainingTargets(),
    weekdays: ActivityWeekdays = ActivityWeekdays(),
    excluded: set[tuple[date, Activity]] | None = None,
) -> list[Session]:
    """Generate a preview without saving any proposed workouts.

    Dates before the backend host's current local date are excluded.

    Parameters
    ----------
    path : Path
        Database file location.
    week_start : date
        Inclusive start date of the rolling horizon, on any weekday.
    weeks : int
        Fixed four-week (28-day) planning horizon.
    blocked : set[date]
        Ephemeral whole-day restrictions for this planning request.
    moves : list[ProposalMove] | None
        Explicit unsaved draft positions to retain during generation.
    dismissed : set[date] | None
        Dates excluded from automatic suggestions in this preview.

    targets : TrainingTargets
        Soft counts per seven-day period; intervals are part of total runs.
    weekdays : ActivityWeekdays
        Recurring allowed weekdays used for generation and draft moves.
    excluded : set[tuple[date, Activity]] | None
        Individual workout exclusions, preserving other same-day activities.

    Returns
    -------
    list[Session]
        Unsaved suggestions from the target and recovery rules.

    Raises
    ------
    ValueError
        If the horizon or stored session values are invalid.
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database operation fails.
    """
    if weeks != 4:
        raise ValueError("weeks must be 4 (28 days)")
    existing = get_sessions(
        path, week_start - timedelta(days=7), week_start + timedelta(days=7 * weeks + 6)
    )
    return _suggest_with_moves(
        week_start,
        existing,
        blocked,
        weeks,
        _planning_date(),
        moves or [],
        dismissed or set(),
        targets,
        weekdays,
        excluded or set(),
    )


def accept_proposals(
    path: Path,
    week_start: date,
    blocked: set[date],
    proposals: list[Session],
    weeks: int = 4,
    moves: list[ProposalMove] | None = None,
    dismissed: set[date] | None = None,
    confirm: bool = False,
    targets: TrainingTargets = TrainingTargets(),
    weekdays: ActivityWeekdays = ActivityWeekdays(),
    excluded: set[tuple[date, Activity]] | None = None,
) -> list[Session]:
    """Revalidate selected suggestions and commit the entire selection atomically.

    The current local date is checked again so previews can expire overnight.

    Parameters
    ----------
    path : Path
        Database file location.
    week_start : date
        Inclusive start date used to generate the preview.
    blocked : set[date]
        Whole-day restrictions used to generate the preview.
    weeks : int
        Same fixed four-week horizon used for the preview.
    proposals : list[Session]
        Unmodified suggestions selected for acceptance; an empty list is allowed.
    moves : list[ProposalMove] | None
        Same explicit draft positions used during generation.
    dismissed : set[date] | None
        Same excluded suggestion dates used during generation.
    confirm : bool
        Save validated suggestions as confirmed upcoming workouts when true.
    targets : TrainingTargets
        Same training targets used for the preview.
    weekdays : ActivityWeekdays
        Recurring allowed weekdays used for generation and draft moves.
    excluded : set[tuple[date, Activity]] | None
        Same per-workout exclusions used for the preview.

    Returns
    -------
    list[Session]
        Committed sessions with generated identifiers.

    Raises
    ------
    ProposalConflict
        If selected suggestions are duplicated, altered, elapsed, or no longer available.
    ValueError
        If the horizon or stored session values are invalid.
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database operation fails; the entire selection is rolled back.
    """
    if weeks != 4:
        raise ValueError("weeks must be 4 (28 days)")
    with closing(connect(path)) as conn, conn:
        # Reserve the write transaction before reading so competing requests
        # cannot book a proposed date between validation and insertion.
        conn.execute("BEGIN IMMEDIATE")
        existing = list_sessions(
            conn,
            week_start - timedelta(days=7),
            week_start + timedelta(days=7 * weeks + 6),
        )
        not_before = _planning_date()
        if any(session.day < not_before for session in proposals):
            raise ProposalConflict(
                "Some selected dates have elapsed; generate suggestions again"
            )
        available = _suggest_with_moves(
            week_start,
            existing,
            blocked,
            weeks,
            not_before,
            moves or [],
            dismissed or set(),
            targets,
            weekdays,
            excluded or set(),
        )
        if len({(s.day, s.activity) for s in proposals}) != len(proposals):
            raise ProposalConflict(
                "Duplicate proposed workouts; generate suggestions again"
            )
        if any(session not in available for session in proposals):
            # After midnight, replacement runs can occupy dates that were empty
            # in the preview and change the gym ranking. Also allow the complete
            # selection from the original-date layout, rechecked against current
            # bookings. Never combine drafts from the two different layouts.
            original_layout = (
                _suggest_with_moves(
                    week_start,
                    existing,
                    blocked,
                    weeks,
                    week_start,
                    moves or [],
                    dismissed or set(),
                    targets,
                    weekdays,
                    excluded or set(),
                )
                if not_before > week_start
                else []
            )
            if any(session not in original_layout for session in proposals):
                raise ProposalConflict(
                    "The calendar or proposals changed; generate suggestions again"
                )
        return [
            save_session(
                conn, replace(session, status=Status.CONFIRMED) if confirm else session
            )
            for session in proposals
        ]
