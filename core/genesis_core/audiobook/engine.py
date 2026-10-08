"""Hörbuch-Engine (§23) - Metadaten-Übernahme + Kapitel-Verwaltung.

Drei getrennte, aber zusammengehörige Verantwortlichkeiten:

1. **Metadaten-Übernahme** (`apply_audiobook_tags`): übernimmt bereits in
   der Datei eingebettete Tags (siehe `audiobook/tags.py`) in die
   `Audiobook`-Tabelle. Anders als die MusicBrainz-basierte
   `MetadataEngine` gibt es (noch) KEINEN Online-Hörbuch-Provider (Audible/
   Google Books o.ä. sind Download/Import-Adapter, Phase 8) - diese Engine
   arbeitet daher bewusst NUR mit bereits vorhandenen Datei-Tags. Erfordert
   trotzdem `user_confirmed=True` (Prinzip #17/§44), auch wenn die Daten
   "nur" aus der Datei selbst stammen - Konsistenz mit dem projektweiten
   Sicherheitsmodell (jede Änderung braucht Bestätigung).

2. **Kapitel-Erkennung** (`detect_chapters`): liest bereits in der Datei
   eingebettete Kapitelmarken (MP4-Chapters/ID3-CHAP, via ffprobe
   `-show_chapters`) - reine Analyse, erfindet nichts.

3. **Kapitel-Erzeugung** (`generate_fixed_interval_chapters`): §23 nennt
   "Kapitel erzeugen" als OPTIONALES Feature. Eine inhaltlich sinnvolle
   Erzeugung (z.B. Stille-Erkennung an Kapitelgrenzen) wäre eine eigene
   DSP-Analyse - bewusst zurückgestellt (analog ADR-0013/ADR-0014). Diese
   Version erzeugt stattdessen GLEICHMÄSSIGE Intervall-Marken (z.B. alle 10
   Minuten) - ehrlich benannt ("Kapitel 1", "Kapitel 2", ...), NICHT als
   inhaltlich sinnvolle Kapitelgrenzen ausgegeben.
"""
from __future__ import annotations

import csv
import dataclasses
import io
import json
import math

from sqlalchemy import select

from genesis_core.audiobook.tags import AudiobookTagSnapshot
from genesis_core.db.models import Audiobook, Chapter, MediaFile, Series
from genesis_core.logutil import get_logger
from genesis_core.scanner.ffprobe_util import probe_file

log = get_logger("AudiobookEngine")


class AudiobookApplyNotConfirmedError(PermissionError):
    """Analog zu `MetadataApplyNotConfirmedError` - harte Absicherung von
    Prinzip #17/§44 direkt im Code."""


class ChapterDetectionError(RuntimeError):
    """Wird geworfen, wenn ffprobe fehlt oder die Datei nicht lesbar ist."""


@dataclasses.dataclass(frozen=True)
class ChapterCandidate:
    index: int
    title: str | None
    start_seconds: float
    end_seconds: float | None


def apply_audiobook_tags(
    session, media_file_id: int, tags: AudiobookTagSnapshot, *, user_confirmed: bool,
) -> Audiobook:
    """Übernimmt gelesene Tags in die `Audiobook`-Tabelle. Erfordert IMMER
    `user_confirmed=True` - der Aufrufer darf dies nur nach echter
    Nutzerbestätigung setzen (Prinzip #17/§44)."""
    if not user_confirmed:
        raise AudiobookApplyNotConfirmedError(
            "Hörbuch-Metadaten dürfen nur nach expliziter Nutzerbestätigung "
            "übernommen werden (Prinzip #17, §44)."
        )

    media_file = session.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden.")

    series_obj = _get_or_create_series(session, tags.series)

    audiobook = session.execute(
        select(Audiobook).where(Audiobook.media_file_id == media_file_id)
    ).scalar_one_or_none()
    if audiobook is None:
        audiobook = Audiobook(media_file_id=media_file_id)
        session.add(audiobook)

    if tags.title:
        audiobook.title = tags.title
    if tags.author:
        audiobook.author = tags.author
    if tags.narrator:
        audiobook.narrator = tags.narrator
    if tags.publisher:
        audiobook.publisher = tags.publisher
    if series_obj is not None:
        audiobook.series_id = series_obj.id
    if tags.volume_number is not None:
        audiobook.volume_number = tags.volume_number
    if tags.year is not None:
        audiobook.year = tags.year
    if tags.language:
        audiobook.language = tags.language
    if tags.description:
        audiobook.description = tags.description

    session.flush()
    log.info(
        "Hörbuch-Tags übernommen für MediaFile %d: %s - %s",
        media_file_id, audiobook.author, audiobook.title,
    )
    return audiobook


def _get_or_create_series(session, name: str | None) -> Series | None:
    if not name:
        return None
    series = session.execute(select(Series).where(Series.name == name)).scalar_one_or_none()
    if series is None:
        series = Series(name=name)
        session.add(series)
        session.flush()
    return series


def detect_chapters(absolute_path: str) -> list[ChapterCandidate]:
    """Liest bereits in der Datei eingebettete Kapitelmarken (ffprobe
    `-show_chapters`) - reine Analyse, erzeugt/verändert nichts."""
    raw = probe_file(absolute_path)
    if raw is None:
        raise ChapterDetectionError(
            "Kapitel konnten nicht gelesen werden - ffprobe ist nicht verfügbar oder "
            "die Datei konnte nicht analysiert werden."
        )
    raw_chapters = raw.get("chapters", []) or []
    candidates: list[ChapterCandidate] = []
    for i, ch in enumerate(raw_chapters):
        start = float(ch.get("start_time", 0.0))
        end_raw = ch.get("end_time")
        end = float(end_raw) if end_raw is not None else None
        title = None
        tags = ch.get("tags") or {}
        if isinstance(tags, dict):
            title = tags.get("title")
        candidates.append(ChapterCandidate(index=i, title=title, start_seconds=start, end_seconds=end))
    return candidates


def generate_fixed_interval_chapters(
    duration_seconds: float, interval_minutes: float,
) -> list[ChapterCandidate]:
    """Erzeugt GLEICHMÄSSIGE Intervall-Kapitelmarken - KEINE inhaltlich
    sinnvolle Kapitelerkennung (siehe Moduldocstring). `duration_seconds`
    muss bereits bekannt sein (z.B. aus `TechnicalMetadata`)."""
    if duration_seconds <= 0:
        raise ValueError("Dauer muss größer als 0 sein.")
    if interval_minutes <= 0:
        raise ValueError("Intervall muss größer als 0 sein.")

    interval_seconds = interval_minutes * 60.0
    count = max(1, math.ceil(duration_seconds / interval_seconds))
    candidates: list[ChapterCandidate] = []
    for i in range(count):
        start = i * interval_seconds
        end = min((i + 1) * interval_seconds, duration_seconds)
        candidates.append(
            ChapterCandidate(index=i, title=f"Kapitel {i + 1}", start_seconds=start, end_seconds=end)
        )
    return candidates


def replace_chapters(session, media_file_id: int, candidates: list[ChapterCandidate]) -> list[Chapter]:
    """Ersetzt ALLE bestehenden Kapitel einer Datei durch die neue Liste
    (atomar, keine Teilmenge stehen lassen) - erfordert vom Aufrufer bereits
    eine Nutzerbestätigung (siehe API-Schicht, `confirm=True`)."""
    existing = session.execute(
        select(Chapter).where(Chapter.media_file_id == media_file_id)
    ).scalars().all()
    for row in existing:
        session.delete(row)
    session.flush()

    rows: list[Chapter] = []
    for candidate in candidates:
        row = Chapter(
            media_file_id=media_file_id,
            index=candidate.index,
            title=candidate.title,
            start_ms=int(candidate.start_seconds * 1000),
            end_ms=int(candidate.end_seconds * 1000) if candidate.end_seconds is not None else None,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def export_chapters_json(chapters: list[Chapter]) -> str:
    data = [
        {
            "index": c.index,
            "title": c.title,
            "start_ms": c.start_ms,
            "end_ms": c.end_ms,
        }
        for c in chapters
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)


def export_chapters_csv(chapters: list[Chapter]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["index", "title", "start_ms", "end_ms"])
    for c in chapters:
        writer.writerow([c.index, c.title or "", c.start_ms, c.end_ms if c.end_ms is not None else ""])
    return buffer.getvalue()
