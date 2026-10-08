"""Zentraler Fehlerdialog der PySide6-Referenz-UI (§37).

Zwei Faelle werden hier bewusst getrennt behandelt:

1. `show_api_error()` - eine Core-API-Anfrage ist fehlgeschlagen
   (`GenesisAPIError`). Zeigt zusaetzlich zur Fehlermeldung die
   nachschlagbare Fehler-ID + einen Loesungshinweis an, falls der globale
   Exception-Handler der Core-API eine mitgeliefert hat (§37-Format) -
   genau die Angaben, die der Nutzer braucht, um den Vorfall im
   Fehler-Center (nav.error_center) wiederzufinden, ohne selbst
   Logdateien durchsuchen zu muessen.
2. `install_global_excepthook()` - faengt echte, unerwartete Python-/Qt-
   Exceptions INNERHALB der UI selbst ab (z.B. ein Programmierfehler beim
   Aufbau einer View), damit die Anwendung nie kommentarlos abstuerzt oder
   mit einer rohen Traceback-Konsole vor dem Nutzer steht ("kein stiller
   Fehlschlag" gilt fuer die UI genauso wie fuer die Core-API).

Migrationshinweis (Deep-Review Sitzung 12 - vorheriger Zustand siehe
Git-Historie dieser Datei): Saemtliche `QMessageBox.critical(...)`-
Aufrufstellen fuer `GenesisAPIError` im gesamten Projekt wurden auf
`show_api_error()` umgestellt, damit JEDE fehlgeschlagene Core-API-
Anfrage konsistent die Fehler-ID/den Loesungshinweis anzeigt. Der
optionale `message`-Parameter erlaubt es den aufrufenden Views dabei,
ihre bisherige, handlungsspezifische Fehlermeldung (z.B. "Kapitel
konnten nicht geladen werden: {error}") unveraendert als Haupttext
beizubehalten - `show_api_error()` ergaenzt nur noch die Fehler-ID/den
Loesungshinweis darunter, ohne den vorhandenen, spezifischeren Text zu
verdraengen oder zu duplizieren. Einzige bewusste Ausnahme:
`OSError`-Faelle (z.B. beim lokalen Schreiben einer Export-Datei) bleiben
unveraendert bei einfachem `QMessageBox.critical(...)`, da
`show_api_error()` explizit fuer `GenesisAPIError` typisiert ist
(kein `error_id`/`solution_hint` bei einem `OSError`).
"""
from __future__ import annotations

import sys
import traceback
from types import TracebackType

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from genesis_ui.api_client import GenesisAPIError
from genesis_ui.i18n import tr


def show_api_error(parent: QWidget | None, exc: GenesisAPIError,
                    *, title: str | None = None, message: str | None = None) -> None:
    """Zeigt eine fehlgeschlagene Core-API-Anfrage als Dialog. Haengt bei
    Vorhandensein eine nachschlagbare Fehler-ID + Loesungshinweis an -
    genau die beiden Felder, die der Nutzer braucht, um den Vorfall im
    Fehler-Center (nav.error_center) wiederzufinden, OHNE selbst Logdateien
    durchsuchen zu muessen.

    `message` erlaubt es Aufrufern, statt des rohen `str(exc)` eine eigene,
    handlungsspezifische Meldung voranzustellen (z.B. bereits per `tr(...)`
    uebersetzt und mit `error=exc` interpoliert) - Fehler-ID/Loesungshinweis
    werden in jedem Fall ergaenzt.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(title or tr("common.error_title"))
    text = message if message is not None else str(exc)
    if exc.error_id:
        text += "\n\n" + tr("error_dialog.error_id_line", error_id=exc.error_id)
    if exc.solution_hint:
        text += "\n" + tr("error_dialog.solution_hint_line", hint=exc.solution_hint)
    # QMessageBox.setText() interpretiert Inhalt genau wie QLabel per
    # Qt.AutoText - str(exc) kann eine vom Core Service gelieferte, nicht
    # vom Entwickler geschriebene Fehlermeldung enthalten (Deep-Review-Fund
    # Sitzung 11, siehe genesis_ui.widgets-Moduldocstring).
    box.setTextFormat(Qt.PlainText)
    box.setText(text)
    box.exec()



def install_global_excepthook(main_window: QWidget) -> None:
    """Ersetzt `sys.excepthook` fuer die Laufzeit des Prozesses. Faengt
    jede sonst unbehandelte Exception aus einem Qt-Slot/Event-Handler ab,
    protokolliert sie auf stderr (fuer die Entwicklung/Fehlersuche) UND
    zeigt dem Nutzer einen verstaendlichen Dialog mit ausklappbaren
    technischen Details, statt dass die Anwendung kommentarlos haengen
    bleibt oder abstuerzt. Rein defensiv - veraendert nie Daten."""

    def _hook(exc_type: type[BaseException], exc_value: BaseException,
              exc_tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(details)

        try:
            box = QMessageBox(main_window)
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle(tr("error_dialog.unexpected_title"))
            box.setText(tr("error_dialog.unexpected_text"))
            box.setDetailedText(details)
            box.exec()
        except Exception as dialog_exc:  # noqa: BLE001 - Dialog darf den Hook nie sprengen
            # Die urspruengliche Exception steht bereits oben auf stderr (kein
            # Datenverlust) - hier nur zusaetzlich vermerken, dass auch die
            # Dialoganzeige selbst fehlgeschlagen ist (kein stiller
            # Zweitfehler, Deep-Review Sitzung 13/S110).
            sys.stderr.write(
                f"[error_dialog] Fehlerdialog konnte nicht angezeigt werden: {dialog_exc}\n"
            )

    sys.excepthook = _hook


__all__ = ["install_global_excepthook", "show_api_error"]
