"""Tests fuer die KI-API (§25 KI-Metadaten, §26 KI-Suche, §27 KI-Musik,
ADR-0017)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.ai.base import AISuggestion
from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.db.models import MediaFile, MediaKind


class _StubProvider:
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
                field_name=f, field_value=f"value-{f}", model_name="stub-model",
                model_version="1.0", confidence=0.6, prompt=context,
            )
            for f in fields
        ]

    def embed_text(self, text: str):
        return [1.0, 0.0] if "calm" in text.lower() else [0.0, 1.0]


def _make_app(tmp_path: Path, *, stub: bool = True):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    app = create_app(settings)
    if stub:
        app.state.genesis.ai_provider = _StubProvider()
    return app


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _seed_media(app, filename: str = "song.mp3", kind: MediaKind = MediaKind.MUSIC) -> int:
    with app.state.genesis.db.session() as session:
        mf = MediaFile(
            absolute_path=f"/tmp/{filename}", directory="/tmp", filename=filename,
            extension=Path(filename).suffix, kind=kind, size_bytes=1000,
        )
        session.add(mf)
        session.flush()
        return mf.id


# --- §25 KI-Metadaten -------------------------------------------------------


def test_ai_suggest_unknown_media_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.post("/media/999/ai/suggest", json={})
    assert resp.status_code == 404


def test_ai_suggest_returns_stub_suggestions(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    resp = client.post(f"/media/{media_id}/ai/suggest", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 9  # SUGGESTABLE_FIELDS
    assert all(s["is_ai_generated"] for s in body)
    assert all(s["model_name"] == "stub-model" for s in body)


def test_ai_suggest_with_explicit_fields(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    resp = client.post(f"/media/{media_id}/ai/suggest", json={"fields": ["genre", "mood"]})
    assert resp.status_code == 200
    body = resp.json()
    assert {s["field_name"] for s in body} == {"genre", "mood"}


def test_ai_suggest_disabled_ai_returns_empty(tmp_path):
    app = _make_app(tmp_path, stub=False)  # default NullAIProvider (ai.enabled=False)
    client = _make_client(app)
    media_id = _seed_media(app)
    resp = client.post(f"/media/{media_id}/ai/suggest", json={})
    assert resp.status_code == 200
    assert resp.json() == []


def test_ai_apply_requires_confirm(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    accepted = [
        {"field_name": "genre", "field_value": "Rock", "model_name": "stub-model",
         "model_version": "1.0", "confidence": 0.6},
    ]
    resp = client.post(f"/media/{media_id}/ai/apply", json={"accepted": accepted, "confirm": False})
    assert resp.status_code == 422


def test_ai_apply_unknown_media_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    accepted = [
        {"field_name": "genre", "field_value": "Rock", "model_name": "stub-model"},
    ]
    resp = client.post("/media/999/ai/apply", json={"accepted": accepted, "confirm": True})
    assert resp.status_code == 404


def test_ai_apply_persists_and_is_listable(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    accepted = [
        {"field_name": "mood", "field_value": "melancholisch", "model_name": "stub-model",
         "model_version": "1.0", "confidence": 0.6, "prompt": "ctx"},
    ]
    resp = client.post(f"/media/{media_id}/ai/apply", json={"accepted": accepted, "confirm": True})
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["entries"][0]["field_value"] == "melancholisch"
    assert body["entries"][0]["accepted_by_user"] is True

    resp2 = client.get(f"/media/{media_id}/ai/metadata")
    assert resp2.status_code == 200
    stored = resp2.json()
    assert len(stored) == 1
    assert stored[0]["field_name"] == "mood"


def test_ai_metadata_unknown_media_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/999/ai/metadata")
    assert resp.status_code == 404


def test_ai_status_reflects_disabled_default(tmp_path):
    app = _make_app(tmp_path, stub=False)
    client = _make_client(app)
    resp = client.get("/ai/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["provider"] == "null"


def test_ai_status_reflects_stub_provider(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/ai/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "stub"
    assert body["available"] is True


# --- §27 KI-Musik ------------------------------------------------------------


def test_ai_music_get_returns_null_when_not_set(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    resp = client.get(f"/media/{media_id}/ai-music")
    assert resp.status_code == 200
    assert resp.json() is None


def test_ai_music_get_unknown_media_returns_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/media/999/ai-music")
    assert resp.status_code == 404


def test_ai_music_apply_requires_confirm(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    resp = client.post(
        f"/media/{media_id}/ai-music/apply",
        json={"status": "ai_generated", "confirm": False},
    )
    assert resp.status_code == 422


def test_ai_music_apply_sets_fields_and_reclassifies_kind(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    media_id = _seed_media(app)
    resp = client.post(
        f"/media/{media_id}/ai-music/apply",
        json={
            "status": "ai_generated", "source": "Suno", "model": "Suno v4",
            "style": "Synthwave", "artist_name": "Nova Synth", "confirm": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()["track"]
    assert body["ai_status"] == "ai_generated"
    assert body["ai_source"] == "Suno"
    assert body["artist_names"] == ["Nova Synth"]

    resp2 = client.get(f"/media/{media_id}/ai-music")
    assert resp2.status_code == 200
    assert resp2.json()["ai_model"] == "Suno v4"

    # MediaFile.kind wurde auf ai_music umklassifiziert.
    with app.state.genesis.db.session() as session:
        mf = session.get(MediaFile, media_id)
        assert mf.kind == MediaKind.AI_MUSIC


# --- §26 KI-Suche -------------------------------------------------------------


def test_ai_search_reindex_and_search_end_to_end(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    calm_id = _seed_media(app, filename="calm_song.mp3")
    with app.state.genesis.db.session() as session:
        from genesis_core.db.models import Track
        session.add(Track(media_file_id=calm_id, title="Calm Lullaby"))
        session.commit()
    rock_id = _seed_media(app, filename="rock_song.mp3")
    with app.state.genesis.db.session() as session:
        from genesis_core.db.models import Track
        session.add(Track(media_file_id=rock_id, title="Hard Rock Anthem"))
        session.commit()

    resp = client.post("/ai/search/reindex")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["embedded"] == 2

    resp2 = client.post("/ai/search", json={"query": "calm relaxing music", "top_k": 5})
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["available"] is True
    assert len(body["results"]) == 2
    assert body["results"][0]["media_file_id"] == calm_id


def test_ai_search_disabled_ai_returns_unavailable(tmp_path):
    app = _make_app(tmp_path, stub=False)
    client = _make_client(app)
    resp = client.post("/ai/search", json={"query": "irgendwas"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True  # NullAIProvider.is_available()==True, liefert aber []
    assert body["results"] == []
