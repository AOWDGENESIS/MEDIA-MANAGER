"""Einstellungen (nav.settings, §55).

Schliesst Gap A aus docs/GAP_ANALYSIS.md: GUI-basierte Konfiguration ohne
manuelles config.yaml-Editieren. Nutzt `PATCH /settings` (siehe
genesis_core/api/app.py) - jede Speicherung erfordert `confirm=true`
(Prinzip #17), da manche Felder (Cloud-KI-Freigabe, automatische
Downloads, Original-Dateien ueberschreiben) das Datenschutz-/
Sicherheitsverhalten der gesamten Anwendung aendern koennen.

Absichtlich NICHT Teil dieser Seite: die Metadaten-Provider-Verwaltung
(MusicBrainz/AcoustID/CoverArtArchive) - siehe `nav.providers` ->
`ProvidersView` (Gap I, eigene Seite wegen eigenem fachlichen Kontext).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


class SettingsView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._settings: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        header = QLabel(tr("settings_view.title"))
        header.setObjectName("SectionTitle")
        outer.addWidget(header)

        note = QLabel(tr("settings_view.intro_note"))
        note.setWordWrap(True)
        outer.addWidget(note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_host = QWidget()
        scroll.setWidget(form_host)
        form_root = QVBoxLayout(form_host)
        form_root.setSpacing(16)
        outer.addWidget(scroll, stretch=1)

        self._build_general_section(form_root)
        self._build_media_folders_section(form_root)
        self._build_ai_section(form_root)
        self._build_voice_section(form_root)
        self._build_loudness_section(form_root)
        self._build_download_section(form_root)
        self._build_privacy_section(form_root)
        form_root.addStretch(1)

        bottom_row = QHBoxLayout()
        self.save_btn = QPushButton(tr("settings_view.save_button"))
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.reload_btn = QPushButton(tr("settings_view.reload_button"))
        self.reload_btn.clicked.connect(self._reload)
        bottom_row.addWidget(self.save_btn)
        bottom_row.addWidget(self.reload_btn)
        bottom_row.addStretch(1)
        outer.addLayout(bottom_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self._reload()

    # --- Aufbau der Formularabschnitte --------------------------------------

    def _build_general_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_general"))
        form = QFormLayout(box)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["de", "en", "ja", "ru"])
        form.addRow(tr("settings_view.language_label"), self.language_combo)
        self.require_confirmation_check = QCheckBox()
        form.addRow(
            tr("settings_view.require_confirmation_label"), self.require_confirmation_check
        )
        root.addWidget(box)

    def _build_media_folders_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_media_folders"))
        layout = QVBoxLayout(box)
        note = QLabel(tr("settings_view.media_folders_note"))
        note.setWordWrap(True)
        layout.addWidget(note)

        self.folders_list = QListWidget()
        layout.addWidget(self.folders_list)

        row = QHBoxLayout()
        self.add_folder_btn = QPushButton(tr("settings_view.add_folder_button"))
        self.add_folder_btn.clicked.connect(self._on_add_folder_clicked)
        self.remove_folder_btn = QPushButton(tr("settings_view.remove_folder_button"))
        self.remove_folder_btn.clicked.connect(self._on_remove_folder_clicked)
        self.scan_btn = QPushButton(tr("settings_view.scan_button"))
        self.scan_btn.setObjectName("Primary")
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        row.addWidget(self.add_folder_btn)
        row.addWidget(self.remove_folder_btn)
        row.addWidget(self.scan_btn)
        row.addStretch(1)
        layout.addLayout(row)
        root.addWidget(box)

    def _build_ai_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_ai"))
        form = QFormLayout(box)
        self.ai_enabled_check = QCheckBox()
        form.addRow(tr("settings_view.ai_enabled_label"), self.ai_enabled_check)
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["null", "ollama"])
        form.addRow(tr("settings_view.ai_provider_label"), self.ai_provider_combo)
        self.ai_endpoint_edit = QLineEdit()
        form.addRow(tr("settings_view.ai_endpoint_label"), self.ai_endpoint_edit)
        self.ai_model_edit = QLineEdit()
        form.addRow(tr("settings_view.ai_model_label"), self.ai_model_edit)
        self.ai_embedding_model_edit = QLineEdit()
        form.addRow(tr("settings_view.ai_embedding_model_label"), self.ai_embedding_model_edit)
        self.ai_timeout_spin = QDoubleSpinBox()
        self.ai_timeout_spin.setRange(1.0, 600.0)
        self.ai_timeout_spin.setSuffix(" s")
        form.addRow(tr("settings_view.ai_timeout_label"), self.ai_timeout_spin)
        root.addWidget(box)

    def _build_voice_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_voice"))
        form = QFormLayout(box)
        self.voice_enabled_check = QCheckBox()
        form.addRow(tr("settings_view.voice_enabled_label"), self.voice_enabled_check)
        self.voice_provider_combo = QComboBox()
        self.voice_provider_combo.addItems(["null", "piper"])
        form.addRow(tr("settings_view.voice_provider_label"), self.voice_provider_combo)
        self.voice_export_format_combo = QComboBox()
        self.voice_export_format_combo.addItems(["wav", "mp3", "flac"])
        form.addRow(
            tr("settings_view.voice_export_format_label"), self.voice_export_format_combo
        )
        root.addWidget(box)

    def _build_loudness_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_loudness"))
        form = QFormLayout(box)
        self.loudness_target_lufs_spin = QDoubleSpinBox()
        self.loudness_target_lufs_spin.setRange(-40.0, 0.0)
        self.loudness_target_lufs_spin.setSuffix(" LUFS")
        form.addRow(
            tr("settings_view.loudness_target_lufs_label"), self.loudness_target_lufs_spin
        )
        self.loudness_target_true_peak_spin = QDoubleSpinBox()
        self.loudness_target_true_peak_spin.setRange(-10.0, 0.0)
        self.loudness_target_true_peak_spin.setSuffix(" dBTP")
        form.addRow(
            tr("settings_view.loudness_target_true_peak_label"),
            self.loudness_target_true_peak_spin,
        )
        self.loudness_overwrite_check = QCheckBox()
        form.addRow(
            tr("settings_view.loudness_overwrite_originals_label"),
            self.loudness_overwrite_check,
        )
        warning = QLabel(tr("settings_view.loudness_overwrite_warning"))
        warning.setWordWrap(True)
        form.addRow(warning)
        root.addWidget(box)

    def _build_download_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_download"))
        form = QFormLayout(box)
        self.download_enabled_check = QCheckBox()
        form.addRow(tr("settings_view.download_enabled_label"), self.download_enabled_check)
        self.download_youtube_check = QCheckBox()
        form.addRow(
            tr("settings_view.download_enable_youtube_label"), self.download_youtube_check
        )
        self.download_tiktok_check = QCheckBox()
        form.addRow(
            tr("settings_view.download_enable_tiktok_label"), self.download_tiktok_check
        )

        dir_row = QHBoxLayout()
        self.download_dir_edit = QLineEdit()
        self.download_dir_browse_btn = QPushButton(tr("settings_view.download_dir_browse_button"))
        self.download_dir_browse_btn.clicked.connect(self._on_browse_download_dir_clicked)
        dir_row.addWidget(self.download_dir_edit, stretch=1)
        dir_row.addWidget(self.download_dir_browse_btn)
        form.addRow(tr("settings_view.download_dir_label"), dir_row)

        self.download_max_size_spin = QSpinBox()
        self.download_max_size_spin.setRange(1, 1_000_000)
        self.download_max_size_spin.setSuffix(" MB")
        form.addRow(tr("settings_view.download_max_size_label"), self.download_max_size_spin)
        self.download_min_free_disk_spin = QSpinBox()
        self.download_min_free_disk_spin.setRange(0, 1_000_000)
        self.download_min_free_disk_spin.setSuffix(" MB")
        form.addRow(
            tr("settings_view.download_min_free_disk_label"), self.download_min_free_disk_spin
        )
        self.download_timeout_spin = QDoubleSpinBox()
        self.download_timeout_spin.setRange(1.0, 600.0)
        self.download_timeout_spin.setSuffix(" s")
        form.addRow(tr("settings_view.download_timeout_label"), self.download_timeout_spin)
        root.addWidget(box)

    def _build_privacy_section(self, root: QVBoxLayout) -> None:
        box = QGroupBox(tr("settings_view.section_privacy"))
        form = QFormLayout(box)
        self.privacy_telemetry_check = QCheckBox()
        form.addRow(tr("settings_view.privacy_telemetry_label"), self.privacy_telemetry_check)
        self.privacy_cloud_ai_check = QCheckBox()
        form.addRow(tr("settings_view.privacy_allow_cloud_ai_label"), self.privacy_cloud_ai_check)
        self.privacy_auto_downloads_check = QCheckBox()
        form.addRow(
            tr("settings_view.privacy_allow_auto_downloads_label"),
            self.privacy_auto_downloads_check,
        )
        self.privacy_auto_deletion_check = QCheckBox()
        form.addRow(
            tr("settings_view.privacy_allow_auto_deletion_label"),
            self.privacy_auto_deletion_check,
        )
        self.privacy_auto_overwrite_check = QCheckBox()
        form.addRow(
            tr("settings_view.privacy_allow_auto_overwrite_label"),
            self.privacy_auto_overwrite_check,
        )
        root.addWidget(box)

    # --- Laden/Anzeigen ------------------------------------------------------

    def _reload(self) -> None:
        try:
            self._settings = self.api.get_settings()
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("settings_view.load_failed", error=str(exc)))
            return
        s = self._settings

        self.language_combo.setCurrentText(s["general"]["language"])
        self.require_confirmation_check.setChecked(
            s["general"]["require_confirmation_for_bulk_changes"]
        )

        self.folders_list.clear()
        for folder in s["paths"]["media_folders"]:
            self.folders_list.addItem(folder)

        self.ai_enabled_check.setChecked(s["ai"]["enabled"])
        self.ai_provider_combo.setCurrentText(s["ai"]["provider"])
        self.ai_endpoint_edit.setText(s["ai"]["endpoint"])
        self.ai_model_edit.setText(s["ai"]["model"])
        self.ai_embedding_model_edit.setText(s["ai"]["embedding_model"])
        self.ai_timeout_spin.setValue(s["ai"]["timeout_seconds"])

        self.voice_enabled_check.setChecked(s["voice"]["enabled"])
        self.voice_provider_combo.setCurrentText(s["voice"]["provider"])
        self.voice_export_format_combo.setCurrentText(s["voice"]["default_export_format"])

        self.loudness_target_lufs_spin.setValue(s["loudness"]["target_lufs"])
        self.loudness_target_true_peak_spin.setValue(s["loudness"]["target_true_peak_dbtp"])
        self.loudness_overwrite_check.setChecked(s["loudness"]["overwrite_originals"])

        self.download_enabled_check.setChecked(s["download"]["enabled"])
        self.download_youtube_check.setChecked(s["download"]["enable_youtube"])
        self.download_tiktok_check.setChecked(s["download"]["enable_tiktok"])
        self.download_dir_edit.setText(s["download"]["downloads_dir"] or "")
        self.download_max_size_spin.setValue(s["download"]["max_download_size_mb"])
        self.download_min_free_disk_spin.setValue(s["download"]["min_free_disk_mb"])
        self.download_timeout_spin.setValue(s["download"]["request_timeout_seconds"])

        self.privacy_telemetry_check.setChecked(s["privacy"]["telemetry_enabled"])
        self.privacy_cloud_ai_check.setChecked(s["privacy"]["allow_cloud_ai"])
        self.privacy_auto_downloads_check.setChecked(s["privacy"]["allow_automatic_downloads"])
        self.privacy_auto_deletion_check.setChecked(s["privacy"]["allow_automatic_deletion"])
        self.privacy_auto_overwrite_check.setChecked(s["privacy"]["allow_automatic_overwrite"])

        self.status_label.setText("")

    # --- Medienordner ----------------------------------------------------------

    def _on_add_folder_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, tr("settings_view.add_folder_dialog_title")
        )
        if not directory:
            return
        existing = [
            self.folders_list.item(i).text() for i in range(self.folders_list.count())
        ]
        if directory not in existing:
            self.folders_list.addItem(directory)

    def _on_remove_folder_clicked(self) -> None:
        for item in self.folders_list.selectedItems():
            self.folders_list.takeItem(self.folders_list.row(item))

    def _on_scan_clicked(self) -> None:
        """Startet einen Bibliotheksscan direkt mit der aktuell in der Liste
        angezeigten Ordnermenge (POST /scan nimmt seine Zielordner als
        expliziten Parameter entgegen - unabhaengig davon, ob die Liste
        bereits gespeichert wurde, Prinzip #4/#5: rein lesende Analyse,
        veraendert keine Mediendatei)."""
        folders = [self.folders_list.item(i).text() for i in range(self.folders_list.count())]
        if not folders:
            self.status_label.setText(tr("settings_view.scan_no_folders"))
            return
        try:
            result = self.api.trigger_scan(folders)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("settings_view.scan_failed", error=str(exc)))
            return
        files_found = result.get("result", {}).get("files_found", 0)
        self.status_label.setText(tr("settings_view.scan_done", count=files_found))

    def _on_browse_download_dir_clicked(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, tr("settings_view.download_dir_dialog_title")
        )
        if directory:
            self.download_dir_edit.setText(directory)

    # --- Speichern -------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        folders = [self.folders_list.item(i).text() for i in range(self.folders_list.count())]
        updates = {
            "general": {
                "language": self.language_combo.currentText(),
                "require_confirmation_for_bulk_changes": self.require_confirmation_check.isChecked(),
            },
            "paths": {
                "media_folders": folders,
            },
            "ai": {
                "enabled": self.ai_enabled_check.isChecked(),
                "provider": self.ai_provider_combo.currentText(),
                "endpoint": self.ai_endpoint_edit.text(),
                "model": self.ai_model_edit.text(),
                "embedding_model": self.ai_embedding_model_edit.text(),
                "timeout_seconds": self.ai_timeout_spin.value(),
            },
            "voice": {
                "enabled": self.voice_enabled_check.isChecked(),
                "provider": self.voice_provider_combo.currentText(),
                "default_export_format": self.voice_export_format_combo.currentText(),
            },
            "loudness": {
                "target_lufs": self.loudness_target_lufs_spin.value(),
                "target_true_peak_dbtp": self.loudness_target_true_peak_spin.value(),
                "overwrite_originals": self.loudness_overwrite_check.isChecked(),
            },
            "download": {
                "enabled": self.download_enabled_check.isChecked(),
                "enable_youtube": self.download_youtube_check.isChecked(),
                "enable_tiktok": self.download_tiktok_check.isChecked(),
                "downloads_dir": self.download_dir_edit.text() or None,
                "max_download_size_mb": self.download_max_size_spin.value(),
                "min_free_disk_mb": self.download_min_free_disk_spin.value(),
                "request_timeout_seconds": self.download_timeout_spin.value(),
            },
            "privacy": {
                "telemetry_enabled": self.privacy_telemetry_check.isChecked(),
                "allow_cloud_ai": self.privacy_cloud_ai_check.isChecked(),
                "allow_automatic_downloads": self.privacy_auto_downloads_check.isChecked(),
                "allow_automatic_deletion": self.privacy_auto_deletion_check.isChecked(),
                "allow_automatic_overwrite": self.privacy_auto_overwrite_check.isChecked(),
            },
        }

        reply = QMessageBox.question(
            self,
            tr("settings_view.save_confirm_title"),
            tr("settings_view.save_confirm_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            result = self.api.update_settings(updates, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("settings_view.save_failed", error=str(exc)))
            return

        # _reload() ZUERST (es setzt am Ende selbst den Status-Text auf ""),
        # die eigentliche Erfolgsmeldung erst DANACH setzen - sonst wuerde
        # sie sofort wieder ueberschrieben (siehe Testfall in
        # test_gap_closure_settings_providers_view.py).
        self._reload()
        if result.get("restart_required"):
            self.status_label.setText(tr("settings_view.save_done_restart_required"))
        else:
            self.status_label.setText(tr("settings_view.save_done"))
