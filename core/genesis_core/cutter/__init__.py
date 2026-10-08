"""Audio-Cutter (§18, ADR-0011).

Oeffentliche Fassade: Engine (reine Planung/Datenklassen) + FFmpeg-Anbindung
werden hier gebuendelt re-exportiert, analog zu `genesis_core.loudness`.
"""
from __future__ import annotations

from genesis_core.cutter.engine import (
    CutApplyNotConfirmedError,
    CutPlan,
    CutRenderError,
    CutResult,
    InvalidCutSelectionError,
    WaveformGenerationError,
    apply_cut,
    generate_waveform_image,
    plan_cut,
)

__all__ = [
    "CutApplyNotConfirmedError",
    "CutPlan",
    "CutRenderError",
    "CutResult",
    "InvalidCutSelectionError",
    "WaveformGenerationError",
    "apply_cut",
    "generate_waveform_image",
    "plan_cut",
]
