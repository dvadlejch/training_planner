"""Application operations shared by HTTP routes and future interfaces."""

from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from math import isfinite
from pathlib import Path

from training_planner.domain.models import ProposalMove, Session, Status
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
        Inclusive date cutoff for generating or accepting suggestions.
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
        If an identifier is supplied or metrics are outside their allowed ranges.
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


def _validate_session(session: Session) -> None:
    """Validate optional workout metrics for both creation and editing."""
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

    Raise LookupError for missing records and ValueError for invalid metrics or
    a body-supplied identifier. The update is committed in one transaction.
    """
    _validate_session(session)
    if session.id is not None:
        raise ValueError("The session identifier must be supplied separately")
    with closing(connect(path)) as conn, conn:
        return save_session(conn, replace(session, id=session_id))


def change_session_status(path: Path, session_id: int, status: Status) -> Session:
    """Commit a status-only update, raising LookupError for a missing workout."""
    with closing(connect(path)) as conn, conn:
        return set_session_status(conn, session_id, status)


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
) -> list[Session]:
    """Reserve explicit draft positions and plan around them without saving them.

    Manual draft positions follow the same user control as manually added sessions;
    they may override preferred weekdays and recovery spacing. Other suggestions
    still account for their workload. Both original and destination dates must be
    inside the planning horizon, and destinations must be future, free and available.
    """
    end = week_start + timedelta(days=7 * weeks - 1)
    origins: set[date] = set()
    occupied = {session.day for session in existing} | blocked
    pinned: list[Session] = []
    for move in moves:
        session = move.session
        if (
            move.original_day in origins
            or not week_start <= move.original_day <= end
            or not max(week_start, not_before) <= session.day <= end
            or session.day in occupied
            or session.status != Status.PLANNED
            or session.id is not None
        ):
            raise ProposalConflict(
                "A moved suggestion is unavailable; change its date or start a new plan"
            )
        origins.add(move.original_day)
        occupied.add(session.day)
        pinned.append(session)
    generated = suggest_week(
        week_start,
        existing + pinned,
        blocked | origins | dismissed,
        not_before=not_before,
        weeks=weeks,
    )
    return sorted(pinned + generated, key=lambda session: session.day)


def generate_proposals(
    path: Path,
    week_start: date,
    blocked: set[date],
    weeks: int = 1,
    moves: list[ProposalMove] | None = None,
    dismissed: set[date] | None = None,
) -> list[Session]:
    """Generate a preview without saving any proposed workouts.

    Dates before the backend host's current local date are excluded.

    Parameters
    ----------
    path : Path
        Database file location.
    week_start : date
        Monday starting the requested week.
    weeks : int
        Planning horizon, from one to four weeks.
    blocked : set[date]
        Ephemeral whole-day restrictions for this planning request.
    moves : list[ProposalMove] | None
        Explicit unsaved draft positions to retain during generation.
    dismissed : set[date] | None
        Dates excluded from automatic suggestions in this preview.

    Returns
    -------
    list[Session]
        Unsaved suggestions from the existing starter rules.

    Raises
    ------
    ValueError
        If week_start is not a Monday or stored session values are invalid.
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database operation fails.
    """
    if not 1 <= weeks <= 4:
        raise ValueError("weeks must be between 1 and 4")
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
    )


def accept_proposals(
    path: Path,
    week_start: date,
    blocked: set[date],
    proposals: list[Session],
    weeks: int = 1,
    moves: list[ProposalMove] | None = None,
    dismissed: set[date] | None = None,
) -> list[Session]:
    """Revalidate selected suggestions and commit the entire selection atomically.

    The current local date is checked again so previews can expire overnight.

    Parameters
    ----------
    path : Path
        Database file location.
    week_start : date
        Monday used to generate the preview.
    blocked : set[date]
        Whole-day restrictions used to generate the preview.
    weeks : int
        Same one-to-four-week horizon used for the preview.
    proposals : list[Session]
        Unmodified suggestions selected for acceptance; an empty list is allowed.
    moves : list[ProposalMove] | None
        Same explicit draft positions used during generation.
    dismissed : set[date] | None
        Same excluded suggestion dates used during generation.

    Returns
    -------
    list[Session]
        Committed sessions with generated identifiers.

    Raises
    ------
    ProposalConflict
        If selected suggestions are duplicated, altered, elapsed, or no longer available.
    ValueError
        If week_start is not a Monday or stored session values are invalid.
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database operation fails; the entire selection is rolled back.
    """
    if not 1 <= weeks <= 4:
        raise ValueError("weeks must be between 1 and 4")
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
        )
        if len({session.day for session in proposals}) != len(proposals):
            raise ProposalConflict(
                "Duplicate proposed dates; generate suggestions again"
            )
        if any(session not in available for session in proposals):
            raise ProposalConflict(
                "The calendar or proposals changed; generate suggestions again"
            )
        return [save_session(conn, session) for session in proposals]
