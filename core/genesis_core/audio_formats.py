"""Gemeinsame Audio-Zielformat-/Codec-Zuordnung (§18 Audio Cutter, §19
Loudness-Engine).

Urspruenglich lebte diese Tabelle nur in `genesis_core/loudness/engine.py`
(siehe ADR-0010); mit dem Audio Cutter (ADR-0011) kam ein zweiter
Verbraucher hinzu, der einen vom Quellformat UNABHAENGIGEN Zielformat-
Katalog braucht (Nutzer waehlt explizit MP3/WAV/FLAC, siehe §18) - deshalb
jetzt in ein eigenes, von beiden importiertes Modul extrahiert (bewusst
aufgeschobene Extraktion, siehe PROGRESS.md Sitzung 6: "YAGNI vorerst
bewusst nicht vorgezogen, sobald ein zweiter Verbraucher existiert").
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class AudioFormatSpec:
    name: str
    extension: str
    ffmpeg_codec_args: tuple[str, ...]
    is_lossy: bool


_SPECS = [
    AudioFormatSpec("mp3", ".mp3", ("-c:a", "libmp3lame", "-b:a", "256k"), True),
    AudioFormatSpec("flac", ".flac", ("-c:a", "flac"), False),
    AudioFormatSpec("wav", ".wav", ("-c:a", "pcm_s16le"), False),
    AudioFormatSpec("ogg", ".ogg", ("-c:a", "libvorbis", "-q:a", "6"), True),
    AudioFormatSpec("opus", ".opus", ("-c:a", "libopus", "-b:a", "160k"), True),
    AudioFormatSpec("m4a", ".m4a", ("-c:a", "aac", "-b:a", "256k"), True),
    AudioFormatSpec("aac", ".aac", ("-c:a", "aac", "-b:a", "256k"), True),
]

FORMATS_BY_NAME: dict[str, AudioFormatSpec] = {spec.name: spec for spec in _SPECS}
FORMATS_BY_EXTENSION: dict[str, AudioFormatSpec] = {spec.extension: spec for spec in _SPECS}

# Verlustfreier Rueckfall, wenn ein Quell-/Zielformat nicht in der Tabelle
# steht (z.B. unbekannte/seltene Endung) - lieber verlustfrei und mit
# anderer Endung als ueberhaupt nicht nutzbar (Prinzip #16: transparent,
# nicht stillschweigend falsch gekennzeichnet).
FALLBACK_FORMAT = FORMATS_BY_NAME["flac"]

# §18: "Export mindestens: MP3, WAV, FLAC" - das ist die vom Audio Cutter
# dem Nutzer angebotene Mindestauswahl (mehr Formate sind ueber
# FORMATS_BY_NAME trotzdem technisch verfuegbar).
CUTTER_MINIMUM_EXPORT_FORMATS: tuple[str, ...] = ("mp3", "wav", "flac")


def spec_for_extension(extension: str) -> tuple[AudioFormatSpec, bool]:
    """Liefert (Spec, war_bekannt). Bei unbekannter Endung wird der
    verlustfreie Fallback (FLAC) zurueckgegeben, `war_bekannt=False`."""
    spec = FORMATS_BY_EXTENSION.get(extension.lower())
    if spec is not None:
        return spec, True
    return FALLBACK_FORMAT, False


def spec_for_name(name: str) -> AudioFormatSpec:
    try:
        return FORMATS_BY_NAME[name.lower()]
    except KeyError as exc:
        raise ValueError(
            f"Unbekanntes Zielformat '{name}' - unterstuetzt: {', '.join(FORMATS_BY_NAME)}"
        ) from exc
