from pathlib import Path

from genesis_core.metadata.tag_reader import read_existing_tags


def test_reads_tags_from_all_generated_formats(test_library_root: Path):
    """Deckt einen real gefundenen Bug ab: mutagens Vorbis-Comment-
    Implementierung (FLAC/OGG) wirft `ValueError` statt `False` bei
    `in`-Pruefungen fuer Schluessel, die keine gueltigen Vorbis-Feldnamen
    sind (z.B. MP4-Atom-Namen wie '\xa9day') - siehe tag_reader._first_value."""
    for fmt in ("mp3", "flac", "ogg"):
        path = test_library_root / "Music" / "Test Artist" / "Test Album" / f"01 - Test Song.{fmt}"
        tags = read_existing_tags(path)
        assert tags.has_any_tag is True, f"Format {fmt}: Tags sollten gelesen werden"
        assert tags.title == "Test Song"
        assert tags.artist == "Test Artist"
        assert tags.album == "Test Album"


def test_wav_without_tags_returns_empty_result(test_library_root: Path):
    path = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.wav"
    tags = read_existing_tags(path)
    # FFmpeg schreibt standardmaessig keine ID3-Tags in reines WAV - das ist
    # ein normaler Zustand, kein Fehler.
    assert tags.has_any_tag is False


def test_missing_file_returns_empty_result_not_error(tmp_path: Path):
    tags = read_existing_tags(tmp_path / "does-not-exist.mp3")
    assert tags.has_any_tag is False
    assert tags.title is None


def test_non_audio_file_returns_empty_result_not_error(tmp_path: Path):
    junk = tmp_path / "not_audio.mp3"
    junk.write_bytes(b"garbage-not-an-audio-file")
    tags = read_existing_tags(junk)
    assert tags.has_any_tag is False
