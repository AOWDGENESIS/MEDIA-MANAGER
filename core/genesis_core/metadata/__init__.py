"""Metadata-Engine (§10/§11) - siehe engine.py fuer die vollstaendige
Beschreibung des Erkennen->Vorschlag->Confidence-Ablaufs."""
from __future__ import annotations

from genesis_core.metadata.engine import (
    MetadataApplyNotConfirmedError,
    MetadataEngine,
    MetadataSuggestion,
)
from genesis_core.metadata.tag_reader import ExistingTags, read_existing_tags

__all__ = [
    "ExistingTags",
    "MetadataApplyNotConfirmedError",
    "MetadataEngine",
    "MetadataSuggestion",
    "read_existing_tags",
]
