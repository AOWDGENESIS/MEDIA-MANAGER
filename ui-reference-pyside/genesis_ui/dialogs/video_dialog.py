"""Dialog für Filme & Serien (§24, Phase 5, ADR-0016).

Ablauf (Erkennen -> Vorschlag -> Confidence -> Vorschau -> Benutzerfreigabe
-> Änderung, Prinzip #4/#17), analog zum `AudiobookDialog` (ADR-0015):
1. Beim Öffnen werden bereits in der Datei eingebettete Tags gelesen
   (Film-Metadaten-Vorschau) sowie eine Film-vs-Episode-Erkennung
   durchgeführt (Tags + Dateipfad-Muster) - beides rein lesend.
2. Eine Übernahme als Film ODER als Episode erfordert eine explizite
   Bestätigung. Der Nutzer entscheidet selbst, welcher der beiden Fälle
   zutrifft (die Erkennung ist ein Vorschlag mit Confidence, kein
   automatisches Umschalten von `MediaFile.kind`).

Es gibt bewusst KEINEN Online-Provider (TMDb/IMDb etc. sind
Download/Import-Adapter, Phase 8) - siehe genesis_core/video/engine.py.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text


class VideoDialog(QDialog):
    def __init__(self, api: GenesisAPIClient, media_id: int, filename: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.media_id = media_id
        self.changed = False

        self.setWindowTitle(tr("video_dialog.window_title", filename=filename))
        self.resize(720, 560)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)

        tabs.addTab(self._build_movie_tab(), tr("video_dialog.tab_movie"))
        tabs.addTab(self._build_episode_tab(), tr("video_dialog.tab_episode"))

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton(tr("video_dialog.close_button"))
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._load_movie_tab()
        self._load_episode_tab()

    # --- Tab 1: Film -------------------------------------------------------------

    def _build_movie_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(tr("video_dialog.movie_info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.movie_status_label = QLabel(tr("video_dialog.loading"))
        layout.addWidget(self.movie_status_label)

        form = QFormLayout()
        self.movie_title_label = QLabel()
        self.movie_year_label = QLabel()
        self.movie_genre_label = QLabel()
        self.movie_director_label = QLabel()
        self.movie_actors_label = QLabel()
        self.movie_description_label = QLabel()
        for widget in (
            self.movie_title_label, self.movie_year_label, self.movie_genre_label,
            self.movie_director_label, self.movie_actors_label, self.movie_description_label,
        ):
            widget.setWordWrap(True)
        form.addRow(tr("video_dialog.field_title"), self.movie_title_label)
        form.addRow(tr("video_dialog.field_year"), self.movie_year_label)
        form.addRow(tr("video_dialog.field_genre"), self.movie_genre_label)
        form.addRow(tr("video_dialog.field_director"), self.movie_director_label)
        form.addRow(tr("video_dialog.field_actors"), self.movie_actors_label)
        form.addRow(tr("video_dialog.field_description"), self.movie_description_label)
        layout.addLayout(form)

        self.movie_persisted_label = QLabel(tr("video_dialog.not_saved_yet"))
        self.movie_persisted_label.setWordWrap(True)
        self.movie_persisted_label.setStyleSheet("color: #8fbf8f;")
        layout.addWidget(self.movie_persisted_label)

        btn_row = QHBoxLayout()
        self.apply_movie_btn = QPushButton(tr("video_dialog.apply_movie_button"))
        self.apply_movie_btn.setEnabled(False)
        self.apply_movie_btn.clicked.connect(self._on_apply_movie_clicked)
        btn_row.addWidget(self.apply_movie_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return tab

    def _load_movie_tab(self) -> None:
        empty = tr("common.value_empty")
        try:
            tags = self.api.get_video_tags_preview(self.media_id)
        except GenesisAPIError as exc:
            set_plain_text(self.movie_status_label, tr("video_dialog.load_failed", error=exc))
            return

        if not tags.get("has_any_tag"):
            self.movie_status_label.setText(tr("video_dialog.no_tags_found"))
        else:
            self.movie_status_label.setText(tr("video_dialog.tags_found"))

        # Deep-Review-Fund (Sitzung 11, Fortsetzung): alle Werte stammen aus
        # eingebetteten Datei-Tags (externer Inhalt) - set_plain_text()
        # statt setText() verhindert Qt.AutoText-Fehlinterpretation.
        set_plain_text(self.movie_title_label, tags.get("title") or empty)
        self.movie_year_label.setText(str(tags.get("year")) if tags.get("year") else empty)
        set_plain_text(self.movie_genre_label, tags.get("genre") or empty)
        directors = tags.get("director_names") or []
        actors = tags.get("actor_names") or []
        set_plain_text(self.movie_director_label, ", ".join(directors) if directors else empty)
        set_plain_text(self.movie_actors_label, ", ".join(actors) if actors else empty)
        set_plain_text(self.movie_description_label, tags.get("description") or empty)

        self.apply_movie_btn.setEnabled(bool(tags.get("has_any_tag")))
        self._reload_persisted_movie()

    def _reload_persisted_movie(self) -> None:
        try:
            saved = self.api.get_movie(self.media_id)
        except GenesisAPIError:
            saved = None
        if saved is None:
            self.movie_persisted_label.setText(tr("video_dialog.not_saved_yet"))
        else:
            set_plain_text(
                self.movie_persisted_label,
                tr(
                    "video_dialog.movie_saved_summary",
                    title=saved.get("title") or tr("common.value_empty"),
                    year=saved.get("year") or tr("common.value_empty"),
                ),
            )

    def _on_apply_movie_clicked(self) -> None:
        confirm = QMessageBox.question(
            self,
            tr("video_dialog.confirm_movie_title"),
            tr("video_dialog.confirm_movie_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.api.apply_movie_metadata(self.media_id, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("video_dialog.apply_movie_failed", error=exc))
            return
        self.changed = True
        self._reload_persisted_movie()
        QMessageBox.information(
            self, tr("video_dialog.applied_title"), tr("video_dialog.movie_applied_text")
        )

    # --- Tab 2: Serie/Episode ------------------------------------------------------

    def _build_episode_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(tr("video_dialog.episode_info"))
        info.setWordWrap(True)
        layout.addWidget(info)

        self.episode_status_label = QLabel(tr("video_dialog.loading"))
        layout.addWidget(self.episode_status_label)

        form = QFormLayout()
        self.episode_series_label = QLabel()
        self.episode_season_label = QLabel()
        self.episode_number_label = QLabel()
        self.episode_title_label = QLabel()
        self.episode_confidence_label = QLabel()
        for widget in (
            self.episode_series_label, self.episode_season_label, self.episode_number_label,
            self.episode_title_label, self.episode_confidence_label,
        ):
            widget.setWordWrap(True)
        form.addRow(tr("video_dialog.field_series"), self.episode_series_label)
        form.addRow(tr("video_dialog.field_season"), self.episode_season_label)
        form.addRow(tr("video_dialog.field_episode_number"), self.episode_number_label)
        form.addRow(tr("video_dialog.field_title"), self.episode_title_label)
        form.addRow(tr("video_dialog.field_confidence"), self.episode_confidence_label)
        layout.addLayout(form)

        self.episode_persisted_label = QLabel(tr("video_dialog.not_saved_yet"))
        self.episode_persisted_label.setWordWrap(True)
        self.episode_persisted_label.setStyleSheet("color: #8fbf8f;")
        layout.addWidget(self.episode_persisted_label)

        btn_row = QHBoxLayout()
        self.apply_episode_btn = QPushButton(tr("video_dialog.apply_episode_button"))
        self.apply_episode_btn.setEnabled(False)
        self.apply_episode_btn.clicked.connect(self._on_apply_episode_clicked)
        btn_row.addWidget(self.apply_episode_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return tab

    def _load_episode_tab(self) -> None:
        empty = tr("common.value_empty")
        try:
            result = self.api.detect_episode_preview(self.media_id)
        except GenesisAPIError as exc:
            set_plain_text(self.episode_status_label, tr("video_dialog.load_failed", error=exc))
            return

        if result.get("is_likely_episode"):
            self.episode_status_label.setText(tr("video_dialog.episode_likely"))
        else:
            self.episode_status_label.setText(tr("video_dialog.episode_unlikely"))

        def _with_source(value, source) -> str:
            if value is None:
                return empty
            if source:
                return f"{value}  ({tr(f'video_dialog.source_{source}')})"
            return str(value)

        # Deep-Review-Fund (Sitzung 11, Fortsetzung): series/title stammen
        # aus erkannten Datei-/Pfadnamen (externer Inhalt).
        set_plain_text(
            self.episode_series_label,
            _with_source(result.get("series_name"), result.get("series_source")),
        )
        self.episode_season_label.setText(
            _with_source(result.get("season_number"), result.get("season_source"))
        )
        self.episode_number_label.setText(
            _with_source(result.get("episode_number"), result.get("episode_source"))
        )
        set_plain_text(
            self.episode_title_label,
            _with_source(result.get("title"), result.get("title_source")),
        )
        self.episode_confidence_label.setText(f"{result.get('confidence', 0.0):.0%}")

        self.apply_episode_btn.setEnabled(bool(result.get("is_likely_episode")))
        self._reload_persisted_episode()

    def _reload_persisted_episode(self) -> None:
        try:
            saved = self.api.get_episode(self.media_id)
        except GenesisAPIError:
            saved = None
        if saved is None:
            self.episode_persisted_label.setText(tr("video_dialog.not_saved_yet"))
        else:
            set_plain_text(
                self.episode_persisted_label,
                tr(
                    "video_dialog.episode_saved_summary",
                    series=saved.get("series") or tr("common.value_empty"),
                    season=saved.get("season_number") or tr("common.value_empty"),
                    episode=saved.get("episode_number") or tr("common.value_empty"),
                ),
            )

    def _on_apply_episode_clicked(self) -> None:
        confirm = QMessageBox.question(
            self,
            tr("video_dialog.confirm_episode_title"),
            tr("video_dialog.confirm_episode_text"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.api.apply_episode_metadata(self.media_id, confirm=True)
        except GenesisAPIError as exc:
            show_api_error(self, exc, message=tr("video_dialog.apply_episode_failed", error=exc))
            return
        self.changed = True
        self._reload_persisted_episode()
        QMessageBox.information(
            self, tr("video_dialog.applied_title"), tr("video_dialog.episode_applied_text")
        )
