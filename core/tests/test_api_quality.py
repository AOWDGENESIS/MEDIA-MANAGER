"""Tests fuer die Qualitätsanalyse-API (§20, Phase 3, ADR-0014)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import Loudness, MediaFile, MediaKind, TechnicalMetadata, Track


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media(
    app,
    path: Path,
    *,
    with_technical: bool = True,
    audio_codec: str = "mp3",
    extension: str | None = None,
    bitrate_kbps: int | None = 320,
    sample_rate_hz: int | None = 44100,
    bit_depth: int | None = None,
    channels: int | None = 2,
    duration_seconds: float | None = 180.0,
    last_scan_error: str | None = None,
    tag_duration_seconds: float | None = None,
    loudness: tuple[float, float] | None = None,
) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=extension or path.suffix.lower(), kind=MediaKind.MUSIC,
            size_bytes=1_000_000, last_scan_error=last_scan_error,
        )
        session.add(mf)
        session.flush()
        if with_technical:
            session.add(
                TechnicalMetadata(
                    media_file_id=mf.id, audio_codec=audio_codec, bitrate_kbps=bitrate_kbps,
                    sample_rate_hz=sample_rate_hz, bit_depth=bit_depth, channels=channels,
                    duration_seconds=duration_seconds,
                )
            )
        if tag_duration_seconds is not None:
            session.add(Track(media_file_id=mf.id, duration_seconds=tag_duration_seconds))
        if loudness is not None:
            session.add(
                Loudness(media_file_id=mf.id, integrated_lufs=loudness[0], true_peak_dbtp=loudness[1])
            )
        session.flush()
        return mf.id


def test_analyze_requires_token(tmp_path: Path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    response = client.post("/media/1/quality/analyze")
    assert response.status_code in (401, 403)


def test_analyze_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    response = client.post("/media/99999/quality/analyze")
    assert response.status_code == 404


def test_analyze_without_technical_metadata_returns_422(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.mp3", with_technical=False)
    response = client.post(f"/media/{media_id}/quality/analyze")
    assert response.status_code == 422


def test_analyze_clean_file_reports_no_suspicions(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.mp3", tag_duration_seconds=180.0)
    response = client.post(f"/media/{media_id}/quality/analyze")
    assert response.status_code == 200
    body = response.json()
    assert body["suspected_upscale"] is False
    assert body["suspected_transcode"] is False
    assert body["suspected_corruption"] is False
    assert body["suspected_truncation"] is False


def test_analyze_detects_transcode_mismatch(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.flac", audio_codec="mp3")
    response = client.post(f"/media/{media_id}/quality/analyze")
    assert response.json()["suspected_transcode"] is True


def test_analyze_detects_truncation_against_tag_duration(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(
        app, tmp_path / "a.mp3", duration_seconds=100.0, tag_duration_seconds=240.0
    )
    response = client.post(f"/media/{media_id}/quality/analyze")
    assert response.json()["suspected_truncation"] is True


def test_analyze_detects_corruption_from_scan_error(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.mp3", last_scan_error="invalid header")
    response = client.post(f"/media/{media_id}/quality/analyze")
    assert response.json()["suspected_corruption"] is True


def test_analyze_detects_upscale_suspicion(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(
        app, tmp_path / "a.flac", audio_codec="flac", bitrate_kbps=150,
        sample_rate_hz=44100, bit_depth=16, channels=2,
    )
    response = client.post(f"/media/{media_id}/quality/analyze")
    assert response.json()["suspected_upscale"] is True


def test_analyze_includes_loudness_notes_when_available(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.mp3", loudness=(-14.0, 1.5))
    response = client.post(f"/media/{media_id}/quality/analyze")
    notes = response.json()["notes"]
    assert any("dBTP" in n for n in notes)


def test_get_quality_before_analysis_returns_null(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.mp3")
    response = client.get(f"/media/{media_id}/quality")
    assert response.status_code == 200
    assert response.json() is None


def test_get_quality_after_analysis_returns_persisted_report(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.flac", audio_codec="mp3")
    client.post(f"/media/{media_id}/quality/analyze")

    response = client.get(f"/media/{media_id}/quality")
    assert response.status_code == 200
    body = response.json()
    assert body["suspected_transcode"] is True
    assert isinstance(body["notes"], list) and body["notes"]


def test_get_quality_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    response = client.get("/media/99999/quality")
    assert response.status_code == 404


def test_reanalysis_overwrites_previous_result_instead_of_duplicating(tmp_path: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "a.flac", audio_codec="mp3")
    client.post(f"/media/{media_id}/quality/analyze")
    client.post(f"/media/{media_id}/quality/analyze")

    with app.state.genesis.db.session() as session:
        from sqlalchemy import select
        rows = session.execute(
            select(TechnicalMetadata).where(TechnicalMetadata.media_file_id == media_id)
        ).scalars().all()
        assert len(rows) == 1
