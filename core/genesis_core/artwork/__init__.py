"""Artwork Engine (§22).

Drei getrennte, unterschiedlich risikoreiche Operationen:
1. `extract_embedded_artwork` - rein LESEND, kein Risiko (Prinzip #4/#5).
2. Provider-Abruf (`CoverArtArchiveProvider.fetch_front_cover`, siehe
   genesis_core.providers) + `cache_artwork` - schreibt nur eine NEUE Datei
   in den GENESIS-eigenen Cache-Ordner, ruehrt die Mediendatei nicht an.
3. `embed_artwork` - VERAENDERT die Mediendatei selbst (fuegt eingebettetes
   Cover ein) - erfordert daher IMMER `user_confirmed=True`, exakt wie
   Rename/Metadaten-Uebernahme (Prinzip #17, §44).
"""
from __future__ import annotations

from genesis_core.artwork.engine import (
    ArtworkApplyNotConfirmedError,
    ArtworkError,
    cache_artwork,
    embed_artwork,
    extract_embedded_artwork,
)

__all__ = [
    "ArtworkApplyNotConfirmedError",
    "ArtworkError",
    "cache_artwork",
    "embed_artwork",
    "extract_embedded_artwork",
]
