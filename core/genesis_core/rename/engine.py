"""Rename-Engine (§15/§16): Vorlage -> verpflichtende Vorschau -> Bestaetigung
-> Ausfuehrung mit Rollback bei Teilausfall.

Scope dieser ersten Version (bewusste, dokumentierte Einschraenkung):
Vorlagen aendern nur den DATEINAMEN innerhalb des BESTEHENDEN Verzeichnisses,
noch keine komplette Bibliotheks-Neuorganisation in Ordnerbaeume
(Artist/Album/...). Eine echte Verzeichnis-Umstrukturierung braucht
zusaetzliche Sicherheitsueberlegungen (Basis-Verzeichnis-Tracking,
verwaiste leere Ordner, plattformuebergreifende Pfadlaengen) und ist als
Backlog-Punkt fuer eine spaetere Phase vorgesehen (siehe PROGRESS.md) -
lieber eine kleinere, gruendlich getestete Funktion jetzt als eine
halbfertige, riskantere jetzt.

Sicherheitsmechanik:
1. `preview_renames` ist rein LESEND (Prinzip #4/#5) - prüft Kollisionen
   (im Batch UNTEREINANDER und gegen die Festplatte/DB), fehlende Felder,
   und ob die Dateiendung erhalten bleibt.
2. `apply_renames` erfordert IMMER `user_confirmed=True` (Prinzip #17, §44)
   und fuehrt NUR konfliktfreie, valide Eintraege aus. Schlaegt eine
   Umbenennung inmitten des Batches unerwartet fehl (z.B. Race Condition,
   Berechtigungsfehler), werden alle in diesem Aufruf bereits erfolgreich
   umbenannten Dateien wieder auf ihren Originalnamen zurueckgesetzt
   (Prinzip #4 - kein gefaehrlicher Halbzustand).
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from sqlalchemy import select

from genesis_core.db.models import Album, MediaFile, Track
from genesis_core.logutil import get_logger
from genesis_core.rename.templates import RenameTemplateError, render_template

log = get_logger("RenameEngine")


class RenameApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `apply_renames` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #17/§44, hart im Code erzwungen)."""


class RenameBatchFailedError(RuntimeError):
    """Ein Batch wurde teilweise ausgefuehrt und dann vollstaendig
    zurueckgerollt, weil ein unerwarteter Fehler mitten im Batch auftrat."""


@dataclasses.dataclass
class RenamePreviewItem:
    media_file_id: int
    old_absolute_path: str
    new_absolute_path: str
    empty_fields: list[str]
    has_conflict: bool
    conflict_reason: str | None
    is_identical: bool
    template_error: str | None = None

    @property
    def is_actionable(self) -> bool:
        return (
            self.template_error is None
            and not self.has_conflict
            and not self.is_identical
        )


@dataclasses.dataclass
class RenameApplyResult:
    media_file_id: int
    applied: bool
    old_absolute_path: str
    new_absolute_path: str
    reason: str | None = None


def _build_context(media_file: MediaFile, track: Track | None, album: Album | None) -> dict:
    ext = media_file.extension.lstrip(".")
    return {
        "artist": track.album_artist if track else None,
        "albumartist": track.album_artist if track else None,
        "album": album.title if album else None,
        "title": track.title if track else None,
        "track": track.track_number if track else None,
        "disc": track.disc_number if track else None,
        "year": track.year if track else None,
        "ext": ext,
        "original_filename": Path(media_file.filename).stem,
    }


def preview_renames(
    session, media_file_ids: list[int], template: str
) -> list[RenamePreviewItem]:
    """Rein lesende Vorschau (Prinzip #4/#5) - veraendert nichts auf der
    Festplatte oder in der Datenbank."""
    if "/" in template or "\\" in template:
        raise RenameTemplateError(
            "Verzeichniswechsel per Vorlage (\"/\" oder \"\\\") wird in dieser "
            "Version noch nicht unterstuetzt - Vorlagen aendern aktuell nur "
            "den Dateinamen innerhalb des bestehenden Ordners."
        )

    items: list[RenamePreviewItem] = []
    planned_targets: dict[str, list[int]] = {}

    for media_file_id in media_file_ids:
        media_file = session.get(MediaFile, media_file_id)
        if media_file is None:
            continue
        track = session.execute(
            select(Track).where(Track.media_file_id == media_file_id)
        ).scalar_one_or_none()
        album = session.get(Album, track.album_id) if (track and track.album_id) else None

        context = _build_context(media_file, track, album)
        old_path = Path(media_file.absolute_path)

        try:
            new_filename, empty_fields = render_template(template, context)
        except RenameTemplateError as exc:
            items.append(
                RenamePreviewItem(
                    media_file_id=media_file_id,
                    old_absolute_path=str(old_path),
                    new_absolute_path=str(old_path),
                    empty_fields=[],
                    has_conflict=False,
                    conflict_reason=None,
                    is_identical=False,
                    template_error=str(exc),
                )
            )
            continue

        new_path = old_path.parent / new_filename
        expected_ext = media_file.extension.lower()
        template_error = None
        if new_path.suffix.lower() != expected_ext:
            template_error = (
                f"Die Vorlage aendert die Dateiendung von '{expected_ext}' zu "
                f"'{new_path.suffix.lower()}' - das wuerde die Datei nicht "
                "wirklich konvertieren, nur den Namen veraendern. Bitte "
                f"'{{ext}}' in der Vorlage verwenden."
            )

        planned_targets.setdefault(str(new_path), []).append(media_file_id)
        items.append(
            RenamePreviewItem(
                media_file_id=media_file_id,
                old_absolute_path=str(old_path),
                new_absolute_path=str(new_path),
                empty_fields=empty_fields,
                has_conflict=False,  # wird im zweiten Durchlauf unten gesetzt
                conflict_reason=None,
                is_identical=(new_path == old_path),
                template_error=template_error,
            )
        )

    # Zweiter Durchlauf: Konflikte erkennen (Batch-intern + Festplatte + DB).
    known_absolute_paths = {
        p for (p,) in session.execute(select(MediaFile.absolute_path)).all()
    }
    for item in items:
        if item.template_error or item.is_identical:
            continue
        target = item.new_absolute_path
        collided_with_other_item = len(planned_targets.get(target, [])) > 1
        exists_on_disk = Path(target).exists()
        # Deep-Review-Fund (Sitzung 3, F-09): Auf case-insensitiven, aber
        # case-preservierenden Dateisystemen (Windows/NTFS = Hauptzielsystem
        # dieser App, macOS-Standard-APFS) meldet `Path(target).exists()`
        # bereits True fuer eine reine GROSS-/kleinschreibungs-Korrektur der
        # EIGENEN Datei (z.B. "song.mp3" -> "Song.mp3"), weil das
        # Betriebssystem den Zielnamen als bereits vorhanden ansieht. Ohne
        # diese Pruefung wuerde das faelschlich als Kollision mit einer
        # FREMDEN Datei gemeldet und eine ganz gewoehnliche Aktion (Schreib-
        # weise korrigieren) waere nie moeglich. `os.path.samefile` prueft
        # die tatsaechliche Dateiidentitaet (Inode/File-ID) statt nur den
        # Namen und unterscheidet so zuverlaessig "ist meine eigene Datei"
        # von "gehoert einer anderen Datei" - auf case-sensitiven
        # Dateisystemen (Linux) ist alter und neuer Pfad ohnehin nie
        # gleichzeitig vorhanden, daher dort ein reiner No-Op.
        is_case_only_self_match = False
        if exists_on_disk and target != item.old_absolute_path:
            old_path_on_disk = Path(item.old_absolute_path)
            if old_path_on_disk.exists():
                try:
                    is_case_only_self_match = os.path.samefile(target, old_path_on_disk)
                except OSError:
                    is_case_only_self_match = False
        exists_in_db_for_other_file = (
            target in known_absolute_paths and target != item.old_absolute_path
        )
        if collided_with_other_item:
            item.has_conflict = True
            item.conflict_reason = (
                "Mehrere ausgewaehlte Dateien wuerden auf denselben Zielnamen "
                "umbenannt (Vorlage nicht eindeutig genug fuer diese Auswahl)."
            )
        elif (exists_on_disk and not is_case_only_self_match) or exists_in_db_for_other_file:
            item.has_conflict = True
            item.conflict_reason = f"Zieldatei existiert bereits: {target}"

    return items



def apply_renames(
    session, preview_items: list[RenamePreviewItem], *, user_confirmed: bool
) -> list[RenameApplyResult]:
    if not user_confirmed:
        raise RenameApplyNotConfirmedError(
            "Eine Umbenennung darf nur nach expliziter Nutzerbestaetigung der "
            "Vorschau ausgefuehrt werden (Prinzip #17, §44, §16)."
        )

    results: list[RenameApplyResult] = []
    completed_fs_renames: list[tuple[Path, Path]] = []

    try:
        for item in preview_items:
            if not item.is_actionable:
                reason = item.template_error or item.conflict_reason or "Kein Zielname (identisch)"
                results.append(
                    RenameApplyResult(
                        media_file_id=item.media_file_id,
                        applied=False,
                        old_absolute_path=item.old_absolute_path,
                        new_absolute_path=item.new_absolute_path,
                        reason=reason,
                    )
                )
                continue

            old_path = Path(item.old_absolute_path)
            new_path = Path(item.new_absolute_path)

            os.rename(old_path, new_path)  # atomar auf demselben Dateisystem
            completed_fs_renames.append((old_path, new_path))

            media_file = session.get(MediaFile, item.media_file_id)
            if media_file is not None:
                media_file.absolute_path = str(new_path)
                media_file.directory = str(new_path.parent)
                media_file.filename = new_path.name
                # Sofortiges Flush statt erst beim Commit am Ende des
                # umgebenden `with db.session():`-Blocks: so schlagen
                # DB-Constraint-Verletzungen (z.B. doppelter absolute_path)
                # SOFORT hier fehl und loesen unseren Dateisystem-Rollback
                # aus, statt erst spaeter unbemerkt beim finalen Commit
                # (Restrisiko: ein Fehler ausschliesslich beim finalen
                # COMMIT selbst, z.B. Festplatte voll, bleibt ein sehr
                # seltener Grenzfall, siehe Moduldocstring).
                session.flush()

            results.append(
                RenameApplyResult(
                    media_file_id=item.media_file_id,
                    applied=True,
                    old_absolute_path=str(old_path),
                    new_absolute_path=str(new_path),
                )
            )
            log.info("Umbenannt: %s -> %s", old_path, new_path)
    except Exception as exc:
        log.error(
            "Umbenennen-Batch fehlgeschlagen (%s) - rolle %d bereits "
            "durchgefuehrte Umbenennung(en) zurueck.",
            exc, len(completed_fs_renames),
        )
        for old_path, new_path in reversed(completed_fs_renames):
            try:
                os.rename(new_path, old_path)
            except OSError as rollback_exc:
                log.critical(
                    "KRITISCH: Rollback fehlgeschlagen fuer %s -> %s: %s. "
                    "Manuelle Pruefung erforderlich!",
                    new_path, old_path, rollback_exc,
                )
        raise RenameBatchFailedError(
            f"Umbenennen-Vorgang fehlgeschlagen und zurueckgerollt: {exc}"
        ) from exc

    return results
