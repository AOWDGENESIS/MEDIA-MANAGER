"""Hashing-Hilfsfunktionen (§6 Punkt 6: Hash erzeugen).

Read-only: Dateien werden ausschliesslich gelesen, niemals veraendert.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable


def sha256_of_file(
    path: str | Path, chunk_size: int = 1024 * 1024,
    checkpoint: Callable[[], None] | None = None,
) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if checkpoint is not None:
                checkpoint()
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()
