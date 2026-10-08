"""Cover Art Archive-Anbindung (§22 Artwork Engine).

Liest ausschliesslich (holt Bilddaten anhand einer MusicBrainz-Release-ID) -
schreibt oder embedded NICHTS in eine lokale Datei. Das Einbetten in eine
Mediendatei ist eine eigene, bestaetigungspflichtige Aktion
(siehe genesis_core/artwork/engine.py, Prinzip #5/#44).
"""
from __future__ import annotations

import httpx

from genesis_core.logutil import get_logger
from genesis_core.providers.base import ProviderError, build_user_agent, make_http_client

log = get_logger("CoverArtArchiveProvider")

COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org"


class CoverArtArchiveProvider:
    name = "coverartarchive"

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

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_front_cover(self, release_musicbrainz_id: str) -> tuple[bytes, str] | None:
        """Liefert (Bilddaten, MIME-Typ) des Frontcovers, oder None, wenn
        kein Artwork fuer diese Release existiert (kein Fehler - das ist ein
        normaler, haeufiger Fall, keine erfundenen Platzhalterbilder!)."""
        url = f"{COVER_ART_ARCHIVE_BASE}/release/{release_musicbrainz_id}/front"
        try:
            resp = self._client.get(url, follow_redirects=True)
        except httpx.TimeoutException as exc:
            raise ProviderError("Cover Art Archive hat nicht rechtzeitig geantwortet.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cover Art Archive nicht erreichbar: {exc}") from exc

        if resp.status_code == 404:
            return None
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Cover Art Archive-Anfrage fehlgeschlagen (HTTP {exc.response.status_code})."
            ) from exc

        content_type = resp.headers.get("content-type", "image/jpeg")
        return resp.content, content_type
