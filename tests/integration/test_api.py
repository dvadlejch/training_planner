"""Verify API boundaries and transactional proposal acceptance."""

from datetime import date

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
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
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
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
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
    assert (
        client.post("/api/proposals", json={"week_start": "2026-10-06"}).status_code
        == 422
    )
    assert (
        client.get(
            "/api/sessions", params={"start": "2026-10-11", "end": "2026-10-05"}
        ).status_code
        == 422
    )


def test_fully_blocked_week_and_empty_acceptance_are_valid(client):
    """A rest week and declining every suggestion are valid workflows."""
    request = {
        "week_start": "2026-10-05",
        "blocked": [f"2026-10-{day:02}" for day in range(5, 12)],
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
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
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
            "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
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
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-11"}
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
    assert [item["day"] for item in response.json()] == [
        "2026-10-07",
        "2026-10-09",
        "2026-10-10",
    ]


def test_generation_returns_empty_preview_for_elapsed_week(client, planning_clock):
    """A wholly elapsed week produces no suggestions rather than an error."""
    planning_clock["today"] = date(2026, 10, 12)
    response = client.post("/api/proposals", json={"week_start": "2026-10-05"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("low,high", [(0, 2), (2, 6), (4, 2), (2, None), (None, 2)])
def test_invalid_hr_targets_are_rejected(client, low, high):
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
            "end": "2026-10-11",
        },
    ).json() == [saved]


def test_planning_loads_previous_week_recovery(client):
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


@pytest.mark.parametrize("weeks", [0, 5, 1.5])
def test_invalid_planning_horizon_is_rejected(client, weeks):
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


def test_two_week_fallback_round_trip_and_neighboring_booking_revalidation(client):
    request = {
        "week_start": "2026-10-05",
        "weeks": 2,
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
            "day": "2026-10-19",
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
            "end": "2026-10-19",
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
    request = {"week_start": "2026-10-05", "weeks": 2}
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
        == 409
    )


def test_future_deferred_run_survives_midnight_after_preferred_sunday(
    client, planning_clock
):
    request = {
        "week_start": "2026-10-05",
        "weeks": 2,
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

    A two-week preview contains a Saturday hike, a shortened Monday easy run,
    and a deferred Tuesday long run. Compare batch acceptance with accepting
    Monday first and with accepting each item in either chronological order.
    Regeneration must only remove saved items, and the original remaining
    proposals must still pass acceptance without being moved or rewritten.
    """
    request = {"week_start": "2026-10-05", "weeks": 2}
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

    accepted_days: set[str] = set()
    for batch in batches:
        selected = [{k: v for k, v in s.items() if k != "id"} for s in batch]
        accepted = client.post(
            "/api/proposals/accept", json={**request, "proposals": selected}
        )
        assert accepted.status_code == 201, accepted.text
        accepted_days.update(s["day"] for s in batch)
        regenerated = client.post("/api/proposals", json=request)
        assert regenerated.status_code == 200
        assert regenerated.json() == [
            s for s in preview if s["day"] not in accepted_days
        ]

    saved = client.get(
        "/api/sessions", params={"start": "2026-10-05", "end": "2026-10-18"}
    )
    assert saved.status_code == 200
    assert [{**s, "id": None} for s in saved.json()] == preview
