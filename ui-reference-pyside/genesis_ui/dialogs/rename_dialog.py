"""Dialog fuer konfigurierbare Umbenennungs-Vorlagen mit Pflicht-Vorschau vor
Massenaenderungen (Prinzip #16, §15/§44)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

DEFAULT_TEMPLATE = "{track:02d} - {artist} - {title}.{ext}"


class RenamePreviewDialog(QDialog):
    """Erzwingt den Ablauf Vorlage -> Vorschau -> explizite Bestaetigung ->
    Anwenden. Es gibt keinen Weg, direkt umzubenennen, ohne vorher die
    Vorschau fuer die exakt gleiche Auswahl gesehen zu haben."""

    def __init__(self, api: GenesisAPIClient, media_file_ids: list[int],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_file_ids = media_file_ids
        self._preview_items: list[dict] = []

        self.setWindowTitle(tr("rename_dialog.window_title"))
        self.resize(820, 420)

        root = QVBoxLayout(self)

        info = QLabel(tr("rename_dialog.info", count=len(media_file_ids)))
        info.setWordWrap(True)
        root.addWidget(info)

        template_row = QHBoxLayout()
        template_row.addWidget(QLabel(tr("rename_dialog.template_label")))
        self.template_edit = QLineEdit(DEFAULT_TEMPLATE)
        template_row.addWidget(self.template_edit, stretch=1)
        preview_btn = QPushButton(tr("rename_dialog.preview_button"))
        preview_btn.clicked.connect(self._on_preview_clicked)
        template_row.addWidget(preview_btn)
        root.addLayout(template_row)

        self.status_label = QLabel(tr("rename_dialog.no_preview_yet"))
        root.addWidget(self.status_label)

        columns = [
            tr("rename_dialog.column_old_name"), tr("rename_dialog.column_new_name"),
            tr("rename_dialog.column_status"),
        ]
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton(tr("rename_dialog.apply_button"))
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.apply_btn.setEnabled(False)
        close_btn = QPushButton(tr("rename_dialog.cancel_button"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._on_preview_clicked()

    def _on_preview_clicked(self) -> None:
        template = self.template_edit.text().strip()
        if not template:
            self.status_label.setText(tr("rename_dialog.template_empty"))
            self.apply_btn.setEnabled(False)
            return
        try:
            self._preview_items = self.api.rename_preview(self.media_file_ids, template)
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("rename_dialog.template_invalid", error=exc))
            self.apply_btn.setEnabled(False)
            self.table.setRowCount(0)
            return

        actionable = sum(1 for i in self._preview_items if i["is_actionable"])
        self.status_label.setText(
            tr("rename_dialog.summary", count=len(self._preview_items), actionable=actionable)
        )
        self.table.setRowCount(len(self._preview_items))
        for row, item in enumerate(self._preview_items):
            old_name = item["old_absolute_path"].rsplit("/", 1)[-1]
            new_name = item["new_absolute_path"].rsplit("/", 1)[-1]
            if item["template_error"]:
                status = tr("rename_dialog.status_error", error=item["template_error"])
            elif item["has_conflict"]:
                status = tr("rename_dialog.status_conflict", reason=item["conflict_reason"])
            elif item["is_identical"]:
                status = tr("rename_dialog.status_identical")
            elif item["empty_fields"]:
                # Deep-Review-Fund (Sitzung 3, F-10): Die API berechnet
                # bewusst, welche Platzhalter fuer diese Datei leer sind
                # (Prinzip #16 - keine Fantasiedaten, aber der Nutzer soll
                # gewarnt werden), das wurde hier bisher verschluckt und nie
                # angezeigt. Jetzt sichtbar statt stillschweigend "bereit".
                status = tr(
                    "rename_dialog.status_ready_with_warning",
                    fields=", ".join(item["empty_fields"]),
                )
            else:
                status = tr("rename_dialog.status_ready")
            self.table.setItem(row, 0, QTableWidgetItem(old_name))
            self.table.setItem(row, 1, QTableWidgetItem(new_name))
            self.table.setItem(row, 2, QTableWidgetItem(status))

        self.apply_btn.setEnabled(actionable > 0)

    def _on_apply_clicked(self) -> None:
        template = self.template_edit.text().strip()
        actionable = sum(1 for i in self._preview_items if i["is_actionable"])
        confirm = QMessageBox.question(
            self,
            tr("rename_dialog.confirm_title"),
            tr("rename_dialog.confirm_text", count=actionable),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            result = self.api.rename_apply(self.media_file_ids, template, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("rename_dialog.apply_failed", error=exc))
            return

        applied = sum(1 for r in result["results"] if r["applied"])
        QMessageBox.information(
            self, tr("rename_dialog.done_title"),
            tr("rename_dialog.done_text", applied=applied, total=len(result["results"])),
        )
        self.accept()
