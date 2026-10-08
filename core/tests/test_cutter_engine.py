"""Tests fuer die Audio-Cutter-Engine (§18, Phase 3, ADR-0011).

Nutzt die gemeinsame `test_library_root`-Fixture (SAFE TEST MODE, §51) -
niemals echte Mediendateien. Dateien werden vor jedem Test in ein eigenes
`tmp_path` kopiert, da `apply_cut` eine Geschwisterdatei neben dem Original
anlegt und Tests sich nicht gegenseitig die gemeinsame Session-Fixture
verschmutzen duerfen.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from genesis_core.cutter import (
    CutApplyNotConfirmedError,
    InvalidCutSelectionError,
    WaveformGenerationError,
    apply_cut,
    generate_waveform_image,
    plan_cut,
)


def _copy_song(test_library_root: Path, tmp_path: Path, fixture_name: str = "01 - Test Song.mp3") -> Path:
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / fixture_name
    dst = tmp_path / fixture_name
    shutil.copy2(src, dst)
    return dst


def _ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip().split("=")[1])


# --- Waveform (rein lesend) --------------------------------------------------

def test_generate_waveform_image_creates_png(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    output_png = tmp_path / "wave.png"

    result = generate_waveform_image(path, output_png)

    assert result == output_png
    assert output_png.exists()
    assert output_png.stat().st_size > 0
    # Original unangetastet (Prinzip #4/#5)
    assert path.exists()


def test_generate_waveform_image_missing_source_raises_clear_error(tmp_path: Path):
    with pytest.raises(WaveformGenerationError):
        generate_waveform_image(tmp_path / "does-not-exist.mp3", tmp_path / "wave.png")


# --- plan_cut (reine Berechnung, kein ffmpeg) --------------------------------

def test_plan_cut_is_pure_no_output_file_created(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)

    plan = plan_cut(1, str(path), 1.0, 3.0, "mp3")

    assert not Path(plan.output_path).exists()
    assert plan.start_seconds == 1.0
    assert plan.end_seconds == 3.0
    assert plan.selection_duration_seconds == 2.0
    assert plan.output_path.endswith(".cut.mp3")
    assert plan.is_lossy_export is True
    assert plan.has_conflict is False


def test_plan_cut_rejects_end_before_start(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidCutSelectionError):
        plan_cut(1, str(path), 5.0, 2.0, "mp3")


def test_plan_cut_rejects_negative_start(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidCutSelectionError):
        plan_cut(1, str(path), -1.0, 2.0, "mp3")


def test_plan_cut_rejects_end_beyond_known_duration(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidCutSelectionError):
        plan_cut(1, str(path), 0.0, 999.0, "mp3", source_duration_seconds=5.0)


def test_plan_cut_rejects_fades_longer_than_selection(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidCutSelectionError):
        plan_cut(1, str(path), 0.0, 2.0, "mp3", fade_in_seconds=1.5, fade_out_seconds=1.5)


def test_plan_cut_rejects_unknown_export_format(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidCutSelectionError):
        plan_cut(1, str(path), 0.0, 2.0, "wma")


def test_plan_cut_detects_existing_output_conflict(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    conflicting = path.with_name(f"{path.stem}.cut.mp3")
    conflicting.write_bytes(b"not actually audio")

    plan = plan_cut(1, str(path), 0.0, 2.0, "mp3")

    assert plan.has_conflict is True
    assert "cut.mp3" in plan.conflict_reason


@pytest.mark.parametrize("export_format,expected_ext", [("mp3", ".mp3"), ("wav", ".wav"), ("flac", ".flac")])
def test_plan_cut_supports_minimum_required_formats(
    test_library_root: Path, tmp_path: Path, export_format: str, expected_ext: str,
):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_cut(1, str(path), 0.0, 2.0, export_format)
    assert plan.output_path.endswith(f".cut{expected_ext}")


# --- apply_cut (schreibt tatsaechlich, braucht Bestaetigung) -----------------

def test_apply_cut_requires_confirmation(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_cut(1, str(path), 0.0, 2.0, "mp3")

    with pytest.raises(CutApplyNotConfirmedError):
        apply_cut(plan, user_confirmed=False)
    assert not Path(plan.output_path).exists()


def test_apply_cut_never_touches_original(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    original_bytes = path.read_bytes()
    plan = plan_cut(1, str(path), 1.0, 3.0, "mp3")

    apply_cut(plan, user_confirmed=True)

    assert path.read_bytes() == original_bytes


def test_apply_cut_produces_exact_duration_for_lossless_formats(test_library_root: Path, tmp_path: Path):
    """Siehe ADR-0011: der Filter-basierte (atrim) Ansatz liefert fuer
    verlustfreie Formate eine sample-genaue Dauer, anders als der getestete
    (und bewusst verworfene) Stream-Copy-Ansatz."""
    path = _copy_song(test_library_root, tmp_path, fixture_name="01 - Test Song.wav")
    plan = plan_cut(1, str(path), 1.0, 3.0, "flac")

    result = apply_cut(plan, user_confirmed=True)

    duration = _ffprobe_duration(Path(result.output_path))
    assert duration == pytest.approx(2.0, abs=0.01)


def test_apply_cut_applies_fades_without_error(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path, fixture_name="01 - Test Song.wav")
    plan = plan_cut(1, str(path), 0.5, 3.0, "wav", fade_in_seconds=0.3, fade_out_seconds=0.3)

    result = apply_cut(plan, user_confirmed=True)

    assert Path(result.output_path).exists()
    duration = _ffprobe_duration(Path(result.output_path))
    assert duration == pytest.approx(2.5, abs=0.01)


def test_apply_cut_refuses_to_overwrite_existing_output(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_cut(1, str(path), 0.0, 2.0, "mp3")
    apply_cut(plan, user_confirmed=True)

    # Zweiter Plan fuer dieselbe Auswahl erkennt den Konflikt bereits vorab.
    plan2 = plan_cut(1, str(path), 0.0, 2.0, "mp3")
    assert plan2.has_conflict is True
