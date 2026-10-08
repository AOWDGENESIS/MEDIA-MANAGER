"""Online-Metadaten-Provider (§10, §22) - MusicBrainz, AcoustID, Cover Art
Archive. Alle drei sind reine LESE-Clients externer, offener Dienste.

Werden nur genutzt, wenn `Settings.metadata.enabled=True` (Default: AUS,
§56 - kein Internetzwang). Siehe genesis_core/metadata/engine.py fuer die
Orchestrierung und Konfidenzberechnung.
"""
from __future__ import annotations

from genesis_core.config import MetadataSettings
from genesis_core.providers.acoustid import AcoustIDProvider
from genesis_core.providers.base import (
    ProviderError,
    ProviderNotConfiguredError,
    RecordingMatch,
)
from genesis_core.providers.coverartarchive import CoverArtArchiveProvider
from genesis_core.providers.musicbrainz import MusicBrainzProvider


class ProviderBundle:
    """Haelt die konfigurierten Provider-Instanzen fuer die Lebensdauer des
    Prozesses bzw. einer Test-Instanz. Nicht konfigurierte/deaktivierte
    Provider sind hier bewusst `None` statt eines Fake-Objekts, damit die
    Engine explizit "nicht verfuegbar" statt eines stillen Fallbacks meldet
    (Prinzip #16)."""

    def __init__(
        self,
        musicbrainz: MusicBrainzProvider | None,
        acoustid: AcoustIDProvider | None,
        coverartarchive: CoverArtArchiveProvider | None,
    ):
        self.musicbrainz = musicbrainz
        self.acoustid = acoustid
        self.coverartarchive = coverartarchive

    def close(self) -> None:
        for provider in (self.musicbrainz, self.acoustid, self.coverartarchive):
            if provider is not None:
                provider.close()


def build_providers(settings: MetadataSettings) -> ProviderBundle:
    """Fabrikfunktion analog zu genesis_core.ai.build_ai_provider - erzeugt
    nur Provider, die der Nutzer explizit aktiviert hat."""
    if not settings.enabled:
        return ProviderBundle(musicbrainz=None, acoustid=None, coverartarchive=None)

    musicbrainz = (
        MusicBrainzProvider(
            contact_email=settings.contact_email,
            timeout_seconds=settings.request_timeout_seconds,
        )
        if settings.musicbrainz_enabled
        else None
    )
    acoustid = (
        AcoustIDProvider(
            api_key=settings.acoustid_api_key,
            contact_email=settings.contact_email,
            timeout_seconds=settings.request_timeout_seconds,
        )
        if settings.acoustid_enabled
        else None
    )
    coverartarchive = (
        CoverArtArchiveProvider(
            contact_email=settings.contact_email,
            timeout_seconds=settings.request_timeout_seconds,
        )
        if settings.coverartarchive_enabled
        else None
    )
    return ProviderBundle(
        musicbrainz=musicbrainz, acoustid=acoustid, coverartarchive=coverartarchive
    )


__all__ = [
    "AcoustIDProvider",
    "CoverArtArchiveProvider",
    "MusicBrainzProvider",
    "ProviderBundle",
    "ProviderError",
    "ProviderNotConfiguredError",
    "RecordingMatch",
    "build_providers",
]
