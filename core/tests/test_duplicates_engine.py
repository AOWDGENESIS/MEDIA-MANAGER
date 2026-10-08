"""Tests fuer die mehrstufige Duplikaterkennung (§21, Phase 3, ADR-0013).

Reine Unit-Tests auf Basis von `MediaSnapshot` - keine Dateien/DB noetig,
da die Engine bewusst als reine Vergleichslogik entkoppelt ist (siehe
Moduldocstring in engine.py).
"""
from __future__ import annotations

import pytest

from genesis_core.duplicates import (
    DuplicateCategory,
    MediaSnapshot,
    compare_pair,
    find_duplicate_candidates,
)


def _snap(media_file_id: int, **overrides) -> MediaSnapshot:
    defaults = {
        "media_file_id": media_file_id,
        "absolute_path": f"/music/file{media_file_id}.mp3",
        "size_bytes": 1000,
        "content_hash_sha256": f"hash{media_file_id}",
        "duration_seconds": 10.0,
        "audio_codec": "mp3",
        "sample_rate_hz": 44100,
        "channels": 2,
        "fingerprint": f"fp{media_file_id}",
        "title": "Song",
        "artist": "Artist",
        "album": "Album",
    }
    defaults.update(overrides)
    return MediaSnapshot(**defaults)


def test_compare_pair_rejects_comparing_file_with_itself():
    a = _snap(1)
    with pytest.raises(ValueError):
        compare_pair(a, a)


def test_identical_hash_is_exact_duplicate():
    a = _snap(1, content_hash_sha256="samehash")
    b = _snap(2, content_hash_sha256="samehash", size_bytes=999999)  # Groesse irrelevant bei Hash-Treffer
    result = compare_pair(a, b)
    assert result.category == DuplicateCategory.EXACT_DUPLICATE
    assert result.confidence == 1.0
    assert "hash" in result.matched_stages
    # Kanonische (kleinere zuerst) Reihenfolge
    assert result.media_file_id_a == 1
    assert result.media_file_id_b == 2


def test_same_duration_and_technical_params_is_probable_duplicate():
    a = _snap(1, content_hash_sha256="h1", fingerprint="fpA")
    b = _snap(2, content_hash_sha256="h2", fingerprint="fpB")
    result = compare_pair(a, b)
    assert result.category == DuplicateCategory.PROBABLE_DUPLICATE
    assert "duration" in result.matched_stages
    assert "technical_params" in result.matched_stages
    assert 0.0 < result.confidence <= 1.0


def test_matching_fingerprint_and_duration_but_different_technical_params_is_same_content_different_format():
    a = _snap(1, content_hash_sha256="h1", fingerprint="fpSAME", audio_codec="pcm_s16le",
              sample_rate_hz=44100, channels=2, size_bytes=5_000_000)
    b = _snap(2, content_hash_sha256="h2", fingerprint="fpSAME", audio_codec="mp3",
              sample_rate_hz=44100, channels=2, size_bytes=500_000)
    result = compare_pair(a, b)
    assert result.category == DuplicateCategory.SAME_CONTENT_DIFFERENT_FORMAT
    assert "fingerprint" in result.matched_stages


def test_matching_fingerprint_but_different_duration_is_similar_content():
    a = _snap(1, content_hash_sha256="h1", fingerprint="fpSAME", duration_seconds=10.0)
    b = _snap(2, content_hash_sha256="h2", fingerprint="fpSAME", duration_seconds=60.0)
    result = compare_pair(a, b)
    assert result.category == DuplicateCategory.SIMILAR_CONTENT
    assert result.confidence < 0.8  # geringere Sicherheit als die anderen Kategorien


def test_completely_different_files_yield_no_candidate():
    a = _snap(1, content_hash_sha256="h1", fingerprint="fp1", duration_seconds=10.0,
              audio_codec="mp3", title="Song A", artist="Artist A", album="Album A")
    b = _snap(2, content_hash_sha256="h2", fingerprint="fp2", duration_seconds=999.0,
              audio_codec="flac", sample_rate_hz=96000, channels=1,
              title="Song B", artist="Artist B", album="Album B")
    assert compare_pair(a, b) is None


def test_missing_duration_degrades_gracefully_instead_of_false_positive():
    """Fehlende technische Analyse (noch nicht durchgefuehrt) darf NIEMALS
    faelschlich als Duplikat-Treffer gewertet werden (Prinzip #17)."""
    a = _snap(1, content_hash_sha256="h1", duration_seconds=None)
    b = _snap(2, content_hash_sha256="h2", duration_seconds=None)
    assert compare_pair(a, b) is None


def test_duration_tolerance_absorbs_small_encoding_rounding():
    a = _snap(1, content_hash_sha256="h1", duration_seconds=10.00)
    b = _snap(2, content_hash_sha256="h2", duration_seconds=10.04)
    result = compare_pair(a, b)
    assert result is not None
    assert result.category == DuplicateCategory.PROBABLE_DUPLICATE


def test_metadata_match_increases_confidence_but_is_not_required():
    a = _snap(1, content_hash_sha256="h1", title=None, artist=None, album=None)
    b = _snap(2, content_hash_sha256="h2", title=None, artist=None, album=None)
    without_metadata = compare_pair(a, b)

    a2 = _snap(3, content_hash_sha256="h3")
    b2 = _snap(4, content_hash_sha256="h4")
    with_metadata = compare_pair(a2, b2)

    assert without_metadata.category == with_metadata.category == DuplicateCategory.PROBABLE_DUPLICATE
    assert with_metadata.confidence > without_metadata.confidence
    assert "metadata" in with_metadata.matched_stages
    assert "metadata" not in without_metadata.matched_stages


def test_find_duplicate_candidates_excludes_unrelated_files():
    unique = _snap(5, content_hash_sha256="unique", fingerprint="unique_fp",
                    duration_seconds=12345.0, audio_codec="flac", sample_rate_hz=96000, channels=1,
                    title="Totally Different", artist="Nobody", album="Nowhere")
    a = _snap(1, content_hash_sha256="samehash")
    b = _snap(2, content_hash_sha256="samehash")

    candidates = find_duplicate_candidates([a, b, unique])

    assert len(candidates) == 1
    assert {candidates[0].media_file_id_a, candidates[0].media_file_id_b} == {1, 2}


def test_find_duplicate_candidates_sorted_by_confidence_descending():
    exact_a = _snap(1, content_hash_sha256="samehash")
    exact_b = _snap(2, content_hash_sha256="samehash")
    probable_a = _snap(
        3, content_hash_sha256="h3", duration_seconds=42.0, audio_codec="flac",
        sample_rate_hz=48000, channels=1, fingerprint="fpP3",
        title=None, artist=None, album=None,
    )
    probable_b = _snap(
        4, content_hash_sha256="h4", duration_seconds=42.0, audio_codec="flac",
        sample_rate_hz=48000, channels=1, fingerprint="fpP4",
        title=None, artist=None, album=None,
    )

    candidates = find_duplicate_candidates([exact_a, exact_b, probable_a, probable_b])

    assert len(candidates) == 2
    assert candidates[0].category == DuplicateCategory.EXACT_DUPLICATE
    assert candidates[1].category == DuplicateCategory.PROBABLE_DUPLICATE
    assert candidates[0].confidence >= candidates[1].confidence


def test_find_duplicate_candidates_empty_list_returns_empty():
    assert find_duplicate_candidates([]) == []


def test_find_duplicate_candidates_single_file_returns_empty():
    assert find_duplicate_candidates([_snap(1)]) == []
