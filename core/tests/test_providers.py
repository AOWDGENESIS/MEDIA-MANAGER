"""Tests fuer die Online-Metadaten-Provider. Nutzen httpx.MockTransport
(Teil von httpx, keine zusaetzliche Abhaengigkeit) statt echter Netzwerk-
aufrufe - deterministisch, offline-faehig, und deckt Fehlerpfade ab, die
gegen echte Dienste kaum reproduzierbar waeren (z.B. Timeout, 503)."""
from __future__ import annotations

import time

import httpx
import pytest

from genesis_core.providers.acoustid import AcoustIDProvider
from genesis_core.providers.base import ProviderError, ProviderNotConfiguredError
from genesis_core.providers.coverartarchive import CoverArtArchiveProvider
from genesis_core.providers.musicbrainz import MusicBrainzProvider


def _client_with_handler(handler) -> httpx.Client:
    # User-Agent wie im Produktivpfad (genesis_core.providers.base.build_user_agent)
    # setzen, damit Tests denselben Header sehen, den echte Provider ohne
    # injizierten Test-Client via make_http_client() erhalten wuerden.
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        headers={"User-Agent": "GENESIS-Media-Manager/0.2.0 ( test@example.invalid )"},
    )


# --- MusicBrainz ------------------------------------------------------------

MB_RECORDING_RESPONSE = {
    "id": "recording-mbid-123",
    "title": "Test Song",
    "artist-credit": [{"name": "Test Artist", "artist": {"id": "artist-mbid-456"}}],
    "releases": [
        {
            "id": "release-mbid-789",
            "title": "Test Album",
            "date": "2020-05-01",
            "media": [{"tracks": [{"number": "3"}]}],
        }
    ],
}

MB_SEARCH_RESPONSE = {
    "recordings": [
        {**MB_RECORDING_RESPONSE, "score": 92},
    ]
}


def test_musicbrainz_lookup_recording_parses_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "recording/recording-mbid-123" in str(request.url)
        assert request.headers["User-Agent"].startswith("GENESIS-Media-Manager/")
        return httpx.Response(200, json=MB_RECORDING_RESPONSE)

    provider = MusicBrainzProvider(client=_client_with_handler(handler))
    match = provider.lookup_recording("recording-mbid-123")

    assert match is not None
    assert match.title == "Test Song"
    assert match.artist == "Test Artist"
    assert match.album == "Test Album"
    assert match.year == 2020
    assert match.track_number == 3
    assert match.musicbrainz_recording_id == "recording-mbid-123"
    assert match.musicbrainz_release_id == "release-mbid-789"


def test_musicbrainz_search_normalizes_score_to_0_1():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "recording/?" in str(request.url) or request.url.path.endswith("/recording/")
        return httpx.Response(200, json=MB_SEARCH_RESPONSE)

    provider = MusicBrainzProvider(client=_client_with_handler(handler))
    results = provider.search_recordings(artist="Test Artist", title="Test Song")

    assert len(results) == 1
    assert results[0].confidence == pytest.approx(0.92)


def test_musicbrainz_search_requires_title():
    provider = MusicBrainzProvider(client=_client_with_handler(lambda r: httpx.Response(200)))
    with pytest.raises(ProviderError, match="Titel"):
        provider.search_recordings(artist="X", title=None)


def test_musicbrainz_http_error_raises_clear_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    provider = MusicBrainzProvider(client=_client_with_handler(handler))
    with pytest.raises(ProviderError, match="fehlgeschlagen"):
        provider.lookup_recording("some-mbid")


def test_musicbrainz_timeout_raises_clear_provider_error():
    def handler(request: httpx.Request):
        raise httpx.TimeoutException("timed out", request=request)

    provider = MusicBrainzProvider(client=_client_with_handler(handler))
    with pytest.raises(ProviderError, match="nicht rechtzeitig"):
        provider.lookup_recording("some-mbid")


def test_musicbrainz_escapes_lucene_special_characters():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.params["query"]
        return httpx.Response(200, json={"recordings": []})

    provider = MusicBrainzProvider(client=_client_with_handler(handler))
    provider.search_recordings(artist=None, title='Song: "Weird" (Title)')
    assert "\\:" in captured["query"] or "\\(" in captured["query"]


# --- AcoustID -----------------------------------------------------------------

ACOUSTID_OK_RESPONSE = {
    "status": "ok",
    "results": [
        {
            "id": "acoustid-uuid",
            "score": 0.95,
            "recordings": [
                {
                    "id": "recording-mbid-123",
                    "title": "Test Song",
                    "artists": [{"id": "artist-mbid-456", "name": "Test Artist"}],
                    "releasegroups": [{"title": "Test Album"}],
                }
            ],
        }
    ],
}


def test_acoustid_without_api_key_raises_not_configured():
    provider = AcoustIDProvider(api_key="", client=_client_with_handler(lambda r: httpx.Response(200)))
    assert provider.is_configured() is False
    with pytest.raises(ProviderNotConfiguredError):
        provider.lookup(fingerprint="AQAA...", duration_seconds=6.0)


def test_acoustid_lookup_parses_and_sorts_by_confidence():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["client"] == "test-key"
        return httpx.Response(200, json=ACOUSTID_OK_RESPONSE)

    provider = AcoustIDProvider(api_key="test-key", client=_client_with_handler(handler))
    matches = provider.lookup(fingerprint="AQAA...", duration_seconds=6.0)

    assert len(matches) == 1
    assert matches[0].confidence == pytest.approx(0.95)
    assert matches[0].musicbrainz_recording_id == "recording-mbid-123"
    assert matches[0].album == "Test Album"


def test_acoustid_error_status_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "error", "error": {"message": "invalid fingerprint"}}
        )

    provider = AcoustIDProvider(api_key="test-key", client=_client_with_handler(handler))
    with pytest.raises(ProviderError, match="invalid fingerprint"):
        provider.lookup(fingerprint="bad", duration_seconds=6.0)


# --- Cover Art Archive ----------------------------------------------------


def test_coverartarchive_fetch_front_cover_returns_bytes_and_mime():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\xff\xd8\xff-fake-jpeg", headers={"content-type": "image/jpeg"})

    provider = CoverArtArchiveProvider(client=_client_with_handler(handler))
    result = provider.fetch_front_cover("release-mbid-789")

    assert result is not None
    data, mime = result
    assert data.startswith(b"\xff\xd8\xff")
    assert mime == "image/jpeg"


def test_coverartarchive_404_returns_none_not_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    provider = CoverArtArchiveProvider(client=_client_with_handler(handler))
    assert provider.fetch_front_cover("release-without-art") is None


# --- Optionaler Live-Integrationstest (analog test_ai_provider.py/ADR-0003) --


def _internet_reachable() -> bool:
    try:
        return httpx.get("https://musicbrainz.org/ws/2/", timeout=3.0).status_code < 500
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _internet_reachable(), reason="Kein Internetzugriff in dieser Umgebung")
def test_musicbrainz_live_search_then_lookup_round_trip():
    """Optionaler Integrationstest gegen die echte MusicBrainz-API (wird
    uebersprungen statt fehlzuschlagen, wenn kein Internet verfuegbar ist -
    analog zum Ollama-Integrationstest, ADR-0003-Praezedenzfall). Verifiziert
    die reale HTTP-/JSON-Verarbeitung, nicht nur die gemockte.

    Bewusst OHNE hartcodierte MusicBrainz-ID: eine per Textsuche gefundene
    ID wird direkt per lookup_recording erneut aufgeloest - das ist robust
    gegen Datenbankaenderungen bei MusicBrainz und benoetigt kein vorab
    "geratenes" MBID (das waere selbst eine unbelegte Behauptung, Prinzip #16).

    Haertung (Deep-Review Sitzung 13): der eigene Client erzwingt zwar
    bereits einen Mindestabstand von 1s zwischen Anfragen (siehe
    `MusicBrainzProvider._rate_limited_get`), MusicBrainz selbst liefert
    aber - unabhaengig davon, vermutlich durch serverseitige Gesamtlast -
    gelegentlich einen transienten HTTP 503 ("Service Unavailable"),
    empirisch reproduziert in dieser Sitzung. Ein einzelner 503 ist kein
    Hinweis auf einen Fehler in GENESIS selbst (der deterministische,
    gemockte Fehlerpfad fuer 503 ist bereits separat oben abgedeckt) -
    deshalb wird hier mit Backoff wiederholt und bei fortgesetztem 503
    uebersprungen statt fehlzuschlagen (gleiche Grundidee wie der
    vorhandene Internet-Erreichbarkeits-Skip oben).
    """
    provider = MusicBrainzProvider(contact_email="genesis-dev-test@example.invalid")
    last_exc: ProviderError | None = None
    try:
        for attempt, backoff_seconds in enumerate((0.0, 2.0, 4.0)):
            if backoff_seconds:
                time.sleep(backoff_seconds)
            try:
                search_results = provider.search_recordings(artist="Beatles", title="Help")
                break
            except ProviderError as exc:
                if "HTTP 503" not in str(exc):
                    raise
                last_exc = exc
        else:
            pytest.skip(
                f"MusicBrainz lieferte wiederholt HTTP 503 (transiente Serverlast): {last_exc}"
            )

        assert search_results, "Erwartete mindestens einen Treffer fuer eine haeufige Suche"

        top_hit_id = search_results[0].musicbrainz_recording_id
        assert top_hit_id

        match = provider.lookup_recording(top_hit_id)
    finally:
        provider.close()

    assert match is not None
    assert match.musicbrainz_recording_id == top_hit_id
    assert match.title is not None
