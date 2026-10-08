"""Dialog für Hörbücher & Kapitel (§23, Phase 4, ADR-0015).

Ablauf (Erkennen -> Vorschlag -> Vorschau -> Benutzerfreigabe -> Änderung,
Prinzip #4/#17):
1. Beim Öffnen werden bereits in der Datei eingebettete Tags gelesen
   (`audiobook/tags`-Vorschau) sowie bereits gespeicherte Hörbuch-
   Metadaten/Kapitel geladen - beides rein lesend, keine Bestätigung nötig.
2. Eine Übernahme der Tag-Vorschau in die DB, eine Kapitel-Erkennung/
   -Erzeugung sowie ein Kapitel-Umbenennen erfordern JEWEILS eine explizite
   Bestätigung (Ja/Nein-Dialog) - auch wenn die Quelle "nur" die Datei
   selbst ist (Konsistenz mit dem projektweiten Sicherheitsmodell).
3. Export (JSON/CSV) ist eine reine Lesefunktion ohne Bestätigungspflicht.

Es gibt bewusst KEINEN Online-Hörbuch-Provider (Audible etc. sind
Download/Import-Adapter, Phase 8) - siehe genesis_core/audiobook/engine.py.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


def _format_ms(ms: int | None) -> str:
    if ms is None:
        return tr("common.value_empty")
    total_seconds = ms / 1000.0
    minutes, seconds = divmod(total_seconds, 60)
    return f"{int(minutes):02d}:{seconds:05.2f}"


class AudiobookDialog(QDialog):
    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.changed = False
        self._tag_preview: dict | None = None
        self._pending_candidates: list[dict] = []
        self._pending_action: str | None = None  # "detect" oder "generate"

        self.setWindowTitle(tr("audiobook_dialog.window_title", filename=filename))
        self.resize(760, 640)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)

        tabs.addTab(self._build_metadata_tab(), tr("audiobook_dialog.tab_metadata"))
        tabs.addTab(self._build_chapters_tab(), tr("audiobook_dialog.tab_chapters"))

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton(tr("audiobook_dialog.close_button"))
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._load_metadata()
        self._load_chapters()

    # --- Tab 1: Metadaten (aus eingebetteten Tags) ---------------------------

    def _build_metadata_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(tr("audiobook_dialog.metadata_info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.metadata_status_label = QLabel(tr("audiobook_dialog.loading"))
        layout.addWidget(self.metadata_status_label)

        form = QFormLayout()
        self.title_label = QLabel()
        self.author_label = QLabel()
        self.narrator_label = QLabel()
        self.series_label = QLabel()
        self.volume_label = QLabel()
        self.publisher_label = QLabel()
        self.year_label = QLabel()
        self.language_label = QLabel()
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        for label_widget in (
            self.title_label, self.author_label, self.narrator_label, self.series_label,
            self.volume_label, self.publisher_label, self.year_label, self.language_label,
            self.description_label,
        ):
            label_widget.setWordWrap(True)
        form.addRow(tr("audiobook_dialog.field_title"), self.title_label)
        form.addRow(tr("audiobook_dialog.field_author"), self.author_label)
        form.addRow(tr("audiobook_dialog.field_narrator"), self.narrator_label)
        form.addRow(tr("audiobook_dialog.field_series"), self.series_label)
        form.addRow(tr("audiobook_dialog.field_volume"), self.volume_label)
        form.addRow(tr("audiobook_dialog.field_publisher"), self.publisher_label)
        form.addRow(tr("audiobook_dialog.field_year"), self.year_label)
        form.addRow(tr("audiobook_dialog.field_language"), self.language_label)
        form.addRow(tr("audiobook_dialog.field_description"), self.description_label)
        layout.addLayout(form)

        self.persisted_label = QLabel(tr("audiobook_dialog.not_saved_yet"))
        self.persisted_label.setWordWrap(True)
        self.persisted_label.setStyleSheet("color: #8fbf8f;")
        layout.addWidget(self.persisted_label)

        btn_row = QHBoxLayout()
        self.apply_tags_btn = QPushButton(tr("audiobook_dialog.apply_tags_button"))
        self.apply_tags_btn.setEnabled(False)
        self.apply_tags_btn.clicked.connect(self._on_apply_tags_clicked)
        btn_row.addWidget(self.apply_tags_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return tab

    def _load_metadata(self) -> None:
        try:
            self._tag_preview = self.api.get_audiobook_tags_preview(self.media_id)
        except GenesisAPIError as exc:
            # Core-Fehlermeldung ist dynamischer Text, siehe Moduldocstring
            # von genesis_ui.widgets.
            set_plain_text(self.metadata_status_label, tr("audiobook_dialog.load_failed", error=exc))
            return

        p = self._tag_preview
        empty = tr("common.value_empty")
        if not p.get("has_any_tag"):
            self.metadata_status_label.setText(tr("audiobook_dialog.no_tags_found"))
        else:
            self.metadata_status_label.setText(tr("audiobook_dialog.tags_found"))

        def _with_source(value, source_key, source_label_key) -> str:
            if value is None:
                return empty
            if source_key and p.get(source_key):
                return f"{value}  ({tr(source_label_key)})"
            return str(value)

        # Deep-Review-Fund (Sitzung 11, Fortsetzung): Titel/Autor/Erzaehler/
        # Serie/Verlag/Sprache/Beschreibung kommen aus eingebetteten
        # Datei-Tags (externe, vom Nutzer nicht hier eingegebene Werte) -
        # set_plain_text() statt setText() verhindert Qt.AutoText-
        # Fehlinterpretation (siehe genesis_ui.widgets-Moduldocstring).
        set_plain_text(self.title_label, p.get("title") or empty)
        set_plain_text(
            self.author_label,
            _with_source(
                p.get("author"), "author_source",
                "audiobook_dialog.source_artist_field"
                if p.get("author_source") == "artist_field"
                else "audiobook_dialog.source_tag",
            ),
        )
        set_plain_text(
            self.narrator_label,
            _with_source(
                p.get("narrator"), "narrator_source",
                "audiobook_dialog.source_composer_field"
                if p.get("narrator_source") == "composer_field"
                else "audiobook_dialog.source_tag",
            ),
        )
        set_plain_text(
            self.series_label,
            _with_source(
                p.get("series"), "series_source",
                "audiobook_dialog.source_album_field"
                if p.get("series_source") == "album_field"
                else "audiobook_dialog.source_tag",
            ),
        )
        self.volume_label.setText(str(p.get("volume_number")) if p.get("volume_number") else empty)
        set_plain_text(self.publisher_label, p.get("publisher") or empty)
        self.year_label.setText(str(p.get("year")) if p.get("year") else empty)
        set_plain_text(self.language_label, p.get("language") or empty)
        set_plain_text(self.description_label, p.get("description") or empty)

        self.apply_tags_btn.setEnabled(bool(p.get("has_any_tag")))
        self._reload_persisted_audiobook()

    def _reload_persisted_audiobook(self) -> None:
        try:
            saved = self.api.get_audiobook(self.media_id)
        except GenesisAPIError:
            saved = None
        if saved is None:
            self.persisted_label.setText(tr("audiobook_dialog.not_saved_yet"))
        else:
            # Dynamisch: title/author stammen aus gespeicherten,
            # vom Nutzer nicht hier eingegebenen Hoerbuch-Metadaten.
            set_plain_text(
                self.persisted_label,
                tr(
                    "audiobook_dialog.saved_summary",
                    title=saved.get("title") or tr("common.value_empty"),
                    author=saved.get("author") or tr("common.value_empty"),
                ),
            )

    def _on_apply_tags_clicked(self) -> None:
        confirm = QMessageBox.question(
            self,
            tr("audiobook_dialog.confirm_tags_title"),
            tr("audiobook_dialog.confirm_tags_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.api.apply_audiobook_tags(self.media_id, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.apply_tags_failed", error=exc))
            return
        self.changed = True
        self._reload_persisted_audiobook()
        QMessageBox.information(
            self, tr("audiobook_dialog.applied_title"), tr("audiobook_dialog.applied_text")
        )

    # --- Tab 2: Kapitel --------------------------------------------------------

    def _build_chapters_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel(tr("audiobook_dialog.chapters_current_label")))
        self.chapters_table = QTableWidget(0, 4)
        self.chapters_table.setHorizontalHeaderLabels([
            tr("audiobook_dialog.column_index"), tr("audiobook_dialog.column_title"),
            tr("audiobook_dialog.column_start"), tr("audiobook_dialog.column_end"),
        ])
        self.chapters_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.chapters_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.chapters_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.chapters_table, stretch=1)

        chapter_action_row = QHBoxLayout()
        self.rename_chapter_btn = QPushButton(tr("audiobook_dialog.rename_chapter_button"))
        self.rename_chapter_btn.setEnabled(False)
        self.rename_chapter_btn.clicked.connect(self._on_rename_chapter_clicked)
        self.export_json_btn = QPushButton(tr("audiobook_dialog.export_json_button"))
        self.export_json_btn.clicked.connect(lambda: self._on_export_clicked("json"))
        self.export_csv_btn = QPushButton(tr("audiobook_dialog.export_csv_button"))
        self.export_csv_btn.clicked.connect(lambda: self._on_export_clicked("csv"))
        chapter_action_row.addWidget(self.rename_chapter_btn)
        chapter_action_row.addStretch(1)
        chapter_action_row.addWidget(self.export_json_btn)
        chapter_action_row.addWidget(self.export_csv_btn)
        layout.addLayout(chapter_action_row)
        self.chapters_table.itemSelectionChanged.connect(
            lambda: self.rename_chapter_btn.setEnabled(
                bool(self.chapters_table.selectionModel().selectedRows())
            )
        )

        layout.addWidget(QLabel(tr("audiobook_dialog.detect_section_label")))
        detect_row = QHBoxLayout()
        self.detect_btn = QPushButton(tr("audiobook_dialog.detect_button"))
        self.detect_btn.clicked.connect(self._on_detect_clicked)
        detect_row.addWidget(self.detect_btn)
        detect_row.addStretch(1)
        layout.addLayout(detect_row)

        layout.addWidget(QLabel(tr("audiobook_dialog.generate_section_label")))
        generate_row = QHBoxLayout()
        generate_row.addWidget(QLabel(tr("audiobook_dialog.interval_label")))
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 240.0)
        self.interval_spin.setValue(10.0)
        self.interval_spin.setSuffix(f" {tr('audiobook_dialog.minutes_suffix')}")
        generate_row.addWidget(self.interval_spin)
        self.generate_preview_btn = QPushButton(tr("audiobook_dialog.generate_preview_button"))
        self.generate_preview_btn.clicked.connect(self._on_generate_preview_clicked)
        generate_row.addWidget(self.generate_preview_btn)
        generate_row.addStretch(1)
        layout.addLayout(generate_row)

        layout.addWidget(QLabel(tr("audiobook_dialog.preview_label")))
        self.candidates_table = QTableWidget(0, 3)
        self.candidates_table.setHorizontalHeaderLabels([
            tr("audiobook_dialog.column_title"), tr("audiobook_dialog.column_start"),
            tr("audiobook_dialog.column_end"),
        ])
        self.candidates_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.candidates_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.candidates_table, stretch=1)

        apply_row = QHBoxLayout()
        self.apply_candidates_btn = QPushButton(tr("audiobook_dialog.apply_candidates_button"))
        self.apply_candidates_btn.setEnabled(False)
        self.apply_candidates_btn.clicked.connect(self._on_apply_candidates_clicked)
        apply_row.addWidget(self.apply_candidates_btn)
        apply_row.addStretch(1)
        layout.addLayout(apply_row)

        return tab

    def _load_chapters(self) -> None:
        try:
            rows = self.api.list_chapters(self.media_id)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.load_chapters_failed", error=exc))
            return
        self.chapters_table.setRowCount(len(rows))
        self._chapter_ids: list[int] = []
        for row_idx, row in enumerate(rows):
            self._chapter_ids.append(row["id"])
            values = [
                str(row["index"]), row.get("title") or "",
                _format_ms(row["start_ms"]), _format_ms(row.get("end_ms")),
            ]
            for col, value in enumerate(values):
                self.chapters_table.setItem(row_idx, col, QTableWidgetItem(value))

    def _on_detect_clicked(self) -> None:
        try:
            result = self.api.detect_chapters_preview(self.media_id)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.detect_failed", error=exc))
            return
        self._pending_candidates = result["candidates"]
        self._pending_action = "detect"
        self._render_candidates()

    def _on_generate_preview_clicked(self) -> None:
        try:
            result = self.api.generate_chapters_preview(
                self.media_id, interval_minutes=self.interval_spin.value()
            )
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.generate_failed", error=exc))
            return
        self._pending_candidates = result["candidates"]
        self._pending_action = "generate"
        self._render_candidates()

    def _render_candidates(self) -> None:
        rows = self._pending_candidates
        self.candidates_table.setRowCount(len(rows))
        for row_idx, c in enumerate(rows):
            values = [
                c.get("title") or "",
                _format_ms(int(c["start_seconds"] * 1000)),
                _format_ms(int(c["end_seconds"] * 1000)) if c.get("end_seconds") is not None else "",
            ]
            for col, value in enumerate(values):
                self.candidates_table.setItem(row_idx, col, QTableWidgetItem(value))
        self.apply_candidates_btn.setEnabled(bool(rows))

    def _on_apply_candidates_clicked(self) -> None:
        if not self._pending_candidates or self._pending_action is None:
            return
        confirm = QMessageBox.question(
            self,
            tr("audiobook_dialog.confirm_chapters_title"),
            tr("audiobook_dialog.confirm_chapters_text", count=len(self._pending_candidates)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            if self._pending_action == "detect":
                self.api.detect_chapters_apply(self.media_id, confirm=True)
            else:
                self.api.generate_chapters_apply(
                    self.media_id, interval_minutes=self.interval_spin.value(), confirm=True
                )
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.apply_chapters_failed", error=exc))
            return
        self.changed = True
        self._load_chapters()
        QMessageBox.information(
            self, tr("audiobook_dialog.applied_title"), tr("audiobook_dialog.chapters_applied_text")
        )

    def _on_rename_chapter_clicked(self) -> None:
        rows = self.chapters_table.selectionModel().selectedRows()
        if not rows:
            return
        chapter_id = self._chapter_ids[rows[0].row()]
        current_title = self.chapters_table.item(rows[0].row(), 1).text()
        new_title, ok = QInputDialog.getText(
            self, tr("audiobook_dialog.rename_chapter_title"),
            tr("audiobook_dialog.rename_chapter_prompt"), text=current_title,
        )
        if not ok or not new_title:
            return
        confirm = QMessageBox.question(
            self,
            tr("audiobook_dialog.confirm_rename_title"),
            tr("audiobook_dialog.confirm_rename_text", title=new_title),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.api.rename_chapter(self.media_id, chapter_id, title=new_title, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.rename_failed", error=exc))
            return
        self.changed = True
        self._load_chapters()

    def _on_export_clicked(self, fmt: str) -> None:
        suffix = "json" if fmt == "json" else "csv"
        filter_str = (
            tr("audiobook_dialog.export_filter_json")
            if fmt == "json" else tr("audiobook_dialog.export_filter_csv")
        )
        path, _ = QFileDialog.getSaveFileName(
            self, tr("audiobook_dialog.export_dialog_title"), f"chapters.{suffix}", filter_str,
        )
        if not path:
            return
        try:
            content = self.api.export_chapters_text(self.media_id, fmt=fmt)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("audiobook_dialog.export_failed", error=exc))
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        except OSError as exc:
            QMessageBox.critical(
                self, tr("common.error_title"), tr("audiobook_dialog.export_write_failed", error=exc)
            )
            return
        QMessageBox.information(
            self, tr("audiobook_dialog.export_done_title"),
            tr("audiobook_dialog.export_done_text", path=path),
        )
