"""Dialog fuer das Artwork-Modul (§22): Cover anzeigen, online suchen
(nur Vorschlag/Cache), und erst nach expliziter Bestaetigung einbetten
(Prinzip #17, §44) - die Mediendatei wird nie automatisch veraendert."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text

PREVIEW_SIZE = 320


class ArtworkDialog(QDialog):
    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.changed = False
        self._pending_artwork_id: int | None = None

        self.setWindowTitle(tr("artwork_dialog.window_title", filename=filename))
        self.resize(420, 520)

        root = QVBoxLayout(self)

        self.status_label = QLabel(tr("artwork_dialog.loading"))
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.image_label.setStyleSheet("border: 1px solid #444;")
        root.addWidget(self.image_label, stretch=1)

        btn_row = QHBoxLayout()
        self.fetch_btn = QPushButton(tr("artwork_dialog.fetch_button"))
        self.fetch_btn.clicked.connect(self._on_fetch_online_clicked)
        self.embed_btn = QPushButton(tr("artwork_dialog.embed_button"))
        self.embed_btn.setEnabled(False)
        self.embed_btn.clicked.connect(self._on_embed_clicked)
        close_btn = QPushButton(tr("artwork_dialog.close_button"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.fetch_btn)
        btn_row.addWidget(self.embed_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        info = QLabel(tr("artwork_dialog.info"))
        info.setWordWrap(True)
        root.addWidget(info)

        self._load_embedded()

    def _show_pixmap_from_bytes(self, data: bytes) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(data) and not pixmap.isNull():
            self.image_label.setPixmap(
                pixmap.scaled(
                    PREVIEW_SIZE, PREVIEW_SIZE,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
            )
        else:
            self.image_label.setText(tr("artwork_dialog.image_unloadable"))

    def _load_embedded(self) -> None:
        try:
            result = self.api.get_artwork_bytes(self.media_id)
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("artwork_dialog.load_failed", error=exc))
            return

        if result is None:
            self.status_label.setText(tr("artwork_dialog.none_embedded"))
            self.image_label.setText(tr("artwork_dialog.no_cover_placeholder"))
            return

        data, _mime = result
        self.status_label.setText(tr("artwork_dialog.current_embedded"))
        self._show_pixmap_from_bytes(data)

    def _on_fetch_online_clicked(self) -> None:
        try:
            result = self.api.fetch_artwork_online(self.media_id)
        except GenesisAPIError as exc:
            QMessageBox.warning(
                self, tr("artwork_dialog.fetch_failed_title"),
                tr("artwork_dialog.fetch_failed_text", error=exc),
            )
            return

        self._pending_artwork_id = result["artwork_id"]
        cached_path = result["cached_path"]
        try:
            with open(cached_path, "rb") as f:
                data = f.read()
            self.status_label.setText(tr("artwork_dialog.fetched_not_embedded"))
            self._show_pixmap_from_bytes(data)
            self.embed_btn.setEnabled(True)
        except OSError as exc:
            QMessageBox.warning(self, tr("common.error_title"),
                                 tr("artwork_dialog.cache_read_failed", error=exc))

    def _on_embed_clicked(self) -> None:
        if self._pending_artwork_id is None:
            return
        confirm = QMessageBox.question(
            self,
            tr("artwork_dialog.confirm_title"),
            tr("artwork_dialog.confirm_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.api.embed_artwork(self.media_id, self._pending_artwork_id, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("artwork_dialog.embed_failed", error=exc))
            return

        self.changed = True
        self.embed_btn.setEnabled(False)
        QMessageBox.information(
            self, tr("artwork_dialog.embedded_title"), tr("artwork_dialog.embedded_text")
        )
        self._load_embedded()
