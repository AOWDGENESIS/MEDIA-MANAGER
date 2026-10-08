"""Tests für `LibraryBrowserView` (nav.artists/albums/titles/genres/
persons/sources, §9/§62, Gap-Analyse B).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.api_client import GenesisAPIError  # noqa: E402
from genesis_ui.views.library_view import LibraryBrowserView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeLibraryAPI:
    def __init__(self):
        self.list_should_fail = False
        self.detail_should_fail = False

    def _maybe_fail(self):
        if self.list_should_fail:
            raise GenesisAPIError("simuliert: Core nicht erreichbar")

    def list_library_artists(self, search=None):
        self._maybe_fail()
        rows = [
            {"id": 1, "name": "Die Toten Hosen", "sort_name": "Toten Hosen, Die",
             "album_count": 1, "track_count": 1},
            {"id": 2, "name": "Kraftklub", "sort_name": "Kraftklub", "album_count": 0,
             "track_count": 0},
        ]
        if search:
            rows = [r for r in rows if search.lower() in r["name"].lower()]
        return rows

    def get_library_artist_detail(self, artist_id):
        if self.detail_should_fail:
            raise GenesisAPIError("simuliert: Detail fehlgeschlagen")
        if artist_id == 1:
            return {
                "id": 1, "name": "Die Toten Hosen", "sort_name": "Toten Hosen, Die",
                "musicbrainz_id": "mb-123",
                "albums": [{"id": 1, "title": "Opium fürs Volk", "artist_id": 1,
                            "artist_name": "Die Toten Hosen", "year": 1996, "track_count": 1}],
            }
        return {"id": 2, "name": "Kraftklub", "sort_name": "Kraftklub",
                "musicbrainz_id": None, "albums": []}

    def list_library_albums(self, search=None):
        self._maybe_fail()
        return [{"id": 1, "title": "Opium fürs Volk", "artist_id": 1,
                  "artist_name": "Die Toten Hosen", "year": 1996, "track_count": 1}]

    def get_library_album_detail(self, album_id):
        return {
            "id": 1, "title": "Opium fürs Volk", "artist_id": 1,
            "artist_name": "Die Toten Hosen", "year": 1996, "musicbrainz_id": None,
            "tracks": [{"id": 1, "media_file_id": 1, "title": "Alles aus Liebe",
                        "track_number": 1, "disc_number": None, "duration_seconds": 215.0}],
        }

    def list_library_tracks(self, search=None):
        self._maybe_fail()
        items = [{"id": 1, "media_file_id": 1, "title": "Alles aus Liebe",
                  "artist_name": "Die Toten Hosen", "album_title": "Opium fürs Volk",
                  "genre_name": "Punk Rock", "year": 1996, "track_number": 1,
                  "duration_seconds": 215.0}]
        return {"total": len(items), "items": items}

    def list_library_genres(self, search=None):
        self._maybe_fail()
        return [{"id": 1, "name": "Punk Rock", "track_count": 1}]

    def get_library_genre_detail(self, genre_id):
        return {"id": 1, "name": "Punk Rock",
                "tracks": [{"id": 1, "media_file_id": 1, "title": "Alles aus Liebe",
                            "artist_name": "Die Toten Hosen", "album_title": "Opium fürs Volk",
                            "genre_name": "Punk Rock", "year": 1996, "track_number": 1,
                            "duration_seconds": 215.0}]}

    def list_library_persons(self, search=None):
        self._maybe_fail()
        return [{"id": 1, "name": "Campino", "role_count": 1}]

    def get_library_person_detail(self, person_id):
        return {"id": 1, "name": "Campino",
                "roles": [{"role": "artist", "work_kind": "track", "work_id": 1,
                           "work_title": "Alles aus Liebe", "media_file_id": 1}]}

    def list_library_sources(self, search=None):
        self._maybe_fail()
        items = [{"id": 1, "media_file_id": 1, "filename": "t1.mp3",
                  "source_name": "YouTube Download", "provider_name": "youtube",
                  "original_url": "https://x", "original_id": "abc",
                  "imported_at": "2024-01-01T00:00:00", "import_method": "download"}]
        return {"total": len(items), "items": items}


def test_artists_list_and_detail(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="artists", title="Interpreten")
    assert view.tree.topLevelItemCount() == 2
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    text = view.detail_text.toPlainText()
    assert "Die Toten Hosen" in text
    assert "Opium fürs Volk" in text
    assert "1996" in text


def test_artists_search_filters_list(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="artists", title="Interpreten")
    view.search_edit.setText("Kraftklub")
    view._reload()
    assert view.tree.topLevelItemCount() == 1
    assert view.tree.topLevelItem(0).text(0) == "Kraftklub"


def test_albums_detail_shows_tracks(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="albums", title="Alben")
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    text = view.detail_text.toPlainText()
    assert "Alles aus Liebe" in text
    assert "3:35" in text


def test_titles_detail_uses_row_data_without_extra_call(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="titles", title="Titel")
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    text = view.detail_text.toPlainText()
    assert "Alles aus Liebe" in text
    assert "Punk Rock" in text
    assert "Opium fürs Volk" in text


def test_genres_detail(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="genres", title="Genres")
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    text = view.detail_text.toPlainText()
    assert "Alles aus Liebe" in text
    assert "Die Toten Hosen" in text


def test_persons_detail_renders_role_and_work_labels(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="persons", title="Personen")
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    text = view.detail_text.toPlainText()
    assert "Interpret" in text  # uebersetztes role label fuer "artist"
    assert "Musiktitel" in text  # uebersetztes work_kind label fuer "track"
    assert "Alles aus Liebe" in text


def test_sources_detail_uses_row_data(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="sources", title="Quellen")
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    text = view.detail_text.toPlainText()
    assert "youtube" in text
    assert "t1.mp3" in text


def test_list_load_failure_shows_status_message(qapp):
    api = _FakeLibraryAPI()
    api.list_should_fail = True
    view = LibraryBrowserView(api, kind="artists", title="Interpreten")
    assert "simuliert" in view.status_label.text()
    assert view.tree.topLevelItemCount() == 0


def test_empty_list_shows_no_items_hint(qapp):
    api = _FakeLibraryAPI()
    view = LibraryBrowserView(api, kind="artists", title="Interpreten")
    view.search_edit.setText("nonexistent-xyz")
    view._reload()
    assert view.tree.topLevelItemCount() == 0
    assert view.status_label.text() != ""
