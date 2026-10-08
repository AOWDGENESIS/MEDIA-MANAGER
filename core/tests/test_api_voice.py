"""Tests fuer die Voice-Studio-API (§28/§29, ADR-0018)."""
from __future__ import annotations

import wave
from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings
from genesis_core.voice.base import TTSProviderUnavailableError, TTSResult


class _StubTTSProvider:
    name = "stub"
    is_local = True
    requires_internet = False

    def __init__(self, available: bool = True):
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def synthesize(self, text: str, *, model_path, output_wav_path: str) -> TTSResult:
        if not self._available:
            raise TTSProviderUnavailableError("Stub nicht verfuegbar")
        Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_wav_path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(b"\x00\x00" * 8000)
        return TTSResult(
            output_path=output_wav_path, duration_seconds=0.5, sample_rate=16000,
            engine_name=self.name,
        )


def _make_app(tmp_path: Path, *, available: bool = True):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    app = create_app(settings)
    app.state.genesis.tts_provider = _StubTTSProvider(available=available)
    return app


def _make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def _create_profile(client: TestClient, name: str = "Test-Stimme", **overrides) -> dict:
    payload = {
        "name": name, "engine": "stub", "model_path": "/tmp/fake.onnx",
        "language": "de", "model_license": "MIT", "offline_capable": True,
        "open_source": True, "commercial_use_allowed": True, "confirm": True,
    }
    payload.update(overrides)
    resp = client.post("/voice/profiles", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["profile"]


# --- Status/Katalog ---------------------------------------------------------


def test_voice_status_reports_engine_transparency(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/voice/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "stub"
    assert body["is_local"] is True
    assert body["requires_internet"] is False
    assert body["available"] is True


def test_voice_engines_catalog_lists_piper(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/voice/engines")
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()["engines"]]
    assert "piper" in ids


def test_voice_requires_token(tmp_path):
    app = _make_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/voice/status")
    assert resp.status_code in (401, 403)


# --- Profilverwaltung --------------------------------------------------------


def test_create_voice_profile_requires_confirm(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.post(
        "/voice/profiles",
        json={"name": "X", "engine": "stub", "confirm": False},
    )
    assert resp.status_code == 422


def test_create_and_list_voice_profiles(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client)
    assert profile["engine"] == "stub"
    assert profile["model_license"] == "MIT"
    assert profile["commercial_use_allowed"] is True

    resp = client.get("/voice/profiles")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["profiles"]]
    assert "Test-Stimme" in names


def test_create_voice_profile_duplicate_name_conflict(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    _create_profile(client, name="Dup")
    resp = client.post(
        "/voice/profiles",
        json={"name": "Dup", "engine": "stub", "confirm": True},
    )
    assert resp.status_code == 409


def test_get_voice_profile_not_found(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/voice/profiles/999999")
    assert resp.status_code == 404


def test_delete_voice_profile_requires_confirm(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client)
    resp = client.request(
        "DELETE", f"/voice/profiles/{profile['id']}", json={"confirm": False}
    )
    assert resp.status_code == 422


def test_delete_voice_profile_requires_exact_name(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client)
    resp = client.request(
        "DELETE", f"/voice/profiles/{profile['id']}",
        json={"confirm": True, "confirm_name": "falsch"},
    )
    assert resp.status_code == 403
    # Profil existiert weiterhin.
    assert client.get(f"/voice/profiles/{profile['id']}").status_code == 200


def test_delete_voice_profile_succeeds(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client)
    resp = client.request(
        "DELETE", f"/voice/profiles/{profile['id']}",
        json={"confirm": True, "confirm_name": profile["name"]},
    )
    assert resp.status_code == 200
    assert client.get(f"/voice/profiles/{profile['id']}").status_code == 404


# --- Synthese -----------------------------------------------------------


def test_synthesize_requires_confirm(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client)
    resp = client.post(
        f"/voice/profiles/{profile['id']}/synthesize",
        json={"text": "Hallo", "confirm": False},
    )
    assert resp.status_code == 422


def test_synthesize_unknown_profile_404(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.post(
        "/voice/profiles/999999/synthesize", json={"text": "Hallo", "confirm": True}
    )
    assert resp.status_code == 404


def test_synthesize_creates_audio_and_history(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client)
    resp = client.post(
        f"/voice/profiles/{profile['id']}/synthesize",
        json={"text": "Hallo Welt", "export_format": "wav", "confirm": True},
    )
    assert resp.status_code == 200, resp.text
    synthesis = resp.json()["synthesis"]
    assert synthesis["duration_seconds"] == 0.5
    assert Path(synthesis["output_path"]).exists()

    history = client.get("/voice/syntheses")
    assert history.status_code == 200
    assert len(history.json()["syntheses"]) == 1

    audio_resp = client.get(f"/voice/syntheses/{synthesis['id']}/audio")
    assert audio_resp.status_code == 200
    assert audio_resp.headers["content-type"] == "audio/wav"
    assert len(audio_resp.content) > 0


def test_synthesize_unavailable_provider_returns_409(tmp_path):
    app = _make_app(tmp_path, available=False)
    client = _make_client(app)
    profile = _create_profile(client)
    resp = client.post(
        f"/voice/profiles/{profile['id']}/synthesize",
        json={"text": "Hallo", "confirm": True},
    )
    assert resp.status_code == 409


def test_voice_profile_test_endpoint_uses_canned_phrase(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    profile = _create_profile(client, language="de")
    resp = client.post(
        f"/voice/profiles/{profile['id']}/test", json={"confirm": True}
    )
    assert resp.status_code == 200
    synthesis = resp.json()["synthesis"]
    assert synthesis["is_test_phrase"] is True
    assert "GENESIS" in synthesis["text"]


def test_list_syntheses_filters_by_profile(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    p1 = _create_profile(client, name="P1")
    p2 = _create_profile(client, name="P2")
    client.post(f"/voice/profiles/{p1['id']}/synthesize", json={"text": "Eins", "confirm": True})
    client.post(f"/voice/profiles/{p2['id']}/synthesize", json={"text": "Zwei", "confirm": True})

    resp = client.get("/voice/syntheses", params={"profile_id": p1["id"]})
    assert resp.status_code == 200
    rows = resp.json()["syntheses"]
    assert len(rows) == 1
    assert rows[0]["voice_profile_id"] == p1["id"]


def test_audio_endpoint_404_for_unknown_synthesis(tmp_path):
    app = _make_app(tmp_path)
    client = _make_client(app)
    resp = client.get("/voice/syntheses/999999/audio")
    assert resp.status_code == 404
