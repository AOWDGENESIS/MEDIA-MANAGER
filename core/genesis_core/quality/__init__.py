"""Qualitätsanalyse (§20) - öffentliche Fassade, analog zu den übrigen
Phase-3-Engines (`genesis_core.loudness`/`cutter`/`convert`/`duplicates`)."""
from __future__ import annotations

from genesis_core.quality.engine import QualityReport, QualitySnapshot, analyze_quality

__all__ = ["QualityReport", "QualitySnapshot", "analyze_quality"]
