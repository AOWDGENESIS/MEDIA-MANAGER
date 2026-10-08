"""Dialog fuer die Loudness-Engine (§19, Phase 3, ADR-0010).

Ablauf (Erkennen -> Analysieren -> Vorschlag -> Vorschau -> Bestaetigung ->
Aenderung -> Protokoll, Prinzip #4/#5/#17):
1. Beim Oeffnen wird automatisch gemessen (`analyze`) - rein lesend, keine
   Bestaetigung noetig (gleiche Risikoklasse wie die automatische
   Technikanalyse beim Scan).
2. Eine Normalisierungs-VORSCHAU wird automatisch mit den konfigurierten
   Standardzielwerten geladen (ebenfalls rein lesend, erzeugt keine Datei).
   Fuer Medienarten ohne Normalisierungs-Unterstuetzung (Video) wird dieser
   Teil deaktiviert, die reine Messung bleibt aber sichtbar.
3. Erst nach explizitem Klick + Bestaetigungsdialog wird tatsaechlich eine
   NEUE Datei erzeugt - das Original wird NIE veraendert.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


class LoudnessDialog(QDialog):
    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.changed = False
        self._normalization_supported = True

        self.setWindowTitle(tr("loudness_dialog.window_title", filename=filename))
        self.resize(560, 560)

        root = QVBoxLayout(self)

        self.status_label = QLabel(tr("loudness_dialog.analyzing"))
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        analyze_row = QHBoxLayout()
        self.analyze_btn = QPushButton(tr("loudness_dialog.analyze_button"))
        self.analyze_btn.clicked.connect(self._run_analysis)
        analyze_row.addWidget(self.analyze_btn)
        analyze_row.addStretch(1)
        root.addLayout(analyze_row)

        form = QFormLayout()
        self.target_lufs_spin = QDoubleSpinBox()
        self.target_lufs_spin.setRange(-40.0, 0.0)
        self.target_lufs_spin.setDecimals(1)
        self.target_lufs_spin.setSuffix(" LUFS")
        self.target_tp_spin = QDoubleSpinBox()
        self.target_tp_spin.setRange(-9.0, 0.0)
        self.target_tp_spin.setDecimals(1)
        self.target_tp_spin.setSuffix(" dBTP")
        form.addRow(tr("loudness_dialog.target_lufs_label"), self.target_lufs_spin)
        form.addRow(tr("loudness_dialog.target_true_peak_label"), self.target_tp_spin)
        root.addLayout(form)

        preview_row = QHBoxLayout()
        self.preview_btn = QPushButton(tr("loudness_dialog.preview_button"))
        self.preview_btn.clicked.connect(self._run_preview)
        preview_row.addWidget(self.preview_btn)
        preview_row.addStretch(1)
        root.addLayout(preview_row)

        self.plan_label = QLabel(tr("loudness_dialog.no_preview_yet"))
        self.plan_label.setWordWrap(True)
        root.addWidget(self.plan_label)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #e0a030;")
        self.warning_label.hide()
        root.addWidget(self.warning_label)

        root.addWidget(QLabel(tr("loudness_dialog.history_label")))
        self.history_list = QListWidget()
        root.addWidget(self.history_list, stretch=1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton(tr("loudness_dialog.apply_button"))
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        close_btn = QPushButton(tr("loudness_dialog.close_button"))
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._current_plan: dict | None = None
        # Solange die Spinboxen noch nicht mit den vom Server gelieferten
        # Standardzielwerten vorbelegt wurden, wird bei `_run_preview()` KEIN
        # Zielwert mitgeschickt (Server verwendet dann Settings.loudness) -
        # ein reiner Flag statt "ist der Wert 0.0" zu pruefen, da 0.0 ein
        # technisch gueltiger (wenn auch unueblicher) Zielwert waere.
        self._targets_initialized = False
        self._run_analysis()

    # --- Aktionen -----------------------------------------------------------

    def _run_analysis(self) -> None:
        try:
            measurement = self.api.analyze_loudness(self.media_id)
        except GenesisAPIError as exc:
            set_plain_text(self.status_label, tr("loudness_dialog.analyze_failed", error=exc))
            return

        self.status_label.setText(
            tr(
                "loudness_dialog.measured_label",
                lufs=f"{measurement['integrated_lufs']:.1f}",
                peak=f"{measurement['true_peak_dbtp']:.1f}",
                lra=f"{measurement['loudness_range_lu']:.1f}",
            )
        )
        self._reload_history()
        self._run_preview()

    def _reload_history(self) -> None:
        self.history_list.clear()
        try:
            rows = self.api.list_loudness(self.media_id)
        except GenesisAPIError:
            return
        for row in rows:
            date = (row.get("measured_at") or "")[:19].replace("T", " ")
            if row.get("normalized"):
                text = tr(
                    "loudness_dialog.history_row_normalized", date=date,
                    lufs=f"{row['integrated_lufs']:.1f}", peak=f"{row['true_peak_dbtp']:.1f}",
                    path=row.get("normalized_output_path") or "",
                )
            else:
                text = tr(
                    "loudness_dialog.history_row_measured", date=date,
                    lufs=f"{row['integrated_lufs']:.1f}", peak=f"{row['true_peak_dbtp']:.1f}",
                )
            self.history_list.addItem(text)

    def _run_preview(self) -> None:
        target_lufs = self.target_lufs_spin.value() if self._targets_initialized else None
        target_tp = self.target_tp_spin.value() if self._targets_initialized else None
        try:
            plan = self.api.preview_loudness_normalization(
                self.media_id, target_lufs=target_lufs, target_true_peak_dbtp=target_tp,
            )
        except GenesisAPIError as exc:
            if "nicht unterstützt" in str(exc):
                self._normalization_supported = False
                self.plan_label.setText(tr("loudness_dialog.unsupported_kind"))
                self.target_lufs_spin.setEnabled(False)
                self.target_tp_spin.setEnabled(False)
                self.preview_btn.setEnabled(False)
                self.apply_btn.setEnabled(False)
            else:
                set_plain_text(self.plan_label, tr("loudness_dialog.preview_failed", error=exc))
            return

        self._current_plan = plan
        # Spinboxen beim ERSTEN erfolgreichen Preview mit den vom Server
        # verwendeten (konfigurierten Standard-)Zielwerten vorbelegen.
        if not self._targets_initialized:
            self.target_lufs_spin.setValue(plan["target_lufs"])
            self.target_tp_spin.setValue(plan["target_true_peak_dbtp"])
            self._targets_initialized = True

        # output_path/output_format_note sind dynamische Inhalte (Dateipfad
        # bzw. Backend-Text) - siehe genesis_ui.widgets-Moduldocstring.
        text = (
            tr(
                "loudness_dialog.plan_summary",
                gain=f"{plan['planned_gain_db']:+.2f}",
                target_lufs=f"{plan['target_lufs']:.1f}",
                target_tp=f"{plan['target_true_peak_dbtp']:.1f}",
                predicted_tp=f"{plan['predicted_output_true_peak_dbtp']:.1f}",
                output_path=plan["output_path"],
            )
            + "\n"
            + plan["output_format_note"]
        )
        if plan["will_likely_alter_dynamics"]:
            self.warning_label.setText(tr("loudness_dialog.dynamics_warning"))
            self.warning_label.show()
        else:
            self.warning_label.hide()

        if plan["has_conflict"]:
            text += "\n\n" + tr("loudness_dialog.conflict_warning")
            self.apply_btn.setEnabled(False)
        else:
            self.apply_btn.setEnabled(self._normalization_supported)
        set_plain_text(self.plan_label, text)

    def _on_apply_clicked(self) -> None:
        if self._current_plan is None:
            return
        confirm = QMessageBox.question(
            self,
            tr("loudness_dialog.confirm_title"),
            tr("loudness_dialog.confirm_text", output_path=self._current_plan["output_path"]),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            result = self.api.apply_loudness_normalization(
                self.media_id,
                target_lufs=self._current_plan["target_lufs"],
                target_true_peak_dbtp=self._current_plan["target_true_peak_dbtp"],
                target_lra=self._current_plan["target_lra"],
                confirm=True,
            )
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("loudness_dialog.apply_failed", error=exc))
            return

        self.changed = True
        QMessageBox.information(
            self, tr("loudness_dialog.done_title"),
            tr(
                "loudness_dialog.done_text",
                lufs=f"{result['achieved_integrated_lufs']:.1f}",
                peak=f"{result['achieved_true_peak_dbtp']:.1f}",
                output_path=result["output_path"],
            ),
        )
        self._reload_history()
        self._run_preview()
