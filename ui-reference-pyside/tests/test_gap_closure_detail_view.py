"""Regressionstests für die Gap-Analyse-Gruppe 1 (siehe
`docs/GAP_ANALYSIS.md` Gaps D/E/F und `PROGRESS.md`): Cover-Anzeige im
Detailbereich, "Datei öffnen"/"Ordner öffnen"/"Pfad kopieren" sowie
Loudness- und KI-Analyse-Abschnitte in der vereinheitlichten
`MediaTableView`-Detailansicht (§8/§22/§59/§61).

Läuft unter QT_QPA_PLATFORM=offscreen mit Fake-API-Clients statt eines
echten Core Service (siehe test_phase9_hardening_views.py für das
etablierte Testmuster). `QDesktopServices.openUrl()` wird NIEMALS wirklich
aufgerufen (kann in einer Headless-Sandbox ohne Desktop-Umgebung hängen
bleiben) - stattdessen wird `open_path_in_os`/`copy_path_to_clipboard`
per `monkeypatch` ersetzt und nur die Aufrufparameter geprüft.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from genesis_ui.api_client import GenesisAPIError
from genesis_ui.views import media_table as media_table_module
from genesis_ui.views.media_table import MediaTableView, pixmap_from_artwork_bytes


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeAPI:
    """Liefert eine einzelne Testdatei samt Loudness-/KI-/Quellen-Daten.
    Jede Methode ist individuell durch Monkeypatching auf der Instanz
    überschreibbar, um Fehler-/Leerfälle zu simulieren."""

    def __init__(self) -> None:
        self.embed_calls: list[int] = []

    def list_media(self, kind=None, search=None, limit=500):
        return {
            "items": [
                {
                    "id": 1,
                    "kind": "track",
                    "filename": "song.mp3",
                    "extension": "mp3",
                    "size_bytes": 12345,
                    "absolute_path": "/tmp/song.mp3",
                }
            ]
        }

    def media_detail(self, media_id: int) -> dict:
        return {
            "absolute_path": "/tmp/song.mp3",
            "file_exists_on_disk": True,
            "filename": "song.mp3",
            "directory": "/tmp",
            "size_bytes": 12345,
            "extension": "mp3",
            "mtime": "2026-01-01T00:00:00",
            "content_hash_sha256": "abc123",
            "technical": {"duration_s": 180},
            "track": None,
            "has_embedded_artwork": False,
        }

    def get_quality(self, media_id: int):
        return None

    def get_artwork_bytes(self, media_id: int):
        return None

    def list_loudness(self, media_id: int) -> list[dict]:
        return [
            {
                "integrated_lufs": -14.2,
                "true_peak_dbtp": -1.0,
                "loudness_range_lu": 5.0,
                "normalized": True,
            }
        ]

    def get_ai_metadata(self, media_id: int) -> list[dict]:
        return [
            {
                "field_name": "genre",
                "field_value": "Pop",
                "model_name": "gpt-x",
                "confidence": 0.9,
                "accepted_by_user": True,
            }
        ]

    def list_media_sources(self, media_id: int) -> list[dict]:
        return [
            {
                "source_name": "YouTube Rip",
                "provider_name": "youtube",
                "imported_at": "2026-01-01T00:00:00",
            }
        ]


def _build_view(api) -> MediaTableView:
    view = MediaTableView(api, None, "Alle Medien")
    view.refresh()
    view.table.selectRow(0)
    view._on_selection_changed()
    return view


# --- Gap D: Cover-Anzeige ----------------------------------------------------

def test_pixmap_from_artwork_bytes_decodes_valid_image() -> None:
    source = QPixmap(500, 500)
    source.fill(QColor("red"))
    buf = bytes()
    from PySide6.QtCore import QBuffer, QIODevice

    qbuf = QBuffer()
    qbuf.open(QIODevice.WriteOnly)
    source.save(qbuf, "PNG")
    data = bytes(qbuf.data())

    result = pixmap_from_artwork_bytes(data)
    assert result is not None
    assert not result.isNull()
    # Auf die Vorschaugroesse herunterskaliert, nicht in Originalgroesse.
    assert max(result.width(), result.height()) <= 220


def test_pixmap_from_artwork_bytes_returns_none_for_garbage() -> None:
    assert pixmap_from_artwork_bytes(b"this is not an image") is None


def test_detail_panel_shows_no_cover_placeholder_when_api_returns_none() -> None:
    view = _build_view(_FakeAPI())
    assert view.cover_label.pixmap().isNull()
    assert view.cover_label.text() == "Kein Cover vorhanden"


def test_detail_panel_renders_cover_pixmap_when_artwork_available() -> None:
    api = _FakeAPI()
    source = QPixmap(100, 100)
    source.fill(QColor("blue"))
    from PySide6.QtCore import QBuffer, QIODevice

    qbuf = QBuffer()
    qbuf.open(QIODevice.WriteOnly)
    source.save(qbuf, "PNG")
    data = bytes(qbuf.data())
    api.get_artwork_bytes = lambda media_id: (data, "image/png")

    view = _build_view(api)
    assert not view.cover_label.pixmap().isNull()
    assert view.cover_label.text() == ""


def test_detail_panel_falls_back_to_placeholder_on_corrupt_artwork_bytes() -> None:
    api = _FakeAPI()
    api.get_artwork_bytes = lambda media_id: (b"corrupt-bytes", "image/jpeg")
    view = _build_view(api)
    assert view.cover_label.pixmap().isNull()
    assert view.cover_label.text() == "Kein Cover vorhanden"


# --- Gap E: Datei/Ordner oeffnen + Pfad kopieren -----------------------------

def test_open_file_folder_copy_buttons_enabled_only_for_single_selection() -> None:
    view = _build_view(_FakeAPI())
    assert view.open_file_btn.isEnabled()
    assert view.open_folder_btn.isEnabled()
    assert view.copy_path_btn.isEnabled()

    view.table.clearSelection()
    view._on_selection_changed()
    assert not view.open_file_btn.isEnabled()
    assert not view.open_folder_btn.isEnabled()
    assert not view.copy_path_btn.isEnabled()


def test_open_file_button_calls_open_path_in_os_with_file_target(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        media_table_module, "open_path_in_os",
        lambda path, reveal_containing_folder: calls.append((path, reveal_containing_folder)) or True,
    )
    view = _build_view(_FakeAPI())
    view._on_open_file_clicked()
    assert calls == [("/tmp/song.mp3", False)]


def test_open_folder_button_calls_open_path_in_os_with_folder_flag(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        media_table_module, "open_path_in_os",
        lambda path, reveal_containing_folder: calls.append((path, reveal_containing_folder)) or True,
    )
    view = _build_view(_FakeAPI())
    view._on_open_folder_clicked()
    assert calls == [("/tmp/song.mp3", True)]


def test_open_file_shows_warning_when_open_path_in_os_fails(monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(media_table_module, "open_path_in_os", lambda *a, **k: False)
    warned = {}

    def _fake_warning(parent, title, text):
        warned["title"] = title
        warned["text"] = text
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(_fake_warning))
    view = _build_view(_FakeAPI())
    view._on_open_file_clicked()
    assert "/tmp/song.mp3" in warned["text"]


def test_copy_path_button_copies_absolute_path(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        media_table_module, "copy_path_to_clipboard", lambda path: calls.append(path)
    )
    view = _build_view(_FakeAPI())
    view._on_copy_path_clicked()
    assert calls == ["/tmp/song.mp3"]


# --- Gap F: Loudness + KI-Analyse + Quelle in der Detailansicht -------------

def test_detail_panel_includes_loudness_section_with_latest_measurement() -> None:
    view = _build_view(_FakeAPI())
    text = view.detail_panel.toPlainText()
    assert "LOUDNESS" in text
    assert "-14.2" in text
    assert "-1.0" in text


def test_detail_panel_shows_loudness_none_when_never_analyzed() -> None:
    api = _FakeAPI()
    api.list_loudness = lambda media_id: []
    view = _build_view(api)
    text = view.detail_panel.toPlainText()
    assert "noch nicht analysiert" in text


def test_detail_panel_tolerates_loudness_api_error() -> None:
    api = _FakeAPI()

    def _raise(media_id):
        raise GenesisAPIError("boom")

    api.list_loudness = _raise
    view = _build_view(api)
    text = view.detail_panel.toPlainText()
    assert "noch nicht analysiert" in text


def test_detail_panel_includes_ai_analysis_section_with_model_and_confidence() -> None:
    view = _build_view(_FakeAPI())
    text = view.detail_panel.toPlainText()
    assert "KI-ANALYSE" in text
    assert "genre: Pop" in text
    assert "gpt-x" in text
    assert "0.9" in text


def test_detail_panel_shows_ai_none_when_no_suggestions() -> None:
    api = _FakeAPI()
    api.get_ai_metadata = lambda media_id: []
    view = _build_view(api)
    text = view.detail_panel.toPlainText()
    assert "keine KI-Vorschläge vorhanden" in text


def test_detail_panel_includes_source_section() -> None:
    view = _build_view(_FakeAPI())
    text = view.detail_panel.toPlainText()
    assert "QUELLE" in text
    assert "YouTube Rip" in text
    assert "youtube" in text


def test_detail_panel_shows_source_none_when_no_import_record() -> None:
    api = _FakeAPI()
    api.list_media_sources = lambda media_id: []
    view = _build_view(api)
    text = view.detail_panel.toPlainText()
    assert "kein Importnachweis" in text
