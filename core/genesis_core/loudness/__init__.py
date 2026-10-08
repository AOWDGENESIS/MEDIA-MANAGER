"""Loudness-Engine (§19, Phase 3).

Siehe ADR-0010 (DECISIONS.md) fuer die volle Begruendung der
Technologieentscheidung. Kurzfassung: statt `pyloudnorm` (misst nur
Integrated-LUFS/LRA, hat KEINE True-Peak-Unterstuetzung nach ITU-R
BS.1770 Annex 2) wird FFmpegs eingebauter `loudnorm`-Filter genutzt - er
ist bereits eine Projektabhaengigkeit (Scanner nutzt ffprobe), implementiert
EBU R128/ITU-R BS.1770 vollstaendig inklusive True Peak, und liefert sowohl
die Messwerte (Pass 1, JSON) als auch die eigentliche Normalisierung
(Pass 2) aus einem einzigen, gut getesteten Werkzeug.

Oeffentliche API:
- `measure_loudness(path)` - reine Messung, keine Dateiaenderung.
- `plan_normalization(measurement, ...)` - reine Berechnung (Zielgewinn,
  Ausgabepfad, Warnungen), KEIN ffmpeg-Aufruf.
- `apply_normalization(plan, user_confirmed=True)` - fuehrt Pass 2 aus,
  erzeugt IMMER eine NEUE Datei (Original wird nie veraendert, Prinzip #4/#5).
"""
from genesis_core.loudness.engine import (
    AUDIO_MEDIA_KINDS,
    LoudnessMeasurement,
    LoudnessMeasurementError,
    NormalizationApplyNotConfirmedError,
    NormalizationPlan,
    NormalizationResult,
    apply_normalization,
    measure_loudness,
    plan_normalization,
)

__all__ = [
    "AUDIO_MEDIA_KINDS",
    "LoudnessMeasurement",
    "LoudnessMeasurementError",
    "NormalizationApplyNotConfirmedError",
    "NormalizationPlan",
    "NormalizationResult",
    "apply_normalization",
    "measure_loudness",
    "plan_normalization",
]
