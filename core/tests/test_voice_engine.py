"""Tests fuer die Voice-Studio-Engine (§28/§29, ADR-0018).

Nutzt einen deterministischen Stub-Provider statt der echten Piper-Engine
(CI-Stabilitaet, kein Modell-Download noetig) - die echte Piper-Anbindung
wird separat in test_voice_piper_provider.py geprueft (uebersprungen, wenn
piper-tts/Modelle nicht installiert sind).
"""
from __future__ import annotations

import wave
from pathlib import Path

import pytest

from genesis_core.db import Database
from genesis_core.voice.base import TTSProvider, TTSProviderUnavailableError, TTSResult
from genesis_core.voice.engine import (
    VoiceApplyNotConfirmedError,
    VoiceDeleteNotConfirmedError,
    VoiceProfileInput,
    VoiceProfileNotFoundError,
    VoiceSynthesisError,
    create_voice_profile,
    delete_voice_profile,
    get_test_phrase_for_language,
    get_voice_profile,
    list_syntheses,
    list_voice_profiles,
    synthesize_text,
)


class StubTTSProvider(TTSProvider):
    name = "stub"
    is_local = True
    requires_internet = False

    def __init__(self, available: bool = True, fail: bool = False):
        self._available = available
        self._fail = fail
        self.calls: list[str] = []

    def is_available(self) -> bool:
        return self._available

    def synthesize(self, text: str, *, model_path, output_wav_path: str) -> TTSResult:
        self.calls.append(text)
        if not self._available:
            raise TTSProviderUnavailableError("Stub nicht verfuegbar")
        if self._fail:
            raise RuntimeError("Simulierter Renderfehler")
        Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_wav_path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(b"\x00\x00" * 16000)  # 1 Sekunde Stille
        return TTSResult(
            output_path=output_wav_path, duration_seconds=1.0, sample_rate=16000,
            engine_name=self.name,
        )


def _profile_input(name: str = "Test-Stimme", **overrides) -> VoiceProfileInput:
    data = {
        "name": name, "engine": "stub", "model_path": "/tmp/fake.onnx", "language": "de",
        "description": "Test", "model_license": "MIT", "offline_capable": True,
        "open_source": True, "commercial_use_allowed": True, "sample_path": None,
    }
    data.update(overrides)
    return VoiceProfileInput(**data)


def test_create_voice_profile_requires_confirm(db: Database):
    with db.session() as session, pytest.raises(VoiceApplyNotConfirmedError):
        create_voice_profile(session, _profile_input(), confirm=False)


def test_create_voice_profile_persists_all_disclosure_fields(db: Database):
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        assert profile.id is not None
        assert profile.engine == "stub"
        assert profile.model_license == "MIT"
        assert profile.offline_capable is True
        assert profile.open_source is True
        assert profile.commercial_use_allowed is True


def test_create_voice_profile_rejects_empty_name(db: Database):
    with db.session() as session, pytest.raises(ValueError):
        create_voice_profile(session, _profile_input(name="   "), confirm=True)


def test_create_voice_profile_rejects_duplicate_name(db: Database):
    with db.session() as session:
        create_voice_profile(session, _profile_input(name="Dup"), confirm=True)
        with pytest.raises(ValueError):
            create_voice_profile(session, _profile_input(name="Dup"), confirm=True)


def test_list_and_get_voice_profiles(db: Database):
    with db.session() as session:
        create_voice_profile(session, _profile_input(name="A"), confirm=True)
        create_voice_profile(session, _profile_input(name="B"), confirm=True)
        profiles = list_voice_profiles(session)
        assert [p.name for p in profiles] == ["A", "B"]
        found = get_voice_profile(session, profiles[0].id)
        assert found is not None and found.name == "A"
        assert get_voice_profile(session, 999999) is None


def test_delete_voice_profile_requires_confirm(db: Database):
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        with pytest.raises(VoiceApplyNotConfirmedError):
            delete_voice_profile(session, profile.id, confirm=False, confirm_name=profile.name)


def test_delete_voice_profile_requires_exact_name_match(db: Database):
    """§28/Prinzip #6: Loeschen braucht eine VERSCHAERFTE Bestaetigung -
    der blosse confirm=True-Flag reicht nicht, der Name muss wiederholt
    werden."""
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        with pytest.raises(VoiceDeleteNotConfirmedError):
            delete_voice_profile(session, profile.id, confirm=True, confirm_name="falscher Name")
        # Profil existiert nach fehlgeschlagenem Loeschversuch weiterhin.
        assert get_voice_profile(session, profile.id) is not None


def test_delete_voice_profile_succeeds_with_exact_name(db: Database):
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        profile_id = profile.id
        delete_voice_profile(session, profile_id, confirm=True, confirm_name=profile.name)
        assert get_voice_profile(session, profile_id) is None


def test_delete_voice_profile_not_found(db: Database):
    with db.session() as session, pytest.raises(VoiceProfileNotFoundError):
        delete_voice_profile(session, 999999, confirm=True, confirm_name="x")


def test_delete_voice_profile_never_touches_sample_file_on_disk(db: Database, tmp_path: Path):
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF....fake")
    with db.session() as session:
        profile = create_voice_profile(
            session, _profile_input(sample_path=str(sample)), confirm=True
        )
        delete_voice_profile(session, profile.id, confirm=True, confirm_name=profile.name)
    assert sample.exists()  # Prinzip #4: Originaldateien werden nie geloescht


def test_synthesize_requires_confirm(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        with pytest.raises(VoiceApplyNotConfirmedError):
            synthesize_text(
                session, provider, profile.id, "Hallo", output_dir=tmp_path, confirm=False
            )
        assert provider.calls == []


def test_synthesize_rejects_empty_text(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        with pytest.raises(ValueError):
            synthesize_text(
                session, provider, profile.id, "   ", output_dir=tmp_path, confirm=True
            )


def test_synthesize_unknown_profile(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session, pytest.raises(VoiceProfileNotFoundError):
        synthesize_text(
            session, provider, 999999, "Hallo", output_dir=tmp_path, confirm=True
        )


def test_synthesize_creates_new_file_and_history_row(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        row = synthesize_text(
            session, provider, profile.id, "Hallo Welt", output_dir=tmp_path,
            export_format="wav", confirm=True,
        )
        assert Path(row.output_path).exists()
        assert row.duration_seconds == pytest.approx(1.0)
        assert row.sample_rate == 16000
        assert row.engine == "stub"
        assert row.is_test_phrase is False


def test_synthesize_exports_to_mp3(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        row = synthesize_text(
            session, provider, profile.id, "Export-Test", output_dir=tmp_path,
            export_format="mp3", confirm=True,
        )
        assert row.output_path.endswith(".mp3")
        assert Path(row.output_path).exists()


def test_synthesize_propagates_provider_unavailable(db: Database, tmp_path: Path):
    provider = StubTTSProvider(available=False)
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        with pytest.raises(TTSProviderUnavailableError):
            synthesize_text(
                session, provider, profile.id, "Hallo", output_dir=tmp_path, confirm=True
            )


def test_synthesize_wraps_render_failure(db: Database, tmp_path: Path):
    provider = StubTTSProvider(fail=True)
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        with pytest.raises(VoiceSynthesisError):
            synthesize_text(
                session, provider, profile.id, "Hallo", output_dir=tmp_path, confirm=True
            )


def test_list_syntheses_filters_by_profile(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session:
        p1 = create_voice_profile(session, _profile_input(name="P1"), confirm=True)
        p2 = create_voice_profile(session, _profile_input(name="P2"), confirm=True)
        synthesize_text(session, provider, p1.id, "Eins", output_dir=tmp_path, confirm=True)
        synthesize_text(session, provider, p2.id, "Zwei", output_dir=tmp_path, confirm=True)
        synthesize_text(session, provider, p1.id, "Drei", output_dir=tmp_path, confirm=True)

        all_rows = list_syntheses(session)
        assert len(all_rows) == 3
        p1_rows = list_syntheses(session, profile_id=p1.id)
        assert len(p1_rows) == 2
        assert all(r.voice_profile_id == p1.id for r in p1_rows)


def test_get_test_phrase_for_language_known_and_fallback():
    assert "GENESIS" in get_test_phrase_for_language("de")
    assert "GENESIS" in get_test_phrase_for_language("en")
    assert "GENESIS" in get_test_phrase_for_language("xx")  # unbekannt -> Fallback
    assert "GENESIS" in get_test_phrase_for_language(None)


def test_cascade_delete_removes_synthesis_history(db: Database, tmp_path: Path):
    provider = StubTTSProvider()
    with db.session() as session:
        profile = create_voice_profile(session, _profile_input(), confirm=True)
        synthesize_text(session, provider, profile.id, "Hallo", output_dir=tmp_path, confirm=True)
        profile_id = profile.id
        delete_voice_profile(session, profile_id, confirm=True, confirm_name=profile.name)
        assert list_syntheses(session, profile_id=profile_id) == []
