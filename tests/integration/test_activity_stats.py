"""Verify recorded workout results across API, storage and quick status changes."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from training_planner.api.app import create_app


@pytest.mark.parametrize("activity", ["easy_run", "cycle", "hike", "gym"])
def test_recorded_results_round_trip_and_edit(tmp_path: Path, activity: str) -> None:
    """Preserve independent targets, results and multiline notes through edits."""
    payload: dict[str, object] = {
        "day": date.today().isoformat(),
        "activity": activity,
        "status": "completed",
        "duration_min": 45,
        "actual_duration_min": 32.5,
        "distance_km": 5.2,
        "average_hr_bpm": 142,
        "elevation_gain_m": 123.4,
        "active_calories_kcal": 345.5,
        "effort": 5,
        "notes": "Bench press: 60 kg — 3 × 8\nPull-ups: 8, 7, 6",
    }
    with TestClient(create_app(tmp_path / "stats.db")) as client:
        response = client.post("/api/sessions", json=payload)
        assert response.status_code == 201
        saved = response.json()
        identifier = saved.pop("id")
        assert saved == {**payload, "hr_zone_min": None, "hr_zone_max": None}
        payload["actual_duration_min"] = 30
        payload["distance_km"] = None
        response = client.put(f"/api/sessions/{identifier}", json=payload)
        assert response.status_code == 200
        updated = response.json()
        assert updated["actual_duration_min"] == 30
        assert updated["duration_min"] == 45
        assert updated["distance_km"] is None
        response = client.patch(
            f"/api/sessions/{identifier}/status", json={"status": "confirmed"}
        )
        assert response.json() == {**updated, "status": "confirmed"}
        response = client.get(
            "/api/sessions", params={"start": payload["day"], "end": payload["day"]}
        )
        assert response.json() == [{**updated, "status": "confirmed"}]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actual_duration_min", -1),
        ("actual_duration_min", 1441),
        ("distance_km", -0.1),
        ("distance_km", "NaN"),
        ("elevation_gain_m", -1),
        ("elevation_gain_m", "Infinity"),
        ("active_calories_kcal", -1),
        ("active_calories_kcal", "NaN"),
        ("average_hr_bpm", 0),
        ("average_hr_bpm", 301),
        ("average_hr_bpm", 140.5),
    ],
)
def test_invalid_recorded_stats_are_rejected(
    tmp_path: Path, field: str, value: float | str
) -> None:
    """Reject negative, nonfinite and out-of-range stats on create and update."""
    with TestClient(create_app(tmp_path / "stats.db")) as client:
        payload = {"day": date.today().isoformat(), "activity": "easy_run"}
        identifier = client.post("/api/sessions", json=payload).json()["id"]
        invalid = {**payload, field: value}
        assert client.post("/api/sessions", json=invalid).status_code == 422
        assert client.put(f"/api/sessions/{identifier}", json=invalid).status_code == 422


def test_unknown_and_zero_results_remain_distinct(tmp_path: Path) -> None:
    """Permit completion with no stats and preserve explicitly recorded zeroes."""
    with TestClient(create_app(tmp_path / "stats.db")) as client:
        payload = {
            "day": date.today().isoformat(),
            "activity": "hike",
            "status": "completed",
        }
        saved = client.post("/api/sessions", json=payload).json()
        fields = [
            "actual_duration_min",
            "distance_km",
            "average_hr_bpm",
            "elevation_gain_m",
            "active_calories_kcal",
        ]
        assert all(saved[field] is None for field in fields)
        zeroes = {field: 0 for field in fields if field != "average_hr_bpm"}
        saved = client.put(
            f"/api/sessions/{saved['id']}", json={**payload, **zeroes}
        ).json()
        assert all(saved[field] == 0 for field in zeroes)
