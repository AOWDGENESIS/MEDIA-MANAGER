"""Medien-Tabellenansicht mit Detailbereich (Originalauftrag §8/§59)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.ai_dialog import AIDialog
from genesis_ui.dialogs.artwork_dialog import ArtworkDialog
from genesis_ui.dialogs.audiobook_dialog import AudiobookDialog
from genesis_ui.dialogs.convert_dialog import ConvertDialog
from genesis_ui.dialogs.cutter_dialog import CutterDialog
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.dialogs.loudness_dialog import LoudnessDialog
from genesis_ui.dialogs.metadata_dialog import MetadataSuggestionsDialog
from genesis_ui.dialogs.rename_dialog import RenamePreviewDialog
from genesis_ui.dialogs.search_filters_dialog import (
    SearchFiltersDialog,
    count_active_filters,
)
from genesis_ui.widgets.player_bar import PlayerBarWidget

#: Maximale Kantenlaenge (Pixel) fuer das Cover-Vorschaubild im Detailbereich
#: (Gap-Analyse D, §8/§22/§59 "COVER"). Bewusst klein gehalten - dies ist
#: eine Vorschau, kein Vollbild-Betrachter.
_COVER_PREVIEW_SIZE = 220


def pixmap_from_artwork_bytes(data: bytes) -> QPixmap | None:
    """Wandelt rohe Bild-Bytes (von `GET /media/{id}/artwork`) in ein auf
    `_COVER_PREVIEW_SIZE` skaliertes `QPixmap` um. Liefert `None`, wenn die
    Bytes kein von Qt decodierbares Bildformat enthalten (z.B. beschaedigte
    Artwork-Datei) - dann zeigt die UI stattdessen den "kein Cover"-Platzhalter
    an, STATT mit einem leeren/kaputten Bild abzustuerzen oder etwas zu
    erfinden (Grundprinzip: keine erfundenen Informationen).
    Als eigene, reine Funktion ausgelagert, damit sie ohne laufende
    `MediaTableView`-Instanz isoliert testbar ist."""
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        return None
    return pixmap.scaled(
        _COVER_PREVIEW_SIZE, _COVER_PREVIEW_SIZE,
        Qt.KeepAspectRatio, Qt.SmoothTransformation,
    )


def open_path_in_os(path: str, *, reveal_containing_folder: bool) -> bool:
    """Oeffnet eine Datei bzw. deren Ordner mit der Standardanwendung des
    Betriebssystems (§8/§61 "Datei oeffnen"/"Ordner oeffnen", Gap-Analyse E).

    Rein lesend/anzeigend - veraendert und loescht nichts (Grundprinzip #4/
    #5), daher ohne Bestaetigungsdialog nutzbar. Nutzt `QDesktopServices`
    (plattformunabhaengig, in Qt selbst enthalten - keine zusaetzliche
    Abhaengigkeit) statt eines Windows-spezifischen `os.startfile`, damit
    dieselbe Funktion unveraendert auch in der Linux-Sandbox waehrend der
    Entwicklung/bei Tests funktioniert.
    Liefert `True`/`False` statt zu werfen, da ein fehlgeschlagenes Oeffnen
    (z.B. keine registrierte Standardanwendung) kein Fehler des Programms
    selbst ist, sondern lediglich dem Nutzer gemeldet werden muss."""
    target = Path(path)
    location = target.parent if reveal_containing_folder else target
    if not location.exists():
        return False
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(location))))


def copy_path_to_clipboard(path: str) -> None:
    """Kopiert den vollstaendigen physischen Dateipfad in die
    Zwischenablage (§8 "Pfad kopieren", Gap-Analyse E)."""
    QApplication.clipboard().setText(path)
from genesis_ui.dialogs.video_dialog import VideoDialog
from genesis_ui.i18n import tr


def _columns() -> list[str]:
    return [
        tr("media_table.column_title"), tr("media_table.column_kind"),
        tr("media_table.column_format"), tr("media_table.column_size"),
        tr("media_table.column_path"),
    ]


class MediaTableView(QWidget):
    def __init__(self, api: GenesisAPIClient, kind: str | None, title: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.kind = kind

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(title)
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(tr("media_table.search_placeholder"))
        self.search_box.returnPressed.connect(self.refresh)
        search_btn = QPushButton(tr("media_table.search_button"))
        search_btn.clicked.connect(self.refresh)
        search_row.addWidget(self.search_box)
        search_row.addWidget(search_btn)
        # §9 (Gap-Analyse C) - erweiterte Such-/Filterfelder (Genre, Quelle,
        # Person, Serie, Format, Groesse, Dauer, Lautheit, KI-Status,
        # Qualitaetsverdacht, fehlende Metadaten/Cover, Duplikate), die der
        # einfache Freitext-Suchschlitz allein nicht abdecken kann.
        self.filters_btn = QPushButton(tr("media_table.filters_button"))
        self.filters_btn.clicked.connect(self._on_filters_clicked)
        search_row.addWidget(self.filters_btn)
        self.filters_active_label = QLabel("")
        search_row.addWidget(self.filters_active_label)
        root.addLayout(search_row)

        self._active_filters: dict = {}

        action_row = QHBoxLayout()
        # §60 (Gap-Analyse G) - einfacher, in die Bibliothek eingebauter
        # Player statt nur werkzeuggebundener Vorschauen (Cutter/Voice
        # Studio). Fuer jede einzeln ausgewaehlte, lokal vorhandene Datei
        # nutzbar - rein wiedergebend, veraendert nichts (Prinzip #4/#5).
        self.play_btn = QPushButton(tr("media_table.play_button"))
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._on_play_clicked)
        self.metadata_btn = QPushButton(tr("media_table.metadata_button"))
        self.metadata_btn.setEnabled(False)
        self.metadata_btn.clicked.connect(self._on_metadata_suggestions_clicked)
        self.rename_btn = QPushButton(tr("media_table.rename_button"))
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(self._on_rename_clicked)
        self.artwork_btn = QPushButton(tr("media_table.artwork_button"))
        self.artwork_btn.setEnabled(False)
        self.artwork_btn.clicked.connect(self._on_artwork_clicked)
        self.loudness_btn = QPushButton(tr("media_table.loudness_button"))
        self.loudness_btn.setEnabled(False)
        self.loudness_btn.clicked.connect(self._on_loudness_clicked)
        self.cutter_btn = QPushButton(tr("media_table.cutter_button"))
        self.cutter_btn.setEnabled(False)
        self.cutter_btn.clicked.connect(self._on_cutter_clicked)
        self.convert_btn = QPushButton(tr("media_table.convert_button"))
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self._on_convert_clicked)
        self.fingerprint_btn = QPushButton(tr("media_table.fingerprint_button"))
        self.fingerprint_btn.setEnabled(False)
        self.fingerprint_btn.clicked.connect(self._on_fingerprint_clicked)
        self.quality_btn = QPushButton(tr("media_table.quality_button"))
        self.quality_btn.setEnabled(False)
        self.quality_btn.clicked.connect(self._on_quality_clicked)
        # §23 - nur sinnvoll fuer Medien der Art "audiobook" (siehe
        # _on_selection_changed, dort wird die Sichtbarkeit anhand der
        # tatsaechlichen MediaKind des ausgewaehlten Mediums gesteuert).
        self.audiobook_btn = QPushButton(tr("media_table.audiobook_button"))
        self.audiobook_btn.setEnabled(False)
        self.audiobook_btn.clicked.connect(self._on_audiobook_clicked)
        # §24 - nur sinnvoll fuer Medien der Art "movie"/"episode" (siehe
        # _on_selection_changed).
        self.video_btn = QPushButton(tr("media_table.video_button"))
        self.video_btn.setEnabled(False)
        self.video_btn.clicked.connect(self._on_video_clicked)
        # §25/§27 - fuer jede einzeln ausgewaehlte Datei nutzbar (KI-
        # Vorschlaege sind medienartunabhaengig); der KI-Musik-Tab im
        # Dialog selbst blendet sich fuer nicht-musikalische Medien aus.
        self.ai_btn = QPushButton(tr("media_table.ai_button"))
        self.ai_btn.setEnabled(False)
        self.ai_btn.clicked.connect(self._on_ai_clicked)
        action_row.addWidget(self.play_btn)
        action_row.addWidget(self.metadata_btn)
        action_row.addWidget(self.rename_btn)
        action_row.addWidget(self.artwork_btn)
        action_row.addWidget(self.loudness_btn)
        action_row.addWidget(self.cutter_btn)
        action_row.addWidget(self.convert_btn)
        action_row.addWidget(self.fingerprint_btn)
        action_row.addWidget(self.quality_btn)
        action_row.addWidget(self.audiobook_btn)
        action_row.addWidget(self.video_btn)
        action_row.addWidget(self.ai_btn)
        # §8/§61 - Datei/Ordner oeffnen + Pfad kopieren (Gap-Analyse E).
        # Rein anzeigende, nie veraendernde Aktionen - daher bewusst ohne
        # Bestaetigungsdialog (Grundprinzip #4/#5/§44).
        self.open_file_btn = QPushButton(tr("media_table.open_file_button"))
        self.open_file_btn.setEnabled(False)
        self.open_file_btn.clicked.connect(self._on_open_file_clicked)
        self.open_folder_btn = QPushButton(tr("media_table.open_folder_button"))
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._on_open_folder_clicked)
        self.copy_path_btn = QPushButton(tr("media_table.copy_path_button"))
        self.copy_path_btn.setEnabled(False)
        self.copy_path_btn.clicked.connect(self._on_copy_path_clicked)
        action_row.addWidget(self.open_file_btn)
        action_row.addWidget(self.open_folder_btn)
        action_row.addWidget(self.copy_path_btn)
        action_row.addStretch(1)
        root.addLayout(action_row)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, stretch=1)

        columns = _columns()
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        # §61 (Gap-Analyse Gap H) - die im Original-Auftrag als
        # Rechtsklick-Kontextmenue beschriebenen globalen Aktionen standen
        # bisher NUR als auswahlabhaengige Werkzeugleisten-Buttons zur
        # Verfuegung. Das Kontextmenue ergaenzt (nicht ersetzt) die Toolbar -
        # beide bedienen dieselben, bereits vorhandenen `_on_..._clicked`-
        # Handler, es gibt also keine zweite Implementierung derselben
        # Aktion.
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        splitter.addWidget(self.table)

        # §8/§59 - "COVER" ist laut Spezifikation der ERSTE Bestandteil der
        # Detailansicht (Gap-Analyse D: vorher wurde Artwork nirgends in der
        # UI tatsaechlich angezeigt, nur bearbeitet). Eigenes Widget mit
        # vertikalem Layout statt direkt den QTextEdit in den Splitter zu
        # haengen, damit Cover + Textdetails zusammen scrollen/sich anpassen.
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        self.cover_label = QLabel(tr("media_table.detail.no_cover"))
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setFixedHeight(_COVER_PREVIEW_SIZE)
        self.cover_label.setObjectName("CoverPreview")
        detail_layout.addWidget(self.cover_label)

        self.detail_panel = QTextEdit()
        self.detail_panel.setReadOnly(True)
        self.detail_panel.setPlaceholderText(tr("media_table.detail_placeholder"))
        detail_layout.addWidget(self.detail_panel, stretch=1)

        splitter.addWidget(detail_container)
        splitter.setSizes([700, 400])

        # §60 (Gap-Analyse G) - persistente Wiedergabeleiste UNTER dem
        # Splitter, bleibt beim Wechsel der Auswahl/beim Neuladen sichtbar
        # (echter Bibliotheksplayer statt eines Wegwerf-Dialogs).
        self.player_bar = PlayerBarWidget()
        root.addWidget(self.player_bar)

        self._media_ids: list[int] = []
        self._media_kinds: list[str] = []
        self.refresh()

    def refresh(self) -> None:
        # Eine neu geladene Trefferliste kann die gerade spielende Datei
        # enthalten oder auch nicht (z.B. nach einer Suche) - in beiden
        # Faellen ist "weiterhin unsichtbar im Hintergrund spielen" das
        # ueberraschendere Verhalten, daher wird die Wiedergabe hier
        # bewusst beendet statt sie stillschweigend weiterlaufen zu lassen.
        if hasattr(self, "player_bar"):
            self.player_bar.stop_and_clear()
        try:
            data = self.api.list_media(
                kind=self.kind,
                search=self.search_box.text() or None,
                limit=500,
                **self._active_filters,
            )
        except GenesisAPIError as exc:
            self.detail_panel.setPlainText(tr("media_table.error_api", error=exc))
            return

        items = data["items"]
        self._media_ids = [item["id"] for item in items]
        self._media_kinds = [item["kind"] for item in items]
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            size_kb = item["size_bytes"] / 1024
            values = [
                item["filename"],
                item["kind"],
                item["extension"].lstrip("."),
                tr("media_table.size_kb", value=f"{size_kb:,.1f}".replace(",", ".")),
                item["absolute_path"],
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def _selected_media_ids(self) -> list[int]:
        rows = self.table.selectionModel().selectedRows()
        return [self._media_ids[r.row()] for r in rows]

    def _on_table_context_menu(self, pos) -> None:
        """§61 (Gap-Analyse Gap H) - Rechtsklick-Kontextmenue mit denselben
        Aktionen wie die Werkzeugleiste. Ein Rechtsklick auf eine noch
        nicht ausgewaehlte Zeile waehlt zuerst nur diese Zeile aus (uebliches
        Dateimanager-Verhalten); ein Rechtsklick innerhalb einer bereits
        bestehenden Mehrfachauswahl laesst diese unangetastet, damit
        Sammelaktionen (z.B. Umbenennen) weiter ueber die gesamte Auswahl
        wirken."""
        item = self.table.itemAt(pos)
        if item is not None:
            row = item.row()
            selected_rows = {index.row() for index in self.table.selectionModel().selectedRows()}
            if row not in selected_rows:
                self.table.selectRow(row)

        menu = self._build_context_menu()
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _build_context_menu(self) -> QMenu:
        """Ausgelagert aus `_on_table_context_menu()`, damit Tests den
        Menueinhalt (Beschriftungen, Aktivierungszustand) pruefen koennen,
        ohne den tatsaechlichen modalen `QMenu.exec()`-Aufruf (der in der
        Offscreen-Sandbox blockieren kann) ausloesen zu muessen."""
        menu = QMenu(self)
        entries = [
            (self.play_btn, self._on_play_clicked),
            (self.metadata_btn, self._on_metadata_suggestions_clicked),
            (self.rename_btn, self._on_rename_clicked),
            (self.artwork_btn, self._on_artwork_clicked),
            (self.loudness_btn, self._on_loudness_clicked),
            (self.cutter_btn, self._on_cutter_clicked),
            (self.convert_btn, self._on_convert_clicked),
            (self.fingerprint_btn, self._on_fingerprint_clicked),
            (self.quality_btn, self._on_quality_clicked),
            (self.audiobook_btn, self._on_audiobook_clicked),
            (self.video_btn, self._on_video_clicked),
            (self.ai_btn, self._on_ai_clicked),
            (self.open_file_btn, self._on_open_file_clicked),
            (self.open_folder_btn, self._on_open_folder_clicked),
            (self.copy_path_btn, self._on_copy_path_clicked),
        ]
        for button, handler in entries:
            action = menu.addAction(button.text())
            action.setEnabled(button.isEnabled())
            action.triggered.connect(handler)
        return menu

    def _on_filters_clicked(self) -> None:
        """§9 (Gap-Analyse Gap C) - oeffnet den Dialog fuer erweiterte
        Suchfilter, vorbelegt mit den aktuell aktiven Filtern, und loest
        bei Bestaetigung sofort ein `refresh()` mit den neuen Filtern aus."""
        dialog = SearchFiltersDialog(self._active_filters, self)
        if dialog.exec():
            self._active_filters = dialog.get_filters()
            self._update_filters_active_label()
            self.refresh()

    def _update_filters_active_label(self) -> None:
        count = count_active_filters(self._active_filters)
        if count:
            self.filters_active_label.setText(
                tr("media_table.filters_active_label", count=count)
            )
        else:
            self.filters_active_label.setText("")

    def _on_play_clicked(self) -> None:
        """§60 (Gap-Analyse G) - startet die eingebettete Wiedergabeleiste
        fuer die aktuell einzeln ausgewaehlte Datei. Bewusst ein expliziter
        Button-Klick statt Autoplay beim Auswaehlen einer Tabellenzeile."""
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        absolute_path = self.table.item(rows[0].row(), 4).text()
        kind = self._media_kinds[rows[0].row()]
        self.player_bar.load_and_play(absolute_path, filename, kind)

    def _on_metadata_suggestions_clicked(self) -> None:
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        dialog = MetadataSuggestionsDialog(self.api, selected[0], filename, self)
        dialog.exec()
        if dialog.applied:
            self._on_selection_changed()

    def _on_rename_clicked(self) -> None:
        selected = self._selected_media_ids()
        if not selected:
            return
        dialog = RenamePreviewDialog(self.api, selected, self)
        if dialog.exec():
            self.refresh()

    def _on_artwork_clicked(self) -> None:
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        dialog = ArtworkDialog(self.api, selected[0], filename, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_loudness_clicked(self) -> None:
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        dialog = LoudnessDialog(self.api, selected[0], filename, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_cutter_clicked(self) -> None:
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        absolute_path = self.table.item(rows[0].row(), 4).text()
        dialog = CutterDialog(self.api, selected[0], filename, absolute_path, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_convert_clicked(self) -> None:
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        dialog = ConvertDialog(self.api, selected[0], filename, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_fingerprint_clicked(self) -> None:
        """Berechnet und speichert den Chromaprint-Fingerabdruck (Analyse,
        kein `confirm` noetig - veraendert keine Mediendatei). Vorstufe fuer
        die Duplikaterkennung (§21, nav.duplicates)."""
        selected = self._selected_media_ids()
        if not selected:
            return
        try:
            result = self.api.compute_fingerprint(selected[0])
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("media_table.fingerprint_failed", error=exc))
            return
        QMessageBox.information(
            self, tr("media_table.fingerprint_done_title"),
            tr("media_table.fingerprint_done_text", duration=f"{result['duration_seconds']:.1f}"),
        )

    def _on_quality_clicked(self) -> None:
        """Reine Analyse (kein `confirm` noetig) - Ergebnis ist IMMER ein
        Verdacht, niemals ein Fakt (§20). Aktualisiert anschließend die
        Detailansicht, damit der neue Befund sofort sichtbar ist."""
        selected = self._selected_media_ids()
        if not selected:
            return
        try:
            self.api.analyze_quality(selected[0])
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("media_table.quality_failed", error=exc))
            return
        QMessageBox.information(
            self, tr("media_table.quality_done_title"), tr("media_table.quality_done_text")
        )
        self._on_selection_changed()

    def _on_audiobook_clicked(self) -> None:
        """§23 - öffnet den Hörbuch-/Kapitel-Dialog (nur für Medien der Art
        "audiobook", siehe Sichtbarkeitslogik in `_on_selection_changed`)."""
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        dialog = AudiobookDialog(self.api, selected[0], filename, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_video_clicked(self) -> None:
        """§24 - öffnet den Film-/Serien-Dialog (nur für Medien der Art
        "movie"/"episode", siehe Sichtbarkeitslogik in
        `_on_selection_changed`)."""
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        dialog = VideoDialog(self.api, selected[0], filename, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_ai_clicked(self) -> None:
        """§25/§27 - öffnet den KI-Dialog (Vorschläge + ggf. KI-Musik-Tab)."""
        selected = self._selected_media_ids()
        if not selected:
            return
        rows = self.table.selectionModel().selectedRows()
        filename = self.table.item(rows[0].row(), 0).text()
        kind = self._media_kinds[rows[0].row()]
        dialog = AIDialog(self.api, selected[0], filename, kind, self)
        dialog.exec()
        if dialog.changed:
            self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        self.play_btn.setEnabled(len(rows) == 1)
        self.rename_btn.setEnabled(bool(rows))
        self.metadata_btn.setEnabled(len(rows) == 1)
        self.artwork_btn.setEnabled(len(rows) == 1)
        self.loudness_btn.setEnabled(len(rows) == 1)
        self.cutter_btn.setEnabled(len(rows) == 1)
        self.convert_btn.setEnabled(len(rows) == 1)
        self.fingerprint_btn.setEnabled(len(rows) == 1)
        self.quality_btn.setEnabled(len(rows) == 1)
        is_single_audiobook = (
            len(rows) == 1 and self._media_kinds[rows[0].row()] == "audiobook"
        )
        self.audiobook_btn.setEnabled(is_single_audiobook)
        is_single_video = (
            len(rows) == 1 and self._media_kinds[rows[0].row()] in ("movie", "episode")
        )
        self.video_btn.setEnabled(is_single_video)
        self.ai_btn.setEnabled(len(rows) == 1)
        self.open_file_btn.setEnabled(len(rows) == 1)
        self.open_folder_btn.setEnabled(len(rows) == 1)
        self.copy_path_btn.setEnabled(len(rows) == 1)
        if not rows:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText(tr("media_table.detail.no_cover"))
            return
        media_id = self._media_ids[rows[0].row()]
        self._refresh_cover(media_id)
        try:
            detail = self.api.media_detail(media_id)
        except GenesisAPIError as exc:
            self.detail_panel.setPlainText(tr("media_table.error_detail", error=exc))
            return

        yes = tr("common.value_yes")
        no = tr("common.value_no")
        empty = tr("common.value_empty")
        d = "media_table.detail"
        exists_text = yes if detail["file_exists_on_disk"] else tr(f"{d}.exists_no")
        lines = [
            tr(f"{d}.path_header"),
            f"  {detail['absolute_path']}",
            tr(f"{d}.exists_on_disk", status=exists_text),
            "",
            tr(f"{d}.filename", value=detail["filename"]),
            tr(f"{d}.directory", value=detail["directory"]),
            tr(f"{d}.size", value=f"{detail['size_bytes']:,}".replace(",", ".")),
            tr(f"{d}.format", value=detail["extension"]),
            tr(f"{d}.modified", value=detail["mtime"]),
            tr(f"{d}.sha256", value=detail["content_hash_sha256"]),
            "",
        ]
        if detail.get("technical"):
            t = detail["technical"]
            lines.append(tr(f"{d}.technical_header"))
            for key, value in t.items():
                if value is not None:
                    lines.append(f"  {key}: {value}")
            lines.append("")

        try:
            quality = self.api.get_quality(media_id)
        except GenesisAPIError:
            quality = None
        if quality is not None:
            lines.append(tr(f"{d}.quality_header"))
            flags = [
                (tr(f"{d}.quality_flag_upscale"), quality["suspected_upscale"]),
                (tr(f"{d}.quality_flag_transcode"), quality["suspected_transcode"]),
                (tr(f"{d}.quality_flag_corruption"), quality["suspected_corruption"]),
                (tr(f"{d}.quality_flag_truncation"), quality["suspected_truncation"]),
            ]
            for label, flagged in flags:
                lines.append(f"  {label}: {yes if flagged else no}")
            for note in quality["notes"]:
                lines.append(f"  - {note}")
            lines.append("")

        track = detail.get("track")
        if track:
            confirmed = (
                tr(f"{d}.confirmed_yes") if track.get("is_user_confirmed")
                else tr(f"{d}.confirmed_no")
            )
            lines.append(tr(f"{d}.metadata_header"))
            lines.append(tr(f"{d}.title", value=track.get("title") or empty))
            lines.append(
                tr(
                    f"{d}.track_disc",
                    track=track.get("track_number") or empty,
                    disc=track.get("disc_number") or empty,
                )
            )
            lines.append(tr(f"{d}.year", value=track.get("year") or empty))
            lines.append(tr(f"{d}.source", value=track.get("source") or empty))
            lines.append(tr(f"{d}.confidence", value=track.get("confidence")))
            lines.append(tr(f"{d}.user_confirmed", value=confirmed))
        else:
            lines.append(tr(f"{d}.metadata_none"))
        lines.append("")
        embedded = yes if detail.get("has_embedded_artwork") else no
        lines.append(tr(f"{d}.embedded_artwork", value=embedded))
        lines.append("")

        # §59 "LOUDNESS" - Gap-Analyse F: vorher nur im separaten
        # Lautheit-Dialog sichtbar, nicht in der zentralen Detailansicht.
        try:
            loudness_history = self.api.list_loudness(media_id)
        except GenesisAPIError:
            loudness_history = []
        lines.append(tr(f"{d}.loudness_header"))
        if loudness_history:
            latest = loudness_history[0]  # API liefert neueste zuerst

            def _lv(key: str) -> object:
                v = latest.get(key)
                return v if v is not None else empty

            lines.append(tr(f"{d}.loudness_integrated", value=_lv("integrated_lufs")))
            lines.append(tr(f"{d}.loudness_true_peak", value=_lv("true_peak_dbtp")))
            lines.append(tr(f"{d}.loudness_lra", value=_lv("loudness_range_lu")))
            normalized = yes if latest.get("normalized") else no
            lines.append(tr(f"{d}.loudness_normalized", value=normalized))
        else:
            lines.append(tr(f"{d}.loudness_none"))
        lines.append("")

        # §59 "KI-ANALYSE" - Gap-Analyse F: KI-Vorschlaege IMMER mit Modell/
        # Version/Zeitstempel/Confidence (§25), nie ohne diese Herkunft.
        try:
            ai_entries = self.api.get_ai_metadata(media_id)
        except GenesisAPIError:
            ai_entries = []
        lines.append(tr(f"{d}.ai_header"))
        if ai_entries:
            for entry in ai_entries:
                accepted = yes if entry.get("accepted_by_user") else no
                lines.append(
                    tr(
                        f"{d}.ai_entry",
                        field=entry.get("field_name"),
                        value=entry.get("field_value"),
                        model=entry.get("model_name") or empty,
                        confidence=entry.get("confidence"),
                        accepted=accepted,
                    )
                )
        else:
            lines.append(tr(f"{d}.ai_none"))
        lines.append("")

        # §59/§32 "QUELLE" - Herkunft eines importierten Mediums.
        try:
            sources = self.api.list_media_sources(media_id)
        except GenesisAPIError:
            sources = []
        lines.append(tr(f"{d}.source_header"))
        if sources:
            for src in sources:
                lines.append(
                    tr(
                        f"{d}.source_entry",
                        name=src.get("source_name") or empty,
                        provider=src.get("provider_name") or empty,
                        imported_at=src.get("imported_at") or empty,
                    )
                )
        else:
            lines.append(tr(f"{d}.source_none"))

        self.detail_panel.setPlainText("\n".join(lines))

    def _refresh_cover(self, media_id: int) -> None:
        """§8/§22/§59 "COVER" - Gap-Analyse D: zeigt das eingebettete/
        gespeicherte Artwork tatsaechlich an, statt es nur im ArtworkDialog
        bearbeitbar, aber nirgends sichtbar zu machen."""
        try:
            result = self.api.get_artwork_bytes(media_id)
        except GenesisAPIError:
            result = None
        if result is None:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText(tr("media_table.detail.no_cover"))
            return
        data, _content_type = result
        pixmap = pixmap_from_artwork_bytes(data)
        if pixmap is None:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText(tr("media_table.detail.no_cover"))
            return
        self.cover_label.setText("")
        self.cover_label.setPixmap(pixmap)

    def _selected_absolute_path(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        return self.table.item(rows[0].row(), 4).text()

    def _on_open_file_clicked(self) -> None:
        """§8/§61 "Datei öffnen" (Gap-Analyse E)."""
        path = self._selected_absolute_path()
        if path is None:
            return
        if not open_path_in_os(path, reveal_containing_folder=False):
            QMessageBox.warning(
                self, tr("media_table.open_file_failed_title"),
                tr("media_table.open_file_failed_text", path=path),
            )

    def _on_open_folder_clicked(self) -> None:
        """§8/§61 "Ordner öffnen" (Gap-Analyse E)."""
        path = self._selected_absolute_path()
        if path is None:
            return
        if not open_path_in_os(path, reveal_containing_folder=True):
            QMessageBox.warning(
                self, tr("media_table.open_folder_failed_title"),
                tr("media_table.open_folder_failed_text", path=path),
            )

    def _on_copy_path_clicked(self) -> None:
        """§8/§61 "Pfad kopieren" (Gap-Analyse E)."""
        path = self._selected_absolute_path()
        if path is None:
            return
        copy_path_to_clipboard(path)
        window = self.window()
        # In Tests/isoliertem Einsatz hat `window()` ggf. kein `statusBar()`
        # (nur echte `QMainWindow`-Instanzen haben eines) - dann wird die
        # Rueckmeldung einfach ausgelassen, statt mit `AttributeError`
        # abzustuerzen (die Zwischenablage ist trotzdem schon gesetzt).
        if window is not None and hasattr(window, "statusBar"):
            window.statusBar().showMessage(tr("media_table.path_copied_status", path=path), 5000)
