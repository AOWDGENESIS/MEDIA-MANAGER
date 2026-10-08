"""Tests fuer genesis_core.scanner.ffprobe_util (§6 Punkt 4, §20, §24, §47).

Testet ausschliesslich die reine Parsing-/Reduktionslogik auf synthetischem
ffprobe-JSON (kein echter ffprobe-Subprozess noetig) - inkl. der in dieser
Phase neu hinzugekommenen Sprachen-/Untertitel-Extraktion fuer Filme/Serien.
"""
from __future__ import annotations

from genesis_core.scanner.ffprobe_util import (
    _collect_stream_languages,
    _collect_subtitle_streams,
    _parse_frame_rate,
    extract_technical_summary,
    ffprobe_available,
    probe_file,
)


def test_ffprobe_available_is_bool():
    assert isinstance(ffprobe_available(), bool)


def test_probe_file_missing_file_returns_none_or_handles_gracefully(tmp_path):
    # Egal ob ffprobe installiert ist oder nicht: eine nicht existierende
    # Datei darf niemals eine Exception werfen (Prinzip #19 - strukturierte
    # Fehlerbehandlung statt stillem/hartem Fehlschlag).
    missing = tmp_path / "does_not_exist.mp4"
    result = probe_file(missing)
    assert result is None


def test_extract_technical_summary_audio_only():
    raw = {
        "format": {"format_name": "mp3", "duration": "123.456", "bit_rate": "192000"},
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "mp3",
                "sample_rate": "44100",
                "channels": 2,
                "bits_per_sample": 16,
            }
        ],
        "chapters": [],
    }
    summary = extract_technical_summary(raw)
    assert summary["container_format"] == "mp3"
    assert summary["duration_seconds"] == 123.456
    assert summary["bitrate_kbps"] == 192
    assert summary["chapters_count"] == 0
    assert summary["audio_codec"] == "mp3"
    assert summary["sample_rate_hz"] == 44100
    assert summary["channels"] == 2
    assert summary["bit_depth"] == 16
    # Keine Video-Felder, kein video_stream vorhanden
    assert "video_codec" not in summary
    # Keine Sprachen-/Untertitel-Tags vorhanden -> Felder fehlen komplett
    # (nicht leere Liste, s. Doku in ffprobe_util.py: "fehlendes Tag wird
    # nicht geraten")
    assert "languages_json" not in summary
    assert "subtitles_json" not in summary
    assert summary["raw_ffprobe_json"] == raw


def test_extract_technical_summary_video_with_hdr_and_languages_and_subtitles():
    raw = {
        "format": {"format_name": "mov,mp4,m4a", "duration": "5400.0", "bit_rate": "8000000"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 3840,
                "height": 2160,
                "avg_frame_rate": "24000/1001",
                "color_transfer": "smpte2084",
            },
            {
                "codec_type": "audio",
                "codec_name": "eac3",
                "sample_rate": "48000",
                "channels": 6,
                "tags": {"language": "eng"},
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "tags": {"language": "ger"},
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "tags": {"language": "eng"},  # Duplikat -> darf nicht doppelt erscheinen
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "tags": {},  # kein Sprachen-Tag -> wird ausgelassen, nicht geraten
            },
            {
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "tags": {"language": "ger", "title": "Deutsch (Forced)"},
                "disposition": {"forced": 1},
            },
            {
                "codec_type": "subtitle",
                "codec_name": "ass",
                "tags": {"language": "eng", "title": "English"},
                "disposition": {"forced": 0},
            },
        ],
        "chapters": [{"id": 0}, {"id": 1}],
    }
    summary = extract_technical_summary(raw)

    assert summary["video_codec"] == "hevc"
    assert summary["resolution_width"] == 3840
    assert summary["resolution_height"] == 2160
    assert summary["fps"] == round(24000 / 1001, 3)
    assert summary["hdr"] is True
    assert summary["chapters_count"] == 2

    # Erster gefundener Audio-Stream bestimmt die primaeren Audio-Felder.
    assert summary["audio_codec"] == "eac3"
    assert summary["channels"] == 6

    # Sprachen dedupliziert, reihenfolgeerhaltend, "und"/leer ausgelassen.
    assert summary["languages_json"] == ["eng", "ger"]

    # Untertitel-Liste mit Sprache/Codec/Titel/Forced-Flag.
    assert summary["subtitles_json"] == [
        {"language": "ger", "codec": "subrip", "title": "Deutsch (Forced)", "forced": True},
        {"language": "eng", "codec": "ass", "title": "English", "forced": False},
    ]


def test_extract_technical_summary_undetermined_language_is_skipped():
    raw = {
        "format": {},
        "streams": [
            {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "und"}},
            {"codec_type": "audio", "codec_name": "aac", "tags": {"language": "unk"}},
        ],
        "chapters": [],
    }
    summary = extract_technical_summary(raw)
    assert "languages_json" not in summary


def test_collect_stream_languages_filters_by_codec_type():
    streams = [
        {"codec_type": "audio", "tags": {"language": "eng"}},
        {"codec_type": "subtitle", "tags": {"language": "fre"}},
        {"codec_type": "video", "tags": {"language": "xxx"}},
    ]
    assert _collect_stream_languages(streams, codec_type="audio") == ["eng"]
    assert _collect_stream_languages(streams, codec_type="subtitle") == ["fre"]


def test_collect_subtitle_streams_empty_when_none_present():
    streams = [{"codec_type": "audio"}, {"codec_type": "video"}]
    assert _collect_subtitle_streams(streams) == []


def test_parse_frame_rate_fraction():
    assert _parse_frame_rate("30000/1001") == round(30000 / 1001, 3)


def test_parse_frame_rate_plain_number():
    assert _parse_frame_rate("25") == 25.0


def test_parse_frame_rate_invalid_values_return_none():
    assert _parse_frame_rate(None) is None
    assert _parse_frame_rate("0/0") is None
    assert _parse_frame_rate("N/A") is None
    assert _parse_frame_rate("not-a-number") is None
