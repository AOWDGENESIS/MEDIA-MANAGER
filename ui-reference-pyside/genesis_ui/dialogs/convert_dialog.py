"""Dialog fuer das Konvertierungs-Werkzeug (nav.convert, Phase 3).

Ablauf (Vorschlag/Vorschau -> Bestaetigung -> Aenderung -> Protokoll,
Prinzip #4/#5/#17):
1. Zielformat (+ optionale Bitrate bei verlustbehafteten Formaten) auswaehlen
   - jede Aenderung aktualisiert automatisch eine reine Vorschau (kein
   ffmpeg-Aufruf, erzeugt keine Datei).
2. Erst nach explizitem Klick + Bestaetigungsdialog wird tatsaechlich eine
   NEUE Datei erzeugt - das Original wird NIE veraendert.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text

TARGET_FORMATS = ("mp3", "wav", "flac", "ogg", "opus", "m4a", "aac")


class ConvertDialog(QDialog):
    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.changed = False
        self._current_plan: dict | None = None

        self.setWindowTitle(tr("convert_dialog.window_title", filename=filename))
        self.resize(560, 560)

        root = QVBoxLayout(self)

        form = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(TARGET_FORMATS)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)

        self.bitrate_checkbox = QCheckBox(tr("convert_dialog.custom_bitrate_checkbox"))
        self.bitrate_checkbox.toggled.connect(self._on_bitrate_toggle)
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(32, 320)
        self.bitrate_spin.setSingleStep(32)
        self.bitrate_spin.setValue(192)
        self.bitrate_spin.setSuffix(" kbps")
        self.bitrate_spin.setEnabled(False)
        self.bitrate_spin.valueChanged.connect(self._run_preview)

        bitrate_row = QHBoxLayout()
        bitrate_row.addWidget(self.bitrate_checkbox)
        bitrate_row.addWidget(self.bitrate_spin)

        form.addRow(tr("convert_dialog.format_label"), self.format_combo)
        form.addRow(tr("convert_dialog.bitrate_label"), bitrate_row)
        root.addLayout(form)

        self.plan_label = QLabel(tr("convert_dialog.no_preview_yet"))
        self.plan_label.setWordWrap(True)
        root.addWidget(self.plan_label)

        root.addWidget(QLabel(tr("convert_dialog.history_label")))
        self.history_list = QListWidget()
        root.addWidget(self.history_list, stretch=1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton(tr("convert_dialog.apply_button"))
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        close_btn = QPushButton(tr("convert_dialog.close_button"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._reload_history()
        self._run_preview()

    # --- Aktionen -------------------------------------------------------------

    def _on_format_changed(self, _text: str) -> None:
        self._run_preview()

    def _on_bitrate_toggle(self, checked: bool) -> None:
        self.bitrate_spin.setEnabled(checked)
        self._run_preview()

    def _reload_history(self) -> None:
        self.history_list.clear()
        try:
            rows = self.api.list_conversions(self.media_id)
        except GenesisAPIError:
            return
        for row in rows:
            date = (row.get("created_at") or "")[:19].replace("T", " ")
            bitrate = f"{row['bitrate_kbps']} kbps" if row.get("bitrate_kbps") else "-"
            text = tr(
                "convert_dialog.history_row", date=date,
                source=row["source_format"], target=row["target_format"],
                bitrate=bitrate, path=row.get("output_path") or "",
            )
            self.history_list.addItem(text)

    def _run_preview(self) -> None:
        target_format = self.format_combo.currentText()
        bitrate = self.bitrate_spin.value() if self.bitrate_checkbox.isChecked() else None
        try:
            plan = self.api.preview_conversion(
                self.media_id, target_format=target_format, bitrate_kbps=bitrate,
            )
        except GenesisAPIError as exc:
            self._current_plan = None
            set_plain_text(self.plan_label, tr("convert_dialog.preview_failed", error=exc))
            self.apply_btn.setEnabled(False)
            return

        self._current_plan = plan
        # output_path ist ein Dateipfad (dynamischer Inhalt) - siehe
        # genesis_ui.widgets-Moduldocstring.
        text = tr(
            "convert_dialog.plan_summary",
            source_format=plan["source_format"], target_format=plan["target_format"],
            output_path=plan["output_path"],
        )
        if plan["is_no_op_same_format"]:
            text += "\n" + tr("convert_dialog.no_op_warning")

        if plan["has_conflict"]:
            text += "\n\n" + tr("convert_dialog.conflict_warning")
            self.apply_btn.setEnabled(False)
        else:
            self.apply_btn.setEnabled(True)
        set_plain_text(self.plan_label, text)

    def _on_apply_clicked(self) -> None:
        if self._current_plan is None:
            return
        confirm = QMessageBox.question(
            self,
            tr("convert_dialog.confirm_title"),
            tr("convert_dialog.confirm_text", output_path=self._current_plan["output_path"]),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            result = self.api.apply_conversion(
                self.media_id,
                target_format=self._current_plan["target_format"],
                bitrate_kbps=self._current_plan["bitrate_kbps"],
                confirm=True,
            )
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("convert_dialog.apply_failed", error=exc))
            return

        self.changed = True
        QMessageBox.information(
            self, tr("convert_dialog.done_title"),
            tr("convert_dialog.done_text", output_path=result["output_path"]),
        )
        self._reload_history()
        self._run_preview()
