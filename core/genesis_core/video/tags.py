"""Liest film-/serienspezifische Tags aus einer Mediendatei (§24).

Analog zu `genesis_core.audiobook.tags` - rein LESEND, niemals
`.save()` (siehe `metadata/tag_reader.py` Moduldocstring). Es gibt keinen
Online-Provider (TMDb/IMDb o.ä. wären Download/Import-Adapter, Phase 8) -
alle Werte stammen ausschliesslich aus bereits in der Datei eingebetteten
Tags.

Zwei Lesewege, je nach Containerformat:
1. MP4-Familie (`.mp4`, `.m4v`, `.mov`) - `mutagen` liest Standard-Atome
   (`\xa9nam`, `tvsh`/`tvsn`/`tves` fuer TV-Shows) UND Freeform-Atome
   (`----:com.apple.iTunes:*`, z.B. fuer Regisseur/Schauspieler, die es als
   MP4-Standardatom nicht gibt).
2. Alle anderen unterstuetzten Video-Container (`.mkv`, `.avi`, `.webm`,
   `.wmv`) - `mutagen` bietet dafuer KEINE Tag-Lese-API; stattdessen werden
   die globalen Format-Tags aus dem bereits vorhandenen rohen ffprobe-JSON
   genutzt (gaengige Konvention bei mit `mkvpropedit`/`mkvmerge` getaggten
   Matroska-Dateien: Grossbuchstaben-Schluessel wie TITLE/DATE/GENRE/
   DIRECTOR/ACTOR/SHOW).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import mutagen

from genesis_core.logutil import get_logger
from genesis_core.metadata.tag_reader import first_tag_value, parse_leading_int
from genesis_core.scanner.ffprobe_util import probe_file

log = get_logger("VideoTagReader")

_TITLE_KEYS = ("title", "TIT2", "\xa9nam", "TITLE")
_YEAR_KEYS = ("date", "originaldate", "TDRC", "\xa9day", "DATE", "YEAR")
_GENRE_KEYS = ("genre", "TCON", "\xa9gen", "GENRE")
_DESCRIPTION_KEYS = (
    "description", "comment", "TIT3", "desc", "ldes", "\xa9cmt",
    "----:com.apple.iTunes:DESCRIPTION", "DESCRIPTION", "SYNOPSIS", "COMMENT",
)
_DIRECTOR_KEYS = (
    "TXXX:DIRECTOR", "----:com.apple.iTunes:DIRECTOR", "----:com.apple.iTunes:Director",
    "DIRECTOR",
)
_ACTOR_KEYS = (
    "TXXX:ACTOR", "TXXX:ACTORS", "----:com.apple.iTunes:ACTOR", "----:com.apple.iTunes:Actor",
    "----:com.apple.iTunes:CAST", "ACTOR", "ACTORS", "CAST",
)
_SERIES_KEYS = ("tvsh", "TXXX:SHOW", "TXXX:SERIES", "SHOW", "SERIES")
_SEASON_KEYS = ("tvsn", "TXXX:SEASON", "TXXX:SEASON_NUMBER", "SEASON", "SEASON_NUMBER")
_EPISODE_KEYS = (
    "tves", "TXXX:EPISODE", "TXXX:EPISODE_NUMBER", "TXXX:EPISODE_SORT",
    "EPISODE", "EPISODE_NUMBER", "EPISODE_SORT",
)


@dataclasses.dataclass
class VideoTagSnapshot:
    title: str | None = None
    year: int | None = None
    genre: str | None = None
    description: str | None = None
    director_names: list[str] = dataclasses.field(default_factory=list)
    actor_names: list[str] = dataclasses.field(default_factory=list)
    series: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    has_any_tag: bool = False


def _split_names(raw: str | None) -> list[str]:
    """Mehrere Namen in einem Feld (z.B. "Anna Meier, Peter Schmidt") werden
    an Komma/Semikolon getrennt - rein mechanische Aufteilung, keine
    Erfindung neuer Information (Prinzip #16)."""
    if not raw:
        return []
    parts = raw.replace(";", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def _snapshot_from_tags(tags: Any) -> VideoTagSnapshot:
    result = VideoTagSnapshot(
        title=first_tag_value(tags, _TITLE_KEYS),
        year=parse_leading_int(first_tag_value(tags, _YEAR_KEYS)),
        genre=first_tag_value(tags, _GENRE_KEYS),
        description=first_tag_value(tags, _DESCRIPTION_KEYS),
        director_names=_split_names(first_tag_value(tags, _DIRECTOR_KEYS)),
        actor_names=_split_names(first_tag_value(tags, _ACTOR_KEYS)),
        series=first_tag_value(tags, _SERIES_KEYS),
        season_number=parse_leading_int(first_tag_value(tags, _SEASON_KEYS)),
        episode_number=parse_leading_int(first_tag_value(tags, _EPISODE_KEYS)),
    )
    result.has_any_tag = any(
        v for v in (
            result.title, result.year, result.series, result.season_number,
            result.episode_number, result.director_names, result.actor_names,
        )
    )
    return result


def read_video_tags(path: str | Path) -> VideoTagSnapshot:
    """Liest vorhandene Film-/Serien-Tags. Liefert bei fehlenden/unlesbaren
    Tags einen leeren `VideoTagSnapshot` (has_any_tag=False) statt eines
    Fehlers - fehlende Tags sind ein normaler Zustand, kein Defekt."""
    path = Path(path)
    try:
        audio = mutagen.File(path)
    except Exception as exc:  # noqa: BLE001 - mutagen wirft diverse Subklassen
        log.warning("Video-Tags konnten nicht gelesen werden (%s): %s", path.name, exc)
        audio = None

    if audio is not None and audio.tags is not None:
        return _snapshot_from_tags(audio.tags)

    # Fallback fuer Container ohne mutagen-Tag-Unterstuetzung (MKV/AVI/
    # WMV/WebM) - nutzt die bereits vorhandene ffprobe-Grundlage.
    raw = probe_file(path)
    if raw is None:
        return VideoTagSnapshot()
    format_tags = (raw.get("format", {}) or {}).get("tags", {}) or {}
    # ffprobe liefert Format-Tags als flaches Dict mit genau EINEM String-
    # Wert pro Schluessel (kein Listen-Wrapping wie bei mutagen) - fuer
    # `first_tag_value()` wird das als Ein-Element-"Tags"-Mapping behandelt,
    # indem die Werte in Listen verpackt werden (gleiche erwartete Form).
    wrapped = {k: [v] for k, v in format_tags.items()}
    return _snapshot_from_tags(wrapped)
