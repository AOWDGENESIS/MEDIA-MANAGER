"""Audio-Fingerprinting (§12/§13).

Nutzt Chromaprint (`fpcalc`-CLI, LGPL-2.1, siehe
licenses/THIRD-PARTY-LICENSES.md) fuer akustische Fingerabdruecke. Ein
Fingerprint identifiziert eine Aufnahme anhand ihres Audioinhalts,
unabhaengig von Dateiname/Tags - Grundlage fuer:
- AcoustID-Abgleich (Wiedererkennung ohne verlaessliche Tags)
- Duplikaterkennung ueber Formate/Encodings hinweg (Phase 3)
- Wiedererkennung nach Verschieben/Umbenennen (§ Pfad-Relokation)

WICHTIG: Fingerprinting liest die Datei nur (Prinzip #4/#5) und veraendert
sie nie.
"""
from __future__ import annotations

from genesis_core.fingerprint.chromaprint import (
    FingerprintError,
    FingerprintResult,
    compute_fingerprint,
    is_fpcalc_available,
)

__all__ = [
    "FingerprintError",
    "FingerprintResult",
    "compute_fingerprint",
    "is_fpcalc_available",
]
