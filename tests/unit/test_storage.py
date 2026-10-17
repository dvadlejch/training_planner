"""Verify persistence identities and the current session schema."""

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


def test_zone_targets_survive_update_and_reopening(tmp_path):
    """Preserve updated heart-rate zone targets after reopening the database."""
    path = tmp_path / "training.db"
    day = date(2026, 10, 5)
    with closing(connect(path)) as conn:
        with conn:
            saved = save_session(
                conn,
                Session(
                    day,
                    Activity.INTERVAL_RUN,
                    hr_zone_min=4,
                    hr_zone_max=5,
                ),
            )
        saved.hr_zone_min = saved.hr_zone_max = 2
        with conn:
            save_session(conn, saved)
    with closing(connect(path)) as conn:
        sessions = list_sessions(conn, day, day)
        assert len(sessions) == 1
        assert sessions[0].id == saved.id
        assert sessions[0].hr_zone_min == sessions[0].hr_zone_max == 2
