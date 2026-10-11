"""Verify persistence identities and compatibility with the existing schema."""

from contextlib import closing
from datetime import date

from training_planner.domain.models import Activity, Session
from training_planner.storage.db import connect, list_sessions, save_session


def test_saved_identifier_can_be_used_for_an_update(tmp_path):
    """Retaining the returned identifier permits updates instead of duplicate inserts."""
    with closing(connect(tmp_path / "training.db")) as conn:
        with conn:
            saved = save_session(conn, Session(date(2026, 10, 5), Activity.EASY_RUN))
        assert saved.id is not None
        saved.notes = "Updated"
        with conn:
            save_session(conn, saved)
        sessions = list_sessions(conn, saved.day, saved.day)
        assert len(sessions) == 1
        assert sessions[0].notes == "Updated"
