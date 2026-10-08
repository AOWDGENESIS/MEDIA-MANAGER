#!/usr/bin/env python3
"""Startet die GENESIS PySide6-Referenz-UI.

Voraussetzung: der Core Service laeuft (core/run_api.py), Standard-Port 8420.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from genesis_ui.dialogs.error_dialog import install_global_excepthook
from genesis_ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GENESIS Media Manager")
    window = MainWindow()
    # §37 gilt auch fuer die UI selbst: ein unerwarteter Programmierfehler
    # soll nie zu einem kommentarlosen Absturz/Einfrieren fuehren, sondern
    # zu einem verstaendlichen Dialog mit Details fuer den Fehlerbericht.
    install_global_excepthook(window)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
