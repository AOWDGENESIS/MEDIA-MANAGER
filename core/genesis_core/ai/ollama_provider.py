"""Ollama-Provider - lokale KI ueber die Ollama-HTTP-API (ADR-0003, §46).

Standard-Endpoint http://127.0.0.1:11434, konfigurierbares Modell
(Standard: qwen2.5:0.5b - klein genug fuer bescheidene Hardware, Apache-2.0
lizenziert). Keine Cloud-Anfrage, kein Netzwerkzugriff ausserhalb 127.0.0.1.
"""
from __future__ import annotations

import json

import httpx

from genesis_core.ai.base import AIProvider, AISuggestion
from genesis_core.logutil import get_logger

log = get_logger("OllamaProvider")


class OllamaProvider(AIProvider):
    name = "ollama"
    is_local = True
    requires_internet = False

    def __init__(
        self, endpoint: str = "http://127.0.0.1:11434", model: str = "qwen2.5:0.5b",
        timeout_seconds: float = 30.0, embedding_model: str = "all-minilm",
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        # Separates (kleineres) Modell fuer /api/embed (§26) - die meisten
        # reinen Text-Generierungsmodelle unterstuetzen keine Embeddings.
        self.embedding_model = embedding_model

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.endpoint}/api/version", timeout=2.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def suggest_text_fields(self, context: str, fields: list[str]) -> list[AISuggestion]:
        if not fields:
            return []
        prompt = self._build_prompt(context, fields)
        try:
            resp = httpx.post(
                f"{self.endpoint}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Ollama-Anfrage fehlgeschlagen: %s", exc)
            return []

        raw_response = resp.json().get("response", "")
        try:
            parsed: dict = json.loads(raw_response)
        except json.JSONDecodeError:
            log.warning("Ollama lieferte kein gueltiges JSON: %r", raw_response[:200])
            return []

        suggestions: list[AISuggestion] = []
        for field in fields:
            value = parsed.get(field)
            if value is None or str(value).strip() == "":
                continue
            suggestions.append(
                AISuggestion(
                    field_name=field,
                    field_value=str(value),
                    model_name=f"ollama:{self.model}",
                    model_version=None,
                    confidence=0.6,  # konservativ, da lokale LLM-Heuristik ohne Audioanalyse
                    prompt=prompt,
                )
            )
        return suggestions

    def embed_text(self, text: str) -> list[float] | None:
        """Liefert einen Embedding-Vektor via Ollamas `/api/embed` (§26).

        Nutzt bewusst ein eigenes, dediziertes Embedding-Modell statt des
        Text-Generierungsmodells - reine Chat-/Instruct-Modelle lehnen
        `/api/embed`-Anfragen haeufig ab ("does not support embeddings").
        Liefert None statt einer Exception, wenn Ollama nicht erreichbar
        ist oder das Embedding-Modell lokal fehlt (dann bleibt die
        semantische Suche einfach leer/deaktiviert, kein Absturz).
        """
        try:
            resp = httpx.post(
                f"{self.endpoint}/api/embed",
                json={"model": self.embedding_model, "input": text},
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Ollama-Embedding-Anfrage fehlgeschlagen: %s", exc)
            return None

        data = resp.json()
        if "error" in data:
            log.warning("Ollama-Embedding-Fehler: %s", data["error"])
            return None
        embeddings = data.get("embeddings")
        if not embeddings or not isinstance(embeddings, list):
            return None
        return list(embeddings[0])

    @staticmethod
    def _build_prompt(context: str, fields: list[str]) -> str:
        field_list = ", ".join(fields)
        return (
            "Du bist ein Metadaten-Assistent fuer eine lokale Medienbibliothek. "
            "Antworte AUSSCHLIESSLICH als JSON-Objekt mit genau diesen Schluesseln: "
            f"{field_list}. "
            "Erfinde keine Fakten, die nicht aus dem Kontext ableitbar sind - "
            "wenn du dir unsicher bist, setze den Wert auf einen kurzen, klar als "
            "Vermutung erkennbaren Text oder lasse ihn leer.\n\n"
            f"KONTEXT:\n{context}\n\nJSON:"
        )
