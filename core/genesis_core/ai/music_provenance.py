"""KI-Musik-Provenienz (§27, ADR-0017).

Im Unterschied zu §25 (KI erzeugt Metadaten-VORSCHLAEGE) geht es hier um
das GEGENTEIL: der Nutzer erklaert, dass eine Mediendatei selbst (teilweise)
KI-generierte Musik IST, und traegt die ihm bekannte Herkunft ein. GENESIS
kann KI-Urheberschaft einer Audiodatei nicht selbst zuverlaessig feststellen
(das waere eine unbelegte Tatsachenbehauptung, Prinzip #16) - daher ist
dieser gesamte Fluss AUSSCHLIESSLICH eine manuelle, bestaetigungspflichtige
Nutzerangabe, niemals ein KI-Vorschlag.

Status-Werte exakt nach Spezifikation: AI Generated / Human Generated /
Hybrid / Unknown (`AIStatus`). Wird eine Datei als AI_GENERATED oder HYBRID
deklariert, wechselt `MediaFile.kind` zu `AI_MUSIC` (zeigt sie in der
eigenen Navigationskategorie "KI-Musik" an) - HUMAN_GENERATED/UNKNOWN lassen
die bestehende Klassifikation unangetastet.
"""
from __future__ import annotations

import dataclasses
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from genesis_core.db.models import (
    AIStatus,
    MediaFile,
    MediaKind,
    Person,
    PersonRole,
    PersonRoleType,
    Track,
)
from genesis_core.logutil import get_logger

log = get_logger("AIMusicProvenance")


class AIMusicApplyNotConfirmedError(PermissionError):
    pass


@dataclasses.dataclass
class AIMusicProvenanceInput:
    status: AIStatus
    source: str | None = None
    model: str | None = None
    prompt: str | None = None
    creation_date: dt.datetime | None = None
    instrumental: bool | None = None
    style: str | None = None
    mood: str | None = None
    owner: str | None = None
    artist_name: str | None = None


def _get_or_create_track(db: Session, media_file: MediaFile) -> Track:
    track = db.execute(
        select(Track).where(Track.media_file_id == media_file.id)
    ).scalar_one_or_none()
    if track is not None:
        return track
    track = Track(media_file_id=media_file.id)
    db.add(track)
    db.flush()
    return track


def _get_or_create_person(db: Session, name: str) -> Person:
    person = db.execute(select(Person).where(Person.name == name)).scalar_one_or_none()
    if person is not None:
        return person
    person = Person(name=name)
    db.add(person)
    db.flush()
    return person


def apply_ai_music_provenance(
    db: Session,
    media_file_id: int,
    data: AIMusicProvenanceInput,
    *,
    confirm: bool,
) -> Track:
    """Speichert die vom Nutzer erklaerte KI-Musik-Herkunft (§27).

    Bestaetigungspflichtig wie jede Aenderung (Prinzip #17/§44) - auch
    wenn der Nutzer selbst der "Provider" der Information ist, bleibt die
    Vorschau-vor-Uebernahme-Regel bestehen (Konsistenz mit allen anderen
    Apply-Fluessen des Projekts).
    """
    if not confirm:
        raise AIMusicApplyNotConfirmedError(
            "KI-Musik-Angaben erfordern eine explizite Bestaetigung (confirm=True)."
        )
    media_file = db.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden")

    track = _get_or_create_track(db, media_file)
    track.ai_status = data.status
    track.ai_source = data.source
    track.ai_model = data.model
    track.ai_prompt = data.prompt
    track.ai_creation_date = data.creation_date
    track.ai_instrumental = data.instrumental
    track.ai_style = data.style
    track.ai_mood = data.mood
    track.ai_owner = data.owner

    if data.artist_name:
        person = _get_or_create_person(db, data.artist_name)
        existing_role = db.execute(
            select(PersonRole).where(
                PersonRole.track_id == track.id,
                PersonRole.role == PersonRoleType.ARTIST,
                PersonRole.person_id == person.id,
            )
        ).scalar_one_or_none()
        if existing_role is None:
            db.add(PersonRole(person_id=person.id, role=PersonRoleType.ARTIST, track_id=track.id))

    if data.status in (AIStatus.AI_GENERATED, AIStatus.HYBRID):
        media_file.kind = MediaKind.AI_MUSIC

    db.commit()
    db.refresh(track)
    log.info(
        "KI-Musik-Herkunft gespeichert fuer MediaFile %s: status=%s",
        media_file_id,
        data.status.value,
    )
    return track


def get_ai_music_provenance(db: Session, media_file_id: int) -> Track | None:
    return db.execute(
        select(Track).where(Track.media_file_id == media_file_id)
    ).scalar_one_or_none()


def artist_names_for_track(db: Session, track_id: int) -> list[str]:
    roles = db.execute(
        select(PersonRole).where(
            PersonRole.track_id == track_id, PersonRole.role == PersonRoleType.ARTIST
        )
    ).scalars()
    names: list[str] = []
    for role in roles:
        person = db.get(Person, role.person_id)
        if person is not None:
            names.append(person.name)
    return names
