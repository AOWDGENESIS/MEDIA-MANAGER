"""Erzeugt eine winzige, synthetische Test-Mediathek via FFmpeg (ADR-0004).

WICHTIG: Erzeugt NIEMALS echte urheberrechtlich geschuetzte Inhalte. Alle
Dateien sind Sinuston-/Stille-/Farbbalken-Erzeugnisse mit klar erfundenen,
als Test gekennzeichneten Tags. Dient ausschliesslich dem SAFE TEST MODE
(§50/§51) - niemals gegen echte, persoenliche Medienbibliotheken verwenden.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import mutagen.mp4

FFMPEG = shutil.which("ffmpeg")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def generate_test_library(root: Path) -> dict[str, Path]:
    """Erzeugt eine kleine Testbibliothek unterhalb von `root` und liefert
    ein Dict mit benannten Beispielpfaden zurueck. `root` sollte immer ein
    temporaeres Verzeichnis sein (siehe conftest.py Fixture `test_library`).
    """
    if FFMPEG is None:
        raise RuntimeError("ffmpeg nicht gefunden - kann keine Testmedien erzeugen")

    root = Path(root)
    music_dir = root / "Music" / "Test Artist" / "Test Album"
    audiobook_dir = root / "Audiobooks" / "Test Author" / "Test Book"
    video_dir = root / "Movies"
    series_dir = root / "Series" / "Test Series" / "Season 01"
    for d in (music_dir, audiobook_dir, video_dir, series_dir):
        d.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # --- Musik: 6 Sekunden Sinuston, verschiedene Formate ---
    # (6s statt kuerzer, weil Chromaprint/fpcalc fuer sehr kurze, tonal
    # konstante Clips oft einen leeren Fingerprint liefert - siehe
    # core/tests/test_fingerprint.py. Bleibt trotzdem winzig, < 200 KB total.)
    for fmt, ext, extra in [
        ("mp3", "mp3", ["-b:a", "128k"]),
        ("flac", "flac", []),
        ("wav", "wav", []),
        ("ogg", "ogg", []),
    ]:
        out = music_dir / f"01 - Test Song.{ext}"
        _run(
            [
                FFMPEG, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                *extra,
                "-metadata", "title=Test Song",
                "-metadata", "artist=Test Artist",
                "-metadata", "album=Test Album",
                str(out),
            ]
        )
        paths[f"music_{fmt}"] = out

    # --- Hoerbuch: M4B mit 3 Sekunden Stille ---
    m4b_path = audiobook_dir / "Test Book.m4b"
    _run(
        [
            FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", "3", "-c:a", "aac",
            "-metadata", "title=Test Book",
            "-metadata", "artist=Test Author",
            str(m4b_path),
        ]
    )
    paths["audiobook_m4b"] = m4b_path

    # --- Video: 2 Sekunden Farbbalken, niedrige Aufloesung ---
    video_path = video_dir / "Test Movie (2026).mp4"
    _run(
        [
            FFMPEG, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:duration=2:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
            "-metadata", "title=Test Movie",
            "-metadata", "genre=Test-Drama",
            "-metadata:s:a:0", "language=eng",
            str(video_path),
        ]
    )
    # Regisseur/Schauspieler (§24, §63 Wissensgraph) gibt es keine
    # standardisierte ffmpeg-"-metadata"-Zuordnung fuer - werden daher ueber
    # mutagen als MP4-Freeform-Atome nachtraeglich gesetzt (analog zum
    # TXXX-Nachtrag beim Hoerbuch-Testbuch, siehe audiobook/tags.py).
    movie_tags = mutagen.mp4.MP4(video_path)
    movie_tags["----:com.apple.iTunes:DIRECTOR"] = b"Test Director"
    movie_tags["----:com.apple.iTunes:ACTOR"] = b"Test Actor One, Test Actor Two"
    movie_tags.save()
    paths["movie_mp4"] = video_path

    # --- Serie: Episode MIT eingebetteten TV-Show-Atomen (tvsh/tvsn/tves) ---
    episode_tagged_path = series_dir / "Test Series - Pilot.mp4"
    _run(
        [
            FFMPEG, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:duration=2:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
            "-metadata", "title=Pilot",
            str(episode_tagged_path),
        ]
    )
    episode_tags = mutagen.mp4.MP4(episode_tagged_path)
    episode_tags["tvsh"] = "Test Series"
    episode_tags["tvsn"] = [1]
    episode_tags["tves"] = [1]
    episode_tags["----:com.apple.iTunes:ACTOR"] = b"Test Actor One"
    episode_tags.save()
    paths["episode_tagged_mp4"] = episode_tagged_path

    # --- Serie: Episode OHNE Tags, nur per Dateiname erkennbar (S01E02) -
    # testet den Dateinamen-Fallback (Prinzip #16: Quelle bleibt transparent
    # "filename_pattern" statt "tag", siehe video/engine.py). ---
    episode_filename_path = series_dir / "Test Series - S01E02 - Second Episode.mp4"
    _run(
        [
            FFMPEG, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:duration=2:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
            str(episode_filename_path),
        ]
    )
    paths["episode_filename_mp4"] = episode_filename_path

    # --- Eine "verwaiste" Datei mit kryptischem Namen (Rename-Testfall) ---
    unknown_path = music_dir.parent / "unknown123.mp3"
    _run(
        [
            FFMPEG, "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=6",
            str(unknown_path),
        ]
    )
    paths["unknown_named_file"] = unknown_path

    return paths


if __name__ == "__main__":
    import sys
    import tempfile

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    result = generate_test_library(target)
    print(f"Testbibliothek erzeugt unter: {target}")
    for name, path in result.items():
        print(f"  {name}: {path}")
