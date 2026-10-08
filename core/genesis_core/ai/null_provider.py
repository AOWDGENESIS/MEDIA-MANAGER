"""Null-Provider: keine KI aktiv. Standard, wenn ai.enabled=False (§56)."""
from __future__ import annotations

from genesis_core.ai.base import AIProvider, AISuggestion


class NullAIProvider(AIProvider):
    name = "null"
    is_local = True
    requires_internet = False

    def is_available(self) -> bool:
        return True

    def suggest_text_fields(self, context: str, fields: list[str]) -> list[AISuggestion]:
        return []

    def embed_text(self, text: str) -> list[float] | None:
        return None
