from pathlib import Path

import pytest

from genesis_core.fingerprint import FingerprintError, compute_fingerprint, is_fpcalc_available


def test_fpcalc_availability_matches_system():
    # Reine Konsistenzpruefung - kein hartes Require, damit die Suite auch
    # in Umgebungen ohne Chromaprint nicht kollabiert (siehe uebernaechster Test).
    assert isinstance(is_fpcalc_available(), bool)


@pytest.mark.skipif(not is_fpcalc_available(), reason="fpcalc nicht installiert")
def test_compute_fingerprint_for_synthetic_audio(test_library_root: Path):
    # Gezielt die generierte "Test Song"-MP3 verwenden (6s Sinuston) statt
    # irgendeiner Datei aus der Bibliothek: sehr kurze/tonal konstante Clips
    # liefern bei Chromaprint teils einen leeren Fingerprint (siehe
    # testdata_generator/generate.py Kommentar).
    candidates = list(test_library_root.rglob("01 - Test Song.mp3"))
    assert candidates, "Testbibliothek sollte die generierte Test-Song-MP3 enthalten"

    result = compute_fingerprint(candidates[0])
    assert result.algorithm == "chromaprint"
    assert len(result.fingerprint_data) > 10
    assert result.duration_seconds > 0


def test_compute_fingerprint_missing_file_raises_clear_error(tmp_path: Path):
    if not is_fpcalc_available():
        pytest.skip("fpcalc nicht installiert")
    with pytest.raises(FingerprintError, match="nicht gefunden"):
        compute_fingerprint(tmp_path / "does-not-exist.mp3")


def test_compute_fingerprint_non_audio_file_raises_clear_error(tmp_path: Path):
    if not is_fpcalc_available():
        pytest.skip("fpcalc nicht installiert")
    junk = tmp_path / "not_audio.mp3"
    junk.write_bytes(b"dies ist keine gueltige Audiodatei")
    with pytest.raises(FingerprintError):
        compute_fingerprint(junk)
