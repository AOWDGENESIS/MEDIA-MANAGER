"""Tests für `genesis_core.logutil.reader` (§54, Gap-Analyse Gap J -
Log-Viewer).

Strukturiertes Datei-Logging existierte bereits (`genesis_core.logutil`) -
dieser Reader macht es erstmals lesend abfragbar (gefiltert/paginiert),
ohne die Logdatei selbst jemals zu verändern (Prinzip #4/#5).
"""
from __future__ import annotations

import logging
from pathlib import Path

from genesis_core.logutil import configure_logging, get_logger
from genesis_core.logutil.reader import read_log_entries


def _seed_log(log_dir: Path) -> None:
    configure_logging(log_dir=log_dir, level=logging.DEBUG)
    scanner = get_logger("MediaScanner")
    scanner.info("Scan gestartet: /music")
    scanner.warning("Datei fehlt: /music/x.mp3")
    try:
        raise ValueError("boom")
    except ValueError:
        scanner.error("Fehler beim Scan", exc_info=True)
    download = get_logger("DownloadEngine")
    download.info("Import abgeschlossen")


def test_reads_all_entries_newest_first(tmp_path):
    _seed_log(tmp_path)
    total, entries = read_log_entries(tmp_path, limit=10)
    assert total == 4
    assert [e.component.strip() for e in entries] == [
        "genesis.DownloadEngine",
        "genesis.MediaScanner",
        "genesis.MediaScanner",
        "genesis.MediaScanner",
    ]
    assert entries[0].message == "Import abgeschlossen"


def test_traceback_lines_are_attached_to_their_log_entry(tmp_path):
    _seed_log(tmp_path)
    _total, entries = read_log_entries(tmp_path, limit=10)
    error_entry = next(e for e in entries if e.level == "ERROR")
    assert "Fehler beim Scan" in error_entry.message
    assert "Traceback" in error_entry.message
    assert "ValueError: boom" in error_entry.message


def test_level_filter_is_minimum_not_exact(tmp_path):
    _seed_log(tmp_path)
    total, entries = read_log_entries(tmp_path, level="WARNING")
    assert total == 2
    assert {e.level for e in entries} == {"WARNING", "ERROR"}


def test_level_filter_case_insensitive(tmp_path):
    _seed_log(tmp_path)
    total, _entries = read_log_entries(tmp_path, level="warning")
    assert total == 2


def test_component_filter_matches_substring(tmp_path):
    _seed_log(tmp_path)
    total, entries = read_log_entries(tmp_path, component="download")
    assert total == 1
    assert entries[0].component.strip() == "genesis.DownloadEngine"


def test_search_filter_matches_message_substring(tmp_path):
    _seed_log(tmp_path)
    total, entries = read_log_entries(tmp_path, search="fehlt")
    assert total == 1
    assert "Datei fehlt" in entries[0].message


def test_pagination_with_offset_and_limit(tmp_path):
    _seed_log(tmp_path)
    _total, page1 = read_log_entries(tmp_path, limit=2, offset=0)
    _total, page2 = read_log_entries(tmp_path, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].message != page2[0].message
    # Keine Ueberschneidung zwischen den Seiten.
    assert {id(e) for e in page1}.isdisjoint({id(e) for e in page2})


def test_missing_log_directory_returns_empty_result(tmp_path):
    missing = tmp_path / "does-not-exist"
    total, entries = read_log_entries(missing)
    assert total == 0
    assert entries == []


def test_combined_filters(tmp_path):
    _seed_log(tmp_path)
    # level ist ein MINDEST-Level (§54-Reihenfolge) - "MediaScanner" liefert
    # bei INFO alle drei seiner Meldungen (INFO/WARNING/ERROR liegen alle
    # auf oder ueber INFO), waehrend WARNING nur die zwei schwereren davon
    # durchlaesst.
    total_info, _entries_info = read_log_entries(
        tmp_path, level="INFO", component="MediaScanner"
    )
    assert total_info == 3

    total_warning, entries_warning = read_log_entries(
        tmp_path, level="WARNING", component="MediaScanner"
    )
    assert total_warning == 2
    assert {e.level for e in entries_warning} == {"WARNING", "ERROR"}


def test_rotated_backup_files_are_included(tmp_path):
    """Simuliert eine bereits rotierte Logdatei (`genesis.log.1`) neben der
    aktuellen (`genesis.log`) - beide muessen gelesen werden, in
    chronologisch korrekter Reihenfolge (rotierte Datei ist AELTER)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "genesis.log.1").write_text(
        "2026-01-01 00:00:00 | INFO     | genesis.Old            | Alte Meldung\n",
        encoding="utf-8",
    )
    (tmp_path / "genesis.log").write_text(
        "2026-01-02 00:00:00 | INFO     | genesis.New            | Neue Meldung\n",
        encoding="utf-8",
    )
    total, entries = read_log_entries(tmp_path, limit=10)
    assert total == 2
    # Neueste zuerst.
    assert entries[0].message == "Neue Meldung"
    assert entries[1].message == "Alte Meldung"
