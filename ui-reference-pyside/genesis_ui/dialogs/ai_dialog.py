"""Dialog für KI-Metadaten & KI-Musik-Herkunft (§25/§27, Phase 6, ADR-0017).

Ablauf (Erkennen -> Vorschlag -> Confidence -> Vorschau -> Benutzerfreigabe
-> Änderung, Prinzip #4/#17), analog zu `AudiobookDialog`/`VideoDialog`:

Tab 1 "KI-Vorschläge" (§25): der Nutzer fordert explizit Vorschläge an
(NICHTS passiert automatisch im Hintergrund), waehlt per Checkbox aus,
welche Vorschlaege er fuer sinnvoll haelt, und uebernimmt NUR diese nach
Bestaetigung. Jeder gespeicherte Eintrag zeigt Modell/Konfidenz (Prinzip
#9). Ist die KI deaktiviert (NullAIProvider, §56-Standard), liefert die
Vorschau immer eine leere Liste - das wird klar kommuniziert, kein Fehler.

Tab 2 "KI-Musik" (§27): IMMER eine manuelle Nutzerangabe (GENESIS kann KI-
Urheberschaft nicht selbst feststellen) - nur fuer Musik/KI-Musik-Dateien
sichtbar.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import escape_mnemonic, set_plain_text

_AI_MUSIC_RELEVANT_KINDS = {"music", "ai_music"}
_AI_STATUS_VALUES = ["unknown", "human_generated", "ai_generated", "hybrid"]


class AIDialog(QDialog):
    def __init__(
        self, api: GenesisAPIClient, media_id: int, filename: str, kind: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.kind = kind
        self.changed = False
        self._suggestion_rows: list[tuple[QCheckBox, dict]] = []

        self.setWindowTitle(tr("ai_dialog.window_title", filename=filename))
        self.resize(760, 620)

        root = QVBoxLayout(self)

        self.status_banner = QLabel(tr("ai_dialog.loading"))
        self.status_banner.setWordWrap(True)
        self.status_banner.setStyleSheet("color: #9fb8d8;")
        root.addWidget(self.status_banner)

        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)
        tabs.addTab(self._build_suggestions_tab(), tr("ai_dialog.tab_suggestions"))
        if kind in _AI_MUSIC_RELEVANT_KINDS:
            tabs.addTab(self._build_ai_music_tab(), tr("ai_dialog.tab_ai_music"))

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton(tr("ai_dialog.close_button"))
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._load_ai_status()
        self._reload_stored_metadata()
        if kind in _AI_MUSIC_RELEVANT_KINDS:
            self._load_ai_music()

    # --- KI-Status-Banner ----------------------------------------------------

    def _load_ai_status(self) -> None:
        try:
            status = self.api.get_ai_status()
        except GenesisAPIError as exc:
            self.status_banner.setText(tr("ai_dialog.status_load_failed", error=exc))
            return
        if not status.get("enabled"):
            self.status_banner.setText(tr("ai_dialog.status_disabled"))
        elif not status.get("available"):
            self.status_banner.setText(
                tr("ai_dialog.status_unavailable", provider=status.get("provider"))
            )
        else:
            self.status_banner.setText(
                tr(
                    "ai_dialog.status_active",
                    provider=status.get("provider"),
                    model=status.get("model"),
                )
            )

    # --- Tab 1: KI-Vorschläge (§25) --------------------------------------------

    def _build_suggestions_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(tr("ai_dialog.suggestions_info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        generate_row = QHBoxLayout()
        self.generate_btn = QPushButton(tr("ai_dialog.generate_button"))
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        generate_row.addWidget(self.generate_btn)
        generate_row.addStretch(1)
        layout.addLayout(generate_row)

        self.suggestions_status_label = QLabel("")
        self.suggestions_status_label.setWordWrap(True)
        layout.addWidget(self.suggestions_status_label)

        self.suggestions_container = QWidget()
        self.suggestions_layout = QVBoxLayout(self.suggestions_container)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.suggestions_container)
        layout.addWidget(scroll, stretch=1)

        apply_row = QHBoxLayout()
        self.apply_suggestions_btn = QPushButton(tr("ai_dialog.apply_selected_button"))
        self.apply_suggestions_btn.setEnabled(False)
        self.apply_suggestions_btn.clicked.connect(self._on_apply_suggestions_clicked)
        apply_row.addWidget(self.apply_suggestions_btn)
        apply_row.addStretch(1)
        layout.addLayout(apply_row)

        stored_label = QLabel(tr("ai_dialog.stored_metadata_title"))
        bold_font = stored_label.font()
        bold_font.setBold(True)
        stored_label.setFont(bold_font)
        layout.addWidget(stored_label)
        self.stored_metadata_label = QLabel(tr("ai_dialog.no_stored_metadata"))
        self.stored_metadata_label.setWordWrap(True)
        layout.addWidget(self.stored_metadata_label)

        return tab

    def _on_generate_clicked(self) -> None:
        self.suggestions_status_label.setText(tr("ai_dialog.loading"))
        self._clear_suggestions()
        try:
            suggestions = self.api.suggest_ai_metadata(self.media_id)
        except GenesisAPIError as exc:
            self.suggestions_status_label.setText(tr("ai_dialog.generate_failed", error=exc))
            return

        if not suggestions:
            self.suggestions_status_label.setText(tr("ai_dialog.no_suggestions"))
            self.apply_suggestions_btn.setEnabled(False)
            return

        self.suggestions_status_label.setText(
            tr("ai_dialog.suggestions_found", count=len(suggestions))
        )
        for suggestion in suggestions:
            # Deep-Review-Fund (Sitzung 11): `field_value`/`model_name` sind
            # KI-/Konfigurationsausgaben, keine im Quellcode stehenden
            # Beschriftungen - ein einzelnes "&" darin wuerde QCheckBox
            # sonst als Mnemonic-Markierung fehlinterpretieren (siehe
            # `genesis_ui.widgets.escape_mnemonic`-Docstring).
            checkbox = QCheckBox(
                escape_mnemonic(
                    tr(
                        "ai_dialog.suggestion_row",
                        field=suggestion["field_name"],
                        value=suggestion["field_value"],
                        model=suggestion["model_name"],
                        confidence=f"{(suggestion.get('confidence') or 0.0):.0%}",
                    )
                )
            )
            self.suggestions_layout.addWidget(checkbox)
            self._suggestion_rows.append((checkbox, suggestion))
        self.suggestions_layout.addStretch(1)
        self.apply_suggestions_btn.setEnabled(True)

    def _clear_suggestions(self) -> None:
        self._suggestion_rows.clear()
        while self.suggestions_layout.count():
            item = self.suggestions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_apply_suggestions_clicked(self) -> None:
        accepted = [data for checkbox, data in self._suggestion_rows if checkbox.isChecked()]
        if not accepted:
            QMessageBox.information(
                self, tr("ai_dialog.nothing_selected_title"), tr("ai_dialog.nothing_selected_text")
            )
            return
        confirm = QMessageBox.question(
            self,
            tr("ai_dialog.confirm_apply_title"),
            tr("ai_dialog.confirm_apply_text", count=len(accepted)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        payload = [
            {
                "field_name": s["field_name"], "field_value": s["field_value"],
                "model_name": s["model_name"], "model_version": s.get("model_version"),
                "confidence": s.get("confidence"), "prompt": s.get("prompt"),
            }
            for s in accepted
        ]
        try:
            self.api.apply_ai_metadata(self.media_id, payload, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("ai_dialog.apply_failed", error=exc))
            return
        self.changed = True
        self._reload_stored_metadata()
        QMessageBox.information(
            self, tr("ai_dialog.applied_title"), tr("ai_dialog.applied_text")
        )

    def _reload_stored_metadata(self) -> None:
        try:
            stored = self.api.get_ai_metadata(self.media_id)
        except GenesisAPIError:
            stored = []
        if not stored:
            self.stored_metadata_label.setText(tr("ai_dialog.no_stored_metadata"))
            return
        lines = [
            tr(
                "ai_dialog.stored_metadata_row",
                field=e["field_name"], value=e["field_value"], model=e["model_name"],
            )
            for e in stored
        ]
        # set_plain_text() statt .setText(): `lines` enthaelt KI-generierte
        # Werte, QLabel wuerde HTML-aehnlichen Inhalt sonst als Rich-Text
        # interpretieren (Deep-Review-Fund Sitzung 11).
        set_plain_text(self.stored_metadata_label, "\n".join(lines))

    # --- Tab 2: KI-Musik (§27) -------------------------------------------------

    def _build_ai_music_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(tr("ai_dialog.ai_music_info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.ai_music_persisted_label = QLabel(tr("ai_dialog.ai_music_not_set"))
        self.ai_music_persisted_label.setWordWrap(True)
        self.ai_music_persisted_label.setStyleSheet("color: #8fbf8f;")
        layout.addWidget(self.ai_music_persisted_label)

        form = QFormLayout()
        self.ai_music_status_combo = QComboBox()
        for value in _AI_STATUS_VALUES:
            self.ai_music_status_combo.addItem(tr(f"ai_dialog.status_{value}"), value)
        form.addRow(tr("ai_dialog.field_status"), self.ai_music_status_combo)

        self.ai_music_source_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_source"), self.ai_music_source_edit)
        self.ai_music_model_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_model"), self.ai_music_model_edit)
        self.ai_music_prompt_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_prompt"), self.ai_music_prompt_edit)
        self.ai_music_style_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_style"), self.ai_music_style_edit)
        self.ai_music_mood_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_mood"), self.ai_music_mood_edit)
        self.ai_music_owner_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_owner"), self.ai_music_owner_edit)
        self.ai_music_artist_edit = QLineEdit()
        form.addRow(tr("ai_dialog.field_artist_name"), self.ai_music_artist_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.apply_ai_music_btn = QPushButton(tr("ai_dialog.apply_ai_music_button"))
        self.apply_ai_music_btn.clicked.connect(self._on_apply_ai_music_clicked)
        btn_row.addWidget(self.apply_ai_music_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return tab

    def _load_ai_music(self) -> None:
        try:
            saved = self.api.get_ai_music(self.media_id)
        except GenesisAPIError:
            saved = None
        if saved is None:
            self.ai_music_persisted_label.setText(tr("ai_dialog.ai_music_not_set"))
            return
        self.ai_music_persisted_label.setText(
            tr("ai_dialog.ai_music_saved_summary", status=tr(f"ai_dialog.status_{saved['ai_status']}"))
        )
        self.ai_music_status_combo.setCurrentIndex(
            max(0, self.ai_music_status_combo.findData(saved["ai_status"]))
        )
        self.ai_music_source_edit.setText(saved.get("ai_source") or "")
        self.ai_music_model_edit.setText(saved.get("ai_model") or "")
        self.ai_music_prompt_edit.setText(saved.get("ai_prompt") or "")
        self.ai_music_style_edit.setText(saved.get("ai_style") or "")
        self.ai_music_mood_edit.setText(saved.get("ai_mood") or "")
        self.ai_music_owner_edit.setText(saved.get("ai_owner") or "")
        artist_names = saved.get("artist_names") or []
        self.ai_music_artist_edit.setText(artist_names[0] if artist_names else "")

    def _on_apply_ai_music_clicked(self) -> None:
        confirm = QMessageBox.question(
            self,
            tr("ai_dialog.confirm_ai_music_title"),
            tr("ai_dialog.confirm_ai_music_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        data = {
            "status": self.ai_music_status_combo.currentData(),
            "source": self.ai_music_source_edit.text().strip() or None,
            "model": self.ai_music_model_edit.text().strip() or None,
            "prompt": self.ai_music_prompt_edit.text().strip() or None,
            "style": self.ai_music_style_edit.text().strip() or None,
            "mood": self.ai_music_mood_edit.text().strip() or None,
            "owner": self.ai_music_owner_edit.text().strip() or None,
            "artist_name": self.ai_music_artist_edit.text().strip() or None,
        }
        try:
            self.api.apply_ai_music(self.media_id, data, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("ai_dialog.apply_ai_music_failed", error=exc))
            return
        self.changed = True
        self._load_ai_music()
        QMessageBox.information(
            self, tr("ai_dialog.applied_title"), tr("ai_dialog.ai_music_applied_text")
        )
