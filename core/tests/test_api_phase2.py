"""Tests fuer die Phase-2-API-Endpunkte (Metadaten-Vorschlaege, Umbenennen,
Artwork). Nutzen dieselbe token-authentifizierte Test-Client-Fabrik wie
test_api.py."""
from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.providers.musicbrainz import MusicBrainzProvider


def _make_app(tmp_path: Path, *, metadata_enabled: bool = False):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    settings.metadata.enabled = metadata_enabled
    return create_app(settings)


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_music_file(app, path: Path) -> int:
    from genesis_core.db.models import MediaFile, MediaKind

    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=str(path), directory=str(path.parent), filename=path.name,
            extension=path.suffix.lower(), kind=MediaKind.MUSIC, size_bytes=path.stat().st_size,
        )
        session.add(mf)
        session.flush()
        return mf.id


# --- Metadaten-Vorschlaege ----------------------------------------------------


def test_metadata_suggestions_disabled_by_default(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path, metadata_enabled=False)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    resp = client.get(f"/media/{media_id}/metadata-suggestions")
    assert resp.status_code == 409  # nicht konfiguriert/deaktiviert, kein Absturz


MB_SEARCH_RESPONSE = {
    "recordings": [
        {
            "id": "recording-mbid-1", "title": "Test Song", "score": 95,
            "artist-credit": [{"name": "Test Artist", "artist": {"id": "artist-mbid-1"}}],
            "releases": [{"id": "release-mbid-1", "title": "Test Album", "date": "2020-01-01",
                          "media": [{"tracks": [{"number": "1"}]}]}],
        }
    ]
}


def test_metadata_suggestions_and_apply_roundtrip(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path, metadata_enabled=True)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MB_SEARCH_RESPONSE)

    mocked_mb = MusicBrainzProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    )
    with patch.object(app.state.genesis.providers, "musicbrainz", mocked_mb):
        resp = client.get(f"/media/{media_id}/metadata-suggestions")
        assert resp.status_code == 200
        suggestions = resp.json()["suggestions"]
        assert len(suggestions) == 1
        match = suggestions[0]["match"]
        assert match["title"] == "Test Song"

        # Ohne confirm=true -> 422, keine Uebernahme
        resp = client.post(
            f"/media/{media_id}/metadata-suggestions/apply",
            json={"match": match, "confirm": False},
        )
        assert resp.status_code == 422

        # Mit confirm=true -> uebernommen
        resp = client.post(
            f"/media/{media_id}/metadata-suggestions/apply",
            json={"match": match, "confirm": True},
        )
        assert resp.status_code == 200
        track = resp.json()["track"]
        assert track["title"] == "Test Song"
        assert track["is_user_confirmed"] is True


def test_metadata_apply_rejects_match_below_configured_min_confidence(
    tmp_path: Path, test_library_root: Path
):
    """Deep-Review-Fund F-12 (Sitzung 3): `confirm=true` beweist nur, dass
    IRGENDETWAS vom Nutzer bestaetigt wurde - nicht, dass der eingereichte
    `match` wirklich der vom Server generierte Vorschlag mit ausreichender
    Konfidenz ist (z.B. bei einem Client-Bug). Der Server muss die
    konfigurierte Mindest-Konfidenz unabhaengig vom `confirm`-Flag selbst
    noch einmal durchsetzen (Defense-in-Depth, Prinzip #17)."""
    app = _make_app(tmp_path, metadata_enabled=True)
    app.state.genesis.settings.metadata.min_confidence_for_suggestion = 0.5
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    low_confidence_match = {
        "provider": "musicbrainz", "recording_mbid": "r-1", "release_mbid": "rel-1",
        "artist_mbid": "a-1", "title": "Verdaechtiger Titel", "artist": "Irgendwer",
        "album": "Irgendein Album", "track_number": 1, "year": 2020,
        "confidence": 0.1,
    }
    resp = client.post(
        f"/media/{media_id}/metadata-suggestions/apply",
        json={"match": low_confidence_match, "confirm": True},
    )
    assert resp.status_code == 422
    assert "Konfidenz" in resp.json()["detail"]

    # Die Datenbank darf dadurch NICHT veraendert worden sein.
    with app.state.genesis.db.session() as session:
        from genesis_core.db.models import Track

        track = session.query(Track).filter(Track.media_file_id == media_id).one_or_none()
        assert track is None or track.title != "Verdaechtiger Titel"


def test_metadata_suggestions_unknown_media_returns_404(tmp_path: Path):
    app = _make_app(tmp_path, metadata_enabled=True)
    client = _make_client(app)
    resp = client.get("/media/99999/metadata-suggestions")
    assert resp.status_code == 404


# --- Umbenennen ---------------------------------------------------------------


def test_rename_preview_and_apply_roundtrip(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "old.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    from genesis_core.db.models import Track

    with app.state.genesis.db.session() as session:
        session.add(Track(media_file_id=media_id, title="Renamed Title", track_number=9))

    resp = client.post(
        "/rename/preview", json={"media_file_ids": [media_id], "template": "{track:02d} - {title}.{ext}"}
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["new_absolute_path"] == str(tmp_path / "09 - Renamed Title.mp3")
    assert items[0]["is_actionable"] is True

    # Ohne confirm -> 422
    resp = client.post(
        "/rename/apply",
        json={"media_file_ids": [media_id], "template": "{track:02d} - {title}.{ext}", "confirm": False},
    )
    assert resp.status_code == 422
    assert path.exists()  # unveraendert

    resp = client.post(
        "/rename/apply",
        json={"media_file_ids": [media_id], "template": "{track:02d} - {title}.{ext}", "confirm": True},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["applied"] is True
    assert not path.exists()
    assert (tmp_path / "09 - Renamed Title.mp3").exists()

    # Job wurde protokolliert (Rollback-Grundlage, §17)
    jobs_resp = client.get("/jobs")
    job_types = [j["job_type"] for j in jobs_resp.json()]
    assert "rename" in job_types


def test_rename_endpoints_reject_directory_templates(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    resp = client.post(
        "/rename/preview", json={"media_file_ids": [media_id], "template": "{artist}/{title}.{ext}"}
    )
    assert resp.status_code == 422


# --- Artwork --------------------------------------------------------------


def test_artwork_endpoint_404_when_none_embedded(tmp_path: Path, test_library_root: Path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    resp = client.get(f"/media/{media_id}/artwork")
    assert resp.status_code == 404


def test_artwork_fetch_online_then_embed_roundtrip(tmp_path: Path, test_library_root: Path):
    """Voller Online-Flow (§22): Online-Cover wird NUR gecacht, nie direkt in
    die Datei geschrieben; das Einbetten ist ein zweiter, separat
    bestaetigungspflichtiger Schritt (Prinzip #5/#17/#44)."""
    from genesis_core.db.models import Album, Track
    from genesis_core.providers.coverartarchive import CoverArtArchiveProvider

    app = _make_app(tmp_path, metadata_enabled=True)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    tiny_jpeg = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300030202020202"
        "03020202030303030406040404040408060605060907090a0a090809090a0c"
        "0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b"
        "080001000101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
    )

    with app.state.genesis.db.session() as session:
        album = Album(title="Test Album", musicbrainz_id="11111111-1111-1111-1111-111111111111")
        session.add(album)
        session.flush()
        session.add(Track(media_file_id=media_id, title="Test Song", album_id=album.id))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=tiny_jpeg, headers={"content-type": "image/jpeg"})

    mocked_caa = CoverArtArchiveProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    )
    with patch.object(app.state.genesis.providers, "coverartarchive", mocked_caa):
        # Online-Suche legt NUR einen Cache-Eintrag + DB-Zeile an - Datei bleibt unberuehrt
        resp = client.post(f"/media/{media_id}/artwork/fetch-online")
        assert resp.status_code == 200
        artwork_id = resp.json()["artwork_id"]

        # Die Mediendatei selbst hat noch kein eingebettetes Artwork
        resp = client.get(f"/media/{media_id}/artwork")
        assert resp.status_code == 404

        # Ohne confirm -> 422, Datei bleibt unveraendert
        resp = client.post(
            f"/media/{media_id}/artwork/embed", json={"artwork_id": artwork_id, "confirm": False}
        )
        assert resp.status_code == 422
        resp = client.get(f"/media/{media_id}/artwork")
        assert resp.status_code == 404

        # Mit confirm=true -> jetzt tatsaechlich eingebettet
        resp = client.post(
            f"/media/{media_id}/artwork/embed", json={"artwork_id": artwork_id, "confirm": True}
        )
        assert resp.status_code == 200
        assert resp.json()["embedded"] is True

        resp = client.get(f"/media/{media_id}/artwork")
        assert resp.status_code == 200
        assert resp.content == tiny_jpeg


def test_artwork_embed_uses_persisted_mime_type_not_cache_file_extension_guess(
    tmp_path: Path, test_library_root: Path
):
    """Deep-Review-Fund F-11 (Sitzung 3): Fruehr wurde der MIME-Typ beim
    Einbetten blind aus der Cache-Datei-ENDUNG geraten
    (`.endswith(".png")` sonst "image/jpeg"). `cache_artwork` mappt
    UNBEKANNTE Mime-Typen aber still auf die Endung ".jpg" (siehe
    `_MIME_TO_EXT`) - fuer einen hypothetischen zukuenftigen Provider, der
    z.B. "image/webp" liefert, haette die alte Rate-Logik daraufhin
    faelschlich "image/jpeg" eingebettet, obwohl die Bilddaten tatsaechlich
    WebP sind. Der neue Code muss stattdessen den beim Online-Abruf
    gespeicherten `Artwork.mime_type` direkt verwenden (verlustfrei, kein
    Raten) - dieser Test verifiziert das per direkter DB-Pruefung UND durch
    Verfolgen des tatsaechlich eingebetteten mime-Werts."""
    from genesis_core.db.models import Album, Artwork, Track
    from genesis_core.providers.coverartarchive import CoverArtArchiveProvider

    app = _make_app(tmp_path, metadata_enabled=True)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    # Beliebige, gueltige Bild-Bytes reichen hier - es geht nur um die
    # MIME-Typ-Weiterleitung, nicht um echte Bildverarbeitung.
    fake_webp_bytes = b"RIFF....WEBPVP8 fake-but-good-enough-for-this-test"

    with app.state.genesis.db.session() as session:
        album = Album(title="Test Album", musicbrainz_id="22222222-2222-2222-2222-222222222222")
        session.add(album)
        session.flush()
        session.add(Track(media_file_id=media_id, title="Test Song", album_id=album.id))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=fake_webp_bytes, headers={"content-type": "image/webp"}
        )

    mocked_caa = CoverArtArchiveProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    )
    with patch.object(app.state.genesis.providers, "coverartarchive", mocked_caa):
        resp = client.post(f"/media/{media_id}/artwork/fetch-online")
        assert resp.status_code == 200
        artwork_id = resp.json()["artwork_id"]
        assert resp.json()["mime_type"] == "image/webp"

        # Der Cache-Dateipfad bekommt wegen des unbekannten Mime-Typs die
        # ".jpg"-Fallback-Endung - GENAU das ist die Falle, die F-11 behebt.
        assert resp.json()["cached_path"].endswith(".jpg")

    with app.state.genesis.db.session() as session:
        artwork = session.get(Artwork, artwork_id)
        # Der tatsaechliche MIME-Typ wurde korrekt persistiert, NICHT aus
        # der (irrefuehrenden) ".jpg"-Cache-Endung zurueckgewonnen.
        assert artwork.mime_type == "image/webp"


def test_artwork_fetch_online_without_known_album_mbid_returns_409(
    tmp_path: Path, test_library_root: Path
):
    app = _make_app(tmp_path, metadata_enabled=True)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    resp = client.post(f"/media/{media_id}/artwork/fetch-online")
    assert resp.status_code == 409


def test_artwork_endpoint_returns_embedded_image(tmp_path: Path, test_library_root: Path):
    from genesis_core.artwork import embed_artwork

    app = _make_app(tmp_path)
    client = _make_client(app)
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)
    media_id = _seed_music_file(app, path)

    tiny_jpeg = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300030202020202"
        "03020202030303030406040404040408060605060907090a0a090809090a0c"
        "0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b"
        "080001000101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
    )
    embed_artwork(path, tiny_jpeg, "image/jpeg", user_confirmed=True)

    resp = client.get(f"/media/{media_id}/artwork")
    assert resp.status_code == 200
    assert resp.content == tiny_jpeg
    assert resp.headers["content-type"] == "image/jpeg"
