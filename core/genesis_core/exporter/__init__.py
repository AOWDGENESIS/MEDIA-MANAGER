"""Export-Modul (§42): JSON, CSV, XML sowie M3U/M3U8-Wiedergabelisten.

Reine LESEFUNKTION (Prinzip #4/#5) - exportiert nur bereits in der
Datenbank vorhandene Informationen in ein externes, interoperables
Dateiformat. Veraendert nie eine Mediendatei oder die Datenbank, braucht
daher KEINE Bestaetigung (im Unterschied zu allen aendernden Operationen).

Architektur: `build_export_rows()` sammelt die Daten aus der Datenbank in
ein einziges, formatneutrales `MediaExportRow`-Objekt pro Datei. Die
eigentlichen Formatierer (`to_json`, `to_csv`, `to_xml`, `to_m3u`) kennen
NIE die Datenbank selbst - sie sind reine, isoliert testbare String-
Funktionen auf Basis dieser neutralen Zwischenform (analog zu
`MediaSnapshot` in `genesis_core.duplicates`).

M3U/M3U8 (§42): beide Formate sind inhaltlich identisch (Zeile pro Pfad,
optional mit `#EXTINF`-Zusatzzeile); der einzige historische Unterschied
ist, dass M3U8 explizit UTF-8-Dateinamen/-Titel garantiert, waehrend M3U
urspruenglich die lokale Systemkodierung voraussetzte. Da GENESIS
durchgehend UTF-8 verwendet, erzeugt `to_m3u()` fuer beide Varianten
denselben Text - der Aufrufer (API-Schicht) entscheidet nur ueber die
Dateiendung/den gemeldeten media_type.
"""
from __future__ import annotations

import csv
import dataclasses
import io
import json
import xml.etree.ElementTree as ET

from sqlalchemy import select

from genesis_core.db import Database
from genesis_core.db.models import Album, MediaFile, TechnicalMetadata, Track


@dataclasses.dataclass
class MediaExportRow:
    media_file_id: int
    absolute_path: str
    filename: str
    extension: str
    kind: str
    size_bytes: int
    content_hash_sha256: str | None
    is_missing: bool
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    year: int | None = None
    duration_seconds: float | None = None


def build_export_rows(db: Database, media_file_ids: list[int] | None = None) -> list[MediaExportRow]:
    """Sammelt die Exportzeilen. `media_file_ids=None` exportiert die
    gesamte Bibliothek (alle MediaFile-Zeilen); eine uebergebene Liste
    beschraenkt den Export auf eine Auswahl (z.B. die aktuell gefilterte
    Ansicht in der UI oder eine manuell zusammengestellte Wiedergabeliste)."""
    with db.session() as session:
        stmt = select(MediaFile)
        if media_file_ids is not None:
            stmt = stmt.where(MediaFile.id.in_(media_file_ids))
        media_files = list(session.execute(stmt).scalars())

        rows: list[MediaExportRow] = []
        for mf in media_files:
            track = session.execute(
                select(Track).where(Track.media_file_id == mf.id)
            ).scalar_one_or_none()
            album_title = None
            if track is not None and track.album_id is not None:
                album = session.get(Album, track.album_id)
                album_title = album.title if album is not None else None
            technical = session.execute(
                select(TechnicalMetadata).where(TechnicalMetadata.media_file_id == mf.id)
            ).scalar_one_or_none()

            rows.append(
                MediaExportRow(
                    media_file_id=mf.id,
                    absolute_path=mf.absolute_path,
                    filename=mf.filename,
                    extension=mf.extension,
                    kind=mf.kind.value,
                    size_bytes=mf.size_bytes,
                    content_hash_sha256=mf.content_hash_sha256,
                    is_missing=mf.is_missing,
                    title=track.title if track else None,
                    artist=track.album_artist if track else None,
                    album=album_title,
                    track_number=track.track_number if track else None,
                    year=track.year if track else None,
                    duration_seconds=technical.duration_seconds if technical else None,
                )
            )
        return rows


def to_json(rows: list[MediaExportRow]) -> str:
    data = [dataclasses.asdict(r) for r in rows]
    return json.dumps(data, ensure_ascii=False, indent=2)


_CSV_FIELDS = [
    "media_file_id", "absolute_path", "filename", "extension", "kind",
    "size_bytes", "content_hash_sha256", "is_missing", "title", "artist",
    "album", "track_number", "year", "duration_seconds",
]


def to_csv(rows: list[MediaExportRow]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for r in rows:
        writer.writerow(dataclasses.asdict(r))
    return buffer.getvalue()


def to_xml(rows: list[MediaExportRow]) -> str:
    root = ET.Element("genesis_media_export")
    for r in rows:
        item = ET.SubElement(root, "media")
        for field_name, value in dataclasses.asdict(r).items():
            el = ET.SubElement(item, field_name)
            el.text = "" if value is None else str(value)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def to_m3u(rows: list[MediaExportRow], *, extended: bool = True) -> str:
    """Erzeugt eine M3U/M3U8-Wiedergabeliste (§42). `extended=True`
    schreibt zusaetzlich `#EXTINF`-Zeilen mit Dauer+Titel (verbreitetes
    "Extended M3U"-Format); `extended=False` erzeugt eine minimale Liste
    nur mit Pfaden (maximale Kompatibilitaet mit sehr einfachen Playern)."""
    lines = ["#EXTM3U"] if extended else []
    for r in rows:
        if extended:
            duration = int(r.duration_seconds) if r.duration_seconds else -1
            label = r.title or r.filename
            if r.artist:
                label = f"{r.artist} - {label}"
            lines.append(f"#EXTINF:{duration},{label}")
        lines.append(r.absolute_path)
    return "\n".join(lines) + "\n"


__all__ = [
    "MediaExportRow",
    "build_export_rows",
    "to_csv",
    "to_json",
    "to_m3u",
    "to_xml",
]
