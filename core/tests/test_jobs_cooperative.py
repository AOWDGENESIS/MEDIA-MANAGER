"""Tests fuer pausierbare/abbrechbare Batch-Jobs (§35/§36, ADR-0020)."""
from __future__ import annotations

import pytest

from genesis_core.db import Database
from genesis_core.jobs import JobCancelledError, JobManager


def test_checkpoint_returns_immediately_when_running(db: Database) -> None:
    jobs = JobManager(db, app_version="test")
    job_id = jobs.create_job("test_batch")
    jobs.start(job_id)
    jobs.cooperative_checkpoint(job_id)  # darf nicht blockieren/werfen


def test_checkpoint_raises_when_cancelled(db: Database) -> None:
    jobs = JobManager(db, app_version="test")
    job_id = jobs.create_job("test_batch")
    jobs.start(job_id)
    jobs.cancel(job_id)
    with pytest.raises(JobCancelledError):
        jobs.cooperative_checkpoint(job_id)


def test_checkpoint_raises_when_job_missing(db: Database) -> None:
    jobs = JobManager(db, app_version="test")
    with pytest.raises(JobCancelledError):
        jobs.cooperative_checkpoint("JOB-DOES-NOT-EXIST")


def test_checkpoint_blocks_while_paused_then_continues(db: Database) -> None:
    jobs = JobManager(db, app_version="test")
    job_id = jobs.create_job("test_batch")
    jobs.start(job_id)
    jobs.pause(job_id)

    import threading

    def resume_later():
        import time

        time.sleep(0.3)
        jobs.resume(job_id)

    t = threading.Thread(target=resume_later)
    t.start()
    jobs.cooperative_checkpoint(job_id, poll_interval_seconds=0.05, max_wait_seconds=5)
    t.join()
    assert jobs.get_job(job_id).status.value == "running"


def test_checkpoint_raises_when_paused_too_long(db: Database) -> None:
    jobs = JobManager(db, app_version="test")
    job_id = jobs.create_job("test_batch")
    jobs.start(job_id)
    jobs.pause(job_id)
    with pytest.raises(JobCancelledError):
        jobs.cooperative_checkpoint(job_id, poll_interval_seconds=0.02, max_wait_seconds=0.1)


def test_pause_resume_cancel_transitions(db: Database) -> None:
    jobs = JobManager(db, app_version="test")
    job_id = jobs.create_job("test_batch")
    jobs.start(job_id)
    assert jobs.get_job(job_id).status.value == "running"
    jobs.pause(job_id)
    assert jobs.get_job(job_id).status.value == "paused"
    jobs.resume(job_id)
    assert jobs.get_job(job_id).status.value == "running"
    jobs.cancel(job_id)
    assert jobs.get_job(job_id).status.value == "cancelled"
