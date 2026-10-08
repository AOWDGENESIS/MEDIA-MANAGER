from __future__ import annotations

from genesis_core.config import VoiceSettings
from genesis_core.voice.base import TTSProvider, TTSProviderUnavailableError, TTSResult
from genesis_core.voice.null_provider import NullTTSProvider
from genesis_core.voice.piper_provider import PiperTTSProvider


def build_tts_provider(settings: VoiceSettings) -> TTSProvider:
    """Fabrikfunktion: erzeugt den konfigurierten TTS-Provider (Prinzip
    #8/#13). Gibt den NullTTSProvider zurueck, wenn `voice.enabled=False`
    ist oder kein unterstuetzter Provider konfiguriert ist (§56: lokale
    Sprachsynthese ist standardmaessig AUS, auch wenn sie nie an die Cloud
    sendet - der Nutzer muss sie bewusst aktivieren)."""
    if not settings.enabled:
        return NullTTSProvider()
    if settings.provider == "piper":
        return PiperTTSProvider()
    return NullTTSProvider()


__all__ = [
    "NullTTSProvider",
    "PiperTTSProvider",
    "TTSProvider",
    "TTSProviderUnavailableError",
    "TTSResult",
    "build_tts_provider",
]
