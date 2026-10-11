"""SQLite session repository; callers own write transactions."""

import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

from training_planner.domain.models import Activity, Session, Status

DEFAULT_DB = Path("data/training.db")


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open the local database and initialize the existing session schema.

    Parameters
    ----------
    path : Path
        Database file location; parent directories are created when needed.

    Returns
    -------
    sqlite3.Connection
        Connection with named rows; the caller must close it.

    Raises
    ------
    OSError
        If the database directory cannot be created.
    sqlite3.Error
        If the database cannot be opened or initialized.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            activity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            duration_min INTEGER,
            effort INTEGER,
            notes TEXT NOT NULL DEFAULT ''
        )""")
        conn.commit()
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def save_session(conn: sqlite3.Connection, session: Session) -> Session:
    """Insert or update a session without committing the caller's transaction.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection.
    session : Session
        Session to insert, or an existing session identified by its id.

    Returns
    -------
    Session
        Saved session with its database identifier. The input is not modified.

    Raises
    ------
    LookupError
        If an update targets a session that does not exist.
    sqlite3.Error
        If the write fails.
    """
    values = (
        session.day.isoformat(),
        session.activity.value,
        session.status.value,
        session.duration_min,
        session.effort,
        session.notes,
    )
    if session.id is None:
        cursor = conn.execute(
            "INSERT INTO sessions (day, activity, status, duration_min, effort, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            values,
        )
        return replace(session, id=cursor.lastrowid)
    cursor = conn.execute(
        "UPDATE sessions SET day=?, activity=?, status=?, duration_min=?, effort=?, notes=? "
        "WHERE id=?",
        (*values, session.id),
    )
    if cursor.rowcount != 1:
        raise LookupError(f"Session {session.id} does not exist")
    return replace(session)


def list_sessions(conn: sqlite3.Connection, start: date, end: date) -> list[Session]:
    """Read sessions within an inclusive calendar-date range.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection with named rows.
    start : date
        First included date.
    end : date
        Last included date.

    Returns
    -------
    list[Session]
        Saved sessions ordered by date and identifier.

    Raises
    ------
    sqlite3.Error
        If the query fails.
    ValueError
        If stored dates, activities, or statuses are invalid.
    """
    rows = conn.execute(
        "SELECT * FROM sessions WHERE day BETWEEN ? AND ? ORDER BY day, id",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        Session(
            id=row["id"],
            day=date.fromisoformat(row["day"]),
            activity=Activity(row["activity"]),
            status=Status(row["status"]),
            duration_min=row["duration_min"],
            effort=row["effort"],
            notes=row["notes"],
        )
        for row in rows
    ]
