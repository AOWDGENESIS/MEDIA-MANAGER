"""Zentraler i18n-Mechanismus (§53): Alle UI-Texte kommen aus
Sprachressourcen, niemals hartcodiert.

Architekturentscheidung (siehe ADR-0009 in DECISIONS.md):
- Die eigentlichen Übersetzungen liegen als reine JSON-Dateien im
  Repository-Wurzelverzeichnis unter `i18n/<sprachcode>.json` ab - NICHT in
  `core/` oder `ui-reference-pyside/`, weil sowohl die Python-UI
  (PySide6-Referenz) als auch die .NET-UI (WPF-Ziel) dieselben Quelldateien
  konsumieren sollen (siehe `GenesisMediaManager.Client/I18n/Translator.cs`
  für das C#-Äquivalent dieses Moduls). Ein geteiltes, reines JSON-Format
  ohne Build-Schritt (kein gettext-.mo-Kompilieren, kein Qt-Linguist-
  `.qm`-Build) wurde bewusst gewählt, weil es:
  1. ohne zusätzliche Toolchain in BEIDEN Stacks lesbar ist
     (`json`-Stdlib in Python, `System.Text.Json` in .NET),
  2. Übersetzer/innen nur eine einzige Dateiart pro Sprache anfassen
     müssen, unabhängig davon, welcher UI-Client den Text später zeigt,
  3. zur Laufzeit ohne Neustart/Neukompilierung austauschbar ist.
- `de.json` ist die Quelle der Wahrheit (jeder Schlüssel MUSS dort
  existieren). Fehlt ein Schlüssel in einer anderen Sprache, wird auf
  Englisch, dann auf den rohen Schlüssel selbst zurückgefallen - niemals
  eine leere/blanke UI-Stelle (kein stiller Fehlschlag, Prinzip aus §37).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("genesis.i18n")

SUPPORTED_LANGUAGES = ("de", "en", "ja", "ru")
DEFAULT_LANGUAGE = "de"
FALLBACK_LANGUAGE = "en"


def default_catalog_dir() -> Path:
    """Findet das `i18n/`-Verzeichnis an der Repository-Wurzel, ausgehend
    von diesem Modul (`core/genesis_core/i18n/__init__.py` -> drei Ebenen
    hoch -> Repo-Wurzel -> `i18n/`). Funktioniert unabhängig davon, von wo
    der Prozess gestartet wurde (CLI, API-Server, Tests)."""
    return Path(__file__).resolve().parents[3] / "i18n"


class TranslationCatalogError(RuntimeError):
    """Die Sprachressourcen konnten nicht geladen werden (z.B. defekte
    JSON-Datei) - wird bewusst NICHT verschluckt, damit ein kaputter
    Sprachressourcen-Stand sofort auffällt statt leise falsche/fehlende
    Texte zu zeigen."""


class Translator:
    """Lädt Sprachkataloge und löst Schlüssel zu lokalisiertem Text auf.

    Nicht thread-sicher für `set_language` unter paralleler Nutzung -
    für diese Single-User-Desktop-App ausreichend (vgl. ADR-0001).
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE, catalog_dir: Path | None = None):
        self.catalog_dir = catalog_dir or default_catalog_dir()
        self._catalogs: dict[str, dict[str, str]] = {}
        self._missing_keys_warned: set[tuple[str, str]] = set()
        self.language = DEFAULT_LANGUAGE  # wird gleich per set_language gesetzt
        self.set_language(language)

    def _load_catalog(self, language: str) -> dict[str, str]:
        if language in self._catalogs:
            return self._catalogs[language]
        path = self.catalog_dir / f"{language}.json"
        if not path.exists():
            if language in (DEFAULT_LANGUAGE, FALLBACK_LANGUAGE):
                raise TranslationCatalogError(
                    f"Sprachkatalog fehlt: {path} (benötigt als Fallback-Basis)."
                )
            logger.warning("Sprachkatalog für '%s' nicht gefunden (%s) - nutze Fallback.",
                            language, path)
            self._catalogs[language] = {}
            return self._catalogs[language]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TranslationCatalogError(
                f"Sprachkatalog '{path}' ist beschädigt/nicht lesbar: {exc}"
            ) from exc
        flat = _flatten(data)
        self._catalogs[language] = flat
        return flat

    def set_language(self, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            logger.warning(
                "Unbekannter Sprachcode '%s' - falle auf '%s' zurück (§53: DE/EN/JA/RU).",
                language, DEFAULT_LANGUAGE,
            )
            language = DEFAULT_LANGUAGE
        # Default- und Fallback-Katalog sind immer vorab geladen, damit
        # tr() nie mitten im Betrieb unerwartet eine Exception wirft, nur
        # weil die aktuelle Sprache gewechselt wurde.
        self._load_catalog(DEFAULT_LANGUAGE)
        self._load_catalog(FALLBACK_LANGUAGE)
        self._load_catalog(language)
        self.language = language

    def tr(self, key: str, **kwargs: Any) -> str:
        """Löst `key` (z.B. "rename_dialog.title") zu lokalisiertem Text
        auf. Reihenfolge: aktuelle Sprache -> Englisch -> Deutsch (Quelle
        der Wahrheit) -> roher Schlüssel (niemals eine Exception/leere
        Stelle in der UI, Prinzip "kein stiller Fehlschlag").
        `**kwargs` werden per `str.format(**kwargs)` eingesetzt, z.B.
        `tr("rename_dialog.summary", count=5)` für "{count} Datei(en) ...".
        """
        for candidate_lang in (self.language, FALLBACK_LANGUAGE, DEFAULT_LANGUAGE):
            catalog = self._catalogs.get(candidate_lang, {})
            if key in catalog:
                template = catalog[key]
                if candidate_lang != self.language:
                    self._warn_missing_once(key, self.language)
                try:
                    return template.format(**kwargs)
                except (KeyError, IndexError) as exc:
                    logger.warning(
                        "i18n-Platzhalterfehler bei Schlüssel '%s' (Sprache '%s'): %s",
                        key, candidate_lang, exc,
                    )
                    return template
        self._warn_missing_once(key, self.language)
        return key

    def _warn_missing_once(self, key: str, language: str) -> None:
        marker = (key, language)
        if marker not in self._missing_keys_warned:
            self._missing_keys_warned.add(marker)
            logger.warning(
                "i18n: Schlüssel '%s' fehlt für Sprache '%s' (Fallback aktiv).",
                key, language,
            )


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    """Wandelt ein verschachteltes JSON-Objekt
    (`{"rename_dialog": {"title": "..."}}`) in flache Punkt-Schlüssel um
    (`"rename_dialog.title"`), damit Kataloge thematisch strukturiert
    geschrieben werden können, der Zugriff im Code aber ein einfacher
    String bleibt."""
    flat: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, full_key))
        else:
            flat[full_key] = str(value)
    return flat


# Prozessweite Standardinstanz - von beiden UI-Schichten (PySide6-Referenz)
# sowie vom Core selbst (z.B. für Error-Keys in zukünftigen API-Antworten,
# siehe Backlog in docs/REVIEW_LOG.md) nutzbar, ohne dass jede Stelle ihren
# eigenen Translator verwalten muss. `configure_default_language` wird
# beim App-Start einmal mit der tatsächlichen Einstellung aufgerufen.
_default_translator: Translator | None = None


def get_translator() -> Translator:
    global _default_translator
    if _default_translator is None:
        _default_translator = Translator()
    return _default_translator


def configure_default_language(language: str) -> None:
    get_translator().set_language(language)


def tr(key: str, **kwargs: Any) -> str:
    """Bequemlichkeitsfunktion: `from genesis_core.i18n import tr`."""
    return get_translator().tr(key, **kwargs)
