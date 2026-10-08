"""Tests fuer die KI-Metadaten-Engine (§25, ADR-0017)."""
from __future__ import annotations

from pathlib import Path

import pytest

from genesis_core.ai.base import AISuggestion
from genesis_core.ai.engine import (
    SUGGESTABLE_FIELDS,
    AIApplyNotConfirmedError,
    apply_suggestions,
    build_context,
    list_ai_metadata,
    suggest_metadata,
)
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, MediaKind, Track


class _StubProvider:
    """Deterministischer Test-Provider (kein echtes Netzwerk/Ollama)."""

    name = "stub"
    is_local = True
    requires_internet = False

    def __init__(self, available: bool = True):
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def suggest_text_fields(self, context: str, fields: list[str]) -> list[AISuggestion]:
        return [
            AISuggestion(
                field_name=field,
                field_value=f"stub-value-for-{field}",
                model_name="stub-model",
                model_version="1.0",
                confidence=0.5,
                prompt=context,
            )
            for field in fields
        ]

    def embed_text(self, text: str):
        return None


def _make_media_file(db: Database, filename: str = "song.mp3") -> int:
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


def test_suggest_metadata_unknown_media_file_raises(db: Database):
    with db.session() as session, pytest.raises(ValueError):
        suggest_metadata(session, 9999, _StubProvider())


def test_suggest_metadata_unknown_field_raises(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session, pytest.raises(ValueError):
        suggest_metadata(session, media_file_id, _StubProvider(), fields=["not_a_real_field"])


def test_suggest_metadata_null_provider_returns_empty():
    pass  # abgedeckt in test_ai_provider.py (NullAIProvider), hier nur Engine-Integration


def test_suggest_metadata_provider_unavailable_returns_empty(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session:
        result = suggest_metadata(session, media_file_id, _StubProvider(available=False))
        assert result == []


def test_suggest_metadata_returns_suggestions_for_all_default_fields(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session:
        suggestions = suggest_metadata(session, media_file_id, _StubProvider())
        assert {s.field_name for s in suggestions} == set(SUGGESTABLE_FIELDS)
        for s in suggestions:
            assert s.is_ai_generated is True
            assert s.model_name == "stub-model"
            assert s.confidence == 0.5


def test_suggest_metadata_with_explicit_field_subset(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session:
        suggestions = suggest_metadata(session, media_file_id, _StubProvider(), fields=["genre"])
        assert len(suggestions) == 1
        assert suggestions[0].field_name == "genre"


def test_build_context_includes_filename_and_existing_track_fields(db: Database):
    media_file_id = _make_media_file(db, filename="my_song.mp3")
    with db.session() as session:
        session.add(Track(media_file_id=media_file_id, title="Mein Titel", year=2020))
        session.commit()
    with db.session() as session:
        context = build_context(session, session.get(MediaFile, media_file_id))
        assert "my_song.mp3" in context
        assert "Mein Titel" in context
        assert "2020" in context


def test_apply_suggestions_requires_confirm(db: Database):
    media_file_id = _make_media_file(db)
    suggestion = AISuggestion(
        field_name="genre", field_value="Rock", model_name="stub-model",
        model_version="1.0", confidence=0.7,
    )
    with db.session() as session, pytest.raises(AIApplyNotConfirmedError):
        apply_suggestions(session, media_file_id, [suggestion], confirm=False)


def test_apply_suggestions_unknown_media_file_raises(db: Database):
    suggestion = AISuggestion(
        field_name="genre", field_value="Rock", model_name="stub-model",
        model_version="1.0", confidence=0.7,
    )
    with db.session() as session, pytest.raises(ValueError):
        apply_suggestions(session, 9999, [suggestion], confirm=True)


def test_apply_suggestions_writes_ai_metadata_with_full_provenance(db: Database):
    media_file_id = _make_media_file(db)
    suggestion = AISuggestion(
        field_name="mood", field_value="melancholisch", model_name="ollama:qwen2.5:0.5b",
        model_version=None, confidence=0.6, prompt="KONTEXT...",
    )
    with db.session() as session:
        saved = apply_suggestions(session, media_file_id, [suggestion], confirm=True)
        assert len(saved) == 1
        entry = saved[0]
        assert entry.field_name == "mood"
        assert entry.field_value == "melancholisch"
        assert entry.is_ai_generated is True
        assert entry.model_name == "ollama:qwen2.5:0.5b"
        assert entry.confidence == 0.6
        assert entry.accepted_by_user is True
        assert entry.created_at is not None

    with db.session() as session:
        stored = list_ai_metadata(session, media_file_id)
        assert len(stored) == 1
        assert stored[0].field_value == "melancholisch"


def test_apply_suggestions_reapply_same_field_and_model_replaces_entry(db: Database):
    media_file_id = _make_media_file(db)
    first = AISuggestion(
        field_name="genre", field_value="Rock", model_name="stub-model",
        model_version="1.0", confidence=0.5,
    )
    second = AISuggestion(
        field_name="genre", field_value="Hard Rock", model_name="stub-model",
        model_version="1.0", confidence=0.8,
    )
    with db.session() as session:
        apply_suggestions(session, media_file_id, [first], confirm=True)
    with db.session() as session:
        apply_suggestions(session, media_file_id, [second], confirm=True)
    with db.session() as session:
        stored = list_ai_metadata(session, media_file_id)
        assert len(stored) == 1
        assert stored[0].field_value == "Hard Rock"
        assert stored[0].confidence == 0.8


def test_apply_suggestions_different_models_both_kept(db: Database):
    media_file_id = _make_media_file(db)
    a = AISuggestion(
        field_name="genre", field_value="Rock", model_name="model-a",
        model_version=None, confidence=0.5,
    )
    b = AISuggestion(
        field_name="genre", field_value="Pop", model_name="model-b",
        model_version=None, confidence=0.5,
    )
    with db.session() as session:
        apply_suggestions(session, media_file_id, [a, b], confirm=True)
    with db.session() as session:
        stored = list_ai_metadata(session, media_file_id)
        assert {s.model_name for s in stored} == {"model-a", "model-b"}


def test_list_ai_metadata_empty_when_none_applied(db: Database):
    media_file_id = _make_media_file(db)
    with db.session() as session:
        assert list_ai_metadata(session, media_file_id) == []
