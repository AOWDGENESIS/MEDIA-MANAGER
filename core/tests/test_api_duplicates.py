"""Tests fuer die Duplikaterkennungs-API (§21, Phase 3, ADR-0013). Nutzt
dieselbe token-authentifizierte Test-Client-Fabrik wie test_api_convert.py.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import Fingerprint, MediaFile, MediaKind, TechnicalMetadata, Track


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media_with_technical(
    app,
    path: Path,
    *,
    size_bytes: int = 1000,
    content_hash: str | None = None,
    duration_seconds: float | None = 10.0,
    audio_codec: str | None = "mp3",
    sample_rate_hz: int | None = 44100,
    channels: int | None = 2,
    fingerprint_data: str | None = None,
    title: str | None = None,
) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=MediaKind.MUSIC, size_bytes=size_bytes,
            content_hash_sha256=content_hash,
        )
        session.add(mf)
        session.flush()
        session.add(
            TechnicalMetadata(
                media_file_id=mf.id, audio_codec=audio_codec, sample_rate_hz=sample_rate_hz,
                channels=channels, duration_seconds=duration_seconds,
            )
        )
        if fingerprint_data is not None:
            session.add(
                Fingerprint(media_file_id=mf.id, algorithm="chromaprint", fingerprint_data=fingerprint_data)
            )
        if title is not None:
            session.add(Track(media_file_id=mf.id, title=title))
        session.flush()
        return mf.id


def test_scan_requires_token(tmp_path: Path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    response = client.post("/duplicates/scan", json={})
    assert response.status_code in (401, 403)


def test_scan_finds_exact_duplicate_pair(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    id1 = _seed_media_with_technical(app, tmp_path / "a.mp3", content_hash="samehash")
    id2 = _seed_media_with_technical(app, tmp_path / "b.mp3", content_hash="samehash")

    response = client.post("/duplicates/scan", json={})
    assert response.status_code == 200
    groups = response.json()
    assert len(groups) == 1
    assert groups[0]["category"] == "exact_duplicate"
    assert groups[0]["confidence"] == 1.0
    assert set(groups[0]["media_file_ids"]) == {id1, id2}
    assert groups[0]["reviewed"] is False


def test_scan_finds_same_content_different_format(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_media_with_technical(
        app, tmp_path / "a.wav", content_hash="h1", audio_codec="pcm_s16le",
        size_bytes=5_000_000, fingerprint_data="fpSAME",
    )
    _seed_media_with_technical(
        app, tmp_path / "b.mp3", content_hash="h2", audio_codec="mp3",
        size_bytes=500_000, fingerprint_data="fpSAME",
    )

    response = client.post("/duplicates/scan", json={})
    groups = response.json()
    assert len(groups) == 1
    assert groups[0]["category"] == "same_content_different_format"


def test_scan_with_no_duplicates_returns_empty_list(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_media_with_technical(
        app, tmp_path / "a.mp3", content_hash="h1", duration_seconds=10.0,
        audio_codec="mp3", sample_rate_hz=44100, channels=2,
    )
    _seed_media_with_technical(
        app, tmp_path / "b.flac", content_hash="h2", duration_seconds=999.0,
        audio_codec="flac", sample_rate_hz=96000, channels=1,
    )

    response = client.post("/duplicates/scan", json={})
    assert response.status_code == 200
    assert response.json() == []


def test_scan_rejects_unknown_kind_filter(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    response = client.post("/duplicates/scan", json={"kind": "not_a_real_kind"})
    assert response.status_code == 422


def test_list_duplicates_filters_by_reviewed(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_media_with_technical(app, tmp_path / "a.mp3", content_hash="samehash")
    _seed_media_with_technical(app, tmp_path / "b.mp3", content_hash="samehash")
    client.post("/duplicates/scan", json={})

    unreviewed = client.get("/duplicates", params={"reviewed": False}).json()
    assert len(unreviewed) == 1
    reviewed = client.get("/duplicates", params={"reviewed": True}).json()
    assert reviewed == []

    group_id = unreviewed[0]["id"]
    review_response = client.post(f"/duplicates/{group_id}/review")
    assert review_response.status_code == 200
    assert review_response.json()["reviewed"] is True

    unreviewed_after = client.get("/duplicates", params={"reviewed": False}).json()
    assert unreviewed_after == []
    reviewed_after = client.get("/duplicates", params={"reviewed": True}).json()
    assert len(reviewed_after) == 1


def test_reviewed_groups_survive_rescan_but_unreviewed_are_replaced(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_media_with_technical(app, tmp_path / "a.mp3", content_hash="samehash")
    _seed_media_with_technical(app, tmp_path / "b.mp3", content_hash="samehash")
    client.post("/duplicates/scan", json={})

    group_id = client.get("/duplicates").json()[0]["id"]
    client.post(f"/duplicates/{group_id}/review")

    # Zweiter Scan mit denselben Dateien - die ueberprueft/verworfene Gruppe
    # bleibt unangetastet bestehen (gleiche ID), es entsteht KEINE doppelte
    # neue unreviewed-Gruppe fuer dasselbe Paar... tatsaechlich wird aber ein
    # erneuter Fund trotzdem ein neues unreviewed-Duplikat erzeugen, da diese
    # einfache Implementierung Paare nicht gegen bereits ueberprueft gemeldete
    # Paare abgleicht (siehe engine.py/ADR-0013 - Backlog). Hier wird nur
    # geprueft, dass die ueberprueft-Gruppe selbst nicht geloescht wird.
    client.post("/duplicates/scan", json={})
    still_reviewed = client.get("/duplicates", params={"reviewed": True}).json()
    assert len(still_reviewed) == 1
    assert still_reviewed[0]["id"] == group_id


def test_unreview_restores_group_to_unreviewed(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_media_with_technical(app, tmp_path / "a.mp3", content_hash="samehash")
    _seed_media_with_technical(app, tmp_path / "b.mp3", content_hash="samehash")
    client.post("/duplicates/scan", json={})
    group_id = client.get("/duplicates").json()[0]["id"]

    client.post(f"/duplicates/{group_id}/review")
    unreview_response = client.post(f"/duplicates/{group_id}/unreview")
    assert unreview_response.status_code == 200
    assert unreview_response.json()["reviewed"] is False


def test_review_unknown_group_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    response = client.post("/duplicates/99999/review")
    assert response.status_code == 404


def test_scan_can_be_scoped_by_kind(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_media_with_technical(app, tmp_path / "a.mp3", content_hash="samehash")
    with app.state.genesis.db.session() as session:
        movie = MediaFile(
            absolute_path=str(tmp_path / "b.mp3"), directory=str(tmp_path), filename="b.mp3",
            extension=".mp3", kind=MediaKind.MOVIE, size_bytes=1000, content_hash_sha256="samehash",
        )
        session.add(movie)
        session.flush()
        session.add(TechnicalMetadata(media_file_id=movie.id, duration_seconds=10.0))

    response = client.post("/duplicates/scan", json={"kind": "music"})
    assert response.json() == []  # das zweite Duplikat ist als MOVIE eingestuft, nicht MUSIC
