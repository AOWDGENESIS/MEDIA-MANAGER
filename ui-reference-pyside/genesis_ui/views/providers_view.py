"""Metadaten-Provider (nav.providers, §10/§11, Gap-Analyse I).

Betrifft die ONLINE-Metadatenabgleich-Provider (MusicBrainz, AcoustID,
Cover Art Archive) - zu unterscheiden von den Download-/Import-Providern
(YouTube/TikTok/etc., siehe `nav.download_center` -> `DownloadCenterView`,
deren Verwaltung bereits existiert). Nutzt denselben `PATCH /settings`-
Endpunkt wie `SettingsView`, schreibt aber ausschliesslich in den
`metadata`-Abschnitt.

Standardmaessig ist der komplette Online-Abgleich AUS (§56, "kein
Internetzwang") - selbst wenn aktiviert, bleibt laut `MetadataSettings`-
Docstring jeder Treffer nur ein Vorschlag mit Konfidenzwert (Prinzip #17),
niemals eine automatische Uebernahme.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


class ProvidersView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("providers_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("providers_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        box = QGroupBox(tr("providers_view.section_general"))
        form = QFormLayout(box)
        self.enabled_check = QCheckBox()
        form.addRow(tr("providers_view.metadata_enabled_label"), self.enabled_check)
        enabled_note = QLabel(tr("providers_view.metadata_enabled_note"))
        enabled_note.setWordWrap(True)
        form.addRow(enabled_note)
        root.addWidget(box)

        providers_box = QGroupBox(tr("providers_view.section_providers"))
        p_form = QFormLayout(providers_box)
        self.musicbrainz_check = QCheckBox()
        p_form.addRow(tr("providers_view.musicbrainz_enabled_label"), self.musicbrainz_check)
        self.acoustid_check = QCheckBox()
        p_form.addRow(tr("providers_view.acoustid_enabled_label"), self.acoustid_check)
        self.acoustid_key_edit = QLineEdit()
        p_form.addRow(tr("providers_view.acoustid_api_key_label"), self.acoustid_key_edit)
        acoustid_note = QLabel(tr("providers_view.acoustid_api_key_note"))
        acoustid_note.setWordWrap(True)
        acoustid_note.setOpenExternalLinks(True)
        p_form.addRow(acoustid_note)
        self.coverartarchive_check = QCheckBox()
        p_form.addRow(
            tr("providers_view.coverartarchive_enabled_label"), self.coverartarchive_check
        )
        root.addWidget(providers_box)

        contact_box = QGroupBox(tr("providers_view.section_contact"))
        c_form = QFormLayout(contact_box)
        self.contact_email_edit = QLineEdit()
        c_form.addRow(tr("providers_view.contact_email_label"), self.contact_email_edit)
        contact_note = QLabel(tr("providers_view.contact_email_note"))
        contact_note.setWordWrap(True)
        c_form.addRow(contact_note)
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 120.0)
        self.timeout_spin.setSuffix(" s")
        c_form.addRow(tr("providers_view.request_timeout_label"), self.timeout_spin)
        self.min_confidence_spin = QDoubleSpinBox()
        self.min_confidence_spin.setRange(0.0, 1.0)
        self.min_confidence_spin.setSingleStep(0.05)
        c_form.addRow(tr("providers_view.min_confidence_label"), self.min_confidence_spin)
        min_confidence_note = QLabel(tr("providers_view.min_confidence_note"))
        min_confidence_note.setWordWrap(True)
        c_form.addRow(min_confidence_note)
        root.addWidget(contact_box)

        root.addStretch(1)

        bottom_row = QHBoxLayout()
        self.save_btn = QPushButton(tr("providers_view.save_button"))
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.reload_btn = QPushButton(tr("providers_view.reload_button"))
        self.reload_btn.clicked.connect(self._reload)
        bottom_row.addWidget(self.save_btn)
        bottom_row.addWidget(self.reload_btn)
        bottom_row.addStretch(1)
        root.addLayout(bottom_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._reload()

    def _reload(self) -> None:
        try:
            settings = self.api.get_settings()
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("providers_view.load_failed", error=str(exc)))
            return
        m = settings["metadata"]
        self.enabled_check.setChecked(m["enabled"])
        self.musicbrainz_check.setChecked(m["musicbrainz_enabled"])
        self.acoustid_check.setChecked(m["acoustid_enabled"])
        self.acoustid_key_edit.setText(m["acoustid_api_key"])
        self.coverartarchive_check.setChecked(m["coverartarchive_enabled"])
        self.contact_email_edit.setText(m["contact_email"])
        self.timeout_spin.setValue(m["request_timeout_seconds"])
        self.min_confidence_spin.setValue(m["min_confidence_for_suggestion"])
        self.status_label.setText("")

    def _on_save_clicked(self) -> None:
        updates = {
            "metadata": {
                "enabled": self.enabled_check.isChecked(),
                "musicbrainz_enabled": self.musicbrainz_check.isChecked(),
                "acoustid_enabled": self.acoustid_check.isChecked(),
                "acoustid_api_key": self.acoustid_key_edit.text(),
                "coverartarchive_enabled": self.coverartarchive_check.isChecked(),
                "contact_email": self.contact_email_edit.text(),
                "request_timeout_seconds": self.timeout_spin.value(),
                "min_confidence_for_suggestion": self.min_confidence_spin.value(),
            }
        }
        reply = QMessageBox.question(
            self,
            tr("providers_view.save_confirm_title"),
            tr("providers_view.save_confirm_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.api.update_settings(updates, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("providers_view.save_failed", error=str(exc)))
            return
        # _reload() ZUERST, da es am Ende selbst den Status-Text auf ""
        # zuruecksetzt - sonst wuerde die Erfolgsmeldung sofort wieder
        # ueberschrieben.
        self._reload()
        self.status_label.setText(tr("providers_view.save_done"))
