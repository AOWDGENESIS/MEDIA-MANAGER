"""Bibliotheks-Drill-down (nav.artists/albums/titles/genres/persons/sources,
§9/§62, Gap-Analyse B).

Loest die bisherigen reinen Navigations-Platzhalter fuer Interpreten,
Alben, Titel, Genres, Personen und Quellen ab - EINE gemeinsame,
parametrisierte View (statt sechs fast identischer Kopien), da sich alle
sechs auf dasselbe Muster abbilden lassen: durchsuchbare Liste (links/oben)
+ Detailbereich (rechts/unten), rein lesend (Prinzip #4/#5 - keine
Schreibzugriffe, daher keine Bestaetigungsdialoge noetig).

Bei Interpreten/Alben/Genres/Personen laedt ein Klick auf eine Zeile einen
ZUSAETZLICHEN Detail-Request (`get_library_<kind>_detail`), da die
Listen-Antwort nur Aggregatwerte enthaelt (z.B. Alben-/Titelanzahl, nicht
die Alben/Titel selbst). Bei Titeln und Quellen enthaelt die Listen-
Antwort bereits alle Felder - dort wird NUR aus den bereits geladenen
Zeilendaten gerendert, ohne weiteren Netzwerk-Roundtrip.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError
from genesis_ui.dialogs.error_dialog import show_api_error
from genesis_ui.i18n import tr


def _fmt(value: Any) -> str:
    """Einheitliche Leerwert-Darstellung (`-`) statt `None`/`""` roh
    anzuzeigen - konsistent mit `common.value_empty` an anderen Stellen."""
    if value is None or value == "":
        return tr("library_view.value_none")
    return str(value)


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return tr("library_view.value_none")
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


_ROLE_KEYS = {
    "artist": "library_view.persons.role_artist",
    "actor": "library_view.persons.role_actor",
    "director": "library_view.persons.role_director",
    "author": "library_view.persons.role_author",
    "narrator": "library_view.persons.role_narrator",
    "composer": "library_view.persons.role_composer",
    "publisher": "library_view.persons.role_publisher",
}

_WORK_KIND_KEYS = {
    "movie": "library_view.persons.work_movie",
    "episode": "library_view.persons.work_episode",
    "audiobook": "library_view.persons.work_audiobook",
    "track": "library_view.persons.work_track",
}


class LibraryBrowserView(QWidget):
    """`kind` in {"artists", "albums", "titles", "genres", "persons",
    "sources"} - siehe `main_window.NAV_STRUCTURE`."""

    def __init__(self, api: GenesisAPIClient, kind: str, title: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.kind = kind
        self._rows: dict[int, dict] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QLabel(title)
        header.setObjectName("SectionTitle")
        root.addWidget(header)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("library_view.search_placeholder"))
        self.search_edit.returnPressed.connect(self._reload)
        search_row.addWidget(self.search_edit, stretch=1)
        search_btn = QPushButton(tr("library_view.search_button"))
        search_btn.clicked.connect(self._reload)
        search_row.addWidget(search_btn)
        refresh_btn = QPushButton(tr("library_view.refresh_button"))
        refresh_btn.clicked.connect(self._reload)
        search_row.addWidget(refresh_btn)
        root.addLayout(search_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        columns = _COLUMN_SPECS[kind]
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr(header_key) for header_key, _field in columns])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlainText(tr("library_view.detail_placeholder"))

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.detail_text)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        self._reload()

    # -- Laden -------------------------------------------------------------

    def _reload(self) -> None:
        self.tree.clear()
        self._rows.clear()
        self.detail_text.setPlainText(tr("library_view.detail_placeholder"))
        search = self.search_edit.text().strip() or None
        try:
            rows = _LIST_FNS[self.kind](self.api, search)
        except GenesisAPIError as exc:
            self.status_label.setText(tr("library_view.load_failed", error=str(exc)))
            return
        self.status_label.setText("" if rows else tr("library_view.no_items"))
        columns = _COLUMN_SPECS[self.kind]
        for row in rows:
            self._rows[row["id"]] = row
            values = [_render_cell(row.get(field)) for _header, field in columns]
            item = QTreeWidgetItem(values)
            item.setData(0, Qt.UserRole, row["id"])
            self.tree.addTopLevelItem(item)

    # -- Auswahl / Detail ----------------------------------------------------

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            self.detail_text.setPlainText(tr("library_view.detail_placeholder"))
            return
        row_id = items[0].data(0, Qt.UserRole)
        row = self._rows.get(row_id)
        if row is None:
            return
        detail_fn = _DETAIL_FNS.get(self.kind)
        if detail_fn is None:
            # titles/sources: Zeile selbst enthaelt bereits alle Felder.
            self.detail_text.setPlainText(_RENDER_FNS[self.kind](row))
            return
        try:
            detail = detail_fn(self.api, row_id)
        except GenesisAPIError as exc:
            self.detail_text.setPlainText(tr("library_view.detail_load_failed", error=str(exc)))
            show_api_error(self, exc)
            return
        self.detail_text.setPlainText(_RENDER_FNS[self.kind](detail))


def _render_cell(value: Any) -> str:
    if value is None:
        return tr("library_view.value_none")
    return str(value)


# --- Pro-Kind-Konfiguration ---------------------------------------------------

_COLUMN_SPECS: dict[str, list[tuple[str, str]]] = {
    "artists": [
        ("library_view.artists.col_name", "name"),
        ("library_view.artists.col_sort_name", "sort_name"),
        ("library_view.artists.col_albums", "album_count"),
        ("library_view.artists.col_tracks", "track_count"),
    ],
    "albums": [
        ("library_view.albums.col_title", "title"),
        ("library_view.albums.col_artist", "artist_name"),
        ("library_view.albums.col_year", "year"),
        ("library_view.albums.col_tracks", "track_count"),
    ],
    "titles": [
        ("library_view.titles.col_title", "title"),
        ("library_view.titles.col_artist", "artist_name"),
        ("library_view.titles.col_album", "album_title"),
        ("library_view.titles.col_genre", "genre_name"),
        ("library_view.titles.col_year", "year"),
    ],
    "genres": [
        ("library_view.genres.col_name", "name"),
        ("library_view.genres.col_tracks", "track_count"),
    ],
    "persons": [
        ("library_view.persons.col_name", "name"),
        ("library_view.persons.col_roles", "role_count"),
    ],
    "sources": [
        ("library_view.sources.col_filename", "filename"),
        ("library_view.sources.col_source_name", "source_name"),
        ("library_view.sources.col_provider", "provider_name"),
        ("library_view.sources.col_imported_at", "imported_at"),
    ],
}


def _list_artists(api: GenesisAPIClient, search: str | None) -> list[dict]:
    return api.list_library_artists(search)


def _list_albums(api: GenesisAPIClient, search: str | None) -> list[dict]:
    return api.list_library_albums(search)


def _list_titles(api: GenesisAPIClient, search: str | None) -> list[dict]:
    return api.list_library_tracks(search)["items"]


def _list_genres(api: GenesisAPIClient, search: str | None) -> list[dict]:
    return api.list_library_genres(search)


def _list_persons(api: GenesisAPIClient, search: str | None) -> list[dict]:
    return api.list_library_persons(search)


def _list_sources(api: GenesisAPIClient, search: str | None) -> list[dict]:
    return api.list_library_sources(search)["items"]


_LIST_FNS: dict[str, Callable[[GenesisAPIClient, str | None], list[dict]]] = {
    "artists": _list_artists,
    "albums": _list_albums,
    "titles": _list_titles,
    "genres": _list_genres,
    "persons": _list_persons,
    "sources": _list_sources,
}

_DETAIL_FNS: dict[str, Callable[[GenesisAPIClient, int], dict]] = {
    "artists": lambda api, row_id: api.get_library_artist_detail(row_id),
    "albums": lambda api, row_id: api.get_library_album_detail(row_id),
    "genres": lambda api, row_id: api.get_library_genre_detail(row_id),
    "persons": lambda api, row_id: api.get_library_person_detail(row_id),
}


def _render_artist_detail(detail: dict) -> str:
    lines = [
        tr("library_view.artists.detail_name", value=_fmt(detail["name"])),
        tr("library_view.artists.detail_sort_name", value=_fmt(detail["sort_name"])),
        tr("library_view.artists.detail_musicbrainz_id", value=_fmt(detail["musicbrainz_id"])),
        "",
        tr("library_view.artists.detail_albums_header", count=len(detail["albums"])),
    ]
    if not detail["albums"]:
        lines.append(tr("library_view.artists.detail_albums_none"))
    for album in detail["albums"]:
        lines.append(tr(
            "library_view.artists.detail_album_entry",
            title=_fmt(album["title"]), year=_fmt(album["year"]), count=album["track_count"],
        ))
    return "\n".join(lines)


def _render_album_detail(detail: dict) -> str:
    lines = [
        tr("library_view.albums.detail_title", value=_fmt(detail["title"])),
        tr("library_view.albums.detail_artist", value=_fmt(detail["artist_name"])),
        tr("library_view.albums.detail_year", value=_fmt(detail["year"])),
        tr("library_view.albums.detail_musicbrainz_id", value=_fmt(detail["musicbrainz_id"])),
        "",
        tr("library_view.albums.detail_tracks_header", count=len(detail["tracks"])),
    ]
    if not detail["tracks"]:
        lines.append(tr("library_view.albums.detail_tracks_none"))
    for t in detail["tracks"]:
        disc = t["disc_number"] or 1
        number = t["track_number"] if t["track_number"] is not None else "?"
        position = f"{disc}.{number}"
        lines.append(tr(
            "library_view.albums.detail_track_entry",
            position=position, title=_fmt(t["title"]), duration=_fmt_duration(t["duration_seconds"]),
        ))
    return "\n".join(lines)


def _render_title_detail(row: dict) -> str:
    return "\n".join([
        tr("library_view.titles.detail_title", value=_fmt(row["title"])),
        tr("library_view.titles.detail_artist", value=_fmt(row["artist_name"])),
        tr("library_view.titles.detail_album", value=_fmt(row["album_title"])),
        tr("library_view.titles.detail_genre", value=_fmt(row["genre_name"])),
        tr("library_view.titles.detail_year", value=_fmt(row["year"])),
        tr("library_view.titles.detail_track_number", value=_fmt(row["track_number"])),
        tr("library_view.titles.detail_duration", value=_fmt_duration(row["duration_seconds"])),
        tr("library_view.titles.detail_media_file_id", value=_fmt(row["media_file_id"])),
    ])


def _render_genre_detail(detail: dict) -> str:
    lines = [
        tr("library_view.genres.detail_name", value=_fmt(detail["name"])),
        "",
        tr("library_view.genres.detail_tracks_header", count=len(detail["tracks"])),
    ]
    if not detail["tracks"]:
        lines.append(tr("library_view.genres.detail_tracks_none"))
    for t in detail["tracks"]:
        album = t["album_title"] or tr("library_view.genres.no_album")
        lines.append(tr(
            "library_view.genres.detail_track_entry",
            title=_fmt(t["title"]), artist=_fmt(t["artist_name"]), album=album,
        ))
    return "\n".join(lines)


def _render_person_detail(detail: dict) -> str:
    lines = [
        tr("library_view.persons.detail_name", value=_fmt(detail["name"])),
        "",
        tr("library_view.persons.detail_roles_header", count=len(detail["roles"])),
    ]
    if not detail["roles"]:
        lines.append(tr("library_view.persons.detail_roles_none"))
    for r in detail["roles"]:
        role_label = tr(_ROLE_KEYS.get(r["role"], "library_view.value_none"))
        work_label = tr(_WORK_KIND_KEYS.get(r["work_kind"], "library_view.value_none"))
        lines.append(tr(
            "library_view.persons.detail_role_entry",
            role=role_label, work_kind=work_label, title=_fmt(r["work_title"]),
        ))
    return "\n".join(lines)


def _render_source_detail(row: dict) -> str:
    return "\n".join([
        tr("library_view.sources.detail_filename", value=_fmt(row["filename"])),
        tr("library_view.sources.detail_source_name", value=_fmt(row["source_name"])),
        tr("library_view.sources.detail_provider", value=_fmt(row["provider_name"])),
        tr("library_view.sources.detail_url", value=_fmt(row["original_url"])),
        tr("library_view.sources.detail_original_id", value=_fmt(row["original_id"])),
        tr("library_view.sources.detail_imported_at", value=_fmt(row["imported_at"])),
        tr("library_view.sources.detail_import_method", value=_fmt(row["import_method"])),
        tr("library_view.sources.detail_media_file_id", value=_fmt(row["media_file_id"])),
    ])


_RENDER_FNS: dict[str, Callable[[dict], str]] = {
    "artists": _render_artist_detail,
    "albums": _render_album_detail,
    "titles": _render_title_detail,
    "genres": _render_genre_detail,
    "persons": _render_person_detail,
    "sources": _render_source_detail,
}
