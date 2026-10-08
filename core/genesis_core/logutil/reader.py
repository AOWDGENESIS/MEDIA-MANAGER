"""Lesender Zugriff auf die von `configure_logging()` erzeugten Logdateien
(§54, Gap-Analyse Gap J - Log-Viewer).

Strukturiertes Datei-Logging (TRACE…CRITICAL) existierte bereits
(`genesis_core/logutil/__init__.py`), aber es gab weder einen API-Endpunkt
noch eine echte GUI-Seite, um die Logdatei(en) tatsächlich einzusehen - nur
eine `nav.logs`-Platzhalterseite. Dieses Modul parst die bereits
bestehenden Logdateien (aktuelle Datei + rotierte Backups) und liefert sie
gefiltert/paginiert zurück - rein lesend (Prinzip #4/#5), schreibt nie in
die Logdatei und verändert sie nicht.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Numerische Reihenfolge der Level, konsistent mit `logutil.TRACE_LEVEL` und
# den Standard-`logging`-Stufen - erlaubt einen "mindestens WARNING"-Filter,
# wie es ein echter Log-Viewer braucht (nicht nur exakte Gleichheit).
LEVEL_ORDER = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# Entspricht exakt `StructuredFormatter.format()`:
# "{ts} | {levelname:<8} | {component:<20} | {message}"
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| "
    r"(?P<level>\S+)\s*\| "
    r"(?P<component>.+?)\s*\| "
    r"(?P<message>.*)$"
)


@dataclass
class LogEntry:
    timestamp: str
    level: str
    component: str
    message: str


def _list_log_files_oldest_first(log_dir: Path) -> list[Path]:
    """`RotatingFileHandler`-Semantik: `genesis.log` ist die aktuelle
    (neueste) Datei, `genesis.log.1` die zuletzt rotierte (naechst-aeltere),
    `genesis.log.2` aelter als `.1` usw. Liefert alle tatsaechlich
    vorhandenen Dateien in chronologischer Reihenfolge (aeltest zuerst)."""
    base = log_dir / "genesis.log"
    rotated: list[tuple[int, Path]] = []
    n = 1
    while (log_dir / f"genesis.log.{n}").exists():
        rotated.append((n, log_dir / f"genesis.log.{n}"))
        n += 1
    rotated.sort(key=lambda item: -item[0])
    files = [path for _, path in rotated]
    if base.exists():
        files.append(base)
    return files


def _parse_log_lines(lines: list[str]) -> list[LogEntry]:
    """Gruppiert Folgezeilen ohne eigenen Kopf (z.B. Exception-Tracebacks
    unter `record.exc_info`) als Fortsetzung der zuletzt erkannten
    Log-Zeile, statt sie als eigenstaendige, kopflose Eintraege zu
    behandeln."""
    entries: list[LogEntry] = []
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line:
            continue
        match = _LINE_RE.match(line)
        if match:
            entries.append(
                LogEntry(
                    timestamp=match.group("ts"),
                    level=match.group("level"),
                    component=match.group("component"),
                    message=match.group("message"),
                )
            )
        elif entries:
            entries[-1].message += "\n" + line
    return entries


def read_log_entries(
    log_dir: Path,
    *,
    level: str | None = None,
    component: str | None = None,
    search: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[int, list[LogEntry]]:
    """Liefert `(total, items)` - `total` ist die Anzahl aller nach Filtern
    passenden Eintraege, `items` die angeforderte Seite davon, NEUESTE
    Eintraege zuerst (typisches Log-Viewer-Verhalten: der Nutzer interessiert
    sich zuerst fuer das aktuelle Geschehen, nicht fuer den Dateianfang).

    Liest JEDE verfuegbare Logdatei (aktuell + rotierte Backups) komplett
    neu ein - bei der vom Rotations-Mechanismus ohnehin begrenzten
    Gesamtgroesse (`max_bytes * backup_count`, Standard ca. 10 MB) ist das
    fuer eine von Hand ausgeloeste GUI-Ansicht unproblematisch.
    """
    log_dir = Path(log_dir)
    all_entries: list[LogEntry] = []
    for path in _list_log_files_oldest_first(log_dir):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        all_entries.extend(_parse_log_lines(lines))

    min_level = LEVEL_ORDER.get((level or "").upper())
    filtered = []
    for entry in all_entries:
        if min_level is not None and LEVEL_ORDER.get(entry.level.upper(), 0) < min_level:
            continue
        if component and component.lower() not in entry.component.lower():
            continue
        if search and search.lower() not in entry.message.lower():
            continue
        filtered.append(entry)

    total = len(filtered)
    newest_first = list(reversed(filtered))
    page = newest_first[offset : offset + limit]
    return total, page
