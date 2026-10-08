"""Tests gegen die ECHTE Piper-Engine (kein Mock), analog zum
Ollama-Integrationstest in test_ai (§28/§29, ADR-0018).

Werden automatisch uebersprungen, wenn piper-tts nicht installiert ist oder
keine Testmodelle unter GENESIS_PIPER_TEST_VOICES_DIR gefunden werden - so
bleibt die CI-Suite stabil, waehrend lokale/manuelle Laeufe mit echten
Modellen die tatsaechliche Audioerzeugung verifizieren.

Testmodelle werden NICHT ins Repository committed (Groesse/Lizenz) -
siehe scripts/setup_voice_studio.sh, das sie nach /opt/genesis_voices_test
laedt (ausserhalb des Workspace, siehe PROGRESS.md "Ressourcen-Disziplin").
"""
from __future__ import annotations

import os
import wave
from pathlib import Path

import pytest

from genesis_core.voice.base import TTSProviderUnavailableError
from genesis_core.voice.piper_provider import PiperTTSProvider

VOICES_DIR = Path(os.environ.get("GENESIS_PIPER_TEST_VOICES_DIR", "/opt/piper_voices"))
DE_MODEL = VOICES_DIR / "de_DE-thorsten-low.onnx"
EN_MODEL = VOICES_DIR / "en_US-amy-low.onnx"

pytestmark = pytest.mark.skipif(
    not DE_MODEL.exists(), reason="Keine lokalen Piper-Testmodelle gefunden (siehe Moduldocstring)"
)


def test_piper_is_available():
    provider = PiperTTSProvider()
    assert provider.is_available() is True


def test_piper_synthesizes_real_german_audio(tmp_path: Path):
    provider = PiperTTSProvider()
    out = tmp_path / "out.wav"
    result = provider.synthesize(
        "Hallo, dies ist ein echter Test der Piper-Sprachsynthese.",
        model_path=str(DE_MODEL), output_wav_path=str(out),
    )
    assert out.exists()
    assert out.stat().st_size > 1000
    assert result.duration_seconds > 1.0
    assert result.sample_rate > 0
    assert result.engine_name == "piper"
    with wave.open(str(out), "rb") as wav_file:
        assert wav_file.getnframes() > 0


@pytest.mark.skipif(not EN_MODEL.exists(), reason="Kein englisches Testmodell gefunden")
def test_piper_synthesizes_real_english_audio(tmp_path: Path):
    provider = PiperTTSProvider()
    out = tmp_path / "out_en.wav"
    result = provider.synthesize(
        "Hello, this is a real test of the Piper speech engine.",
        model_path=str(EN_MODEL), output_wav_path=str(out),
    )
    assert out.exists()
    assert result.duration_seconds > 1.0


def test_piper_caches_loaded_voice_across_calls(tmp_path: Path):
    provider = PiperTTSProvider()
    out1 = tmp_path / "a.wav"
    out2 = tmp_path / "b.wav"
    provider.synthesize("Erster Satz.", model_path=str(DE_MODEL), output_wav_path=str(out1))
    provider.synthesize("Zweiter Satz.", model_path=str(DE_MODEL), output_wav_path=str(out2))
    assert str(DE_MODEL) in provider._voice_cache
    assert out1.exists() and out2.exists()


def test_piper_raises_clear_error_for_missing_model(tmp_path: Path):
    provider = PiperTTSProvider()
    out = tmp_path / "out.wav"
    with pytest.raises(TTSProviderUnavailableError):
        provider.synthesize(
            "Text", model_path=str(tmp_path / "does_not_exist.onnx"),
            output_wav_path=str(out),
        )


def test_piper_rejects_empty_text(tmp_path: Path):
    provider = PiperTTSProvider()
    out = tmp_path / "out.wav"
    with pytest.raises(ValueError):
        provider.synthesize("   ", model_path=str(DE_MODEL), output_wav_path=str(out))
