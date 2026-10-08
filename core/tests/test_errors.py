"""Tests fuer das zentrale Error-Center (§37, ADR-0020)."""
from __future__ import annotations

from genesis_core.db import Database
from genesis_core.errors import GenesisError, list_errors, log_error, log_exception, mark_resolved


def test_log_error_assigns_sequential_ids_per_day(db: Database) -> None:
    first = log_error(db, "TestComponent", "Erster Fehler", action="scan")
    second = log_error(db, "TestComponent", "Zweiter Fehler", action="scan")
    assert first.error_id != second.error_id
    assert first.error_id.startswith("ERR-")
    first_seq = int(first.error_id.rsplit("-", 1)[-1])
    second_seq = int(second.error_id.rsplit("-", 1)[-1])
    assert second_seq == first_seq + 1


def test_log_exception_captures_traceback(db: Database) -> None:
    try:
        raise ValueError("etwas ist kaputt")
    except ValueError as exc:
        record = log_exception(db, "TestComponent", exc, action="test")
    assert "ValueError" in record.technical_details
    assert "etwas ist kaputt" in record.technical_details


def test_list_errors_returns_newest_first(db: Database) -> None:
    log_error(db, "A", "Fehler 1")
    log_error(db, "B", "Fehler 2")
    rows = list_errors(db, limit=10)
    assert len(rows) >= 2
    assert rows[0].message == "Fehler 2"


def test_mark_resolved(db: Database) -> None:
    record = log_error(db, "A", "Fehler X")
    assert mark_resolved(db, record.error_id) is True
    rows = list_errors(db, unresolved_only=True)
    assert all(r.error_id != record.error_id for r in rows)


def test_mark_resolved_unknown_id_returns_false(db: Database) -> None:
    assert mark_resolved(db, "ERR-99999999-99999") is False


def test_genesis_error_carries_structured_fields() -> None:
    exc = GenesisError(
        "Anzeigetext", component="Scanner", action="scan", file_path="/x/y.mp3",
        technical_details="traceback...", solution_hint="Erneut versuchen",
    )
    assert exc.component == "Scanner"
    assert exc.file_path == "/x/y.mp3"
    assert str(exc) == "Anzeigetext"
