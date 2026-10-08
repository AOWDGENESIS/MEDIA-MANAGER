"""Download-/Import-Center (§30-§32, ADR-0019).

Swappable Provider-Architektur fuer den Import von Mediendateien aus
unterschiedlichen Quellen (lokale Dateien, direkte Medien-URLs,
YouTube/TikTok ueber yt-dlp) sowie explizit korrekt ERKANNTE und GEMELDETE
Nichtverfuegbarkeit bei DRM-/anmeldepflichtigen Diensten (Spotify, Audible,
Pocket FM) - siehe `genesis_core.download.drm_blocked`.

Siehe `genesis_core.download.engine.DownloadEngine` fuer die Orchestrierung
des kompletten §31-Workflows und `genesis_core.download.registry` fuer die
Provider-Registrierung.
"""
from __future__ import annotations

from genesis_core.download.base import (
    AvailabilityResult,
    ConfirmationRequiredError,
    DownloadedFile,
    DownloadError,
    DownloadNotPermittedError,
    DownloadOption,
    DownloadProvider,
    ProviderNotFoundError,
    SourceMetadata,
)
from genesis_core.download.engine import DownloadEngine, ImportResult
from genesis_core.download.registry import build_download_providers, detect_provider

__all__ = [
    "AvailabilityResult",
    "ConfirmationRequiredError",
    "DownloadEngine",
    "DownloadError",
    "DownloadNotPermittedError",
    "DownloadOption",
    "DownloadProvider",
    "DownloadedFile",
    "ImportResult",
    "ProviderNotFoundError",
    "SourceMetadata",
    "build_download_providers",
    "detect_provider",
]
