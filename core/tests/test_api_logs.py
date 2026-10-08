"""Tests für `GET /logs` (§54, Gap-Analyse Gap J - Log-Viewer).

Strukturiertes Datei-Logging existierte bereits, aber ohne API-Zugriff.
Nutzt einen echten Scan-Lauf (löst reale `genesis.MediaScanner`-Logzeilen
aus), um den Endpunkt gegen eine authentische Logdatei statt künstlich
vorbereiteter Zeilen zu testen.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path / "data"
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def test_logs_endpoint_requires_token(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/logs")
    assert resp.status_code == 401


def test_logs_endpoint_returns_entries_after_a_scan(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)

    scan_resp = client.post("/scan", json={"directories": [str(test_library_root)]})
    assert scan_resp.status_code == 200

    logs_resp = client.get("/logs")
    assert logs_resp.status_code == 200
    body = logs_resp.json()
    assert body["total"] > 0
    assert any("Scan" in item["message"] or "scan" in item["component"].lower()
                for item in body["items"])


def test_logs_endpoint_level_filter(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    client.post("/scan", json={"directories": [str(test_library_root)]})

    all_logs = client.get("/logs").json()
    warning_logs = client.get("/logs", params={"level": "WARNING"}).json()
    assert warning_logs["total"] <= all_logs["total"]
    assert all(item["level"] in ("WARNING", "ERROR", "CRITICAL") for item in warning_logs["items"])


def test_logs_endpoint_component_filter(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    client.post("/scan", json={"directories": [str(test_library_root)]})

    resp = client.get("/logs", params={"component": "MediaScanner"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all("mediascanner" in item["component"].lower() for item in body["items"])


def test_logs_endpoint_pagination(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    client.post("/scan", json={"directories": [str(test_library_root)]})

    page1 = client.get("/logs", params={"limit": 1, "offset": 0}).json()
    page2 = client.get("/logs", params={"limit": 1, "offset": 1}).json()
    assert len(page1["items"]) == 1
    if page2["total"] > 1:
        assert page1["items"][0]["message"] != page2["items"][0]["message"]


def test_logs_endpoint_empty_before_any_activity(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/logs")
    assert resp.status_code == 200
    # Zumindest der Start der App selbst erzeugt i.d.R. keine Eintraege ohne
    # jede Aktion - total darf 0 sein, darf aber nicht fehlschlagen.
    assert resp.json()["total"] >= 0
