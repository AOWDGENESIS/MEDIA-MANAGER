"""Regressionstests für die konkreten Funde aus dem Deep-Review-Pass
Sitzung 11 (siehe `docs/REVIEW_LOG.md`): Qt-Mnemonic-Fehlinterpretation
von '&' in dynamischem Checkbox-Text (`AIDialog`) und Qt-Rich-Text-
Autoerkennung bei `QLabel`s, die externe/dynamische Inhalte anzeigen.
Laeuft unter QT_QPA_PLATFORM=offscreen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from genesis_ui.api_client import GenesisAPIError
from genesis_ui.dialogs import error_dialog
from genesis_ui.dialogs.ai_dialog import AIDialog
from genesis_ui.widgets import escape_mnemonic, set_plain_text


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_escape_mnemonic_doubles_ampersands() -> None:
    assert escape_mnemonic("Rock & Pop") == "Rock && Pop"
    assert escape_mnemonic("AC/DC") == "AC/DC"
    assert escape_mnemonic("") == ""


def test_set_plain_text_forces_plain_text_format() -> None:
    from PySide6.QtWidgets import QLabel

    label = QLabel()
    set_plain_text(label, "<b>sollte nicht fett sein</b>")
    assert label.textFormat() == Qt.PlainText
    assert label.text() == "<b>sollte nicht fett sein</b>"


class _FakeAIAPI:
    """Liefert einen KI-Metadatenvorschlag mit einem '&' im Wert - genau
    der Fall, der vor dem Fix eine Checkbox mit fehlinterpretiertem
    Mnemonic erzeugt hätte (z.B. echte Genre-Werte wie 'Rock & Pop')."""

    def get_ai_status(self) -> dict:
        return {"enabled": True, "available": True, "provider": "ollama", "model": "llama3"}

    def get_ai_metadata(self, media_id: int) -> list[dict]:
        return []

    def suggest_ai_metadata(self, media_id: int, fields=None) -> list[dict]:
        return [
            {
                "field_name": "genre", "field_value": "Rock & Pop",
                "model_name": "llama3", "model_version": None,
                "confidence": 0.8, "prompt": None,
            }
        ]


def test_show_api_error_forces_plain_text_on_message_box(monkeypatch) -> None:
    captured = {}

    def _fake_exec(self):
        captured["text_format"] = self.textFormat()
        captured["text"] = self.text()
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "exec", _fake_exec)
    exc = GenesisAPIError(
        "Core-Fehler mit <b>Markup</b>", error_id="ERR-TEST-0001", solution_hint="Erneut versuchen",
    )
    error_dialog.show_api_error(None, exc)
    assert captured["text_format"] == Qt.PlainText
    assert "<b>Markup</b>" in captured["text"]
    assert "ERR-TEST-0001" in captured["text"]


def test_ai_dialog_suggestion_checkbox_escapes_ampersand_in_ai_value() -> None:
    dialog = AIDialog(_FakeAIAPI(), media_id=1, filename="test.mp3", kind="movie")
    dialog._on_generate_clicked()

    assert len(dialog._suggestion_rows) == 1
    checkbox, _data = dialog._suggestion_rows[0]
    # Vor dem Fix stand hier ein einzelnes '&' - Qt haette "Pop" mit
    # unterstrichenem "P" als (ungewollte) Mnemonic-Taste gerendert.
    assert "&&" in checkbox.text()
    assert "Rock && Pop" in checkbox.text()
