"""Tests für die Hörbuch-Engine (§23, ADR-0015)."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from genesis_core.audiobook import (
    AudiobookApplyNotConfirmedError,
    AudiobookTagSnapshot,
    ChapterCandidate,
    ChapterDetectionError,
    apply_audiobook_tags,
    detect_chapters,
    export_chapters_csv,
    export_chapters_json,
    generate_fixed_interval_chapters,
    read_audiobook_tags,
    replace_chapters,
)
from genesis_core.db import Database
from genesis_core.db.models import Audiobook, Chapter, MediaFile, MediaKind, Series


def _make_media_file(db: Database, absolute_path: str) -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path=absolute_path,
            directory=str(Path(absolute_path).parent),
            filename=Path(absolute_path).name,
            extension=".m4b",
            kind=MediaKind.AUDIOBOOK,
            size_bytes=1234,
        )
        session.add(mf)
        session.flush()
        return mf.id


# --- read_audiobook_tags -----------------------------------------------------


def test_read_audiobook_tags_missing_file_returns_empty_snapshot():
    snap = read_audiobook_tags("/no/such/file.m4b")
    assert snap.has_any_tag is False
    assert snap.title is None


def test_read_audiobook_tags_real_file(tmp_path):
    pytest.importorskip("mutagen")
    import subprocess

    out = tmp_path / "book.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1",
            "-metadata", "title=Die Reise beginnt",
            "-metadata", "artist=Max Mustermann",
            "-metadata", "album=Die große Reise",
            str(out),
        ],
        check=True, capture_output=True,
    )
    snap = read_audiobook_tags(out)
    assert snap.has_any_tag is True
    assert snap.title == "Die Reise beginnt"
    assert snap.author == "Max Mustermann"
    assert snap.author_source == "artist_field"
    assert snap.series == "Die große Reise"
    assert snap.series_source == "album_field"


# --- apply_audiobook_tags -----------------------------------------------------


def test_apply_audiobook_tags_requires_confirmation(db: Database):
    media_id = _make_media_file(db, "/library/audiobooks/book1.m4b")
    snap = AudiobookTagSnapshot(title="Testbuch", author="Autor Eins")
    with db.session() as session, pytest.raises(AudiobookApplyNotConfirmedError):
        apply_audiobook_tags(session, media_id, snap, user_confirmed=False)


def test_apply_audiobook_tags_writes_row_and_creates_series(db: Database):
    media_id = _make_media_file(db, "/library/audiobooks/book2.m4b")
    snap = AudiobookTagSnapshot(
        title="Band 1",
        author="Autor Zwei",
        narrator="Sprecher Eins",
        series="Die Testreihe",
        volume_number=1,
        publisher="Testverlag",
        year=2020,
        language="de",
        description="Eine Beschreibung.",
    )
    with db.session() as session:
        audiobook = apply_audiobook_tags(session, media_id, snap, user_confirmed=True)
        session.commit()
        audiobook_id = audiobook.id

    with db.session() as session:
        row = session.get(Audiobook, audiobook_id)
        assert row.title == "Band 1"
        assert row.author == "Autor Zwei"
        assert row.narrator == "Sprecher Eins"
        assert row.volume_number == 1
        assert row.publisher == "Testverlag"
        assert row.year == 2020
        series = session.get(Series, row.series_id)
        assert series.name == "Die Testreihe"

    # zweiter Aufruf fuer dieselbe Datei darf KEINE zweite Zeile erzeugen
    # (Update statt Insert, analog Artist/Album get-or-create-Muster)
    with db.session() as session:
        apply_audiobook_tags(
            session, media_id, AudiobookTagSnapshot(title="Band 1 (Update)"), user_confirmed=True,
        )
        session.commit()

    with db.session() as session:
        rows = session.execute(
            select(Audiobook).where(Audiobook.media_file_id == media_id)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "Band 1 (Update)"


def test_apply_audiobook_tags_reuses_existing_series(db: Database):
    media_id_1 = _make_media_file(db, "/library/audiobooks/series_a_1.m4b")
    media_id_2 = _make_media_file(db, "/library/audiobooks/series_a_2.m4b")
    with db.session() as session:
        apply_audiobook_tags(
            session, media_id_1,
            AudiobookTagSnapshot(title="Teil 1", series="Serie A"),
            user_confirmed=True,
        )
        apply_audiobook_tags(
            session, media_id_2,
            AudiobookTagSnapshot(title="Teil 2", series="Serie A"),
            user_confirmed=True,
        )
        session.commit()

    with db.session() as session:
        series_rows = session.execute(select(Series).where(Series.name == "Serie A")).scalars().all()
        assert len(series_rows) == 1


def test_apply_audiobook_tags_unknown_media_file_raises(db: Database):
    with db.session() as session, pytest.raises(ValueError):
        apply_audiobook_tags(session, 999999, AudiobookTagSnapshot(title="x"), user_confirmed=True)


# --- Kapitel-Erkennung --------------------------------------------------------


def test_detect_chapters_nonexistent_file_raises():
    with pytest.raises(ChapterDetectionError):
        detect_chapters("/no/such/file.m4b")


def test_detect_chapters_reads_embedded_chapters(tmp_path):
    import subprocess

    chapters_file = tmp_path / "chapters.txt"
    chapters_file.write_text(
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Kapitel Eins\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=2000\nEND=4000\ntitle=Kapitel Zwei\n",
        encoding="utf-8",
    )
    out = tmp_path / "book_with_chapters.m4a"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=4",
            "-i", str(chapters_file), "-map_metadata", "1",
            "-c:a", "aac", str(out),
        ],
        check=True, capture_output=True,
    )
    candidates = detect_chapters(str(out))
    assert len(candidates) == 2
    assert candidates[0].title == "Kapitel Eins"
    assert candidates[0].start_seconds == pytest.approx(0.0)
    assert candidates[1].title == "Kapitel Zwei"
    assert candidates[1].start_seconds == pytest.approx(2.0, abs=0.01)


# --- generate_fixed_interval_chapters -----------------------------------------


def test_generate_fixed_interval_chapters_basic():
    candidates = generate_fixed_interval_chapters(duration_seconds=25 * 60, interval_minutes=10)
    assert len(candidates) == 3
    assert candidates[0].start_seconds == 0
    assert candidates[0].end_seconds == 600
    assert candidates[2].end_seconds == pytest.approx(1500.0)
    assert candidates[0].title == "Kapitel 1"


def test_generate_fixed_interval_chapters_rejects_invalid_input():
    with pytest.raises(ValueError):
        generate_fixed_interval_chapters(duration_seconds=0, interval_minutes=10)
    with pytest.raises(ValueError):
        generate_fixed_interval_chapters(duration_seconds=100, interval_minutes=0)


# --- replace_chapters + Export -------------------------------------------------


def test_replace_chapters_overwrites_existing(db: Database):
    media_id = _make_media_file(db, "/library/audiobooks/chapters1.m4b")
    candidates_v1 = [ChapterCandidate(index=0, title="Alt", start_seconds=0, end_seconds=60)]
    candidates_v2 = generate_fixed_interval_chapters(duration_seconds=120, interval_minutes=1)

    with db.session() as session:
        replace_chapters(session, media_id, candidates_v1)
        session.commit()

    with db.session() as session:
        replace_chapters(session, media_id, candidates_v2)
        session.commit()

    with db.session() as session:
        rows = session.execute(
            select(Chapter).where(Chapter.media_file_id == media_id).order_by(Chapter.index)
        ).scalars().all()
        assert len(rows) == 2
        assert rows[0].title == "Kapitel 1"
        assert rows[0].start_ms == 0
        assert rows[1].start_ms == 60_000


def test_export_chapters_json_and_csv():
    chapters = [
        Chapter(media_file_id=1, index=0, title="Eins", start_ms=0, end_ms=60000),
        Chapter(media_file_id=1, index=1, title="Zwei", start_ms=60000, end_ms=None),
    ]
    as_json = export_chapters_json(chapters)
    assert "Eins" in as_json
    assert "60000" in as_json

    as_csv = export_chapters_csv(chapters)
    lines = as_csv.strip().splitlines()
    assert lines[0] == "index,title,start_ms,end_ms"
    assert lines[1] == "0,Eins,0,60000"
    assert lines[2] == "1,Zwei,60000,"
