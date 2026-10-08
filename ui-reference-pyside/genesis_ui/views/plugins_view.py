"""Plugins (nav.plugins, §34).

Rein lesende Uebersicht ueber alle beim Start aus `data_dir/plugins/`
geladenen Plugins - AUCH die fehlgeschlagenen, mit Klartext-Fehlermeldung
(§34: ein kaputtes Plugin wird sichtbar gemacht, statt es stillschweigend
zu verstecken oder den Host damit zu destabilisieren). "Neu laden" ist
unkritisch (liest nur erneut das Plugin-Verzeichnis ein, veraendert keine
Nutzerdaten) und erspart einen Neustart des Core Service, nachdem der
Nutzer ein eigenes Plugin in den Ordner gelegt hat.
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


class PluginsView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("plugins_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("plugins_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.reload_btn = QPushButton(tr("plugins_view.reload_button"))
        self.reload_btn.setObjectName("Primary")
        self.reload_btn.clicked.connect(self._on_reload_clicked)
        controls.addWidget(self.reload_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.plugins_dir_label = QLabel("")
        self.plugins_dir_label.setWordWrap(True)
        root.addWidget(self.plugins_dir_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("plugins_view.col_id"),
            tr("plugins_view.col_kind"),
            tr("plugins_view.col_name"),
            tr("plugins_view.col_version"),
            tr("plugins_view.col_author"),
            tr("plugins_view.col_license"),
            tr("plugins_view.col_status"),
        ])
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        root.addWidget(self.tree, stretch=1)

        self._reload()

    def _on_reload_clicked(self) -> None:
        try:
            result = self.api.reload_plugins()
        except GenesisAPIError as exc:
            show_api_error(self, exc)
            return
        self._render(result)

    def _reload(self) -> None:
        try:
            result = self.api.list_plugins()
        except GenesisAPIError as exc:
            self.status_label.setText(tr("plugins_view.load_failed", error=str(exc)))
            return
        self._render(result)

    def _render(self, result: dict) -> None:
        # set_plain_text() statt .setText(): der Ordnerpfad kommt aus den
        # Core-Einstellungen, kein fest im Quellcode stehender Text
        # (Deep-Review-Fund Sitzung 11).
        set_plain_text(
            self.plugins_dir_label,
            tr("plugins_view.plugins_dir_label", path=result["plugins_dir"]),
        )
        plugins = result["plugins"]
        self.tree.clear()
        for plugin in plugins:
            status_key = (
                "plugins_view.status_loaded" if plugin["loaded_successfully"]
                else "plugins_view.status_failed"
            )
            status_text = tr(status_key)
            if not plugin["loaded_successfully"] and plugin.get("load_error"):
                status_text = f"{status_text}: {plugin['load_error']}"
            item = QTreeWidgetItem([
                plugin["plugin_id"] or "-",
                plugin["plugin_kind"] or "-",
                plugin["display_name"] or "-",
                plugin["version"] or "-",
                plugin["author"] or "-",
                plugin["license"] or "-",
                status_text,
            ])
            self.tree.addTopLevelItem(item)

        self.status_label.setText("" if plugins else tr("plugins_view.no_plugins"))
