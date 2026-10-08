"""API-Tests fuer Diagnostics (§38), Backup (§40) und Scan & Repair (§39)."""
from __future__ import annotations

import sqlite3
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


def test_diagnostics_endpoint_returns_report(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.get("/diagnostics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_status"] in ("ok", "warning", "error")
    assert any(c["check_id"] == "database" for c in body["checks"])


def test_backup_create_list_and_restore_round_trip(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)

    created = client.post("/backup/db")
    assert created.status_code == 200
    backup_id = created.json()["backup_id"]
    assert Path(created.json()["path"]).exists()

    listed = client.get("/backup", params={"backup_type": "db"})
    assert listed.status_code == 200
    assert any(b["id"] == backup_id for b in listed.json()["backups"])

    # Wiederherstellung ohne Bestaetigung muss verweigert werden.
    refused = client.post(f"/backup/{backup_id}/restore", json={"confirm": False})
    assert refused.status_code == 403

    restored = client.post(f"/backup/{backup_id}/restore", json={"confirm": True})
    assert restored.status_code == 200
    assert restored.json()["restored_from_backup_id"] == backup_id


def test_backup_restore_unknown_id_returns_404(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/backup/999999/restore", json={"confirm": True})
    assert resp.status_code == 404


def test_config_backup_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    app.state.genesis.settings.save()
    client = _client(app)
    resp = client.post("/backup/config")
    assert resp.status_code == 200
    assert Path(resp.json()["path"]).exists()


def _create_orphan_track(app) -> None:
    state = app.state.genesis
    from genesis_core.db.models import MediaFile, MediaKind, Track

    with state.db.session() as session:
        mf = MediaFile(
            absolute_path="/tmp/api_repair/song.mp3", directory="/tmp/api_repair",
            filename="song.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=1,
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id
        session.add(Track(media_file_id=media_file_id, title="verwaist"))

    conn = sqlite3.connect(str(state.db.database_path))
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM media_files WHERE id = ?", (media_file_id,))
        conn.commit()
    finally:
        conn.close()


def test_repair_plan_preview_execute_round_trip(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    _create_orphan_track(app)

    plan_resp = client.get("/repair/plan")
    assert plan_resp.status_code == 200
    plan_items = plan_resp.json()["items"]
    assert any(i["action_type"] == "cleanup_orphaned_rows" for i in plan_items)

    preview_resp = client.post(
        "/repair/preview",
        json={"items": [{"action_type": i["action_type"], "target": i["target"]} for i in plan_items]},
    )
    assert preview_resp.status_code == 200
    preview_items = preview_resp.json()["items"]
    orphan_preview = next(i for i in preview_items if i["action_type"] == "cleanup_orphaned_rows")
    assert len(orphan_preview["row_ids"]) == 1

    # Ausfuehrung ohne Bestaetigung muss verweigert werden.
    refused = client.post("/repair/execute", json={"items": preview_items, "confirm": False})
    assert refused.status_code == 403

    executed = client.post("/repair/execute", json={"items": preview_items, "confirm": True})
    assert executed.status_code == 200
    body = executed.json()
    assert body["backup"]["backup_type"] == "db"
    assert any(a["action_type"] == "cleanup_orphaned_rows" for a in body["actions"])

    job_resp = client.get(f"/jobs/{body['job_id']}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "completed"


def test_repair_plan_empty_on_clean_db(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.get("/repair/plan")
    assert resp.status_code == 200
    assert resp.json()["items"] == []
