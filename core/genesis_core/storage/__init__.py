"""Speicherplatzpruefung vor grossen Operationen (Originalauftrag, Abschnitt
"vor grossen Operationen pruefen, ob genuegend Speicherplatz verfuegbar ist").

Phase 8 (Download Center, §30-§32) ist der erste konkrete Verbraucher dieses
Moduls, weil ein Download aus dem Internet der klassische Fall ist, bei dem
GENESIS vorab NICHT weiss, wie gross das Ergebnis am Ende tatsaechlich wird
(Server-Angaben wie Content-Length koennen fehlen oder veraltet sein) und ein
voller Datentraeger mitten im Schreibvorgang sonst zu abgebrochenen,
halbfertigen Dateien fuehren wuerde.

Backlog (siehe PROGRESS.md): weitere grosse Operationen (Backups,
Stapel-Konvertierung, Lautheits-Normalisierung vieler Dateien) sollten in
einer spaeteren Haertungsphase ebenfalls `ensure_free_space` konsultieren,
statt sich ausschliesslich auf Betriebssystem-Fehler im Nachhinein zu
verlassen.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import shutil
import time
from pathlib import Path


class InsufficientStorageError(RuntimeError):
    """Wird VOR einer grossen Schreiboperation ausgeloest, wenn absehbar ist,
    dass der verfuegbare Speicherplatz nicht ausreicht - verhindert
    abgebrochene/halbfertige Dateien und damit Datenmuell (Prinzip #4)."""


@dataclasses.dataclass
class StorageCheckResult:
    path: str
    free_bytes: int
    required_bytes: int
    min_free_bytes_after: int
    sufficient: bool

    @property
    def free_mb(self) -> float:
        return self.free_bytes / (1024 * 1024)

    @property
    def required_mb(self) -> float:
        return self.required_bytes / (1024 * 1024)


def check_free_space(
    path: str | Path,
    required_bytes: int,
    min_free_bytes_after: int = 0,
) -> StorageCheckResult:
    """Reine Pruef-/Analysefunktion (Prinzip #4/#5) - veraendert nichts,
    meldet nur, ob nach einer hypothetischen Operation von `required_bytes`
    noch mindestens `min_free_bytes_after` frei waeren.

    `path` muss nicht existieren, nur ein vorhandener Vorfahre (z.B. das
    Zielverzeichnis, das ggf. erst noch angelegt wird) - wir laufen den
    Pfad notfalls nach oben, bis ein existierendes Verzeichnis gefunden
    wird, damit auch ein noch nicht angelegter Unterordner geprueft werden
    kann.
    """
    probe = Path(path)
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            break
        probe = parent

    usage = shutil.disk_usage(probe)
    required = max(0, int(required_bytes))
    min_after = max(0, int(min_free_bytes_after))
    sufficient = (usage.free - required) >= min_after
    return StorageCheckResult(
        path=str(probe),
        free_bytes=usage.free,
        required_bytes=required,
        min_free_bytes_after=min_after,
        sufficient=sufficient,
    )


def ensure_free_space(
    path: str | Path,
    required_bytes: int,
    min_free_bytes_after: int = 0,
) -> StorageCheckResult:
    """Wie `check_free_space`, loest aber `InsufficientStorageError` aus,
    wenn nicht genuegend Platz vorhanden ist - zum direkten Einsatz
    unmittelbar vor einer grossen Schreiboperation."""
    result = check_free_space(path, required_bytes, min_free_bytes_after)
    if not result.sufficient:
        raise InsufficientStorageError(
            f"Nicht genuegend freier Speicherplatz unter {result.path}: "
            f"{result.free_mb:.1f} MB frei, benoetigt werden {result.required_mb:.1f} MB "
            f"(Mindestreserve danach: {min_free_bytes_after / (1024 * 1024):.1f} MB)."
        )
    return result


# ---------------------------------------------------------------------------
# §41 Temp-Aufraeumung - Erweiterung dieses Moduls um das Gegenstueck zur
# Speicherplatzpruefung: wo `ensure_free_space` VOR einer grossen Operation
# warnt, raeumt dieser Abschnitt NACHTRAEGLICH liegen gebliebene temporaere
# Dateien auf (z.B. Reste eines abgebrochenen Downloads/Imports, einer
# unterbrochenen Konvertierung). Betroffen ist ausschliesslich das von
# GENESIS selbst verwaltete Temp-Verzeichnis (settings.paths.resolved_
# temp_dir()) - NIEMALS Original-Mediendateien oder vom Nutzer angelegte
# Ordner (Prinzip #1/#4).
# ---------------------------------------------------------------------------


class TempCleanupNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `cleanup_temp_files` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #6, §44) - auch fuer GENESIS-eigene temporaere
    Dateien gilt: keine Loeschung ohne Bestaetigung der zuvor erzeugten
    Vorschau (§39 Scan & Repair ist der uebliche Aufrufer)."""


@dataclasses.dataclass
class TempFileCandidate:
    path: str
    size_bytes: int
    modified_at: str
    age_seconds: float


def scan_temp_files(
    temp_dir: str | Path, *, older_than_seconds: float | None = None
) -> list[TempFileCandidate]:
    """Rein lesende Vorschau (Prinzip #4/#5): listet Dateien im Temp-
    Verzeichnis auf, optional nur solche, die seit mindestens
    `older_than_seconds` nicht mehr veraendert wurden (verhindert, dass
    eine gerade erst erzeugte, noch in Benutzung befindliche Temp-Datei
    faelschlich als "aufraeumbar" gilt)."""
    temp_path = Path(temp_dir)
    if not temp_path.exists():
        return []
    now = time.time()
    results: list[TempFileCandidate] = []
    for entry in temp_path.rglob("*"):
        if not entry.is_file():
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        age_seconds = max(0.0, now - stat.st_mtime)
        if older_than_seconds is not None and age_seconds < older_than_seconds:
            continue
        results.append(
            TempFileCandidate(
                path=str(entry),
                size_bytes=stat.st_size,
                modified_at=dt.datetime.fromtimestamp(
                    stat.st_mtime, dt.UTC
                ).isoformat(),
                age_seconds=age_seconds,
            )
        )
    return results


def cleanup_temp_files(
    temp_dir: str | Path,
    candidates: list[TempFileCandidate] | None = None,
    *,
    older_than_seconds: float | None = None,
    user_confirmed: bool,
) -> list[str]:
    """Loescht die uebergebenen (oder frisch ermittelten) Temp-Datei-
    Kandidaten. Erfordert IMMER `user_confirmed=True` (Prinzip #6, §44) -
    siehe Moduldocstring-Abschnitt. Einzelne fehlschlagende Loeschungen
    (z.B. Datei zwischenzeitlich bereits entfernt/gesperrt) brechen den
    gesamten Vorgang NICHT ab, sondern werden uebersprungen (kein
    gefaehrlicher Halbzustand, da jede Datei fuer sich unabhaengig ist -
    anders als z.B. beim Umbenennen gibt es hier keinen Rollback-Bedarf,
    da eine geloeschte Temp-Datei nie wiederhergestellt werden muss)."""
    if not user_confirmed:
        raise TempCleanupNotConfirmedError(
            "Das Aufraeumen temporaerer Dateien darf nur nach expliziter "
            "Nutzerbestaetigung der zuvor gezeigten Vorschau erfolgen "
            "(Prinzip #6, §44)."
        )
    if candidates is None:
        candidates = scan_temp_files(temp_dir, older_than_seconds=older_than_seconds)

    removed: list[str] = []
    for candidate in candidates:
        try:
            Path(candidate.path).unlink()
            removed.append(candidate.path)
        except OSError:
            continue
    return removed
