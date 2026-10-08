"""Backup-Modul (§40).

Versionierte Sicherungen von Datenbank und Konfiguration - AUSDRUECKLICH
NIEMALS von Original-Mediendateien (siehe Moduldocstring von
`genesis_core.db.models.Backup`: "backup_type: db/config/rename_journal").
Ein Medienarchiv kann hunderte Gigabyte/Terabyte gross sein; GENESIS sichert
nur die eigenen, kleinen Verwaltungsdaten, aus denen sich im Ernstfall alles
wieder rekonstruieren laesst (Metadaten-DB, Konfiguration) - die eigentlichen
Mediendateien bleiben unveraendert an ihrem Ort (Prinzip #1/#4) und brauchen
daher kein eigenes GENESIS-Backup.

Sicherheitsmechanik:
- `create_db_backup`/`create_config_backup` sind unkritisch (erzeugen nur
  eine zusaetzliche Kopie) und brauchen daher KEINE Bestaetigung.
- Die Datenbanksicherung nutzt die SQLite Online Backup API
  (`sqlite3.Connection.backup`) statt eines rohen Dateikopiervorgangs,
  damit eine konsistente Sicherung entsteht, auch waehrend die
  Datenbank im WAL-Modus aktiv in Benutzung ist (kein Snapshot mitten in
  einem Schreibvorgang).
- `restore_db_backup` ist eine ECHTE Aenderung (ueberschreibt die aktive
  Datenbank) und erfordert daher IMMER `user_confirmed=True` (Prinzip #6,
  §44). Bevor ueberschrieben wird, erstellt die Funktion selbst zuerst ein
  automatisches Backup des AKTUELLEN Standes ("pre_restore") - eine
  Wiederherstellung darf niemals selbst zu unwiderruflichem Datenverlust
  fuehren koennen.
- Alte Versionen werden automatisch rotiert (`max_versions`), damit das
  Backup-Verzeichnis nicht unbegrenzt waechst - betrifft ausschliesslich
  GENESIS-eigene Sicherungskopien, nie Nutzerdaten/Originaldateien.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import shutil
import sqlite3
import uuid
from pathlib import Path

from sqlalchemy import select

from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.db.models import Backup
from genesis_core.logutil import get_logger

log = get_logger("Backup")

DEFAULT_MAX_BACKUP_VERSIONS = 10


class BackupError(RuntimeError):
    """Sicherung/Wiederherstellung fehlgeschlagen (z.B. Quelle fehlt,
    Ziel nicht beschreibbar) - strukturiert gemeldet statt roher
    Stacktrace (§37)."""


class BackupRestoreNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `restore_db_backup` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #6, §44, §40 - eine Wiederherstellung
    ueberschreibt die aktive Datenbank und ist damit eine ECHTE
    Aenderung, kein reiner Lesevorgang)."""


@dataclasses.dataclass
class BackupResult:
    backup_id: int
    backup_type: str
    path: str
    version_label: str
    size_bytes: int
    created_at: str
    pruned_paths: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class RestoreResult:
    pre_restore_backup: BackupResult
    restored_from_backup_id: int
    restored_from_path: str


def _version_label() -> str:
    """Zeitstempel + kurzes Zufallssuffix (Deep-Review-Fund: zwei
    Sicherungen desselben Typs innerhalb derselben Sekunde - z.B. eine
    Datenbanksicherung direkt gefolgt von der automatischen
    "pre_restore"-Sicherung bei `restore_db_backup` - wuerden mit reiner
    Sekundenaufloesung denselben Dateinamen erzeugen und sich so
    gegenseitig auf der Festplatte ueberschreiben, obwohl beide
    Datenbankzeilen als getrennte Backups weiterbestehen. Das Suffix
    macht jeden Dateinamen eindeutig, unabhaengig von der
    Aufruffrequenz oder Systemuhr-Aufloesung.)"""
    now = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{now}-{uuid.uuid4().hex[:8]}"


def _record_backup(db: Database, backup_type: str, path: Path, version_label: str) -> BackupResult:
    size_bytes = path.stat().st_size
    with db.session() as session:
        row = Backup(
            backup_type=backup_type,
            path=str(path),
            version_label=version_label,
            size_bytes=size_bytes,
        )
        session.add(row)
        session.flush()
        backup_id = row.id
        created_at = row.created_at.isoformat()
    return BackupResult(
        backup_id=backup_id,
        backup_type=backup_type,
        path=str(path),
        version_label=version_label,
        size_bytes=size_bytes,
        created_at=created_at,
    )


def _prune_old_backups(db: Database, backup_type: str, max_versions: int) -> list[str]:
    """Behaelt die `max_versions` neuesten Sicherungen eines Typs, entfernt
    aeltere (sowohl Datenbankzeile als auch Datei). Betrifft ausschliesslich
    GENESIS-eigene Sicherungskopien (siehe Moduldocstring)."""
    if max_versions <= 0:
        return []
    removed: list[str] = []
    with db.session() as session:
        rows = list(
            session.execute(
                select(Backup)
                .where(Backup.backup_type == backup_type)
                .order_by(Backup.created_at.desc())
            ).scalars()
        )
        for row in rows[max_versions:]:
            path = Path(row.path)
            try:
                if path.exists():
                    path.unlink()
                removed.append(str(path))
            except OSError as exc:
                log.warning("Konnte altes Backup %s nicht entfernen: %s", path, exc)
                continue
            session.delete(row)
    if removed:
        log.info("%d alte Backup(s) vom Typ '%s' rotiert.", len(removed), backup_type)
    return removed


def create_db_backup(
    db: Database, settings: Settings, *, max_versions: int = DEFAULT_MAX_BACKUP_VERSIONS
) -> BackupResult:
    """Erstellt eine konsistente Sicherung der aktuellen Datenbank mittels
    der SQLite Online Backup API (sicher auch bei aktivem WAL-Modus)."""
    backup_dir = settings.paths.resolved_backup_dir() / "db"
    backup_dir.mkdir(parents=True, exist_ok=True)
    version_label = _version_label()
    dest_path = backup_dir / f"genesis-{version_label}.db"

    try:
        source_conn = sqlite3.connect(str(db.database_path))
        try:
            dest_conn = sqlite3.connect(str(dest_path))
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            source_conn.close()
    except sqlite3.Error as exc:
        raise BackupError(f"Datenbanksicherung fehlgeschlagen: {exc}") from exc

    result = _record_backup(db, "db", dest_path, version_label)
    result.pruned_paths = _prune_old_backups(db, "db", max_versions)
    log.info("Datenbank-Backup erstellt: %s (%d Bytes)", dest_path, result.size_bytes)
    return result


def create_config_backup(
    db: Database,
    settings: Settings,
    config_path: Path | None = None,
    *,
    max_versions: int = DEFAULT_MAX_BACKUP_VERSIONS,
) -> BackupResult:
    """Sichert die (kleine, textuelle) config.yaml - unabhaengig von der
    Datenbanksicherung, damit die Konfiguration auch ohne DB-Wiederher-
    stellung separat zurueckgeholt werden kann."""
    source_path = config_path or (settings.paths.data_dir / "config.yaml")
    if not source_path.exists():
        raise BackupError(f"Konfigurationsdatei nicht gefunden: {source_path}")

    backup_dir = settings.paths.resolved_backup_dir() / "config"
    backup_dir.mkdir(parents=True, exist_ok=True)
    version_label = _version_label()
    dest_path = backup_dir / f"config-{version_label}.yaml"

    try:
        shutil.copy2(source_path, dest_path)
    except OSError as exc:
        raise BackupError(f"Konfigurationssicherung fehlgeschlagen: {exc}") from exc

    result = _record_backup(db, "config", dest_path, version_label)
    result.pruned_paths = _prune_old_backups(db, "config", max_versions)
    log.info("Konfigurations-Backup erstellt: %s", dest_path)
    return result


def list_backups(db: Database, backup_type: str | None = None, limit: int = 50) -> list[Backup]:
    with db.session() as session:
        stmt = select(Backup).order_by(Backup.created_at.desc()).limit(limit)
        if backup_type is not None:
            stmt = stmt.where(Backup.backup_type == backup_type)
        return list(session.execute(stmt).scalars())


def restore_db_backup(
    db: Database, settings: Settings, backup_id: int, *, user_confirmed: bool
) -> RestoreResult:
    """Stellt eine fruehere Datenbanksicherung wieder her - eine ECHTE,
    destruktive Aenderung an der aktiven Datenbank und daher IMMER nur
    nach ausdruecklicher Bestaetigung (Prinzip #6, §44).

    Erstellt VOR dem Ueberschreiben automatisch ein weiteres Backup des
    aktuellen (noch nicht wiederhergestellten) Standes, damit auch eine
    Wiederherstellung selbst jederzeit rueckgaengig gemacht werden kann
    (Prinzip #4 - niemals ein unwiderruflicher Vorgang).

    Bekannte, bewusst in Kauf genommene Eigenheit: Die Backup-Metadaten
    (Tabelle `backups`) leben IN der Datenbank, die hier ueberschrieben
    wird. Nach einer Wiederherstellung eines AELTEREN Standes "verschwinden"
    daher aus Sicht der Backup-Liste alle Backup-EINTRAEGE, die nach dem
    wiederhergestellten Zeitpunkt entstanden sind - die zugehoerigen
    SICHERUNGSDATEIEN selbst bleiben aber unberuehrt auf der Festplatte
    liegen (werden nur nicht mehr in der DB referenziert). Dies entspricht
    dem erwarteten Verhalten einer echten Wiederherstellung (man erhaelt
    exakt den damaligen Stand zurueck) und ist kein Datenverlust der
    Sicherungsdateien selbst."""
    if not user_confirmed:
        raise BackupRestoreNotConfirmedError(
            "Eine Datenbank-Wiederherstellung darf nur nach expliziter "
            "Nutzerbestaetigung erfolgen (Prinzip #6, §44, §40)."
        )

    with db.session() as session:
        backup = session.get(Backup, backup_id)
        if backup is None or backup.backup_type != "db":
            raise BackupError(
                f"Datenbank-Backup mit ID {backup_id} nicht gefunden."
            )
        backup_path = Path(backup.path)

    if not backup_path.exists():
        raise BackupError(
            f"Sicherungsdatei fehlt auf der Festplatte: {backup_path} "
            "(Datenbankeintrag verweist auf eine nicht mehr vorhandene Datei)."
        )

    pre_restore = create_db_backup(db, settings)

    try:
        db.engine.dispose()  # alle gepoolten Verbindungen freigeben, damit kein Handle blockiert
        dest_conn = sqlite3.connect(str(db.database_path))
        try:
            source_conn = sqlite3.connect(str(backup_path))
            try:
                source_conn.backup(dest_conn)
            finally:
                source_conn.close()
        finally:
            dest_conn.close()
    except sqlite3.Error as exc:
        raise BackupError(f"Wiederherstellung fehlgeschlagen: {exc}") from exc

    log.info(
        "Datenbank aus Backup %d (%s) wiederhergestellt - vorheriger Stand "
        "zuvor als Backup %d gesichert.",
        backup_id, backup_path, pre_restore.backup_id,
    )
    return RestoreResult(
        pre_restore_backup=pre_restore,
        restored_from_backup_id=backup_id,
        restored_from_path=str(backup_path),
    )


__all__ = [
    "DEFAULT_MAX_BACKUP_VERSIONS",
    "BackupError",
    "BackupRestoreNotConfirmedError",
    "BackupResult",
    "RestoreResult",
    "create_config_backup",
    "create_db_backup",
    "list_backups",
    "restore_db_backup",
]
