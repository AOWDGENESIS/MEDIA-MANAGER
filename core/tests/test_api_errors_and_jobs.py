"""Tests fuer den globalen Exception-Handler (§37) und Job-Pause/Resume/
Cancel-Endpunkte (§35/§36), ADR-0020."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _client(app) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def test_unhandled_exception_returns_structured_error(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)

    @app.get("/__boom_for_test__", dependencies=[])
    def _boom():
        raise RuntimeError("absichtlicher Testfehler")

    resp = client.get("/__boom_for_test__")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_id"].startswith("ERR-")
    assert "timestamp" in body
    assert "solution_hint" in body
    assert "unerwarteter Fehler" in body["message"]

    # Fehler muss im Error-Center auffindbar sein (§37/§38).
    list_resp = client.get("/errors")
    assert list_resp.status_code == 200
    error_ids = [e["error_id"] for e in list_resp.json()["errors"]]
    assert body["error_id"] in error_ids


def test_resolve_unknown_error_returns_404(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/errors/ERR-99999999-99999/resolve")
    assert resp.status_code == 404


def test_job_pause_resume_cancel_endpoints(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    state = app.state.genesis
    job_id = state.jobs.create_job("test_batch")
    state.jobs.start(job_id)

    resp = client.post(f"/jobs/{job_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"

    resp = client.post(f"/jobs/{job_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

    resp = client.post(f"/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_job_pause_unknown_job_returns_404(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/jobs/JOB-DOES-NOT-EXIST/pause")
    assert resp.status_code == 404


def test_job_resume_already_completed_returns_409(tmp_path: Path) -> None:
    """Deep-Review-Fund (Sitzung 11): resume() auf einen bereits
    abgeschlossenen Job musste frueher stillschweigend durchgehen und den
    Job faelschlich wieder auf 'running' zuruecksetzen - jetzt lehnt der
    Endpunkt dies mit 409 (Konflikt) ab, der Job bleibt unveraendert."""
    app = _make_app(tmp_path)
    client = _client(app)
    state = app.state.genesis
    job_id = state.jobs.create_job("test_batch")
    state.jobs.start(job_id)
    state.jobs.complete(job_id)

    resp = client.post(f"/jobs/{job_id}/resume")
    assert resp.status_code == 409
    assert "completed" in resp.json()["detail"]

    # Unveraendert geblieben - kein "Geister-Job".
    get_resp = client.get(f"/jobs/{job_id}")
    assert get_resp.json()["status"] == "completed"


def test_job_pause_not_running_returns_409(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    state = app.state.genesis
    job_id = state.jobs.create_job("test_batch")
    # Noch PENDING, nicht gestartet.

    resp = client.post(f"/jobs/{job_id}/pause")
    assert resp.status_code == 409


def test_job_cancel_twice_is_idempotent_via_api(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    state = app.state.genesis
    job_id = state.jobs.create_job("test_batch")
    state.jobs.start(job_id)

    first = client.post(f"/jobs/{job_id}/cancel")
    assert first.status_code == 200
    second = client.post(f"/jobs/{job_id}/cancel")
    assert second.status_code == 200
    assert second.json()["status"] == "cancelled"
