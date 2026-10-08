"""Tests für `SearchFiltersDialog` (§9, Gap-Analyse Gap C - erweiterte
Bibliotheks-Suchfilter)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.dialogs.search_filters_dialog import (  # noqa: E402
    SearchFiltersDialog,
    count_active_filters,
)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_default_filters_are_all_none():
    dialog = SearchFiltersDialog()
    filters = dialog.get_filters()
    assert count_active_filters(filters) == 0
    assert all(v is None for v in filters.values())


def test_text_fields_map_to_filter_keys():
    dialog = SearchFiltersDialog()
    dialog.genre_edit.setText("Elektro")
    dialog.source_edit.setText("YouTube")
    dialog.person_edit.setText("Erika Mustermann")
    dialog.series_edit.setText("Die grosse Reihe")
    dialog.extension_edit.setText("mp3")

    filters = dialog.get_filters()
    assert filters["genre"] == "Elektro"
    assert filters["source"] == "YouTube"
    assert filters["person"] == "Erika Mustermann"
    assert filters["series"] == "Die grosse Reihe"
    assert filters["extension"] == "mp3"


def test_whitespace_only_text_counts_as_unset():
    dialog = SearchFiltersDialog()
    dialog.genre_edit.setText("   ")
    filters = dialog.get_filters()
    assert filters["genre"] is None


def test_year_season_episode_spin_boxes():
    dialog = SearchFiltersDialog()
    dialog.year_spin.setValue(2021)
    dialog.season_spin.setValue(2)
    dialog.episode_spin.setValue(5)
    filters = dialog.get_filters()
    assert filters["year"] == 2021
    assert filters["season"] == 2
    assert filters["episode_number"] == 5


def test_size_fields_convert_mb_to_bytes():
    dialog = SearchFiltersDialog()
    dialog.min_size_mb_spin.setValue(10)
    dialog.max_size_mb_spin.setValue(500)
    filters = dialog.get_filters()
    assert filters["min_size_bytes"] == 10_000_000
    assert filters["max_size_bytes"] == 500_000_000


def test_duration_fields_pass_through_seconds():
    dialog = SearchFiltersDialog()
    dialog.min_duration_spin.setValue(120)
    dialog.max_duration_spin.setValue(600)
    filters = dialog.get_filters()
    assert filters["min_duration_s"] == 120
    assert filters["max_duration_s"] == 600


def test_lufs_filter_only_applied_when_enabled():
    dialog = SearchFiltersDialog()
    dialog.min_lufs_spin.setValue(-20)
    dialog.max_lufs_spin.setValue(-10)
    # Checkbox NICHT aktiviert -> Werte duerfen nicht in den Filtern landen,
    # auch wenn die Spinboxen bereits einen Wert != Default haben.
    filters = dialog.get_filters()
    assert filters["min_lufs"] is None
    assert filters["max_lufs"] is None

    dialog.lufs_enabled_check.setChecked(True)
    filters2 = dialog.get_filters()
    assert filters2["min_lufs"] == -20
    assert filters2["max_lufs"] == -10


def test_ai_status_combo_maps_to_backend_value():
    dialog = SearchFiltersDialog()
    index = dialog.ai_status_combo.findData("ai_generated")
    assert index >= 0
    dialog.ai_status_combo.setCurrentIndex(index)
    filters = dialog.get_filters()
    assert filters["ai_status"] == "ai_generated"


def test_ai_status_any_maps_to_none():
    dialog = SearchFiltersDialog()
    assert dialog.ai_status_combo.currentData() == ""
    filters = dialog.get_filters()
    assert filters["ai_status"] is None


def test_boolean_flag_checkboxes():
    dialog = SearchFiltersDialog()
    dialog.quality_issues_check.setChecked(True)
    dialog.missing_metadata_check.setChecked(True)
    dialog.missing_cover_check.setChecked(True)
    dialog.duplicate_only_check.setChecked(True)
    filters = dialog.get_filters()
    assert filters["has_quality_issues"] is True
    assert filters["missing_metadata"] is True
    assert filters["missing_cover"] is True
    assert filters["duplicate_only"] is True


def test_initial_filters_prefill_fields():
    initial = {
        "genre": "Elektro",
        "year": 2020,
        "has_quality_issues": True,
        "min_lufs": -20,
        "max_lufs": -10,
        "ai_status": "hybrid",
    }
    dialog = SearchFiltersDialog(initial_filters=initial)
    assert dialog.genre_edit.text() == "Elektro"
    assert dialog.year_spin.value() == 2020
    assert dialog.quality_issues_check.isChecked()
    assert dialog.lufs_enabled_check.isChecked()
    assert dialog.min_lufs_spin.value() == -20
    assert dialog.max_lufs_spin.value() == -10
    assert dialog.ai_status_combo.currentData() == "hybrid"


def test_reset_clears_all_fields_back_to_defaults():
    dialog = SearchFiltersDialog()
    dialog.genre_edit.setText("Elektro")
    dialog.year_spin.setValue(2020)
    dialog.quality_issues_check.setChecked(True)
    dialog.lufs_enabled_check.setChecked(True)

    dialog._reset_all_fields()

    filters = dialog.get_filters()
    assert count_active_filters(filters) == 0


def test_count_active_filters_ignores_falsy_values():
    assert count_active_filters({"a": None, "b": "", "c": False, "d": 0}) == 0
    assert count_active_filters({"a": "x", "b": 1, "c": True}) == 3
