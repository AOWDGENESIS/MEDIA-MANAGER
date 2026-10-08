"""Tests fuer die lokale semantische Suche (§26, ADR-0017)."""
from __future__ import annotations

from pathlib import Path

import pytest

from genesis_core.ai.search import (
    embedding_text_for_media_file,
    reindex_all,
    reindex_media_file,
    semantic_search,
)
from genesis_core.db import Database
from genesis_core.db.models import AIEmbedding, MediaFile, MediaKind, Track


class _StubEmbeddingProvider:
    """Deterministischer Embedding-Stub: Vektor haengt nur vom Text ab,
    damit sich Aehnlichkeit vorhersagbar testen laesst."""

    name = "stub-embed"
    is_local = True
    requires_internet = False

    def __init__(self, available: bool = True, vectors: dict[str, list[float]] | None = None):
        self._available = available
        self._vectors = vectors or {}

    def is_available(self) -> bool:
        return self._available

    def suggest_text_fields(self, context: str, fields: list[str]):
        return []

    def embed_text(self, text: str):
        for key, vector in self._vectors.items():
            if key in text:
                return vector
        return [1.0, 0.0, 0.0]


def _make_media_file(db: Database, filename: str, title: str | None = None) -> int:
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
        if title:
            session.add(Track(media_file_id=mf.id, title=title))
        session.commit()
        return mf.id


def test_embedding_text_includes_filename(db: Database):
    media_file_id = _make_media_file(db, "lullaby.mp3", title="Ruhiges Schlaflied")
    with db.session() as session:
        mf = session.get(MediaFile, media_file_id)
        text = embedding_text_for_media_file(session, mf)
        assert "lullaby.mp3" in text
        assert "Ruhiges Schlaflied" in text


def test_reindex_media_file_unavailable_provider_returns_none(db: Database):
    media_file_id = _make_media_file(db, "a.mp3")
    with db.session() as session:
        result = reindex_media_file(session, media_file_id, _StubEmbeddingProvider(available=False))
        assert result is None


def test_reindex_media_file_unknown_media_file_raises(db: Database):
    with db.session() as session, pytest.raises(ValueError):
        reindex_media_file(session, 9999, _StubEmbeddingProvider())


def test_reindex_media_file_creates_embedding(db: Database):
    media_file_id = _make_media_file(db, "a.mp3", title="Calm Song")
    with db.session() as session:
        entry = reindex_media_file(session, media_file_id, _StubEmbeddingProvider())
        assert entry is not None
        assert entry.dimension == 3
        assert entry.model_name == "stub-embed"

    with db.session() as session:
        stored = session.query(AIEmbedding).filter_by(media_file_id=media_file_id).one()
        assert stored.vector_json == [1.0, 0.0, 0.0]


def test_reindex_media_file_skips_unchanged_text(db: Database):
    media_file_id = _make_media_file(db, "a.mp3", title="Calm Song")
    provider = _StubEmbeddingProvider()
    with db.session() as session:
        first = reindex_media_file(session, media_file_id, provider)
        first_id = first.id
    with db.session() as session:
        second = reindex_media_file(session, media_file_id, provider)
        # Gleicher Datensatz (Text unveraendert) - kein neuer Eintrag.
        assert second.id == first_id
    with db.session() as session:
        count = session.query(AIEmbedding).filter_by(media_file_id=media_file_id).count()
        assert count == 1


def test_reindex_media_file_recomputes_when_text_changes(db: Database):
    media_file_id = _make_media_file(db, "a.mp3", title="Old Title")
    provider = _StubEmbeddingProvider(vectors={"Old Title": [1.0, 0.0, 0.0]})
    with db.session() as session:
        reindex_media_file(session, media_file_id, provider)

    with db.session() as session:
        track = session.query(Track).filter_by(media_file_id=media_file_id).one()
        track.title = "New Title"
        session.commit()

    provider2 = _StubEmbeddingProvider(vectors={"New Title": [0.0, 1.0, 0.0]})
    with db.session() as session:
        updated = reindex_media_file(session, media_file_id, provider2)
        assert updated.vector_json == [0.0, 1.0, 0.0]
    with db.session() as session:
        count = session.query(AIEmbedding).filter_by(media_file_id=media_file_id).count()
        assert count == 1  # ersetzt, nicht dupliziert


def test_reindex_all_unavailable_provider(db: Database):
    _make_media_file(db, "a.mp3")
    with db.session() as session:
        stats = reindex_all(session, _StubEmbeddingProvider(available=False))
        assert stats["embedded"] == 0


def test_reindex_all_embeds_every_media_file(db: Database):
    _make_media_file(db, "a.mp3")
    _make_media_file(db, "b.mp3")
    with db.session() as session:
        stats = reindex_all(session, _StubEmbeddingProvider())
        assert stats["total"] == 2
        assert stats["embedded"] == 2


def test_semantic_search_unavailable_provider_returns_empty(db: Database):
    with db.session() as session:
        results = semantic_search(session, _StubEmbeddingProvider(available=False), "query")
        assert results == []


def test_semantic_search_no_index_returns_empty(db: Database):
    _make_media_file(db, "a.mp3")
    with db.session() as session:
        results = semantic_search(session, _StubEmbeddingProvider(), "query")
        assert results == []


def test_semantic_search_ranks_by_cosine_similarity(db: Database):
    calm_id = _make_media_file(db, "calm.mp3", title="Calm Lullaby")
    rock_id = _make_media_file(db, "rock.mp3", title="Dark Rock Anthem")

    provider = _StubEmbeddingProvider(
        vectors={
            "calm.mp3": [1.0, 0.0],
            "Calm Lullaby": [1.0, 0.0],
            "rock.mp3": [0.0, 1.0],
            "Dark Rock Anthem": [0.0, 1.0],
        }
    )
    # Reindex beide Dateien mit providerspezifischen Vektoren je Kontext-Text.
    with db.session() as session:
        reindex_media_file(session, calm_id, provider)
        reindex_media_file(session, rock_id, provider)

    # Leerstring ist Teilstring jedes Textes -> embed_text liefert fuer JEDE
    # Suchanfrage denselben (zum "calm"-Vektor identischen) Vektor, damit
    # sich die erwartete Rangfolge deterministisch pruefen laesst.
    query_provider = _StubEmbeddingProvider(vectors={"": [1.0, 0.0]})
    with db.session() as session:
        results = semantic_search(session, query_provider, "ruhige Musik", top_k=5)
        assert len(results) == 2
        assert results[0].media_file_id == calm_id
        assert results[0].score == pytest.approx(1.0)
        assert results[1].media_file_id == rock_id
        assert results[1].score == pytest.approx(0.0)
