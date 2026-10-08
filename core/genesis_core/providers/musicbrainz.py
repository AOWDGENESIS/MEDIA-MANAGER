"""MusicBrainz-Anbindung (§10) - offene Musik-Metadatenbank, CC0/PDL-Daten.

Zwei Zugriffspfade:
1. `lookup_recording(mbid)` - exakte Aufloesung einer bekannten
   MusicBrainz-Recording-ID (z.B. aus einem AcoustID-Treffer).
2. `search_recordings(artist, title)` - Text-Suche, Fallback wenn kein
   Fingerprint/keine AcoustID-Konfiguration verfuegbar ist. Liefert
   MusicBrainz' eigenen Relevanz-Score (0-100), der als Basis fuer unsere
   Konfidenzberechnung dient (siehe metadata/engine.py) - bewusst NICHT so
   verlaesslich eingestuft wie ein Fingerprint-Treffer.

Rate-Limiting: MusicBrainz verlangt fuer unauthentifizierte Clients max.
1 Anfrage/Sekunde (API-Richtlinie) - ein Verstoss kann zur IP-Sperre fuer
ALLE Nutzer dieses Dienstes fuehren, nicht nur fuer GENESIS. Ein einfacher
Mindestabstand wird deshalb hart erzwungen.
"""
from __future__ import annotations

import time

import httpx

from genesis_core.logutil import get_logger
from genesis_core.providers.base import (
    ProviderError,
    RecordingMatch,
    build_user_agent,
    make_http_client,
)

log = get_logger("MusicBrainzProvider")

MUSICBRAINZ_API_BASE = "https://musicbrainz.org/ws/2"
MIN_REQUEST_INTERVAL_SECONDS = 1.0  # API-Richtlinie, siehe Moduldocstring


class MusicBrainzProvider:
    name = "musicbrainz"

    def __init__(
        self,
        contact_email: str = "",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ):
        self._client = client or make_http_client(
            timeout_seconds, build_user_agent(contact_email)
        )
        self._owns_client = client is None
        self._last_request_at: float = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _rate_limited_get(self, url: str, params: dict) -> dict:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        try:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"MusicBrainz hat nicht rechtzeitig geantwortet ({url})."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"MusicBrainz-Anfrage fehlgeschlagen (HTTP {exc.response.status_code}): {url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"MusicBrainz nicht erreichbar: {exc}") from exc
        finally:
            self._last_request_at = time.monotonic()
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError("MusicBrainz-Antwort war kein gueltiges JSON.") from exc

    def lookup_recording(self, musicbrainz_recording_id: str) -> RecordingMatch | None:
        """Exakte Aufloesung einer bekannten Recording-MBID (aus AcoustID)."""
        data = self._rate_limited_get(
            f"{MUSICBRAINZ_API_BASE}/recording/{musicbrainz_recording_id}",
            params={"fmt": "json", "inc": "releases+artist-credits"},
        )
        return _parse_recording(data, provider=self.name, confidence=None)

    def search_recordings(
        self, artist: str | None, title: str | None, limit: int = 5
    ) -> list[RecordingMatch]:
        """Text-basierte Fallback-Suche, wenn kein Fingerprint verfuegbar ist."""
        if not title:
            raise ProviderError("MusicBrainz-Textsuche benoetigt mindestens einen Titel.")
        query_parts = [f'recording:"{_escape_lucene(title)}"']
        if artist:
            query_parts.append(f'artist:"{_escape_lucene(artist)}"')
        query = " AND ".join(query_parts)

        data = self._rate_limited_get(
            f"{MUSICBRAINZ_API_BASE}/recording/",
            params={"query": query, "fmt": "json", "limit": limit},
        )
        recordings = data.get("recordings", [])
        results = []
        for rec in recordings:
            # MusicBrainz liefert einen eigenen Relevanz-Score 0-100.
            mb_score = float(rec.get("score", 0)) / 100.0
            match = _parse_recording(rec, provider=self.name, confidence=mb_score)
            if match is not None:
                results.append(match)
        return results


def _escape_lucene(value: str) -> str:
    """Escaped Sonderzeichen, die in MusicBrainz'/Lucene-Suchsyntax reserviert
    sind, damit Nutzereingaben (Titel/Interpret) die Anfrage nicht
    verfaelschen oder als Syntaxfehler enden."""
    reserved = '+-&&||!(){}[]^"~*?:\\/'
    escaped = value
    for ch in reserved:
        escaped = escaped.replace(ch, f"\\{ch}")
    return escaped


def _parse_recording(
    data: dict, provider: str, confidence: float | None
) -> RecordingMatch | None:
    if not data or "id" not in data:
        return None
    artist_credit = data.get("artist-credit") or []
    artist_name = artist_credit[0]["name"] if artist_credit else None
    artist_mbid = artist_credit[0].get("artist", {}).get("id") if artist_credit else None

    releases = data.get("releases") or []
    release = releases[0] if releases else {}
    album_title = release.get("title")
    release_id = release.get("id")
    year = None
    release_date = release.get("date")
    if release_date and len(release_date) >= 4 and release_date[:4].isdigit():
        year = int(release_date[:4])

    track_number = None
    media = release.get("media") or []
    if media:
        tracks = media[0].get("tracks") or []
        if tracks:
            try:
                track_number = int(tracks[0].get("number"))
            except (TypeError, ValueError):
                track_number = None

    return RecordingMatch(
        provider=provider,
        confidence=confidence if confidence is not None else 1.0,
        title=data.get("title"),
        artist=artist_name,
        album=album_title,
        year=year,
        track_number=track_number,
        musicbrainz_recording_id=data.get("id"),
        musicbrainz_release_id=release_id,
        musicbrainz_artist_id=artist_mbid,
    )
