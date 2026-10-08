"""Katalog bekannter TTS-Engines (§28, ADR-0018).

Liefert NUR unverbindliche Vorschlagswerte fuer die Oberflaeche beim Anlegen
eines neuen Voice-Profils (vorausgefuellte Formularfelder) - der Nutzer sieht
und bestaetigt diese Werte immer explizit, bevor ein Profil gespeichert wird
(Prinzip #9/#17). Die tatsaechlich gespeicherten Werte kommen IMMER aus der
Nutzereingabe, nie automatisch/stillschweigend aus diesem Katalog.

Wichtig: `model_license`/`commercial_use_allowed` im Katalog beschreiben nur
die ENGINE (den Programmcode), NICHT die einzelne Stimme/das Modell - z.B.
sind Piper-Stimmen aus rhasspy/piper-voices separat MIT-lizenziert, aber
nicht alle ausdruecklich fuer kommerzielle Nutzung freigegeben (siehe
jeweilige MODEL_CARD.md der Stimme). Der Nutzer muss das PRO STIMME pruefen
und beim Anlegen des Profils eintragen - siehe ADR-0018.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class EngineCatalogEntry:
    id: str
    label: str
    is_local: bool
    requires_internet: bool
    suggested_engine_license: str
    homepage: str
    notes: str


ENGINE_CATALOG: list[EngineCatalogEntry] = [
    EngineCatalogEntry(
        id="piper",
        label="Piper (lokal, VITS/ONNX, CPU)",
        is_local=True,
        requires_internet=False,
        suggested_engine_license="GPL-3.0-or-later (OHF-Voice/piper1-gpl)",
        homepage="https://github.com/OHF-voice/piper1-gpl",
        notes=(
            "Die Engine selbst ist GPL-3.0-or-later. Einzelne Stimmen-"
            "Modelle (z.B. aus rhasspy/piper-voices) haben eine EIGENE, "
            "separate Lizenz (haeufig MIT) - bitte vor dem Anlegen eines "
            "Profils die MODEL_CARD der jeweiligen Stimme pruefen und die "
            "Lizenz-/Kommerz-Felder entsprechend ausfuellen."
        ),
    ),
]

ENGINE_CATALOG_BY_ID = {entry.id: entry for entry in ENGINE_CATALOG}
