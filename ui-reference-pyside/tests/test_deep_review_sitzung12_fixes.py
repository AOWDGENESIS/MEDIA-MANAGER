"""Regressionstests für die Funde/Abschlussarbeiten aus Deep-Review-Sitzung
12 (siehe `docs/REVIEW_LOG.md` Abschnitt 8 und `PROGRESS.md`
"Deep-Review-Sitzung 12"): vollständige Migration der verbleibenden
`QMessageBox.critical(...)`-Aufrufstellen für `GenesisAPIError` auf
`show_api_error()`, bei gleichzeitigem Erhalt der bisherigen,
handlungsspezifischen Fehlermeldung über den neuen `message`-Parameter.
Läuft unter QT_QPA_PLATFORM=offscreen.
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
from genesis_ui.dialogs.artwork_dialog import ArtworkDialog


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_show_api_error_message_param_overrides_default_text_but_keeps_error_id(
    monkeypatch,
) -> None:
    """`message=` ersetzt nur den Haupttext (die bisherige, handlungs-
    spezifische Meldung bleibt also sichtbar) - Fehler-ID/Loesungshinweis
    werden trotzdem IMMER angehaengt, damit der Nutzer den Vorfall im
    Fehler-Center wiederfinden kann."""
    captured = {}

    def _fake_exec(self):
        captured["text_format"] = self.textFormat()
        captured["text"] = self.text()
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "exec", _fake_exec)
    exc = GenesisAPIError(
        "roher Core-Fehlertext", error_id="ERR-TEST-0002", solution_hint="Server neu starten",
    )
    error_dialog.show_api_error(
        None, exc, message="Einbetten fehlgeschlagen: roher Core-Fehlertext",
    )
    assert captured["text_format"] == Qt.PlainText
    assert captured["text"].startswith("Einbetten fehlgeschlagen: roher Core-Fehlertext")
    assert "ERR-TEST-0002" in captured["text"]
    assert "Server neu starten" in captured["text"]


def test_show_api_error_without_message_falls_back_to_str_exc(monkeypatch) -> None:
    captured = {}

    def _fake_exec(self):
        captured["text"] = self.text()
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "exec", _fake_exec)
    exc = GenesisAPIError("roher Core-Fehlertext")
    error_dialog.show_api_error(None, exc)
    assert captured["text"] == "roher Core-Fehlertext"


class _FakeArtworkAPI:
    """Liefert initial kein eingebettetes Cover und laesst `embed_artwork()`
    mit einem `GenesisAPIError` fehlschlagen - genau der Pfad, der vor der
    Sitzung-12-Migration nur eine einfache `QMessageBox.critical(...)` ohne
    Fehler-ID/Loesungshinweis gezeigt haette."""

    def get_artwork_bytes(self, media_id: int):
        return None

    def embed_artwork(self, media_id: int, artwork_id: int, confirm: bool = False):
        raise GenesisAPIError(
            "Artwork nicht gefunden", error_id="ERR-ARTWORK-0001",
            solution_hint="Online-Suche erneut ausfuehren",
        )


def test_artwork_dialog_embed_failure_uses_show_api_error_with_context(monkeypatch) -> None:
    captured = {}

    def _fake_exec(self):
        captured["text"] = self.text()
        captured["text_format"] = self.textFormat()
        return QMessageBox.Ok

    # Bestaetigungsdialog vor dem Einbetten automatisch mit "Ja" beantworten.
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
    )
    monkeypatch.setattr(QMessageBox, "exec", _fake_exec)

    dialog = ArtworkDialog(_FakeArtworkAPI(), media_id=1, filename="cover-test.mp3")
    dialog._pending_artwork_id = 42
    dialog._on_embed_clicked()

    # Die bisherige, handlungsspezifische Meldung bleibt erhalten ...
    assert "Artwork nicht gefunden" in captured["text"]
    # ... UND die Fehler-ID/der Loesungshinweis werden jetzt zusaetzlich
    # angezeigt (das ist der eigentliche Zweck der Migration).
    assert "ERR-ARTWORK-0001" in captured["text"]
    assert "Online-Suche erneut ausfuehren" in captured["text"]
    assert captured["text_format"] == Qt.PlainText
    # Fehlgeschlagenes Einbetten darf den "changed"-Status nicht faelschlich
    # auf True setzen (kein stiller Teilerfolg).
    assert dialog.changed is False
