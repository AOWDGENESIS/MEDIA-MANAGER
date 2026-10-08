"""Tests für die Hörbuch- & Kapitel-API (§23, Phase 4, ADR-0015)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import Chapter, MediaFile, MediaKind, TechnicalMetadata


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media(app, path: Path, *, duration_seconds: float | None = None) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=MediaKind.AUDIOBOOK, size_bytes=1_000_000,
        )
        session.add(mf)
        session.flush()
        if duration_seconds is not None:
            session.add(TechnicalMetadata(media_file_id=mf.id, duration_seconds=duration_seconds))
        session.flush()
        return mf.id


def _make_tagged_mp3(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1",
            "-metadata", "title=Die Reise beginnt",
            "-metadata", "artist=Max Mustermann",
            "-metadata", "album=Die große Reise",
            str(path),
        ],
        check=True, capture_output=True,
    )


def _make_chaptered_m4a(path: Path, tmp_path: Path) -> None:
    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text(
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Kapitel Eins\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=2000\nEND=4000\ntitle=Kapitel Zwei\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=4",
            "-i", str(chapters_file), "-map_metadata", "1",
            "-c:a", "aac", str(path),
        ],
        check=True, capture_output=True,
    )


# --- Tags ----------------------------------------------------------------


def test_audiobook_tags_preview_unknown_media_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/999/audiobook/tags")
    assert resp.status_code == 404


def test_audiobook_tags_preview_reads_embedded_tags(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = tmp_path / "book.mp3"
    _make_tagged_mp3(path)
    media_id = _seed_media(app, path)

    resp = client.get(f"/media/{media_id}/audiobook/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Die Reise beginnt"
    assert data["author"] == "Max Mustermann"
    assert data["author_source"] == "artist_field"
    assert data["has_any_tag"] is True


def test_audiobook_tags_apply_requires_confirm(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = tmp_path / "book.mp3"
    _make_tagged_mp3(path)
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/audiobook/tags/apply", json={"confirm": False})
    assert resp.status_code == 422


def test_audiobook_tags_apply_writes_and_persists(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = tmp_path / "book.mp3"
    _make_tagged_mp3(path)
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/audiobook/tags/apply", json={"confirm": True})
    assert resp.status_code == 200
    audiobook = resp.json()["audiobook"]
    assert audiobook["title"] == "Die Reise beginnt"
    assert audiobook["author"] == "Max Mustermann"
    assert audiobook["series"] == "Die große Reise"

    resp2 = client.get(f"/media/{media_id}/audiobook")
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Die Reise beginnt"


# --- Kapitel-Erkennung -----------------------------------------------------


def test_chapters_detect_preview_and_apply(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = tmp_path / "book_chapters.m4a"
    _make_chaptered_m4a(path, tmp_path)
    media_id = _seed_media(app, path)

    preview = client.post(f"/media/{media_id}/chapters/detect")
    assert preview.status_code == 200
    candidates = preview.json()["candidates"]
    assert len(candidates) == 2
    assert candidates[0]["title"] == "Kapitel Eins"

    # kein confirm -> abgelehnt
    rejected = client.post(f"/media/{media_id}/chapters/detect/apply", json={"confirm": False})
    assert rejected.status_code == 422

    applied = client.post(f"/media/{media_id}/chapters/detect/apply", json={"confirm": True})
    assert applied.status_code == 200
    chapters = applied.json()["chapters"]
    assert len(chapters) == 2

    listed = client.get(f"/media/{media_id}/chapters")
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_chapters_detect_unreadable_file_returns_422(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    path = tmp_path / "broken.m4a"
    path.write_bytes(b"not a real media file")
    media_id = _seed_media(app, path)

    resp = client.post(f"/media/{media_id}/chapters/detect")
    assert resp.status_code == 422


# --- Kapitel-Erzeugung (Intervall) -----------------------------------------


def test_chapters_generate_requires_known_duration(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "noduration.mp3", duration_seconds=None)

    resp = client.post(f"/media/{media_id}/chapters/generate", json={"interval_minutes": 10})
    assert resp.status_code == 422


def test_chapters_generate_preview_and_apply(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "longbook.mp3", duration_seconds=25 * 60)

    preview = client.post(f"/media/{media_id}/chapters/generate", json={"interval_minutes": 10})
    assert preview.status_code == 200
    candidates = preview.json()["candidates"]
    assert len(candidates) == 3
    assert candidates[0]["title"] == "Kapitel 1"

    rejected = client.post(
        f"/media/{media_id}/chapters/generate/apply",
        json={"interval_minutes": 10, "confirm": False},
    )
    assert rejected.status_code == 422

    applied = client.post(
        f"/media/{media_id}/chapters/generate/apply",
        json={"interval_minutes": 10, "confirm": True},
    )
    assert applied.status_code == 200
    assert len(applied.json()["chapters"]) == 3


# --- Kapitel umbenennen -----------------------------------------------------


def test_rename_chapter_requires_confirm_and_updates_title(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "book.mp3", duration_seconds=600)
    with app.state.genesis.db.session() as session:
        chapter = Chapter(media_file_id=media_id, index=0, title="Alt", start_ms=0, end_ms=60000)
        session.add(chapter)
        session.flush()
        chapter_id = chapter.id

    rejected = client.patch(
        f"/media/{media_id}/chapters/{chapter_id}", json={"title": "Neu", "confirm": False}
    )
    assert rejected.status_code == 422

    applied = client.patch(
        f"/media/{media_id}/chapters/{chapter_id}", json={"title": "Neu", "confirm": True}
    )
    assert applied.status_code == 200
    assert applied.json()["title"] == "Neu"


def test_rename_chapter_unknown_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "book.mp3", duration_seconds=600)

    resp = client.patch(
        f"/media/{media_id}/chapters/999", json={"title": "Neu", "confirm": True}
    )
    assert resp.status_code == 404


# --- Export ------------------------------------------------------------------


def test_export_chapters_json_and_csv(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app, tmp_path / "book.mp3", duration_seconds=600)
    with app.state.genesis.db.session() as session:
        session.add(Chapter(media_file_id=media_id, index=0, title="Eins", start_ms=0, end_ms=60000))
        session.add(Chapter(media_file_id=media_id, index=1, title="Zwei", start_ms=60000, end_ms=None))
        session.flush()

    as_json = client.get(f"/media/{media_id}/chapters/export", params={"format": "json"})
    assert as_json.status_code == 200
    assert "Eins" in as_json.text

    as_csv = client.get(f"/media/{media_id}/chapters/export", params={"format": "csv"})
    assert as_csv.status_code == 200
    assert "index,title,start_ms,end_ms" in as_csv.text
