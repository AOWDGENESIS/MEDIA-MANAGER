"""Mehrstufige Duplikaterkennung (§21).

Oeffentliche Fassade, analog zu `genesis_core.loudness`/`genesis_core.cutter`/
`genesis_core.convert`.
"""
from __future__ import annotations

from genesis_core.duplicates.engine import (
    DuplicateCandidate,
    DuplicateCategory,
    MediaSnapshot,
    compare_pair,
    find_duplicate_candidates,
)

__all__ = [
    "DuplicateCandidate",
    "DuplicateCategory",
    "MediaSnapshot",
    "compare_pair",
    "find_duplicate_candidates",
]
