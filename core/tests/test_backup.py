"""Tests fuer das Backup-Modul (§40) - Datenbank/Konfiguration, NIEMALS
Mediendateien (siehe Moduldocstring von genesis_core.backup)."""
from __future__ import annotations

from pathlib import Path

import pytest

from genesis_core.backup import (
    BackupError,
    BackupRestoreNotConfirmedError,
    create_config_backup,
    create_db_backup,
    list_backups,
    restore_db_backup,
)
from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, MediaKind


def test_create_db_backup_creates_file_and_row(db: Database, settings: Settings):
    result = create_db_backup(db, settings)
    assert Path(result.path).exists()
    assert result.size_bytes > 0
    rows = list_backups(db, "db")
    assert any(r.id == result.backup_id for r in rows)


def test_create_config_backup_copies_config_file(db: Database, settings: Settings):
    settings.save()
    result = create_config_backup(db, settings)
    assert Path(result.path).exists()
    assert Path(result.path).read_text(encoding="utf-8") == (
        (settings.paths.data_dir / "config.yaml").read_text(encoding="utf-8")
    )


def test_create_config_backup_missing_source_raises(db: Database, settings: Settings):
    missing = settings.paths.data_dir / "does_not_exist.yaml"
    with pytest.raises(BackupError):
        create_config_backup(db, settings, config_path=missing)


def test_restore_db_backup_requires_confirmation(db: Database, settings: Settings):
    result = create_db_backup(db, settings)
    with pytest.raises(BackupRestoreNotConfirmedError):
        restore_db_backup(db, settings, result.backup_id, user_confirmed=False)


def test_restore_db_backup_round_trip(db: Database, settings: Settings):
    """Sichert eine leere DB, fuegt danach Daten hinzu, stellt die leere
    Sicherung wieder her - die zusaetzlich hinzugefuegten Daten muessen
    danach wieder verschwunden sein (echte Wiederherstellung, kein Merge)."""
    empty_backup = create_db_backup(db, settings)

    with db.session() as session:
        session.add(
            MediaFile(
                absolute_path="/tmp/backup_test/song.mp3", directory="/tmp/backup_test",
                filename="song.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=1,
            )
        )
    with db.session() as session:
        from sqlalchemy import func, select

        count = session.execute(select(func.count()).select_from(MediaFile)).scalar_one()
        assert count == 1

    restore_result = restore_db_backup(db, settings, empty_backup.backup_id, user_confirmed=True)
    assert restore_result.restored_from_backup_id == empty_backup.backup_id
    assert Path(restore_result.pre_restore_backup.path).exists()

    with db.session() as session:
        from sqlalchemy import func, select

        count = session.execute(select(func.count()).select_from(MediaFile)).scalar_one()
        assert count == 0


def test_restore_unknown_backup_id_raises(db: Database, settings: Settings):
    with pytest.raises(BackupError):
        restore_db_backup(db, settings, 999999, user_confirmed=True)


def test_db_backup_rotation_keeps_only_max_versions(db: Database, settings: Settings):
    created = [create_db_backup(db, settings, max_versions=3) for _ in range(5)]
    rows = list_backups(db, "db", limit=100)
    assert len(rows) == 3
    # Die drei NEUESTEN (letzten erzeugten) muessen erhalten bleiben.
    remaining_ids = {r.id for r in rows}
    assert created[-1].backup_id in remaining_ids
    assert created[-2].backup_id in remaining_ids
    assert created[-3].backup_id in remaining_ids
    assert created[0].backup_id not in remaining_ids


def test_version_labels_are_unique_even_within_same_second(db: Database, settings: Settings):
    """Deep-Review-Regressionstest: zwei Backups desselben Typs, die
    (quasi) gleichzeitig entstehen, duerfen sich NICHT gegenseitig auf der
    Festplatte ueberschreiben (siehe Fix in genesis_core.backup._version_label)."""
    r1 = create_db_backup(db, settings)
    r2 = create_db_backup(db, settings)
    assert r1.path != r2.path
    assert Path(r1.path).exists()
    assert Path(r2.path).exists()
