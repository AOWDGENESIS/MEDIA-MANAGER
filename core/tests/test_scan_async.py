"""Synthetische Regression: Fortschritt, Abbruch/Rollback, Einzellauf-Sperre.

Keine Nutzerdateien oder echten Medienprozesse. Alle Scans bleiben in tmp_path.
"""
from __future__ import annotations

import time
from threading import Event

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import MediaFile
from genesis_core.scanner import scanner


def client_for(tmp_path):
    settings = Settings()
    settings.paths.data_dir = tmp_path / "data"
    settings.general.safe_test_mode = True
    app = create_app(settings)
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client, app


def await_status(client, job_id, expected, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        response = client.get(f"/scan/{job_id}/status")
        assert response.status_code == 200
        status = response.json()
        if status["status"] == expected:
            return status
        if status["status"] in ("failed", "cancelled", "completed"):
            raise AssertionError(f"Unexpected terminal scan: {status}")
        time.sleep(0.03)
    raise AssertionError(f"Scan did not reach {expected}")


def test_async_scan_progress_single_flight_and_cancel_rollback(tmp_path, monkeypatch):
    media_dir = tmp_path / "music"
    media_dir.mkdir()
    for index in range(2):
        (media_dir / f"song{index}.mp3").write_bytes(b"synthetic")
    client, app = client_for(tmp_path)
    entered = Event()
    release = Event()
    original_hash = scanner.sha256_of_file
    calls = 0

    def held_hash(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            assert release.wait(5), "Synthetic scan exceeded test deadline"
        return original_hash(*args, **kwargs)

    monkeypatch.setattr(scanner, "sha256_of_file", held_hash)
    response = client.post("/scan/start", json={
        "directories": [str(media_dir)], "run_ffprobe": False,
    })
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert entered.wait(5)
    try:
        status = client.get(f"/scan/{job_id}/status").json()
        assert status["files_found"] == 1
        assert status["status"] == "running"
        assert client.post("/scan/start", json={"directories": [str(media_dir)]}).status_code == 409
        assert client.post(f"/jobs/{job_id}/pause").status_code == 409
        assert client.post(f"/scan/{job_id}/cancel").json()["cancel_requested"] is True
    finally:
        release.set()
    ended = await_status(client, job_id, "cancelled")
    assert ended["result"] is None
    with app.state.genesis.db.session() as session:
        assert session.scalar(select(func.count(MediaFile.id))) == 0
    # Kein gespenstischer Background-Job und kein zweiter Scan gleichzeitig.
    again = client.post("/scan/start", json={
        "directories": [str(media_dir)], "run_ffprobe": False,
    })
    assert again.status_code == 202
    complete = await_status(client, again.json()["job_id"], "completed")
    assert complete["result"]["files_found"] == 2
    assert complete["files_found"] == 2
    with app.state.genesis.db.session() as session:
        assert session.scalar(select(func.count(MediaFile.id))) == 2


def test_restart_marks_only_orphaned_scan_failed(tmp_path):
    client, app = client_for(tmp_path)
    orphan = app.state.genesis.jobs.create_job("scan")
    other = app.state.genesis.jobs.create_job("other")
    # Neue AppState-Instanz, gleiches temporaeres Datenverzeichnis, kein Thread.
    client_for(tmp_path)
    assert app.state.genesis.jobs.get_job(orphan).status.value == "failed"
    assert app.state.genesis.jobs.get_job(other).status.value == "pending"


def test_async_scan_auth_and_failure(tmp_path, monkeypatch):
    client, app = client_for(tmp_path)
    bare = TestClient(app)
    assert bare.post("/scan/start", json={"directories": []}).status_code == 401
    assert bare.get("/scan/nonexistent/status").status_code == 401
    assert client.get("/scan/nonexistent/status").status_code == 404
    monkeypatch.setattr(scanner, "MAX_MEDIA_FILES_PER_SCAN", 0)
    media_dir = tmp_path / "music"
    media_dir.mkdir()
    (media_dir / "one.mp3").write_bytes(b"fake")
    response = client.post("/scan/start", json={"directories": [str(media_dir)]})
    assert response.status_code == 202
    status = await_status(client, response.json()["job_id"], "failed")
    assert "keine Teil-Ergebnisse gespeichert" in status["error"]
    with app.state.genesis.db.session() as session:
        assert session.scalar(select(func.count(MediaFile.id))) == 0
