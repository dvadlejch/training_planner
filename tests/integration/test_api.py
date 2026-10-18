"""Verify API boundaries and transactional proposal acceptance."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from training_planner.api.app import create_app
from training_planner.application.services import (
    accept_proposals,
    generate_proposals,
    get_sessions,
)


@pytest.fixture(autouse=True)
def planning_clock(monkeypatch):
    """Freeze the service clock so fixed calendar dates remain deterministic."""
    from training_planner.application import services

    clock = {"today": date(2026, 10, 5)}
    monkeypatch.setattr(services, "_planning_date", lambda: clock["today"])
    return clock


@pytest.fixture
def client(tmp_path):
    """Use a separate database for each API test."""
    with TestClient(create_app(tmp_path / "training.db")) as test_client:
        yield test_client


def test_session_round_trip_preserves_unknown_metrics(client):
    """Unknown metrics remain null and saved sessions receive identifiers."""
    response = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym"}
    )
    assert response.status_code == 201
    saved = response.json()
    assert isinstance(saved["id"], int)
    assert saved["duration_min"] is None
    assert saved["effort"] is None
    response = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    )
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
        client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
        == []
    )
    proposals = [
        {key: value for key, value in item.items() if key != "id"} for item in preview
    ]
    response = client.post(
        "/api/proposals/accept", json={**request, "proposals": proposals}
    )
    assert response.status_code == 201
    assert all(isinstance(item["id"], int) for item in response.json())


def test_confirm_suggestion_saves_only_that_workout_as_confirmed(client):
    """Direct confirmation validates a draft and saves only it as upcoming training."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    proposal = {key: value for key, value in preview[0].items() if key != "id"}
    response = client.post(
        "/api/proposals/accept",
        json={**request, "proposals": [proposal], "confirm": True},
    )
    assert response.status_code == 201
    saved = response.json()[0]
    assert isinstance(saved["id"], int)
    assert saved == {**proposal, "status": "confirmed", "id": saved["id"]}
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [saved]
    repeated = client.post(
        "/api/proposals/accept",
        json={**request, "proposals": [proposal], "confirm": True},
    )
    assert repeated.status_code == 409


def test_confirm_suggestion_rejects_an_altered_draft(client):
    """Confirmation cannot bypass preview revalidation by editing workout details."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    proposal = {key: value for key, value in preview[0].items() if key != "id"}
    response = client.post(
        "/api/proposals/accept",
        json={
            **request,
            "proposals": [{**proposal, "notes": "Altered workout"}],
            "confirm": True,
        },
    )
    assert response.status_code == 409
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
        == []
    )


@pytest.mark.parametrize(
    "reverse", [False, True], ids=["earliest-first", "latest-first"]
)
def test_suggestions_can_be_confirmed_individually(client, reverse):
    """Confirm each original draft independently in either chronological order."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    proposals = [{k: v for k, v in item.items() if k != "id"} for item in preview]
    saved = []
    for proposal in reversed(proposals) if reverse else proposals:
        response = client.post(
            "/api/proposals/accept",
            json={**request, "proposals": [proposal], "confirm": True},
        )
        assert response.status_code == 201, response.text
        saved.extend(response.json())
    assert len(saved) == len(preview)
    assert all(item["status"] == "confirmed" for item in saved)


def test_stale_batch_is_rejected_without_partial_acceptance(client):
    """An intervening booking prevents the whole outdated batch from being saved."""
    request = {"week_start": "2026-10-05", "blocked": []}
    preview = client.post("/api/proposals", json=request).json()
    booking = client.post(
        "/api/sessions", json={"day": preview[-1]["day"], "activity": "cycle"}
    ).json()
    proposals = [
        {key: value for key, value in item.items() if key != "id"} for item in preview
    ]
    response = client.post(
        "/api/proposals/accept", json={**request, "proposals": proposals}
    )
    assert response.status_code == 409
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
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


def test_non_monday_start_is_allowed_and_reversed_range_is_rejected(client):
    """Allow a rolling horizon on any weekday and reject reversed query intervals."""
    assert (
        client.post("/api/proposals", json={"week_start": "2026-10-06"}).status_code
        == 200
    )
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-11", "end": "2026-10-05"}
        ).status_code
        == 422
    )


def test_rolling_sunday_preview_can_be_confirmed(client, planning_clock):
    """A Sunday start includes next week's gym dates and confirms the same preview."""
    planning_clock["today"] = date(2026, 10, 18)
    request = {
        "week_start": "2026-10-18",
        "blocked": ["2026-10-20", "2026-10-22"],
    }
    response = client.post("/api/proposals", json=request)
    assert response.status_code == 200
    preview = response.json()
    gym_days = {item["day"] for item in preview if item["activity"] == "gym"}
    assert {"2026-10-21", "2026-10-23"} <= gym_days
    assert len(gym_days) == 12
    assert all("2026-10-18" <= item["day"] <= "2026-11-14" for item in preview)
    draft = next(item for item in preview if item["day"] == "2026-10-21")
    proposal = {key: value for key, value in draft.items() if key != "id"}
    accepted = client.post(
        "/api/proposals/accept",
        json={**request, "proposals": [proposal], "confirm": True},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()[0]["status"] == "confirmed"


def test_fully_blocked_week_and_empty_acceptance_are_valid(client):
    """A rest week and declining every suggestion are valid workflows."""
    request = {
        "week_start": "2026-10-05",
        "blocked": [
            (date(2026, 10, 5) + timedelta(days=i)).isoformat() for i in range(28)
        ],
    }
    assert client.post("/api/proposals", json=request).json() == []
    response = client.post("/api/proposals/accept", json={**request, "proposals": []})
    assert response.status_code == 201
    assert response.json() == []


def test_duplicate_and_altered_proposals_are_rejected(client):
    """Accept only distinct, unmodified suggestions from the current rules."""
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
        client.post(
            "/api/proposals/accept", json={**request, "proposals": [preview]}
        ).status_code
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
    proposals = [
        {key: value for key, value in item.items() if key != "id"} for item in preview
    ]
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": proposals}
        ).status_code
        == 201
    )
    sessions = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json()
    assert saved in sessions


def test_api_construction_and_health_do_not_create_database(tmp_path):
    """Importing or checking health does not create an application database."""
    path = tmp_path / "unused.db"
    with TestClient(create_app(path)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
    assert not path.exists()


def test_acceptance_saves_only_selected_proposals(client):
    """Accepting a subset leaves every unchecked suggestion unsaved."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    selected = [
        {key: value for key, value in item.items() if key != "id"}
        for item in preview[::2]
    ]

    response = client.post(
        "/api/proposals/accept", json={**request, "proposals": selected}
    )

    assert response.status_code == 201
    saved = response.json()
    assert [item["day"] for item in saved] == [item["day"] for item in selected]
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
        == saved
    )


@pytest.mark.parametrize("include_elapsed", [True, False])
def test_acceptance_rechecks_date_after_midnight(
    client, planning_clock, include_elapsed
):
    """Reject elapsed selections atomically while allowing still-eligible items."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    planning_clock["today"] = date(2026, 10, 6)
    selected = [
        {key: value for key, value in item.items() if key != "id"}
        for item in preview
        if include_elapsed or item["day"] >= "2026-10-06"
    ]

    response = client.post(
        "/api/proposals/accept", json={**request, "proposals": selected}
    )

    assert response.status_code == (409 if include_elapsed else 201)
    saved = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json()
    if include_elapsed:
        assert saved == []
    else:
        assert saved == response.json()
        assert [item["day"] for item in saved] == [item["day"] for item in selected]


def test_generation_excludes_elapsed_dates(client, planning_clock):
    """The API applies the inclusive service clock cutoff to previews."""
    planning_clock["today"] = date(2026, 10, 7)
    response = client.post("/api/proposals", json={"week_start": "2026-10-05"})

    assert response.status_code == 200
    assert response.json()
    assert all("2026-10-07" <= item["day"] <= "2026-11-01" for item in response.json())
    assert any(item["day"] == "2026-10-07" for item in response.json())


def test_generation_returns_empty_preview_for_elapsed_horizon(client, planning_clock):
    """A wholly elapsed horizon produces no suggestions rather than an error."""
    planning_clock["today"] = date(2026, 11, 2)
    response = client.post("/api/proposals", json={"week_start": "2026-10-05"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("low,high", [(0, 2), (2, 6), (4, 2), (2, None), (None, 2)])
def test_invalid_hr_targets_are_rejected(client, low, high):
    """Invalid hr targets are rejected."""
    response = client.post(
        "/api/sessions",
        json={
            "day": "2026-10-06",
            "activity": "easy_run",
            "hr_zone_min": low,
            "hr_zone_max": high,
        },
    )
    assert response.status_code == 422


def test_interval_target_and_duration_round_trip(client):
    """Interval target and duration round trip."""
    payload = {
        "day": "2026-10-06",
        "activity": "interval_run",
        "duration_min": 45,
        "hr_zone_min": 4,
        "hr_zone_max": 5,
        "notes": "10 min warm-up; 4 x 4 min hard, 3 x 3 min easy; 10 min cool-down",
    }
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201
    saved = response.json()
    assert all(saved[key] == value for key, value in payload.items())
    assert client.get(
        "/api/sessions",
        params={
            "start": "2026-10-05",
            "end": "2026-11-01",
        },
    ).json() == [saved]


def test_planning_loads_previous_week_recovery(client):
    """Planning loads previous week recovery."""
    client.post(
        "/api/sessions",
        json={
            "day": "2026-10-04",
            "activity": "race",
            "duration_min": 60,
        },
    )
    preview = client.post("/api/proposals", json={"week_start": "2026-10-05"}).json()
    monday = next(item for item in preview if item["day"] == "2026-10-05")
    assert monday["duration_min"] == 20
    assert monday["hr_zone_min"] == monday["hr_zone_max"] == 2


def test_altered_zone_target_cannot_be_accepted(client):
    """Altered zone target cannot be accepted."""
    request = {"week_start": "2026-10-05"}
    item = client.post("/api/proposals", json=request).json()[0]
    item.pop("id")
    item.update(hr_zone_min=4, hr_zone_max=5)
    assert (
        client.post(
            "/api/proposals/accept",
            json={
                **request,
                "proposals": [item],
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize("weeks", [0, 1, 2, 3, 5, 1.5])
def test_invalid_planning_horizon_is_rejected(client, weeks):
    """Invalid planning horizon is rejected."""
    request = {"week_start": "2026-10-05", "weeks": weeks}
    assert client.post("/api/proposals", json=request).status_code == 422
    assert (
        client.post(
            "/api/proposals/accept",
            json={
                **request,
                "proposals": [],
            },
        ).status_code
        == 422
    )


def test_four_week_fallback_round_trip_and_neighboring_booking_revalidation(client):
    """Two week fallback round trip and neighboring booking revalidation."""
    request = {
        "week_start": "2026-10-05",
        "weeks": 4,
        "blocked": ["2026-10-10", "2026-10-11"],
    }
    preview = client.post("/api/proposals", json=request)
    assert preview.status_code == 200
    run = next(s for s in preview.json() if s["activity"] == "long_run")
    assert run["day"] == "2026-10-12"
    run.pop("id")
    # A booking outside the horizon still affects its final weekend.
    race = client.post(
        "/api/sessions",
        json={
            "day": "2026-11-02",
            "activity": "race",
        },
    ).json()
    selected = [{k: v for k, v in s.items() if k != "id"} for s in preview.json()]
    rejected = client.post(
        "/api/proposals/accept", json={**request, "proposals": selected}
    )
    assert rejected.status_code == 409
    assert client.get(
        "/api/sessions",
        params={
            "start": "2026-10-05",
            "end": "2026-11-02",
        },
    ).json() == [race]
    # The unaffected Monday run can still be accepted on its own.
    accepted = client.post("/api/proposals/accept", json={**request, "proposals": [run]})
    assert accepted.status_code == 201
    saved = client.get(
        "/api/sessions",
        params={
            "start": "2026-10-12",
            "end": "2026-10-12",
        },
    ).json()
    assert saved == accepted.json()


def test_new_neighboring_run_invalidates_hike_preview(client):
    """New neighboring run invalidates hike preview."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    hike = next(s for s in preview if s["activity"] == "hike")
    hike.pop("id")
    booking = client.post(
        "/api/sessions",
        json={
            "day": "2026-10-12",
            "activity": "long_run",
            "duration_min": 45,
        },
    ).json()
    assert (
        client.post(
            "/api/proposals/accept",
            json={
                **request,
                "proposals": [hike],
            },
        ).status_code
        == 409
    )
    assert client.get(
        "/api/sessions",
        params={
            "start": "2026-10-05",
            "end": "2026-10-12",
        },
    ).json() == [booking]


def test_horizon_cannot_be_shrunk_to_accept_an_outside_proposal(client):
    """Horizon cannot be shrunk to accept an outside proposal."""
    request = {"week_start": "2026-10-05", "weeks": 4}
    preview = client.post("/api/proposals", json=request).json()
    outside = next(s for s in preview if s["day"] >= "2026-10-12")
    outside.pop("id")
    assert (
        client.post(
            "/api/proposals/accept",
            json={
                **request,
                "weeks": 1,
                "proposals": [outside],
            },
        ).status_code
        == 422
    )


def test_future_deferred_run_survives_midnight_after_preferred_sunday(
    client, planning_clock
):
    """Future deferred run survives midnight after preferred sunday."""
    request = {
        "week_start": "2026-10-05",
        "weeks": 4,
        "blocked": ["2026-10-10", "2026-10-11"],
    }
    preview = client.post("/api/proposals", json=request).json()
    run = next(s for s in preview if s["activity"] == "long_run")
    assert run["day"] == "2026-10-12"
    run.pop("id")
    planning_clock["today"] = date(2026, 10, 12)
    accepted = client.post("/api/proposals/accept", json={**request, "proposals": [run]})
    assert accepted.status_code == 201
    assert accepted.json()[0]["day"] == "2026-10-12"


@pytest.mark.parametrize(
    "acceptance_order", ["batch", "monday_first", "forward", "reverse"]
)
def test_acceptance_order_preserves_remaining_suggestions(
    client: TestClient, acceptance_order: str
) -> None:
    """Accepting unchanged proposals preserves every remaining suggestion.

    A four-week preview contains a Saturday hike, a shortened Monday easy run,
    and a deferred Tuesday long run. Compare batch acceptance with accepting
    Monday first and with accepting each item in either chronological order.
    Regeneration must only remove saved items, and the original remaining
    proposals must still pass acceptance without being moved or rewritten.
    """
    request = {"week_start": "2026-10-05", "weeks": 4}
    response = client.post("/api/proposals", json=request)
    assert response.status_code == 200
    preview = response.json()
    assert any(s["day"] == "2026-10-10" and s["activity"] == "hike" for s in preview)
    monday = next(s for s in preview if s["day"] == "2026-10-12")
    assert monday["activity"] == "easy_run"
    assert monday["duration_min"] == 20
    assert any(s["day"] == "2026-10-13" and s["activity"] == "long_run" for s in preview)

    if acceptance_order == "batch":
        batches = [preview]
    elif acceptance_order == "monday_first":
        batches = [[monday], [s for s in preview if s != monday]]
    else:
        ordered = list(reversed(preview)) if acceptance_order == "reverse" else preview
        batches = [[s] for s in ordered]

    accepted_keys: set[tuple[str, str]] = set()
    for batch in batches:
        selected = [{k: v for k, v in s.items() if k != "id"} for s in batch]
        accepted = client.post(
            "/api/proposals/accept", json={**request, "proposals": selected}
        )
        assert accepted.status_code == 201, accepted.text
        accepted_keys.update((s["day"], s["activity"]) for s in batch)
        regenerated = client.post("/api/proposals", json=request)
        assert regenerated.status_code == 200
        assert regenerated.json() == [
            s for s in preview if (s["day"], s["activity"]) not in accepted_keys
        ]

    saved = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    )
    assert saved.status_code == 200
    assert (
        sorted(
            [{**s, "id": None} for s in saved.json()],
            key=lambda s: (s["day"], s["activity"]),
        )
        == preview
    )


@pytest.mark.parametrize("status", ["planned", "confirmed", "completed", "skipped"])
def test_delete_session_persists_and_preserves_other_entries(client, status):
    """Delete only the selected saved activity, regardless of its workout status."""
    saved = client.post(
        "/api/sessions",
        json={"day": "2026-10-06", "activity": "gym", "status": status},
    ).json()
    other = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "cycle"}
    ).json()

    response = client.delete(f"/api/sessions/{saved['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [other]
    assert client.delete(f"/api/sessions/{saved['id']}").status_code == 404


def test_delete_missing_session_preserves_calendar(client):
    """Missing identifiers return a useful 404 without removing existing activities."""
    saved = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym"}
    ).json()
    response = client.delete("/api/sessions/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Session 9999 does not exist"}
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [saved]


def test_accepted_suggestion_can_be_deleted_and_proposed_again(client):
    """Deleting an accepted suggestion frees its date for a fresh planning preview."""
    request = {"week_start": "2026-10-05"}
    proposal = client.post("/api/proposals", json=request).json()[0]
    proposal.pop("id")
    saved = client.post(
        "/api/proposals/accept", json={**request, "proposals": [proposal]}
    ).json()[0]
    assert client.delete(f"/api/sessions/{saved['id']}").status_code == 204
    assert {**proposal, "id": None} in client.post("/api/proposals", json=request).json()


@pytest.mark.parametrize("status", ["planned", "confirmed", "completed", "skipped"])
def test_update_session_preserves_identity_and_other_entries(client, status):
    """Replace all workout fields and move dates without inserting or altering peers."""
    original = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym"}
    ).json()
    other = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "cycle"}
    ).json()
    replacement = {
        "day": "2026-10-13",
        "activity": "interval_run",
        "status": status,
        "duration_min": 45,
        "effort": 8,
        "hr_zone_min": 4,
        "hr_zone_max": 5,
        "notes": "Moved and corrected",
        "actual_duration_min": None,
        "distance_km": None,
        "average_hr_bpm": None,
        "elevation_gain_m": None,
        "active_calories_kcal": None,
    }
    response = client.put(f"/api/sessions/{original['id']}", json=replacement)
    assert response.status_code == 200
    updated = {**replacement, "id": original["id"]}
    assert response.json() == updated
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [other, updated]


def test_update_can_clear_optional_metrics(client):
    """Editing can explicitly clear optional values without changing the identifier."""
    original = client.post(
        "/api/sessions",
        json={
            "day": "2026-10-06",
            "activity": "easy_run",
            "duration_min": 30,
            "effort": 5,
            "hr_zone_min": 2,
            "hr_zone_max": 2,
            "notes": "Old",
        },
    ).json()
    response = client.put(
        f"/api/sessions/{original['id']}",
        json={
            "day": "2026-10-06",
            "activity": "gym",
            "duration_min": None,
            "effort": None,
            "hr_zone_min": None,
            "hr_zone_max": None,
            "notes": "",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        **original,
        "activity": "gym",
        "duration_min": None,
        "effort": None,
        "hr_zone_min": None,
        "hr_zone_max": None,
        "notes": "",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"duration_min": -1},
        {"duration_min": 1441},
        {"effort": 0},
        {"effort": 11},
        {"hr_zone_min": 4, "hr_zone_max": 2},
        {"hr_zone_min": 2},
        {"activity": "unknown"},
        {"status": "unknown"},
        {"id": 99},
    ],
)
def test_invalid_update_preserves_saved_record(client, change):
    """Reject invalid metrics, enums and body identifiers without modifying storage."""
    original = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym"}
    ).json()
    response = client.put(
        f"/api/sessions/{original['id']}",
        json={"day": "2026-10-06", "activity": "gym", **change},
    )
    assert response.status_code == 422
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [original]


def test_update_missing_session_does_not_insert(client):
    """Updating a missing identifier returns 404 rather than creating a workout."""
    response = client.put(
        "/api/sessions/9999", json={"day": "2026-10-06", "activity": "gym"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Session 9999 does not exist"}
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
        == []
    )


def test_editing_accepted_workout_invalidates_stale_suggestions(client):
    """Explicit edits retain accepted IDs and acceptance still rechecks the calendar.

    Accept one suggestion, then move that saved workout onto another proposed
    day. The stale proposal for that day must be rejected without losing the edit.
    """
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    same_type = [s for s in preview if s["activity"] == "gym"]
    first, second = [{k: v for k, v in s.items() if k != "id"} for s in same_type[:2]]
    saved = client.post(
        "/api/proposals/accept", json={**request, "proposals": [first]}
    ).json()[0]
    edited = client.put(
        f"/api/sessions/{saved['id']}", json={**first, "day": second["day"]}
    )
    assert edited.status_code == 200
    assert edited.json()["id"] == saved["id"]
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": [second]}
        ).status_code
        == 409
    )
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [edited.json()]


def test_status_changes_preserve_details_identity_and_other_records(client):
    """Persist every status transition while preserving all other saved fields."""
    saved = client.post(
        "/api/sessions",
        json={
            "day": "2026-10-06",
            "activity": "interval_run",
            "duration_min": 45,
            "effort": 8,
            "hr_zone_min": 4,
            "hr_zone_max": 5,
            "notes": "Keep details",
        },
    ).json()
    other = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym"}
    ).json()
    for status in ["confirmed", "completed", "skipped", "planned"]:
        response = client.patch(
            f"/api/sessions/{saved['id']}/status", json={"status": status}
        )
        assert response.status_code == 200
        assert response.json() == {**saved, "status": status}
        assert client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json() == [{**saved, "status": status}, other]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": None},
        {"status": "unknown"},
        {"status": "confirmed", "notes": "Overwrite"},
        {"status": "confirmed", "id": 99},
    ],
)
def test_invalid_status_change_keeps_original_workout(client, payload):
    """Reject missing/invalid statuses and extra fields without changing the record."""
    saved = client.post(
        "/api/sessions", json={"day": "2026-10-06", "activity": "gym"}
    ).json()
    response = client.patch(f"/api/sessions/{saved['id']}/status", json=payload)
    assert response.status_code == 422
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [saved]


def test_status_change_missing_workout_returns_404(client):
    """A status mutation cannot create a missing workout."""
    response = client.patch("/api/sessions/9999/status", json={"status": "confirmed"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Session 9999 does not exist"}
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
        == []
    )


def test_confirmed_workouts_remain_booked_and_preserved_during_planning(client):
    """Confirmation preserves scheduling constraints without marking workouts complete.

    Compare proposals around a demanding planned workout before and after
    confirmation, then accept the preview and ensure the confirmed record survives.
    """
    saved = client.post(
        "/api/sessions",
        json={"day": "2026-10-08", "activity": "interval_run", "effort": 8},
    ).json()
    request = {"week_start": "2026-10-05"}
    before = client.post("/api/proposals", json=request).json()
    confirmed = client.patch(
        f"/api/sessions/{saved['id']}/status", json={"status": "confirmed"}
    ).json()
    assert confirmed == {**saved, "status": "confirmed"}
    after = client.post("/api/proposals", json=request).json()
    assert after == before
    assert all(item["day"] != saved["day"] for item in after)
    proposals = [{k: v for k, v in item.items() if k != "id"} for item in after]
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": proposals}
        ).status_code
        == 201
    )
    assert (
        confirmed
        in client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
    )


def test_moved_draft_is_reserved_without_saving_and_can_be_accepted(client):
    """Replanning retains a moved draft, excludes its origin and saves only on accept."""
    request: dict[str, object] = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    source = next(item for item in preview if item["day"] == "2026-10-06")
    moved = {key: value for key, value in source.items() if key != "id"}
    moved["day"] = "2026-10-08"
    request["moves"] = [{"original_day": source["day"], "session": moved}]
    response = client.post("/api/proposals", json=request)
    assert response.status_code == 200, response.text
    recalculated = response.json()
    assert {**moved, "id": None} in recalculated
    assert all(item["day"] != "2026-10-06" for item in recalculated)
    assert len({(item["day"], item["activity"]) for item in recalculated}) == len(
        recalculated
    )
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
        ).json()
        == []
    )
    accepted = client.post(
        "/api/proposals/accept", json={**request, "proposals": [moved]}
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()[0] == {**moved, "id": accepted.json()[0]["id"]}
    assert isinstance(accepted.json()[0]["id"], int)


def test_confirm_moved_draft_then_confirm_another_suggestion(client):
    """Confirm a moved draft and another workout after releasing its draft reservation.

    The accepted move becomes a saved booking. Subsequent confirmation omits that
    move and keeps its original date dismissed, matching the calendar workflow.
    """
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    source = next(item for item in preview if item["day"] == "2026-10-06")
    moved = {key: value for key, value in source.items() if key != "id"}
    moved["day"] = "2026-10-08"
    moves = [{"original_day": source["day"], "session": moved}]
    recalculated = client.post("/api/proposals", json={**request, "moves": moves}).json()
    confirmed = client.post(
        "/api/proposals/accept",
        json={**request, "moves": moves, "proposals": [moved], "confirm": True},
    )
    assert confirmed.status_code == 201, confirmed.text
    other = next(item for item in recalculated if item["day"] != moved["day"])
    proposal = {key: value for key, value in other.items() if key != "id"}
    response = client.post(
        "/api/proposals/accept",
        json={
            **request,
            "dismissed": [source["day"]],
            "proposals": [proposal],
            "confirm": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()[0]["status"] == "confirmed"


def test_draft_move_can_be_accepted_without_recalculating(client):
    """Keeping a preview still permits accepting a valid explicitly moved draft."""
    request = {"week_start": "2026-10-05"}
    preview = client.post("/api/proposals", json=request).json()
    source = next(item for item in preview if item["day"] == "2026-10-06")
    moved = {key: value for key, value in source.items() if key != "id"}
    moved["day"] = "2026-10-08"
    response = client.post(
        "/api/proposals/accept",
        json={
            **request,
            "moves": [{"original_day": source["day"], "session": moved}],
            "proposals": [moved],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()[0]["day"] == "2026-10-08"


@pytest.mark.parametrize(
    ("destination", "original", "status", "blocked"),
    [
        ("2026-10-04", "2026-10-06", "planned", []),
        ("2026-11-02", "2026-10-06", "planned", []),
        ("2026-10-08", "2026-11-02", "planned", []),
        ("2026-10-08", "2026-10-06", "completed", []),
        ("2026-10-08", "2026-10-06", "confirmed", []),
        ("2026-10-08", "2026-10-06", "planned", ["2026-10-08"]),
    ],
)
def test_invalid_manual_draft_positions_are_rejected(
    client, destination, original, status, blocked
):
    """Drafts cannot bypass horizon, planned-status or blocked-date constraints."""
    moved = {"day": destination, "activity": "gym", "status": status}
    request = {
        "week_start": "2026-10-05",
        "blocked": blocked,
        "moves": [{"original_day": original, "session": moved}],
    }
    assert client.post("/api/proposals", json=request).status_code == 409
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": [moved]}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("duplicate", ["origin", "destination"])
def test_duplicate_manual_draft_positions_are_rejected(client, duplicate):
    """Each moved draft has a unique origin and destination within its request."""
    first = {
        "original_day": "2026-10-06",
        "session": {"day": "2026-10-08", "activity": "gym"},
    }
    second = {
        "original_day": "2026-10-06" if duplicate == "origin" else "2026-10-07",
        "session": {
            "day": "2026-10-09" if duplicate == "origin" else "2026-10-08",
            "activity": "gym",
        },
    }
    response = client.post(
        "/api/proposals", json={"week_start": "2026-10-05", "moves": [first, second]}
    )
    assert response.status_code == 409


def test_intervening_booking_rejects_moved_draft_batch_atomically(client):
    """Acceptance rechecks moved destinations and never partially saves stale batches."""
    moved = {"day": "2026-10-08", "activity": "gym"}
    request = {
        "week_start": "2026-10-05",
        "moves": [{"original_day": "2026-10-06", "session": moved}],
    }
    preview = client.post("/api/proposals", json=request).json()
    proposals = [{k: v for k, v in item.items() if k != "id"} for item in preview]
    booking = client.post("/api/sessions", json=moved).json()
    response = client.post(
        "/api/proposals/accept", json={**request, "proposals": proposals}
    )
    assert response.status_code == 409
    assert client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-11-01"}
    ).json() == [booking]


def test_moved_draft_expires_before_acceptance(client, planning_clock):
    """A moved preview remains subject to the server's current-date validation."""
    moved = {"day": "2026-10-08", "activity": "gym"}
    request = {
        "week_start": "2026-10-05",
        "moves": [{"original_day": "2026-10-06", "session": moved}],
    }
    assert client.post("/api/proposals", json=request).status_code == 200
    planning_clock["today"] = date(2026, 10, 9)
    assert client.post("/api/proposals", json=request).status_code == 409
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": [moved]}
        ).status_code
        == 409
    )


def test_replanning_accounts_for_workload_of_unsaved_moved_drafts(client):
    """A manually positioned hike keeps its date and constrains new endurance work."""
    moved = {"day": "2026-10-09", "activity": "hike", "duration_min": 180}
    response = client.post(
        "/api/proposals",
        json={
            "week_start": "2026-10-05",
            "moves": [{"original_day": "2026-10-10", "session": moved}],
        },
    )
    assert response.status_code == 200, response.text
    proposals = response.json()
    assert any(
        item["day"] == "2026-10-09" and item["activity"] == "hike" for item in proposals
    )
    assert all(
        item["activity"] != "long_run" or item["day"] > "2026-10-11"
        for item in proposals
    )
    assert all(item["day"] != "2026-10-10" for item in proposals)


def test_dismissed_suggestions_stay_out_of_recalculation_and_acceptance(client):
    """Preview exclusions survive regeneration and acceptance without saving anything."""
    request = {"week_start": "2026-10-05", "dismissed": ["2026-10-06"]}
    response = client.post("/api/proposals", json=request)
    assert response.status_code == 200
    preview = response.json()
    assert all(item["day"] != "2026-10-06" for item in preview)
    selected = [
        {key: value for key, value in item.items() if key != "id"} for item in preview
    ]
    accepted = client.post(
        "/api/proposals/accept", json={**request, "proposals": selected}
    )
    assert accepted.status_code == 201, accepted.text
    assert all(item["day"] != "2026-10-06" for item in accepted.json())


def test_dismissed_date_can_receive_an_explicit_draft_move(client):
    """Dismissing a suggestion leaves its date available for explicit moves."""
    response = client.post(
        "/api/proposals",
        json={
            "week_start": "2026-10-05",
            "dismissed": ["2026-10-08"],
            "moves": [
                {
                    "original_day": "2026-10-06",
                    "session": {"day": "2026-10-08", "activity": "gym"},
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert any(item["day"] == "2026-10-08" for item in response.json())


@pytest.mark.parametrize(
    "targets",
    [
        {"gym": -1},
        {"gym": 8},
        {"runs": 8},
        {"runs": 1.5},
        {"gym": True},
        {"runs": 0, "intervals": 1},
        {"intervals": 3},
        {"unexpected": 1},
    ],
)
def test_invalid_training_targets_rejected_at_both_endpoints(client, targets):
    """Generation and acceptance reject invalid counts and inconsistent run mixes."""
    request = {"week_start": "2026-10-05", "targets": targets}
    assert client.post("/api/proposals", json=request).status_code == 422
    assert (
        client.post(
            "/api/proposals/accept", json={**request, "proposals": []}
        ).status_code
        == 422
    )


def test_same_day_proposals_can_be_confirmed_independently(client):
    """Confirming the gym draft leaves a same-day easy run available for acceptance."""
    request = {
        "week_start": "2026-10-05",
        "targets": {"gym": 1, "runs": 1, "intervals": 0},
        "blocked": [
            (date(2026, 10, 5) + timedelta(days=i)).isoformat()
            for i in range(28)
            if i % 7 != 0
        ],
    }
    preview = client.post("/api/proposals", json=request).json()
    same_day = [s for s in preview if s["day"] == "2026-10-05"]
    assert {s["activity"] for s in same_day} == {"gym", "easy_run"}
    for draft in same_day:
        proposal = {k: v for k, v in draft.items() if k != "id"}
        response = client.post(
            "/api/proposals/accept",
            json={**request, "proposals": [proposal], "confirm": True},
        )
        assert response.status_code == 201, response.text
    saved = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-05"}
    ).json()
    assert {s["activity"] for s in saved} == {"gym", "easy_run"}
    assert all(s["status"] == "confirmed" for s in saved)


def test_same_day_draft_moves_have_separate_origins_and_destinations(client):
    """Two workout types can share original and moved dates without identity clashes."""
    moves = [
        {
            "original_day": "2026-10-05",
            "session": {"day": "2026-10-08", "activity": activity},
        }
        for activity in ("gym", "easy_run")
    ]
    request = {"week_start": "2026-10-05", "moves": moves}
    response = client.post("/api/proposals", json=request)
    assert response.status_code == 200, response.text
    pinned = [s for s in response.json() if s["day"] == "2026-10-08"]
    assert {s["activity"] for s in pinned} == {"gym", "easy_run"}
    proposals = [{k: v for k, v in s.items() if k != "id"} for s in pinned]
    accepted = client.post(
        "/api/proposals/accept", json={**request, "proposals": proposals}
    )
    assert accepted.status_code == 201, accepted.text


def test_excluding_one_same_day_draft_preserves_the_other(client):
    """Per-workout exclusions never turn the whole date into an unavailable day."""
    request = {
        "week_start": "2026-10-05",
        "targets": {"gym": 1, "runs": 1},
        "blocked": [
            (date(2026, 10, 5) + timedelta(days=i)).isoformat()
            for i in range(28)
            if i % 7 != 0
        ],
        "excluded": [{"day": "2026-10-05", "activity": "easy_run"}],
    }
    preview = client.post("/api/proposals", json=request).json()
    first_day = [s for s in preview if s["day"] == "2026-10-05"]
    assert len(first_day) == 1
    assert first_day[0]["activity"] == "gym"
    proposal = {k: v for k, v in first_day[0].items() if k != "id"}
    accepted = client.post(
        "/api/proposals/accept", json={**request, "proposals": [proposal]}
    )
    assert accepted.status_code == 201, accepted.text
