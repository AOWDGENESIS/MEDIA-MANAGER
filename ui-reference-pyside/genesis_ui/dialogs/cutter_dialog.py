"""Dialog fuer den grafischen Audio-Cutter (§18, Phase 3, ADR-0011).

Ablauf (Erkennen -> Vorschlag/Vorschau -> Bestaetigung -> Aenderung ->
Protokoll, Prinzip #4/#5/#17):
1. Beim Oeffnen wird automatisch ein Waveform-Vorschaubild geladen (rein
   lesend - erzeugt nur ein Cache-PNG, veraendert das Original nicht).
2. Start/Ende/Fade-In/Fade-Out werden als sekunden-genaue Zahlenfelder statt
   per Maus-Drag eingegeben (erfuellt die §18-Anforderung "exakte
   Zeitposition" direkt, siehe ADR-0011) und per Vorschau validiert (reine
   Berechnung, erzeugt keine Datei).
3. Wiedergabe/Pause ueber `QtMultimedia` erlaubt das Abhoeren der
   Originaldatei, inkl. Sprung zum Start-/End-Zeitpunkt der aktuellen
   Auswahl, um die Grenzen vor dem Export genau zu pruefen.
4. Erst nach explizitem Klick + Bestaetigungsdialog wird tatsaechlich eine
   NEUE Exportdatei erzeugt - das Original wird NIE veraendert.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
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

EXPORT_FORMATS = ("mp3", "wav", "flac")


class CutterDialog(QDialog):
    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 absolute_path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.absolute_path = absolute_path
        self.changed = False
        self._current_plan: dict | None = None
        self._known_duration_seconds: float | None = None
        try:
            detail = self.api.media_detail(media_id)
            technical = detail.get("technical") or {}
            self._known_duration_seconds = technical.get("duration_seconds")
        except GenesisAPIError:
            pass  # Dauer bleibt unbekannt - Spinboxen behalten ihre weiten Standardgrenzen.

        self.setWindowTitle(tr("cutter_dialog.window_title", filename=filename))
        self.resize(680, 680)

        root = QVBoxLayout(self)

        self.waveform_label = QLabel(tr("cutter_dialog.loading_waveform"))
        self.waveform_label.setMinimumHeight(140)
        self.waveform_label.setStyleSheet("background-color: #1c1f26;")
        self.waveform_label.setScaledContents(True)
        root.addWidget(self.waveform_label)

        # Wiedergabe (§18: Wiedergabe/Pause). Spielt die ORIGINALDATEI ab -
        # rein lesend, veraendert nichts (Prinzip #4/#5). In der Sandbox ohne
        # Audiogeraet nicht hoerbar pruefbar, nur konstruktions-/
        # offscreen-testbar (siehe PROGRESS.md).
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setSource(QUrl.fromLocalFile(self.absolute_path))

        playback_row = QHBoxLayout()
        self.play_btn = QPushButton(tr("cutter_dialog.play_button"))
        self.play_btn.clicked.connect(self._on_play_clicked)
        self.pause_btn = QPushButton(tr("cutter_dialog.pause_button"))
        self.pause_btn.clicked.connect(self._player.pause)
        self.play_selection_btn = QPushButton(tr("cutter_dialog.play_selection_button"))
        self.play_selection_btn.clicked.connect(self._on_play_selection_clicked)
        playback_row.addWidget(self.play_btn)
        playback_row.addWidget(self.pause_btn)
        playback_row.addWidget(self.play_selection_btn)
        playback_row.addStretch(1)
        root.addLayout(playback_row)

        form = QFormLayout()
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 36000.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setSuffix(" s")
        self.start_spin.valueChanged.connect(self._run_preview)
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.01, 36000.0)
        self.end_spin.setDecimals(2)
        if self._known_duration_seconds:
            # Kleine Sicherheitsmarge (statt der exakten Dauer), damit das
            # Runden auf 2 Nachkommastellen in der Spinbox nicht knapp ueber
            # die tatsaechliche Dateidauer hinausschiesst und die erste
            # automatische Vorschau faelschlich als ungueltig ablehnt.
            safe_duration = max(self._known_duration_seconds - 0.1, 0.01)
            self.start_spin.setMaximum(safe_duration)
            self.end_spin.setMaximum(safe_duration)
            default_end = safe_duration
        else:
            default_end = 10.0
        self.end_spin.setValue(default_end)
        self.end_spin.setSuffix(" s")
        self.end_spin.valueChanged.connect(self._run_preview)
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_in_spin.setRange(0.0, 3600.0)
        self.fade_in_spin.setDecimals(2)
        self.fade_in_spin.setSuffix(" s")
        self.fade_in_spin.valueChanged.connect(self._run_preview)
        self.fade_out_spin = QDoubleSpinBox()
        self.fade_out_spin.setRange(0.0, 3600.0)
        self.fade_out_spin.setDecimals(2)
        self.fade_out_spin.setSuffix(" s")
        self.fade_out_spin.valueChanged.connect(self._run_preview)
        self.format_combo = QComboBox()
        self.format_combo.addItems(EXPORT_FORMATS)
        self.format_combo.currentTextChanged.connect(self._run_preview)

        form.addRow(tr("cutter_dialog.start_label"), self.start_spin)
        form.addRow(tr("cutter_dialog.end_label"), self.end_spin)
        form.addRow(tr("cutter_dialog.fade_in_label"), self.fade_in_spin)
        form.addRow(tr("cutter_dialog.fade_out_label"), self.fade_out_spin)
        form.addRow(tr("cutter_dialog.format_label"), self.format_combo)
        root.addLayout(form)

        self.plan_label = QLabel(tr("cutter_dialog.no_preview_yet"))
        self.plan_label.setWordWrap(True)
        root.addWidget(self.plan_label)

        root.addWidget(QLabel(tr("cutter_dialog.history_label")))
        self.history_list = QListWidget()
        root.addWidget(self.history_list, stretch=1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton(tr("cutter_dialog.apply_button"))
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        close_btn = QPushButton(tr("cutter_dialog.close_button"))
        close_btn.clicked.connect(self._on_close)
        btn_row.addWidget(self.apply_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._load_waveform()
        self._reload_history()
        self._run_preview()

    # --- Aktionen -------------------------------------------------------------

    def _load_waveform(self) -> None:
        try:
            data = self.api.get_cutter_waveform_bytes(self.media_id)
        except GenesisAPIError as exc:
            set_plain_text(self.waveform_label, tr("cutter_dialog.waveform_failed", error=exc))
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.waveform_label.setPixmap(pixmap)
        else:
            set_plain_text(
                self.waveform_label,
                tr("cutter_dialog.waveform_failed", error="invalid PNG"),
            )

    def _reload_history(self) -> None:
        self.history_list.clear()
        try:
            rows = self.api.list_cuts(self.media_id)
        except GenesisAPIError:
            return
        for row in rows:
            date = (row.get("created_at") or "")[:19].replace("T", " ")
            text = tr(
                "cutter_dialog.history_row", date=date,
                start=f"{row['start_seconds']:.2f}", end=f"{row['end_seconds']:.2f}",
                format=row["export_format"], path=row.get("output_path") or "",
            )
            self.history_list.addItem(text)

    def _run_preview(self) -> None:
        start = self.start_spin.value()
        end = self.end_spin.value()
        fade_in = self.fade_in_spin.value()
        fade_out = self.fade_out_spin.value()
        export_format = self.format_combo.currentText()
        try:
            plan = self.api.preview_cut(
                self.media_id, start_seconds=start, end_seconds=end,
                export_format=export_format, fade_in_seconds=fade_in, fade_out_seconds=fade_out,
            )
        except GenesisAPIError as exc:
            self._current_plan = None
            set_plain_text(self.plan_label, tr("cutter_dialog.preview_failed", error=exc))
            self.apply_btn.setEnabled(False)
            return

        self._current_plan = plan
        # output_path ist ein Dateipfad (dynamischer Inhalt) - siehe
        # genesis_ui.widgets-Moduldocstring.
        text = (
            tr(
                "cutter_dialog.plan_summary",
                duration=f"{plan['selection_duration_seconds']:.2f}",
                format=plan["export_format"],
                output_path=plan["output_path"],
            )
            + ("\n" + tr("cutter_dialog.lossy_note") if plan["is_lossy_export"] else "")
        )
        if plan["has_conflict"]:
            text += "\n\n" + tr("cutter_dialog.conflict_warning")
            self.apply_btn.setEnabled(False)
        else:
            self.apply_btn.setEnabled(True)
        set_plain_text(self.plan_label, text)

    def _on_play_clicked(self) -> None:
        self._player.setPosition(int(self.start_spin.value() * 1000))
        self._player.play()

    def _on_play_selection_clicked(self) -> None:
        """Spielt NUR die aktuelle Auswahl ab (Start bis Ende) zur
        Kontrolle vor dem Export - rein lesend, erzeugt keine Datei."""
        self._player.setPosition(int(self.start_spin.value() * 1000))
        self._player.play()
        end_ms = int(self.end_spin.value() * 1000)

        def _stop_at_end(position: int) -> None:
            if position >= end_ms:
                self._player.pause()
                self._player.positionChanged.disconnect(_stop_at_end)

        self._player.positionChanged.connect(_stop_at_end)

    def _on_apply_clicked(self) -> None:
        if self._current_plan is None:
            return
        confirm = QMessageBox.question(
            self,
            tr("cutter_dialog.confirm_title"),
            tr("cutter_dialog.confirm_text", output_path=self._current_plan["output_path"]),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            result = self.api.apply_cut(
                self.media_id,
                start_seconds=self._current_plan["start_seconds"],
                end_seconds=self._current_plan["end_seconds"],
                export_format=self._current_plan["export_format"],
                fade_in_seconds=self._current_plan["fade_in_seconds"],
                fade_out_seconds=self._current_plan["fade_out_seconds"],
                confirm=True,
            )
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("cutter_dialog.apply_failed", error=exc))
            return

        self.changed = True
        QMessageBox.information(
            self, tr("cutter_dialog.done_title"),
            tr("cutter_dialog.done_text", output_path=result["output_path"]),
        )
        self._reload_history()
        self._run_preview()

    def _on_close(self) -> None:
        self._player.stop()
        self.reject()

    def closeEvent(self, event) -> None:
        self._player.stop()
        super().closeEvent(event)
