"""Explizit BLOCKIERTE Quellen (§30 harte Grenze: keine DRM-Umgehung).

Spotify, Audible und Pocket FM liefern ihre kostenpflichtigen Inhalte
ausschliesslich DRM-verschluesselt und/oder ausschliesslich ueber ihre
eigenen, anmeldepflichtigen Apps/SDKs aus. Ein "Download-Adapter", der
solche Inhalte trotzdem extrahiert, waere zwingend entweder eine
DRM-Umgehung oder eine unsichere Wiederverwendung gespeicherter
Zugangsdaten/Sitzungscookies - beides ist durch §30 ausdruecklich
ausgeschlossen.

Diese Provider werden daher bewusst NICHT als "fehlende Funktion", sondern
als korrekt erkannte und gemeldete Nichtverfuegbarkeit implementiert (§31:
"Wenn ein Dienst keinen zulaessigen Download ermoeglicht, muss die
Anwendung dies erkennen und entsprechend melden."). Sie sind trotzdem
vollwertige, registrierte Provider (zeigen in der UI z.B. "Audible-Links
werden erkannt, aber: DRM-geschuetzt, kein Download moeglich" statt die URL
einfach nicht zu erkennen) - das macht das Verhalten fuer Nutzer
nachvollziehbar, statt sie im Unklaren zu lassen.
"""
from __future__ import annotations

import re
from pathlib import Path

from genesis_core.download.base import (
    AvailabilityResult,
    DownloadedFile,
    DownloadNotPermittedError,
    DownloadOption,
    DownloadProvider,
    SourceMetadata,
)


class DRMBlockedProvider(DownloadProvider):
    """Erkennt URLs eines bekannten DRM-/anmeldepflichtigen Dienstes und
    meldet IMMER "nicht verfuegbar" mit einer erklaerenden Begruendung -
    versucht NIEMALS, tatsaechlich Daten vom Dienst abzurufen."""

    requires_internet = False  # macht bewusst keinen einzigen Netzwerkaufruf

    def __init__(self, provider_id: str, display_name: str, url_patterns: list[str], reason: str):
        self.provider_id = provider_id
        self.display_name = display_name
        self.url_patterns = url_patterns
        self.reason = reason

    def matches(self, url: str) -> bool:
        return any(re.search(pattern, url) for pattern in self.url_patterns)

    def check_availability(self, url: str) -> AvailabilityResult:
        return AvailabilityResult(available=False, reason=self.reason)

    def fetch_metadata(self, url: str) -> SourceMetadata:
        raise DownloadNotPermittedError(self.reason)

    def list_options(self, url: str) -> list[DownloadOption]:
        raise DownloadNotPermittedError(self.reason)

    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        raise DownloadNotPermittedError(self.reason)


def build_spotify_provider() -> DRMBlockedProvider:
    return DRMBlockedProvider(
        provider_id="spotify",
        display_name="Spotify",
        url_patterns=[r"spotify\.com/", r"^spotify:"],
        reason=(
            "Spotify liefert Musik ausschliesslich DRM-verschluesselt ueber die "
            "eigene App/SDK aus. GENESIS umgeht keine DRM-Schutzmechanismen (§30) - "
            "ein Download ist hier nicht moeglich. Nutze stattdessen z.B. Spotifys "
            "eigenen Daten-Export oder kaufe/importiere die Titel aus einer "
            "DRM-freien Quelle."
        ),
    )


def build_audible_provider() -> DRMBlockedProvider:
    return DRMBlockedProvider(
        provider_id="audible",
        display_name="Audible",
        url_patterns=[r"audible\.(?:com|de|co\.uk)/"],
        reason=(
            "Audible-Hoerbuecher sind DRM-geschuetzt (Audible-eigenes AAX/AAXC-"
            "Format) und erfordern ein angemeldetes Konto. GENESIS speichert keine "
            "Zugangsdaten und umgeht kein DRM (§30) - ein Download ist hier nicht "
            "moeglich. Bereits regulaer erworbene, entschluesselte Hoerbuchdateien "
            "koennen stattdessen als lokale Datei importiert werden."
        ),
    )


def build_pocket_fm_provider() -> DRMBlockedProvider:
    return DRMBlockedProvider(
        provider_id="pocket_fm",
        display_name="Pocket FM",
        url_patterns=[r"pocketfm\.com/"],
        reason=(
            "Pocket-FM-Inhalte sind ueber die eigene App DRM-/kontogebunden "
            "ausgeliefert. GENESIS umgeht kein DRM und speichert keine Zugangsdaten "
            "(§30) - ein Download ist hier nicht moeglich."
        ),
    )
