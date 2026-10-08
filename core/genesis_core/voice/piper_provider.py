"""Piper-Anbindung (§28/§29, ADR-0018).

Piper (OHF-Voice/piper1-gpl, GPL-3.0-or-later) ist eine schnelle, rein
lokale VITS/ONNX-Sprachsynthese ohne GPU-Zwang - laeuft vollstaendig
offline, keine Netzwerkanfrage waehrend der Synthese (echte
Sandbox-Messung: Modell+Phonemizer-Daten sind im Python-Paket bzw. den
lokalen Modelldateien enthalten, siehe ADR-0018 fuer die Lizenzdetails).

Wichtig: die Modelldateien selbst (.onnx + .onnx.json) werden NIE automatisch
heruntergeladen - der Nutzer muss sie bewusst beschaffen und beim Anlegen
eines Voice-Profils auf den lokalen Pfad verweisen (Prinzip #17, §56).
`scripts/setup_voice_studio.sh` laedt zu Testzwecken zwei kleine Stimmen
(Deutsch/Englisch) aus dem oeffentlichen rhasspy/piper-voices-Repository.
"""
from __future__ import annotations

import wave
from pathlib import Path

from genesis_core.logutil import get_logger
from genesis_core.voice.base import TTSProvider, TTSProviderUnavailableError, TTSResult

log = get_logger("PiperTTSProvider")


class PiperTTSProvider(TTSProvider):
    name = "piper"
    is_local = True
    requires_internet = False

    def __init__(self) -> None:
        # Kleiner Cache geladener Modelle (ONNX-Laden ist der teuerste
        # Schritt, ~1-2s) - gleiche Modelldatei wird bei wiederholten
        # Syntheseanfragen nicht erneut von der Platte geladen.
        self._voice_cache: dict[str, object] = {}

    def is_available(self) -> bool:
        try:
            import piper  # noqa: F401
        except ImportError:
            return False
        return True

    def _load_voice(self, model_path: str):
        if model_path in self._voice_cache:
            return self._voice_cache[model_path]
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise TTSProviderUnavailableError(
                "Das Python-Paket 'piper-tts' ist nicht installiert - siehe "
                "scripts/setup_python_env.sh bzw. scripts/setup_voice_studio.sh."
            ) from exc

        config_path = f"{model_path}.json"
        if not Path(model_path).exists():
            raise TTSProviderUnavailableError(
                f"Piper-Modelldatei nicht gefunden: {model_path}"
            )
        if not Path(config_path).exists():
            raise TTSProviderUnavailableError(
                f"Piper-Konfigurationsdatei nicht gefunden: {config_path} "
                "(wird neben der .onnx-Datei erwartet)."
            )
        voice = PiperVoice.load(model_path, config_path=config_path, use_cuda=False)
        self._voice_cache[model_path] = voice
        return voice

    def synthesize(
        self, text: str, *, model_path: str | None, output_wav_path: str
    ) -> TTSResult:
        if not self.is_available():
            raise TTSProviderUnavailableError(
                "Das Python-Paket 'piper-tts' ist nicht installiert."
            )
        if not model_path:
            raise TTSProviderUnavailableError(
                "Diesem Voice-Profil ist keine Piper-Modelldatei zugeordnet "
                "(model_path fehlt)."
            )
        if not text.strip():
            raise ValueError("Der zu sprechende Text darf nicht leer sein.")

        voice = self._load_voice(model_path)
        Path(output_wav_path).parent.mkdir(parents=True, exist_ok=True)
        with wave.open(output_wav_path, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        with wave.open(output_wav_path, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate) if rate else 0.0

        log.info(
            "Piper-Synthese abgeschlossen: %d Zeichen -> %s (%.2fs, %d Hz)",
            len(text), output_wav_path, duration, rate,
        )
        return TTSResult(
            output_path=output_wav_path,
            duration_seconds=duration,
            sample_rate=rate,
            engine_name=self.name,
        )
