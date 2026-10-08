"""FFprobe-Anbindung fuer technische Medienanalyse (§6 Punkt 4, §47).

Nutzt das system-installierte FFmpeg/FFprobe (Open Source, siehe
licenses/THIRD-PARTY-LICENSES.md fuer die konkrete Build-Variante/Lizenz,
Prinzip #10/#47). Rein lesend - FFprobe veraendert nie die Quelldatei.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from genesis_core.logutil import get_logger

log = get_logger("FFprobe")


class FFprobeNotAvailable(RuntimeError):
    pass


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def probe_file(path: str | Path, timeout_seconds: float = 30.0) -> dict[str, Any] | None:
    """Liefert das rohe ffprobe-JSON oder None, wenn ffprobe fehlt/fehlschlaegt.

    Fehler werden geloggt, nie stillschweigend verschluckt (Prinzip #19/§37) -
    aber der Scan bricht dadurch nicht ab (eine Datei ohne technische Analyse
    bleibt UNKNOWN/unvollstaendig, statt den ganzen Scan zu stoppen).
    """
    if not ffprobe_available():
        log.warning("ffprobe nicht gefunden - technische Analyse wird uebersprungen")
        return None
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-show_chapters",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as exc:
        log.warning("ffprobe fehlgeschlagen fuer %s: %s", path, exc.stderr.strip())
        return None
    except subprocess.TimeoutExpired:
        log.warning("ffprobe Timeout fuer %s", path)
        return None
    except json.JSONDecodeError:
        log.warning("ffprobe lieferte ungueltiges JSON fuer %s", path)
        return None


def extract_technical_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Reduziert das rohe ffprobe-JSON auf die Felder unseres
    TechnicalMetadata-Schemas (§20/§3 Filme)."""

    fmt = raw.get("format", {}) or {}
    streams = raw.get("streams", []) or []
    chapters = raw.get("chapters", []) or []

    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

    summary: dict[str, Any] = {
        "container_format": fmt.get("format_name"),
        "duration_seconds": float(fmt["duration"]) if fmt.get("duration") else None,
        "bitrate_kbps": int(int(fmt["bit_rate"]) / 1000) if fmt.get("bit_rate") else None,
        "chapters_count": len(chapters),
    }

    if audio_stream:
        summary["audio_codec"] = audio_stream.get("codec_name")
        summary["sample_rate_hz"] = (
            int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate") else None
        )
        summary["channels"] = audio_stream.get("channels")
        bits = audio_stream.get("bits_per_raw_sample") or audio_stream.get("bits_per_sample")
        summary["bit_depth"] = int(bits) if bits else None

    if video_stream:
        summary["video_codec"] = video_stream.get("codec_name")
        summary["resolution_width"] = video_stream.get("width")
        summary["resolution_height"] = video_stream.get("height")
        fps_raw = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        summary["fps"] = _parse_frame_rate(fps_raw)
        color_transfer = (video_stream.get("color_transfer") or "").lower()
        summary["hdr"] = color_transfer in {"smpte2084", "arib-std-b67"}

    # §24 (Filme/Serien) - Sprachen/Untertitel. Wird unabhaengig von der
    # Medienart ermittelt (schadet bei Musik/Hoerbuch nicht, ist dort nur
    # meist leer) - rein deskriptiv aus bereits vorhandenen Stream-Tags,
    # nichts wird erraten (Prinzip #16).
    languages = _collect_stream_languages(streams, codec_type="audio")
    if languages:
        summary["languages_json"] = languages
    subtitles = _collect_subtitle_streams(streams)
    if subtitles:
        summary["subtitles_json"] = subtitles

    summary["raw_ffprobe_json"] = raw
    return summary


def _collect_stream_languages(streams: list[dict[str, Any]], *, codec_type: str) -> list[str]:
    """Deduplizierte, reihenfolgeerhaltende Liste der Sprachcodes (z.B.
    "eng", "ger") aus den `tags.language`-Feldern der passenden Streams.
    Fehlt das Tag, wird NICHTS geraten (keine Sprache != unbekannte Sprache
    wird unterschieden - fehlende Eintraege werden einfach ausgelassen)."""
    seen: list[str] = []
    for stream in streams:
        if stream.get("codec_type") != codec_type:
            continue
        lang = ((stream.get("tags") or {}).get("language") or "").strip()
        if lang and lang.lower() not in {"und", "unk"} and lang not in seen:
            seen.append(lang)
    return seen


def _collect_subtitle_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Liste bereits eingebetteter Untertitel-Spuren (Sprache/Codec/Titel/
    Forced-Flag) - rein deskriptiv, keine Untertitel-Erzeugung/-Aenderung."""
    subtitles: list[dict[str, Any]] = []
    for stream in streams:
        if stream.get("codec_type") != "subtitle":
            continue
        tags = stream.get("tags") or {}
        disposition = stream.get("disposition") or {}
        subtitles.append(
            {
                "language": tags.get("language"),
                "codec": stream.get("codec_name"),
                "title": tags.get("title"),
                "forced": bool(disposition.get("forced")),
            }
        )
    return subtitles


def _parse_frame_rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        if "/" in value:
            num, den = value.split("/")
            den_f = float(den)
            return round(float(num) / den_f, 3) if den_f else None
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None
