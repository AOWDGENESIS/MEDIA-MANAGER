"""Tests für die Bibliotheks-Drill-down-API (§9/§62, Gap-Analyse B).

Interpreten/Alben/Titel/Genres/Personen/Quellen - rein lesende
Browsing-Endpunkte oberhalb bestehender Tabellen (genesis_core.library).
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import (
    Album,
    Artist,
    Genre,
    MediaFile,
    MediaKind,
    Person,
    PersonRole,
    PersonRoleType,
    Source,
    Track,
)


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_library(app, tmp_path: Path) -> dict:
    with app.state.genesis.db.session() as session:
        artist = Artist(name="Die Toten Hosen", sort_name="Toten Hosen, Die")
        session.add(artist)
        session.flush()

        album = Album(title="Opium fürs Volk", artist_id=artist.id, year=1996)
        session.add(album)
        session.flush()

        genre = Genre(name="Punk Rock")
        session.add(genre)
        session.flush()

        mf1 = MediaFile(
            absolute_path=str(tmp_path / "t1.mp3"), directory=str(tmp_path),
            filename="t1.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=123,
        )
        mf2 = MediaFile(
            absolute_path=str(tmp_path / "t2.mp3"), directory=str(tmp_path),
            filename="t2.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=456,
        )
        session.add_all([mf1, mf2])
        session.flush()

        track1 = Track(
            media_file_id=mf1.id, title="Alles aus Liebe", album_id=album.id,
            genre_id=genre.id, track_number=1, year=1996,
        )
        # Titel ohne Album-Zuordnung, aber mit freitextlichem album_artist
        # (bewusster Test der in library.py dokumentierten Modellgrenze).
        track2 = Track(
            media_file_id=mf2.id, title="Nur zu Besuch", album_artist="Die Toten Hosen",
            genre_id=genre.id, year=2002,
        )
        session.add_all([track1, track2])
        session.flush()

        source = Source(
            media_file_id=mf1.id, source_name="YouTube Download",
            provider_name="youtube", original_url="https://youtube.example/x",
            import_method="download",
        )
        session.add(source)

        person = Person(name="Campino")
        session.add(person)
        session.flush()
        session.add(PersonRole(person_id=person.id, role=PersonRoleType.ARTIST, track_id=track1.id))
        session.flush()

        return {
            "artist_id": artist.id, "album_id": album.id, "genre_id": genre.id,
            "track1_id": track1.id, "track2_id": track2.id, "person_id": person.id,
        }


def test_list_and_detail_artists(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    ids = _seed_library(app, tmp_path)

    resp = client.get("/library/artists")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Die Toten Hosen"
    assert items[0]["album_count"] == 1
    assert items[0]["track_count"] == 1  # nur track1 ist einem Album zugeordnet

    resp = client.get(f"/library/artists/{ids['artist_id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["name"] == "Die Toten Hosen"
    assert len(detail["albums"]) == 1
    assert detail["albums"][0]["title"] == "Opium fürs Volk"

    assert client.get("/library/artists/999999").status_code == 404


def test_list_and_detail_albums(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    ids = _seed_library(app, tmp_path)

    resp = client.get("/library/albums")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["artist_name"] == "Die Toten Hosen"
    assert items[0]["track_count"] == 1

    resp = client.get(f"/library/albums/{ids['album_id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["title"] == "Opium fürs Volk"
    assert len(detail["tracks"]) == 1
    assert detail["tracks"][0]["title"] == "Alles aus Liebe"

    assert client.get("/library/albums/999999").status_code == 404


def test_list_tracks_includes_album_artist_fallback(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_library(app, tmp_path)

    resp = client.get("/library/tracks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    titles = {i["title"]: i for i in body["items"]}
    assert titles["Alles aus Liebe"]["artist_name"] == "Die Toten Hosen"
    # Titel ohne Album -> artist_name faellt auf album_artist zurueck
    assert titles["Nur zu Besuch"]["artist_name"] == "Die Toten Hosen"
    assert titles["Nur zu Besuch"]["album_title"] is None

    resp = client.get("/library/tracks", params={"search": "Liebe"})
    assert resp.json()["total"] == 1


def test_list_and_detail_genres(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    ids = _seed_library(app, tmp_path)

    resp = client.get("/library/genres")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Punk Rock"
    assert items[0]["track_count"] == 2

    resp = client.get(f"/library/genres/{ids['genre_id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["tracks"]) == 2

    assert client.get("/library/genres/999999").status_code == 404


def test_list_and_detail_persons(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    ids = _seed_library(app, tmp_path)

    resp = client.get("/library/persons")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Campino"
    assert items[0]["role_count"] == 1

    resp = client.get(f"/library/persons/{ids['person_id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["roles"]) == 1
    assert detail["roles"][0]["role"] == "artist"
    assert detail["roles"][0]["work_kind"] == "track"
    assert detail["roles"][0]["work_title"] == "Alles aus Liebe"

    assert client.get("/library/persons/999999").status_code == 404


def test_list_sources(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _seed_library(app, tmp_path)

    resp = client.get("/library/sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["provider_name"] == "youtube"
    assert body["items"][0]["filename"] == "t1.mp3"

    resp = client.get("/library/sources", params={"search": "nonexistent-provider"})
    assert resp.json()["total"] == 0


def test_library_endpoints_require_token(tmp_path):
    app = _make_app(tmp_path)
    no_token_client = TestClient(app)
    for url in (
        "/library/artists", "/library/albums", "/library/tracks",
        "/library/genres", "/library/persons", "/library/sources",
    ):
        assert no_token_client.get(url).status_code in (401, 403)
