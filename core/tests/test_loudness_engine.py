"""Tests fuer die Loudness-Engine (§19, Phase 3, ADR-0010).

Nutzt die gemeinsame `test_library_root`-Fixture (SAFE TEST MODE, §51) -
niemals echte Mediendateien. Dateien werden vor jedem Test in ein eigenes
`tmp_path` kopiert, da `apply_normalization` eine Geschwisterdatei neben dem
Original anlegt und Tests sich nicht gegenseitig die gemeinsame
Session-Fixture verschmutzen duerfen.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from genesis_core.db.models import MediaKind
from genesis_core.loudness import (
    NormalizationApplyNotConfirmedError,
    apply_normalization,
    ffmpeg_loudnorm,
    measure_loudness,
    plan_normalization,
)
from genesis_core.loudness.engine import LoudnessMeasurementError, UnsupportedMediaKindError


def _copy_song(test_library_root: Path, tmp_path: Path, fixture_name: str = "01 - Test Song.mp3") -> Path:
    src = test_library_root / "Music" / "Test Artist" / "Test Album" / fixture_name
    dst = tmp_path / fixture_name
    shutil.copy2(src, dst)
    return dst


def test_measure_loudness_returns_plausible_values(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)

    assert -70.0 < measurement.integrated_lufs < 0.0
    assert measurement.true_peak_dbtp < 5.0
    assert measurement.loudness_range_lu >= 0.0
    assert measurement.measured_at is not None


def test_measure_loudness_missing_file_raises_clear_error(tmp_path: Path):
    with pytest.raises(LoudnessMeasurementError):
        measure_loudness(tmp_path / "does-not-exist.mp3")


def test_plan_normalization_rejects_video_media_kinds(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)

    with pytest.raises(UnsupportedMediaKindError):
        plan_normalization(1, str(path), MediaKind.MOVIE, measurement, -14.0, -1.0)


@pytest.mark.parametrize("media_kind", [
    MediaKind.MUSIC, MediaKind.AUDIOBOOK, MediaKind.PODCAST_EPISODE, MediaKind.AI_MUSIC,
])
def test_plan_normalization_accepts_all_audio_media_kinds(
    test_library_root: Path, tmp_path: Path, media_kind
):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)
    plan = plan_normalization(1, str(path), media_kind, measurement, -14.0, -1.0)
    assert plan.output_path.endswith(".normalized.mp3")
    assert plan.has_conflict is False


def test_plan_normalization_is_pure_no_file_created(test_library_root: Path, tmp_path: Path):
    """`plan_normalization` darf unter KEINEN Umstaenden eine Datei anlegen
    (Prinzip #4/#5: Analyse/Vorschlag ist immer sicher, ohne Nebenwirkung)."""
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)
    files_before = set(tmp_path.iterdir())

    plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)

    assert set(tmp_path.iterdir()) == files_before


def test_apply_normalization_requires_confirmation(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)
    plan = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)

    with pytest.raises(NormalizationApplyNotConfirmedError):
        apply_normalization(plan, user_confirmed=False)
    assert not Path(plan.output_path).exists()


def test_apply_normalization_never_touches_original(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    original_bytes = path.read_bytes()
    measurement = measure_loudness(path)
    plan = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)

    apply_normalization(plan, user_confirmed=True)

    assert path.read_bytes() == original_bytes, "Original darf niemals veraendert werden"
    assert Path(plan.output_path).exists()


def test_apply_normalization_achieves_target_within_tolerance(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)
    plan = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)

    result = apply_normalization(plan, user_confirmed=True)

    assert abs(result.achieved_integrated_lufs - (-14.0)) < 0.5
    assert result.achieved_true_peak_dbtp <= -1.0 + 0.3  # kleine Toleranz fuer Messungenauigkeit

    remeasured = measure_loudness(plan.output_path)
    assert abs(remeasured.integrated_lufs - result.achieved_integrated_lufs) < 0.2


def test_apply_normalization_refuses_to_overwrite_existing_output(
    test_library_root: Path, tmp_path: Path
):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)
    plan = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)
    Path(plan.output_path).write_bytes(b"not actually audio - pre-existing file")

    plan_again = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)
    assert plan_again.has_conflict is True
    assert plan_again.conflict_reason is not None

    with pytest.raises(FileExistsError):
        apply_normalization(plan_again, user_confirmed=True)
    # Die vorab existierende (fremde) Datei darf nicht angetastet worden sein.
    assert Path(plan.output_path).read_bytes() == b"not actually audio - pre-existing file"


def test_plan_flags_dynamics_warning_for_aggressive_target(test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    measurement = measure_loudness(path)
    # 0 LUFS Ziel ist fuer praktisch jede normale Aufnahme unerreichbar ohne
    # den True-Peak-Deckel zu verletzen -> muss als Dynamik-Warnung markiert
    # werden (Transparenzprinzip #16), nicht stillschweigend ausgefuehrt.
    plan = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, 0.0, -1.0)
    assert plan.will_likely_alter_dynamics is True


@pytest.mark.parametrize("fixture_name,expect_lossy", [
    ("01 - Test Song.mp3", True),
    ("01 - Test Song.flac", False),
    ("01 - Test Song.ogg", True),
])
def test_output_format_matches_source_and_flags_lossy_reencode(
    test_library_root: Path, tmp_path: Path, fixture_name, expect_lossy
):
    path = _copy_song(test_library_root, tmp_path, fixture_name)
    measurement = measure_loudness(path)
    plan = plan_normalization(1, str(path), MediaKind.MUSIC, measurement, -14.0, -1.0)

    assert plan.output_path.endswith(Path(fixture_name).suffix.replace(
        Path(fixture_name).suffix, f".normalized{Path(fixture_name).suffix}"
    ))
    assert plan.is_lossy_reencode is expect_lossy

    result = apply_normalization(plan, user_confirmed=True)
    assert Path(result.output_path).exists()


def test_ffmpeg_not_available_raises_clear_error(monkeypatch, test_library_root: Path, tmp_path: Path):
    path = _copy_song(test_library_root, tmp_path)
    monkeypatch.setattr(ffmpeg_loudnorm, "ffmpeg_available", lambda: False)
    with pytest.raises(LoudnessMeasurementError):
        measure_loudness(path)
