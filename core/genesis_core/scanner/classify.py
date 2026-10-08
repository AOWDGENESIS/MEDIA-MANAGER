"""Format-Erkennung und grobe Klassifikation nach Dateiendung.

Dies ist eine erste, konservative Heuristik (Dateiendung -> Medienart). Eine
verfeinerte Klassifikation (z.B. Musik vs. Hoerbuch bei gleicher Endung
".m4a"/".mp3") erfolgt spaeter zusaetzlich ueber Tags/Laufzeit/Verzeichnis-
struktur in der Metadata-Engine (Phase 2+) - hier wird bewusst NICHT geraten,
sondern nur eindeutig Zuordenbares klassifiziert; alles andere -> UNKNOWN
(Prinzip #16: transparent, nichts erfinden).
"""
from __future__ import annotations

from genesis_core.db.models import MediaKind

AUDIO_MUSIC_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".aiff", ".aif", ".aac", ".m4a", ".alac",
    ".ogg", ".opus", ".wma",
}

AUDIOBOOK_SPECIFIC_EXTENSIONS = {".m4b"}

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv"}

# Endungen, die sowohl fuer Musik als auch Hoerbuch ueblich sind -> ohne
# weitere Analyse (Tags/Ordnerstruktur, spaetere Phase) bleibt es bei
# MUSIC als konservativem Default, NICHT bei UNKNOWN, weil das die deutlich
# haeufigere Verwendung ist. Die tatsaechliche Unterscheidung Musik/Hoerbuch
# erfolgt inhaltlich in Phase 2/4 (Metadata-Engine), niemals hier geraten.
AMBIGUOUS_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".flac", ".wav"}


def classify_by_extension(extension: str) -> MediaKind:
    ext = extension.lower()
    if ext in AUDIOBOOK_SPECIFIC_EXTENSIONS:
        return MediaKind.AUDIOBOOK
    if ext in VIDEO_EXTENSIONS:
        return MediaKind.MOVIE  # Film/Serie-Unterscheidung folgt in Phase 5
    if ext in AUDIO_MUSIC_EXTENSIONS:
        return MediaKind.MUSIC
    return MediaKind.UNKNOWN


def is_supported_media_extension(extension: str) -> bool:
    ext = extension.lower()
    return (
        ext in AUDIO_MUSIC_EXTENSIONS
        or ext in AUDIOBOOK_SPECIFIC_EXTENSIONS
        or ext in VIDEO_EXTENSIONS
    )
