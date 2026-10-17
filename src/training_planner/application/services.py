"""Application operations shared by HTTP routes and future interfaces."""

from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from training_planner.domain.models import Session
from training_planner.domain.running import validate_zone_target
from training_planner.planner.rules import suggest_week
from training_planner.storage.db import connect, list_sessions, save_session


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
    validate_zone_target(session.hr_zone_min, session.hr_zone_max)
    if session.id is not None:
        raise ValueError("A new session must not have an id")
    if session.duration_min is not None and not 0 <= session.duration_min <= 1440:
        raise ValueError("duration_min must be between 0 and 1440")
    if session.effort is not None and not 1 <= session.effort <= 10:
        raise ValueError("effort must be between 1 and 10")
    with closing(connect(path)) as conn, conn:
        return save_session(conn, session)


def generate_proposals(
    path: Path, week_start: date, blocked: set[date], weeks: int = 1
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
    return suggest_week(
        week_start, existing, blocked, not_before=_planning_date(), weeks=weeks
    )


def accept_proposals(
    path: Path,
    week_start: date,
    blocked: set[date],
    proposals: list[Session],
    weeks: int = 1,
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
        available = suggest_week(
            week_start, existing, blocked, not_before=not_before, weeks=weeks
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
