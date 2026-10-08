"""Hauptfenster der GENESIS Referenz-UI (Originalauftrag §4).

Nur EIN Client von zweien (siehe ARCHITECTURE.md ADR-0001) - dient als
Referenz-/Test-Oberflaeche waehrend der gesamten Entwicklung und laeuft
tatsaechlich in dieser Linux-Sandbox. Enthaelt bewusst keine Fachlogik,
nur Darstellung + Aufrufe der lokalen Core-API.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient
from genesis_ui.i18n import configure_default_language, tr
from genesis_ui.theme import DARK_STYLESHEET
from genesis_ui.views.ai_center_view import AICenterView
from genesis_ui.views.backups_view import BackupsView
from genesis_ui.views.dashboard import DashboardView
from genesis_ui.views.diagnostics_view import DiagnosticsView
from genesis_ui.views.download_center_view import DownloadCenterView
from genesis_ui.views.duplicates_view import DuplicatesView
from genesis_ui.views.error_center_view import ErrorCenterView
from genesis_ui.views.job_queue_view import JobQueueView
from genesis_ui.views.library_view import LibraryBrowserView
from genesis_ui.views.log_viewer_view import LogViewerView
from genesis_ui.views.media_table import MediaTableView
from genesis_ui.views.plugins_view import PluginsView
from genesis_ui.views.providers_view import ProvidersView
from genesis_ui.views.settings_view import SettingsView
from genesis_ui.views.voice_studio_view import VoiceStudioView

logger = logging.getLogger("genesis_ui.main_window")

# Navigationsstruktur exakt gemaess Originalauftrag §4. Labels/Detailtexte
# sind i18n-Schluessel (§53 - keine hartcodierten UI-Texte), aufgeloest in
# `_build_navigation`/`_create_page` erst beim tatsaechlichen Bauen der
# Oberflaeche (damit ein spaeterer Sprachwechsel zur Laufzeit moeglich
# bleibt, ohne diese Struktur anfassen zu muessen).
NAV_STRUCTURE = [
    ("nav.section_dashboard", None, [("nav.dashboard", "dashboard", None)]),
    (
        "nav.section_media",
        None,
        [
            ("nav.music", "media", "music"),
            ("nav.audiobook", "media", "audiobook"),
            ("nav.movie", "media", "movie"),
            ("nav.episode", "media", "episode"),
            ("nav.podcast", "media", "podcast_episode"),
            ("nav.ai_music", "media", "ai_music"),
            ("nav.unknown", "media", "unknown"),
        ],
    ),
    (
        "nav.section_library",
        None,
        [
            ("nav.search", "media", None),
            ("nav.artists", "library", "artists"),
            ("nav.albums", "library", "albums"),
            ("nav.titles", "library", "titles"),
            ("nav.genres", "library", "genres"),
            ("nav.persons", "library", "persons"),
            ("nav.sources", "library", "sources"),
        ],
    ),
    (
        "nav.section_tools",
        None,
        [
            ("nav.media_analysis", "placeholder", "nav.media_analysis_detail"),
            ("nav.metadata_editor", "placeholder", "nav.metadata_editor_detail"),
            ("nav.rename", "placeholder", "nav.rename_detail"),
            ("nav.loudness", "placeholder", "nav.loudness_detail"),
            ("nav.cutter", "placeholder", "nav.cutter_detail"),
            ("nav.convert", "placeholder", "nav.convert_detail"),
            ("nav.audio_recognition", "placeholder", "nav.audio_recognition_detail"),
            ("nav.duplicates", "duplicates", None),
            ("nav.quality_check", "placeholder", "nav.quality_check_detail"),
            ("nav.artwork", "placeholder", "nav.artwork_detail"),
        ],
    ),
    (
        "nav.section_download_import",
        None,
        [
            ("nav.download_center", "download_center", None),
            ("nav.import", "download_center", None),
            ("nav.sources", "library", "sources"),
        ],
    ),
    (
        "nav.section_ai",
        None,
        [
            ("nav.ai_metadata", "ai_center", None),
            ("nav.ai_audio_analysis", "placeholder", "nav.ai_audio_analysis_detail"),
            ("nav.voice_studio", "voice_studio", None),
            ("nav.tts", "voice_studio", None),
        ],
    ),
    (
        "nav.section_system",
        None,
        [
            ("nav.settings", "settings", None),
            ("nav.databases", "placeholder", "nav.databases_detail"),
            ("nav.providers", "providers", None),
            ("nav.plugins", "plugins", None),
            ("nav.licenses", "placeholder", "nav.licenses_detail"),
            ("nav.logs", "log_viewer", None),
            ("nav.backups", "backups", None),
            ("nav.diagnostics", "diagnostics", None),
            ("nav.job_queue", "job_queue", None),
            ("nav.error_center", "error_center", None),
        ],
    ),
]


class PlaceholderView(QWidget):
    def __init__(self, title_key: str, detail_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel(tr(detail_key))
        title.setObjectName("SectionTitle")
        note = QLabel(tr("app.placeholder_note"))
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self, api_base_url: str = "http://127.0.0.1:8420"):
        super().__init__()
        self.api = GenesisAPIClient(api_base_url)
        self._apply_language_from_settings()

        self.setWindowTitle(tr("app.window_title"))
        self.resize(1280, 800)
        self.setStyleSheet(DARK_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)

        brand = QLabel(tr("app.brand"))
        brand.setStyleSheet("font-weight: 700; font-size: 15px;")
        sidebar_layout.addWidget(brand)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        sidebar_layout.addWidget(self.tree)
        main_layout.addWidget(sidebar)

        # --- Content Area ---
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(56)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 8, 16, 8)
        global_search = QLineEdit()
        global_search.setPlaceholderText(tr("app.global_search_placeholder"))
        topbar_layout.addWidget(global_search)
        content_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, stretch=1)
        main_layout.addWidget(content, stretch=1)

        self._page_index: dict[str, int] = {}
        self._build_navigation()

        self.setStatusBar(QStatusBar())
        self._refresh_status()

    def _apply_language_from_settings(self) -> None:
        """Liest `general.language` beim Start einmalig vom Core Service
        (§53: Sprache ist eine GUI-Einstellung, kein manuell editiertes
        Konfigurationsfeld). Ist die API beim Start nicht erreichbar, bleibt
        es beim Default (Deutsch) - kein Absturz, kein stiller Blockzustand
        (Prinzip "kein stiller Fehlschlag")."""
        try:
            settings = self.api.get_settings()
            configure_default_language(settings["general"]["language"])
        except Exception:
            # Kein stiller Fehlschlag (Grundprinzip): mindestens protokollieren,
            # auch wenn der Nutzer bewusst beim Default (Deutsch) bleibt
            # (Deep-Review Sitzung 13/S110).
            logger.warning(
                "Konnte Sprache nicht vom Core Service laden, bleibe bei Default.",
                exc_info=True,
            )

    def _build_navigation(self) -> None:
        for section_key, _section_kind, entries in NAV_STRUCTURE:
            section_item = QTreeWidgetItem([tr(section_key)])
            section_item.setFlags(section_item.flags() & ~Qt.ItemIsSelectable)
            font = section_item.font(0)
            font.setBold(True)
            section_item.setFont(0, font)
            self.tree.addTopLevelItem(section_item)

            for label_key, page_type, page_arg in entries:
                child = QTreeWidgetItem([tr(label_key)])
                page_key = f"{page_type}:{page_arg}"
                if page_key not in self._page_index:
                    self._page_index[page_key] = self.stack.count()
                    self.stack.addWidget(self._create_page(label_key, page_type, page_arg))
                child.setData(0, Qt.UserRole, page_key)
                section_item.addChild(child)
            section_item.setExpanded(True)

        self.tree.itemClicked.connect(self._on_nav_clicked)
        if self.tree.topLevelItemCount() > 0:
            first_child = self.tree.topLevelItem(0).child(0)
            self.tree.setCurrentItem(first_child)
            self._on_nav_clicked(first_child, 0)

    def _create_page(self, label_key: str, page_type: str, page_arg: str | None) -> QWidget:
        if page_type == "dashboard":
            return DashboardView(self.api)
        if page_type == "media":
            return MediaTableView(self.api, kind=page_arg, title=tr(label_key))
        if page_type == "duplicates":
            return DuplicatesView(self.api)
        if page_type == "ai_center":
            return AICenterView(self.api)
        if page_type == "voice_studio":
            return VoiceStudioView(self.api)
        if page_type == "download_center":
            return DownloadCenterView(self.api)
        if page_type == "plugins":
            return PluginsView(self.api)
        if page_type == "backups":
            return BackupsView(self.api)
        if page_type == "diagnostics":
            return DiagnosticsView(self.api)
        if page_type == "job_queue":
            return JobQueueView(self.api)
        if page_type == "error_center":
            return ErrorCenterView(self.api)
        if page_type == "settings":
            return SettingsView(self.api)
        if page_type == "providers":
            return ProvidersView(self.api)
        if page_type == "library":
            return LibraryBrowserView(self.api, kind=page_arg, title=tr(label_key))
        if page_type == "log_viewer":
            return LogViewerView(self.api)
        # page_arg ist hier selbst ein i18n-Schluessel (z.B. "nav.artists_detail").
        return PlaceholderView(label_key, page_arg or label_key)

    def _on_nav_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        page_key = item.data(0, Qt.UserRole)
        if page_key is None:
            return
        self.stack.setCurrentIndex(self._page_index[page_key])

    def _refresh_status(self) -> None:
        try:
            health = self.api.health()
            mode = tr("app.state_on") if health["safe_test_mode"] else tr("app.state_off")
            self.statusBar().showMessage(
                tr("app.status_connected", version=health["version"], mode=mode)
            )
        except Exception:  # noqa: BLE001 - Verbindungspruefung darf nie abstuerzen
            self.statusBar().showMessage(tr("app.status_unreachable"))
