"""Ansicht fuer die Duplikaterkennung (nav.duplicates, §21, ADR-0013).

Bewusst eine EIGENE Navigationsseite (anders als Cutter/Loudness/Convert,
die als Pro-Datei-Dialoge aus der Medientabelle heraus geoeffnet werden) -
ein Duplikat-Scan betrifft immer die GESAMTE (oder nach Medienart gefilterte)
Bibliothek, nicht eine einzelne Datei.

Ablauf: Scan starten (reine Analyse, erzeugt/loescht/aendert KEINE Datei) ->
Ergebnisliste mit Kategorie + Confidence + Begruendung + Dateipfaden ->
Nutzer kann eine Gruppe als "geprueft" markieren (rein organisatorisch, keine
Dateiaenderung) oder diese Markierung wieder aufheben. Es gibt bewusst KEINE
Loeschfunktion (§21: "Niemals automatisch löschen" - Loeschen ist in dieser
Version ueberhaupt nicht Teil des Werkzeugs, auch nicht manuell)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
from genesis_ui.i18n import MEDIA_KIND_LABEL_KEYS, tr
from genesis_ui.widgets import set_plain_text

CATEGORY_LABEL_KEYS = {
    "exact_duplicate": "duplicates_view.category_exact",
    "probable_duplicate": "duplicates_view.category_probable",
    "same_content_different_format": "duplicates_view.category_same_content",
    "similar_content": "duplicates_view.category_similar",
}

SCOPE_OPTIONS = [(None, "duplicates_view.scope_all")] + [
    (kind, label_key) for kind, label_key in MEDIA_KIND_LABEL_KEYS.items()
]


class DuplicatesView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._path_cache: dict[int, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("duplicates_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("duplicates_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        controls.addWidget(QLabel(tr("duplicates_view.scope_label")))
        self.scope_combo = QComboBox()
        for _kind, label_key in SCOPE_OPTIONS:
            self.scope_combo.addItem(tr(label_key))
        controls.addWidget(self.scope_combo)

        self.scan_btn = QPushButton(tr("duplicates_view.scan_button"))
        self.scan_btn.setObjectName("Primary")
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        controls.addWidget(self.scan_btn)

        self.show_reviewed_combo = QComboBox()
        self.show_reviewed_combo.addItem(tr("duplicates_view.filter_open"), False)
        self.show_reviewed_combo.addItem(tr("duplicates_view.filter_reviewed"), True)
        self.show_reviewed_combo.addItem(tr("duplicates_view.filter_all"), None)
        self.show_reviewed_combo.currentIndexChanged.connect(lambda _i: self._reload())
        controls.addWidget(self.show_reviewed_combo)
        controls.addStretch(1)
        root.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("duplicates_view.col_category"),
            tr("duplicates_view.col_confidence"),
            tr("duplicates_view.col_files"),
            tr("duplicates_view.col_reason"),
            tr("duplicates_view.col_status"),
        ])
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.tree, stretch=1)

        action_row = QHBoxLayout()
        self.mark_reviewed_btn = QPushButton(tr("duplicates_view.mark_reviewed_button"))
        self.mark_reviewed_btn.setEnabled(False)
        self.mark_reviewed_btn.clicked.connect(self._on_mark_reviewed_clicked)
        self.unreview_btn = QPushButton(tr("duplicates_view.unreview_button"))
        self.unreview_btn.setEnabled(False)
        self.unreview_btn.clicked.connect(self._on_unreview_clicked)
        action_row.addWidget(self.mark_reviewed_btn)
        action_row.addWidget(self.unreview_btn)
        action_row.addStretch(1)
        root.addLayout(action_row)

        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        self._reload()

    # --- Aktionen ---------------------------------------------------------

    def _on_scan_clicked(self) -> None:
        scope_index = self.scope_combo.currentIndex()
        kind = SCOPE_OPTIONS[scope_index][0]
        self.scan_btn.setEnabled(False)
        self.status_label.setText(tr("duplicates_view.scanning"))
        try:
            groups = self.api.scan_duplicates(kind=kind)
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("duplicates_view.scan_failed", error=exc))
            self.scan_btn.setEnabled(True)
            return
        self.scan_btn.setEnabled(True)
        self.status_label.setText(tr("duplicates_view.scan_done", count=len(groups)))
        self._reload()

    def _on_mark_reviewed_clicked(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            return
        try:
            self.api.review_duplicate_group(group_id)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("duplicates_view.review_failed", error=exc))
            return
        self._reload()

    def _on_unreview_clicked(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            return
        try:
            self.api.unreview_duplicate_group(group_id)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("duplicates_view.review_failed", error=exc))
            return
        self._reload()

    def _on_selection_changed(self) -> None:
        item = self.tree.currentItem()
        has_selection = item is not None
        reviewed = bool(item.data(0, Qt.UserRole + 1)) if has_selection else False
        self.mark_reviewed_btn.setEnabled(has_selection and not reviewed)
        self.unreview_btn.setEnabled(has_selection and reviewed)

    def _selected_group_id(self) -> int | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        return item.data(0, Qt.UserRole)

    # --- Laden --------------------------------------------------------------

    def _resolve_path(self, media_file_id: int) -> str:
        if media_file_id in self._path_cache:
            return self._path_cache[media_file_id]
        try:
            detail = self.api.media_detail(media_file_id)
            path = detail.get("absolute_path", f"#{media_file_id}")
        except GenesisAPIError:
            path = f"#{media_file_id}"
        self._path_cache[media_file_id] = path
        return path

    def _reload(self) -> None:
        self.tree.clear()
        reviewed_filter = self.show_reviewed_combo.currentData()
        try:
            groups = self.api.list_duplicates(reviewed=reviewed_filter)
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("duplicates_view.load_failed", error=exc))
            return

        for group in groups:
            category_key = CATEGORY_LABEL_KEYS.get(group["category"], group["category"])
            paths = [self._resolve_path(mid) for mid in group["media_file_ids"]]
            status_key = (
                "duplicates_view.status_reviewed" if group["reviewed"]
                else "duplicates_view.status_open"
            )
            item = QTreeWidgetItem([
                tr(category_key),
                f"{group['confidence']:.0%}",
                "\n".join(paths),
                group["reason"],
                tr(status_key),
            ])
            item.setData(0, Qt.UserRole, group["id"])
            item.setData(0, Qt.UserRole + 1, group["reviewed"])
            self.tree.addTopLevelItem(item)

        if not groups:
            self.status_label.setText(tr("duplicates_view.no_results"))
        self.mark_reviewed_btn.setEnabled(False)
        self.unreview_btn.setEnabled(False)
