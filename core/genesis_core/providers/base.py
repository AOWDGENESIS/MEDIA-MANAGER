"""Gemeinsame Schnittstelle fuer Online-Metadaten-Provider (§10/§34).

Jeder Provider hier ist ein reiner LESE-Client fuer eine externe API. Kein
Provider schreibt jemals in die GENESIS-Datenbank oder eine Mediendatei -
das ist ausschliesslich Aufgabe der `metadata`-Engine, und dort nur nach
expliziter Nutzerbestaetigung (Prinzip #17, §44).
"""
from __future__ import annotations

import dataclasses

import httpx

from genesis_core import __version__


class ProviderError(RuntimeError):
    """Wird bei jedem Fehlschlag geworfen (Netzwerk, Timeout, HTTP-Fehler,
    unerwartetes Antwortformat). Traeger einer klaren, deutschsprachigen
    Fehlermeldung (§37) - niemals eine rohe httpx-Exception nach aussen
    durchreichen, und niemals stillschweigend erfundene Daten liefern
    (Prinzip #16), wenn ein Provider nicht erreichbar ist."""


class ProviderNotConfiguredError(ProviderError):
    """Der Provider ist bewusst deaktiviert oder erfordert eine fehlende
    Konfiguration (z.B. API-Key). Wird vom Aufrufer als "nicht verfuegbar"
    behandelt, NICHT als technischer Fehler."""


def build_user_agent(contact_email: str | None) -> str:
    """MusicBrainz/AcoustID verlangen einen aussagekraeftigen User-Agent mit
    Kontaktmoeglichkeit (API-Richtlinie) - ohne diesen drohen IP-weite
    Sperren fuer ALLE Nutzer der jeweiligen Dienste, nicht nur fuer GENESIS.
    """
    contact = contact_email or "kein-kontakt-hinterlegt@example.invalid"
    return f"GENESIS-Media-Manager/{__version__} ( {contact} )"


@dataclasses.dataclass
class RecordingMatch:
    """Ein einzelner Kandidat fuer eine Musik-Aufnahme, unabhaengig davon,
    ueber welchen Provider/Weg er gefunden wurde (Fingerprint oder
    Text-Suche). Confidence liegt IMMER zwischen 0.0 und 1.0 und ist NIE
    eine feststehende Wahrheit (Prinzip #17)."""

    provider: str
    confidence: float
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    track_number: int | None = None
    musicbrainz_recording_id: str | None = None
    musicbrainz_release_id: str | None = None
    musicbrainz_artist_id: str | None = None


def make_http_client(timeout_seconds: float, user_agent: str) -> httpx.Client:
    """Zentrale Fabrik fuer HTTP-Clients dieses Pakets - garantiert, dass
    JEDER Provider einen Timeout und einen konformen User-Agent setzt
    (Deep-Review-Prinzip: kein httpx-Aufruf ohne Timeout)."""
    return httpx.Client(
        timeout=timeout_seconds,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
