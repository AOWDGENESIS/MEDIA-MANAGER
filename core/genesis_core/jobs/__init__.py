"""Job Queue (§35/§36).

Phase-1-Umfang: Erzeugen/Verfolgen von Jobs mit eindeutiger ID, Fortschritt,
Fehlern/Warnungen, sowie Status-Uebergaengen (pending/running/paused/
completed/failed/cancelled). Die eigentliche parallele Ausfuehrung
langlaufender Aufgaben (Thread-/Prozess-Pool, Pause/Resume mitten in einer
Datei) folgt in spaeteren Phasen zusammen mit den jeweiligen Engines
(Scanner, Fingerprint, Loudness, Download, ...), die sich alle in diese
Queue einhaengen.

Hinweis (Deep Review, Sitzung 2): Job-IDs werden bewusst NICHT mehr aus
einem rein prozesslokalen In-Memory-Zaehler erzeugt. Ein solcher Zaehler
startet bei jedem Neustart des Core Service wieder bei 1 und kollidiert
dadurch garantiert mit bereits in der Datenbank vorhandenen IDs desselben
Tages (reproduzierbarer Bug, durch die Testsuite `test_job_id_*` belegt).
Stattdessen wird die naechste freie laufende Nummer aus der Datenbank
abgeleitet und bei einem seltenen Konflikt (parallele Erstellung) mit
begrenzten Wiederholungsversuchen neu vergeben (klassisches
Optimistic-Concurrency-Muster, siehe Deep-Review-Profil SQL/B5).
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from genesis_core.db import Database
from genesis_core.db.models import JobStatus, ProcessingHistory, ProcessingJob
from genesis_core.logutil import get_logger

log = get_logger("JobQueue")

MAX_JOB_ID_RETRIES = 5


class JobCancelledError(RuntimeError):
    """Wird von `JobManager.cooperative_checkpoint` ausgeloest, wenn ein
    laufender Batch-Job zwischenzeitlich abgebrochen wurde - die Engine
    fängt dies ab, beendet sauber (kein halbfertiger, unprotokollierter
    Zustand) und markiert den Job als CANCELLED statt FAILED."""


class JobTransitionError(RuntimeError):
    """Deep-Review-Fund (Sitzung 11): wird ausgeloest, wenn ein
    Statusuebergang (start/pause/resume/cancel) vom tatsaechlichen
    aktuellen Status des Jobs aus nicht erlaubt ist - z.B. 'fortsetzen'
    eines bereits abgeschlossenen oder abgebrochenen Jobs. Ohne diese
    Pruefung konnte ein bereits laengst beendeter Job (z.B. durch einen
    verspaeteten Doppelklick oder zwei fast gleichzeitige Anfragen) wieder
    faelschlich auf 'laeuft' zurueckgesetzt werden, obwohl keine Engine
    mehr tatsaechlich daran arbeitet - ein 'Geister-Job', der im
    Job-Queue-UI auf ewig 'laeuft', aber nie wieder Fortschritt macht.
    API-Schicht mappt dies auf HTTP 409 (Konflikt mit aktuellem Zustand),
    analog zu `JobCancelledError`."""



def _today_prefix() -> str:
    return f"JOB-{dt.datetime.now(dt.UTC).strftime('%Y%m%d')}-"


def _next_job_id(session, prefix: str) -> str:
    """Ermittelt die naechste freie Job-ID fuer den heutigen Tag anhand des
    aktuellen Datenbankinhalts (nicht anhand eines prozesslokalen Zaehlers -
    siehe Moduldocstring)."""
    existing_max = session.execute(
        select(func.max(ProcessingJob.id)).where(ProcessingJob.id.like(f"{prefix}%"))
    ).scalar_one_or_none()
    next_seq = 1
    if existing_max:
        try:
            next_seq = int(existing_max.rsplit("-", 1)[-1]) + 1
        except ValueError:
            next_seq = 1
    return f"{prefix}{next_seq:05d}"


class JobManager:
    def __init__(self, db: Database, app_version: str = "0.2.0"):
        self.db = db
        self.app_version = app_version
        # Deep-Review-Fund (Sitzung 11): schuetzt Statusuebergaenge
        # (start/pause/resume/cancel) vor "Lost Update"-Rennen bei
        # gleichzeitigen Anfragen auf denselben Job. JobManager ist pro
        # Core-Service-Prozess ein einziges, in `AppState` gehaltenes
        # Singleton (kein zweiter Prozess schreibt an derselben DB vorbei)
        # - ein einfacher Prozess-Lock reicht daher aus, verteiltes
        # Locking ueber die DB waere hier unnoetiger Mehraufwand.
        self._transition_lock = threading.Lock()

    def create_job(self, job_type: str, params: dict | None = None, total_items: int = 0) -> str:
        prefix = _today_prefix()
        last_error: Exception | None = None
        for attempt in range(MAX_JOB_ID_RETRIES):
            job_id = None
            try:
                # self.db.session() committet automatisch beim normalen
                # Verlassen des with-Blocks (siehe genesis_core.db.Database.
                # session). Ein IntegrityError beim Commit wird dort
                # zurueckgerollt und erneut ausgeloest - wir fangen ihn HIER,
                # ausserhalb des with-Blocks, ab und versuchen es mit einer
                # neu ermittelten ID erneut.
                with self.db.session() as session:
                    job_id = _next_job_id(session, prefix)
                    job = ProcessingJob(
                        id=job_id,
                        job_type=job_type,
                        status=JobStatus.PENDING,
                        total_items=total_items,
                        params_json=params or {},
                        app_version=self.app_version,
                    )
                    session.add(job)
            except IntegrityError as exc:
                last_error = exc
                log.warning(
                    "Job-ID-Konflikt bei %s (Versuch %d/%d) - neue ID wird vergeben",
                    job_id, attempt + 1, MAX_JOB_ID_RETRIES,
                )
                continue
            log.info("Job erstellt: %s (%s)", job_id, job_type)
            return job_id
        raise RuntimeError(
            f"Konnte nach {MAX_JOB_ID_RETRIES} Versuchen keine eindeutige Job-ID vergeben"
        ) from last_error


    def start(self, job_id: str) -> None:
        self._transition(
            job_id,
            allowed_from={JobStatus.PENDING},
            new_status=JobStatus.RUNNING,
            extra_fields={"started_at": dt.datetime.now(dt.UTC)},
        )

    def report_progress(
        self,
        job_id: str,
        processed_items: int | None = None,
        current_item: str | None = None,
        error_delta: int = 0,
        warning_delta: int = 0,
    ) -> None:
        with self.db.session() as session:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                return
            if processed_items is not None:
                job.processed_items = processed_items
            if current_item is not None:
                job.current_item = current_item
            job.error_count += error_delta
            job.warning_count += warning_delta

    def pause(self, job_id: str) -> None:
        """§35/§36 - nur aus 'laeuft' heraus erlaubt (siehe JobTransitionError-
        Docstring). Die PySide6-Job-Queue-Ansicht aktiviert den
        Pause-Button bereits nur bei status=='running' - diese Pruefung
        ist die serverseitige Durchsetzung derselben Regel, falls der
        UI-Zustand veraltet ist (z.B. der Job ist zwischen Laden der
        Ansicht und Klick von selbst fertig geworden)."""
        self._transition(job_id, allowed_from={JobStatus.RUNNING}, new_status=JobStatus.PAUSED)

    def resume(self, job_id: str) -> None:
        self._transition(job_id, allowed_from={JobStatus.PAUSED}, new_status=JobStatus.RUNNING)

    def cancel(self, job_id: str) -> None:
        """Abbrechen ist - anders als pause/resume/start - bewusst
        idempotent, wenn der Job bereits CANCELLED ist: `execute_repairs_
        endpoint` (und vergleichbare Stellen) rufen `cancel()` sowohl beim
        Auftreten von `JobCancelledError` INNERHALB der Engine als auch
        moeglicherweise bereits vorher ueber den oeffentlichen
        `/jobs/{id}/cancel`-Endpunkt auf - ein zweiter Aufruf darf dabei
        NICHT fehlschlagen. Abbrechen eines bereits COMPLETED/FAILED-Jobs
        bleibt dagegen verboten (waere fachlich irrefuehrend - ein bereits
        erfolgreich abgeschlossener Stapel-Umbenennungslauf darf im
        Protokoll nicht nachtraeglich als 'abgebrochen' erscheinen)."""
        self._transition(
            job_id,
            allowed_from={JobStatus.PENDING, JobStatus.RUNNING, JobStatus.PAUSED},
            new_status=JobStatus.CANCELLED,
            extra_fields={"finished_at": dt.datetime.now(dt.UTC)},
            idempotent_if_already=JobStatus.CANCELLED,
        )

    def complete(self, job_id: str) -> None:
        self._transition(
            job_id,
            allowed_from={JobStatus.RUNNING, JobStatus.PAUSED},
            new_status=JobStatus.COMPLETED,
            extra_fields={"finished_at": dt.datetime.now(dt.UTC)},
        )

    def fail(self, job_id: str, error_message: str) -> None:
        """Im Unterschied zu start/pause/resume/cancel bewusst OHNE
        Statusuebergangs-Pruefung: 'als fehlgeschlagen markieren' muss
        immer moeglich sein, unabhaengig vom aktuellen Status - Prinzip
        #19/§37 'keine stillen Fehler' hat hier Vorrang vor einer strikten
        Zustandsmaschine. Laeuft dennoch unter demselben Lock wie die
        uebrigen Uebergaenge, damit ein gleichzeitiges complete()/cancel()
        nicht mit einem fail() um denselben DB-Write konkurriert."""
        with self._transition_lock, self.db.session() as session:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                return
            job.status = JobStatus.FAILED
            job.finished_at = dt.datetime.now(dt.UTC)
            job.error_count += 1
        log.error("Job fehlgeschlagen: %s - %s", job_id, error_message)

    def record_history(
        self,
        job_id: str,
        action: str,
        media_file_id: int | None = None,
        before: dict | None = None,
        after: dict | None = None,
        user_action: str | None = None,
        error: str | None = None,
        warning: str | None = None,
    ) -> None:
        """Fuer Rollback (§17): Vorher-/Nachher-Zustand jeder Einzelaenderung."""
        with self.db.session() as session:
            session.add(
                ProcessingHistory(
                    job_id=job_id,
                    media_file_id=media_file_id,
                    action=action,
                    before_json=before,
                    after_json=after,
                    user_action=user_action,
                    app_version=self.app_version,
                    error=error,
                    warning=warning,
                )
            )

    def cooperative_checkpoint(
        self, job_id: str, poll_interval_seconds: float = 0.2, max_wait_seconds: float = 3600.0
    ) -> None:
        """§35 "pausierbar/fortsetzbar/abbrechbar" - zwischen einzelnen
        Elementen eines Batch-Jobs (z.B. je Datei beim Scan & Repair oder
        bei einer Stapel-Neuberechnung) aufzurufen. Blockiert kooperativ
        (Polling, kein Threading-Primitiv noetig - Phase-1-Umfang bewusst
        einfach gehalten, siehe Moduldocstring), solange der Job PAUSED
        ist, und wirft `JobCancelledError`, sobald er CANCELLED wurde -
        die aufrufende Engine fängt das ab und beendet sauber.

        Kein No-Op bei fehlendem Job (z.B. nach DB-Reset mitten im Lauf) -
        dann wird ebenfalls abgebrochen, statt unbemerkt endlos weiter zu
        laufen."""
        waited = 0.0
        while True:
            job = self.get_job(job_id)
            if job is None or job.status == JobStatus.CANCELLED:
                raise JobCancelledError(f"Job {job_id} wurde abgebrochen")
            if job.status != JobStatus.PAUSED:
                return
            if waited >= max_wait_seconds:
                raise JobCancelledError(
                    f"Job {job_id} blieb laenger als {max_wait_seconds}s pausiert - abgebrochen"
                )
            time.sleep(poll_interval_seconds)
            waited += poll_interval_seconds

    def get_job(self, job_id: str) -> ProcessingJob | None:
        with self.db.session() as session:
            return session.get(ProcessingJob, job_id)

    def list_jobs(self, limit: int = 50) -> list[ProcessingJob]:
        with self.db.session() as session:
            return list(
                session.execute(
                    select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(limit)
                ).scalars()
            )

    def _transition(
        self,
        job_id: str,
        *,
        allowed_from: frozenset[JobStatus],
        new_status: JobStatus,
        extra_fields: dict | None = None,
        idempotent_if_already: JobStatus | None = None,
    ) -> None:
        """Deep-Review-Fund (Sitzung 11): fuehrt Lesen des aktuellen Status
        und Schreiben des neuen Status ATOMAR (ein Lock + eine einzige
        DB-Session/Transaktion) aus, statt wie zuvor Lesen (`get_job`) und
        Schreiben als zwei getrennte Operationen mit einer Rennbedingung
        dazwischen. Verweigert den Uebergang mit `JobTransitionError`,
        wenn der tatsaechliche aktuelle Status nicht in `allowed_from`
        enthalten ist - AUSSER der Job hat bereits exakt `new_status`
        erreicht (idempotent, siehe `cancel()`-Docstring)."""
        with self._transition_lock, self.db.session() as session:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                log.warning("Job nicht gefunden: %s", job_id)
                return
            if idempotent_if_already is not None and job.status == idempotent_if_already:
                return
            if job.status not in allowed_from:
                raise JobTransitionError(
                    f"Job {job_id}: Uebergang nach '{new_status.value}' ist aus "
                    f"Status '{job.status.value}' nicht erlaubt (erlaubt nur aus: "
                    f"{', '.join(sorted(s.value for s in allowed_from))})."
                )
            job.status = new_status
            for key, value in (extra_fields or {}).items():
                setattr(job, key, value)
