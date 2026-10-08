"""Tests fuer die Audio-Cutter-API-Endpunkte (§18, Phase 3, ADR-0011). Nutzt
dieselbe token-authentifizierte Test-Client-Fabrik wie test_api_loudness.py.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import MediaFile, MediaKind


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media(app, path: Path, kind: MediaKind = MediaKind.MUSIC) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=kind, size_bytes=path.stat().st_size,
        )
        session.add(mf)
        session.flush()
        return mf.id


def _copy_song(test_library_root: Path, tmp_path: Path, name: str = "song.mp3") -> Path:
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    dst = tmp_path / name
    shutil.copy2(src, dst)
    return dst


def test_waveform_requires_token(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    unauth = TestClient(app)
    resp = unauth.get(f"/media/{media_id}/cutter/waveform")
    assert resp.status_code in (401, 403)


def test_waveform_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/99999/cutter/waveform")
    assert resp.status_code == 404


def test_waveform_returns_png(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.get(f"/media/{media_id}/cutter/waveform")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert len(resp.content) > 0


def test_waveform_is_cached_on_second_call(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    first = client.get(f"/media/{media_id}/cutter/waveform")
    cache_path = app.state.genesis.cutter_waveform_dir / f"{media_id}.png"
    mtime_after_first = cache_path.stat().st_mtime

    second = client.get(f"/media/{media_id}/cutter/waveform")

    assert first.status_code == second.status_code == 200
    assert cache_path.stat().st_mtime == mtime_after_first


def test_preview_is_pure_no_file_created(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(
        f"/media/{media_id}/cutter/preview",
        json={"start_seconds": 0.0, "end_seconds": 2.0, "export_format": "mp3"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["selection_duration_seconds"] == 2.0
    assert body["has_conflict"] is False
    assert not Path(body["output_path"]).exists()


def test_preview_rejects_invalid_selection(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(
        f"/media/{media_id}/cutter/preview",
        json={"start_seconds": 5.0, "end_seconds": 1.0, "export_format": "mp3"},
    )

    assert resp.status_code == 422


def test_apply_without_confirm_is_rejected(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(
        f"/media/{media_id}/cutter/apply",
        json={"start_seconds": 0.0, "end_seconds": 2.0, "export_format": "mp3", "confirm": False},
    )

    assert resp.status_code == 422


def test_apply_with_confirm_creates_new_file_and_history(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    original_bytes = path.read_bytes()

    resp = client.post(
        f"/media/{media_id}/cutter/apply",
        json={"start_seconds": 0.0, "end_seconds": 2.0, "export_format": "mp3", "confirm": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    output_path = Path(body["output_path"])
    assert output_path.exists()
    assert output_path != path
    # Original unveraendert (Prinzip #4/#5)
    assert path.read_bytes() == original_bytes

    history = client.get(f"/media/{media_id}/cutter").json()
    assert len(history) == 1
    assert history[0]["output_path"] == body["output_path"]
    assert history[0]["start_seconds"] == 0.0
    assert history[0]["end_seconds"] == 2.0


def test_apply_conflict_returns_409(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    payload = {"start_seconds": 0.0, "end_seconds": 2.0, "export_format": "mp3", "confirm": True}

    first = client.post(f"/media/{media_id}/cutter/apply", json=payload)
    assert first.status_code == 200

    second = client.post(f"/media/{media_id}/cutter/apply", json=payload)
    assert second.status_code == 409


def test_cutter_history_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/99999/cutter")
    assert resp.status_code == 404
