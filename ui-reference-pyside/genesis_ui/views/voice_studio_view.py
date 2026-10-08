"""Voice Studio (§28/§29, Phase 7, ADR-0018).

Eigenstaendige Navigationsseite (analog zu `AICenterView`/`DuplicatesView`) -
Stimmprofile sind nicht an eine einzelne Mediendatei gebunden, sondern eine
projektweite Ressource. Zwei Tabs:

1. "Profile": Verwaltung von Voice-Profilen. Jede Zeile zeigt die vier
   Pflichtangaben aus §28 unmittelbar sichtbar an (Engine, Modell-Lizenz,
   Offline-faehig, Open Source, kommerziell nutzbar) - niemals versteckt
   hinter einem weiteren Klick. Anlegen/Loeschen sind Aenderungen und
   erfordern eine explizite Bestaetigung (Loeschen zusaetzlich die exakte
   Wiederholung des Profilnamens, §28/Prinzip #6 "Loeschen = extra
   confirm").
2. "Text-zu-Sprache": Auswahl eines Profils, Texteingabe, Export als
   WAV/MP3/FLAC, Wiedergabe über die lokale Mediendatei (dieselbe
   QtMultimedia-Technik wie im Audio-Cutter) sowie eine Historie
   vergangener Syntheseergebnisse.

Keine Sprachdaten verlassen dabei jemals automatisch den lokalen Rechner
(§28/§56) - jede Synthese ist eine ausdruecklich bestaetigte Aktion.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text

EXPORT_FORMATS = ("wav", "mp3", "flac")


def _yes_no(value: bool | None) -> str:
    if value is True:
        return tr("common.value_yes")
    if value is False:
        return tr("common.value_no")
    return tr("voice_studio.unknown")


class VoiceStudioView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._profiles: list[dict] = []
        self._engine_catalog: list[dict] = []
        self._last_output_path: str | None = None

        # Wiedergabe der zuletzt erzeugten/ausgewaehlten Audiodatei - spielt
        # die lokale Datei direkt (analog zu CutterDialog), rein lesend.
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel(tr("voice_studio.title"))
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        self.status_banner = QLabel(tr("ai_dialog.loading"))
        self.status_banner.setWordWrap(True)
        self.status_banner.setStyleSheet("color: #9fb8d8;")
        root.addWidget(self.status_banner)

        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)
        tabs.addTab(self._build_profiles_tab(), tr("voice_studio.tab_profiles"))
        tabs.addTab(self._build_tts_tab(), tr("voice_studio.tab_tts"))

        self._load_status()
        self._load_engine_catalog()
        self._reload_profiles()

    # --- Tab 1: Profile ---------------------------------------------------

    def _build_profiles_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.profiles_tree = QTreeWidget()
        self.profiles_tree.setHeaderLabels([
            tr("voice_studio.col_name"),
            tr("voice_studio.col_engine"),
            tr("voice_studio.col_language"),
            tr("voice_studio.col_license"),
            tr("voice_studio.col_offline"),
            tr("voice_studio.col_open_source"),
            tr("voice_studio.col_commercial"),
        ])
        self.profiles_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.profiles_tree.itemSelectionChanged.connect(self._on_profile_selection_changed)
        layout.addWidget(self.profiles_tree, stretch=1)

        button_row = QHBoxLayout()
        self.new_profile_btn = QPushButton(tr("voice_studio.new_profile_button"))
        self.new_profile_btn.clicked.connect(self._toggle_new_profile_form)
        button_row.addWidget(self.new_profile_btn)
        self.delete_profile_btn = QPushButton(tr("voice_studio.delete_profile_button"))
        self.delete_profile_btn.setEnabled(False)
        self.delete_profile_btn.clicked.connect(self._on_delete_profile_clicked)
        button_row.addWidget(self.delete_profile_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.new_profile_group = self._build_new_profile_form()
        self.new_profile_group.setVisible(False)
        layout.addWidget(self.new_profile_group)

        return page

    def _build_new_profile_form(self) -> QGroupBox:
        group = QGroupBox(tr("voice_studio.new_profile_group_title"))
        form = QFormLayout(group)

        self.name_edit = QLineEdit()
        form.addRow(tr("voice_studio.field_name"), self.name_edit)

        self.engine_combo = QComboBox()
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        form.addRow(tr("voice_studio.field_engine"), self.engine_combo)

        model_path_row = QHBoxLayout()
        self.model_path_edit = QLineEdit()
        model_path_row.addWidget(self.model_path_edit, stretch=1)
        browse_model_btn = QPushButton(tr("voice_studio.browse_button"))
        browse_model_btn.clicked.connect(self._on_browse_model_path)
        model_path_row.addWidget(browse_model_btn)
        form.addRow(tr("voice_studio.field_model_path"), model_path_row)

        self.language_edit = QLineEdit()
        self.language_edit.setPlaceholderText("de / en / ja / ru ...")
        form.addRow(tr("voice_studio.field_language"), self.language_edit)

        self.description_edit = QLineEdit()
        form.addRow(tr("voice_studio.field_description"), self.description_edit)

        self.license_edit = QLineEdit()
        form.addRow(tr("voice_studio.field_model_license"), self.license_edit)

        self.offline_check = QCheckBox(tr("voice_studio.field_offline_capable"))
        self.offline_check.setChecked(True)
        form.addRow("", self.offline_check)

        self.open_source_check = QCheckBox(tr("voice_studio.field_open_source"))
        self.open_source_check.setChecked(True)
        form.addRow("", self.open_source_check)

        self.commercial_combo = QComboBox()
        self.commercial_combo.addItem(tr("voice_studio.unknown"), None)
        self.commercial_combo.addItem(tr("common.value_yes"), True)
        self.commercial_combo.addItem(tr("common.value_no"), False)
        form.addRow(tr("voice_studio.field_commercial_use"), self.commercial_combo)

        sample_row = QHBoxLayout()
        self.sample_path_edit = QLineEdit()
        sample_row.addWidget(self.sample_path_edit, stretch=1)
        browse_sample_btn = QPushButton(tr("voice_studio.browse_button"))
        browse_sample_btn.clicked.connect(self._on_browse_sample_path)
        sample_row.addWidget(browse_sample_btn)
        form.addRow(tr("voice_studio.field_sample_path"), sample_row)

        self.engine_notes_label = QLabel("")
        self.engine_notes_label.setWordWrap(True)
        self.engine_notes_label.setStyleSheet("color: #9fb8d8;")
        form.addRow("", self.engine_notes_label)

        create_btn = QPushButton(tr("voice_studio.create_button"))
        create_btn.clicked.connect(self._on_create_profile_clicked)
        form.addRow("", create_btn)

        return group

    def _build_tts_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel(tr("voice_studio.field_profile")))
        self.tts_profile_combo = QComboBox()
        self.tts_profile_combo.currentIndexChanged.connect(self._on_tts_profile_changed)
        profile_row.addWidget(self.tts_profile_combo, stretch=1)
        layout.addLayout(profile_row)

        self.profile_disclosure_label = QLabel("")
        self.profile_disclosure_label.setWordWrap(True)
        self.profile_disclosure_label.setStyleSheet("color: #9fb8d8;")
        layout.addWidget(self.profile_disclosure_label)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(tr("voice_studio.text_placeholder"))
        layout.addWidget(self.text_edit, stretch=1)

        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel(tr("voice_studio.field_export_format")))
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(EXPORT_FORMATS)
        controls_row.addWidget(self.export_format_combo)
        self.synthesize_btn = QPushButton(tr("voice_studio.synthesize_button"))
        self.synthesize_btn.clicked.connect(self._on_synthesize_clicked)
        controls_row.addWidget(self.synthesize_btn)
        self.test_btn = QPushButton(tr("voice_studio.test_button"))
        self.test_btn.clicked.connect(self._on_test_clicked)
        controls_row.addWidget(self.test_btn)
        controls_row.addStretch(1)
        layout.addLayout(controls_row)

        self.synthesis_status_label = QLabel("")
        self.synthesis_status_label.setWordWrap(True)
        layout.addWidget(self.synthesis_status_label)

        playback_row = QHBoxLayout()
        self.play_btn = QPushButton(tr("voice_studio.play_button"))
        self.play_btn.clicked.connect(self._on_play_clicked)
        self.play_btn.setEnabled(False)
        playback_row.addWidget(self.play_btn)
        self.pause_btn = QPushButton(tr("voice_studio.pause_button"))
        self.pause_btn.clicked.connect(self._player.pause)
        playback_row.addWidget(self.pause_btn)
        playback_row.addStretch(1)
        layout.addLayout(playback_row)

        layout.addWidget(QLabel(tr("voice_studio.history_title")))
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels([
            tr("voice_studio.col_created_at"),
            tr("voice_studio.col_text"),
            tr("voice_studio.col_format"),
            tr("voice_studio.col_duration"),
        ])
        self.history_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.history_tree.itemSelectionChanged.connect(self._on_history_selection_changed)
        layout.addWidget(self.history_tree, stretch=1)

        return page

    # --- Laden/Status -------------------------------------------------------

    def _load_status(self) -> None:
        try:
            status = self.api.get_voice_status()
        except GenesisAPIError as exc:
            set_plain_text(self.status_banner, tr("ai_dialog.status_load_failed", error=exc))
            return
        if not status.get("enabled"):
            self.status_banner.setText(tr("voice_studio.status_disabled"))
        elif not status.get("available"):
            set_plain_text(
                self.status_banner,
                tr("voice_studio.status_unavailable", provider=status.get("provider")),
            )
        else:
            set_plain_text(
                self.status_banner,
                tr(
                    "voice_studio.status_active",
                    provider=status.get("provider"),
                ),
            )

    def _load_engine_catalog(self) -> None:
        try:
            self._engine_catalog = self.api.get_voice_engines()
        except GenesisAPIError:
            self._engine_catalog = []
        self.engine_combo.clear()
        for entry in self._engine_catalog:
            self.engine_combo.addItem(entry["label"], entry["id"])
        self._on_engine_changed()

    def _on_engine_changed(self) -> None:
        idx = self.engine_combo.currentIndex()
        if idx < 0 or idx >= len(self._engine_catalog):
            self.engine_notes_label.setText("")
            return
        entry = self._engine_catalog[idx]
        set_plain_text(
            self.engine_notes_label,
            tr(
                "voice_studio.engine_notes",
                license=entry["suggested_engine_license"],
                notes=entry["notes"],
            ),
        )

    def _reload_profiles(self) -> None:
        try:
            self._profiles = self.api.list_voice_profiles()
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("voice_studio.load_profiles_failed", error=exc))
            self._profiles = []

        self.profiles_tree.clear()
        for p in self._profiles:
            item = QTreeWidgetItem([
                p["name"], p["engine"], p.get("language") or "-",
                p.get("model_license") or "-",
                _yes_no(p.get("offline_capable")),
                _yes_no(p.get("open_source")),
                _yes_no(p.get("commercial_use_allowed")),
            ])
            item.setData(0, 1000, p["id"])
            self.profiles_tree.addTopLevelItem(item)

        current_tts_id = self.tts_profile_combo.currentData()
        self.tts_profile_combo.blockSignals(True)
        self.tts_profile_combo.clear()
        for p in self._profiles:
            self.tts_profile_combo.addItem(p["name"], p["id"])
        restored = False
        if current_tts_id is not None:
            for i in range(self.tts_profile_combo.count()):
                if self.tts_profile_combo.itemData(i) == current_tts_id:
                    self.tts_profile_combo.setCurrentIndex(i)
                    restored = True
                    break
        self.tts_profile_combo.blockSignals(False)
        self._on_tts_profile_changed()
        if not restored:
            pass

    # --- Profile anlegen/loeschen ------------------------------------------

    def _toggle_new_profile_form(self) -> None:
        self.new_profile_group.setVisible(not self.new_profile_group.isVisible())

    def _on_browse_model_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("voice_studio.browse_model_title"), "", "*"
        )
        if path:
            self.model_path_edit.setText(path)

    def _on_browse_sample_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("voice_studio.browse_sample_title"), "", "*"
        )
        if path:
            self.sample_path_edit.setText(path)

    def _on_create_profile_clicked(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, tr("common.error_title"), tr("voice_studio.name_required")
            )
            return
        engine_id = self.engine_combo.currentData() or "piper"
        commercial = self.commercial_combo.currentData()

        confirm = QMessageBox.question(
            self,
            tr("voice_studio.confirm_create_title"),
            tr(
                "voice_studio.confirm_create_text",
                name=name,
                engine=engine_id,
                license=self.license_edit.text().strip() or tr("voice_studio.unknown"),
                offline=_yes_no(self.offline_check.isChecked()),
                open_source=_yes_no(self.open_source_check.isChecked()),
                commercial=_yes_no(commercial),
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        payload = {
            "name": name,
            "engine": engine_id,
            "model_path": self.model_path_edit.text().strip() or None,
            "language": self.language_edit.text().strip() or None,
            "description": self.description_edit.text().strip() or None,
            "model_license": self.license_edit.text().strip() or None,
            "offline_capable": self.offline_check.isChecked(),
            "open_source": self.open_source_check.isChecked(),
            "commercial_use_allowed": commercial,
            "sample_path": self.sample_path_edit.text().strip() or None,
        }
        try:
            self.api.create_voice_profile(payload, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("voice_studio.create_failed", error=exc))
            return

        self.name_edit.clear()
        self.model_path_edit.clear()
        self.language_edit.clear()
        self.description_edit.clear()
        self.license_edit.clear()
        self.sample_path_edit.clear()
        self.new_profile_group.setVisible(False)
        self._reload_profiles()

    def _on_profile_selection_changed(self) -> None:
        self.delete_profile_btn.setEnabled(bool(self.profiles_tree.selectedItems()))

    def _on_delete_profile_clicked(self) -> None:
        items = self.profiles_tree.selectedItems()
        if not items:
            return
        item = items[0]
        profile_id = item.data(0, 1000)
        profile_name = item.text(0)

        confirm = QMessageBox.question(
            self,
            tr("voice_studio.confirm_delete_title"),
            tr("voice_studio.confirm_delete_text", name=profile_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        # §28/Prinzip #6 "Loeschen = extra confirm": der Name muss exakt
        # wiederholt werden (lokale Vorab-Pruefung; der Server validiert
        # authoritativ erneut).
        typed_name, ok = QInputDialog.getText(
            self, tr("voice_studio.confirm_delete_name_title"),
            tr("voice_studio.confirm_delete_name_prompt", name=profile_name),
        )
        if not ok:
            return
        if typed_name != profile_name:
            QMessageBox.warning(
                self, tr("common.error_title"), tr("voice_studio.delete_name_mismatch")
            )
            return

        try:
            self.api.delete_voice_profile(profile_id, confirm=True, confirm_name=typed_name)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("voice_studio.delete_failed", error=exc))
            return
        self._reload_profiles()

    # --- Text-zu-Sprache ------------------------------------------------

    def _on_tts_profile_changed(self) -> None:
        profile_id = self.tts_profile_combo.currentData()
        if profile_id is None:
            self.profile_disclosure_label.setText("")
            self.history_tree.clear()
            return
        profile = next((p for p in self._profiles if p["id"] == profile_id), None)
        if profile is not None:
            set_plain_text(
                self.profile_disclosure_label,
                tr(
                    "voice_studio.profile_disclosure",
                    engine=profile["engine"],
                    license=profile.get("model_license") or tr("voice_studio.unknown"),
                    offline=_yes_no(profile.get("offline_capable")),
                    open_source=_yes_no(profile.get("open_source")),
                    commercial=_yes_no(profile.get("commercial_use_allowed")),
                ),
            )
        self._reload_history()

    def _reload_history(self) -> None:
        profile_id = self.tts_profile_combo.currentData()
        self.history_tree.clear()
        if profile_id is None:
            return
        try:
            rows = self.api.list_voice_syntheses(profile_id)
        except GenesisAPIError:
            return
        for r in rows:
            text_preview = r["text"] if len(r["text"]) <= 60 else r["text"][:57] + "..."
            duration = f"{r['duration_seconds']:.1f}s" if r.get("duration_seconds") else "-"
            item = QTreeWidgetItem([
                (r.get("created_at") or "")[:19].replace("T", " "),
                text_preview, r["export_format"], duration,
            ])
            item.setData(0, 1000, r["output_path"])
            self.history_tree.addTopLevelItem(item)

    def _on_history_selection_changed(self) -> None:
        items = self.history_tree.selectedItems()
        if not items:
            return
        self._last_output_path = items[0].data(0, 1000)
        self.play_btn.setEnabled(True)

    def _confirm_and_run_synthesis(self, text: str, *, is_test: bool) -> None:
        profile_id = self.tts_profile_combo.currentData()
        if profile_id is None:
            QMessageBox.warning(
                self, tr("common.error_title"), tr("voice_studio.no_profile_selected")
            )
            return
        confirm = QMessageBox.question(
            self,
            tr("voice_studio.confirm_synthesize_title"),
            tr("voice_studio.confirm_synthesize_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self.synthesis_status_label.setText(tr("voice_studio.synthesizing"))
        try:
            if is_test:
                result = self.api.test_voice_profile(profile_id, confirm=True)
            else:
                export_format = self.export_format_combo.currentText()
                result = self.api.synthesize_voice(
                    profile_id, text, export_format=export_format, confirm=True
                )
        except GenesisAPIError as exc:
            set_plain_text(
                self.synthesis_status_label,
                tr("voice_studio.synthesize_failed", error=exc),
            )
            return

        synthesis = result["synthesis"]
        self._last_output_path = synthesis["output_path"]
        self.play_btn.setEnabled(True)
        # path ist ein Dateipfad (dynamischer Inhalt) - siehe
        # genesis_ui.widgets-Moduldocstring.
        set_plain_text(
            self.synthesis_status_label,
            tr(
                "voice_studio.synthesize_done",
                duration=synthesis.get("duration_seconds") or 0.0,
                path=synthesis["output_path"],
            ),
        )
        self._reload_history()

    def _on_synthesize_clicked(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, tr("common.error_title"), tr("voice_studio.text_required")
            )
            return
        self._confirm_and_run_synthesis(text, is_test=False)

    def _on_test_clicked(self) -> None:
        self._confirm_and_run_synthesis("", is_test=True)

    def _on_play_clicked(self) -> None:
        if not self._last_output_path:
            return
        self._player.setSource(QUrl.fromLocalFile(self._last_output_path))
        self._player.play()
