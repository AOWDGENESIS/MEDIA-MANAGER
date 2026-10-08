"""Regressionstests für die Einbindung von `SearchFiltersDialog` in
`MediaTableView` (§9, Gap-Analyse Gap C).

Prüft, dass bestätigte erweiterte Filter tatsächlich an `api.list_media()`
durchgereicht werden und die Statusanzeige ("Filter aktiv (n)") korrekt
mitgeführt wird. `SearchFiltersDialog.exec()` wird per monkeypatch
ersetzt, um keinen echten modalen Dialog in der Offscreen-Sandbox öffnen
zu müssen (gleiches Prinzip wie bei allen anderen bereits bestehenden
Dialog-Integrationstests in diesem Verzeichnis)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.views import media_table as media_table_module  # noqa: E402
from genesis_ui.views.media_table import MediaTableView  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeAPI:
    def __init__(self) -> None:
        self.list_media_calls: list[dict] = []

    def list_media(self, kind=None, search=None, limit=500, **filters):
        self.list_media_calls.append({"kind": kind, "search": search, **filters})
        return {"items": []}

    def media_detail(self, media_id: int) -> dict:
        raise AssertionError("not expected in this test")


def _build_view(api) -> MediaTableView:
    return MediaTableView(api, None, "Alle Medien")


def test_initial_refresh_sends_no_extra_filters():
    api = _FakeAPI()
    _build_view(api)
    assert api.list_media_calls[-1] == {"kind": None, "search": None}


def test_confirmed_filters_are_merged_into_next_refresh(monkeypatch):
    api = _FakeAPI()
    view = _build_view(api)

    fake_filters = {"genre": "Elektro", "year": 2020}

    class _FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_filters(self):
            return fake_filters

    monkeypatch.setattr(media_table_module, "SearchFiltersDialog", _FakeDialog)

    view._on_filters_clicked()

    last_call = api.list_media_calls[-1]
    assert last_call["genre"] == "Elektro"
    assert last_call["year"] == 2020


def test_filters_active_label_reflects_count(monkeypatch):
    api = _FakeAPI()
    view = _build_view(api)
    assert view.filters_active_label.text() == ""

    class _FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_filters(self):
            return {"genre": "Elektro", "has_quality_issues": True, "year": None}

    monkeypatch.setattr(media_table_module, "SearchFiltersDialog", _FakeDialog)
    view._on_filters_clicked()

    assert "2" in view.filters_active_label.text()


def test_cancelled_dialog_does_not_change_active_filters(monkeypatch):
    api = _FakeAPI()
    view = _build_view(api)
    view._active_filters = {"genre": "Rock"}

    class _FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 0  # Rejected/abgebrochen

        def get_filters(self):
            raise AssertionError("darf bei Abbruch nicht aufgerufen werden")

    monkeypatch.setattr(media_table_module, "SearchFiltersDialog", _FakeDialog)
    view._on_filters_clicked()

    assert view._active_filters == {"genre": "Rock"}
