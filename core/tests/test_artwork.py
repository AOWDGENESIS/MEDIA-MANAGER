from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from genesis_core.artwork import (
    ArtworkApplyNotConfirmedError,
    ArtworkError,
    cache_artwork,
    embed_artwork,
    extract_embedded_artwork,
)

# Ein minimales, aber gueltiges 1x1-JPEG (haendisch konstruiert) - vermeidet
# eine zusaetzliche Abhaengigkeit (Pillow) nur fuer Testbilder.
_TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300030202020202"
    "03020202030303030406040404040408060605060907090a0a090809090a0c"
    "0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b"
    "080001000101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)


def test_extract_from_missing_artwork_returns_none(test_library_root: Path):
    path = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    assert extract_embedded_artwork(path) is None


def test_embed_requires_explicit_confirmation(test_library_root: Path, tmp_path: Path):
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.mp3"
    path = tmp_path / "song.mp3"
    shutil.copy2(src, path)

    with pytest.raises(ArtworkApplyNotConfirmedError):
        embed_artwork(path, _TINY_JPEG, "image/jpeg", user_confirmed=False)


@pytest.mark.parametrize("fixture_name,ext", [
    ("01 - Test Song.mp3", ".mp3"),
    ("01 - Test Song.flac", ".flac"),
    ("01 - Test Song.ogg", ".ogg"),
])
def test_embed_then_extract_roundtrip(test_library_root: Path, tmp_path: Path, fixture_name, ext):
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / fixture_name
    path = tmp_path / f"song{ext}"
    shutil.copy2(src, path)

    embed_artwork(path, _TINY_JPEG, "image/jpeg", user_confirmed=True)
    result = extract_embedded_artwork(path)

    assert result is not None
    data, mime = result
    assert data == _TINY_JPEG
    assert mime == "image/jpeg"


def test_embed_then_extract_roundtrip_m4b_audiobook(test_library_root: Path, tmp_path: Path):
    src = test_library_root / "Audiobooks" / "Test Author" / "Test Book" / "Test Book.m4b"
    path = tmp_path / "book.m4b"
    shutil.copy2(src, path)

    embed_artwork(path, _TINY_JPEG, "image/jpeg", user_confirmed=True)
    result = extract_embedded_artwork(path)

    assert result is not None
    data, mime = result
    assert data == _TINY_JPEG
    assert mime == "image/jpeg"


def test_embed_unsupported_format_raises_clear_error(test_library_root: Path, tmp_path: Path):
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / "01 - Test Song.wav"
    path = tmp_path / "song.wav"
    shutil.copy2(src, path)

    with pytest.raises(ArtworkError, match="nicht unterstuetzt"):
        embed_artwork(path, _TINY_JPEG, "image/jpeg", user_confirmed=True)


def test_embed_mp4_rejects_unsupported_mime_type_instead_of_silently_using_jpeg(
    test_library_root: Path, tmp_path: Path
):
    """Deep-Review-Fund F-11 (Sitzung 3): `_embed_mp4` hat frueher JEDEN
    nicht-PNG-MIME-Typ stillschweigend als JPEG behandelt. Ein echtes
    GIF/WEBP-Cover waere so unlesbar eingebettet worden, ohne dass jemand
    gewarnt wird. Jetzt muss ein klarer Fehler kommen statt eines kaputten
    Covers."""
    src = test_library_root / "Audiobooks" / "Test Author" / "Test Book" / "Test Book.m4b"
    path = tmp_path / "book.m4b"
    shutil.copy2(src, path)

    with pytest.raises(ArtworkError, match="nur JPEG- oder PNG-Cover"):
        embed_artwork(path, _TINY_JPEG, "image/gif", user_confirmed=True)

    # Datei darf durch den abgelehnten Versuch nicht beschaedigt worden sein.
    assert extract_embedded_artwork(path) is None


def test_cache_artwork_writes_deduplicated_file(tmp_path: Path):
    cache_dir = tmp_path / "artwork_cache"
    path1 = cache_artwork(_TINY_JPEG, "image/jpeg", cache_dir)
    path2 = cache_artwork(_TINY_JPEG, "image/jpeg", cache_dir)

    assert path1 == path2  # gleicher Inhalt -> gleicher (deduplizierter) Pfad
    assert path1.exists()
    assert path1.read_bytes() == _TINY_JPEG
    assert path1.suffix == ".jpg"
