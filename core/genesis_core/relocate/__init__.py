"""Pfad-Relokation (§43): Wiederverknuepfung von Mediendateien, die

ausserhalb von GENESIS (z.B. per Windows-Explorer, nach einem
Festplattentausch, nach dem Umhaengen eines Laufwerksbuchstabens)
verschoben/umbenannt wurden und deshalb vom Scanner als `is_missing=True`
markiert sind (siehe `genesis_core.scanner`).

Folgt derselben "Goldenen Prozesskette" wie der Rest des Projekts:
Erkennen (Scanner markiert als vermisst) -> Analysieren/Vorschlag
(`find_relocation_candidates`, rein lesend, mit Konfidenzwert pro
Methode) -> Vorschau (dieselbe Kandidatenliste wird dem Nutzer gezeigt) ->
Bestaetigung -> Aenderung (`apply_relocations`, NUR nach
`user_confirmed=True`) -> Protokoll (ProcessingHistory, analog zur
Rename-Engine - wird von der aufrufenden API-Schicht ergaenzt, genau wie
bei `genesis_core.rename`).

Drei Erkennungsstufen, von staerkstem zu schwaechstem Signal:
1. Datei-Hash (`content_hash_sha256`) - Confidence 1.0. Erkennt auch
   gleichzeitige Umbenennung, da der Hash inhaltsbasiert ist.
2. Dateiname + Dateigroesse - Confidence 0.7. Schwaecheres Signal (Name +
   Groesse koennten zufaellig uebereinstimmen), daher niedrigere
   Konfidenz und NUR ein Fallback, wenn kein frueherer Hash bekannt ist.
3. Audio-Fingerprint (Chromaprint, optional via `use_fingerprint=True`,
   rechenintensiv) - Confidence 0.85. Erkennt denselben Audioinhalt auch
   nach einer Konvertierung waehrend des Verschiebens (z.B. FLAC -> MP3).

WICHTIG: Dies ist ein reiner VORSCHLAG. Keine Konfidenzstufe wird jemals
automatisch uebernommen (Prinzip #17) - `apply_relocations` erfordert
immer eine explizite Nutzerbestaetigung JE Kandidat (die aufrufende
Schicht filtert die vom Nutzer tatsaechlich akzeptierte Teilmenge, bevor
sie `apply_relocations` aufruft).
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from sqlalchemy import select

from genesis_core.db import Database
from genesis_core.db.models import Fingerprint, MediaFile
from genesis_core.fingerprint import FingerprintError, compute_fingerprint, is_fpcalc_available
from genesis_core.logutil import get_logger
from genesis_core.scanner.classify import is_supported_media_extension
from genesis_core.scanner.hashing import sha256_of_file

log = get_logger("Relocate")

MATCH_HASH = "hash"
MATCH_FILENAME_AND_SIZE = "filename_and_size"
MATCH_FINGERPRINT = "fingerprint"

CONFIDENCE_BY_METHOD = {
    MATCH_HASH: 1.0,
    MATCH_FINGERPRINT: 0.85,
    MATCH_FILENAME_AND_SIZE: 0.7,
}


class RelocationApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `apply_relocations` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #6, §44, §43)."""


@dataclasses.dataclass
class RelocationCandidate:
    media_file_id: int
    old_absolute_path: str
    new_absolute_path: str
    match_method: str
    confidence: float


@dataclasses.dataclass
class RelocationApplyResult:
    media_file_id: int
    applied: bool
    old_absolute_path: str
    new_absolute_path: str
    reason: str | None = None


def _collect_candidate_files(search_roots: list[str | Path]) -> list[Path]:
    found: list[Path] = []
    for root in search_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(root_path):
            for name in filenames:
                p = Path(dirpath) / name
                if is_supported_media_extension(p.suffix):
                    found.append(p)
    return found


def find_relocation_candidates(
    db: Database, search_roots: list[str | Path], *, use_fingerprint: bool = False
) -> list[RelocationCandidate]:
    """Schritt 1+2 (Erkennen/Analysieren -> Vorschlag): rein lesend,
    veraendert nichts (Prinzip #4/#5). Durchsucht `search_roots` nach
    Dateien, die zu einer als vermisst markierten MediaFile passen
    koennten."""
    with db.session() as session:
        missing = list(
            session.execute(
                select(MediaFile).where(MediaFile.is_missing == True)
            ).scalars()
        )
        already_known_paths = set(session.execute(select(MediaFile.absolute_path)).scalars())
        existing_fingerprints: dict[int, str] = {}
        if use_fingerprint:
            for mf in missing:
                fp = session.execute(
                    select(Fingerprint)
                    .where(Fingerprint.media_file_id == mf.id)
                    .order_by(Fingerprint.id.desc())
                ).scalars().first()
                if fp is not None:
                    existing_fingerprints[mf.id] = fp.fingerprint_data

    if not missing:
        return []

    candidate_paths = [
        p for p in _collect_candidate_files(search_roots) if str(p) not in already_known_paths
    ]

    candidates_by_size: dict[int, list[Path]] = {}
    for p in candidate_paths:
        try:
            size = p.stat().st_size
        except OSError:
            continue
        candidates_by_size.setdefault(size, []).append(p)

    results: list[RelocationCandidate] = []
    for mf in missing:
        same_size = candidates_by_size.get(mf.size_bytes, [])
        matched: Path | None = None
        method: str | None = None

        if mf.content_hash_sha256:
            for cand in same_size:
                try:
                    cand_hash = sha256_of_file(cand)
                except OSError:
                    continue
                if cand_hash == mf.content_hash_sha256:
                    matched, method = cand, MATCH_HASH
                    break

        if matched is None:
            for cand in same_size:
                if cand.name == mf.filename:
                    matched, method = cand, MATCH_FILENAME_AND_SIZE
                    break

        if matched is None and use_fingerprint and mf.id in existing_fingerprints and is_fpcalc_available():
            target_fp = existing_fingerprints[mf.id]
            for cand in candidate_paths:
                try:
                    cand_fp = compute_fingerprint(cand)
                except FingerprintError:
                    continue
                if cand_fp.fingerprint_data == target_fp:
                    matched, method = cand, MATCH_FINGERPRINT
                    break

        if matched is not None:
            results.append(
                RelocationCandidate(
                    media_file_id=mf.id,
                    old_absolute_path=mf.absolute_path,
                    new_absolute_path=str(matched),
                    match_method=method,
                    confidence=CONFIDENCE_BY_METHOD[method],
                )
            )

    return results


def apply_relocations(
    db: Database, candidates: list[RelocationCandidate], *, user_confirmed: bool
) -> list[RelocationApplyResult]:
    """Schritt 3 (Aenderung): aktualisiert `absolute_path`/`directory`/
    `filename` der betroffenen MediaFile-Zeilen und setzt `is_missing`
    zurueck. Erfordert IMMER `user_confirmed=True` (Prinzip #6, §44).
    Protokollierung in ProcessingHistory erfolgt - analog zur Rename-
    Engine - in der aufrufenden API-Schicht, nicht hier."""
    if not user_confirmed:
        raise RelocationApplyNotConfirmedError(
            "Eine Pfad-Relokation darf nur nach expliziter Nutzerbestaetigung "
            "je Kandidat erfolgen (Prinzip #6, §44, §43)."
        )

    results: list[RelocationApplyResult] = []
    for candidate in candidates:
        new_path = Path(candidate.new_absolute_path)
        if not new_path.exists():
            results.append(
                RelocationApplyResult(
                    media_file_id=candidate.media_file_id, applied=False,
                    old_absolute_path=candidate.old_absolute_path,
                    new_absolute_path=candidate.new_absolute_path,
                    reason="Zieldatei existiert nicht (mehr) auf der Festplatte.",
                )
            )
            continue

        with db.session() as session:
            media_file = session.get(MediaFile, candidate.media_file_id)
            if media_file is None:
                results.append(
                    RelocationApplyResult(
                        media_file_id=candidate.media_file_id, applied=False,
                        old_absolute_path=candidate.old_absolute_path,
                        new_absolute_path=candidate.new_absolute_path,
                        reason="Mediendatei-Eintrag nicht (mehr) in der Datenbank gefunden.",
                    )
                )
                continue
            media_file.absolute_path = str(new_path)
            media_file.directory = str(new_path.parent)
            media_file.filename = new_path.name
            media_file.is_missing = False
            media_file.missing_since = None

        log.info(
            "Pfad-Relokation: %s -> %s (Methode: %s, Konfidenz %.2f)",
            candidate.old_absolute_path, candidate.new_absolute_path,
            candidate.match_method, candidate.confidence,
        )
        results.append(
            RelocationApplyResult(
                media_file_id=candidate.media_file_id, applied=True,
                old_absolute_path=candidate.old_absolute_path,
                new_absolute_path=candidate.new_absolute_path,
            )
        )

    return results


__all__ = [
    "CONFIDENCE_BY_METHOD",
    "MATCH_FILENAME_AND_SIZE",
    "MATCH_FINGERPRINT",
    "MATCH_HASH",
    "RelocationApplyNotConfirmedError",
    "RelocationApplyResult",
    "RelocationCandidate",
    "apply_relocations",
    "find_relocation_candidates",
]
