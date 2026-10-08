"""Diagnose (nav.diagnostics, §38).

Rein lesender Gesundheitsbericht ueber DB, Dateisystem, konfigurierte
Provider (KI/TTS/Download) und das Plugin-System. Veraendert NIE etwas -
eine tatsaechliche Reparatur gefundener Probleme geschieht ausschliesslich
ueber den separaten "Scan & Repair"-Arbeitsablauf (§39, Plan -> Vorschau ->
Ausfuehren), nicht von hier aus.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text

STATUS_LABEL_KEYS = {
    "ok": "diagnostics_view.status_ok",
    "warning": "diagnostics_view.status_warning",
    "error": "diagnostics_view.status_error",
}


class DiagnosticsView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("diagnostics_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("diagnostics_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.run_btn = QPushButton(tr("diagnostics_view.run_button"))
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self._reload)
        controls.addWidget(self.run_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.overall_label = QLabel("")
        self.overall_label.setWordWrap(True)
        root.addWidget(self.overall_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("diagnostics_view.col_check"),
            tr("diagnostics_view.col_status"),
            tr("diagnostics_view.col_message"),
        ])
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        root.addWidget(self.tree, stretch=1)

        self._reload()

    def _reload(self) -> None:
        self.run_btn.setEnabled(False)
        self.status_label.setText(tr("diagnostics_view.running"))
        try:
            report = self.api.run_diagnostics()
        except GenesisAPIError as exc:
            self.run_btn.setEnabled(True)
            self.status_label.setText("")
            show_api_error(self, exc)
            return
        self.run_btn.setEnabled(True)
        self.status_label.setText("")

        overall_key = STATUS_LABEL_KEYS.get(report["overall_status"], report["overall_status"])
        set_plain_text(
            self.overall_label,
            tr("diagnostics_view.overall_status", status=tr(overall_key),
               generated_at=report["generated_at"]),
        )

        self.tree.clear()
        for check in report["checks"]:
            status_key = STATUS_LABEL_KEYS.get(check["status"], check["status"])
            item = QTreeWidgetItem([check["label"], tr(status_key), check["message"]])
            self.tree.addTopLevelItem(item)
