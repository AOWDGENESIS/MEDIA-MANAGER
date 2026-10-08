"""Fehler-Center (nav.error_center, §37).

Zeigt die protokollierten Fehlereintraege (jeder mit eigener, dauerhaft
nachschlagbarer Fehler-ID) aus der zentralen `error_log`-Tabelle. "Geloest"
markieren ist eine rein organisatorische Kennzeichnung (dieselbe Art
Markierung wie bei Duplikat-Gruppen) - es werden dabei nie Dateien oder
sonstige Fachdaten veraendert, nur der Eintrag selbst.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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


class ErrorCenterView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._errors_by_id: dict[str, dict] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("error_center_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("error_center_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.unresolved_checkbox = QCheckBox(tr("error_center_view.unresolved_only_checkbox"))
        self.unresolved_checkbox.setChecked(True)
        self.unresolved_checkbox.stateChanged.connect(lambda _s: self._reload())
        controls.addWidget(self.unresolved_checkbox)
        self.refresh_btn = QPushButton(tr("error_center_view.refresh_button"))
        self.refresh_btn.clicked.connect(self._reload)
        controls.addWidget(self.refresh_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("error_center_view.col_error_id"),
            tr("error_center_view.col_timestamp"),
            tr("error_center_view.col_component"),
            tr("error_center_view.col_message"),
            tr("error_center_view.col_resolved"),
        ])
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, stretch=1)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("DetailBox")
        root.addWidget(self.detail_label)

        action_row = QHBoxLayout()
        self.resolve_btn = QPushButton(tr("error_center_view.resolve_button"))
        self.resolve_btn.setEnabled(False)
        self.resolve_btn.clicked.connect(self._on_resolve_clicked)
        action_row.addWidget(self.resolve_btn)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self._reload()

    # --- Aktionen -------------------------------------------------------------

    def _on_resolve_clicked(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        error_id = item.data(0, Qt.UserRole)
        try:
            self.api.resolve_error(error_id)
        except GenesisAPIError as exc:
            show_api_error(self, exc)
            return
        self._reload()

    def _on_selection_changed(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            self.detail_label.setText("")
            self.resolve_btn.setEnabled(False)
            return
        error_id = item.data(0, Qt.UserRole)
        error = self._errors_by_id.get(error_id, {})
        lines = [
            tr("error_center_view.detail_solution", hint=error.get("solution_hint") or "-"),
            tr(
                "error_center_view.detail_technical",
                details=error.get("technical_details") or "-",
            ),
        ]
        if error.get("file_path"):
            lines.append(tr("error_center_view.detail_file_path", path=error["file_path"]))
        # set_plain_text() statt .setText(): Fehlermeldung/technische
        # Details/Dateipfad stammen aus dem Core Service bzw. aus
        # tatsaechlichen Ausnahmen - keine fest im Quellcode stehenden
        # Texte (Deep-Review-Fund Sitzung 11).
        set_plain_text(self.detail_label, "\n".join(lines))
        self.resolve_btn.setEnabled(not bool(error.get("resolved")))

    # --- Laden ------------------------------------------------------------------

    def _reload(self) -> None:
        try:
            errors = self.api.list_errors(
                limit=200, unresolved_only=self.unresolved_checkbox.isChecked()
            )
        except GenesisAPIError as exc:
            self.status_label.setText(tr("error_center_view.load_failed", error=str(exc)))
            return

        self._errors_by_id = {e["error_id"]: e for e in errors}
        self.tree.clear()
        for error in errors:
            resolved_key = (
                "error_center_view.status_resolved" if error["resolved"]
                else "error_center_view.status_open"
            )
            item = QTreeWidgetItem([
                error["error_id"],
                error["timestamp"] or "-",
                error["component"] or "-",
                error["message"],
                tr(resolved_key),
            ])
            item.setData(0, Qt.UserRole, error["error_id"])
            self.tree.addTopLevelItem(item)

        self.status_label.setText("" if errors else tr("error_center_view.no_errors"))
        self.detail_label.setText("")
        self.resolve_btn.setEnabled(False)
