"""API-Tests fuer Export (§42) und Pfad-Relokation (§43)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path / "genesis_data"
    settings.paths.data_dir.mkdir(parents=True, exist_ok=True)
    settings.general.safe_test_mode = True
    return create_app(settings)


def _client(app) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media(app) -> int:
    from genesis_core.db.models import MediaFile, MediaKind, Track

    state = app.state.genesis
    with state.db.session() as session:
        mf = MediaFile(
            absolute_path="/music/a.mp3", directory="/music", filename="a.mp3",
            extension=".mp3", kind=MediaKind.MUSIC, size_bytes=10,
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id
        session.add(Track(media_file_id=media_file_id, title="Song Z"))
    return media_file_id


def test_export_json_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    _seed_media(app)
    resp = client.get("/export", params={"format": "json"})
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert data[0]["title"] == "Song Z"


def test_export_csv_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    _seed_media(app)
    resp = client.get("/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "a.mp3" in resp.text


def test_export_xml_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    _seed_media(app)
    resp = client.get("/export", params={"format": "xml"})
    assert resp.status_code == 200
    assert "<genesis_media_export>" in resp.text


def test_export_m3u_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    _seed_media(app)
    resp = client.get("/export", params={"format": "m3u"})
    assert resp.status_code == 200
    assert resp.text.startswith("#EXTM3U")
    assert "/music/a.mp3" in resp.text


def test_export_filters_by_media_file_ids(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    media_id = _seed_media(app)
    resp = client.get("/export", params={"format": "json", "media_file_ids": [media_id]})
    assert len(json.loads(resp.text)) == 1
    resp2 = client.get("/export", params={"format": "json", "media_file_ids": [999999]})
    assert json.loads(resp2.text) == []


def test_relocate_scan_and_apply_round_trip(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    state = app.state.genesis

    from genesis_core.db.models import MediaFile, MediaKind

    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "song.mp3"
    content = b"relocate-api-test-content"
    old_path.write_bytes(content)
    content_hash = hashlib.sha256(content).hexdigest()

    with state.db.session() as session:
        mf = MediaFile(
            absolute_path=str(old_path), directory=str(old_dir), filename="song.mp3",
            extension=".mp3", kind=MediaKind.MUSIC, size_bytes=len(content),
            content_hash_sha256=content_hash, is_missing=True,
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id

    new_path = new_dir / "renamed.mp3"
    old_path.rename(new_path)

    scan_resp = client.post("/relocate/scan", json={"search_roots": [str(new_dir)]})
    assert scan_resp.status_code == 200
    candidates = scan_resp.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["media_file_id"] == media_file_id
    assert candidates[0]["match_method"] == "hash"

    refused = client.post("/relocate/apply", json={"candidates": candidates, "confirm": False})
    assert refused.status_code == 403

    applied = client.post("/relocate/apply", json={"candidates": candidates, "confirm": True})
    assert applied.status_code == 200
    body = applied.json()
    assert body["results"][0]["applied"] is True

    detail = client.get(f"/media/{media_file_id}")
    assert detail.status_code == 200
    assert detail.json()["absolute_path"] == str(new_path)
    assert detail.json()["is_missing"] is False


def test_relocate_scan_empty_without_missing_files(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/relocate/scan", json={"search_roots": [str(tmp_path)]})
    assert resp.status_code == 200
    assert resp.json()["candidates"] == []
