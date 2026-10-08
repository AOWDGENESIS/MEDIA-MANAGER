"""KI-Center: Status + lokale semantische Suche (§25 Transparenz, §26,
Phase 6, ADR-0017).

Eigene Navigationsseite (nicht an eine einzelne Datei gebunden), analog zu
`DuplicatesView` - semantische Suche betrifft immer die gesamte (bereits
indizierte) Bibliothek. Pro-Datei-KI-Vorschläge (§25) und KI-Musik-Angaben
(§27) bleiben dagegen im `AIDialog` aus der Medientabelle heraus erreichbar
(dieselbe Architekturentscheidung wie Cutter/Loudness/Convert vs.
Duplicate-Scan).

Reindex ist eine reine additive Cache-Operation (kein `confirm` noetig,
Prinzip #17 gilt fuer Metadatenaenderungen, nicht fuer einen Suchindex).
Ist die KI deaktiviert (§56-Standard), zeigt die Seite das klar an statt
eine verwirrende leere Ergebnisliste ohne Erklaerung.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
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
from genesis_ui.i18n import MEDIA_KIND_LABEL_KEYS, tr
from genesis_ui.widgets import set_plain_text


class AICenterView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(tr("ai_center.title"))
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.status_banner = QLabel(tr("ai_dialog.loading"))
        self.status_banner.setWordWrap(True)
        self.status_banner.setStyleSheet("color: #9fb8d8;")
        layout.addWidget(self.status_banner)

        reindex_row = QHBoxLayout()
        self.reindex_btn = QPushButton(tr("ai_center.reindex_button"))
        self.reindex_btn.clicked.connect(self._on_reindex_clicked)
        reindex_row.addWidget(self.reindex_btn)
        self.reindex_status_label = QLabel("")
        reindex_row.addWidget(self.reindex_status_label)
        reindex_row.addStretch(1)
        layout.addLayout(reindex_row)

        search_row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(tr("ai_center.query_placeholder"))
        self.query_edit.returnPressed.connect(self._on_search_clicked)
        search_row.addWidget(self.query_edit, stretch=1)
        self.search_btn = QPushButton(tr("ai_center.search_button"))
        self.search_btn.clicked.connect(self._on_search_clicked)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        self.search_status_label = QLabel("")
        self.search_status_label.setWordWrap(True)
        layout.addWidget(self.search_status_label)

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(
            [tr("ai_center.col_filename"), tr("ai_center.col_kind"), tr("ai_center.col_score")]
        )
        self.results_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.results_tree, stretch=1)

        self._load_status()

    def _load_status(self) -> None:
        try:
            status = self.api.get_ai_status()
        except GenesisAPIError as exc:
            set_plain_text(self.status_banner, tr("ai_dialog.status_load_failed", error=exc))
            return
        if not status.get("enabled"):
            self.status_banner.setText(tr("ai_dialog.status_disabled"))
        elif not status.get("available"):
            # provider kommt aus der Core-Konfiguration (dynamisch).
            set_plain_text(
                self.status_banner,
                tr("ai_dialog.status_unavailable", provider=status.get("provider")),
            )
        else:
            set_plain_text(
                self.status_banner,
                tr(
                    "ai_dialog.status_active",
                    provider=status.get("provider"),
                    model=status.get("embedding_model"),
                ),
            )

    def _on_reindex_clicked(self) -> None:
        self.reindex_status_label.setText(tr("ai_center.reindexing"))
        try:
            stats = self.api.reindex_ai_search()
        except GenesisAPIError as exc:
            set_plain_text(self.reindex_status_label, tr("ai_center.reindex_failed", error=exc))
            return
        self.reindex_status_label.setText(
            tr("ai_center.reindex_done", embedded=stats["embedded"], total=stats["total"])
        )

    def _on_search_clicked(self) -> None:
        query = self.query_edit.text().strip()
        if not query:
            return
        self.results_tree.clear()
        try:
            result = self.api.ai_semantic_search(query)
        except GenesisAPIError as exc:
            set_plain_text(self.search_status_label, tr("ai_center.search_failed", error=exc))
            return

        if not result.get("available"):
            self.search_status_label.setText(tr("ai_center.search_unavailable"))
            return
        results = result.get("results") or []
        if not results:
            self.search_status_label.setText(tr("ai_center.no_results"))
            return
        self.search_status_label.setText(tr("ai_center.results_found", count=len(results)))
        for r in results:
            kind_label = tr(MEDIA_KIND_LABEL_KEYS.get(r["kind"], r["kind"]))
            item = QTreeWidgetItem([r["filename"], kind_label, f"{r['score']:.0%}"])
            self.results_tree.addTopLevelItem(item)
