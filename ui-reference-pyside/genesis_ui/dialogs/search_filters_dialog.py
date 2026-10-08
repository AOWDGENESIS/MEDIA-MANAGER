"""Dialog für die erweiterten Bibliotheks-Suchfilter (§9, Gap-Analyse Gap C).

Der bestehende `MediaTableView`-Suchschlitz deckte bisher nur einen reinen
Dateiname-/Pfad-Substring ab. §9 fordert deutlich mehr Such-/Filterfelder
(Interpret, Album, Genre, Autor, Sprecher, Serie, Staffel, Episode, Quelle,
Jahr, KI-Status, Format, Dateigröße, Dauer, Lautheit, Qualitätsverdacht,
fehlende Metadaten, fehlendes Cover, Duplikate). Diese Felder sind über
`search` (Freitext, deckt Interpret/Album/Genre/Autor/Sprecher/Serie/Quelle
serverseitig bereits ab) sowie dedizierte Parameter in `GET /media`
ansteuerbar (siehe `genesis_core.library.build_media_search_statement`) -
dieser Dialog bietet dafür eine eigene GUI statt die Nutzer auf
Rohabfrage-Parameter zu verweisen.

Rein lesend/filternd (Prinzip #4/#5) - verändert keine Datensätze, sendet
nur zusätzliche Query-Parameter an den bereits bestehenden `GET /media`.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.i18n import tr

#: Keine Auswahl getroffen - Feld bleibt beim Senden unberücksichtigt (nicht
#: zu verwechseln mit einem tatsächlichen leeren KI-Status-Wert).
_AI_STATUS_ANY = ""

AI_STATUS_CHOICES = [
    (_AI_STATUS_ANY, "search_filters_dialog.ai_status_any"),
    ("ai_generated", "search_filters_dialog.ai_status_ai_generated"),
    ("human_generated", "search_filters_dialog.ai_status_human_generated"),
    ("hybrid", "search_filters_dialog.ai_status_hybrid"),
    ("unknown", "search_filters_dialog.ai_status_unknown"),
]


class SearchFiltersDialog(QDialog):
    """Sammelt alle in §9 geforderten erweiterten Filter in einem Formular
    und liefert sie über `get_filters()` als flaches Dict zurück, das
    `MediaTableView` direkt an `api.list_media(**filters)` durchreicht."""

    def __init__(self, initial_filters: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("search_filters_dialog.window_title"))
        self.resize(480, 560)

        root = QVBoxLayout(self)

        text_group = QGroupBox(tr("search_filters_dialog.group_text"))
        text_form = QFormLayout(text_group)
        self.genre_edit = QLineEdit()
        text_form.addRow(tr("search_filters_dialog.genre_label"), self.genre_edit)
        self.source_edit = QLineEdit()
        text_form.addRow(tr("search_filters_dialog.source_label"), self.source_edit)
        self.person_edit = QLineEdit()
        text_form.addRow(tr("search_filters_dialog.person_label"), self.person_edit)
        self.series_edit = QLineEdit()
        text_form.addRow(tr("search_filters_dialog.series_label"), self.series_edit)
        self.extension_edit = QLineEdit()
        self.extension_edit.setPlaceholderText("mp3, mp4, m4b, …")
        text_form.addRow(tr("search_filters_dialog.extension_label"), self.extension_edit)
        root.addWidget(text_group)

        numeric_group = QGroupBox(tr("search_filters_dialog.group_numeric"))
        numeric_form = QFormLayout(numeric_group)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(0, 2200)
        self.year_spin.setSpecialValueText(tr("search_filters_dialog.any_value"))
        numeric_form.addRow(tr("search_filters_dialog.year_label"), self.year_spin)

        season_row = QHBoxLayout()
        self.season_spin = QSpinBox()
        self.season_spin.setRange(0, 999)
        self.season_spin.setSpecialValueText(tr("search_filters_dialog.any_value"))
        self.episode_spin = QSpinBox()
        self.episode_spin.setRange(0, 9999)
        self.episode_spin.setSpecialValueText(tr("search_filters_dialog.any_value"))
        season_row.addWidget(self.season_spin)
        season_row.addWidget(self.episode_spin)
        season_wrapper = QWidget()
        season_wrapper.setLayout(season_row)
        numeric_form.addRow(
            tr("search_filters_dialog.season_episode_label"), season_wrapper
        )

        size_row = QHBoxLayout()
        self.min_size_mb_spin = QDoubleSpinBox()
        self.min_size_mb_spin.setRange(0, 1_000_000)
        self.min_size_mb_spin.setSuffix(" MB")
        self.max_size_mb_spin = QDoubleSpinBox()
        self.max_size_mb_spin.setRange(0, 1_000_000)
        self.max_size_mb_spin.setSuffix(" MB")
        size_row.addWidget(self.min_size_mb_spin)
        size_row.addWidget(self.max_size_mb_spin)
        size_wrapper = QWidget()
        size_wrapper.setLayout(size_row)
        numeric_form.addRow(tr("search_filters_dialog.size_range_label"), size_wrapper)

        duration_row = QHBoxLayout()
        self.min_duration_spin = QDoubleSpinBox()
        self.min_duration_spin.setRange(0, 999_999)
        self.min_duration_spin.setSuffix(" s")
        self.max_duration_spin = QDoubleSpinBox()
        self.max_duration_spin.setRange(0, 999_999)
        self.max_duration_spin.setSuffix(" s")
        duration_row.addWidget(self.min_duration_spin)
        duration_row.addWidget(self.max_duration_spin)
        duration_wrapper = QWidget()
        duration_wrapper.setLayout(duration_row)
        numeric_form.addRow(
            tr("search_filters_dialog.duration_range_label"), duration_wrapper
        )

        lufs_row = QHBoxLayout()
        self.min_lufs_spin = QDoubleSpinBox()
        self.min_lufs_spin.setRange(-60, 10)
        self.min_lufs_spin.setValue(-60)
        self.max_lufs_spin = QDoubleSpinBox()
        self.max_lufs_spin.setRange(-60, 10)
        self.max_lufs_spin.setValue(10)
        lufs_row.addWidget(self.min_lufs_spin)
        lufs_row.addWidget(self.max_lufs_spin)
        lufs_wrapper = QWidget()
        lufs_wrapper.setLayout(lufs_row)
        numeric_form.addRow(tr("search_filters_dialog.lufs_range_label"), lufs_wrapper)
        self.lufs_enabled_check = QCheckBox(tr("search_filters_dialog.lufs_enabled_label"))
        numeric_form.addRow("", self.lufs_enabled_check)

        root.addWidget(numeric_group)

        choice_group = QGroupBox(tr("search_filters_dialog.group_choice"))
        choice_form = QFormLayout(choice_group)
        self.ai_status_combo = QComboBox()
        for value, label_key in AI_STATUS_CHOICES:
            self.ai_status_combo.addItem(tr(label_key), userData=value)
        choice_form.addRow(tr("search_filters_dialog.ai_status_label"), self.ai_status_combo)
        root.addWidget(choice_group)

        flags_group = QGroupBox(tr("search_filters_dialog.group_flags"))
        flags_layout = QVBoxLayout(flags_group)
        self.quality_issues_check = QCheckBox(
            tr("search_filters_dialog.quality_issues_label")
        )
        self.missing_metadata_check = QCheckBox(
            tr("search_filters_dialog.missing_metadata_label")
        )
        self.missing_cover_check = QCheckBox(tr("search_filters_dialog.missing_cover_label"))
        self.duplicate_only_check = QCheckBox(tr("search_filters_dialog.duplicate_only_label"))
        for checkbox in (
            self.quality_issues_check,
            self.missing_metadata_check,
            self.missing_cover_check,
            self.duplicate_only_check,
        ):
            flags_layout.addWidget(checkbox)
        root.addWidget(flags_group)

        if initial_filters:
            self._apply_initial_filters(initial_filters)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Reset | QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self._reset_all_fields)
        root.addWidget(buttons)

    # -- Vorbelegung/Reset ----------------------------------------------------

    def _apply_initial_filters(self, filters: dict) -> None:
        if filters.get("genre"):
            self.genre_edit.setText(str(filters["genre"]))
        if filters.get("source"):
            self.source_edit.setText(str(filters["source"]))
        if filters.get("person"):
            self.person_edit.setText(str(filters["person"]))
        if filters.get("series"):
            self.series_edit.setText(str(filters["series"]))
        if filters.get("extension"):
            self.extension_edit.setText(str(filters["extension"]))
        if filters.get("year"):
            self.year_spin.setValue(int(filters["year"]))
        if filters.get("season"):
            self.season_spin.setValue(int(filters["season"]))
        if filters.get("episode_number"):
            self.episode_spin.setValue(int(filters["episode_number"]))
        if filters.get("min_size_bytes"):
            self.min_size_mb_spin.setValue(filters["min_size_bytes"] / 1_000_000)
        if filters.get("max_size_bytes"):
            self.max_size_mb_spin.setValue(filters["max_size_bytes"] / 1_000_000)
        if filters.get("min_duration_s"):
            self.min_duration_spin.setValue(filters["min_duration_s"])
        if filters.get("max_duration_s"):
            self.max_duration_spin.setValue(filters["max_duration_s"])
        if filters.get("min_lufs") is not None or filters.get("max_lufs") is not None:
            self.lufs_enabled_check.setChecked(True)
            if filters.get("min_lufs") is not None:
                self.min_lufs_spin.setValue(filters["min_lufs"])
            if filters.get("max_lufs") is not None:
                self.max_lufs_spin.setValue(filters["max_lufs"])
        if filters.get("ai_status"):
            index = self.ai_status_combo.findData(filters["ai_status"])
            if index >= 0:
                self.ai_status_combo.setCurrentIndex(index)
        self.quality_issues_check.setChecked(bool(filters.get("has_quality_issues")))
        self.missing_metadata_check.setChecked(bool(filters.get("missing_metadata")))
        self.missing_cover_check.setChecked(bool(filters.get("missing_cover")))
        self.duplicate_only_check.setChecked(bool(filters.get("duplicate_only")))

    def _reset_all_fields(self) -> None:
        self.genre_edit.clear()
        self.source_edit.clear()
        self.person_edit.clear()
        self.series_edit.clear()
        self.extension_edit.clear()
        self.year_spin.setValue(self.year_spin.minimum())
        self.season_spin.setValue(self.season_spin.minimum())
        self.episode_spin.setValue(self.episode_spin.minimum())
        self.min_size_mb_spin.setValue(0)
        self.max_size_mb_spin.setValue(0)
        self.min_duration_spin.setValue(0)
        self.max_duration_spin.setValue(0)
        self.min_lufs_spin.setValue(-60)
        self.max_lufs_spin.setValue(10)
        self.lufs_enabled_check.setChecked(False)
        self.ai_status_combo.setCurrentIndex(0)
        self.quality_issues_check.setChecked(False)
        self.missing_metadata_check.setChecked(False)
        self.missing_cover_check.setChecked(False)
        self.duplicate_only_check.setChecked(False)

    # -- Ergebnis ---------------------------------------------------------------

    def get_filters(self) -> dict:
        """Liefert nur tatsächlich gesetzte Filter (leere/Default-Werte
        werden als `None` weggelassen, damit `api.list_media(**filters)`
        sie korrekt ignoriert statt die Bibliothek fälschlich leerzufiltern)."""
        filters: dict = {
            "genre": self.genre_edit.text().strip() or None,
            "source": self.source_edit.text().strip() or None,
            "person": self.person_edit.text().strip() or None,
            "series": self.series_edit.text().strip() or None,
            "extension": self.extension_edit.text().strip() or None,
            "year": self.year_spin.value() or None,
            "season": self.season_spin.value() or None,
            "episode_number": self.episode_spin.value() or None,
            "min_size_bytes": (
                int(self.min_size_mb_spin.value() * 1_000_000)
                if self.min_size_mb_spin.value() > 0
                else None
            ),
            "max_size_bytes": (
                int(self.max_size_mb_spin.value() * 1_000_000)
                if self.max_size_mb_spin.value() > 0
                else None
            ),
            "min_duration_s": self.min_duration_spin.value() or None,
            "max_duration_s": self.max_duration_spin.value() or None,
            "ai_status": self.ai_status_combo.currentData() or None,
            "has_quality_issues": self.quality_issues_check.isChecked() or None,
            "missing_metadata": self.missing_metadata_check.isChecked() or None,
            "missing_cover": self.missing_cover_check.isChecked() or None,
            "duplicate_only": self.duplicate_only_check.isChecked() or None,
        }
        if self.lufs_enabled_check.isChecked():
            filters["min_lufs"] = self.min_lufs_spin.value()
            filters["max_lufs"] = self.max_lufs_spin.value()
        else:
            filters["min_lufs"] = None
            filters["max_lufs"] = None
        return filters


def count_active_filters(filters: dict) -> int:
    """Reine Hilfsfunktion (unabhängig von Qt testbar) - zählt, wie viele
    der erweiterten Filter aktuell tatsächlich gesetzt sind, für die
    Statusanzeige in `MediaTableView` ("Filter aktiv (3)")."""
    return sum(1 for value in filters.values() if value not in (None, "", False))
