"""KI-Metadaten-Engine (§25, ADR-0017).

Deckt "Erkennen -> Vorschlag -> Confidence" (`suggest_metadata`) sowie
"Aenderung" (`apply_suggestions`) der "Goldenen Prozesskette" ab - exakt
nach demselben Muster wie `metadata/engine.py` (Online-Provider) und
`audiobook/engine.py`/`video/engine.py` (dateibasierte Erkennung):

    Erkennen -> Analysieren -> Vorschlag -> Confidence -> Vorschau ->
    Benutzerfreigabe -> Aenderung -> Protokoll -> Rollback-Moeglichkeit

Wichtig (Prinzip #9/#16/#17): Jeder KI-Vorschlag ist IMMER nur ein
Vorschlag, bis `apply_suggestions(..., confirm=True)` explizit nach echter
Nutzerinteraktion aufgerufen wird. Gespeichert wird ausschliesslich in der
generischen `AIMetadata`-EAV-Tabelle (nicht in den eigentlichen Track-/
Movie-/Episode-Feldern) - §25 verlangt nur, dass KI-Ergebnisse MIT
"AI generated / Model / Model version / Timestamp / Confidence"
gespeichert werden, nicht, dass sie automatisch die kanonischen
Metadatenfelder ueberschreiben. Eine manuelle Uebernahme in echte Felder
bleibt dem bestehenden Tag-Editor vorbehalten (kein Vermischen der
Verantwortlichkeiten).
"""
from __future__ import annotations

import dataclasses
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from genesis_core.ai.base import AIProvider, AISuggestion
from genesis_core.db.models import (
    AIMetadata,
    Audiobook,
    Episode,
    MediaFile,
    Movie,
    Track,
)
from genesis_core.logutil import get_logger
from genesis_core.metadata.tag_reader import read_existing_tags

log = get_logger("AIEngine")

# §25: die vollstaendige, offene Liste moeglicher KI-Vorschlagsfelder.
# Welche Felder tatsaechlich einen Wert liefern, entscheidet das Modell
# selbst (leere/fehlende Felder werden nicht erfunden, Prinzip #16).
SUGGESTABLE_FIELDS: tuple[str, ...] = (
    "genre",
    "mood",
    "language",
    "instruments",
    "vocals",
    "topic",
    "description",
    "tags",
    "classification",
)


class AIApplyNotConfirmedError(PermissionError):
    pass


@dataclasses.dataclass
class AIMetadataEntry:
    id: int
    field_name: str
    field_value: str
    is_ai_generated: bool
    model_name: str
    model_version: str | None
    confidence: float | None
    prompt: str | None
    created_at: dt.datetime
    accepted_by_user: bool


def build_context(db: Session, media_file: MediaFile) -> str:
    """Baut einen reinen Text-Kontext aus bereits bekannten Informationen
    (Dateiname, vorhandene DB-Metadaten, eingebettete Tags) - NIE aus
    erfundenen/vermuteten Angaben (Prinzip #16). Dieser Kontext ist der
    einzige Input fuer das lokale Modell."""
    lines = [f"Dateiname: {media_file.filename}", f"Medienart: {media_file.kind.value}"]

    track = db.execute(
        select(Track).where(Track.media_file_id == media_file.id)
    ).scalar_one_or_none()
    if track is not None:
        if track.title:
            lines.append(f"Titel: {track.title}")
        if track.composer:
            lines.append(f"Komponist/Interpret-Zusatz: {track.composer}")
        if track.comment:
            lines.append(f"Kommentar: {track.comment}")
        if track.year:
            lines.append(f"Jahr: {track.year}")

    movie = db.execute(
        select(Movie).where(Movie.media_file_id == media_file.id)
    ).scalar_one_or_none()
    if movie is not None:
        if movie.title:
            lines.append(f"Filmtitel: {movie.title}")
        if movie.genre:
            lines.append(f"Bereits bekanntes Genre: {movie.genre}")
        if movie.description:
            lines.append(f"Bereits bekannte Beschreibung: {movie.description}")

    episode = db.execute(
        select(Episode).where(Episode.media_file_id == media_file.id)
    ).scalar_one_or_none()
    if episode is not None:
        if episode.title:
            lines.append(f"Episodentitel: {episode.title}")
        if episode.series:
            lines.append(f"Serie: {episode.series.name}")

    audiobook = db.execute(
        select(Audiobook).where(Audiobook.media_file_id == media_file.id)
    ).scalar_one_or_none()
    if audiobook is not None:
        if audiobook.title:
            lines.append(f"Hoerbuchtitel: {audiobook.title}")
        if audiobook.description:
            lines.append(f"Bereits bekannte Beschreibung: {audiobook.description}")

    # Falls noch keinerlei strukturierte Metadaten existieren, zusaetzlich
    # die rohen, eingebetteten Tags der Datei heranziehen (rein lesend).
    if track is None and movie is None and episode is None and audiobook is None:
        tags = read_existing_tags(media_file.absolute_path)
        if tags.has_any_tag:
            if tags.title:
                lines.append(f"Tag-Titel: {tags.title}")
            if tags.artist:
                lines.append(f"Tag-Interpret: {tags.artist}")
            if tags.genre:
                lines.append(f"Tag-Genre: {tags.genre}")

    return "\n".join(lines)


def suggest_metadata(
    db: Session,
    media_file_id: int,
    provider: AIProvider,
    fields: list[str] | None = None,
) -> list[AISuggestion]:
    """Reine Vorschau - KEIN Seiteneffekt, nichts wird gespeichert.

    Gibt eine leere Liste zurueck (statt eines Fehlers), wenn die KI
    deaktiviert ist (NullAIProvider) oder der Provider nicht erreichbar
    ist - "keine KI verfuegbar" ist ein normaler Zustand, kein Absturz.
    """
    media_file = db.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden")

    requested_fields = fields if fields else list(SUGGESTABLE_FIELDS)
    unknown = set(requested_fields) - set(SUGGESTABLE_FIELDS)
    if unknown:
        raise ValueError(f"Unbekannte KI-Felder: {sorted(unknown)}")

    if not provider.is_available():
        log.info("KI-Provider %s aktuell nicht erreichbar - keine Vorschlaege", provider.name)
        return []

    context = build_context(db, media_file)
    return provider.suggest_text_fields(context, requested_fields)


def apply_suggestions(
    db: Session,
    media_file_id: int,
    accepted: list[AISuggestion],
    *,
    confirm: bool,
) -> list[AIMetadata]:
    """Speichert vom Nutzer akzeptierte KI-Vorschlaege (Prinzip #17/§44).

    Ein erneutes Apply desselben Feldes+Modells ERSETZT den vorherigen
    Eintrag (kein unbegrenztes Anwachsen bei wiederholtem Reindex/Retry),
    analog zum Dedup-Muster aus Phase 4/5 (PersonRole).
    """
    if not confirm:
        raise AIApplyNotConfirmedError(
            "KI-Metadatenuebernahme erfordert eine explizite Bestaetigung (confirm=True)."
        )
    media_file = db.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden")

    saved: list[AIMetadata] = []
    for suggestion in accepted:
        existing = db.execute(
            select(AIMetadata).where(
                AIMetadata.media_file_id == media_file_id,
                AIMetadata.field_name == suggestion.field_name,
                AIMetadata.model_name == suggestion.model_name,
            )
        ).scalar_one_or_none()
        if existing is not None:
            db.delete(existing)
            db.flush()

        entry = AIMetadata(
            media_file_id=media_file_id,
            field_name=suggestion.field_name,
            field_value=suggestion.field_value,
            is_ai_generated=True,
            model_name=suggestion.model_name,
            model_version=suggestion.model_version,
            confidence=suggestion.confidence,
            prompt=suggestion.prompt,
            accepted_by_user=True,
        )
        db.add(entry)
        saved.append(entry)

    db.commit()
    for entry in saved:
        db.refresh(entry)
    log.info(
        "KI-Metadaten uebernommen fuer MediaFile %s: %s",
        media_file_id,
        [s.field_name for s in accepted],
    )
    return saved


def list_ai_metadata(db: Session, media_file_id: int) -> list[AIMetadata]:
    """Alle bisher bestaetigten KI-Metadaten-Eintraege eines Mediums
    (reine Lesefunktion, z.B. fuer die "KI-Analyse"-Detailansicht)."""
    return list(
        db.execute(
            select(AIMetadata)
            .where(AIMetadata.media_file_id == media_file_id)
            .order_by(AIMetadata.field_name)
        ).scalars()
    )
