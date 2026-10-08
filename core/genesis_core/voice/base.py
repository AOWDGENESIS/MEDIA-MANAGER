"""TTS-Engine-Interface (§28/§29, ADR-0018).

Jeder Provider muss:
- klar angeben, ob er lokal/offline arbeitet (`is_local`/`requires_internet`),
- Audio NIEMALS automatisch irgendwohin uebertragen (§56) - `synthesize()`
  schreibt ausschliesslich in eine lokale Datei,
- austauschbar sein (Prinzip #8/#13, §29 "Die Voice Engine muss austauschbar
  sein") - der Aufrufer (voice/engine.py) kennt nur dieses Interface, nie
  eine konkrete Engine-Implementierung direkt.

Die vier Pflichtangaben aus §28 ("Welche Engine? Welche Modell-Lizenz?
Offline? Open Source? Kommerzielle Nutzung erlaubt?") werden bewusst NICHT
hier am Provider festgemacht, sondern am `VoiceProfile` (siehe db/models.py)
- ein und derselbe Provider (z.B. "piper") kann mehrere Modelle/Stimmen mit
UNTERSCHIEDLICHEN Modell-Lizenzen bedienen (z.B. Stimmen aus
rhasspy/piper-voices sind einzeln MIT-lizenziert, aber nicht alle fuer
kommerzielle Nutzung freigegeben - siehe jeweilige MODEL_CARD).
"""
from __future__ import annotations

import abc
import dataclasses


@dataclasses.dataclass
class TTSResult:
    output_path: str
    duration_seconds: float
    sample_rate: int
    engine_name: str


class TTSProviderUnavailableError(RuntimeError):
    """Der Provider ist aktuell nicht einsatzbereit (deaktiviert, Modell
    fehlt, Bibliothek nicht installiert, ...). Wird NIE stillschweigend
    verschluckt (Prinzip #19/§37) - der Aufrufer zeigt dem Nutzer eine
    klare Fehlermeldung statt eines stillen Fehlschlags."""


class TTSProvider(abc.ABC):
    """Abstraktes Interface, austauschbar (Prinzip #8/#13, §29)."""

    name: str = "base"
    is_local: bool = True
    requires_internet: bool = False

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Prueft, ob der Provider grundsaetzlich einsatzbereit ist (z.B.
        ob die benoetigte Bibliothek installiert ist). Prueft NICHT, ob ein
        bestimmtes Modell existiert - das macht `synthesize()`."""

    @abc.abstractmethod
    def synthesize(
        self,
        text: str,
        *,
        model_path: str | None,
        output_wav_path: str,
    ) -> TTSResult:
        """Erzeugt eine WAV-Datei unter `output_wav_path` (immer eine NEUE
        Datei, siehe `voice/engine.py`). Wirft `TTSProviderUnavailableError`
        bei fehlendem Modell/fehlender Engine statt stillschweigend eine
        leere/kaputte Datei zu erzeugen."""
