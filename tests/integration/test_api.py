"""Verify API boundaries and transactional proposal acceptance."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from training_planner.api.app import create_app
from training_planner.application.services import accept_proposals, generate_proposals, get_sessions


@pytest.fixture
def client(tmp_path):
    """Use a separate database for each API test."""
    with TestClient(create_app(tmp_path / "training.db")) as test_client:
        yield test_client


def test_session_round_trip_preserves_unknown_metrics(client):
    """Unknown metrics remain null and saved sessions receive identifiers."""
    response = client.post("/api/sessions", json={"day": "2026-10-06", "activity": "gym"})
    assert response.status_code == 201
    saved = response.json()
    assert isinstance(saved["id"], int)
    assert saved["duration_min"] is None
    assert saved["effort"] is None
    response = client.get("/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"})
    assert response.json() == [saved]


def test_preview_is_not_persisted_and_acceptance_is_explicit(client):
    """Generating suggestions leaves storage untouched until acceptance."""
    request = {"week_start": "2026-10-05", "blocked": ["2026-10-06"]}
    response = client.post("/api/proposals", json=request)
    assert response.status_code == 200
    preview = response.json()
    assert preview and all(item["id"] is None for item in preview)
    assert all(item["day"] != "2026-10-06" for item in preview)
    assert (
        client.get("/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}).json()
        == []
    )
    proposals = [{key: value for key, value in item.items() if key != "id"} for item in preview]
    response = client.post("/api/proposals/accept", json={**request, "proposals": proposals})
    assert response.status_code == 201
    assert all(isinstance(item["id"], int) for item in response.json())


def test_stale_batch_is_rejected_without_partial_acceptance(client):
    """An intervening booking prevents the whole outdated batch from being saved."""
    request = {"week_start": "2026-10-05", "blocked": []}
    preview = client.post("/api/proposals", json=request).json()
    booking = client.post(
        "/api/sessions", json={"day": preview[-1]["day"], "activity": "cycle"}
    ).json()
    proposals = [{key: value for key, value in item.items() if key != "id"} for item in preview]
    response = client.post("/api/proposals/accept", json={**request, "proposals": proposals})
    assert response.status_code == 409
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
    ).json() == [booking]


def test_batch_rolls_back_when_a_write_fails(tmp_path, monkeypatch):
    """A failure during insertion rolls back previously inserted proposals."""
    path = tmp_path / "training.db"
    monday = date(2026, 10, 5)
    proposals = generate_proposals(path, monday, set())
    from training_planner.application import services

    original = services.save_session
    calls = 0

    def fail_second_write(conn, session):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Simulated write failure")
        return original(conn, session)

    monkeypatch.setattr(services, "save_session", fail_second_write)
    with pytest.raises(RuntimeError, match="Simulated"):
        accept_proposals(path, monday, set(), proposals)
    assert get_sessions(path, monday, date(2026, 10, 11)) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"duration_min": -1},
        {"duration_min": 1441},
        {"effort": 0},
        {"effort": 11},
        {"activity": "unknown"},
        {"status": "unknown"},
        {"id": 5},
    ],
)
def test_invalid_session_input_is_rejected(client, payload):
    """Validate metrics, enums, and ownership of database identifiers at the API."""
    response = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym", **payload}
    )
    assert response.status_code == 422


def test_invalid_week_and_reversed_range_are_rejected(client):
    """Reject a non-Monday planning start and a reversed query interval."""
    assert client.post("/api/proposals", json={"week_start": "2026-10-06"}).status_code == 422
    assert (
        client.get("/api/sessions", params={"start": "2026-10-11", "end": "2026-10-05"}).status_code
        == 422
    )


def test_fully_blocked_week_and_empty_acceptance_are_valid(client):
    """A rest week and declining every suggestion are valid workflows."""
    request = {"week_start": "2026-10-05", "blocked": [f"2026-10-{day:02}" for day in range(5, 12)]}
    assert client.post("/api/proposals", json=request).json() == []
    response = client.post("/api/proposals/accept", json={**request, "proposals": []})
    assert response.status_code == 201
    assert response.json() == []


def test_duplicate_and_altered_proposals_are_rejected(client):
    """Acceptance only permits distinct, unmodified suggestions from the current rules."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()[0]
    preview.pop("id")
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": [preview, preview]}
        ).status_code
        == 409
    )
    preview["notes"] = "Altered"
    assert (
        client.post("/api/proposals/accept", json={**request, "proposals": [preview]}).status_code
        == 409
    )


def test_acceptance_preserves_existing_completed_session(client):
    """Accepting new proposals preserves completed records and their metrics."""
    saved = client.post(
        "/api/sessions",
        json={
            "day": "2026-10-06",
            "activity": "gym",
            "status": "completed",
            "effort": 8,
        },
    ).json()
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    proposals = [{key: value for key, value in item.items() if key != "id"} for item in preview]
    assert (
        client.post("/api/proposals/accept", json={**request, "proposals": proposals}).status_code
        == 201
    )
    sessions = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
    ).json()
    assert saved in sessions


def test_api_construction_and_health_do_not_create_database(tmp_path):
    """Importing or checking health does not create an application database."""
    path = tmp_path / "unused.db"
    with TestClient(create_app(path)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
    assert not path.exists()
