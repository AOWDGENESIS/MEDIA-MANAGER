"""Tests fuer das Export-Modul (§42: JSON/CSV/XML/M3U/M3U8)."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from genesis_core.db import Database
from genesis_core.db.models import Album, Artist, MediaFile, MediaKind, TechnicalMetadata, Track
from genesis_core.exporter import build_export_rows, to_csv, to_json, to_m3u, to_xml


def _seed(db: Database) -> int:
    with db.session() as session:
        artist = Artist(name="Artist X")
        session.add(artist)
        session.flush()
        album = Album(title="Album Y", artist_id=artist.id)
        session.add(album)
        session.flush()
        mf = MediaFile(
            absolute_path="/music/a.mp3", directory="/music", filename="a.mp3",
            extension=".mp3", kind=MediaKind.MUSIC, size_bytes=123,
            content_hash_sha256="abc123",
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id
        session.add(
            Track(
                media_file_id=media_file_id, title="Song Z", album_id=album.id,
                album_artist="Artist X", track_number=3, year=2020,
            )
        )
        session.add(TechnicalMetadata(media_file_id=media_file_id, duration_seconds=180.5))
    return media_file_id


def test_build_export_rows_returns_all_by_default(db: Database):
    _seed(db)
    rows = build_export_rows(db)
    assert len(rows) == 1
    assert rows[0].title == "Song Z"
    assert rows[0].artist == "Artist X"
    assert rows[0].album == "Album Y"
    assert rows[0].duration_seconds == 180.5


def test_build_export_rows_filters_by_ids(db: Database):
    media_file_id = _seed(db)
    assert build_export_rows(db, media_file_ids=[999999]) == []
    assert len(build_export_rows(db, media_file_ids=[media_file_id])) == 1


def test_to_json_round_trips(db: Database):
    _seed(db)
    rows = build_export_rows(db)
    parsed = json.loads(to_json(rows))
    assert parsed[0]["filename"] == "a.mp3"
    assert parsed[0]["title"] == "Song Z"


def test_to_csv_has_header_and_row(db: Database):
    _seed(db)
    rows = build_export_rows(db)
    content = to_csv(rows)
    lines = content.strip().splitlines()
    assert lines[0].startswith("media_file_id,")
    assert "a.mp3" in lines[1]


def test_to_xml_is_well_formed_and_contains_data(db: Database):
    _seed(db)
    rows = build_export_rows(db)
    content = to_xml(rows)
    root = ET.fromstring(content)
    assert root.tag == "genesis_media_export"
    media_el = root.find("media")
    assert media_el.find("filename").text == "a.mp3"
    assert media_el.find("title").text == "Song Z"


def test_to_m3u_extended_includes_extinf_and_path(db: Database):
    _seed(db)
    rows = build_export_rows(db)
    content = to_m3u(rows, extended=True)
    assert content.startswith("#EXTM3U")
    assert "#EXTINF:180,Artist X - Song Z" in content
    assert "/music/a.mp3" in content


def test_to_m3u_non_extended_only_paths(db: Database):
    _seed(db)
    rows = build_export_rows(db)
    content = to_m3u(rows, extended=False)
    assert "#EXTM3U" not in content
    assert content.strip() == "/music/a.mp3"


def test_export_empty_library_produces_valid_but_empty_output(db: Database):
    rows = build_export_rows(db)
    assert rows == []
    assert json.loads(to_json(rows)) == []
    assert to_csv(rows).strip().startswith("media_file_id,")
    root = ET.fromstring(to_xml(rows))
    assert list(root) == []
    assert to_m3u(rows) == "#EXTM3U\n"
