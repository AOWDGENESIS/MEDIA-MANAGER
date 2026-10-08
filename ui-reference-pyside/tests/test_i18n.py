"""Tests für `genesis_ui.i18n` - die bewusst von `genesis_core` ENTKOPPELTE
(ADR-0001/ADR-0009) Translator-Implementierung der PySide6-Referenz-UI.
Dies ist der erste Test für die PySide6-UI-Schicht überhaupt (bisher gab
es dort keine automatisierte Testinfrastruktur, siehe PROGRESS.md Backlog)
- hier bewusst als reiner Logik-Test ohne Qt-Widgets gehalten, damit er
ohne `QT_QPA_PLATFORM=offscreen` in jeder CI läuft.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genesis_ui.i18n import SUPPORTED_LANGUAGES, Translator


def test_does_not_import_genesis_core():
    """Architektur-Wächter-Test (ADR-0001/ADR-0009): Diese Datei darf
    NIEMALS `genesis_core` importieren - die UI ist ein reiner
    REST-API-Präsentations-Client. Prüft das durch echtes Entfernen von
    `core/` aus `sys.path` und Neu-Import des Moduls aus einem frischen
    Modul-Namespace."""
    import importlib

    core_path = str(Path(__file__).resolve().parents[2] / "core")
    original_sys_path = list(sys.path)
    original_modules = dict(sys.modules)
    try:
        sys.path = [p for p in sys.path if Path(p).resolve() != Path(core_path).resolve()]
        for mod_name in list(sys.modules):
            if mod_name == "genesis_core" or mod_name.startswith("genesis_core."):
                del sys.modules[mod_name]
            if mod_name == "genesis_ui.i18n":
                del sys.modules[mod_name]
        module = importlib.import_module("genesis_ui.i18n")
        # Instanziieren, um sicherzugehen, dass zur Laufzeit kein
        # verstecktes Nachladen von genesis_core passiert.
        module.Translator("de")
        assert "genesis_core" not in sys.modules, (
            "genesis_ui.i18n hat genesis_core importiert - verletzt ADR-0001."
        )
    finally:
        sys.path = original_sys_path
        sys.modules.clear()
        sys.modules.update(original_modules)


def test_all_catalogs_load_without_error():
    for lang in SUPPORTED_LANGUAGES:
        Translator(lang)


def test_tr_basic_lookup_and_placeholder():
    t = Translator("de")
    assert t.tr("common.button_close") == "Schließen"
    result = t.tr("rename_dialog.summary", count=5, actionable=3)
    assert "5" in result and "3" in result


def test_tr_unknown_key_returns_key_itself_never_raises():
    t = Translator("en")
    assert t.tr("totally.unknown.key") == "totally.unknown.key"


def _flatten_keys(d: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= _flatten_keys(v, full)
        else:
            keys.add(full)
    return keys


def test_all_languages_have_identical_key_sets():
    """§53 - jede UI-Zeichenkette muss in ALLEN vier Sprachen vorhanden sein.
    Verhindert, dass ein spaeteres Feature (z.B. Phase 8 Download Center)
    versehentlich nur in einer Sprache ergaenzt wird und die UI in den
    anderen Sprachen den rohen i18n-Schluessel statt eines Textes anzeigt."""
    catalog_dir = Path(__file__).resolve().parents[2] / "i18n"
    key_sets = {}
    for lang in SUPPORTED_LANGUAGES:
        with open(catalog_dir / f"{lang}.json", encoding="utf-8") as fh:
            key_sets[lang] = _flatten_keys(json.load(fh))

    reference_lang = "de"
    reference_keys = key_sets[reference_lang]
    assert len(reference_keys) > 0
    for lang, keys in key_sets.items():
        missing = reference_keys - keys
        extra = keys - reference_keys
        assert not missing, f"{lang}.json fehlen Schluessel: {sorted(missing)[:20]}"
        assert not extra, f"{lang}.json hat zusaetzliche Schluessel: {sorted(extra)[:20]}"


def test_catalog_dir_override_via_env(tmp_path, monkeypatch):
    catalog_dir = tmp_path / "i18n"
    catalog_dir.mkdir()
    for lang in SUPPORTED_LANGUAGES:
        (catalog_dir / f"{lang}.json").write_text(
            json.dumps({"greeting": f"hello-{lang}"}), encoding="utf-8"
        )
    t = Translator("ja", catalog_dir=catalog_dir)
    assert t.tr("greeting") == "hello-ja"
