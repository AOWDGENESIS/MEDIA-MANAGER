from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from genesis_core.config import MetadataSettings
from genesis_core.db import Database
from genesis_core.db.models import Album, Artist, MediaFile, MediaKind, Track
from genesis_core.metadata.engine import (
    MetadataApplyNotConfirmedError,
    MetadataEngine,
    MetadataSuggestion,
)
from genesis_core.providers import ProviderBundle
from genesis_core.providers.base import RecordingMatch
from genesis_core.providers.musicbrainz import MusicBrainzProvider


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


def _make_media_file(db: Database, absolute_path: str) -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path=absolute_path,
            directory=str(Path(absolute_path).parent),
            filename=Path(absolute_path).name,
            extension=".mp3",
            kind=MediaKind.MUSIC,
            size_bytes=1234,
        )
        session.add(mf)
        session.flush()
        return mf.id


# --- suggest_for_media_file: Text-Suche-Fallback -----------------------------

MB_SEARCH_RESPONSE = {
    "recordings": [
        {
            "id": "recording-mbid-1",
            "title": "Test Song",
            "score": 90,
            "artist-credit": [{"name": "Test Artist", "artist": {"id": "artist-mbid-1"}}],
            "releases": [
                {"id": "release-mbid-1", "title": "Test Album", "date": "2021-01-01",
                 "media": [{"tracks": [{"number": "1"}]}]},
            ],
        }
    ]
}


def test_suggest_uses_text_search_when_no_fingerprint_provider(db: Database, test_library_root: Path):
    media_path = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    media_file_id = _make_media_file(db, str(media_path))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MB_SEARCH_RESPONSE)

    providers = ProviderBundle(
        musicbrainz=MusicBrainzProvider(client=_mock_client(handler)),
        acoustid=None,
        coverartarchive=None,
    )
    engine = MetadataEngine(providers=providers, settings=MetadataSettings(enabled=True))

    with db.session() as session:
        media_file = session.get(MediaFile, media_file_id)
        suggestions = engine.suggest_for_media_file(media_file)

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.method == "text_search"
    assert s.match.title == "Test Song"
    # Text-Suche-Penalty: 0.90 * 0.85 = 0.765
    assert s.match.confidence == pytest.approx(0.9 * 0.85)


def test_suggest_disabled_raises_not_configured(db: Database, test_library_root: Path):
    from genesis_core.providers.base import ProviderNotConfiguredError

    media_path = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    media_file_id = _make_media_file(db, str(media_path))
    engine = MetadataEngine(
        providers=ProviderBundle(None, None, None), settings=MetadataSettings(enabled=False)
    )
    with db.session() as session:
        media_file = session.get(MediaFile, media_file_id)
        with pytest.raises(ProviderNotConfiguredError):
            engine.suggest_for_media_file(media_file)


def test_suggest_below_min_confidence_is_filtered_out(db: Database, test_library_root: Path):
    media_path = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    media_file_id = _make_media_file(db, str(media_path))

    low_score_response = {**MB_SEARCH_RESPONSE}
    low_score_response["recordings"][0] = {**MB_SEARCH_RESPONSE["recordings"][0], "score": 10}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=low_score_response)

    providers = ProviderBundle(
        musicbrainz=MusicBrainzProvider(client=_mock_client(handler)), acoustid=None, coverartarchive=None
    )
    engine = MetadataEngine(
        providers=providers, settings=MetadataSettings(enabled=True, min_confidence_for_suggestion=0.5)
    )
    with db.session() as session:
        media_file = session.get(MediaFile, media_file_id)
        suggestions = engine.suggest_for_media_file(media_file)

    assert suggestions == []  # 0.10 * 0.85 = 0.085, unterhalb 0.5


# --- apply_suggestion --------------------------------------------------------


def _make_suggestion(media_file_id: int, **overrides) -> MetadataSuggestion:
    from genesis_core.metadata.tag_reader import ExistingTags

    match = RecordingMatch(
        provider="musicbrainz",
        confidence=0.9,
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        year=2021,
        track_number=1,
        musicbrainz_recording_id="recording-mbid-1",
        musicbrainz_release_id="release-mbid-1",
        musicbrainz_artist_id="artist-mbid-1",
    )
    for key, value in overrides.items():
        setattr(match, key, value)
    return MetadataSuggestion(
        media_file_id=media_file_id, match=match, method="text_search", existing_tags=ExistingTags()
    )


def test_apply_suggestion_requires_explicit_confirmation(db: Database):
    media_file_id = _make_media_file(db, "/fake/path/song.mp3")
    engine = MetadataEngine(providers=ProviderBundle(None, None, None), settings=MetadataSettings())
    suggestion = _make_suggestion(media_file_id)

    with db.session() as session, pytest.raises(MetadataApplyNotConfirmedError):
        engine.apply_suggestion(session, media_file_id, suggestion, user_confirmed=False)


def test_apply_suggestion_creates_artist_album_track(db: Database):
    media_file_id = _make_media_file(db, "/fake/path/song.mp3")
    engine = MetadataEngine(providers=ProviderBundle(None, None, None), settings=MetadataSettings())
    suggestion = _make_suggestion(media_file_id)

    with db.session() as session:
        track = engine.apply_suggestion(session, media_file_id, suggestion, user_confirmed=True)
        assert track.title == "Test Song"
        assert track.is_user_confirmed is True
        assert track.confidence == pytest.approx(0.9)
        assert track.source == "provider:musicbrainz"

    with db.session() as session:
        artists = session.execute(select(Artist)).scalars().all()
        albums = session.execute(select(Album)).scalars().all()
        tracks = session.execute(select(Track)).scalars().all()
        assert len(artists) == 1
        assert artists[0].name == "Test Artist"
        assert artists[0].musicbrainz_id == "artist-mbid-1"
        assert len(albums) == 1
        assert albums[0].title == "Test Album"
        assert len(tracks) == 1
        assert tracks[0].album_id == albums[0].id


def test_apply_suggestion_reuses_existing_artist_and_album(db: Database):
    """Zweimal denselben Kuenstler/Album anwenden darf keine Duplikate erzeugen."""
    media_file_id_1 = _make_media_file(db, "/fake/path/song1.mp3")
    media_file_id_2 = _make_media_file(db, "/fake/path/song2.mp3")
    engine = MetadataEngine(providers=ProviderBundle(None, None, None), settings=MetadataSettings())

    with db.session() as session:
        engine.apply_suggestion(
            session, media_file_id_1, _make_suggestion(media_file_id_1), user_confirmed=True
        )
    with db.session() as session:
        engine.apply_suggestion(
            session, media_file_id_2, _make_suggestion(media_file_id_2, title="Another Song"),
            user_confirmed=True,
        )

    with db.session() as session:
        artists = session.execute(select(Artist)).scalars().all()
        albums = session.execute(select(Album)).scalars().all()
        assert len(artists) == 1
        assert len(albums) == 1
