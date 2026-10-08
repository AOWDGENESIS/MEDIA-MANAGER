"""Liest vorhandene Tags aus einer Mediendatei (§6 Punkt 5, §14).

Nutzt mutagen ausschliesslich LESEND (`mutagen.File(path)`, niemals
`.save()`) - das Schreiben von Tags ist eine separate, bestaetigungspflichtige
Aktion (siehe metadata/engine.py `apply_suggestion`, Prinzip #5/#44).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import mutagen

from genesis_core.logutil import get_logger

log = get_logger("TagReader")

# Gaengige Tag-Schluessel je Containerformat (ID3/Vorbis/MP4 unterscheiden
# sich in ihrer Schreibweise) - mutagen normalisiert das NICHT automatisch
# fuer generische Files, deshalb bilden wir hier selbst auf einen
# einheitlichen Satz ab.
_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "TIT2", "\xa9nam"),
    "artist": ("artist", "TPE1", "\xa9ART"),
    "album": ("album", "TALB", "\xa9alb"),
    "albumartist": ("albumartist", "album_artist", "TPE2", "aART"),
    "tracknumber": ("tracknumber", "TRCK", "trkn"),
    "discnumber": ("discnumber", "TPOS", "disk"),
    "date": ("date", "originaldate", "TDRC", "\xa9day"),
    "genre": ("genre", "TCON", "\xa9gen"),
    "composer": ("composer", "TCOM", "\xa9wrt"),
}


@dataclasses.dataclass
class ExistingTags:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    albumartist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    genre: str | None = None
    composer: str | None = None
    has_any_tag: bool = False


def first_tag_value(tags, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        try:
            key_present = key in tags
        except ValueError:
            # Vorbis-Comment-Container (FLAC/OGG) lehnen bestimmte
            # Schluessel (z.B. MP4-Atom-Namen wie "\xa9day") bereits beim
            # Zugehoerigkeitstest mit ValueError statt False ab, da sie
            # keine gueltigen Vorbis-Feldnamen sind. Das ist hier normal,
            # weil wir dieselbe Alias-Liste formatuebergreifend abfragen.
            continue
        if key_present:
            value = tags[key]
            if isinstance(value, list) and value:
                value = value[0]
            if value is None:
                continue
            if isinstance(value, (bytes, bytearray)):
                # MP4-Freeform-Atome (z.B. "----:com.apple.iTunes:*") werden
                # von mutagen als `MP4FreeForm` geliefert, einer
                # bytes-Unterklasse - `str(b"...")` wuerde die Python-
                # Byte-Repraesentation ("b'...'") statt des Klartexts
                # liefern (Bugfix Phase 5, zuvor nie getriggert, da bisher
                # genutzte Felder alle bereits Text-Objekte waren).
                try:
                    text = value.decode("utf-8", errors="replace").strip()
                except Exception:  # noqa: BLE001 - defensiv, sollte nie passieren
                    text = str(value).strip()
            else:
                text = str(value).strip()
            if text:
                return text
    return None


def parse_leading_int(value: str | None) -> int | None:
    if not value:
        return None
    # z.B. "3/12" (Tracknummer/Gesamtzahl) oder "(3, 12)" (MP4-Tupel-Reprs)
    digits = ""
    for ch in value.lstrip("(").strip():
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def read_existing_tags(path: str | Path) -> ExistingTags:
    """Liest vorhandene Tags. Liefert bei fehlenden/unlesbaren Tags ein
    leeres `ExistingTags` (has_any_tag=False) statt eines Fehlers - fehlende
    Tags sind ein normaler Zustand, kein technischer Defekt."""
    path = Path(path)
    try:
        audio = mutagen.File(path)
    except Exception as exc:  # noqa: BLE001 - mutagen wirft diverse Subklassen
        log.warning("Tags konnten nicht gelesen werden (%s): %s", path.name, exc)
        return ExistingTags()

    if audio is None or audio.tags is None:
        return ExistingTags()

    tags = audio.tags
    result = ExistingTags(
        title=first_tag_value(tags, _KEY_ALIASES["title"]),
        artist=first_tag_value(tags, _KEY_ALIASES["artist"]),
        album=first_tag_value(tags, _KEY_ALIASES["album"]),
        albumartist=first_tag_value(tags, _KEY_ALIASES["albumartist"]),
        track_number=parse_leading_int(first_tag_value(tags, _KEY_ALIASES["tracknumber"])),
        disc_number=parse_leading_int(first_tag_value(tags, _KEY_ALIASES["discnumber"])),
        year=parse_leading_int(first_tag_value(tags, _KEY_ALIASES["date"])),
        genre=first_tag_value(tags, _KEY_ALIASES["genre"]),
        composer=first_tag_value(tags, _KEY_ALIASES["composer"]),
    )
    result.has_any_tag = any(
        v is not None
        for v in (result.title, result.artist, result.album, result.track_number, result.year)
    )
    return result
