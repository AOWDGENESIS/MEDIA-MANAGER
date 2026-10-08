"""Log-Viewer (nav.logs, §54, Gap-Analyse Gap J).

Strukturiertes Datei-Logging (TRACE…CRITICAL) existierte bereits
(`genesis_core/logutil`), aber `nav.logs` war bisher nur eine reine
Navigations-Platzhalterseite ohne echten Inhalt. Diese Ansicht zeigt die
Logeinträge über den neuen `GET /logs`-Endpunkt an - rein lesend
(Prinzip #4/#5), es gibt keine Möglichkeit, Logeinträge über die GUI zu
löschen oder zu verändern.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

#: Reihenfolge entspricht `genesis_core.logutil.reader.LEVEL_ORDER` -
#: "beliebig" (kein Mindest-Level) steht bewusst an erster Stelle.
LEVEL_FILTER_CHOICES = ["", "TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

PAGE_SIZE = 200


class LogViewerView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._offset = 0
        self._total = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("log_viewer_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("log_viewer_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.level_combo = QComboBox()
        for value in LEVEL_FILTER_CHOICES:
            label = tr("log_viewer_view.level_any") if value == "" else value
            self.level_combo.addItem(label, userData=value)
        self.level_combo.currentIndexChanged.connect(lambda _i: self._reload())
        controls.addWidget(QLabel(tr("log_viewer_view.level_label")))
        controls.addWidget(self.level_combo)

        self.component_edit = QLineEdit()
        self.component_edit.setPlaceholderText(tr("log_viewer_view.component_placeholder"))
        self.component_edit.returnPressed.connect(self._reload)
        controls.addWidget(self.component_edit)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("log_viewer_view.search_placeholder"))
        self.search_edit.returnPressed.connect(self._reload)
        controls.addWidget(self.search_edit)

        self.refresh_btn = QPushButton(tr("log_viewer_view.refresh_button"))
        self.refresh_btn.clicked.connect(self._reload)
        controls.addWidget(self.refresh_btn)
        root.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("log_viewer_view.col_timestamp"),
            tr("log_viewer_view.col_level"),
            tr("log_viewer_view.col_component"),
            tr("log_viewer_view.col_message"),
        ])
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, stretch=1)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("DetailBox")
        root.addWidget(self.detail_label)

        pagination_row = QHBoxLayout()
        self.prev_btn = QPushButton(tr("log_viewer_view.previous_page_button"))
        self.prev_btn.clicked.connect(self._on_previous_page)
        self.next_btn = QPushButton(tr("log_viewer_view.next_page_button"))
        self.next_btn.clicked.connect(self._on_next_page)
        pagination_row.addWidget(self.prev_btn)
        pagination_row.addWidget(self.next_btn)
        pagination_row.addStretch(1)
        root.addLayout(pagination_row)

        self._reload()

    # -- Datenabruf ------------------------------------------------------------

    def _current_filters(self) -> dict:
        return {
            "level": self.level_combo.currentData() or None,
            "component": self.component_edit.text().strip() or None,
            "search": self.search_edit.text().strip() or None,
        }

    def _reload(self) -> None:
        """Setzt beim Aendern eines Filters bewusst auf die erste Seite
        zurueck (§57 - sonst koennte ein Offset ins Leere zeigen, wenn ein
        strengerer Filter weniger Treffer liefert)."""
        self._offset = 0
        self._fetch_and_render()

    def _fetch_and_render(self) -> None:
        try:
            data = self.api.get_logs(
                limit=PAGE_SIZE, offset=self._offset, **self._current_filters()
            )
        except GenesisAPIError as exc:
            self.status_label.setText(tr("log_viewer_view.error_api", error=exc))
            return

        self._total = data["total"]
        items = data["items"]
        self.tree.clear()
        for entry in items:
            item = QTreeWidgetItem([
                entry["timestamp"],
                entry["level"],
                entry["component"].strip(),
                entry["message"].splitlines()[0] if entry["message"] else "",
            ])
            item.setData(0, Qt.UserRole, entry)
            self.tree.addTopLevelItem(item)

        shown_from = self._offset + 1 if items else 0
        shown_to = self._offset + len(items)
        self.status_label.setText(
            tr(
                "log_viewer_view.status_summary",
                shown_from=shown_from, shown_to=shown_to, total=self._total,
            )
        )
        self.prev_btn.setEnabled(self._offset > 0)
        self.next_btn.setEnabled(self._offset + PAGE_SIZE < self._total)
        set_plain_text(self.detail_label, "")

    def _on_previous_page(self) -> None:
        self._offset = max(0, self._offset - PAGE_SIZE)
        self._fetch_and_render()

    def _on_next_page(self) -> None:
        if self._offset + PAGE_SIZE < self._total:
            self._offset += PAGE_SIZE
            self._fetch_and_render()

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            set_plain_text(self.detail_label, "")
            return
        entry = items[0].data(0, Qt.UserRole)
        if entry:
            set_plain_text(self.detail_label, entry["message"])
