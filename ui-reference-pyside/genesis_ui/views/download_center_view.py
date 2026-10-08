"""Download-/Import-Center (§30-§32, Phase 8, ADR-0019).

Eigenstaendige Navigationsseite (analog zu `VoiceStudioView`/`AICenterView`)
mit zwei Tabs:

1. "URL / Online-Quelle": genau der §31-Workflow -
   URL eingeben -> Quelle erkennen -> Verfuegbarkeit pruefen -> Metadaten
   abrufen -> Downloadoptionen anzeigen -> (Benutzer bestaetigt per
   Dialog) -> Import. Jeder einzelne Vorschau-Schritt ist ein separater,
   expliziter Knopfdruck (keine automatische Verkettung) - der Nutzer sieht
   bei jedem Schritt genau, was als naechstes passieren wuerde, bevor er
   fortfaehrt (Prinzip #4/#5/#6).
2. "Lokale Datei": kontrollierter Import einer bereits vorhandenen lokalen
   Datei (Kopie, Original bleibt unangetastet).

Diese Seite ruft NIEMALS automatisch irgendetwas herunter - jeder Download/
Import erfordert einen expliziten Bestaetigungsdialog (§56, Prinzip #6).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
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
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


def _format_duration(seconds) -> str:
    if seconds is None:
        return tr("download_center.metadata_unknown")
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_size(num_bytes) -> str:
    if not num_bytes:
        return "-"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class DownloadCenterView(QWidget):
    def __init__(self, api: GenesisAPIClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self._detected_provider: str | None = None
        self._last_options: list[dict] = []
        self._selected_option_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel(tr("download_center.title"))
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        self.status_banner = QLabel("")
        self.status_banner.setWordWrap(True)
        self.status_banner.setStyleSheet("color: #9fb8d8;")
        root.addWidget(self.status_banner)

        legal_notice = QLabel(tr("download_center.legal_notice"))
        legal_notice.setWordWrap(True)
        legal_notice.setStyleSheet("color: #e0b84d;")
        root.addWidget(legal_notice)

        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)
        tabs.addTab(self._build_url_tab(), tr("download_center.tab_url"))
        tabs.addTab(self._build_local_tab(), tr("download_center.tab_local"))

        self._load_providers()

    # -- Status/Provider-Uebersicht -----------------------------------------

    def _load_providers(self) -> None:
        try:
            data = self.api.list_download_providers()
        except GenesisAPIError as exc:
            # Rohe Core-Fehlermeldung ganz ohne tr()-Wrapper - besonders
            # dynamisch, siehe genesis_ui.widgets-Moduldocstring.
            set_plain_text(self.status_banner, str(exc))
            return
        if not data.get("enabled", False):
            self.status_banner.setText(tr("download_center.status_disabled"))
            return
        names = ", ".join(p["display_name"] for p in data.get("providers", []))
        set_plain_text(self.status_banner, tr("download_center.status_enabled", providers=names))

    # -- Tab 1: URL / Online-Quelle ------------------------------------------

    def _build_url_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel(tr("download_center.url_label")))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(tr("download_center.url_placeholder"))
        url_row.addWidget(self.url_edit, stretch=1)
        layout.addLayout(url_row)

        button_row = QHBoxLayout()
        self.detect_btn = QPushButton(tr("download_center.detect_button"))
        self.detect_btn.clicked.connect(self._on_detect_clicked)
        button_row.addWidget(self.detect_btn)

        self.check_availability_btn = QPushButton(tr("download_center.check_availability_button"))
        self.check_availability_btn.clicked.connect(self._on_check_availability_clicked)
        button_row.addWidget(self.check_availability_btn)

        self.fetch_metadata_btn = QPushButton(tr("download_center.fetch_metadata_button"))
        self.fetch_metadata_btn.clicked.connect(self._on_fetch_metadata_clicked)
        button_row.addWidget(self.fetch_metadata_btn)

        self.list_options_btn = QPushButton(tr("download_center.list_options_button"))
        self.list_options_btn.clicked.connect(self._on_list_options_clicked)
        button_row.addWidget(self.list_options_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.options_tree = QTreeWidget()
        self.options_tree.setHeaderLabels(
            [tr("download_center.options_col_label"), tr("download_center.options_col_size")]
        )
        self.options_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.options_tree.itemSelectionChanged.connect(self._on_option_selection_changed)
        layout.addWidget(self.options_tree)

        self.import_btn = QPushButton(tr("download_center.import_button"))
        self.import_btn.clicked.connect(self._on_import_clicked)
        layout.addWidget(self.import_btn)

        self.url_result_log = QPlainTextEdit()
        self.url_result_log.setReadOnly(True)
        layout.addWidget(self.url_result_log, stretch=1)

        return page

    def _log(self, text: str) -> None:
        self.url_result_log.appendPlainText(text)

    def _current_url(self) -> str | None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, tr("download_center.title"), tr("download_center.url_required"))
            return None
        return url

    def _on_detect_clicked(self) -> None:
        url = self._current_url()
        if url is None:
            return
        try:
            result = self.api.detect_download_source(url)
        except GenesisAPIError as exc:
            self._log(tr("download_center.detect_failed", error=str(exc)))
            return
        self._detected_provider = result.get("provider_id")
        if self._detected_provider:
            self._log(tr("download_center.detected_provider", provider=result.get("display_name")))
        else:
            self._log(tr("download_center.detected_provider_none"))

    def _on_check_availability_clicked(self) -> None:
        url = self._current_url()
        if url is None:
            return
        self._log(tr("download_center.availability_checking"))
        try:
            result = self.api.check_download_availability(url)
        except GenesisAPIError as exc:
            self._log(tr("download_center.availability_failed", error=str(exc)))
            return
        if result.get("available"):
            self._log(tr("download_center.availability_available"))
        else:
            self._log(
                tr("download_center.availability_unavailable", reason=result.get("reason") or "-")
            )

    def _on_fetch_metadata_clicked(self) -> None:
        url = self._current_url()
        if url is None:
            return
        self._log(tr("download_center.metadata_fetching"))
        try:
            meta = self.api.fetch_download_metadata(url)
        except GenesisAPIError as exc:
            self._log(tr("download_center.metadata_failed", error=str(exc)))
            return
        unknown = tr("download_center.metadata_unknown")
        self._log(tr("download_center.metadata_title", title=meta.get("title") or unknown))
        self._log(tr("download_center.metadata_uploader", uploader=meta.get("uploader") or unknown))
        self._log(
            tr("download_center.metadata_duration", duration=_format_duration(meta.get("duration_seconds")))
        )
        self._log(tr("download_center.metadata_license", license=meta.get("license") or unknown))

    def _on_list_options_clicked(self) -> None:
        url = self._current_url()
        if url is None:
            return
        self.options_tree.clear()
        self._last_options = []
        try:
            result = self.api.list_download_options(url)
        except GenesisAPIError as exc:
            self._log(tr("download_center.options_failed", error=str(exc)))
            return
        options = result.get("options", [])
        self._last_options = options
        if not options:
            self._log(tr("download_center.options_none"))
            return
        for opt in options:
            item = QTreeWidgetItem([opt.get("label", opt.get("option_id", "")),
                                     _format_size(opt.get("approx_size_bytes"))])
            item.setData(0, 1, opt.get("option_id"))
            self.options_tree.addTopLevelItem(item)
        self.options_tree.setCurrentItem(self.options_tree.topLevelItem(0))

    def _on_option_selection_changed(self) -> None:
        items = self.options_tree.selectedItems()
        self._selected_option_id = items[0].data(0, 1) if items else None

    def _on_import_clicked(self) -> None:
        url = self._current_url()
        if url is None:
            return
        option_id = self._selected_option_id or "default"
        provider_label = self._detected_provider or "?"
        reply = QMessageBox.question(
            self,
            tr("download_center.confirm_import_title"),
            tr(
                "download_center.confirm_import_text",
                url=url, provider=provider_label, option=option_id,
            ),
        )
        if reply != QMessageBox.Yes:
            return
        self._log(tr("download_center.import_running"))
        try:
            result = self.api.import_download(url, option_id=option_id, confirm=True)
        except GenesisAPIError as exc:
            self._log(tr("download_center.import_failed", error=str(exc)))
            return
        self._report_import_result(result)

    def _report_import_result(self, result: dict) -> None:
        self._log(
            tr(
                "download_center.import_done",
                job_id=result.get("job_id"),
                media_id=result.get("media_file_id"),
                path=result.get("absolute_path"),
            )
        )
        warnings = result.get("warnings") or []
        if warnings:
            self._log(tr("download_center.import_warnings", warnings="; ".join(warnings)))
        suggested = result.get("suggested_filename")
        if suggested:
            self._log(tr("download_center.suggested_filename", name=suggested))

    # -- Tab 2: Lokale Datei --------------------------------------------------

    def _build_local_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel(tr("download_center.local_file_label")))
        self.local_path_edit = QLineEdit()
        path_row.addWidget(self.local_path_edit, stretch=1)
        browse_btn = QPushButton(tr("download_center.browse_button"))
        browse_btn.clicked.connect(self._on_browse_local_file)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.local_import_btn = QPushButton(tr("download_center.import_button"))
        self.local_import_btn.clicked.connect(self._on_local_import_clicked)
        layout.addWidget(self.local_import_btn)

        self.local_result_log = QPlainTextEdit()
        self.local_result_log.setReadOnly(True)
        layout.addWidget(self.local_result_log, stretch=1)

        return page

    def _on_browse_local_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("download_center.browse_title"))
        if path:
            self.local_path_edit.setText(path)

    def _on_local_import_clicked(self) -> None:
        path = self.local_path_edit.text().strip()
        if not path:
            QMessageBox.warning(
                self, tr("download_center.title"), tr("download_center.local_file_required")
            )
            return
        reply = QMessageBox.question(
            self,
            tr("download_center.confirm_local_import_title"),
            tr("download_center.confirm_local_import_text", path=path),
        )
        if reply != QMessageBox.Yes:
            return
        try:
            result = self.api.import_local_file(path, confirm=True)
        except GenesisAPIError as exc:
            self.local_result_log.appendPlainText(tr("download_center.import_failed", error=str(exc)))
            return
        self.local_result_log.appendPlainText(
            tr(
                "download_center.import_done",
                job_id=result.get("job_id"),
                media_id=result.get("media_file_id"),
                path=result.get("absolute_path"),
            )
        )
        warnings = result.get("warnings") or []
        if warnings:
            self.local_result_log.appendPlainText(
                tr("download_center.import_warnings", warnings="; ".join(warnings))
            )
