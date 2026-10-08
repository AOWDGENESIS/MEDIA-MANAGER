"""Strukturiertes Logging (Originalauftrag §54).

Log-Level TRACE..CRITICAL, rotierende Dateien (damit Logs den Workspace nicht
volllaufen lassen - Ressourcen-Disziplin), plus ein einfaches strukturiertes
Format, das spaeter 1:1 in einer UI-Logansicht dargestellt werden kann.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, "TRACE")


def _trace(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(TRACE_LEVEL):
        self._log(TRACE_LEVEL, message, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]


class StructuredFormatter(logging.Formatter):
    """Entspricht dem im Originalauftrag §54 gezeigten Beispielformat:

    2026-09-30 21:00:01
    INFO
    MediaScanner
    Scan started
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        component = record.name
        message = record.getMessage()
        line = f"{ts} | {record.levelname:<8} | {component:<20} | {message}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
    max_bytes: int = 2_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    """Richtet das Root-Logging fuer GENESIS ein.

    - Konsole: menschenlesbar.
    - Datei (falls log_dir angegeben): rotierend, max_bytes*backup_count
      begrenzt die Gesamtgroesse bewusst (Ressourcen-Disziplin: Logs duerfen
      den Workspace nicht volllaufen lassen).
    """
    root = logging.getLogger("genesis")
    root.setLevel(level)
    root.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    root.addHandler(console_handler)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "genesis.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(StructuredFormatter())
        root.addHandler(file_handler)

    return root


def get_logger(component: str) -> logging.Logger:
    """Liefert einen Logger fuer ein bestimmtes Modul/Komponente, z.B.
    ``get_logger("MediaScanner")`` -> Ausgabe zeigt "MediaScanner" als
    Komponente, wie im Originalauftrag gefordert.
    """
    return logging.getLogger(f"genesis.{component}")
