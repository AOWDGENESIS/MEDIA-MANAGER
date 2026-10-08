"""Tests fuer das Konvertierungs-Werkzeug (nav.convert, Phase 3).

Nutzt die gemeinsame `test_library_root`-Fixture (SAFE TEST MODE, §51) -
niemals echte Mediendateien. Dateien werden vor jedem Test in ein eigenes
`tmp_path` kopiert, da `apply_conversion` eine Geschwisterdatei neben dem
Original anlegt und Tests sich nicht gegenseitig die gemeinsame
Session-Fixture verschmutzen duerfen.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from genesis_core.convert import (
    ConversionApplyNotConfirmedError,
    InvalidConversionRequestError,
    apply_conversion,
    plan_conversion,
)


def _copy_song(test_library_root: Path, tmp_path: Path, fixture_name: str = "01 - Test Song.wav") -> Path:
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / fixture_name
    dst = tmp_path / fixture_name
    shutil.copy2(src, dst)
    return dst


def _ffprobe_bitrate(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=bit_rate",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return int(result.stdout.strip())


# --- plan_conversion (reine Berechnung, kein ffmpeg) -------------------------

def test_plan_conversion_is_pure_no_output_file_created(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), "mp3", bitrate_kbps=192)

    assert not Path(plan.output_path).exists()
    assert plan.output_path.endswith(".converted.mp3")
    assert plan.source_format == "wav"
    assert plan.target_format == "mp3"
    assert plan.is_lossy_target is True
    assert plan.is_no_op_same_format is False
    assert plan.has_conflict is False


def test_plan_conversion_detects_no_op_same_format(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), "wav")
    assert plan.is_no_op_same_format is True


def test_plan_conversion_not_no_op_when_bitrate_differs(test_library_root: Path, tmp_path: Path):
    """Auch bei gleichem Format ist es KEIN No-Op, wenn der Nutzer explizit
    eine andere Bitrate anfordert (nur bei verlustbehafteten Formaten
    sinnvoll, aber hier rein als Plan-Logik getestet)."""
    path = _copy_song(test_library_root, tmp_path, fixture_name="01 - Test Song.mp3")
    plan = plan_conversion(1, str(path), "mp3", bitrate_kbps=96)
    assert plan.is_no_op_same_format is False


def test_plan_conversion_rejects_unknown_target_format(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidConversionRequestError):
        plan_conversion(1, str(path), "wma")


def test_plan_conversion_rejects_non_positive_bitrate(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    with pytest.raises(InvalidConversionRequestError):
        plan_conversion(1, str(path), "mp3", bitrate_kbps=0)


def test_plan_conversion_detects_existing_output_conflict(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    conflicting = path.with_name(f"{path.stem}.converted.mp3")
    conflicting.write_bytes(b"not actually audio")

    plan = plan_conversion(1, str(path), "mp3")

    assert plan.has_conflict is True
    assert "converted.mp3" in plan.conflict_reason


@pytest.mark.parametrize("target_format,expected_ext", [("mp3", ".mp3"), ("wav", ".wav"), ("flac", ".flac")])
def test_plan_conversion_supports_minimum_required_formats(
    test_library_root: Path, tmp_path: Path, target_format: str, expected_ext: str,
):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), target_format)
    assert plan.output_path.endswith(f".converted{expected_ext}")


# --- apply_conversion (schreibt tatsaechlich, braucht Bestaetigung) ----------

def test_apply_conversion_requires_confirmation(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), "mp3")

    with pytest.raises(ConversionApplyNotConfirmedError):
        apply_conversion(plan, user_confirmed=False)
    assert not Path(plan.output_path).exists()


def test_apply_conversion_never_touches_original(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    original_bytes = path.read_bytes()
    plan = plan_conversion(1, str(path), "mp3")

    apply_conversion(plan, user_confirmed=True)

    assert path.read_bytes() == original_bytes


def test_apply_conversion_produces_file_with_correct_format(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), "flac")

    result = apply_conversion(plan, user_confirmed=True)

    assert Path(result.output_path).exists()
    assert Path(result.output_path).suffix == ".flac"


def test_apply_conversion_honors_custom_bitrate(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), "mp3", bitrate_kbps=96)

    result = apply_conversion(plan, user_confirmed=True)

    bitrate = _ffprobe_bitrate(Path(result.output_path))
    assert bitrate == pytest.approx(96000, rel=0.05)


def test_apply_conversion_refuses_to_overwrite_existing_output(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    plan = plan_conversion(1, str(path), "mp3")
    apply_conversion(plan, user_confirmed=True)

    plan2 = plan_conversion(1, str(path), "mp3")
    assert plan2.has_conflict is True
