from pathlib import Path

from genesis_core.db import Database
from genesis_core.db.models import MediaFile
from genesis_core.scanner.scanner import scan_directories


def test_scan_finds_all_supported_test_files(db: Database, test_library_root: Path):
    result = scan_directories(db, [test_library_root])

    assert result.files_found >= 6  # 4 Musik + 1 Hoerbuch + 1 Video + 1 unknown
    assert result.files_new == result.files_found
    assert not result.errors

    with db.session() as session:
        from sqlalchemy import select

        count = session.execute(select(MediaFile)).scalars().all()
        assert len(count) == result.files_found


def test_scan_is_idempotent_and_read_only(db: Database, test_library_root: Path):
    """Zweiter Scan derselben, unveraenderten Dateien darf nichts als 'neu'
    oder 'geaendert' erkennen (Prinzip: Scan veraendert nie eine Datei, §6)."""
    scan_directories(db, [test_library_root])
    second = scan_directories(db, [test_library_root])

    assert second.files_new == 0
    assert second.files_changed == 0
    assert second.files_unchanged == second.files_found


def test_scan_detects_missing_file(db: Database, tmp_path: Path):

    from testdata_generator.generate import generate_test_library

    lib = tmp_path / "lib"
    lib.mkdir()
    paths = generate_test_library(lib)

    scan_directories(db, [lib])

    # Datei "verschwindet" (wir loeschen nur die TEST-Kopie, nie eine echte
    # Nutzerdatei - siehe SAFE TEST MODE).
    (paths["unknown_named_file"]).unlink()

    result = scan_directories(db, [lib])
    assert result.files_missing == 1

    with db.session() as session:
        from sqlalchemy import select

        mf = session.execute(
            select(MediaFile).where(
                MediaFile.absolute_path == str(paths["unknown_named_file"].resolve())
            )
        ).scalar_one()
        assert mf.is_missing is True


def test_scan_extracts_technical_metadata_for_video(db: Database, test_library_root: Path):
    scan_directories(db, [test_library_root])
    with db.session() as session:
        from sqlalchemy import select

        from genesis_core.db.models import TechnicalMetadata

        movie_file = session.execute(
            select(MediaFile).where(MediaFile.filename.like("Test Movie%"))
        ).scalar_one()
        tech = session.execute(
            select(TechnicalMetadata).where(TechnicalMetadata.media_file_id == movie_file.id)
        ).scalar_one()
        assert tech.video_codec is not None
        assert tech.resolution_width == 320
        assert tech.resolution_height == 240


def test_scan_skips_unsupported_directory_gracefully(db: Database, tmp_path: Path):
    missing_dir = tmp_path / "does_not_exist"
    result = scan_directories(db, [missing_dir])
    assert result.files_found == 0
    assert len(result.errors) == 1
