"""Backups (nav.backups, §40).

Betrifft AUSSCHLIESSLICH die SQLite-Datenbank und die Konfigurationsdatei -
NIEMALS Mediendateien selbst (riesige Medienbibliotheken werden bewusst
nicht automatisch "gesichert", siehe Originalauftrag §40/§6). Erstellen
ist unkritisch (zusaetzliche Kopie, keine Bestaetigung noetig);
Wiederherstellen ersetzt die AKTIVE Datenbank und ist daher eine echte,
bestaetigungspflichtige Aenderung (Prinzip #6, §44).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
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


def _format_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "-"
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


class BackupsView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("backups_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("backups_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.create_db_btn = QPushButton(tr("backups_view.create_db_button"))
        self.create_db_btn.setObjectName("Primary")
        self.create_db_btn.clicked.connect(self._on_create_db_clicked)
        self.create_config_btn = QPushButton(tr("backups_view.create_config_button"))
        self.create_config_btn.clicked.connect(self._on_create_config_clicked)
        self.refresh_btn = QPushButton(tr("backups_view.refresh_button"))
        self.refresh_btn.clicked.connect(self._reload)
        controls.addWidget(self.create_db_btn)
        controls.addWidget(self.create_config_btn)
        controls.addWidget(self.refresh_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("backups_view.col_id"),
            tr("backups_view.col_type"),
            tr("backups_view.col_created"),
            tr("backups_view.col_size"),
            tr("backups_view.col_path"),
        ])
        self.tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, stretch=1)

        action_row = QHBoxLayout()
        self.restore_btn = QPushButton(tr("backups_view.restore_button"))
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        action_row.addWidget(self.restore_btn)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self._reload()

    # --- Aktionen -------------------------------------------------------------

    def _on_create_db_clicked(self) -> None:
        try:
            self.api.create_db_backup()
        except GenesisAPIError as exc:
            show_api_error(self, exc)
            return
        self.status_label.setText(tr("backups_view.create_done"))
        self._reload()

    def _on_create_config_clicked(self) -> None:
        try:
            self.api.create_config_backup()
        except GenesisAPIError as exc:
            show_api_error(self, exc)
            return
        self.status_label.setText(tr("backups_view.create_done"))
        self._reload()

    def _on_restore_clicked(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        backup_id = item.data(0, Qt.UserRole)
        reply = QMessageBox.question(
            self,
            tr("backups_view.restore_confirm_title"),
            tr("backups_view.restore_confirm_text", backup_id=backup_id),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.api.restore_backup(backup_id, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc)
            return
        self.status_label.setText(tr("backups_view.restore_done"))
        self._reload()

    def _on_selection_changed(self) -> None:
        self.restore_btn.setEnabled(self.tree.currentItem() is not None)

    # --- Laden ------------------------------------------------------------------

    def _reload(self) -> None:
        try:
            backups = self.api.list_backups()
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("backups_view.load_failed", error=str(exc)))
            return

        self.tree.clear()
        for backup in backups:
            item = QTreeWidgetItem([
                str(backup["id"]),
                backup["backup_type"],
                backup["created_at"] or "-",
                _format_size(backup["size_bytes"]),
                backup["path"],
            ])
            item.setData(0, Qt.UserRole, backup["id"])
            self.tree.addTopLevelItem(item)

        if not backups:
            self.status_label.setText(tr("backups_view.no_backups"))
        self.restore_btn.setEnabled(False)
