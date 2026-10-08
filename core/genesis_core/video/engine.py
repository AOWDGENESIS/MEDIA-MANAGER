"""Film-/Serien-Engine (§24) - Episode-Erkennung + Metadaten-Übernahme.

Ablauf (Erkennen -> Vorschlag -> Confidence -> Vorschau -> Benutzerfreigabe
-> Änderung -> Protokoll, Prinzip #4/#5/#17), analog zur Hörbuch-Engine
(`genesis_core.audiobook.engine`, ADR-0015):

1. **Film vs. Serie-Episode unterscheiden** (`detect_episode`): Der Scanner
   klassifiziert ALLE Video-Dateien zunaechst konservativ als
   `MediaKind.MOVIE` (siehe `scanner/classify.py`). Diese Funktion liest
   eingebettete TV-Show-Tags (`tvsh`/`tvsn`/`tves` bzw. Matroska-Aequivalente)
   UND wertet - falls keine Tags vorhanden sind - den Dateinamen/
   Verzeichnispfad nach gaengigen Mustern aus (`S01E02`, `1x02`,
   `Serie/Staffel 01/...`). JEDE Quelle wird transparent gekennzeichnet
   (`"tag"` vs. `"filename_pattern"` vs. `"directory_name"`) - nichts wird
   stillschweigend vermischt (Prinzip #16). Reine Analyse, schreibt nichts.
2. **Übernahme ausschliesslich bestätigungspflichtig**
   (`apply_movie_metadata`/`apply_episode_metadata`,
   `VideoApplyNotConfirmedError` bei `user_confirmed=False`) - setzt dabei
   auch `MediaFile.kind` auf `MOVIE` bzw. `EPISODE` (die eigentliche Film-/
   Serien-Unterscheidung wird also erst durch eine EXPLIZITE
   Nutzerbestätigung wirksam, nicht automatisch beim Scan).
3. **Regisseur/Schauspieler** werden ueber das bereits bestehende, bisher
   ungenutzte `Person`/`PersonRole`-Wissensgraph-Schema (§63) abgebildet -
   ein erneutes Anwenden ERSETZT die bisherige Rollen-Zuordnung atomar
   (`_sync_person_roles`), statt Duplikate anzuhaeufen.

Es gibt bewusst KEINEN Online-Provider (TMDb/IMDb/OMDb o.ä. sind
Download/Import-Adapter, Phase 8) - alle Werte stammen ausschliesslich aus
bereits in der Datei eingebetteten Tags bzw. aus dem Dateipfad selbst.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from sqlalchemy import select

from genesis_core.db.models import (
    Episode,
    MediaFile,
    MediaKind,
    Movie,
    Person,
    PersonRole,
    PersonRoleType,
    Series,
)
from genesis_core.logutil import get_logger
from genesis_core.video.tags import VideoTagSnapshot, read_video_tags

log = get_logger("VideoEngine")

_SXXEXX_RE = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,3})")
_NXN_RE = re.compile(r"(?<!\d)(\d{1,2})x(\d{2,3})(?!\d)")
_SEASON_DIR_RE = re.compile(r"(?:season|staffel)\s*0*(\d{1,2})", re.IGNORECASE)
_TITLE_BEFORE_SXXEXX_RE = re.compile(r"^(.*?)\s*-\s*[Ss]\d{1,2}[Ee]\d{1,3}")


class VideoApplyNotConfirmedError(PermissionError):
    """Analog zu `AudiobookApplyNotConfirmedError` - harte Absicherung von
    Prinzip #17/§44 direkt im Code."""


@dataclasses.dataclass(frozen=True)
class EpisodeDetectionResult:
    is_likely_episode: bool
    confidence: float
    series_name: str | None
    series_source: str | None  # "tag" | "filename_pattern" | "directory_name"
    season_number: int | None
    season_source: str | None  # "tag" | "filename_pattern"
    episode_number: int | None
    episode_source: str | None  # "tag" | "filename_pattern"
    title: str | None
    title_source: str | None  # "tag" | "filename"
    year: int | None
    description: str | None
    director_names: list[str]
    actor_names: list[str]


def _season_episode_from_path(absolute_path: str) -> tuple[int, int] | None:
    combined = f"{Path(absolute_path).stem} {Path(absolute_path).parent.name}"
    match = _SXXEXX_RE.search(combined)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = _NXN_RE.search(combined)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def _series_name_from_path(absolute_path: str) -> tuple[str, str] | None:
    path = Path(absolute_path)
    match = _TITLE_BEFORE_SXXEXX_RE.match(path.stem)
    if match and match.group(1).strip():
        return match.group(1).strip(), "filename_pattern"
    parent = path.parent
    if _SEASON_DIR_RE.search(parent.name) and parent.parent.name:
        return parent.parent.name, "directory_name"
    return None


def detect_episode(absolute_path: str) -> EpisodeDetectionResult:
    """Reine Analyse (Prinzip #4/#5) - liest Tags + wertet den Dateipfad
    aus, schreibt NICHTS."""
    tags = read_video_tags(absolute_path)

    season = tags.season_number
    season_source = "tag" if season is not None else None
    episode = tags.episode_number
    episode_source = "tag" if episode is not None else None

    if season is None or episode is None:
        parsed = _season_episode_from_path(absolute_path)
        if parsed:
            parsed_season, parsed_episode = parsed
            if season is None:
                season = parsed_season
                season_source = "filename_pattern"
            if episode is None:
                episode = parsed_episode
                episode_source = "filename_pattern"

    series_name = tags.series
    series_source = "tag" if series_name else None
    if series_name is None:
        candidate = _series_name_from_path(absolute_path)
        if candidate:
            series_name, series_source = candidate

    title = tags.title
    title_source = "tag" if title else None
    if title is None and series_source == "filename_pattern":
        # Bei "Serie - S01E02 - Folgentitel" steht der Folgentitel nach dem
        # SxxExx-Muster - mechanisch extrahierbar, keine Erfindung.
        stem = Path(absolute_path).stem
        remainder = _TITLE_BEFORE_SXXEXX_RE.sub("", stem, count=1).lstrip(" -")
        if remainder:
            title = remainder
            title_source = "filename"

    is_likely_episode = season is not None or episode is not None or bool(tags.series)
    if season_source == "tag" or episode_source == "tag":
        confidence = 0.9
    elif season_source == "filename_pattern" or episode_source == "filename_pattern":
        confidence = 0.6
    elif series_source is not None:
        confidence = 0.4
    else:
        confidence = 0.0

    return EpisodeDetectionResult(
        is_likely_episode=is_likely_episode,
        confidence=confidence,
        series_name=series_name,
        series_source=series_source,
        season_number=season,
        season_source=season_source,
        episode_number=episode,
        episode_source=episode_source,
        title=title,
        title_source=title_source,
        year=tags.year,
        description=tags.description,
        director_names=list(tags.director_names),
        actor_names=list(tags.actor_names),
    )


def apply_movie_metadata(
    session, media_file_id: int, tags: VideoTagSnapshot, *, user_confirmed: bool,
) -> Movie:
    if not user_confirmed:
        raise VideoApplyNotConfirmedError(
            "Film-Metadaten duerfen nur nach expliziter Nutzerbestaetigung "
            "uebernommen werden (Prinzip #17, §44)."
        )
    media_file = session.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden.")

    movie = session.execute(
        select(Movie).where(Movie.media_file_id == media_file_id)
    ).scalar_one_or_none()
    if movie is None:
        movie = Movie(media_file_id=media_file_id)
        session.add(movie)
        session.flush()

    if tags.title:
        movie.title = tags.title
    if tags.year is not None:
        movie.year = tags.year
    if tags.genre:
        movie.genre = tags.genre
    if tags.description:
        movie.description = tags.description
    # Laufzeit: bereits bekannter technischer Messwert (TechnicalMetadata),
    # keine Schaetzung - wird nur uebernommen, wenn vorhanden.
    if media_file.technical is not None and media_file.technical.duration_seconds:
        movie.runtime_seconds = media_file.technical.duration_seconds

    media_file.kind = MediaKind.MOVIE
    session.flush()

    _sync_person_roles(session, movie_id=movie.id, role=PersonRoleType.DIRECTOR,
                        names=tags.director_names)
    _sync_person_roles(session, movie_id=movie.id, role=PersonRoleType.ACTOR,
                        names=tags.actor_names)

    log.info("Film-Metadaten uebernommen fuer MediaFile %d: %s", media_file_id, movie.title)
    return movie


def apply_episode_metadata(
    session, media_file_id: int, result: EpisodeDetectionResult, *, user_confirmed: bool,
) -> Episode:
    if not user_confirmed:
        raise VideoApplyNotConfirmedError(
            "Episoden-Metadaten duerfen nur nach expliziter Nutzerbestaetigung "
            "uebernommen werden (Prinzip #17, §44)."
        )
    media_file = session.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden.")

    series_obj = _get_or_create_series(session, result.series_name)

    episode = session.execute(
        select(Episode).where(Episode.media_file_id == media_file_id)
    ).scalar_one_or_none()
    if episode is None:
        episode = Episode(media_file_id=media_file_id)
        session.add(episode)
        session.flush()

    if series_obj is not None:
        episode.series_id = series_obj.id
    if result.season_number is not None:
        episode.season_number = result.season_number
    if result.episode_number is not None:
        episode.episode_number = result.episode_number
    if result.title:
        episode.title = result.title
    if result.year is not None:
        episode.year = result.year
    if result.description:
        episode.description = result.description

    media_file.kind = MediaKind.EPISODE
    session.flush()

    _sync_person_roles(session, episode_id=episode.id, role=PersonRoleType.DIRECTOR,
                        names=result.director_names)
    _sync_person_roles(session, episode_id=episode.id, role=PersonRoleType.ACTOR,
                        names=result.actor_names)

    log.info(
        "Episoden-Metadaten uebernommen fuer MediaFile %d: %s S%sE%s",
        media_file_id, series_obj.name if series_obj else "?",
        result.season_number, result.episode_number,
    )
    return episode


def _get_or_create_series(session, name: str | None) -> Series | None:
    if not name:
        return None
    series = session.execute(select(Series).where(Series.name == name)).scalar_one_or_none()
    if series is None:
        series = Series(name=name)
        session.add(series)
        session.flush()
    return series


def _get_or_create_person(session, name: str) -> Person:
    person = session.execute(select(Person).where(Person.name == name)).scalar_one_or_none()
    if person is None:
        person = Person(name=name)
        session.add(person)
        session.flush()
    return person


def _sync_person_roles(
    session, *, role: PersonRoleType, names: list[str],
    movie_id: int | None = None, episode_id: int | None = None,
) -> None:
    """Ersetzt die bisherige Rollen-Zuordnung ATOMAR (alte Zeilen loeschen,
    neue anlegen) - ein erneutes Anwenden haeuft keine Duplikate an."""
    query = select(PersonRole).where(PersonRole.role == role)
    if movie_id is not None:
        query = query.where(PersonRole.movie_id == movie_id)
    if episode_id is not None:
        query = query.where(PersonRole.episode_id == episode_id)
    for row in session.execute(query).scalars().all():
        session.delete(row)
    session.flush()

    for name in names:
        person = _get_or_create_person(session, name)
        session.add(
            PersonRole(person_id=person.id, role=role, movie_id=movie_id, episode_id=episode_id)
        )
    session.flush()
