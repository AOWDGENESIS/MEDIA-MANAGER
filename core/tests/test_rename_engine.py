from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from genesis_core.db import Database
from genesis_core.db.models import Album, Artist, MediaFile, MediaKind, Track
from genesis_core.rename.engine import (
    RenameApplyNotConfirmedError,
    RenameBatchFailedError,
    apply_renames,
    preview_renames,
)
from genesis_core.rename.templates import RenameTemplateError


def _make_file_with_track(tmp_path: Path, filename: str, *, title, track_number, album_title=None):
    path = tmp_path / filename
    path.write_bytes(b"fake-audio-content")
    return path


def _seed_media_and_track(db: Database, path: Path, *, title=None, track_number=None,
                            album_title=None, artist_name=None) -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=MediaKind.MUSIC, size_bytes=path.stat().st_size,
        )
        session.add(mf)
        session.flush()

        album_id = None
        if album_title:
            artist = None
            if artist_name:
                artist = Artist(name=artist_name)
                session.add(artist)
                session.flush()
            album = Album(title=album_title, artist_id=artist.id if artist else None)
            session.add(album)
            session.flush()
            album_id = album.id

        track = Track(
            media_file_id=mf.id, title=title, track_number=track_number,
            album_id=album_id, album_artist=artist_name,
        )
        session.add(track)
        session.flush()
        return mf.id


def test_preview_renders_expected_filename_and_flags_empty_fields(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "01 - old name.mp3", title="New Title", track_number=5)
    media_file_id = _seed_media_and_track(db, path, title="New Title", track_number=5)

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{track:02d} - {title}.{ext}")

    assert len(items) == 1
    item = items[0]
    assert item.new_absolute_path == str(tmp_path / "05 - New Title.mp3")
    assert item.empty_fields == []
    assert item.has_conflict is False
    assert item.is_actionable is True


def test_preview_flags_empty_fields_without_fabricating_data(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "unknown.mp3", title=None, track_number=None)
    media_file_id = _seed_media_and_track(db, path, title=None, track_number=None)

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{artist} - {title}.{ext}")

    assert items[0].empty_fields == ["artist", "title"] or set(items[0].empty_fields) == {"artist", "title"}


def test_preview_detects_extension_change_as_template_error(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "song.mp3", title="Title", track_number=1)
    media_file_id = _seed_media_and_track(db, path, title="Title", track_number=1)

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{title}.txt")

    assert items[0].template_error is not None
    assert items[0].is_actionable is False


def test_preview_detects_batch_internal_collision(db: Database, tmp_path: Path):
    path1 = _make_file_with_track(tmp_path, "a.mp3", title="Same", track_number=1)
    path2 = _make_file_with_track(tmp_path, "b.mp3", title="Same", track_number=1)
    id1 = _seed_media_and_track(db, path1, title="Same", track_number=1)
    id2 = _seed_media_and_track(db, path2, title="Same", track_number=1)

    with db.session() as session:
        items = preview_renames(session, [id1, id2], "{title}.{ext}")

    assert all(item.has_conflict for item in items)


def test_preview_detects_collision_with_existing_file_on_disk(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "song.mp3", title="Title", track_number=1)
    media_file_id = _seed_media_and_track(db, path, title="Title", track_number=1)
    (tmp_path / "Title.mp3").write_bytes(b"already-exists")

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{title}.{ext}")

    assert items[0].has_conflict is True


def test_preview_rejects_directory_separators_in_template(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "song.mp3", title="Title", track_number=1)
    media_file_id = _seed_media_and_track(db, path, title="Title", track_number=1)

    with db.session() as session, pytest.raises(
        RenameTemplateError, match="Verzeichniswechsel"
    ):
        preview_renames(session, [media_file_id], "{artist}/{title}.{ext}")


def test_apply_requires_explicit_confirmation(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "song.mp3", title="Title", track_number=1)
    media_file_id = _seed_media_and_track(db, path, title="Title", track_number=1)

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{track:02d} - {title}.{ext}")
        with pytest.raises(RenameApplyNotConfirmedError):
            apply_renames(session, items, user_confirmed=False)


def test_apply_renames_file_on_disk_and_updates_db(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "old.mp3", title="New Title", track_number=7)
    media_file_id = _seed_media_and_track(db, path, title="New Title", track_number=7)

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{track:02d} - {title}.{ext}")
        results = apply_renames(session, items, user_confirmed=True)

    assert results[0].applied is True
    expected_new_path = tmp_path / "07 - New Title.mp3"
    assert expected_new_path.exists()
    assert not path.exists()

    with db.session() as session:
        media_file = session.get(MediaFile, media_file_id)
        assert media_file.absolute_path == str(expected_new_path)
        assert media_file.filename == "07 - New Title.mp3"


def test_apply_skips_conflicting_items_without_touching_disk(db: Database, tmp_path: Path):
    path = _make_file_with_track(tmp_path, "song.mp3", title="Title", track_number=1)
    media_file_id = _seed_media_and_track(db, path, title="Title", track_number=1)
    blocking_file = tmp_path / "Title.mp3"
    blocking_file.write_bytes(b"already-exists")

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{title}.{ext}")
        results = apply_renames(session, items, user_confirmed=True)

    assert results[0].applied is False
    assert path.exists()  # unveraendert, nichts wurde angefasst
    assert blocking_file.read_bytes() == b"already-exists"


def test_apply_rolls_back_completed_renames_on_mid_batch_failure(db: Database, tmp_path: Path):
    """Kritischer Sicherheitstest: schlaegt Datei 2 von 2 fehl, muss Datei 1
    wieder ihren Originalnamen tragen - kein gefaehrlicher Halbzustand."""
    path1 = _make_file_with_track(tmp_path, "a.mp3", title="First", track_number=1)
    path2 = _make_file_with_track(tmp_path, "b.mp3", title="Second", track_number=2)
    id1 = _seed_media_and_track(db, path1, title="First", track_number=1)
    id2 = _seed_media_and_track(db, path2, title="Second", track_number=2)

    with db.session() as session:
        items = preview_renames(session, [id1, id2], "{track:02d} - {title}.{ext}")

        original_rename = __import__("os").rename
        call_count = {"n": 0}

        def flaky_rename(src, dst):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise OSError("simulierter Fehler (z.B. Berechtigung entzogen)")
            return original_rename(src, dst)

        with (
            patch("genesis_core.rename.engine.os.rename", side_effect=flaky_rename),
            pytest.raises(RenameBatchFailedError),
        ):
            apply_renames(session, items, user_confirmed=True)

    # Datei 1 wurde zurueckgerollt (existiert wieder unter altem Namen)
    assert path1.exists()
    assert path2.exists()
    assert not (tmp_path / "01 - First.mp3").exists()


def test_preview_does_not_flag_case_only_self_rename_as_conflict(db: Database, tmp_path: Path):
    """Deep-Review-Fund F-09 (Sitzung 3): Auf case-insensitiven Dateisystemen
    (Windows/NTFS, macOS/APFS - die eigentlichen Zielplattformen dieser App)
    meldet `Path(target).exists()` bereits True fuer eine reine Gross-
    /Kleinschreibungs-Korrektur der EIGENEN Datei, weil das Betriebssystem
    Ziel- und Quellname als denselben Eintrag behandelt. Das darf NICHT als
    "Zieldatei existiert bereits"-Konflikt mit einer FREMDEN Datei gemeldet
    werden - sonst waere eine Schreibweisen-Korrektur nie moeglich.

    Stellvertreter-Test (Sandbox-/CI-Limitation): ext4 (dieses Testsystem)
    ist case-SENSITIV, Quell- und Zielpfad ("old.mp3" vs. "OLD.mp3") sind
    hier zwei verschiedene, tatsaechlich eigenstaendige Pfade - das reale
    Windows/macOS-Szenario (ein Pfadstring referenziert zwei Schreibweisen
    DERSELBEN Datei) kann auf ext4 nicht direkt nachgestellt werden. Als
    Stellvertreter wird daher ein Hardlink verwendet: zwei verschiedene
    Pfade, die auf denselben Inode zeigen - exakt die Eigenschaft, die
    `os.path.samefile()` erkennen soll und die die neue Konflikt-
    Unterdrueckung in `preview_renames` nutzt. Der Test verifiziert damit
    direkt die neue `samefile`-Logik, nicht das reale Dateisystemverhalten
    selbst (das bleibt auf Windows/macOS manuell zu verifizieren, siehe
    REVIEW_LOG.md Beweisstatus-Hinweis).
    """
    old_path = tmp_path / "old name.mp3"
    old_path.write_bytes(b"fake-audio-content")
    media_file_id = _seed_media_and_track(db, old_path, title="New Title", track_number=1)

    # Zielpfad existiert bereits auf der Platte - aber als Hardlink auf
    # dieselbe physische Datei (Stellvertreter fuer "case-insensitives FS
    # sieht Quelle und Ziel als identisch an").
    target_path = tmp_path / "New Title.mp3"
    import os as _os

    _os.link(old_path, target_path)

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{title}.{ext}")

    assert len(items) == 1
    assert items[0].has_conflict is False, (
        f"Faelschlich als Konflikt markiert: {items[0].conflict_reason}"
    )


def test_preview_still_flags_conflict_with_genuinely_different_file(db: Database, tmp_path: Path):
    """Gegenprobe zu obigem Test: Existiert am Zielpfad eine ECHTE andere
    Datei (anderer Inode), muss der Konflikt weiterhin erkannt werden - die
    neue samefile-Pruefung darf echte Kollisionen nicht verschlucken."""
    old_path = tmp_path / "old name.mp3"
    old_path.write_bytes(b"fake-audio-content")
    media_file_id = _seed_media_and_track(db, old_path, title="New Title", track_number=1)

    target_path = tmp_path / "New Title.mp3"
    target_path.write_bytes(b"eine komplett andere, fremde Datei")  # echte fremde Datei

    with db.session() as session:
        items = preview_renames(session, [media_file_id], "{title}.{ext}")

    assert len(items) == 1
    assert items[0].has_conflict is True
    assert "existiert bereits" in items[0].conflict_reason
