from genesis_core.db import Database
from genesis_core.db.models import MediaFile, MediaKind


def test_database_creates_all_tables(db: Database):

    with db.engine.connect() as conn:
        from sqlalchemy import inspect

        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

    expected_minimum = {
        "media_files", "artists", "albums", "tracks", "genres", "persons",
        "audiobooks", "series", "episodes", "movies", "podcasts",
        "podcast_episodes", "chapters", "sources", "providers", "tags",
        "artwork", "fingerprints", "loudness", "technical_metadata",
        "ai_metadata", "voice_profiles", "processing_jobs",
        "processing_history", "backups", "licenses", "settings",
    }
    missing = expected_minimum - tables
    assert not missing, f"Fehlende Tabellen (Originalauftrag §7): {missing}"


def test_media_file_path_is_authoritative(db: Database):
    """Prinzip #14/#15: physischer Pfad ist Pflicht und eindeutig."""
    with db.session() as session:
        mf = MediaFile(
            absolute_path="/tmp/test/song.mp3",
            directory="/tmp/test",
            filename="song.mp3",
            extension=".mp3",
            kind=MediaKind.MUSIC,
            size_bytes=1234,
        )
        session.add(mf)

    with db.session() as session:
        from sqlalchemy import select

        result = session.execute(
            select(MediaFile).where(MediaFile.absolute_path == "/tmp/test/song.mp3")
        ).scalar_one()
        assert result.filename == "song.mp3"
        assert result.is_missing is False
