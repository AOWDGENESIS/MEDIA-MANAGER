"""Tests fuer die Temp-Aufraeumung (§41, Erweiterung von genesis_core.storage)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from genesis_core.storage import (
    TempCleanupNotConfirmedError,
    cleanup_temp_files,
    scan_temp_files,
)


def _age_file(path: Path, seconds_old: float) -> None:
    ts = time.time() - seconds_old
    os.utime(path, (ts, ts))


def test_scan_temp_files_empty_dir_returns_empty(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    assert scan_temp_files(temp_dir) == []


def test_scan_temp_files_nonexistent_dir_returns_empty(tmp_path: Path):
    assert scan_temp_files(tmp_path / "does_not_exist") == []


def test_scan_temp_files_lists_files_recursively(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    (temp_dir / "sub").mkdir(parents=True)
    (temp_dir / "a.tmp").write_text("x")
    (temp_dir / "sub" / "b.tmp").write_text("yy")

    results = scan_temp_files(temp_dir)
    assert {Path(r.path).name for r in results} == {"a.tmp", "b.tmp"}


def test_scan_temp_files_respects_older_than_filter(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    fresh = temp_dir / "fresh.tmp"
    old = temp_dir / "old.tmp"
    fresh.write_text("x")
    old.write_text("x")
    _age_file(old, seconds_old=10_000)

    results = scan_temp_files(temp_dir, older_than_seconds=3600)
    assert {Path(r.path).name for r in results} == {"old.tmp"}


def test_cleanup_temp_files_requires_confirmation(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    (temp_dir / "a.tmp").write_text("x")
    with pytest.raises(TempCleanupNotConfirmedError):
        cleanup_temp_files(temp_dir, user_confirmed=False)


def test_cleanup_temp_files_deletes_candidates(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    f1 = temp_dir / "a.tmp"
    f2 = temp_dir / "b.tmp"
    f1.write_text("x")
    f2.write_text("y")

    removed = cleanup_temp_files(temp_dir, user_confirmed=True)
    assert set(removed) == {str(f1), str(f2)}
    assert not f1.exists()
    assert not f2.exists()


def test_cleanup_temp_files_skips_already_removed_without_raising(tmp_path: Path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    candidates = scan_temp_files(temp_dir)
    f = temp_dir / "ghost.tmp"
    f.write_text("x")
    candidates = scan_temp_files(temp_dir)
    f.unlink()  # zwischenzeitlich bereits von anderswo entfernt
    removed = cleanup_temp_files(temp_dir, candidates, user_confirmed=True)
    assert removed == []
