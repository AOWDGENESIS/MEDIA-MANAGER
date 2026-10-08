"""Hörbuch-Modul (§23): Tag-basierte Metadaten + Kapitel-Verwaltung.

Siehe `tags.py` (reines Lesen eingebetteter Tags) und `engine.py`
(Übernahme in die DB + Kapitel-Erkennung/-Erzeugung/-Export). Bewusst OHNE
Online-Provider - siehe Moduldocstring in `engine.py`.
"""
from genesis_core.audiobook.engine import (
    AudiobookApplyNotConfirmedError,
    ChapterCandidate,
    ChapterDetectionError,
    apply_audiobook_tags,
    detect_chapters,
    export_chapters_csv,
    export_chapters_json,
    generate_fixed_interval_chapters,
    replace_chapters,
)
from genesis_core.audiobook.tags import AudiobookTagSnapshot, read_audiobook_tags

__all__ = [
    "AudiobookApplyNotConfirmedError",
    "AudiobookTagSnapshot",
    "ChapterCandidate",
    "ChapterDetectionError",
    "apply_audiobook_tags",
    "detect_chapters",
    "export_chapters_csv",
    "export_chapters_json",
    "generate_fixed_interval_chapters",
    "read_audiobook_tags",
    "replace_chapters",
]
