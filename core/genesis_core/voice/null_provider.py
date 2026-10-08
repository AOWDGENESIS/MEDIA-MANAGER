"""Sicherer Standard-Provider (§56: keine lokale TTS-Verarbeitung ohne
ausdrueckliche Aktivierung). Wird verwendet, wenn `voice.enabled=False` oder
kein unterstuetzter Provider konfiguriert ist - niemals stillschweigend auf
einen funktionierenden Fallback ausweichen (Prinzip #17: lieber klar
"nicht verfuegbar" melden als ungefragt etwas tun)."""
from __future__ import annotations

from genesis_core.voice.base import TTSProvider, TTSProviderUnavailableError, TTSResult


class NullTTSProvider(TTSProvider):
    name = "null"
    is_local = True
    requires_internet = False

    def is_available(self) -> bool:
        return False

    def synthesize(
        self, text: str, *, model_path: str | None, output_wav_path: str
    ) -> TTSResult:
        raise TTSProviderUnavailableError(
            "Keine lokale TTS-Engine aktiv (voice.enabled=False oder kein "
            "Provider konfiguriert) - bitte in den Einstellungen aktivieren."
        )
