"""Tests fuer den Audio-Fingerprint-API-Endpunkt (Vorstufe fuer §21/ADR-0013).

`fpcalc` ist in der Sandbox installiert (siehe scripts/setup_python_env.sh),
die Tests werden aber dennoch defensiv uebersprungen, falls es einmal fehlt.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import MediaFile, MediaKind
from genesis_core.fingerprint import is_fpcalc_available


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media(app, path: Path) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=MediaKind.MUSIC, size_bytes=path.stat().st_size,
        )
        session.add(mf)
        session.flush()
        return mf.id


def _copy_song(test_library_root: Path, tmp_path: Path, name: str = "song.wav") -> Path:
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.wav"
    dst = tmp_path / name
    shutil.copy2(src, dst)
    return dst


def test_fingerprint_requires_token(tmp_path: Path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    response = client.post("/media/1/fingerprint")
    assert response.status_code in (401, 403)


def test_fingerprint_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    response = client.post("/media/99999/fingerprint")
    assert response.status_code == 404


def test_get_fingerprint_before_computation_returns_null(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    song = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, song)

    response = client.get(f"/media/{media_id}/fingerprint")
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.skipif(not is_fpcalc_available(), reason="fpcalc nicht installiert")
def test_compute_fingerprint_persists_and_is_retrievable(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    song = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, song)

    response = client.post(f"/media/{media_id}/fingerprint")
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm"] == "chromaprint"
    assert body["duration_seconds"] > 0

    get_response = client.get(f"/media/{media_id}/fingerprint")
    assert get_response.status_code == 200
    assert get_response.json()["algorithm"] == "chromaprint"


@pytest.mark.skipif(not is_fpcalc_available(), reason="fpcalc nicht installiert")
def test_recomputing_fingerprint_updates_existing_row_instead_of_duplicating(
    tmp_path: Path, test_library_root: Path
):
    app = _make_app(tmp_path)
    client = _make_client(app)
    song = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, song)

    client.post(f"/media/{media_id}/fingerprint")
    client.post(f"/media/{media_id}/fingerprint")

    with app.state.genesis.db.session() as session:
        from sqlalchemy import select

        from genesis_core.db.models import Fingerprint
        rows = session.execute(
            select(Fingerprint).where(Fingerprint.media_file_id == media_id)
        ).scalars().all()
        assert len(rows) == 1
