#!/usr/bin/env python3
"""Erzeugt einen automatisierten Roh-Lizenzbericht der Python-Abhaengigkeiten
(§33: "Vor jedem Release soll automatisch eine Lizenzprüfung laufen").

Dies ERSETZT NICHT die manuell gepflegte, kuratierte
licenses/THIRD-PARTY-LICENSES.md (ADR-0005) - es liefert nur die
maschinell erkennbaren Rohdaten als Ausgangsbasis/Abgleich fuer das
Release-Gate (Phase 10).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGES = [
    "sqlalchemy", "alembic", "pydantic", "pydantic-settings", "fastapi",
    "uvicorn", "httpx", "PyYAML", "mutagen", "python-multipart", "pytest",
    "pytest-cov", "PySide6", "shiboken6", "starlette", "anyio", "click", "h11",
    # Phase 7 (Voice Studio, §28/§29, ADR-0018): piper-tts selbst ist
    # GPL-3.0-or-later - Stimmen-MODELLE werden separat lizenziert und NICHT
    # per pip installiert, siehe licenses/THIRD-PARTY-LICENSES.md (erst am
    # Projektende final kuratiert).
    "piper-tts", "onnxruntime", "pathvalidate",
    # Phase 8 (Download Center, §30-§32, ADR-0019): yt-dlp ist Unlicense
    # (Public Domain aequivalent).
    "yt-dlp",
]


OUTPUT = Path(__file__).resolve().parent.parent / "licenses" / "RAW_PIP_LICENSES_REPORT.md"


def main() -> int:
    try:
        result = subprocess.run(
            ["pip-licenses", "--format=markdown", "--with-urls", "--packages", *PACKAGES],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError:
        print("pip-licenses ist nicht installiert (siehe core/requirements.txt).", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"pip-licenses fehlgeschlagen: {exc.stderr}", file=sys.stderr)
        return 1

    OUTPUT.write_text(
        "# Automatisch erzeugter Roh-Lizenzbericht (pip-licenses)\n\n"
        "STATUS: Nur maschinell erkannte Rohdaten. Siehe THIRD-PARTY-LICENSES.md "
        "fuer die kuratierte, manuell geprüfte Fassung (ADR-0005).\n\n"
        + result.stdout,
        encoding="utf-8",
    )
    print(f"Bericht geschrieben nach: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
