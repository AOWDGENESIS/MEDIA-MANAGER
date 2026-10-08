"""Tests fuer die Pfad-Relokation (§43)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, MediaKind
from genesis_core.relocate import (
    MATCH_FILENAME_AND_SIZE,
    MATCH_HASH,
    RelocationApplyNotConfirmedError,
    apply_relocations,
    find_relocation_candidates,
)


def _missing_media_file(db: Database, path: Path, content: bytes) -> int:
    path.write_bytes(content)
    content_hash = hashlib.sha256(content).hexdigest()
    with db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix, kind=MediaKind.MUSIC, size_bytes=len(content),
            content_hash_sha256=content_hash, is_missing=True,
        )
        session.add(mf)
        session.flush()
        return mf.id


def test_find_relocation_candidates_returns_empty_without_missing_files(
    db: Database, settings: Settings
):
    assert find_relocation_candidates(db, [settings.paths.data_dir]) == []


def test_find_relocation_candidates_matches_by_hash_even_if_renamed(
    db: Database, settings: Settings, tmp_path: Path
):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "song.mp3"
    media_file_id = _missing_media_file(db, old_path, b"identical-content-12345")

    new_path = new_dir / "renamed.mp3"
    old_path.rename(new_path)

    candidates = find_relocation_candidates(db, [new_dir])
    assert len(candidates) == 1
    assert candidates[0].media_file_id == media_file_id
    assert candidates[0].match_method == MATCH_HASH
    assert candidates[0].confidence == 1.0
    assert candidates[0].new_absolute_path == str(new_path)


def test_find_relocation_candidates_falls_back_to_filename_and_size(
    db: Database, settings: Settings, tmp_path: Path
):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "song.mp3"
    content = b"some content"
    _missing_media_file(db, old_path, content)

    # Keine content_hash_sha256-Uebereinstimmung moeglich, weil die DB-Zeile
    # absichtlich einen ANDEREN Hash hat (simuliert "Hash nie berechnet"
    # bzw. leicht veraenderte Bytes) - aber gleicher Name+Groesse am neuen Ort.
    with db.session() as session:
        from sqlalchemy import select

        mf = session.execute(select(MediaFile)).scalars().first()
        mf.content_hash_sha256 = "does-not-match-anything"

    new_path = new_dir / "song.mp3"  # gleicher Dateiname
    new_path.write_bytes(content)  # gleiche Groesse
    old_path.unlink()

    candidates = find_relocation_candidates(db, [new_dir])
    assert len(candidates) == 1
    assert candidates[0].match_method == MATCH_FILENAME_AND_SIZE
    assert candidates[0].confidence == 0.7


def test_find_relocation_candidates_ignores_paths_already_known(
    db: Database, settings: Settings, tmp_path: Path
):
    """Eine Kandidatendatei, die bereits einer ANDEREN (nicht vermissten)
    MediaFile zugeordnet ist, darf nie als Relokationsziel vorgeschlagen
    werden (sonst wuerden zwei Datenbankzeilen auf dieselbe Datei zeigen)."""
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    old_path = old_dir / "song.mp3"
    _missing_media_file(db, old_path, b"content-a")

    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_path = other_dir / "other.mp3"
    other_path.write_bytes(b"content-a")  # identischer Inhalt, aber...
    with db.session() as session:
        session.add(
            MediaFile(
                absolute_path=str(other_path), directory=str(other_dir),
                filename="other.mp3", extension=".mp3", kind=MediaKind.MUSIC,
                size_bytes=len(b"content-a"), content_hash_sha256=hashlib.sha256(b"content-a").hexdigest(),
                is_missing=False,
            )
        )

    candidates = find_relocation_candidates(db, [other_dir])
    assert candidates == []


def test_apply_relocations_requires_confirmation(db: Database, settings: Settings, tmp_path: Path):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "song.mp3"
    _missing_media_file(db, old_path, b"content-xyz")
    new_path = new_dir / "song.mp3"
    old_path.rename(new_path)

    candidates = find_relocation_candidates(db, [new_dir])
    with pytest.raises(RelocationApplyNotConfirmedError):
        apply_relocations(db, candidates, user_confirmed=False)


def test_apply_relocations_updates_media_file_and_clears_missing_flag(
    db: Database, settings: Settings, tmp_path: Path
):
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_path = old_dir / "song.mp3"
    media_file_id = _missing_media_file(db, old_path, b"content-xyz")
    new_path = new_dir / "renamed.mp3"
    old_path.rename(new_path)

    candidates = find_relocation_candidates(db, [new_dir])
    results = apply_relocations(db, candidates, user_confirmed=True)
    assert results[0].applied is True

    with db.session() as session:
        mf = session.get(MediaFile, media_file_id)
        assert mf.absolute_path == str(new_path)
        assert mf.filename == "renamed.mp3"
        assert mf.is_missing is False
        assert mf.missing_since is None


def test_apply_relocations_skips_candidate_whose_target_vanished(
    db: Database, settings: Settings, tmp_path: Path
):
    from genesis_core.relocate import RelocationCandidate

    old_dir = tmp_path / "old"
    old_dir.mkdir()
    old_path = old_dir / "song.mp3"
    media_file_id = _missing_media_file(db, old_path, b"x")

    phantom = RelocationCandidate(
        media_file_id=media_file_id, old_absolute_path=str(old_path),
        new_absolute_path=str(tmp_path / "does_not_exist.mp3"),
        match_method=MATCH_HASH, confidence=1.0,
    )
    results = apply_relocations(db, [phantom], user_confirmed=True)
    assert results[0].applied is False
    assert "existiert nicht" in results[0].reason
