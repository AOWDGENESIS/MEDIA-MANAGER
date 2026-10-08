"""AcoustID-Anbindung (§12/§13) - Fingerprint-basierte Wiedererkennung.

AcoustID nimmt einen Chromaprint-Fingerprint entgegen und liefert eine Liste
moeglicher MusicBrainz-Recording-IDs mit einem Score (0.0-1.0), wie sicher
der Fingerprint zu jeder Aufnahme passt. Das ist der verlaesslichste
Erkennungsweg (Audioinhalt statt Tags/Dateiname) - dennoch bleibt es ein
Vorschlag, kein Fakt (Prinzip #17): mehrere Aufnahmen koennen denselben
Fingerprint teilen (Live-Version vs. Studio-Version, identisches Mastering).

Benoetigt einen persoenlichen, kostenlosen API-Key
(https://acoustid.org/api-key) - GENESIS liefert keinen eigenen Key mit
(kein eingebettetes Geheimnis). Ohne konfigurierten Key wirft dieser
Provider `ProviderNotConfiguredError`, NIEMALS erfundene Ergebnisse.
"""
from __future__ import annotations

import httpx

from genesis_core.logutil import get_logger
from genesis_core.providers.base import (
    ProviderError,
    ProviderNotConfiguredError,
    RecordingMatch,
    build_user_agent,
    make_http_client,
)

log = get_logger("AcoustIDProvider")

ACOUSTID_API_BASE = "https://api.acoustid.org/v2/lookup"


class AcoustIDProvider:
    name = "acoustid"

    def __init__(
        self,
        api_key: str,
        contact_email: str = "",
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ):
        self._api_key = api_key
        self._client = client or make_http_client(
            timeout_seconds, build_user_agent(contact_email)
        )
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def is_configured(self) -> bool:
        return bool(self._api_key.strip())

    def lookup(self, fingerprint: str, duration_seconds: float) -> list[RecordingMatch]:
        if not self.is_configured():
            raise ProviderNotConfiguredError(
                "AcoustID ist nicht konfiguriert - kein API-Key hinterlegt "
                "(Einstellungen -> Metadaten -> AcoustID-API-Key). Kostenlos "
                "erhaeltlich unter https://acoustid.org/api-key."
            )
        params = {
            "client": self._api_key,
            "duration": round(duration_seconds),
            "fingerprint": fingerprint,
            "meta": "recordings+releasegroups",
            "format": "json",
        }
        try:
            resp = self._client.get(ACOUSTID_API_BASE, params=params)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError("AcoustID hat nicht rechtzeitig geantwortet.") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"AcoustID-Anfrage fehlgeschlagen (HTTP {exc.response.status_code})."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"AcoustID nicht erreichbar: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError("AcoustID-Antwort war kein gueltiges JSON.") from exc

        if data.get("status") != "ok":
            error_msg = data.get("error", {}).get("message", "unbekannter Fehler")
            raise ProviderError(f"AcoustID meldet einen Fehler: {error_msg}")

        matches: list[RecordingMatch] = []
        for result in data.get("results", []):
            score = float(result.get("score", 0.0))
            for recording in result.get("recordings", []) or []:
                artists = recording.get("artists") or []
                artist_name = artists[0]["name"] if artists else None
                artist_mbid = artists[0].get("id") if artists else None
                release_groups = recording.get("releasegroups") or []
                album_title = release_groups[0].get("title") if release_groups else None
                matches.append(
                    RecordingMatch(
                        provider=self.name,
                        confidence=score,
                        title=recording.get("title"),
                        artist=artist_name,
                        album=album_title,
                        musicbrainz_recording_id=recording.get("id"),
                        musicbrainz_artist_id=artist_mbid,
                    )
                )
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
