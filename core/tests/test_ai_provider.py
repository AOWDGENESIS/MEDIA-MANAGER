import httpx
import pytest

from genesis_core.ai import build_ai_provider
from genesis_core.ai.null_provider import NullAIProvider
from genesis_core.ai.ollama_provider import OllamaProvider
from genesis_core.config import AISettings


def test_ai_disabled_by_default_uses_null_provider():
    provider = build_ai_provider(AISettings())
    assert isinstance(provider, NullAIProvider)
    assert provider.suggest_text_fields("irgendein Kontext", ["genre"]) == []


def test_ollama_provider_selected_when_enabled():
    settings = AISettings(enabled=True, provider="ollama")
    provider = build_ai_provider(settings)
    assert isinstance(provider, OllamaProvider)


def _ollama_reachable() -> bool:
    try:
        return httpx.get("http://127.0.0.1:11434/api/version", timeout=1.0).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama laeuft in dieser Umgebung nicht")
def test_ollama_integration_suggests_fields():
    """Optionaler Integrationstest (ADR-0003): wird uebersprungen statt
    fehlzuschlagen, wenn kein lokaler Ollama-Dienst erreichbar ist."""
    provider = OllamaProvider(model="qwen2.5:0.5b", timeout_seconds=20.0)
    suggestions = provider.suggest_text_fields(
        context="Dateiname: 'Metallica - Enter Sandman.flac', Genre unbekannt.",
        fields=["genre"],
    )
    assert isinstance(suggestions, list)
    for s in suggestions:
        assert s.is_ai_generated is True
        assert s.model_name.startswith("ollama:")
        assert s.confidence is not None
