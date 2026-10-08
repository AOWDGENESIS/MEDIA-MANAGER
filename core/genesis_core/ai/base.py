"""AI-Provider-Interface (§25/§46).

Jeder Provider muss:
- klar angeben, ob er lokal/offline arbeitet,
- ein Ergebnisobjekt liefern, das Modellname/-version, Zeitstempel und
  Konfidenz enthaelt (Prinzip #9), und
- niemals automatisch als "wahr" gelten - der Aufrufer (Metadata-Engine)
  entscheidet ueber Anzeige/Uebernahme nach der "Goldenen Prozesskette".
"""
from __future__ import annotations

import abc
import dataclasses
import datetime as dt


@dataclasses.dataclass
class AISuggestion:
    field_name: str
    field_value: str
    model_name: str
    model_version: str | None
    confidence: float | None
    is_ai_generated: bool = True
    prompt: str | None = None
    created_at: dt.datetime = dataclasses.field(
        default_factory=lambda: dt.datetime.now(dt.UTC)
    )


class AIProvider(abc.ABC):
    """Abstraktes Interface, austauschbar (Prinzip #8/#13/§34 Plugin-System)."""

    name: str = "base"
    is_local: bool = True
    requires_internet: bool = False

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Prueft, ob der Provider aktuell erreichbar/einsatzbereit ist."""

    @abc.abstractmethod
    def suggest_text_fields(
        self, context: str, fields: list[str]
    ) -> list[AISuggestion]:
        """Erzeugt Vorschlaege fuer die angegebenen Metadatenfelder
        (z.B. genre, mood, language, description, tags) basierend auf dem
        gegebenen Kontext (z.B. Dateiname, vorhandene Tags, Transkript-
        Ausschnitt). Erfindet KEINE Fakten ueber die Datei hinaus - liefert
        im Zweifel eine niedrige Confidence statt eine falsche Tatsachen-
        behauptung."""

    @abc.abstractmethod
    def embed_text(self, text: str) -> list[float] | None:
        """Liefert einen lokalen Embedding-Vektor fuer die semantische
        Suche (§26) oder None, wenn der Provider das nicht unterstuetzt
        bzw. nicht erreichbar ist. Niemals eine Cloud-Anfrage (§56)."""
