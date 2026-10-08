"""Provider-Registrierung (§30 "Provider muessen austauschbar sein").

Reihenfolge ist relevant fuer `detect_provider`: spezifischere Provider
(YouTube/TikTok/DRM-blockierte Dienste) werden VOR den beiden generischen
Fangnetzen (direkte URL / lokale Datei) geprueft.
"""
from __future__ import annotations

from genesis_core.config import DownloadSettings
from genesis_core.download.base import DownloadProvider, ProviderNotFoundError
from genesis_core.download.direct_url_provider import DirectURLProvider
from genesis_core.download.drm_blocked import (
    build_audible_provider,
    build_pocket_fm_provider,
    build_spotify_provider,
)
from genesis_core.download.local_file_provider import LocalFileProvider
from genesis_core.download.ytdlp_provider import build_tiktok_provider, build_youtube_provider


def build_download_providers(settings: DownloadSettings) -> dict[str, DownloadProvider]:
    """Baut das Provider-Register gemaess Konfiguration. Reine Instanziierung
    (kein Netzwerkzugriff) - ob ein Provider tatsaechlich NUTZBAR ist (z.B.
    yt-dlp installiert?), zeigt erst `check_availability()` pro Aufruf."""
    providers: list[DownloadProvider] = [
        build_spotify_provider(),
        build_audible_provider(),
        build_pocket_fm_provider(),
    ]
    if settings.enable_youtube:
        providers.append(build_youtube_provider())
    if settings.enable_tiktok:
        providers.append(build_tiktok_provider())
    providers.append(
        DirectURLProvider(
            timeout_seconds=settings.request_timeout_seconds,
            max_size_bytes=settings.max_download_size_mb * 1024 * 1024,
        )
    )
    providers.append(LocalFileProvider())
    return {p.provider_id: p for p in providers}


def detect_provider(providers: dict[str, DownloadProvider], url: str) -> DownloadProvider:
    for provider in providers.values():
        if provider.matches(url):
            return provider
    raise ProviderNotFoundError(f"Keine registrierte Quelle erkennt diese Eingabe: {url!r}")
