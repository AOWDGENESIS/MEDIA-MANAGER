"""Startoptionen fuer externe Medien-CLIs aus dem kopflosen Windows-Core.

Der installierte Core laeuft mit pythonw.exe, also OHNE Eltern-Konsole.
Ein normales subprocess.run(ffprobe/fpcalc/ffmpeg) erzeugt dann unter
Windows fuer jede Datei ein neues sichtbares Konsolenfenster. Ein Scan
vieler Dateien kann so den Desktop unbenutzbar machen. Linux/macOS
behalten die normalen subprocess-Defaults; die Pipes/Exitcodes bleiben
bei allen Plattformen unveraendert.
"""
from __future__ import annotations

import subprocess
import sys


def media_cli_options() -> dict[str, int]:
    """Nur Windows: neue Konsolenfenster von FFmpeg/FFprobe/fpcalc verhindern."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
