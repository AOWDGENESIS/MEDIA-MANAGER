"""Tests fuer den Scan & Repair-Workflow (§39) - Plan -> Vorschau ->
Bestaetigung -> Ausfuehrung mit vorherigem Backup und ProcessingHistory-
Protokollierung (§17/§35/§36/§40)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import func, select

from genesis_core import __version__
from genesis_core.backup import list_backups
from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, MediaKind, ProcessingHistory, Track
from genesis_core.jobs import JobCancelledError, JobManager
from genesis_core.repair import (
    ACTION_CLEANUP_ORPHANED_ROWS,
    ACTION_CLEANUP_TEMP_FILES,
    RepairExecuteNotConfirmedError,
    execute_repairs,
    plan_repairs,
    preview_repairs,
)


def _orphan_track(db: Database) -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path="/tmp/repair/song.mp3", directory="/tmp/repair",
            filename="song.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=1,
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id
        session.add(Track(media_file_id=media_file_id, title="verwaist"))

    conn = sqlite3.connect(str(db.database_path))
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM media_files WHERE id = ?", (media_file_id,))
        conn.commit()
    finally:
        conn.close()
    return media_file_id


def test_plan_repairs_empty_on_clean_setup(db: Database, settings: Settings):
    plan = plan_repairs(db, settings)
    assert plan.is_empty


def test_plan_repairs_detects_orphaned_rows(db: Database, settings: Settings):
    _orphan_track(db)
    plan = plan_repairs(db, settings)
    assert not plan.is_empty
    item = next(i for i in plan.items if i.action_type == ACTION_CLEANUP_ORPHANED_ROWS)
    assert item.target == "tracks"
    assert item.count == 1


def test_plan_repairs_detects_old_temp_files(db: Database, settings: Settings):
    import os
    import time

    temp_dir = settings.paths.resolved_temp_dir()
    stale = temp_dir / "stale.tmp"
    stale.write_text("x")
    old_ts = time.time() - 100_000
    os.utime(stale, (old_ts, old_ts))

    plan = plan_repairs(db, settings, temp_min_age_seconds=3600)
    item = next(i for i in plan.items if i.action_type == ACTION_CLEANUP_TEMP_FILES)
    assert item.count == 1


def test_preview_repairs_lists_concrete_row_ids(db: Database, settings: Settings):
    _orphan_track(db)
    plan = plan_repairs(db, settings)
    preview = preview_repairs(db, settings, plan.items)
    item = next(i for i in preview.items if i.action_type == ACTION_CLEANUP_ORPHANED_ROWS)
    assert len(item.row_ids) == 1


def test_execute_repairs_requires_confirmation(db: Database, settings: Settings):
    jobs = JobManager(db, app_version=__version__)
    job_id = jobs.create_job("scan_and_repair")
    jobs.start(job_id)
    _orphan_track(db)
    plan = plan_repairs(db, settings)
    preview = preview_repairs(db, settings, plan.items)
    with pytest.raises(RepairExecuteNotConfirmedError):
        execute_repairs(db, settings, jobs, job_id, preview, user_confirmed=False)


def test_execute_repairs_removes_orphans_and_creates_backup(db: Database, settings: Settings):
    jobs = JobManager(db, app_version=__version__)
    job_id = jobs.create_job("scan_and_repair")
    jobs.start(job_id)

    _orphan_track(db)
    plan = plan_repairs(db, settings)
    preview = preview_repairs(db, settings, plan.items)

    backups_before = len(list_backups(db, "db"))
    result = execute_repairs(db, settings, jobs, job_id, preview, user_confirmed=True)

    assert Path(result.backup.path).exists()
    assert len(list_backups(db, "db")) == backups_before + 1

    with db.session() as session:
        remaining = session.execute(select(func.count()).select_from(Track)).scalar_one()
        assert remaining == 0

    with db.session() as session:
        history = list(
            session.execute(
                select(ProcessingHistory).where(ProcessingHistory.job_id == job_id)
            ).scalars()
        )
        assert len(history) >= 1
        assert all(h.action.startswith("repair_") for h in history)


def test_execute_repairs_also_removes_temp_files(db: Database, settings: Settings):
    import os
    import time

    temp_dir = settings.paths.resolved_temp_dir()
    stale = temp_dir / "stale.tmp"
    stale.write_text("x")
    old_ts = time.time() - 100_000
    os.utime(stale, (old_ts, old_ts))

    jobs = JobManager(db, app_version=__version__)
    job_id = jobs.create_job("scan_and_repair")
    jobs.start(job_id)

    plan = plan_repairs(db, settings, temp_min_age_seconds=3600)
    preview = preview_repairs(db, settings, plan.items, temp_min_age_seconds=3600)
    execute_repairs(db, settings, jobs, job_id, preview, user_confirmed=True)

    assert not stale.exists()


def test_execute_repairs_raises_if_job_cancelled_before_start(db: Database, settings: Settings):
    jobs = JobManager(db, app_version=__version__)
    job_id = jobs.create_job("scan_and_repair")
    jobs.start(job_id)

    _orphan_track(db)
    plan = plan_repairs(db, settings)
    preview = preview_repairs(db, settings, plan.items)

    jobs.cancel(job_id)
    with pytest.raises(JobCancelledError):
        execute_repairs(db, settings, jobs, job_id, preview, user_confirmed=True)
