from __future__ import annotations

from genesis_core.ai.base import AIProvider, AISuggestion
from genesis_core.ai.null_provider import NullAIProvider
from genesis_core.ai.ollama_provider import OllamaProvider
from genesis_core.config import AISettings


def build_ai_provider(settings: AISettings) -> AIProvider:
    """Fabrikfunktion: erzeugt den konfigurierten Provider (Prinzip #8/#13).

    Gibt niemals einen Cloud-Provider ohne explizite zukuenftige Erweiterung
    zurueck (§56 Default: keine Cloud-KI). Wenn ai.enabled=False, wird immer
    der NullAIProvider verwendet, unabhaengig vom konfigurierten Providernamen.
    """
    if not settings.enabled:
        return NullAIProvider()
    if settings.provider == "ollama":
        return OllamaProvider(
            endpoint=settings.endpoint,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
            embedding_model=settings.embedding_model,
        )
    return NullAIProvider()


__all__ = ["AIProvider", "AISuggestion", "NullAIProvider", "OllamaProvider", "build_ai_provider"]
