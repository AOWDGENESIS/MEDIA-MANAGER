"""Regression gegen flackernde Konsolen und unbeschraenkte Vorab-Scans."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select

from genesis_core import processes
from genesis_core.db import Database
from genesis_core.db.models import MediaFile
from genesis_core.scanner import ffprobe_util
from genesis_core.scanner import scanner


def test_media_cli_options_use_no_window_only_on_windows(monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(processes.sys, "platform", "win32")
        patch.setattr(processes.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
        assert processes.media_cli_options() == {"creationflags": 0x08000000}
        patch.setattr(processes.sys, "platform", "linux")
        assert processes.media_cli_options() == {}


def test_scan_ffprobe_passes_visibility_flag_through(monkeypatch, tmp_path: Path):
    media = tmp_path / "track.mp3"
    media.write_bytes(b"fake")
    spy = Mock(return_value=subprocess.CompletedProcess(
        args=["ffprobe"], returncode=0, stdout=json.dumps({"format": {}}), stderr=""
    ))
    monkeypatch.setattr(ffprobe_util, "ffprobe_available", lambda: True)
    monkeypatch.setattr(ffprobe_util, "media_cli_options", lambda: {"creationflags": 0x08000000})
    monkeypatch.setattr(ffprobe_util.subprocess, "run", spy)
    assert ffprobe_util.probe_file(media) == {"format": {}}
    assert spy.call_args.kwargs["creationflags"] == 0x08000000
    assert spy.call_args.kwargs["capture_output"] is True


def test_scan_file_cap_rolls_back_entire_transaction(db: Database, tmp_path: Path, monkeypatch):
    for n in range(3):
        (tmp_path / f"track{n}.mp3").write_bytes(b"a")
    monkeypatch.setattr(scanner, "MAX_MEDIA_FILES_PER_SCAN", 2)
    with pytest.raises(scanner.ScanSafetyLimit, match="2 Mediendateien"):
        scanner.scan_directories(db, [tmp_path], compute_hash=False, run_ffprobe=False)
    with db.session() as session:
        assert session.scalar(select(func.count(MediaFile.id))) == 0


def test_scan_deadline_rolls_back_without_partial_library(db: Database, tmp_path: Path, monkeypatch):
    (tmp_path / 'track.mp3').write_bytes(b'a')
    monkeypatch.setattr(scanner, 'MAX_SCAN_SECONDS', 0)
    with pytest.raises(scanner.ScanSafetyLimit, match='Sekunden'):
        scanner.scan_directories(db, [tmp_path], compute_hash=False, run_ffprobe=False)
    with db.session() as session:
        assert session.scalar(select(func.count(MediaFile.id))) == 0


def test_scan_hash_budget_fails_before_large_file_is_read(db: Database, tmp_path: Path, monkeypatch):
    (tmp_path / "track.mp3").write_bytes(b"abcde")
    monkeypatch.setattr(scanner, "MAX_HASH_BYTES_PER_SCAN", 4)
    spy = Mock(side_effect=AssertionError("Zu grosse Datei wurde gehasht"))
    monkeypatch.setattr(scanner, "sha256_of_file", spy)
    with pytest.raises(scanner.ScanSafetyLimit, match="Hash-Budget"):
        scanner.scan_directories(db, [tmp_path], run_ffprobe=False)
    spy.assert_not_called()
    with db.session() as session:
        assert session.scalar(select(func.count(MediaFile.id))) == 0
