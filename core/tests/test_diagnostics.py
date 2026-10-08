"""Tests fuer das Diagnostics-Modul (§38)."""
from __future__ import annotations

import sqlite3

from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, MediaKind, Track
from genesis_core.diagnostics import find_orphaned_rows, run_diagnostics


def _make_media_file(db: Database) -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path="/tmp/diag/song.mp3", directory="/tmp/diag",
            filename="song.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=10,
        )
        session.add(mf)
        session.flush()
        return mf.id


def _orphan_track_for(db: Database, media_file_id: int) -> None:
    """Erzeugt gezielt eine verwaiste Zeile (Track ohne zugehoerige
    MediaFile) - simuliert die Art Datenkorruption, die dieser Check
    entdecken soll (z.B. durch ein externes Werkzeug ausserhalb von
    GENESIS). Nutzt eine eigene rohe sqlite3-Verbindung mit deaktivierter
    Fremdschluesselpruefung, damit das normale, von GENESIS selbst niemals
    umgangene FK-Schutzschema (PRAGMA foreign_keys=ON) der Engine
    unberuehrt bleibt."""
    conn = sqlite3.connect(str(db.database_path))
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "DELETE FROM media_files WHERE id = ?", (media_file_id,)
        )
        conn.commit()
    finally:
        conn.close()


def test_run_diagnostics_returns_ok_on_clean_setup(db: Database, settings: Settings):
    report = run_diagnostics(db, settings)
    assert report.overall_status in ("ok", "warning")  # kein Medienordner konfiguriert -> warning ist ok
    ids = {c.check_id for c in report.checks}
    assert "database" in ids
    assert "orphaned_entries" in ids
    db_check = next(c for c in report.checks if c.check_id == "database")
    assert db_check.status == "ok"


def test_find_orphaned_rows_detects_corruption(db: Database):
    with db.session() as session:
        mf = MediaFile(
            absolute_path="/tmp/diag/orphan.mp3", directory="/tmp/diag",
            filename="orphan.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=10,
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id
        track = Track(media_file_id=media_file_id, title="Verwaister Track")
        session.add(track)

    assert find_orphaned_rows(db) == {}

    _orphan_track_for(db, media_file_id)

    orphans = find_orphaned_rows(db)
    assert "tracks" in orphans
    assert len(orphans["tracks"]) == 1


def test_diagnostics_reports_orphaned_rows_as_warning(db: Database, settings: Settings):
    with db.session() as session:
        mf = MediaFile(
            absolute_path="/tmp/diag/orphan2.mp3", directory="/tmp/diag",
            filename="orphan2.mp3", extension=".mp3", kind=MediaKind.MUSIC, size_bytes=10,
        )
        session.add(mf)
        session.flush()
        media_file_id = mf.id
        session.add(Track(media_file_id=media_file_id, title="x"))

    _orphan_track_for(db, media_file_id)

    report = run_diagnostics(db, settings)
    orphan_check = next(c for c in report.checks if c.check_id == "orphaned_entries")
    assert orphan_check.status == "warning"
    assert orphan_check.details["orphans_by_table"]["tracks"] == 1


def test_diagnostics_warns_on_missing_media_folder(db: Database, settings: Settings):
    settings.paths.media_folders = ["/this/path/does/not/exist/genesis"]
    report = run_diagnostics(db, settings)
    folder_check = next(c for c in report.checks if c.check_id == "media_folders")
    assert folder_check.status == "error"


def test_diagnostics_file_permissions_ok_for_writable_data_dir(db: Database, settings: Settings):
    report = run_diagnostics(db, settings)
    perm_check = next(c for c in report.checks if c.check_id == "file_permissions")
    assert perm_check.status == "ok"


def test_diagnostics_never_raises_even_with_bad_plugin_registry(db: Database, settings: Settings):
    class BrokenRegistry:
        def list_plugins(self):
            raise RuntimeError("boom")

    report = run_diagnostics(db, settings, plugin_registry=BrokenRegistry())
    plugin_check = next(c for c in report.checks if c.check_id == "plugins")
    assert plugin_check.status == "error"
    # Der Rest der Diagnose muss trotzdem vollstaendig durchlaufen.
    assert len(report.checks) >= 10
