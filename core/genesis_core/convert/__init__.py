"""Konvertierungs-Werkzeug (nav.convert, nicht separat nummeriert im
Originalauftrag - siehe §47 "Technische Medienengine" ("Konvertierung" als
FFmpeg-Einsatzzweck), §34 Plugin-System ("Converter"-Plugin-Typ), §35 Job
Queue ("Konvertierung" als Jobtyp) und §69 Phase 3 ("Konvertierung")).

Oeffentliche Fassade, analog zu `genesis_core.loudness`/`genesis_core.cutter`.
"""
from __future__ import annotations

from genesis_core.convert.engine import (
    ConversionApplyNotConfirmedError,
    ConversionPlan,
    ConversionRenderError,
    ConversionResult,
    InvalidConversionRequestError,
    apply_conversion,
    plan_conversion,
)

__all__ = [
    "ConversionApplyNotConfirmedError",
    "ConversionPlan",
    "ConversionRenderError",
    "ConversionResult",
    "InvalidConversionRequestError",
    "apply_conversion",
    "plan_conversion",
]
