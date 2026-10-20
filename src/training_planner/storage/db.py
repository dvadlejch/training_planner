"""SQLite session repository; callers own write transactions."""

import json
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

from training_planner.domain.models import Activity, MuscleGroup, Session, Status

DEFAULT_DB = Path("data/training.db")


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open the local database and initialize the current session schema.

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
            notes TEXT NOT NULL DEFAULT '',
            hr_zone_min INTEGER,
            hr_zone_max INTEGER,
            actual_duration_min REAL,
            distance_km REAL,
            average_hr_bpm INTEGER,
            elevation_gain_m REAL,
            active_calories_kcal REAL,
            muscle_groups TEXT NOT NULL DEFAULT '[]'
        )""")
        # Upgrade the preceding session schema without discarding saved workouts.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
        if "muscle_groups" not in columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN muscle_groups "
                "TEXT NOT NULL DEFAULT '[]'"
            )
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
        session.hr_zone_min,
        session.hr_zone_max,
        session.actual_duration_min,
        session.distance_km,
        session.average_hr_bpm,
        session.elevation_gain_m,
        session.active_calories_kcal,
        json.dumps([group.value for group in session.muscle_groups]),
    )
    if session.id is None:
        cursor = conn.execute(
            "INSERT INTO sessions (day, activity, status, duration_min, effort, notes, "
            "hr_zone_min, hr_zone_max, actual_duration_min, distance_km, "
            "average_hr_bpm, elevation_gain_m, active_calories_kcal, muscle_groups) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        return replace(session, id=cursor.lastrowid)
    cursor = conn.execute(
        "UPDATE sessions SET day=?, activity=?, status=?, "
        "duration_min=?, effort=?, notes=?, "
        "hr_zone_min=?, hr_zone_max=?, actual_duration_min=?, distance_km=?, "
        "average_hr_bpm=?, elevation_gain_m=?, active_calories_kcal=?, muscle_groups=? "
        "WHERE id=?",
        (*values, session.id),
    )
    if cursor.rowcount != 1:
        raise LookupError(f"Session {session.id} does not exist")
    return replace(session)


def delete_session(conn: sqlite3.Connection, session_id: int) -> bool:
    """Delete one saved session without committing the caller's transaction.

    Return whether the identifier existed. Other sessions are left untouched.
    """
    cursor = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    return cursor.rowcount == 1


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
    return [_session_from_row(row) for row in rows]


def _session_from_row(row: sqlite3.Row) -> Session:
    """Decode one saved workout using the same contract for reads and updates."""
    return Session(
        id=row["id"],
        day=date.fromisoformat(row["day"]),
        activity=Activity(row["activity"]),
        status=Status(row["status"]),
        duration_min=row["duration_min"],
        effort=row["effort"],
        notes=row["notes"],
        hr_zone_min=row["hr_zone_min"],
        hr_zone_max=row["hr_zone_max"],
        actual_duration_min=row["actual_duration_min"],
        distance_km=row["distance_km"],
        average_hr_bpm=row["average_hr_bpm"],
        elevation_gain_m=row["elevation_gain_m"],
        active_calories_kcal=row["active_calories_kcal"],
        muscle_groups=[MuscleGroup(value) for value in json.loads(row["muscle_groups"])],
    )


def set_session_status(
    conn: sqlite3.Connection, session_id: int, status: Status
) -> Session:
    """Update only status within the caller's transaction, or raise LookupError.

    The write lock keeps the subsequent read consistent until the caller commits.
    """
    cursor = conn.execute(
        "UPDATE sessions SET status=? WHERE id=?", (status.value, session_id)
    )
    if cursor.rowcount != 1:
        raise LookupError(f"Session {session_id} does not exist")
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    return _session_from_row(row)
