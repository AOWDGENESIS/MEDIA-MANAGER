"""i18n-Mechanismus der PySide6-Referenz-UI (§53 - keine hartcodierten
UI-Texte).

WICHTIG (Korrektur gegenüber einem ersten Entwurf dieser Datei): Diese UI
ist laut ADR-0001 bewusst ein reiner Präsentations-Client OHNE
Python-Importabhängigkeit auf `genesis_core` (siehe bereits bestehendes
Vorbild in `api_client.py`, das z.B. `TOKEN_FILENAME` bewusst dupliziert
statt `genesis_core.api.security` zu importieren). Ein `from genesis_core
.i18n import tr` hier würde genau diese Architekturregel brechen - auch
wenn beide Prozesse (Core-Service, PySide6-UI) zufällig auf derselben
Maschine laufen, dürfen sie nur über die REST-API gekoppelt sein, nicht
über Python-Importe.

Deshalb: Diese Datei enthält eine EIGENSTÄNDIGE, bewusst kleine
Translator-Implementierung, die dieselben rohen `i18n/<sprache>.json`-
Dateien liest wie `genesis_core/i18n/__init__.py` und
`GenesisMediaManager.Client/I18n/Translator.cs` - geteilt wird nur das
DATENFORMAT (die JSON-Dateien), nicht der Code. Siehe ADR-0009
(DECISIONS.md) für die vollständige Begründung dieser Drei-Implementierungen-
ein-Datenformat-Entscheidung.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("genesis_ui.i18n")

SUPPORTED_LANGUAGES = ("de", "en", "ja", "ru")
DEFAULT_LANGUAGE = "de"
FALLBACK_LANGUAGE = "en"

# Gemeinsame Media-Kind-Beschriftungen (Dashboard-Kacheln UND
# Navigationsbaum zeigen exakt dieselben Wörter - ein Schlüsselsatz statt
# doppelt gepflegter Übersetzungen, siehe i18n/de.json "nav.*").
MEDIA_KIND_LABEL_KEYS = {
    "music": "nav.music",
    "audiobook": "nav.audiobook",
    "movie": "nav.movie",
    "episode": "nav.episode",
    "podcast_episode": "nav.podcast",
    "ai_music": "nav.ai_music",
    "unknown": "nav.unknown",
}


def _default_catalog_dir() -> Path:
    """Repository-Wurzel ausgehend von dieser Datei
    (`ui-reference-pyside/genesis_ui/i18n.py` -> zwei Ebenen hoch) ->
    `i18n/`. Überschreibbar via `GENESIS_I18N_DIR` (z.B. für Tests oder
    ein künftiges gepacktes/eingefrorenes Deployment, bei dem die
    Verzeichnisstruktur anders aussieht)."""
    env_override = os.environ.get("GENESIS_I18N_DIR")
    if env_override:
        return Path(env_override)
    return Path(__file__).resolve().parents[2] / "i18n"


class Translator:
    def __init__(self, language: str = DEFAULT_LANGUAGE, catalog_dir: Path | None = None):
        self.catalog_dir = catalog_dir or _default_catalog_dir()
        self._catalogs: dict[str, dict[str, str]] = {}
        self._warned: set[tuple[str, str]] = set()
        self.language = DEFAULT_LANGUAGE
        self.set_language(language)

    def _load(self, language: str) -> dict[str, str]:
        if language in self._catalogs:
            return self._catalogs[language]
        path = self.catalog_dir / f"{language}.json"
        if not path.exists():
            logger.warning("Sprachkatalog '%s' nicht gefunden - nutze Fallback.", path)
            self._catalogs[language] = {}
            return self._catalogs[language]
        data = json.loads(path.read_text(encoding="utf-8"))
        flat = _flatten(data)
        self._catalogs[language] = flat
        return flat

    def set_language(self, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            logger.warning("Unbekannter Sprachcode '%s' - falle auf '%s' zurück.",
                            language, DEFAULT_LANGUAGE)
            language = DEFAULT_LANGUAGE
        self._load(DEFAULT_LANGUAGE)
        self._load(FALLBACK_LANGUAGE)
        self._load(language)
        self.language = language

    def tr(self, key: str, **kwargs: Any) -> str:
        for candidate in (self.language, FALLBACK_LANGUAGE, DEFAULT_LANGUAGE):
            catalog = self._catalogs.get(candidate, {})
            if key in catalog:
                try:
                    return catalog[key].format(**kwargs)
                except (KeyError, IndexError) as exc:
                    logger.warning("i18n-Platzhalterfehler bei '%s': %s", key, exc)
                    return catalog[key]
        marker = (key, self.language)
        if marker not in self._warned:
            self._warned.add(marker)
            logger.warning("i18n: Schlüssel '%s' fehlt für Sprache '%s'.", key, self.language)
        return key


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = str(value)
    return flat


_default_translator: Translator | None = None


def get_translator() -> Translator:
    global _default_translator
    if _default_translator is None:
        _default_translator = Translator()
    return _default_translator


def configure_default_language(language: str) -> None:
    get_translator().set_language(language)


def tr(key: str, **kwargs: Any) -> str:
    """`from genesis_ui.i18n import tr` - überall in der PySide6-UI statt
    hartcodierter Strings zu verwenden (§53)."""
    return get_translator().tr(key, **kwargs)


__all__ = [
    "MEDIA_KIND_LABEL_KEYS",
    "SUPPORTED_LANGUAGES",
    "Translator",
    "configure_default_language",
    "get_translator",
    "tr",
]
