"""Strukturierte Fehlerbehandlung (§37) - "keine stillen Fehler".

Jeder unerwartete Fehler bekommt eine eindeutige Error-ID (gleiches Muster
wie die JOB-IDs aus `genesis_core.jobs`, DB-abgeleitet statt
prozesslokalem Zähler - überlebt Neustarts, keine Kollisionen) sowie alle
im Originalauftrag geforderten Felder: Zeit, Komponente, Datei, Aktion,
Fehlermeldung, technische Details, Lösungsvorschlag.

Zwei Einsatzwege:

1. Explizit: eine Engine/ein Endpunkt ruft `log_error(...)` auf, wenn ein
   bekannter, aber nicht vom Nutzer verursachter Fehler auftritt (z.B. ein
   Provider ist nicht erreichbar) - liefert eine Error-ID zurück, die dem
   Nutzer angezeigt werden kann ("Fehler ERR-20261001-00003 - Details").
2. Automatisch: der globale FastAPI-Exception-Handler (siehe
   `api/app.py`, `install_error_handler`) fängt JEDE sonst unbehandelte
   Exception ab, bevor sie als rohe 500-Antwort ohne Kontext beim Client
   ankäme, erzeugt daraus einen Error-Log-Eintrag und liefert eine
   einheitliche, UI-freundliche Fehlerantwort gemäß §37-Beispiel.

WICHTIG: Erwartete, bewusst gestaltete Validierungsfehler (z.B. "confirm
fehlt" -> 422, "Profil nicht gefunden" -> 404) sind KEINE "stillen Fehler"
im Sinne von §37 - sie werden bereits an ihrer jeweiligen Stelle sauber in
eine passende HTTP-Antwort übersetzt und landen bewusst NICHT zusätzlich
im Error-Log (das würde das Log mit erwartetem Verhalten überfluten statt
echte Probleme sichtbar zu machen).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import traceback

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from genesis_core.db import Database
from genesis_core.db.models import ErrorLog
from genesis_core.logutil import get_logger

log = get_logger("ErrorCenter")

MAX_ERROR_ID_RETRIES = 5


def _today_prefix() -> str:
    return f"ERR-{dt.datetime.now(dt.UTC).strftime('%Y%m%d')}-"


def _next_error_id(session, prefix: str) -> str:
    existing_max = session.execute(
        select(func.max(ErrorLog.error_id)).where(ErrorLog.error_id.like(f"{prefix}%"))
    ).scalar_one_or_none()
    next_seq = 1
    if existing_max:
        try:
            next_seq = int(existing_max.rsplit("-", 1)[-1]) + 1
        except ValueError:
            next_seq = 1
    return f"{prefix}{next_seq:05d}"


@dataclasses.dataclass
class ErrorRecord:
    error_id: str
    timestamp: str
    component: str
    message: str
    file_path: str | None = None
    action: str | None = None
    technical_details: str | None = None
    solution_hint: str | None = None


class GenesisError(RuntimeError):
    """Basisklasse für Fehler, die bewusst mit vollem §37-Kontext erzeugt
    werden (statt einer rohen `RuntimeError`/`ValueError`)."""

    def __init__(
        self,
        message: str,
        *,
        component: str,
        action: str | None = None,
        file_path: str | None = None,
        technical_details: str | None = None,
        solution_hint: str | None = None,
    ):
        super().__init__(message)
        self.component = component
        self.action = action
        self.file_path = file_path
        self.technical_details = technical_details
        self.solution_hint = solution_hint


def log_error(
    db: Database,
    component: str,
    message: str,
    *,
    action: str | None = None,
    file_path: str | None = None,
    technical_details: str | None = None,
    solution_hint: str | None = None,
) -> ErrorRecord:
    """Persistiert einen Fehler zentral (Error-Center, §37/§38) und gibt
    eine `ErrorRecord` mit der vergebenen Error-ID zurück."""
    prefix = _today_prefix()
    last_error: Exception | None = None
    for attempt in range(MAX_ERROR_ID_RETRIES):
        error_id = None
        try:
            with db.session() as session:
                error_id = _next_error_id(session, prefix)
                row = ErrorLog(
                    error_id=error_id,
                    component=component,
                    file_path=file_path,
                    action=action,
                    message=message,
                    technical_details=technical_details,
                    solution_hint=solution_hint,
                )
                session.add(row)
                session.flush()
                timestamp = row.timestamp.isoformat()
        except IntegrityError as exc:
            last_error = exc
            log.warning(
                "Error-ID-Konflikt bei %s (Versuch %d/%d) - neue ID wird vergeben",
                error_id, attempt + 1, MAX_ERROR_ID_RETRIES,
            )
            continue
        log.error("[%s] %s (%s): %s", error_id, component, action or "-", message)
        return ErrorRecord(
            error_id=error_id, timestamp=timestamp, component=component, message=message,
            file_path=file_path, action=action, technical_details=technical_details,
            solution_hint=solution_hint,
        )
    raise RuntimeError(
        f"Konnte nach {MAX_ERROR_ID_RETRIES} Versuchen keine eindeutige Error-ID vergeben"
    ) from last_error


def log_exception(
    db: Database,
    component: str,
    exc: Exception,
    *,
    action: str | None = None,
    file_path: str | None = None,
    user_message: str | None = None,
    solution_hint: str | None = None,
) -> ErrorRecord:
    """Komfortfunktion für den häufigen Fall "eine unerwartete Exception
    ist aufgetreten" - übernimmt den vollständigen Traceback automatisch
    als technische Details."""
    return log_error(
        db,
        component,
        user_message or str(exc) or exc.__class__.__name__,
        action=action,
        file_path=file_path,
        technical_details="".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
        solution_hint=solution_hint,
    )


def list_errors(db: Database, limit: int = 100, unresolved_only: bool = False) -> list[ErrorLog]:
    with db.session() as session:
        stmt = select(ErrorLog).order_by(ErrorLog.timestamp.desc()).limit(limit)
        if unresolved_only:
            stmt = stmt.where(ErrorLog.resolved.is_(False))
        return list(session.execute(stmt).scalars())


def mark_resolved(db: Database, error_id: str) -> bool:
    with db.session() as session:
        row = session.execute(
            select(ErrorLog).where(ErrorLog.error_id == error_id)
        ).scalar_one_or_none()
        if row is None:
            return False
        row.resolved = True
        return True
