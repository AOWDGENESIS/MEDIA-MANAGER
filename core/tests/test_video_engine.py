"""Tests für die Film-/Serien-Engine (§24, ADR-0016)."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from genesis_core.db import Database
from genesis_core.db.models import (
    Episode,
    MediaFile,
    MediaKind,
    Movie,
    PersonRole,
    PersonRoleType,
    Series,
)
from genesis_core.video import (
    VideoApplyNotConfirmedError,
    VideoTagSnapshot,
    apply_episode_metadata,
    apply_movie_metadata,
    detect_episode,
    read_video_tags,
)


def _make_media_file(db: Database, absolute_path: str, kind: MediaKind = MediaKind.MOVIE) -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path=absolute_path,
            directory=str(Path(absolute_path).parent),
            filename=Path(absolute_path).name,
            extension=Path(absolute_path).suffix.lower(),
            kind=kind,
            size_bytes=1234,
        )
        session.add(mf)
        session.flush()
        return mf.id


# --- read_video_tags / detect_episode (reine Analyse) ------------------------


def test_read_video_tags_missing_file_returns_empty_snapshot():
    snap = read_video_tags("/no/such/file.mp4")
    assert snap.has_any_tag is False


def test_detect_episode_recognizes_tagged_tv_show(test_library_root: Path):
    path = test_library_root / "Series" / "Test Series" / "Season 01" / "Test Series - Pilot.mp4"
    result = detect_episode(str(path))
    assert result.is_likely_episode is True
    assert result.confidence == pytest.approx(0.9)
    assert result.series_name == "Test Series"
    assert result.series_source == "tag"
    assert result.season_number == 1
    assert result.season_source == "tag"
    assert result.episode_number == 1
    assert result.title == "Pilot"
    assert result.actor_names == ["Test Actor One"]


def test_detect_episode_falls_back_to_filename_pattern(test_library_root: Path):
    path = (
        test_library_root / "Series" / "Test Series" / "Season 01"
        / "Test Series - S01E02 - Second Episode.mp4"
    )
    result = detect_episode(str(path))
    assert result.is_likely_episode is True
    assert result.confidence == pytest.approx(0.6)
    assert result.series_name == "Test Series"
    assert result.series_source == "filename_pattern"
    assert result.season_number == 1
    assert result.season_source == "filename_pattern"
    assert result.episode_number == 2
    assert result.episode_source == "filename_pattern"
    assert result.title == "Second Episode"
    assert result.title_source == "filename"


def test_detect_episode_plain_movie_is_not_an_episode(test_library_root: Path):
    path = test_library_root / "Movies" / "Test Movie (2026).mp4"
    result = detect_episode(str(path))
    assert result.is_likely_episode is False
    assert result.confidence == 0.0
    assert result.series_name is None
    assert result.title == "Test Movie"
    assert "Test Director" in result.director_names
    assert set(result.actor_names) == {"Test Actor One", "Test Actor Two"}


# --- apply_movie_metadata -----------------------------------------------------


def test_apply_movie_metadata_requires_confirmation(db: Database):
    media_id = _make_media_file(db, "/library/movies/movie1.mp4")
    snap = VideoTagSnapshot(title="Testfilm")
    with db.session() as session, pytest.raises(VideoApplyNotConfirmedError):
        apply_movie_metadata(session, media_id, snap, user_confirmed=False)


def test_apply_movie_metadata_writes_row_and_person_roles(db: Database):
    media_id = _make_media_file(db, "/library/movies/movie2.mp4")
    snap = VideoTagSnapshot(
        title="Testfilm", year=2020, genre="Drama", description="Eine Beschreibung.",
        director_names=["Regie Eins"], actor_names=["Schauspieler A", "Schauspieler B"],
    )
    with db.session() as session:
        movie = apply_movie_metadata(session, media_id, snap, user_confirmed=True)
        session.commit()
        movie_id = movie.id

    with db.session() as session:
        row = session.get(Movie, movie_id)
        assert row.title == "Testfilm"
        assert row.year == 2020
        assert row.genre == "Drama"
        mf = session.get(MediaFile, media_id)
        assert mf.kind == MediaKind.MOVIE

        directors = session.execute(
            select(PersonRole).where(
                PersonRole.movie_id == movie_id, PersonRole.role == PersonRoleType.DIRECTOR
            )
        ).scalars().all()
        assert len(directors) == 1
        actors = session.execute(
            select(PersonRole).where(
                PersonRole.movie_id == movie_id, PersonRole.role == PersonRoleType.ACTOR
            )
        ).scalars().all()
        assert len(actors) == 2


def test_apply_movie_metadata_second_apply_replaces_person_roles_not_duplicates(db: Database):
    media_id = _make_media_file(db, "/library/movies/movie3.mp4")
    with db.session() as session:
        movie = apply_movie_metadata(
            session, media_id, VideoTagSnapshot(title="X", actor_names=["A", "B"]),
            user_confirmed=True,
        )
        session.commit()
        movie_id = movie.id

    with db.session() as session:
        apply_movie_metadata(
            session, media_id, VideoTagSnapshot(title="X", actor_names=["C"]),
            user_confirmed=True,
        )
        session.commit()

    with db.session() as session:
        actors = session.execute(
            select(PersonRole).where(
                PersonRole.movie_id == movie_id, PersonRole.role == PersonRoleType.ACTOR
            )
        ).scalars().all()
        assert len(actors) == 1


def test_apply_movie_metadata_unknown_media_file_raises(db: Database):
    with db.session() as session, pytest.raises(ValueError):
        apply_movie_metadata(session, 999999, VideoTagSnapshot(title="x"), user_confirmed=True)


# --- apply_episode_metadata ----------------------------------------------------


def test_apply_episode_metadata_requires_confirmation(db: Database):
    media_id = _make_media_file(db, "/library/series/ep1.mp4", kind=MediaKind.EPISODE)
    result = detect_episode("/library/series/ep1.mp4")
    with db.session() as session, pytest.raises(VideoApplyNotConfirmedError):
        apply_episode_metadata(session, media_id, result, user_confirmed=False)


def test_apply_episode_metadata_writes_row_and_creates_series(
    db: Database, test_library_root: Path,
):
    path = test_library_root / "Series" / "Test Series" / "Season 01" / "Test Series - Pilot.mp4"
    media_id = _make_media_file(db, str(path), kind=MediaKind.MOVIE)
    result = detect_episode(str(path))

    with db.session() as session:
        episode = apply_episode_metadata(session, media_id, result, user_confirmed=True)
        session.commit()
        episode_id = episode.id

    with db.session() as session:
        row = session.get(Episode, episode_id)
        assert row.title == "Pilot"
        assert row.season_number == 1
        assert row.episode_number == 1
        series = session.get(Series, row.series_id)
        assert series.name == "Test Series"
        mf = session.get(MediaFile, media_id)
        assert mf.kind == MediaKind.EPISODE
        actors = session.execute(
            select(PersonRole).where(
                PersonRole.episode_id == episode_id, PersonRole.role == PersonRoleType.ACTOR
            )
        ).scalars().all()
        assert len(actors) == 1


def test_apply_episode_metadata_reuses_existing_series(db: Database, test_library_root: Path):
    path1 = test_library_root / "Series" / "Test Series" / "Season 01" / "Test Series - Pilot.mp4"
    path2 = (
        test_library_root / "Series" / "Test Series" / "Season 01"
        / "Test Series - S01E02 - Second Episode.mp4"
    )
    media_id_1 = _make_media_file(db, str(path1) + ".dup1")
    media_id_2 = _make_media_file(db, str(path2) + ".dup2")

    with db.session() as session:
        apply_episode_metadata(
            session, media_id_1, detect_episode(str(path1)), user_confirmed=True
        )
        apply_episode_metadata(
            session, media_id_2, detect_episode(str(path2)), user_confirmed=True
        )
        session.commit()

    with db.session() as session:
        series_rows = session.execute(
            select(Series).where(Series.name == "Test Series")
        ).scalars().all()
        assert len(series_rows) == 1
