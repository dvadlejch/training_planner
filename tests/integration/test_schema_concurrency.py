"""Exercise concurrent SQLite schema upgrades without losing existing workouts."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date
from pathlib import Path
from threading import Event, current_thread

import pytest

from training_planner.domain.models import Activity, Session
from training_planner.storage import db


@pytest.mark.parametrize("journal_mode", ["delete", "wal"])
def test_concurrent_schema_upgrade_preserves_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, journal_mode: str
) -> None:
    """Concurrent connections upgrade the old schema once and retain saved workouts.

    Pause the first connection just before ALTER TABLE. Without a migration lock,
    the second connection finishes the upgrade first, reproducing the duplicate
    column error. With BEGIN IMMEDIATE, the second connection releases the pause
    before waiting for the first migration's lock. Exercise both journal modes.
    """
    path = tmp_path / "previous.db"
    day = date(2026, 10, 20)
    with closing(db.connect(path)) as conn:
        conn.execute(f"PRAGMA journal_mode={journal_mode}")
        with conn:
            saved = db.save_session(conn, Session(day, Activity.GYM, notes="Keep me"))
            conn.execute("ALTER TABLE sessions DROP COLUMN muscle_groups")

    first_at_upgrade = Event()
    release_first = Event()
    wait_expired = Event()
    original_connect = sqlite3.connect

    def observed_connect(database: Path) -> sqlite3.Connection:
        conn = original_connect(database)
        is_first = current_thread().name.startswith("first-migration")

        def trace(statement: str) -> None:
            if is_first and statement.startswith("ALTER TABLE"):
                first_at_upgrade.set()
                if not release_first.wait(timeout=10):
                    wait_expired.set()
            elif not is_first and statement == "BEGIN IMMEDIATE":
                release_first.set()

        conn.set_trace_callback(trace)
        return conn

    def read_sessions() -> list[Session]:
        with closing(db.connect(path)) as conn:
            return db.list_sessions(conn, day, day)

    def second_read() -> list[Session]:
        try:
            return read_sessions()
        finally:
            release_first.set()

    with monkeypatch.context() as patch:
        patch.setattr(db.sqlite3, "connect", observed_connect)
        with (
            ThreadPoolExecutor(thread_name_prefix="first-migration") as first_pool,
            ThreadPoolExecutor(thread_name_prefix="second-migration") as second_pool,
        ):
            first = first_pool.submit(read_sessions)
            try:
                assert first_at_upgrade.wait(timeout=10)
                second = second_pool.submit(second_read)
                assert second.result(timeout=15) == [saved]
                assert first.result(timeout=15) == [saved]
                assert not wait_expired.is_set()
            finally:
                release_first.set()

    with closing(db.connect(path)) as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(sessions)")]
        assert columns.count("muscle_groups") == 1
        assert db.list_sessions(conn, day, day) == [saved]
        assert not conn.in_transaction
