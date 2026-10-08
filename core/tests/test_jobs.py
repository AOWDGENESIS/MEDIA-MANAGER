"""Regressionstests fuer die Job-Queue (§17/§35/§36).

test_job_id_survives_simulated_restart deckt einen in Sitzung 2 (Deep
Review, Profil Python/SQL/B5-Nebenlaeufigkeit) gefundenen und behobenen
Bug ab: Job-IDs wurden ueber einen rein prozesslokalen In-Memory-Zaehler
erzeugt, der bei jedem Neustart wieder bei 1 begann und dadurch mit bereits
in der Datenbank vorhandenen IDs desselben Tages kollidierte
(sqlite3.IntegrityError). Reproduziert durch zwei unabhaengige JobManager-
Instanzen auf derselben Datenbankdatei (= zwei "Prozessstarts").

Die Tests ab `test_resume_rejects_already_completed_job` decken einen in
Sitzung 11 (Deep Review) gefundenen und behobenen Bug ab: pause/resume/
cancel pruefen den aktuellen Job-Status jetzt serverseitig, bevor sie ihn
aendern - vorher konnte z.B. ein bereits abgeschlossener Job per `resume()`
faelschlich wieder auf RUNNING zurueckgesetzt werden ("Geister-Job").
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from genesis_core.db import Database
from genesis_core.db.models import JobStatus
from genesis_core.jobs import JobManager, JobTransitionError


def test_job_ids_are_sequential_and_unique(db: Database):
    jm = JobManager(db)
    ids = [jm.create_job("scan") for _ in range(5)]
    assert len(set(ids)) == 5, "Job-IDs muessen eindeutig sein"
    assert ids == sorted(ids), "Job-IDs sollten fortlaufend aufsteigend sein"


def test_job_id_survives_simulated_restart(tmp_path: Path):
    """Frueher (Bug): zweite JobManager-Instanz (= 'Neustart') erzeugte
    dieselbe ID wie die letzte der ersten Instanz -> IntegrityError."""
    db_path = tmp_path / "restart_test.db"

    db_process_1 = Database(db_path)
    jm_process_1 = JobManager(db_process_1)
    first_run_ids = [jm_process_1.create_job("scan") for _ in range(3)]

    # Simulierter Neustart: komplett neue Database/JobManager-Instanz,
    # aber dieselbe zugrunde liegende SQLite-Datei (wie bei einem echten
    # Prozess-Neustart am selben Tag).
    db_process_2 = Database(db_path)
    jm_process_2 = JobManager(db_process_2)
    second_run_id = jm_process_2.create_job("scan")

    assert second_run_id not in first_run_ids
    all_ids = first_run_ids + [second_run_id]
    assert len(set(all_ids)) == len(all_ids)


def test_resume_rejects_already_completed_job(db: Database):
    jm = JobManager(db)
    job_id = jm.create_job("scan")
    jm.start(job_id)
    jm.complete(job_id)

    with pytest.raises(JobTransitionError):
        jm.resume(job_id)

    # Der Job darf nach dem fehlgeschlagenen Versuch nicht veraendert
    # worden sein - kein "Geister-Job", der ploetzlich wieder laeuft.
    job = jm.get_job(job_id)
    assert job.status == JobStatus.COMPLETED


def test_pause_rejects_job_that_is_not_running(db: Database):
    jm = JobManager(db)
    job_id = jm.create_job("scan")
    # Noch nicht gestartet (PENDING) - pausieren ist nicht erlaubt.
    with pytest.raises(JobTransitionError):
        jm.pause(job_id)
    assert jm.get_job(job_id).status == JobStatus.PENDING


def test_cancel_is_idempotent_when_already_cancelled(db: Database):
    jm = JobManager(db)
    job_id = jm.create_job("scan")
    jm.start(job_id)
    jm.cancel(job_id)
    # Zweiter Abbruch desselben Jobs darf NICHT fehlschlagen (siehe
    # execute_repairs_endpoint: ruft cancel() ggf. ein zweites Mal auf).
    jm.cancel(job_id)
    assert jm.get_job(job_id).status == JobStatus.CANCELLED


def test_cancel_rejects_already_completed_job(db: Database):
    jm = JobManager(db)
    job_id = jm.create_job("scan")
    jm.start(job_id)
    jm.complete(job_id)
    with pytest.raises(JobTransitionError):
        jm.cancel(job_id)
    assert jm.get_job(job_id).status == JobStatus.COMPLETED


def test_concurrent_cancel_and_resume_never_leaves_job_running(db: Database):
    """Reproduziert die in Sitzung 11 gefundene Rennbedingung: zwei
    Anfragen (abbrechen + fortsetzen) nahezu gleichzeitig auf denselben
    Job. Mit dem Lock+atomarer Transition-Pruefung darf GENAU EINE der
    beiden Operationen erfolgreich sein, niemals beide, und der Job darf
    am Ende nie in einem Status landen, der ihn faelschlich als 'laeuft'
    erscheinen laesst, nachdem er abgebrochen wurde."""
    jm = JobManager(db)
    job_id = jm.create_job("scan")
    jm.start(job_id)
    jm.pause(job_id)

    results = {}

    def do_cancel():
        try:
            jm.cancel(job_id)
            results["cancel"] = "ok"
        except JobTransitionError:
            results["cancel"] = "rejected"

    def do_resume():
        try:
            jm.resume(job_id)
            results["resume"] = "ok"
        except JobTransitionError:
            results["resume"] = "rejected"

    t1 = threading.Thread(target=do_cancel)
    t2 = threading.Thread(target=do_resume)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    final_status = jm.get_job(job_id).status
    # Keine Rennbedingung mehr erlaubt beide Operationen gleichzeitig
    # "erfolgreich" zu sein - der Lock serialisiert sie, die zweite sieht
    # bereits den von der ersten gesetzten Status.
    assert final_status in (JobStatus.CANCELLED, JobStatus.RUNNING)
    if final_status == JobStatus.CANCELLED:
        assert results["cancel"] == "ok"
        assert results["resume"] == "rejected"
    else:
        assert results["resume"] == "ok"
        assert results["cancel"] == "rejected"
