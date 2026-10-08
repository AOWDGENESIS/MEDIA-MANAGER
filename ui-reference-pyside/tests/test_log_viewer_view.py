"""Tests für `LogViewerView` (§54, Gap-Analyse Gap J).

`nav.logs` war bisher eine reine Platzhalterseite - diese Ansicht zeigt die
über `GET /logs` gelieferten strukturierten Logeinträge an (Filter nach
Mindest-Level/Komponente/Freitext, Seitenweise Blättern, Detailansicht der
vollständigen Meldung inkl. mehrzeiliger Tracebacks).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.api_client import GenesisAPIError  # noqa: E402
from genesis_ui.views.log_viewer_view import PAGE_SIZE, LogViewerView  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeAPI:
    def __init__(self, total: int = 5):
        self.calls: list[dict] = []
        self.entries = [
            {
                "timestamp": f"2026-01-01 00:00:{i:02d}",
                "level": "INFO" if i % 2 == 0 else "WARNING",
                "component": "genesis.MediaScanner",
                "message": f"Zeile {i}\nFortsetzung {i}",
            }
            for i in range(total)
        ]

    def get_logs(self, level=None, component=None, search=None, limit=200, offset=0):
        self.calls.append(
            {"level": level, "component": component, "search": search,
             "limit": limit, "offset": offset}
        )
        items = self.entries
        if level:
            items = [e for e in items if e["level"] == level]
        if component:
            items = [e for e in items if component.lower() in e["component"].lower()]
        if search:
            items = [e for e in items if search.lower() in e["message"].lower()]
        return {"total": len(items), "items": items[offset : offset + limit]}


class _FailingAPI:
    def get_logs(self, **kwargs):
        raise GenesisAPIError("Core nicht erreichbar")


def test_loads_entries_on_construction():
    api = _FakeAPI(total=5)
    view = LogViewerView(api)
    assert view.tree.topLevelItemCount() == 5
    assert "5" in view.status_label.text()


def test_level_filter_reduces_results_and_resets_offset():
    api = _FakeAPI(total=5)
    view = LogViewerView(api)
    view._offset = PAGE_SIZE  # simuliert, dass man schon auf Seite 2 war
    index = view.level_combo.findData("WARNING")
    view.level_combo.setCurrentIndex(index)
    assert view._offset == 0
    assert view.tree.topLevelItemCount() == 2
    assert all(
        view.tree.topLevelItem(i).text(1) == "WARNING"
        for i in range(view.tree.topLevelItemCount())
    )


def test_component_and_search_filters_are_passed_through():
    api = _FakeAPI(total=5)
    view = LogViewerView(api)
    view.component_edit.setText("MediaScanner")
    view.search_edit.setText("Zeile 3")
    view._reload()
    last_call = api.calls[-1]
    assert last_call["component"] == "MediaScanner"
    assert last_call["search"] == "Zeile 3"
    assert view.tree.topLevelItemCount() == 1


def test_selecting_a_row_shows_full_multiline_message_in_detail_panel():
    api = _FakeAPI(total=3)
    view = LogViewerView(api)
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    view._on_selection_changed()
    assert "Fortsetzung" in view.detail_label.text()


def test_message_column_only_shows_first_line():
    api = _FakeAPI(total=1)
    view = LogViewerView(api)
    message_cell = view.tree.topLevelItem(0).text(3)
    assert "\n" not in message_cell
    assert message_cell == "Zeile 0"


def test_pagination_buttons_enabled_state():
    api = _FakeAPI(total=PAGE_SIZE + 10)
    view = LogViewerView(api)
    assert not view.prev_btn.isEnabled()
    assert view.next_btn.isEnabled()

    view._on_next_page()
    assert view.prev_btn.isEnabled()
    assert not view.next_btn.isEnabled()

    view._on_previous_page()
    assert not view.prev_btn.isEnabled()
    assert view.next_btn.isEnabled()


def test_next_page_is_a_no_op_at_the_end():
    api = _FakeAPI(total=5)
    view = LogViewerView(api)
    calls_before = len(api.calls)
    view._on_next_page()
    assert len(api.calls) == calls_before  # kein zusaetzlicher API-Aufruf


def test_api_error_is_shown_not_silent():
    view = LogViewerView(_FailingAPI())
    assert "Core nicht erreichbar" in view.status_label.text()
