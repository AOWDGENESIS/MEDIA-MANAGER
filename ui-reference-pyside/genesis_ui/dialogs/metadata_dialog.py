"""Dialog fuer Metadaten-Vorschlaege (Erkennen -> Vorschlag -> Confidence ->
Benutzerfreigabe -> Aenderung, Prinzip #4/#17, §10/§11)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


def _columns() -> list[str]:
    return [
        tr("metadata_dialog.column_provider"), tr("metadata_dialog.column_confidence"),
        tr("metadata_dialog.column_title"), tr("metadata_dialog.column_artist"),
        tr("metadata_dialog.column_album"), tr("metadata_dialog.column_year"),
        tr("metadata_dialog.column_track"),
    ]


class MetadataSuggestionsDialog(QDialog):
    """Zeigt Vorschlaege rein lesend an; eine Uebernahme erfordert eine
    zusaetzliche, explizite Bestaetigung durch den Nutzer (Prinzip #17)."""

    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self._suggestions: list[dict] = []
        self.applied = False

        self.setWindowTitle(tr("metadata_dialog.window_title", filename=filename))
        self.resize(760, 360)

        root = QVBoxLayout(self)
        info = QLabel(tr("metadata_dialog.info"))
        info.setWordWrap(True)
        root.addWidget(info)

        self.status_label = QLabel(tr("metadata_dialog.loading"))
        root.addWidget(self.status_label)

        columns = _columns()
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton(tr("metadata_dialog.apply_button"))
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.apply_btn.setEnabled(False)
        close_btn = QPushButton(tr("metadata_dialog.close_button"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self.table.itemSelectionChanged.connect(
            lambda: self.apply_btn.setEnabled(bool(self.table.selectionModel().selectedRows()))
        )

        self._load()

    def _load(self) -> None:
        try:
            self._suggestions = self.api.get_metadata_suggestions(self.media_id)
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("metadata_dialog.load_failed", error=exc))
            return

        if not self._suggestions:
            self.status_label.setText(tr("metadata_dialog.none_found"))
            return

        self.status_label.setText(
            tr("metadata_dialog.found_count", count=len(self._suggestions))
        )
        self.table.setRowCount(len(self._suggestions))
        for row, s in enumerate(self._suggestions):
            m = s["match"]
            values = [
                m.get("provider", ""),
                f"{m.get('confidence', 0.0):.0%}",
                m.get("title") or "",
                m.get("artist") or "",
                m.get("album") or "",
                str(m.get("year") or ""),
                str(m.get("track_number") or ""),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _on_apply_clicked(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        suggestion = self._suggestions[rows[0].row()]
        match = suggestion["match"]

        confirm = QMessageBox.question(
            self,
            tr("metadata_dialog.confirm_title"),
            tr(
                "metadata_dialog.confirm_text",
                title=match.get("title"), artist=match.get("artist"),
                album=match.get("album"), confidence=f"{match.get('confidence', 0.0):.0%}",
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.api.apply_metadata_suggestion(self.media_id, match, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("metadata_dialog.apply_failed", error=exc))
            return

        self.applied = True
        QMessageBox.information(
            self, tr("metadata_dialog.applied_title"), tr("metadata_dialog.applied_text")
        )
        self.accept()
