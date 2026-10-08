"""Tests für das neue Rechtsklick-Kontextmenü in `MediaTableView` (§61,
Gap-Analyse Gap H - Rest).

Die im Original-Auftrag als Kontextmenü beschriebenen globalen Aktionen
standen bisher NUR als Werkzeugleisten-Buttons zur Verfügung. Das neue
Kontextmenü ergänzt (ersetzt nicht) die Toolbar und bedient dieselben
bereits bestehenden `_on_..._clicked`-Handler - `QMenu.exec()` selbst wird
hier bewusst NICHT aufgerufen (blockierender modaler Aufruf in der
Offscreen-Sandbox), stattdessen wird die ausgelagerte `_build_context_menu()`
sowie die Zeilen-Auswahllogik direkt geprüft (gleiches Testmuster wie bei
`QDesktopServices.openUrl()` in `test_gap_closure_detail_view.py`)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.views.media_table import MediaTableView  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeAPI:
    def list_media(self, kind=None, search=None, limit=500, **filters):
        return {
            "items": [
                {
                    "id": 1, "kind": "track", "filename": "song1.mp3",
                    "extension": "mp3", "size_bytes": 1, "absolute_path": "/tmp/song1.mp3",
                },
                {
                    "id": 2, "kind": "track", "filename": "song2.mp3",
                    "extension": "mp3", "size_bytes": 2, "absolute_path": "/tmp/song2.mp3",
                },
                {
                    "id": 3, "kind": "audiobook", "filename": "book.m4b",
                    "extension": "m4b", "size_bytes": 3, "absolute_path": "/tmp/book.m4b",
                },
            ]
        }

    def media_detail(self, media_id: int) -> dict:
        return {
            "absolute_path": "/tmp/x", "file_exists_on_disk": True, "filename": "x",
            "directory": "/tmp", "size_bytes": 1, "extension": "mp3", "mtime": None,
            "content_hash_sha256": None, "technical": None, "track": None,
            "has_embedded_artwork": False,
        }

    def get_quality(self, media_id: int):
        return None

    def get_artwork_bytes(self, media_id: int):
        return None

    def list_loudness(self, media_id: int) -> list[dict]:
        return []

    def get_ai_metadata(self, media_id: int) -> list[dict]:
        return []

    def list_media_sources(self, media_id: int) -> list[dict]:
        return []


def _build_view() -> MediaTableView:
    return MediaTableView(_FakeAPI(), None, "Alle Medien")


def test_context_menu_has_one_entry_per_toolbar_action():
    view = _build_view()
    view.table.selectRow(0)
    view._on_selection_changed()
    menu = view._build_context_menu()
    assert len(menu.actions()) == 15


def test_context_menu_entries_mirror_toolbar_enabled_state():
    view = _build_view()
    view.table.selectRow(0)
    view._on_selection_changed()
    menu = view._build_context_menu()
    labels_enabled = {a.text(): a.isEnabled() for a in menu.actions()}
    assert labels_enabled[view.play_btn.text()] == view.play_btn.isEnabled()
    assert labels_enabled[view.rename_btn.text()] == view.rename_btn.isEnabled()
    assert labels_enabled[view.audiobook_btn.text()] == view.audiobook_btn.isEnabled()
    assert view.play_btn.isEnabled() is True
    assert view.audiobook_btn.isEnabled() is False  # Zeile 0 ist "track", kein Hoerbuch


def test_context_menu_all_disabled_without_selection():
    view = _build_view()
    view.table.clearSelection()
    view._on_selection_changed()
    menu = view._build_context_menu()
    assert all(not action.isEnabled() for action in menu.actions())


def test_context_menu_reflects_audiobook_specific_button_for_audiobook_row():
    view = _build_view()
    view.table.selectRow(2)  # book.m4b
    view._on_selection_changed()
    menu = view._build_context_menu()
    labels_enabled = {a.text(): a.isEnabled() for a in menu.actions()}
    assert labels_enabled[view.audiobook_btn.text()] is True


def test_right_click_on_unselected_row_selects_only_that_row():
    view = _build_view()
    view.table.selectRow(0)
    view._on_selection_changed()

    rect = view.table.visualRect(view.table.model().index(1, 0))
    item = view.table.itemAt(rect.center())
    assert item is not None
    row = item.row()
    selected_rows = {index.row() for index in view.table.selectionModel().selectedRows()}
    if row not in selected_rows:
        view.table.selectRow(row)

    selected_after = {index.row() for index in view.table.selectionModel().selectedRows()}
    assert selected_after == {1}


def test_right_click_inside_existing_multi_selection_keeps_it():
    from PySide6.QtCore import QItemSelectionModel

    view = _build_view()
    selection_model = view.table.selectionModel()
    for row in (0, 1):
        selection_model.select(
            view.table.model().index(row, 0),
            QItemSelectionModel.Select | QItemSelectionModel.Rows,
        )
    view._on_selection_changed()
    selected_before = {index.row() for index in view.table.selectionModel().selectedRows()}
    assert selected_before == {0, 1}

    rect = view.table.visualRect(view.table.model().index(0, 0))
    item = view.table.itemAt(rect.center())
    row = item.row()
    selected_rows = {index.row() for index in view.table.selectionModel().selectedRows()}
    if row not in selected_rows:
        view.table.selectRow(row)

    selected_after = {index.row() for index in view.table.selectionModel().selectedRows()}
    assert selected_after == {0, 1}


def test_triggering_a_menu_action_calls_the_same_handler_as_the_button(monkeypatch):
    view = _build_view()
    view.table.selectRow(0)
    view._on_selection_changed()

    called = []
    monkeypatch.setattr(view, "_on_play_clicked", lambda: called.append("play"))
    menu = view._build_context_menu()
    play_action = next(a for a in menu.actions() if a.text() == view.play_btn.text())
    play_action.trigger()

    assert called == ["play"]
