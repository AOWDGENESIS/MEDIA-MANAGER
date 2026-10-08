"""Scan & Repair-Workflow (§39).

Setzt die im gesamten Projekt verbindliche "Goldene Prozesskette" (Erkennen
-> Analysieren -> Vorschlag -> Vorschau -> Benutzerfreigabe -> Aenderung ->
Protokoll -> Rollback-Moeglichkeit) auf die von `genesis_core.diagnostics`
(§38) gefundenen, UNGEFAEHRLICH behebbaren Probleme an:

    plan_repairs()     - liest Diagnostics-Funde, fasst sie zu einer Liste
                          MOEGLICHER Reparaturen zusammen (rein lesend).
    preview_repairs()  - detaillierte, pruefbare Auflistung der konkreten
                          Datenbankzeilen/Dateien, die eine ausgewaehlte
                          Reparatur tatsaechlich betreffen wuerde (rein
                          lesend, veraendert nichts).
    execute_repairs()  - fuehrt NUR nach `user_confirmed=True` aus.
                          Erstellt ZUERST automatisch ein Datenbank-Backup
                          (§40 - konkrete Umsetzung von "Backup vor
                          Reparatur-Ausfuehrung") und protokolliert jede
                          Teilaktion in ProcessingHistory (§17). Deep-
                          Review-Praezisierung (Sitzung 11): das
                          tatsaechliche Rollback erfolgt grobkoernig ueber
                          Wiederherstellen DIESES VOR der Ausfuehrung
                          angelegten Gesamt-Backups (`POST /backup/{id}/
                          restore`) - NICHT zeilengenau aus den
                          ProcessingHistory-Eintraegen selbst (diese
                          speichern bei verwaisten Zeilen nur deren IDs,
                          nicht den vollstaendigen Zeileninhalt, und sind
                          damit allein nicht ausreichend fuer ein gezieltes
                          Undo einzelner Teilaktionen). Ruft ausserdem
                          zwischen den einzelnen Teilschritten
                          `JobManager.cooperative_checkpoint` auf, damit
                          ein laufender Reparaturlauf wie jeder andere
                          Batch-Job pausiert/fortgesetzt/abgebrochen
                          werden kann (§35/§36).

Bewusster Umfang dieser ersten Version (siehe PROGRESS.md fuer Backlog):
Nur die beiden ungefaehrlichsten, eindeutig sicheren Reparaturarten sind
abgedeckt - verwaiste Datenbankzeilen (Zeilen ohne zugehoerige Mediendatei,
koennen niemals mit einer echten Datei verwechselt werden) und veraltete
temporaere Dateien. Risikoreichere/urteilsabhaengige Faelle (z.B. ob eine
seit Monaten "fehlende" Mediendatei endgueltig aus der Bibliothek entfernt
werden soll, obwohl der Datentraeger vielleicht nur getrennt ist) werden
HIER BEWUSST NICHT automatisiert, sondern bleiben eine manuelle
Nutzerentscheidung in der jeweiligen Detailansicht.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

from sqlalchemy import delete

from genesis_core.backup import BackupResult, create_db_backup
from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.diagnostics import ORPHAN_CHECK_TABLES, find_orphaned_rows
from genesis_core.jobs import JobManager
from genesis_core.logutil import get_logger
from genesis_core.storage import TempFileCandidate, cleanup_temp_files, scan_temp_files

log = get_logger("Repair")

ACTION_CLEANUP_ORPHANED_ROWS = "cleanup_orphaned_rows"
ACTION_CLEANUP_TEMP_FILES = "cleanup_temp_files"

# Temp-Dateien, die seit weniger als dieser Zeitspanne veraendert wurden,
# gelten als "evtl. noch in Benutzung" und werden NICHT als Reparatur-
# Kandidat vorgeschlagen (Sicherheitsabstand gegen Race Conditions mit
# einem gerade laufenden Download/Export/Schnitt).
DEFAULT_TEMP_MIN_AGE_SECONDS = 3600.0

# Anzahl Zeilen, nach der waehrend der Ausfuehrung einer einzelnen,
# potenziell sehr grossen Tabellen-Bereinigung zusaetzlich ein
# kooperativer Pause/Abbruch-Checkpoint eingeschoben wird (siehe
# Moduldocstring, §35/§36).
CHECKPOINT_CHUNK_SIZE = 200


class RepairExecuteNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `execute_repairs` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #6, §44, §39)."""


@dataclasses.dataclass
class RepairPlanItem:
    action_type: str
    target: str
    count: int
    estimated_bytes: int | None
    description: str


@dataclasses.dataclass
class RepairPlan:
    generated_at: str
    items: list[RepairPlanItem]

    @property
    def is_empty(self) -> bool:
        return not self.items


@dataclasses.dataclass
class RepairPreviewItem:
    action_type: str
    target: str
    row_ids: list[int] = dataclasses.field(default_factory=list)
    temp_files: list[TempFileCandidate] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class RepairPreview:
    generated_at: str
    items: list[RepairPreviewItem]


@dataclasses.dataclass
class RepairActionResult:
    action_type: str
    target: str
    items_processed: int
    detail: str


@dataclasses.dataclass
class RepairExecutionResult:
    job_id: str
    backup: BackupResult
    actions: list[RepairActionResult]


def plan_repairs(
    db: Database, settings: Settings, *, temp_min_age_seconds: float = DEFAULT_TEMP_MIN_AGE_SECONDS
) -> RepairPlan:
    """Schritt 1 (Erkennen/Analysieren): liest ausschliesslich bereits
    vorhandene Diagnostics-/Speicher-Funktionen, veraendert nichts."""
    items: list[RepairPlanItem] = []

    orphans = find_orphaned_rows(db)
    for label, ids in orphans.items():
        items.append(
            RepairPlanItem(
                action_type=ACTION_CLEANUP_ORPHANED_ROWS,
                target=label,
                count=len(ids),
                estimated_bytes=None,
                description=(
                    f"{len(ids)} verwaiste Zeile(n) in '{label}' ohne zugehoerige "
                    "Mediendatei entfernen."
                ),
            )
        )

    temp_candidates = scan_temp_files(
        settings.paths.resolved_temp_dir(), older_than_seconds=temp_min_age_seconds
    )
    if temp_candidates:
        total_bytes = sum(c.size_bytes for c in temp_candidates)
        items.append(
            RepairPlanItem(
                action_type=ACTION_CLEANUP_TEMP_FILES,
                target="temp_dir",
                count=len(temp_candidates),
                estimated_bytes=total_bytes,
                description=(
                    f"{len(temp_candidates)} veraltete temporaere Datei(en) "
                    f"({total_bytes / (1024 * 1024):.1f} MB) loeschen."
                ),
            )
        )

    return RepairPlan(generated_at=dt.datetime.now(dt.UTC).isoformat(), items=items)


def preview_repairs(
    db: Database,
    settings: Settings,
    plan_items: list[RepairPlanItem],
    *,
    temp_min_age_seconds: float = DEFAULT_TEMP_MIN_AGE_SECONDS,
) -> RepairPreview:
    """Schritt 2 (Vorschau): loest die vom Nutzer AUSGEWAEHLTEN Plan-
    Eintraege in die konkreten betroffenen Zeilen/Dateien auf - rein
    lesend, damit der Nutzer vor der Bestaetigung genau sieht, was
    passieren wuerde (Prinzip #17)."""
    items: list[RepairPreviewItem] = []
    orphans: dict[str, list[int]] | None = None

    for plan_item in plan_items:
        if plan_item.action_type == ACTION_CLEANUP_ORPHANED_ROWS:
            if orphans is None:
                orphans = find_orphaned_rows(db)
            row_ids = orphans.get(plan_item.target, [])
            items.append(
                RepairPreviewItem(
                    action_type=ACTION_CLEANUP_ORPHANED_ROWS,
                    target=plan_item.target,
                    row_ids=row_ids,
                )
            )
        elif plan_item.action_type == ACTION_CLEANUP_TEMP_FILES:
            candidates = scan_temp_files(
                settings.paths.resolved_temp_dir(), older_than_seconds=temp_min_age_seconds
            )
            items.append(
                RepairPreviewItem(
                    action_type=ACTION_CLEANUP_TEMP_FILES,
                    target=plan_item.target,
                    temp_files=candidates,
                )
            )
        else:
            log.warning("Unbekannter Reparatur-Aktionstyp uebersprungen: %s", plan_item.action_type)

    return RepairPreview(
        generated_at=dt.datetime.now(dt.UTC).isoformat(), items=items
    )


def _model_for_label(label: str) -> Any:
    for table_label, model in ORPHAN_CHECK_TABLES:
        if table_label == label:
            return model
    return None


def execute_repairs(
    db: Database,
    settings: Settings,
    jobs: JobManager,
    job_id: str,
    preview: RepairPreview,
    *,
    user_confirmed: bool,
) -> RepairExecutionResult:
    """Schritt 3 (Aenderung + Protokoll): fuehrt die in `preview` gezeigten
    Reparaturen tatsaechlich aus. Erfordert IMMER `user_confirmed=True`
    (Prinzip #6, §44). Erstellt vorab ein Datenbank-Backup (§40) und
    protokolliert jede Teilaktion in ProcessingHistory (§17) sowie
    kooperative Checkpoints fuer Pause/Abbruch (§35/§36). Rollback-Hinweis
    (Deep-Review-Praezisierung, Sitzung 11): die Wiederherstellbarkeit
    kommt vom VORAB erstellten Backup (ganze DB, `backup.backup_id` oben),
    nicht aus ProcessingHistory selbst - siehe Moduldocstring."""
    if not user_confirmed:
        raise RepairExecuteNotConfirmedError(
            "Scan & Repair darf nur nach expliziter Nutzerbestaetigung der "
            "Vorschau ausgefuehrt werden (Prinzip #6, §44, §39)."
        )

    backup = create_db_backup(db, settings)
    log.info(
        "Scan & Repair Job %s: Sicherheits-Backup vor Ausfuehrung erstellt (Backup-ID %d).",
        job_id, backup.backup_id,
    )

    results: list[RepairActionResult] = []

    for item in preview.items:
        jobs.cooperative_checkpoint(job_id)

        if item.action_type == ACTION_CLEANUP_ORPHANED_ROWS:
            model = _model_for_label(item.target)
            if model is None or not item.row_ids:
                results.append(
                    RepairActionResult(
                        action_type=item.action_type, target=item.target,
                        items_processed=0, detail="Keine Zeilen zu entfernen.",
                    )
                )
                continue

            removed_total = 0
            for start in range(0, len(item.row_ids), CHECKPOINT_CHUNK_SIZE):
                jobs.cooperative_checkpoint(job_id)
                chunk = item.row_ids[start:start + CHECKPOINT_CHUNK_SIZE]
                with db.session() as session:
                    session.execute(delete(model).where(model.id.in_(chunk)))
                removed_total += len(chunk)
                jobs.record_history(
                    job_id, action=f"repair_{item.action_type}",
                    before={"table": item.target, "removed_ids": chunk},
                    after=None,
                    user_action="scan_and_repair_execute",
                )
            log.info(
                "Scan & Repair Job %s: %d verwaiste Zeile(n) in '%s' entfernt.",
                job_id, removed_total, item.target,
            )
            results.append(
                RepairActionResult(
                    action_type=item.action_type, target=item.target,
                    items_processed=removed_total,
                    detail=f"{removed_total} verwaiste Zeile(n) entfernt.",
                )
            )

        elif item.action_type == ACTION_CLEANUP_TEMP_FILES:
            removed_paths = cleanup_temp_files(
                settings.paths.resolved_temp_dir(), item.temp_files, user_confirmed=True
            )
            jobs.record_history(
                job_id, action=f"repair_{item.action_type}",
                before={"removed_paths": removed_paths}, after=None,
                user_action="scan_and_repair_execute",
            )
            log.info(
                "Scan & Repair Job %s: %d temporaere Datei(en) entfernt.",
                job_id, len(removed_paths),
            )
            results.append(
                RepairActionResult(
                    action_type=item.action_type, target=item.target,
                    items_processed=len(removed_paths),
                    detail=f"{len(removed_paths)} temporaere Datei(en) entfernt.",
                )
            )
        else:
            log.warning("Unbekannter Reparatur-Aktionstyp uebersprungen: %s", item.action_type)

    return RepairExecutionResult(job_id=job_id, backup=backup, actions=results)


__all__ = [
    "ACTION_CLEANUP_ORPHANED_ROWS",
    "ACTION_CLEANUP_TEMP_FILES",
    "CHECKPOINT_CHUNK_SIZE",
    "DEFAULT_TEMP_MIN_AGE_SECONDS",
    "RepairActionResult",
    "RepairExecuteNotConfirmedError",
    "RepairExecutionResult",
    "RepairPlan",
    "RepairPlanItem",
    "RepairPreview",
    "RepairPreviewItem",
    "execute_repairs",
    "plan_repairs",
    "preview_repairs",
]
