"""Tests für die erweiterte Mediensuche/-filterung über `GET /media` (§9,
Gap-Analyse Gap C).

Deckt die in §9 geforderten Such-/Filterfelder ab, die vorher NICHT per API
ansteuerbar waren: Interpret/Album/Genre/Autor/Sprecher/Serie/Quelle (über
`search` sowie dedizierte Parameter), Jahr, Format, Dateigröße, Dauer,
Lautheit, Qualitätsverdacht, fehlende Metadaten, fehlendes Cover, Duplikate,
KI-Status. Rein lesend - erzeugt eine eigene, isolierte Test-Datenbank pro
Testfall (gleiches Muster wie `test_api_library.py`).
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import (
    AIStatus,
    Album,
    Artist,
    Artwork,
    Audiobook,
    DuplicateGroup,
    DuplicateGroupMember,
    Episode,
    Genre,
    Loudness,
    MediaFile,
    MediaKind,
    Movie,
    Person,
    PersonRole,
    PersonRoleType,
    Series,
    Source,
    TechnicalMetadata,
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


def _seed(app, tmp_path: Path) -> None:
    with app.state.genesis.db.session() as session:
        artist = Artist(name="Testband")
        session.add(artist)
        session.flush()
        album = Album(title="Testalbum", artist_id=artist.id, year=2020)
        session.add(album)
        session.flush()
        genre = Genre(name="Elektro")
        session.add(genre)
        session.flush()

        mf1 = MediaFile(
            absolute_path=str(tmp_path / "song1.mp3"), directory=str(tmp_path),
            filename="song1.mp3", extension="mp3", kind=MediaKind.MUSIC,
            size_bytes=5_000_000,
        )
        session.add(mf1)
        session.flush()
        session.add(
            Track(
                media_file_id=mf1.id, title="Mein Song", album_id=album.id,
                genre_id=genre.id, year=2020, duration_seconds=240.0,
                ai_status=AIStatus.AI_GENERATED,
            )
        )
        session.add(
            TechnicalMetadata(
                media_file_id=mf1.id, duration_seconds=240.0, suspected_transcode=True
            )
        )
        session.add(Loudness(media_file_id=mf1.id, integrated_lufs=-14.0))
        session.add(
            Source(media_file_id=mf1.id, source_name="YouTube Rip", provider_name="youtube")
        )
        session.add(Artwork(media_file_id=mf1.id, file_path=str(tmp_path / "cover.jpg")))

        series = Series(name="Die grosse Reihe")
        session.add(series)
        session.flush()
        mf2 = MediaFile(
            absolute_path=str(tmp_path / "book1.m4b"), directory=str(tmp_path),
            filename="book1.m4b", extension="m4b", kind=MediaKind.AUDIOBOOK,
            size_bytes=90_000_000,
        )
        session.add(mf2)
        session.flush()
        ab = Audiobook(
            media_file_id=mf2.id, title="Band Eins", author="Erika Mustermann",
            narrator="Max Mustermann", series_id=series.id, year=2019,
        )
        session.add(ab)
        session.flush()
        person = Person(name="Erika Mustermann")
        session.add(person)
        session.flush()
        session.add(
            PersonRole(person_id=person.id, role=PersonRoleType.AUTHOR, audiobook_id=ab.id)
        )

        mf3 = MediaFile(
            absolute_path=str(tmp_path / "film1.mp4"), directory=str(tmp_path),
            filename="film1.mp4", extension="mp4", kind=MediaKind.MOVIE,
            size_bytes=2_000_000_000,
        )
        session.add(mf3)
        session.flush()
        session.add(Movie(media_file_id=mf3.id, title=None, year=2021, genre="Drama"))

        mf4 = MediaFile(
            absolute_path=str(tmp_path / "series1_s01e01.mkv"), directory=str(tmp_path),
            filename="series1_s01e01.mkv", extension="mkv", kind=MediaKind.EPISODE,
            size_bytes=1_500_000_000,
        )
        session.add(mf4)
        session.flush()
        session.add(
            Episode(
                media_file_id=mf4.id, series_id=series.id, season_number=1,
                episode_number=1, title="Der Anfang", year=2022,
            )
        )

        mf5 = MediaFile(
            absolute_path=str(tmp_path / "song1_copy.mp3"), directory=str(tmp_path),
            filename="song1_copy.mp3", extension="mp3", kind=MediaKind.MUSIC,
            size_bytes=5_000_000,
        )
        session.add(mf5)
        session.flush()
        dg = DuplicateGroup(
            category="hash", confidence=1.0, matched_stages_json=["hash"], reason="identisch"
        )
        session.add(dg)
        session.flush()
        session.add(DuplicateGroupMember(duplicate_group_id=dg.id, media_file_id=mf1.id))
        session.add(DuplicateGroupMember(duplicate_group_id=dg.id, media_file_id=mf5.id))

        session.commit()


def _names(resp) -> set[str]:
    assert resp.status_code == 200
    return {item["filename"] for item in resp.json()["items"]}


def test_search_matches_artist_name(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"search": "Testband"})) == {"song1.mp3"}


def test_search_matches_audiobook_author(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"search": "Mustermann"})) == {"book1.m4b"}


def test_search_matches_series_name(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media", params={"search": "grosse Reihe"}))
    assert names == {"book1.m4b", "series1_s01e01.mkv"}


def test_search_matches_source_name(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"search": "YouTube"})) == {"song1.mp3"}


def test_filter_by_genre(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"genre": "Elektro"})) == {"song1.mp3"}


def test_filter_by_year(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"year": 2019})) == {"book1.m4b"}


def test_filter_by_extension(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"extension": "mp3"})) == {
        "song1.mp3",
        "song1_copy.mp3",
    }


def test_filter_by_size_range(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media", params={"min_size_bytes": 1_000_000_000}))
    assert names == {"film1.mp4", "series1_s01e01.mkv"}


def test_filter_by_duration_range(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(
        client.get("/media", params={"min_duration_s": 200, "max_duration_s": 300})
    )
    assert names == {"song1.mp3"}


def test_filter_by_ai_status(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"ai_status": "ai_generated"})) == {"song1.mp3"}


def test_filter_by_loudness_range(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media", params={"min_lufs": -15, "max_lufs": -13}))
    assert names == {"song1.mp3"}


def test_filter_has_quality_issues(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"has_quality_issues": True})) == {"song1.mp3"}


def test_filter_missing_cover(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media", params={"missing_cover": True}))
    # Nur song1.mp3 hat einen Artwork-Eintrag - alle anderen vier gelten als
    # "fehlt" (inkl. der zweiten Kopie, die KEINEN eigenen Artwork-Eintrag hat).
    assert names == {"book1.m4b", "film1.mp4", "series1_s01e01.mkv", "song1_copy.mp3"}


def test_filter_missing_metadata(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"missing_metadata": True})) == {"film1.mp4"}


def test_filter_duplicate_only(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media", params={"duplicate_only": True}))
    assert names == {"song1.mp3", "song1_copy.mp3"}


def test_filter_by_person(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    assert _names(client.get("/media", params={"person": "Erika"})) == {"book1.m4b"}


def test_filter_by_series_season_episode(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(
        client.get(
            "/media",
            params={"kind": "episode", "season": 1, "episode_number": 1},
        )
    )
    assert names == {"series1_s01e01.mkv"}


def test_combined_kind_and_source_filter(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media", params={"kind": "music", "source": "youtube"}))
    assert names == {"song1.mp3"}


def test_no_filters_returns_everything(tmp_path):
    app = _make_app(tmp_path)
    _seed(app, tmp_path)
    client = _make_client(app)
    names = _names(client.get("/media"))
    assert names == {
        "song1.mp3",
        "book1.m4b",
        "film1.mp4",
        "series1_s01e01.mkv",
        "song1_copy.mp3",
    }
