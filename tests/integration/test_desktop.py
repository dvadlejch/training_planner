"""Verify packaged storage paths, initialization and frontend/API coexistence."""

import asyncio
import socket
import sys
from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest
import uvicorn
from fastapi.testclient import TestClient

from training_planner import desktop
from training_planner.api.app import create_app
from training_planner.storage.db import connect


def test_frozen_database_uses_executable_folder(tmp_path, monkeypatch):
    """Frozen initialization ignores the working directory and development override."""
    installation = tmp_path / "selected installation"
    installation.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(installation / "TrainingPlanner.exe"))
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("TRAINING_PLANNER_DB", str(elsewhere / "wrong.db"))

    assert desktop.main(["--init-db"]) == 0
    database = installation / "data" / "training.db"
    assert database.is_file()
    assert list(elsewhere.iterdir()) == []
    connection = connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    finally:
        connection.close()


def test_reinitializing_database_preserves_records(tmp_path, monkeypatch):
    """Repeated installation setup leaves existing workout records intact."""
    monkeypatch.setattr(desktop, "application_directory", lambda: tmp_path)
    database = tmp_path / "data" / "training.db"
    assert desktop.main(["--init-db"]) == 0
    connection = connect(database)
    try:
        connection.execute(
            "INSERT INTO sessions (day, activity) VALUES ('2026-10-18', 'gym')"
        )
        connection.commit()
    finally:
        connection.close()

    assert desktop.main(["--init-db"]) == 0
    connection = connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    finally:
        connection.close()


def test_storage_failure_returns_nonzero_without_fallback(tmp_path, monkeypatch, capsys):
    """A blocked data directory reports its path and fails installer initialization."""
    monkeypatch.setattr(desktop, "application_directory", lambda: tmp_path)
    (tmp_path / "data").write_text("This file prevents directory creation.")
    assert desktop.main(["--init-db"]) == 1
    assert str(tmp_path / "data" / "training.db") in capsys.readouterr().err
    assert not (tmp_path / "training.db").exists()


def test_frontend_and_api_share_one_server(tmp_path):
    """Built assets and the API work together without hiding missing API routes."""
    frontend = tmp_path / "web"
    frontend.mkdir()
    (frontend / "index.html").write_text("<html>Training calendar</html>")
    (frontend / "app.js").write_text("console.log('calendar');")
    with TestClient(create_app(tmp_path / "training.db", frontend)) as client:
        assert "Training calendar" in client.get("/").text
        assert client.get("/app.js").status_code == 200
        assert client.get("/api/health").json() == {"status": "ok"}
        assert (
            client.post(
                "/api/sessions",
                json={"day": date.today().isoformat(), "activity": "gym"},
            ).status_code
            == 201
        )
        assert client.get("/api/nonexistent").status_code == 404


def test_frozen_frontend_uses_bundle_location(tmp_path, monkeypatch):
    """Bundled assets are resolved independently of the persistent database folder."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(desktop, "__file__", str(tmp_path / "desktop.py"))
    assert desktop.frontend_directory() == tmp_path / "web"


def test_missing_frontend_does_not_start_server(tmp_path, monkeypatch, capsys):
    """An incomplete package fails clearly instead of serving an unusable app."""
    monkeypatch.setattr(desktop, "application_directory", lambda: tmp_path)
    monkeypatch.setattr(desktop, "frontend_directory", lambda: tmp_path / "missing")
    assert desktop.main(["--no-browser"]) == 1
    assert "Built interface missing" in capsys.readouterr().err


def test_occupied_port_does_not_start_or_open_browser(tmp_path, monkeypatch):
    """A port owned by another process cannot redirect startup to that process."""
    monkeypatch.setattr(desktop, "application_directory", lambda: tmp_path)
    monkeypatch.setattr(desktop, "frontend_directory", lambda: tmp_path)
    (tmp_path / "index.html").write_text("calendar")
    browser = Mock()
    monkeypatch.setattr(desktop.webbrowser, "open", browser)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        assert desktop.main(["--port", str(listener.getsockname()[1])]) == 1
    browser.assert_not_called()


@pytest.mark.parametrize(
    "started,open_browser", [(False, True), (True, False), (True, True)]
)
def test_browser_opens_only_after_successful_startup(started, open_browser, monkeypatch):
    """Browser launch requires successful startup and an enabled browser option."""
    monkeypatch.setattr(uvicorn.Server, "startup", AsyncMock())
    browser = Mock()
    monkeypatch.setattr(desktop.webbrowser, "open", browser)
    server = desktop.BrowserServer(uvicorn.Config(create_app()), open_browser)
    server.started = started
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        asyncio.run(server.startup([listener]))
    if started and open_browser:
        browser.assert_called_once_with(url)
    else:
        browser.assert_not_called()
