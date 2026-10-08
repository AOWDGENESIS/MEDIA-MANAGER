"""Deep-Review-Regressionstest (Sitzung 2, Profil Python, Kategorie B6
Performance): ein zweiter Scan derselben, unveraenderten Bibliothek darf
KEINE Datei erneut hashen oder erneut per FFprobe analysieren - sonst
waere inkrementelles Scannen grosser Bibliotheken (Prinzip #12, §57/§58)
nicht gegeben.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from genesis_core.db import Database
from genesis_core.scanner import scanner as scanner_module
from genesis_core.scanner.scanner import scan_directories


def test_unchanged_files_are_not_rehashed_on_second_scan(db: Database, test_library_root: Path):
    scan_directories(db, [test_library_root])  # erster Scan: alles neu, hasht alles

    with patch.object(
        scanner_module, "sha256_of_file", wraps=scanner_module.sha256_of_file
    ) as spy_hash, patch.object(
        scanner_module, "probe_file", wraps=scanner_module.probe_file
    ) as spy_ffprobe:
        result = scan_directories(db, [test_library_root])

    assert result.files_changed == 0
    assert result.files_unchanged == result.files_found
    assert spy_hash.call_count == 0, (
        "Unveraenderte Dateien duerfen bei einem erneuten Scan nicht erneut "
        "gehasht werden (Performance-Regression, Deep Review Sitzung 2)"
    )
    assert spy_ffprobe.call_count == 0, (
        "Unveraenderte Dateien duerfen bei einem erneuten Scan nicht erneut "
        "per FFprobe analysiert werden"
    )


def test_only_actually_changed_file_triggers_rehash(db: Database, tmp_path: Path):
    """Deckt den urspruenglichen Bug ab: FRUEHER loeste die Aenderung EINER
    Datei faelschlich ein Re-FFprobe ALLER nachfolgenden Dateien im selben
    Scan-Lauf aus, weil der kumulierte Zaehler statt eines Pro-Datei-Flags
    geprueft wurde."""
    from testdata_generator.generate import generate_test_library

    lib = tmp_path / "lib"
    lib.mkdir()
    paths = generate_test_library(lib)
    scan_directories(db, [lib])

    # Genau EINE Datei aendern (Groesse/mtime), Rest bleibt unveraendert.
    changed_file = paths["unknown_named_file"]
    changed_file.write_bytes(changed_file.read_bytes() + b"\x00" * 1024)

    with patch.object(
        scanner_module, "probe_file", wraps=scanner_module.probe_file
    ) as spy_ffprobe:
        result = scan_directories(db, [lib])

    assert result.files_changed == 1
    assert result.files_unchanged == result.files_found - 1
    # FFprobe darf nur fuer die EINE tatsaechlich geaenderte Datei laufen,
    # nicht fuer alle danach besuchten Dateien.
    assert spy_ffprobe.call_count == 1
