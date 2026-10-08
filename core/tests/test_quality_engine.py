"""Tests fuer die Qualitaetsanalyse (§20, ADR-0014).

Reine Unit-Tests auf Basis von `QualitySnapshot` - keine Dateien/DB noetig.
"""
from __future__ import annotations

from genesis_core.quality import QualitySnapshot, analyze_quality


def _snap(**overrides) -> QualitySnapshot:
    defaults = {
        "media_file_id": 1,
        "extension": "mp3",
        "container_format": "mp3",
        "audio_codec": "mp3",
        "bitrate_kbps": 320,
        "sample_rate_hz": 44100,
        "bit_depth": None,
        "channels": 2,
        "duration_seconds": 180.0,
        "tag_duration_seconds": 180.0,
        "size_bytes": 1_000_000,
        "last_scan_error": None,
        "integrated_lufs": -14.0,
        "true_peak_dbtp": -1.0,
    }
    defaults.update(overrides)
    return QualitySnapshot(**defaults)


def test_clean_file_has_no_suspicions():
    report = analyze_quality(_snap())
    assert not report.suspected_upscale
    assert not report.suspected_transcode
    assert not report.suspected_corruption
    assert not report.suspected_truncation
    assert "Keine Auffälligkeiten" in report.notes[0]


def test_tag_duration_much_longer_than_measured_flags_truncation():
    report = analyze_quality(_snap(tag_duration_seconds=240.0, duration_seconds=180.0))
    assert report.suspected_truncation
    assert any("abgeschnittene" in n for n in report.notes)


def test_small_duration_rounding_difference_does_not_flag_truncation():
    report = analyze_quality(_snap(tag_duration_seconds=180.4, duration_seconds=180.0))
    assert not report.suspected_truncation


def test_missing_tag_duration_cannot_flag_truncation():
    report = analyze_quality(_snap(tag_duration_seconds=None, duration_seconds=10.0))
    assert not report.suspected_truncation


def test_scan_error_flags_corruption():
    report = analyze_quality(_snap(last_scan_error="ffprobe: invalid data"))
    assert report.suspected_corruption
    assert any("Beschädigung" in n for n in report.notes)


def test_missing_duration_on_nonempty_file_flags_corruption():
    report = analyze_quality(_snap(duration_seconds=None, size_bytes=5000))
    assert report.suspected_corruption


def test_missing_duration_on_empty_file_does_not_flag_corruption():
    """Eine komplett leere Datei (0 Bytes) wuerde beim Scan ohnehin schon
    anders behandelt - kein zusaetzlicher falsch-positiver Verdacht noetig."""
    report = analyze_quality(_snap(duration_seconds=None, size_bytes=0))
    assert not report.suspected_corruption


def test_codec_mismatch_with_extension_flags_transcode():
    report = analyze_quality(_snap(extension="flac", audio_codec="mp3"))
    assert report.suspected_transcode
    assert any("Transcodierung" in n for n in report.notes)


def test_matching_codec_and_extension_does_not_flag_transcode():
    report = analyze_quality(_snap(extension="flac", audio_codec="flac"))
    assert not report.suspected_transcode


def test_unknown_extension_cannot_flag_transcode():
    report = analyze_quality(_snap(extension="xyz", audio_codec="mp3"))
    assert not report.suspected_transcode


def test_wav_pcm_matching_family_does_not_flag_transcode():
    report = analyze_quality(_snap(extension="wav", audio_codec="pcm_s16le"))
    assert not report.suspected_transcode


def test_low_bitrate_flac_flags_upscale_suspicion():
    report = analyze_quality(
        _snap(extension="flac", audio_codec="flac", bitrate_kbps=150,
              sample_rate_hz=44100, bit_depth=16, channels=2)
    )
    assert report.suspected_upscale
    assert any("Upscale" in n for n in report.notes)


def test_normal_flac_compression_ratio_does_not_flag_upscale():
    report = analyze_quality(
        _snap(extension="flac", audio_codec="flac", bitrate_kbps=900,
              sample_rate_hz=44100, bit_depth=16, channels=2)
    )
    assert not report.suspected_upscale


def test_raw_pcm_wav_is_never_flagged_as_upscale():
    """Rohes PCM hat eine durch das Format fest vorgegebene Bitrate - niemals
    ein Kompressions-/Upscale-Indiz, unabhaengig vom Wert."""
    report = analyze_quality(
        _snap(extension="wav", audio_codec="pcm_s16le", bitrate_kbps=10,
              sample_rate_hz=44100, bit_depth=16, channels=2)
    )
    assert not report.suspected_upscale


def test_missing_bit_depth_assumes_16_bit_conservatively():
    report = analyze_quality(
        _snap(extension="flac", audio_codec="flac", bitrate_kbps=900,
              sample_rate_hz=44100, bit_depth=None, channels=2)
    )
    assert not report.suspected_upscale


def test_clipping_true_peak_adds_informational_note_without_dedicated_flag():
    report = analyze_quality(_snap(true_peak_dbtp=1.5))
    assert any("Clipping" in n or "dBTP" in n for n in report.notes)
    # Clipping ist kein eigenes suspected_*-Flag (§20-Doku) - nur ein Hinweis.
    assert not report.suspected_corruption


def test_very_low_loudness_adds_informational_note():
    report = analyze_quality(_snap(integrated_lufs=-50.0))
    assert any("LUFS" in n for n in report.notes)


def test_multiple_suspicions_can_be_flagged_simultaneously():
    report = analyze_quality(
        _snap(
            extension="flac", audio_codec="flac", bitrate_kbps=150,
            sample_rate_hz=44100, bit_depth=16, channels=2,
            tag_duration_seconds=240.0, duration_seconds=180.0,
            last_scan_error="checksum mismatch",
        )
    )
    assert report.suspected_upscale
    assert report.suspected_truncation
    assert report.suspected_corruption
    assert not report.suspected_transcode  # flac/flac passt zusammen
    assert len(report.notes) >= 3
