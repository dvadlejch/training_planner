"""Cover optional gym targets through validation, persistence and editing."""

from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from training_planner.api.app import create_app
from training_planner.application.services import create_session
from training_planner.domain.models import Activity, MuscleGroup, Session
from training_planner.storage.db import connect, list_sessions, save_session


def test_muscle_groups_round_trip_and_clear(tmp_path: Path) -> None:
    """Retain every group across edits, moves, status updates and database reopening."""
    path = tmp_path / "gym.db"
    groups = [group.value for group in MuscleGroup]
    payload = {"day": "2026-10-20", "activity": "gym", "muscle_groups": groups}
    with TestClient(create_app(path)) as client:
        response = client.post("/api/sessions", json=payload)
        assert response.status_code == 201
        saved = response.json()
        assert saved["muscle_groups"] == groups
        url = f"/api/sessions/{saved['id']}"
        moved = {**payload, "day": "2026-10-21", "muscle_groups": ["legs", "abs"]}
        response = client.put(url, json=moved)
        assert response.status_code == 200
        assert response.json()["muscle_groups"] == ["legs", "abs"]
        response = client.patch(f"{url}/status", json={"status": "completed"})
        assert response.status_code == 200
        assert response.json()["muscle_groups"] == ["legs", "abs"]
    with TestClient(create_app(path)) as client:
        response = client.get(
            "/api/sessions", params={"start": "2026-10-21", "end": "2026-10-21"}
        )
        assert response.json()[0]["muscle_groups"] == ["legs", "abs"]
        response = client.put(url, json={**moved, "muscle_groups": []})
        assert response.status_code == 200
        assert response.json()["muscle_groups"] == []
        response = client.post(
            "/api/sessions", json={"day": "2026-10-22", "activity": "gym"}
        )
        assert response.json()["muscle_groups"] == []


@pytest.mark.parametrize(
    ("activity", "groups"),
    [("gym", ["unknown"]), ("gym", ["legs", "legs"]), ("easy_run", ["abs"])],
)
def test_invalid_muscle_groups_are_rejected(
    tmp_path: Path, activity: str, groups: list[str]
) -> None:
    """Reject unknown, duplicate and non-gym targets without altering saved data."""
    with TestClient(create_app(tmp_path / "gym.db")) as client:
        payload = {"day": "2026-10-20", "activity": "gym", "muscle_groups": ["chest"]}
        saved = client.post("/api/sessions", json=payload).json()
        invalid = {**payload, "activity": activity, "muscle_groups": groups}
        assert client.post("/api/sessions", json=invalid).status_code == 422
        assert (
            client.put(f"/api/sessions/{saved['id']}", json=invalid).status_code == 422
        )
        response = client.get(
            "/api/sessions", params={"start": "2026-10-20", "end": "2026-10-20"}
        )
        assert response.json() == [saved]


def test_preceding_database_schema_preserves_sessions(tmp_path: Path) -> None:
    """Upgrade the preceding schema once and retain existing workout identities."""
    path = tmp_path / "previous.db"
    day = date(2026, 10, 20)
    with closing(connect(path)) as conn, conn:
        saved = save_session(conn, Session(day, Activity.GYM, notes="Keep my workout"))
        conn.execute("ALTER TABLE sessions DROP COLUMN muscle_groups")
    for _ in range(2):
        with closing(connect(path)) as conn:
            assert list_sessions(conn, day, day) == [saved]
    with closing(connect(path)) as conn, conn:
        saved.muscle_groups = [MuscleGroup.BACK, MuscleGroup.BICEPS]
        save_session(conn, saved)
    with closing(connect(path)) as conn:
        assert list_sessions(conn, day, day) == [saved]


def test_service_rejects_non_gym_targets(tmp_path: Path) -> None:
    """Enforce gym-only targets for application callers outside the HTTP boundary."""
    with pytest.raises(ValueError, match="only.*gym"):
        create_session(
            tmp_path / "gym.db",
            Session(
                date(2026, 10, 20), Activity.EASY_RUN, muscle_groups=[MuscleGroup.ABS]
            ),
        )
