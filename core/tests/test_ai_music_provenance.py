"""Tests fuer die KI-Musik-Provenienz (§27, ADR-0017)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from genesis_core.ai.music_provenance import (
    AIMusicApplyNotConfirmedError,
    AIMusicProvenanceInput,
    apply_ai_music_provenance,
    artist_names_for_track,
    get_ai_music_provenance,
)
from genesis_core.db import Database
from genesis_core.db.models import AIStatus, MediaFile, MediaKind, Track


def _make_media_file(db: Database, filename: str = "ai_song.mp3") -> int:
    with db.session() as session:
        mf = MediaFile(
            absolute_path=f"/tmp/{filename}",
            directory="/tmp",
            filename=filename,
            extension=Path(filename).suffix,
            kind=MediaKind.MUSIC,
            size_bytes=100,
        )
        session.add(mf)
        session.flush()
        return mf.id


def test_apply_requires_confirm(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.AI_GENERATED)
    with db.session() as session, pytest.raises(AIMusicApplyNotConfirmedError):
        apply_ai_music_provenance(session, media_file_id, data, confirm=False)


def test_apply_unknown_media_file_raises(db: Database):
    data = AIMusicProvenanceInput(status=AIStatus.AI_GENERATED)
    with db.session() as session, pytest.raises(ValueError):
        apply_ai_music_provenance(session, 9999, data, confirm=True)


def test_apply_creates_track_if_missing_and_sets_fields(db: Database):
    media_file_id = _make_media_file(db)
    created_at = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    data = AIMusicProvenanceInput(
        status=AIStatus.AI_GENERATED,
        source="Suno",
        model="Suno v4",
        prompt="upbeat synthwave track",
        creation_date=created_at,
        instrumental=False,
        style="Synthwave",
        mood="energetic",
        owner="Test Owner",
        artist_name="Synthetic Artist",
    )
    with db.session() as session:
        track = apply_ai_music_provenance(session, media_file_id, data, confirm=True)
        assert track.ai_status == AIStatus.AI_GENERATED
        assert track.ai_source == "Suno"
        assert track.ai_model == "Suno v4"
        assert track.ai_prompt == "upbeat synthwave track"
        assert track.ai_instrumental is False
        assert track.ai_style == "Synthwave"
        assert track.ai_mood == "energetic"
        assert track.ai_owner == "Test Owner"

    with db.session() as session:
        mf = session.get(MediaFile, media_file_id)
        assert mf.kind == MediaKind.AI_MUSIC  # AI_GENERATED -> Umklassifizierung


def test_apply_hybrid_also_reclassifies_as_ai_music(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.HYBRID)
    with db.session() as session:
        apply_ai_music_provenance(session, media_file_id, data, confirm=True)
    with db.session() as session:
        mf = session.get(MediaFile, media_file_id)
        assert mf.kind == MediaKind.AI_MUSIC


def test_apply_human_generated_does_not_reclassify(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.HUMAN_GENERATED)
    with db.session() as session:
        apply_ai_music_provenance(session, media_file_id, data, confirm=True)
    with db.session() as session:
        mf = session.get(MediaFile, media_file_id)
        assert mf.kind == MediaKind.MUSIC


def test_apply_unknown_status_does_not_reclassify(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.UNKNOWN)
    with db.session() as session:
        apply_ai_music_provenance(session, media_file_id, data, confirm=True)
    with db.session() as session:
        mf = session.get(MediaFile, media_file_id)
        assert mf.kind == MediaKind.MUSIC


def test_apply_reuses_existing_track(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session:
        session.add(Track(media_file_id=media_file_id, title="Existing Title"))
        session.commit()

    data = AIMusicProvenanceInput(status=AIStatus.AI_GENERATED, model="TestModel")
    with db.session() as session:
        track = apply_ai_music_provenance(session, media_file_id, data, confirm=True)
        assert track.title == "Existing Title"  # unangetastet
        assert track.ai_model == "TestModel"

    with db.session() as session:
        count = session.query(Track).filter_by(media_file_id=media_file_id).count()
        assert count == 1  # kein zweiter Track angelegt


def test_artist_name_creates_person_role(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.AI_GENERATED, artist_name="Nova Synth")
    with db.session() as session:
        track = apply_ai_music_provenance(session, media_file_id, data, confirm=True)
        track_id = track.id

    with db.session() as session:
        names = artist_names_for_track(session, track_id)
        assert names == ["Nova Synth"]


def test_artist_name_reapply_does_not_duplicate_person_role(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.AI_GENERATED, artist_name="Nova Synth")
    with db.session() as session:
        track = apply_ai_music_provenance(session, media_file_id, data, confirm=True)
        track_id = track.id
    with db.session() as session:
        apply_ai_music_provenance(session, media_file_id, data, confirm=True)
    with db.session() as session:
        names = artist_names_for_track(session, track_id)
        assert names == ["Nova Synth"]


def test_get_ai_music_provenance_returns_none_when_no_track(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session:
        assert get_ai_music_provenance(session, media_file_id) is None


def test_get_ai_music_provenance_returns_track_after_apply(db: Database):
    media_file_id = _make_media_file(db)
    data = AIMusicProvenanceInput(status=AIStatus.AI_GENERATED, source="Udio")
    with db.session() as session:
        apply_ai_music_provenance(session, media_file_id, data, confirm=True)
    with db.session() as session:
        track = get_ai_music_provenance(session, media_file_id)
        assert track is not None
        assert track.ai_source == "Udio"
