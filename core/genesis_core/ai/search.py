"""Lokale semantische Suche (§26, ADR-0017).

Spec-Zitat: "Implementiere spaeter semantische Suche [...] Dafuer kann eine
lokale Embedding-Datenbank verwendet werden. Keine Cloud-KI voraussetzen."
Umgesetzt als Brute-Force-Kosinus-Aehnlichkeit ueber in `AIEmbedding`
zwischengespeicherte Vektoren (§57-Hinweis: fuer sehr grosse Bibliotheken
waere eine ANN-Indexstruktur (z.B. FAISS) ein spaeteres Hardening-Thema,
siehe ADR-0017 Backlog - fuer Entwicklungs-/Testbibliotheken reicht die
einfache Variante).

Genau wie alle anderen KI-Funktionen: liefert bei deaktivierter/nicht
erreichbarer KI ein leeres, aber klar als "nicht verfuegbar" markiertes
Ergebnis statt eines Fehlers oder - schlimmer - eines Cloud-Fallbacks.
"""
from __future__ import annotations

import dataclasses
import hashlib
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from genesis_core.ai.base import AIProvider
from genesis_core.ai.engine import build_context
from genesis_core.db.models import AIEmbedding, MediaFile
from genesis_core.logutil import get_logger

log = get_logger("AISearch")


@dataclasses.dataclass
class SemanticSearchResult:
    media_file_id: int
    filename: str
    kind: str
    score: float


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_text_for_media_file(db: Session, media_file: MediaFile) -> str:
    """Wiederverwendet denselben faktenbasierten Kontext wie die
    KI-Metadaten-Vorschau (Prinzip #16: keine erfundenen Zusatzinfos nur
    fuer die Suche)."""
    return build_context(db, media_file)


def reindex_media_file(
    db: Session, media_file_id: int, provider: AIProvider
) -> AIEmbedding | None:
    """Berechnet/aktualisiert den Embedding-Vektor einer einzelnen Datei.

    Liefert None (kein Fehler), wenn die KI deaktiviert/nicht erreichbar
    ist oder der Provider keine Embeddings unterstuetzt. Ueberspringt die
    Neuberechnung, wenn sich der Kontext-Text seit dem letzten Reindex
    nicht geaendert hat (Performance bei grossen Bibliotheken, §57).
    """
    media_file = db.get(MediaFile, media_file_id)
    if media_file is None:
        raise ValueError(f"MediaFile {media_file_id} nicht gefunden")

    if not provider.is_available():
        return None

    text = embedding_text_for_media_file(db, media_file)
    text_hash = _text_hash(text)

    existing = db.execute(
        select(AIEmbedding).where(
            AIEmbedding.media_file_id == media_file_id,
            AIEmbedding.model_name == provider.name,
        )
    ).scalar_one_or_none()
    if existing is not None and existing.source_text_hash == text_hash:
        return existing

    vector = provider.embed_text(text)
    if vector is None:
        return None

    if existing is not None:
        existing.vector_json = vector
        existing.dimension = len(vector)
        existing.source_text_hash = text_hash
        db.commit()
        db.refresh(existing)
        return existing

    entry = AIEmbedding(
        media_file_id=media_file_id,
        model_name=provider.name,
        dimension=len(vector),
        vector_json=vector,
        source_text_hash=text_hash,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def reindex_all(db: Session, provider: AIProvider) -> dict[str, int]:
    """Indiziert alle bekannten Mediendateien (ueberspringt unveraenderte).
    Reine additive Cache-Operation ohne Risiko fuer Originaldateien/
    bestehende Metadaten - daher KEINE Bestaetigungspflicht (anders als
    Metadaten-Uebernahmen, Prinzip #17 gilt dort, nicht hier)."""
    if not provider.is_available():
        return {"total": 0, "embedded": 0, "skipped_unavailable": 1}

    media_file_ids = list(db.execute(select(MediaFile.id)).scalars())
    embedded = 0
    skipped = 0
    for media_file_id in media_file_ids:
        result = reindex_media_file(db, media_file_id, provider)
        if result is not None:
            embedded += 1
        else:
            skipped += 1
    log.info("KI-Suchindex aktualisiert: %s von %s Dateien", embedded, len(media_file_ids))
    return {"total": len(media_file_ids), "embedded": embedded, "skipped_unavailable": skipped}


def semantic_search(
    db: Session, provider: AIProvider, query: str, *, top_k: int = 20
) -> list[SemanticSearchResult]:
    """Liefert die `top_k` aehnlichsten Mediendateien zur Suchanfrage,
    absteigend nach Kosinus-Aehnlichkeit. Leere Liste, wenn KI nicht
    verfuegbar ist oder noch kein Index existiert (kein Fehler)."""
    if not provider.is_available():
        return []

    query_vector = provider.embed_text(query)
    if query_vector is None:
        return []

    rows = list(
        db.execute(
            select(AIEmbedding, MediaFile)
            .join(MediaFile, AIEmbedding.media_file_id == MediaFile.id)
            .where(AIEmbedding.model_name == provider.name)
        ).all()
    )

    scored: list[SemanticSearchResult] = []
    for embedding, media_file in rows:
        score = _cosine_similarity(query_vector, list(embedding.vector_json))
        scored.append(
            SemanticSearchResult(
                media_file_id=media_file.id,
                filename=media_file.filename,
                kind=media_file.kind.value,
                score=score,
            )
        )
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
