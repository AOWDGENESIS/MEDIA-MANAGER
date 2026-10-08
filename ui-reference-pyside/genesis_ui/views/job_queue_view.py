"""Job-Warteschlange (nav.job_queue, §35/§36).

Zeigt ALLE Hintergrund-Jobs (Scan, Umbenennung, Export, Scan & Repair,
Fingerprinting usw.) mit Fortschritt und bietet fuer den aktuell
ausgewaehlten Job Pause/Fortsetzen/Abbrechen an. Die eigentliche
kooperative Pause-/Abbruch-Pruefung findet im Core Service zwischen
einzelnen Arbeitsschritten statt (siehe `JobManager`/`cooperative_
checkpoint` in genesis_core); diese Ansicht setzt nur den gewuenschten
Zielstatus und zeigt den zuletzt bekannten Zustand an - sie fuehrt selbst
keine Jobs aus und veraendert keine Mediendateien.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text

STATUS_LABEL_KEYS = {
    "pending": "job_queue_view.status_pending",
    "running": "job_queue_view.status_running",
    "paused": "job_queue_view.status_paused",
    "completed": "job_queue_view.status_completed",
    "failed": "job_queue_view.status_failed",
    "cancelled": "job_queue_view.status_cancelled",
}

ACTIVE_STATUSES = {"pending", "running", "paused"}

REFRESH_INTERVAL_MS = 2000


class JobQueueView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._jobs_by_id: dict[str, dict] = {}
        self._selected_job_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(tr("job_queue_view.title"))
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        note = QLabel(tr("job_queue_view.intro_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        controls = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("job_queue_view.refresh_button"))
        self.refresh_btn.clicked.connect(self._reload)
        controls.addWidget(self.refresh_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr("job_queue_view.col_id"),
            tr("job_queue_view.col_type"),
            tr("job_queue_view.col_status"),
            tr("job_queue_view.col_progress"),
            tr("job_queue_view.col_errors"),
            tr("job_queue_view.col_warnings"),
            tr("job_queue_view.col_created"),
        ])
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, stretch=1)

        detail_box = QVBoxLayout()
        self.current_item_label = QLabel("")
        self.current_item_label.setWordWrap(True)
        detail_box.addWidget(self.current_item_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        detail_box.addWidget(self.progress_bar)

        action_row = QHBoxLayout()
        self.pause_btn = QPushButton(tr("job_queue_view.pause_button"))
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.resume_btn = QPushButton(tr("job_queue_view.resume_button"))
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_resume_clicked)
        self.cancel_btn = QPushButton(tr("job_queue_view.cancel_button"))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        action_row.addWidget(self.pause_btn)
        action_row.addWidget(self.resume_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addStretch(1)
        detail_box.addLayout(action_row)
        root.addLayout(detail_box)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._reload)
        self._timer.start()

        self._reload()

    # --- Aktionen -------------------------------------------------------------

    def _on_pause_clicked(self) -> None:
        self._run_job_action(self.api.pause_job)

    def _on_resume_clicked(self) -> None:
        self._run_job_action(self.api.resume_job)

    def _on_cancel_clicked(self) -> None:
        if self._selected_job_id is None:
            return
        reply = QMessageBox.question(
            self,
            tr("job_queue_view.cancel_confirm_title"),
            tr("job_queue_view.cancel_confirm_text", job_id=self._selected_job_id),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._run_job_action(self.api.cancel_job)

    def _run_job_action(self, action) -> None:
        if self._selected_job_id is None:
            return
        try:
            action(self._selected_job_id)
        except GenesisAPIError as exc:
            show_api_error(self, exc)
            return
        self._reload()

    # --- Laden ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        item = self.tree.currentItem()
        self._selected_job_id = item.data(0, Qt.UserRole) if item else None
        self._update_detail_panel()

    def _update_detail_panel(self) -> None:
        job = self._jobs_by_id.get(self._selected_job_id) if self._selected_job_id else None
        if job is None:
            self.current_item_label.setText("")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            return

        # set_plain_text() statt .setText(): current_item ist ein
        # Dateipfad aus dem Core Service, kein fest im Quellcode stehender
        # Text - QLabel wuerde HTML-aehnlichen Inhalt sonst als Rich-Text
        # interpretieren (Deep-Review-Fund Sitzung 11).
        set_plain_text(
            self.current_item_label,
            tr("job_queue_view.current_item_label", item=job["current_item"] or "-"),
        )
        total = job["total_items"] or 0
        processed = job["processed_items"] or 0
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(processed, total))
        else:
            # Gesamtmenge unbekannt (z.B. Scan noch nicht abgeschlossen) ->
            # unbestimmter Fortschrittsbalken statt eines irrefuehrenden 0%.
            self.progress_bar.setRange(0, 0)

        status = job["status"]
        self.pause_btn.setEnabled(status == "running")
        self.resume_btn.setEnabled(status == "paused")
        self.cancel_btn.setEnabled(status in ACTIVE_STATUSES)

    def _reload(self) -> None:
        previously_selected = self._selected_job_id
        try:
            jobs = self.api.list_jobs(limit=100)
        except GenesisAPIError as exc:
            self.status_label.setText(tr("job_queue_view.load_failed", error=str(exc)))
            return

        self._jobs_by_id = {j["id"]: j for j in jobs}
        self.tree.clear()
        for job in jobs:
            total = job["total_items"] or 0
            processed = job["processed_items"] or 0
            progress_text = (
                f"{processed}/{total} ({processed / total:.0%})" if total > 0
                else tr("job_queue_view.progress_unknown")
            )
            status_key = STATUS_LABEL_KEYS.get(job["status"], job["status"])
            item = QTreeWidgetItem([
                job["id"],
                job["job_type"],
                tr(status_key),
                progress_text,
                str(job["error_count"]),
                str(job["warning_count"]),
                job["created_at"] or "-",
            ])
            item.setData(0, Qt.UserRole, job["id"])
            self.tree.addTopLevelItem(item)
            if job["id"] == previously_selected:
                self.tree.setCurrentItem(item)

        if not jobs:
            self.status_label.setText(tr("job_queue_view.no_jobs"))
        else:
            self.status_label.setText("")

        if previously_selected not in self._jobs_by_id:
            self._selected_job_id = None
        self._update_detail_panel()
