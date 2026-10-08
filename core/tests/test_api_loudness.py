"""Tests fuer die Loudness-API-Endpunkte (§19, Phase 3, ADR-0010). Nutzt
dieselbe token-authentifizierte Test-Client-Fabrik wie test_api_phase2.py."""
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


def test_analyze_requires_token(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    unauth = TestClient(app)
    resp = unauth.post(f"/media/{media_id}/loudness/analyze")
    assert resp.status_code in (401, 403)


def test_analyze_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.post("/media/99999/loudness/analyze")
    assert resp.status_code == 404


def test_analyze_then_list_history(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/loudness/analyze")
    assert resp.status_code == 200
    body = resp.json()
    assert -70.0 < body["integrated_lufs"] < 0.0
    assert body["true_peak_dbtp"] < 5.0

    history = client.get(f"/media/{media_id}/loudness")
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 1
    assert rows[0]["normalized"] is False


def test_preview_without_prior_analysis_returns_409(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/loudness/normalize/preview", json={})
    assert resp.status_code == 409


def test_preview_uses_configured_defaults_and_creates_no_file(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    client.post(f"/media/{media_id}/loudness/analyze")

    resp = client.post(f"/media/{media_id}/loudness/normalize/preview", json={})
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["target_lufs"] == -14.0  # Settings-Default
    assert plan["target_true_peak_dbtp"] == -1.0
    assert not Path(plan["output_path"]).exists()


def test_preview_rejects_video_media_kind(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path, kind=MediaKind.MOVIE)
    client.post(f"/media/{media_id}/loudness/analyze")

    resp = client.post(f"/media/{media_id}/loudness/normalize/preview", json={})
    assert resp.status_code == 409


def test_apply_without_confirm_returns_422_and_creates_no_file(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    client.post(f"/media/{media_id}/loudness/analyze")

    resp = client.post(f"/media/{media_id}/loudness/normalize/apply", json={"confirm": False})
    assert resp.status_code == 422
    assert not (tmp_path / "song.normalized.mp3").exists()


def test_apply_with_confirm_creates_new_file_and_history_row(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    original_bytes = path.read_bytes()
    media_id = _seed_media(app, path)
    client.post(f"/media/{media_id}/loudness/analyze")

    resp = client.post(
        f"/media/{media_id}/loudness/normalize/apply",
        json={"target_lufs": -14.0, "target_true_peak_dbtp": -1.0, "confirm": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert abs(body["achieved_integrated_lufs"] - (-14.0)) < 0.5
    assert Path(body["output_path"]).exists()

    # Original unveraendert (Prinzip #4/#5).
    assert path.read_bytes() == original_bytes

    # Job wurde protokolliert.
    job_resp = client.get(f"/jobs/{body['job_id']}")
    assert job_resp.status_code == 200
    assert job_resp.json()["status"] == "completed"

    # Neue Historie-Zeile mit normalized=True.
    history = client.get(f"/media/{media_id}/loudness").json()
    normalized_rows = [r for r in history if r["normalized"]]
    assert len(normalized_rows) == 1
    assert normalized_rows[0]["normalized_output_path"] == body["output_path"]


def test_apply_refuses_existing_output_file(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = _copy_song(test_library_root, tmp_path)
    media_id = _seed_media(app, path)
    client.post(f"/media/{media_id}/loudness/analyze")
    (tmp_path / "song.normalized.mp3").write_bytes(b"pre-existing, not audio")

    resp = client.post(f"/media/{media_id}/loudness/normalize/apply", json={"confirm": True})
    assert resp.status_code == 409
    assert (tmp_path / "song.normalized.mp3").read_bytes() == b"pre-existing, not audio"
