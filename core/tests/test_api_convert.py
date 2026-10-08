"""Tests fuer die Konvertierungs-API-Endpunkte (nav.convert, Phase 3). Nutzt
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


def _copy_song(test_library_root: Path, tmp_path: Path, name: str = "song.wav") -> Path:
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.wav"
    dst = tmp_path / name
    shutil.copy2(src, dst)
    return dst


def test_preview_requires_token(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    unauth = TestClient(app)
    resp = unauth.post(f"/media/{media_id}/convert/preview", json={"target_format": "mp3"})
    assert resp.status_code in (401, 403)


def test_preview_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.post("/media/99999/convert/preview", json={"target_format": "mp3"})
    assert resp.status_code == 404


def test_preview_is_pure_no_file_created(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/convert/preview", json={"target_format": "flac"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["target_format"] == "flac"
    assert not Path(body["output_path"]).exists()


def test_preview_rejects_unknown_format(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/convert/preview", json={"target_format": "wma"})
    assert resp.status_code == 422


def test_apply_without_confirm_is_rejected(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(
        f"/media/{media_id}/convert/apply", json={"target_format": "mp3", "confirm": False},
    )
    assert resp.status_code == 422


def test_apply_with_confirm_creates_new_file_and_history(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    original_bytes = path.read_bytes()

    resp = client.post(
        f"/media/{media_id}/convert/apply",
        json={"target_format": "mp3", "bitrate_kbps": 128, "confirm": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    output_path = Path(body["output_path"])
    assert output_path.exists()
    assert output_path != path
    assert path.read_bytes() == original_bytes

    history = client.get(f"/media/{media_id}/convert").json()
    assert len(history) == 1
    assert history[0]["output_path"] == body["output_path"]
    assert history[0]["target_format"] == "mp3"
    assert history[0]["bitrate_kbps"] == 128


def test_apply_conflict_returns_409(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    payload = {"target_format": "mp3", "confirm": True}

    first = client.post(f"/media/{media_id}/convert/apply", json=payload)
    assert first.status_code == 200

    second = client.post(f"/media/{media_id}/convert/apply", json=payload)
    assert second.status_code == 409


def test_convert_history_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/99999/convert")
    assert resp.status_code == 404
