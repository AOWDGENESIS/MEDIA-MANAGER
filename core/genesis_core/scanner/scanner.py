"""Media-Scanner (Originalauftrag §6).

Ablauf pro Scan-Lauf, exakt wie im Auftrag gefordert:
 1. Verzeichnisse rekursiv durchsuchen.
 2. Medienformate erkennen.
 3. Dateien klassifizieren.
 4. technische Informationen auslesen (ffprobe).
 5. vorhandene Metadaten auslesen (Phase 2, hier vorbereitet).
 6. Hash erzeugen.
 7. Audio-Fingerprint erzeugen, sofern moeglich (Phase 3 - hier nur Hook).
 8. Dateipfad speichern.
 9. Datenbank aktualisieren.
10. bereits bekannte Dateien erkennen (Pfad+Hash-Abgleich).
11. geaenderte Dateien erkennen (mtime/Hash-Abweichung).
12. verschwundene Dateien erkennen (in DB, aber nicht mehr im Dateisystem).

WICHTIG: Der Scanner öffnet Dateien ausschliesslich lesend. Er verändert,
verschiebt oder löscht niemals eine Datei (§6 letzter Satz, Prinzip #4/#5).

Deep-Review-Korrekturen (Sitzung 2, Profile Python/SQL/API, Kategorie
Performance B6 und fachliche Korrektheit B1):

1. FRUEHER: Fuer JEDE Datei wurde bei jedem Scan-Lauf unbedingt ein
   SHA-256-Hash ueber den kompletten Dateiinhalt berechnet, auch wenn sich
   Groesse und Aenderungsdatum seit dem letzten Scan nicht veraendert
   hatten. Bei grossen Bibliotheken (Prinzip #12, §57 "vermeide unnoetige
   Neuanalyse") haette das bedeutet, bei jedem Scan die komplette
   Bibliothek erneut vollstaendig einzulesen. FIX: Der teure Hash wird nur
   noch berechnet, wenn eine guenstige Vorpruefung (Groesse/mtime) auf eine
   Aenderung hindeutet, oder wenn noch nie gehasht wurde.
2. FRUEHER: Die Entscheidung, ob FFprobe erneut laufen soll, pruefte
   faelschlich den KUMULIERTEN Scan-Zaehler `result.files_changed` statt
   eines pro-Datei-Flags. Sobald irgendeine Datei im laufenden Scan als
   geaendert erkannt wurde, wurde FFprobe fortan fuer ALLE nachfolgenden,
   tatsaechlich unveraenderten Dateien erneut ausgefuehrt. FIX: pro Datei
   lokales `file_changed`-Flag.
3. FRUEHER: Pro Datei wurde eine eigene SELECT-Abfrage gegen die Datenbank
   ausgefuehrt ("N+1"-Muster). FIX: alle bekannten Dateien werden vor der
   Verzeichnis-Traversierung einmalig geladen. Fuer sehr grosse Bibliotheken
   (mehrere Millionen Dateien) sollte dies in Phase 9 (Performance-Hardening)
   durch einen gezielteren, verzeichnisweise inkrementellen Ansatz ersetzt
   werden - siehe PROGRESS.md Backlog.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import os
from pathlib import Path

from sqlalchemy import select

from genesis_core.db import Database
from genesis_core.db.models import MediaFile, TechnicalMetadata
from genesis_core.logutil import get_logger
from genesis_core.scanner.classify import classify_by_extension, is_supported_media_extension
from genesis_core.scanner.ffprobe_util import extract_technical_summary, probe_file
from genesis_core.scanner.hashing import sha256_of_file

log = get_logger("MediaScanner")


@dataclasses.dataclass
class ScanResult:
    scanned_directories: list[str]
    files_found: int = 0
    files_new: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_missing: int = 0
    files_skipped_unsupported: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)


def scan_directories(
    db: Database,
    directories: list[str | Path],
    compute_hash: bool = True,
    run_ffprobe: bool = True,
) -> ScanResult:
    """Fuehrt einen vollstaendigen, lesenden Scan der angegebenen Verzeichnisse
    durch und aktualisiert die Datenbank entsprechend.
    """
    directories = [Path(d) for d in directories]
    result = ScanResult(scanned_directories=[str(d) for d in directories])

    found_absolute_paths: set[str] = set()

    with db.session() as session:
        # Einmaliges Vorladen statt einer Abfrage pro Datei (siehe Modul-
        # Docstring, Punkt 3).
        known_by_path: dict[str, MediaFile] = {
            mf.absolute_path: mf for mf in session.execute(select(MediaFile)).scalars().all()
        }

        for directory in directories:
            if not directory.exists():
                msg = f"Verzeichnis nicht gefunden, wird uebersprungen: {directory}"
                log.warning(msg)
                result.errors.append(msg)
                continue

            log.info("Scan gestartet: %s", directory)
            for root, _dirs, files in os.walk(directory):
                for name in files:
                    full_path = Path(root) / name
                    extension = full_path.suffix.lower()

                    if not is_supported_media_extension(extension):
                        result.files_skipped_unsupported += 1
                        continue

                    result.files_found += 1
                    absolute_path = str(full_path.resolve())
                    found_absolute_paths.add(absolute_path)

                    try:
                        _upsert_media_file(
                            session,
                            full_path,
                            absolute_path,
                            extension,
                            compute_hash=compute_hash,
                            run_ffprobe=run_ffprobe,
                            result=result,
                            known_by_path=known_by_path,
                        )
                    except OSError as exc:
                        msg = f"Fehler beim Lesen von {full_path}: {exc}"
                        log.error(msg)
                        result.errors.append(msg)

        # Verschwundene Dateien erkennen (Punkt 12) - werden markiert, NICHT
        # aus der DB geloescht (Prinzip #4: nichts wird ungefragt geloescht).
        for media_file in known_by_path.values():
            if media_file.is_missing:
                continue
            in_scanned_scope = any(
                media_file.absolute_path.startswith(str(d.resolve()) + os.sep)
                for d in directories
            )
            if in_scanned_scope and media_file.absolute_path not in found_absolute_paths:
                media_file.is_missing = True
                media_file.missing_since = dt.datetime.now(dt.UTC)
                result.files_missing += 1
                log.warning("Datei nicht mehr auffindbar: %s", media_file.absolute_path)

    log.info(
        "Scan abgeschlossen: %d gefunden, %d neu, %d geaendert, %d unveraendert, "
        "%d vermisst, %d Fehler",
        result.files_found,
        result.files_new,
        result.files_changed,
        result.files_unchanged,
        result.files_missing,
        len(result.errors),
    )
    return result


def _upsert_media_file(
    session,
    full_path: Path,
    absolute_path: str,
    extension: str,
    compute_hash: bool,
    run_ffprobe: bool,
    result: ScanResult,
    known_by_path: dict[str, MediaFile],
) -> None:
    stat = full_path.stat()
    # Naiv (UTC) gespeichert, weil SQLite/SQLAlchemy Zeitzoneninfo beim
    # Roundtrip verwirft - sonst schlagen Vergleiche zwischen frisch gelesenem
    # (tz-aware) und aus der DB geladenem (tz-naiv) mtime fehl.
    mtime = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.UTC).replace(tzinfo=None)

    existing = known_by_path.get(absolute_path)
    is_new = existing is None
    file_changed = False  # PRO DATEI, nicht der kumulierte Scan-Zaehler!

    if is_new:
        content_hash = sha256_of_file(full_path) if compute_hash else None
        media_file = MediaFile(
            absolute_path=absolute_path,
            directory=str(full_path.parent),
            filename=full_path.name,
            extension=extension,
            kind=classify_by_extension(extension),
            size_bytes=stat.st_size,
            mtime=mtime,
            content_hash_sha256=content_hash,
            last_scanned_at=dt.datetime.now(dt.UTC),
        )
        session.add(media_file)
        session.flush()
        known_by_path[absolute_path] = media_file
        result.files_new += 1
        file_changed = True
        log.info("Neue Datei erkannt: %s", absolute_path)
    else:
        media_file = existing
        # Guenstige Pruefung zuerst: nur bei Abweichung in Groesse/mtime
        # (oder wenn noch nie gehasht wurde) wird ueberhaupt gehasht.
        cheap_change_detected = (
            media_file.size_bytes != stat.st_size
            or media_file.mtime is None
            or abs((media_file.mtime - mtime).total_seconds()) > 1
        )
        needs_hash = compute_hash and (
            cheap_change_detected or media_file.content_hash_sha256 is None
        )
        content_hash = sha256_of_file(full_path) if needs_hash else media_file.content_hash_sha256
        file_changed = cheap_change_detected or (
            needs_hash and content_hash != media_file.content_hash_sha256
        )

        media_file.is_missing = False
        media_file.missing_since = None
        media_file.last_scanned_at = dt.datetime.now(dt.UTC)
        if file_changed:
            media_file.size_bytes = stat.st_size
            media_file.mtime = mtime
            if content_hash is not None:
                media_file.content_hash_sha256 = content_hash
            result.files_changed += 1
            log.info("Aenderung erkannt: %s", absolute_path)
        else:
            result.files_unchanged += 1

    if run_ffprobe and (is_new or file_changed):
        raw = probe_file(full_path)
        if raw is not None:
            summary = extract_technical_summary(raw)
            tech = session.execute(
                select(TechnicalMetadata).where(
                    TechnicalMetadata.media_file_id == media_file.id
                )
            ).scalar_one_or_none()
            if tech is None:
                tech = TechnicalMetadata(media_file_id=media_file.id, **summary)
                session.add(tech)
            else:
                for key, value in summary.items():
                    setattr(tech, key, value)
