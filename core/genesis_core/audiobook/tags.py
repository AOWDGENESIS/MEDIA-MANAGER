"""Liest hörbuchspezifische Tags aus einer Mediendatei (§23).

Nutzt dieselbe mutagen-Grundlage wie `genesis_core.metadata.tag_reader`
(rein LESEND, siehe dortigen Moduldocstring), ergänzt aber eigene
Tag-Aliase für Felder, die für Musik irrelevant sind (Autor, Sprecher,
Reihe, Bandnummer, Verlag, Sprache, Beschreibung).

Es gibt für diese Felder KEINEN einheitlichen Standard über ID3/Vorbis/MP4
hinweg (anders als z.B. Titel/Interpret) - viele Hörbuch-Tagging-Tools
(z.B. Mp3tag, AudioBookShelf) nutzen uneinheitliche Konventionen. Diese
Funktion probiert mehrere gängige Varianten je Feld, erfindet aber NIEMALS
einen Wert (Prinzip #16) - jedes Feld bleibt `None`, wenn keine der
bekannten Tag-Varianten vorhanden ist. Der Autor wird zusätzlich aus dem
generischen "artist"-Feld übernommen, FALLS kein dediziertes
Autor-Tag existiert - das ist eine gängige Praxis vieler Hörbuch-Encoder,
wird aber transparent über `author_source` offengelegt, damit der Nutzer
erkennt, woher der Wert stammt.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import mutagen

from genesis_core.logutil import get_logger
from genesis_core.metadata.tag_reader import first_tag_value, parse_leading_int

log = get_logger("AudiobookTagReader")

_AUTHOR_KEYS = ("author", "TXXX:AUTHOR", "----:com.apple.iTunes:AUTHOR")
_ARTIST_KEYS = ("artist", "TPE1", "\xa9ART")
_NARRATOR_KEYS = ("narrator", "TXXX:NARRATOR", "----:com.apple.iTunes:NARRATOR")
_COMPOSER_AS_NARRATOR_KEYS = ("composer", "TCOM", "\xa9wrt")
_SERIES_KEYS = (
    "series", "TXXX:SERIES", "----:com.apple.iTunes:SERIES", "\xa9grp", "grouping",
)
_SERIES_PART_KEYS = (
    "seriespart", "series-part", "TXXX:SERIES-PART", "----:com.apple.iTunes:SERIES-PART",
    "movementnumber", "mvin",
)
_PUBLISHER_KEYS = ("publisher", "organization", "TPUB", "----:com.apple.iTunes:PUBLISHER")
_LANGUAGE_KEYS = ("language", "TLAN", "----:com.apple.iTunes:LANGUAGE")
_DESCRIPTION_KEYS = (
    "description", "comment", "TIT3", "COMM::eng", "\xa9cmt", "ldes", "desc",
    "----:com.apple.iTunes:DESCRIPTION",
)
_TITLE_KEYS = ("title", "TIT2", "\xa9nam")
_ALBUM_KEYS = ("album", "TALB", "\xa9alb")
_DATE_KEYS = ("date", "originaldate", "TDRC", "\xa9day")


@dataclasses.dataclass
class AudiobookTagSnapshot:
    title: str | None = None
    author: str | None = None
    author_source: str | None = None  # "tag" oder "artist_field" (Transparenz, Prinzip #16)
    narrator: str | None = None
    narrator_source: str | None = None  # "tag" oder "composer_field"
    series: str | None = None
    series_source: str | None = None  # "tag" oder "album_field"
    volume_number: int | None = None
    publisher: str | None = None
    year: int | None = None
    language: str | None = None
    description: str | None = None
    has_any_tag: bool = False


def read_audiobook_tags(path: str | Path) -> AudiobookTagSnapshot:
    """Liest vorhandene Hörbuch-Tags. Liefert bei fehlenden/unlesbaren Tags
    einen leeren `AudiobookTagSnapshot` (has_any_tag=False) statt eines
    Fehlers - fehlende Tags sind ein normaler Zustand, kein Defekt."""
    path = Path(path)
    try:
        audio = mutagen.File(path)
    except Exception as exc:  # noqa: BLE001 - mutagen wirft diverse Subklassen
        log.warning("Hörbuch-Tags konnten nicht gelesen werden (%s): %s", path.name, exc)
        return AudiobookTagSnapshot()

    if audio is None or audio.tags is None:
        return AudiobookTagSnapshot()

    tags = audio.tags

    author = first_tag_value(tags, _AUTHOR_KEYS)
    author_source = "tag" if author else None
    if author is None:
        author = first_tag_value(tags, _ARTIST_KEYS)
        author_source = "artist_field" if author else None

    narrator = first_tag_value(tags, _NARRATOR_KEYS)
    narrator_source = "tag" if narrator else None
    if narrator is None:
        narrator = first_tag_value(tags, _COMPOSER_AS_NARRATOR_KEYS)
        narrator_source = "composer_field" if narrator else None

    series = first_tag_value(tags, _SERIES_KEYS)
    series_source = "tag" if series else None
    if series is None:
        series = first_tag_value(tags, _ALBUM_KEYS)
        series_source = "album_field" if series else None

    result = AudiobookTagSnapshot(
        title=first_tag_value(tags, _TITLE_KEYS),
        author=author,
        author_source=author_source,
        narrator=narrator,
        narrator_source=narrator_source,
        series=series,
        series_source=series_source,
        volume_number=parse_leading_int(first_tag_value(tags, _SERIES_PART_KEYS)),
        publisher=first_tag_value(tags, _PUBLISHER_KEYS),
        year=parse_leading_int(first_tag_value(tags, _DATE_KEYS)),
        language=first_tag_value(tags, _LANGUAGE_KEYS),
        description=first_tag_value(tags, _DESCRIPTION_KEYS),
    )
    result.has_any_tag = any(
        v is not None
        for v in (result.title, result.author, result.narrator, result.series, result.year)
    )
    return result
