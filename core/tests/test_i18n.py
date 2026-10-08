"""Tests für den zentralen i18n-Mechanismus (§53). Stellt sicher, dass
Übersetzungen nie zu einer Exception/leeren UI-Stelle führen (kein
stiller Fehlschlag) und dass alle vier Pflichtsprachen vollständig und
konsistent (gleiche Schlüsselmenge) vorliegen."""
from __future__ import annotations

import json

import pytest

from genesis_core.i18n import (
    SUPPORTED_LANGUAGES,
    TranslationCatalogError,
    Translator,
)


def test_all_catalogs_load_without_error():
    for lang in SUPPORTED_LANGUAGES:
        Translator(lang)  # darf nicht werfen


def test_all_catalogs_have_identical_key_sets():
    """Kritisch: Fehlt in EN/JA/RU ein Schlüssel, den DE hat, faellt der
    Fallback zwar sauber auf DE zurueck (kein Absturz), aber es waere eine
    unentdeckte Uebersetzungsluecke. Dieser Test deckt das sofort auf."""
    key_sets = {}
    for lang in SUPPORTED_LANGUAGES:
        key_sets[lang] = set(Translator(lang)._load_catalog(lang).keys())

    de_keys = key_sets["de"]
    assert de_keys, "DE-Katalog (Quelle der Wahrheit) darf nicht leer sein."
    for lang in SUPPORTED_LANGUAGES:
        if lang == "de":
            continue
        missing = de_keys - key_sets[lang]
        extra = key_sets[lang] - de_keys
        assert not missing, f"Sprache '{lang}' fehlen Schlüssel: {missing}"
        assert not extra, f"Sprache '{lang}' hat verwaiste Zusatzschlüssel: {extra}"


def test_tr_substitutes_placeholders():
    t = Translator("de")
    result = t.tr("dashboard.card_total")
    assert result == "Gesamt"

    result = t.tr(
        "dashboard.status", version="1.2.3", ai_provider="ollama",
        ai_status="erreichbar", mode="AN",
    )
    assert "1.2.3" in result and "ollama" in result


def test_tr_falls_back_to_english_then_to_key_itself(tmp_path):
    """Deckt die volle Fallback-Kette ab: fehlt ein Schluessel in der
    aktuellen Sprache, aber existiert in Englisch -> Englisch. Existiert er
    nirgends -> der rohe Schluessel selbst (NIE eine Exception oder eine
    leere/None-Rueckgabe, die UI-Code zum Absturz bringen wuerde)."""
    catalog_dir = tmp_path / "i18n"
    catalog_dir.mkdir()
    (catalog_dir / "de.json").write_text(
        json.dumps({"only_in_de": "Nur Deutsch", "shared": "DE-Text"}), encoding="utf-8"
    )
    (catalog_dir / "en.json").write_text(
        json.dumps({"shared": "EN-Text", "only_in_en": "English only"}), encoding="utf-8"
    )
    (catalog_dir / "ja.json").write_text(json.dumps({}), encoding="utf-8")
    (catalog_dir / "ru.json").write_text(json.dumps({}), encoding="utf-8")

    t = Translator("ja", catalog_dir=catalog_dir)
    # Schluessel existiert nur in EN -> Fallback auf EN greift fuer JA
    assert t.tr("only_in_en") == "English only"
    # Schluessel existiert in DE und EN, JA fehlt -> EN hat Vorrang vor DE
    assert t.tr("shared") == "EN-Text"
    # Schluessel existiert nirgends -> roher Schluessel, keine Exception
    assert t.tr("completely_unknown_key") == "completely_unknown_key"


def test_tr_never_raises_on_missing_placeholder_value():
    """Ein Platzhalter in der Vorlage, der nicht per kwargs mitgeliefert
    wird, darf die UI nicht zum Absturz bringen - lieber die unformatierte
    Vorlage zeigen als eine KeyError-Exception hochzureichen."""
    t = Translator("de")
    result = t.tr("dashboard.status")  # keine kwargs mitgegeben
    assert isinstance(result, str)


def test_set_language_rejects_unsupported_code_with_safe_fallback():
    t = Translator("de")
    t.set_language("fr")  # nicht in SUPPORTED_LANGUAGES
    assert t.language == "de"


def test_broken_catalog_raises_clear_error(tmp_path):
    catalog_dir = tmp_path / "i18n"
    catalog_dir.mkdir()
    (catalog_dir / "de.json").write_text("{ this is not valid json", encoding="utf-8")
    (catalog_dir / "en.json").write_text("{}", encoding="utf-8")

    with pytest.raises(TranslationCatalogError):
        Translator("de", catalog_dir=catalog_dir)


def test_rename_dialog_literal_braces_are_preserved_not_treated_as_placeholders():
    """Die Vorlagen-Hinweistexte im Rename-Dialog zeigen Platzhalternamen
    wie '{artist}' als LITERALEN Text an (keine echte Format-Ersetzung).
    Das JSON escaped das als '{{artist}}' - muss nach dem Rendern wieder zu
    genau einem Klammerpaar werden, nicht verschwinden oder crashen."""
    t = Translator("de")
    result = t.tr("rename_dialog.info", count=3)
    assert "{artist}" in result
    assert "{{artist}}" not in result
