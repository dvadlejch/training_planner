"""Cover optional gym targets through validation, persistence and editing."""

from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from training_planner.api.app import create_app
from training_planner.application import services
from training_planner.application.services import create_session
from training_planner.domain.models import Activity, MuscleGroup, Session
from training_planner.storage.db import connect, list_sessions, save_session


@pytest.fixture(autouse=True)
def planning_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Freeze the clock so upcoming-session checks do not age fixed test dates."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 20))


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


@pytest.mark.parametrize("reverse", [False, True])
def test_custom_gym_split_generation_and_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reverse: bool
) -> None:
    """Generate custom groups, then persist every original proposal in either order."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    split = {"chest": ["biceps"], "back": ["shoulders"], "legs": ["triceps", "abs"]}
    request = {"week_start": "2026-10-05", "gym_split": split}
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        response = client.post("/api/proposals", json=request)
        assert response.status_code == 200
        preview = response.json()
        gyms = [s for s in preview if s["activity"] == "gym"]
        assert len(gyms) == 12
        primaries = ["chest", "back", "legs"]
        assert {gym["muscle_groups"][0] for gym in gyms} == set(primaries)
        for gym in gyms:
            primary = gym["muscle_groups"][0]
            assert gym["muscle_groups"] == [primary, *split[primary]]
        params = {"start": "2026-10-05", "end": "2026-11-01"}
        assert client.get("/api/sessions", params=params).json() == []
        for session in reversed(preview) if reverse else preview:
            proposal = {key: value for key, value in session.items() if key != "id"}
            accepted = client.post(
                "/api/proposals/accept",
                json={**request, "proposals": [proposal], "confirm": True},
            )
            assert accepted.status_code == 201, accepted.text
            assert accepted.json()[0]["muscle_groups"] == session["muscle_groups"]
        saved = client.get("/api/sessions", params=params).json()
        assert {(s["day"], s["activity"]): s["muscle_groups"] for s in saved} == {
            (s["day"], s["activity"]): s["muscle_groups"] for s in preview
        }


@pytest.mark.parametrize(
    "split",
    [
        {"chest": ["legs"]},
        {"back": ["shoulders", "shoulders"]},
        {"legs": ["unknown"]},
        {"chest": None},
        {"other": []},
    ],
)
def test_api_rejects_invalid_gym_split(tmp_path: Path, split: dict[str, object]) -> None:
    """Validate custom splits on both generation and acceptance before writing data."""
    request = {"week_start": "2026-10-05", "gym_split": split}
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        assert client.post("/api/proposals", json=request).status_code == 422
        response = client.post(
            "/api/proposals/accept", json={**request, "proposals": []}
        )
        assert response.status_code == 422


def test_planning_resumes_from_history_outside_recovery_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resume after old Back work despite newer skipped, generic and abs-only gyms."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        for day, status, groups in [
            ("2026-08-01", "completed", ["back", "triceps"]),
            ("2026-09-01", "skipped", ["legs"]),
            ("2026-09-03", "completed", []),
            ("2026-10-01", "completed", ["abs"]),
        ]:
            response = client.post(
                "/api/sessions",
                json={
                    "day": day,
                    "activity": "gym",
                    "status": status,
                    "muscle_groups": groups,
                },
            )
            assert response.status_code == 201
        request = {"week_start": "2026-10-05"}
        response = client.post("/api/proposals", json=request)
        assert response.status_code == 200
        gym = next(s for s in response.json() if s["activity"] == "gym")
        assert gym["muscle_groups"] == ["legs", "biceps", "abs"]
        proposal = {key: value for key, value in gym.items() if key != "id"}
        response = client.post(
            "/api/proposals/accept", json={**request, "proposals": [proposal]}
        )
        assert response.status_code == 201, response.text


def test_changed_split_rejects_stale_proposals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do not silently accept muscle targets from a different set of split settings."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        request = {"week_start": "2026-10-05"}
        preview = client.post("/api/proposals", json=request).json()
        gym = next(s for s in preview if s["activity"] == "gym")
        proposal = {key: value for key, value in gym.items() if key != "id"}
        response = client.post(
            "/api/proposals/accept",
            json={
                **request,
                "gym_split": {"chest": ["biceps"]},
                "proposals": [proposal],
            },
        )
        assert response.status_code == 409


def test_moved_draft_keeps_custom_muscles_through_recalculation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retain an explicit draft's targets while calculating and accepting around it."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    request: dict[str, object] = {
        "week_start": "2026-10-05",
        "gym_split": {"chest": ["biceps"]},
    }
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        preview = client.post("/api/proposals", json=request).json()
        gym = next(s for s in preview if s["activity"] == "gym")
        moved = {key: value for key, value in gym.items() if key != "id"}
        moved["day"] = "2026-10-05"
        request["moves"] = [{"original_day": gym["day"], "session": moved}]
        response = client.post("/api/proposals", json=request)
        assert response.status_code == 200
        assert {**moved, "id": None} in response.json()
        response = client.post(
            "/api/proposals/accept", json={**request, "proposals": [moved]}
        )
        assert response.status_code == 201, response.text
        assert response.json()[0]["muscle_groups"] == ["chest", "biceps"]


@pytest.mark.parametrize("new_activity", ["cycle", "interval_run", "hike"])
def test_new_neighboring_endurance_invalidates_a_leg_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, new_activity: str
) -> None:
    """Recheck spacing before accepting an old leg draft after a new nearby booking."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    request = {"week_start": "2026-10-05"}
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        preview = client.post("/api/proposals", json=request).json()
        gym = next(s for s in preview if "legs" in s["muscle_groups"])
        assert gym["day"] == "2026-10-08"
        proposal = {key: value for key, value in gym.items() if key != "id"}
        saved = client.post(
            "/api/sessions",
            json={
                "day": "2026-10-09",
                "activity": new_activity,
            },
        ).json()
        response = client.post(
            "/api/proposals/accept", json={**request, "proposals": [proposal]}
        )
        assert response.status_code == 409
        response = client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        )
        assert response.json() == [saved]


def test_new_saved_legs_invalidates_neighboring_hike_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject an old hike proposal beside newly saved legs without moving the gym."""
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    request = {"week_start": "2026-10-05"}
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        preview = client.post("/api/proposals", json=request).json()
        hike = next(s for s in preview if s["activity"] == "hike")
        proposal = {key: value for key, value in hike.items() if key != "id"}
        saved = client.post(
            "/api/sessions",
            json={
                "day": "2026-10-09",
                "activity": "gym",
                "muscle_groups": ["legs"],
            },
        ).json()
        response = client.post(
            "/api/proposals/accept", json={**request, "proposals": [proposal]}
        )
        assert response.status_code == 409
        assert saved["day"] == "2026-10-09"
        assert saved["muscle_groups"] == ["legs"]


def test_rotation_history_retains_deferred_leg_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the last target for every primary group after a long break in training.

    Legs were trained before Back and Chest. Keeping only the most recent Chest
    entry would restart at Back and lose the overdue leg target. All entries are
    outside the neighboring recovery window.
    """
    monkeypatch.setattr(services, "_planning_date", lambda: date(2026, 10, 5))
    with TestClient(create_app(tmp_path / "planning.db")) as client:
        for day, group in [
            ("2026-08-01", "legs"),
            ("2026-08-03", "back"),
            ("2026-08-04", "chest"),
        ]:
            response = client.post(
                "/api/sessions",
                json={
                    "day": day,
                    "activity": "gym",
                    "status": "completed",
                    "muscle_groups": [group],
                },
            )
            assert response.status_code == 201
        response = client.post("/api/proposals", json={"week_start": "2026-10-05"})
        assert response.status_code == 200
        first = next(s for s in response.json() if s["activity"] == "gym")
        assert first["muscle_groups"] == ["legs", "biceps", "abs"]
