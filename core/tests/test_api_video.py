"""Tests für die Film-/Serien-API (§24, Phase 5, ADR-0016)."""
from __future__ import annotations

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


def _seed_media(app, path: Path, kind: MediaKind = MediaKind.MOVIE) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=kind, size_bytes=1_000_000,
        )
        session.add(mf)
        session.flush()
        return mf.id


def test_video_tags_preview_unknown_media_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/999/video/tags")
    assert resp.status_code == 404


def test_video_tags_preview_reads_embedded_tags(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Movies" / "Test Movie (2026).mp4"
    media_id = _seed_media(app, path)

    resp = client.get(f"/media/{media_id}/video/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Movie"
    assert "Test Director" in data["director_names"]


def test_episode_detection_preview_for_tagged_episode(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Series" / "Test Series" / "Season 01" / "Test Series - Pilot.mp4"
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/video/episode-detection")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_likely_episode"] is True
    assert data["series_name"] == "Test Series"
    assert data["series_source"] == "tag"
    assert data["season_number"] == 1
    assert data["episode_number"] == 1


def test_episode_detection_preview_for_plain_movie(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Movies" / "Test Movie (2026).mp4"
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/video/episode-detection")
    assert resp.status_code == 200
    assert resp.json()["is_likely_episode"] is False


def test_apply_movie_requires_confirm(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Movies" / "Test Movie (2026).mp4"
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/movie/apply", json={"confirm": False})
    assert resp.status_code == 422


def test_apply_movie_writes_and_persists(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Movies" / "Test Movie (2026).mp4"
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/movie/apply", json={"confirm": True})
    assert resp.status_code == 200
    movie = resp.json()["movie"]
    assert movie["title"] == "Test Movie"
    assert "Test Director" in movie["directors"]
    assert set(movie["actors"]) == {"Test Actor One", "Test Actor Two"}

    resp2 = client.get(f"/media/{media_id}/movie")
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Test Movie"

    # MediaFile.kind muss nach der Bestätigung explizit MOVIE sein.
    detail = client.get(f"/media/{media_id}").json()
    assert detail["kind"] == "movie"


def test_apply_episode_requires_confirm(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Series" / "Test Series" / "Season 01" / "Test Series - Pilot.mp4"
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/episode/apply", json={"confirm": False})
    assert resp.status_code == 422


def test_apply_episode_writes_and_persists(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Series" / "Test Series" / "Season 01" / "Test Series - Pilot.mp4"
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/episode/apply", json={"confirm": True})
    assert resp.status_code == 200
    episode = resp.json()["episode"]
    assert episode["series"] == "Test Series"
    assert episode["season_number"] == 1
    assert episode["episode_number"] == 1
    assert episode["title"] == "Pilot"

    resp2 = client.get(f"/media/{media_id}/episode")
    assert resp2.status_code == 200
    assert resp2.json()["series"] == "Test Series"

    detail = client.get(f"/media/{media_id}").json()
    assert detail["kind"] == "episode"


def test_movie_and_episode_null_when_not_yet_applied(tmp_path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = test_library_root / "Movies" / "Test Movie (2026).mp4"
    media_id = _seed_media(app, path)

    assert client.get(f"/media/{media_id}/movie").json() is None
    assert client.get(f"/media/{media_id}/episode").json() is None
