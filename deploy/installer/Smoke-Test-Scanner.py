"""Windows-CI: exercise the packaged scanner against one generated WAV.

Never accepts an arbitrary user directory: input must be an existing, synthetic
folder under RUNNER_TEMP; the PowerShell driver creates/removes it.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select

from genesis_core.db import Database
from genesis_core.db.models import MediaFile, TechnicalMetadata
from genesis_core.scanner.scanner import scan_directories


def main() -> None:
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    root = (runner_temp / "genesis-ci-real-scan").resolve()
    if not root.is_dir() or root.parent != runner_temp:
        raise RuntimeError("Nur der synthetische RUNNER_TEMP-Ordner ist erlaubt")
    if sorted(p.name for p in root.iterdir()) != ["genesis-offline-ci-tone.wav"]:
        raise RuntimeError("Testordner enthaelt keine einzelne synthetische WAV")
    db = Database(root / "genesis-ci-scan.sqlite")
    result = scan_directories(db, [root])
    assert result.files_found == 1 and result.files_new == 1 and not result.errors, result
    with db.session() as session:
        media = session.execute(select(MediaFile)).scalar_one()
        technical = session.execute(select(TechnicalMetadata)).scalar_one()
        assert media.filename == "genesis-offline-ci-tone.wav"
        assert technical.duration_seconds >= 7, technical.duration_seconds
    print("GENESIS Scan: synthetisches Audio gelesen, Hash und FFprobe-Metadaten gespeichert")


if __name__ == "__main__":
    main()
