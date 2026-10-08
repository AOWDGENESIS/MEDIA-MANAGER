"""Hashing-Hilfsfunktionen (§6 Punkt 6: Hash erzeugen).

Read-only: Dateien werden ausschliesslich gelesen, niemals veraendert.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_of_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()
