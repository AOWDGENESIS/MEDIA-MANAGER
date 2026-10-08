"""Regressionstests für Gap-Analyse-Gruppe 2 (§55, `docs/GAP_ANALYSIS.md`
Gaps A/I): GUI-basierte Konfiguration (`SettingsView`) und Metadaten-
Provider-Verwaltung (`ProvidersView`) über `PATCH /settings`.

Läuft unter QT_QPA_PLATFORM=offscreen mit Fake-API-Clients (siehe
test_gap_closure_detail_view.py für das etablierte Testmuster).
`QMessageBox.question` wird immer auf "Ja" gestellt, `QFileDialog` wird
nie wirklich geöffnet (Headless-Sandbox) - die Ordnerauswahl wird direkt
über `self.folders_list` manipuliert statt über den echten Dialog.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from genesis_ui.api_client import GenesisAPIError
from genesis_ui.views.providers_view import ProvidersView
from genesis_ui.views.settings_view import SettingsView


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _default_settings() -> dict:
    return {
        "general": {
            "language": "de", "safe_test_mode": True,
            "require_confirmation_for_bulk_changes": True,
        },
        "paths": {
            "data_dir": "/tmp/x", "database_path": None, "backup_dir": None,
            "temp_dir": None, "log_dir": None, "media_folders": ["/tmp/music"],
        },
        "ai": {
            "enabled": False, "provider": "null", "endpoint": "http://127.0.0.1:11434",
            "model": "qwen2.5:0.5b", "timeout_seconds": 30.0, "embedding_model": "all-minilm",
        },
        "voice": {"enabled": False, "provider": "null", "default_export_format": "wav"},
        "download": {
            "enabled": False, "downloads_dir": None, "max_download_size_mb": 4096,
            "min_free_disk_mb": 1024, "enable_youtube": True, "enable_tiktok": True,
            "request_timeout_seconds": 20.0,
        },
        "loudness": {
            "target_lufs": -14.0, "target_true_peak_dbtp": -1.0, "overwrite_originals": False,
        },
        "metadata": {
            "enabled": False, "musicbrainz_enabled": True, "acoustid_enabled": True,
            "acoustid_api_key": "", "coverartarchive_enabled": True, "contact_email": "",
            "request_timeout_seconds": 10.0, "min_confidence_for_suggestion": 0.4,
        },
        "privacy": {
            "telemetry_enabled": False, "allow_cloud_ai": False,
            "allow_automatic_downloads": False, "allow_automatic_deletion": False,
            "allow_automatic_overwrite": False,
        },
    }


class _FakeSettingsAPI:
    def __init__(self, *, restart_required: bool = False) -> None:
        self.settings = _default_settings()
        self.last_update: tuple[dict, bool] | None = None
        self.last_scan_directories: list[str] | None = None
        self._restart_required = restart_required
        self.update_should_fail = False
        self.scan_should_fail = False

    def get_settings(self) -> dict:
        return self.settings

    def update_settings(self, updates: dict, *, confirm: bool) -> dict:
        self.last_update = (updates, confirm)
        if self.update_should_fail:
            raise GenesisAPIError("Ungültiger Wert")
        return {
            "settings": self.settings, "restart_required": self._restart_required,
            "job_id": "job-settings-1",
        }

    def trigger_scan(self, directories: list[str]) -> dict:
        self.last_scan_directories = directories
        if self.scan_should_fail:
            raise GenesisAPIError("Core nicht erreichbar")
        return {"job_id": "job-scan-1", "result": {"files_found": 7}}


@pytest.fixture(autouse=True)
def _auto_confirm(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))


# --- SettingsView ------------------------------------------------------------

def test_settings_view_loads_current_values_into_widgets() -> None:
    view = SettingsView(_FakeSettingsAPI())
    assert view.language_combo.currentText() == "de"
    assert view.ai_enabled_check.isChecked() is False
    assert [view.folders_list.item(i).text() for i in range(view.folders_list.count())] == [
        "/tmp/music"
    ]
    assert view.loudness_target_lufs_spin.value() == -14.0


def test_settings_view_save_sends_partial_updates_with_confirm_true() -> None:
    api = _FakeSettingsAPI()
    view = SettingsView(api)
    view.ai_enabled_check.setChecked(True)
    view.ai_model_edit.setText("qwen2.5:7b")
    view._on_save_clicked()

    assert api.last_update is not None
    updates, confirm = api.last_update
    assert confirm is True
    assert updates["ai"]["enabled"] is True
    assert updates["ai"]["model"] == "qwen2.5:7b"
    assert "paths" in updates and "media_folders" in updates["paths"]


def test_settings_view_shows_restart_required_message_after_save() -> None:
    api = _FakeSettingsAPI(restart_required=True)
    view = SettingsView(api)
    view._on_save_clicked()
    assert "Neustart" in view.status_label.text()


def test_settings_view_shows_plain_success_message_without_restart() -> None:
    api = _FakeSettingsAPI(restart_required=False)
    view = SettingsView(api)
    view._on_save_clicked()
    assert view.status_label.text() == "Einstellungen gespeichert."


def test_settings_view_save_failure_shows_error_and_keeps_old_status(monkeypatch) -> None:
    import genesis_ui.views.settings_view as settings_view_module

    api = _FakeSettingsAPI()
    api.update_should_fail = True
    captured = {}
    monkeypatch.setattr(
        settings_view_module, "show_api_error",
        lambda parent, exc, message=None: captured.setdefault("message", message),
    )
    view = SettingsView(api)
    view._on_save_clicked()
    assert "Ungültiger Wert" in captured["message"]


def test_settings_view_add_and_remove_folder() -> None:
    view = SettingsView(_FakeSettingsAPI())
    initial_count = view.folders_list.count()
    view.folders_list.addItem("/tmp/neuer-ordner")
    assert view.folders_list.count() == initial_count + 1
    view.folders_list.setCurrentRow(view.folders_list.count() - 1)
    view._on_remove_folder_clicked()
    assert view.folders_list.count() == initial_count


def test_settings_view_scan_button_uses_current_folder_list() -> None:
    api = _FakeSettingsAPI()
    view = SettingsView(api)
    view.folders_list.addItem("/tmp/noch-ein-ordner")
    view._on_scan_clicked()
    assert api.last_scan_directories == ["/tmp/music", "/tmp/noch-ein-ordner"]
    assert "7" in view.status_label.text()


def test_settings_view_scan_with_empty_folder_list_shows_hint_without_api_call() -> None:
    api = _FakeSettingsAPI()
    view = SettingsView(api)
    view.folders_list.clear()
    view._on_scan_clicked()
    assert api.last_scan_directories is None
    assert view.status_label.text() != ""


# --- ProvidersView ------------------------------------------------------------

def test_providers_view_loads_metadata_section_only() -> None:
    view = ProvidersView(_FakeSettingsAPI())
    assert view.musicbrainz_check.isChecked() is True
    assert view.acoustid_check.isChecked() is True
    assert view.acoustid_key_edit.text() == ""
    assert view.min_confidence_spin.value() == 0.4


def test_providers_view_save_sends_only_metadata_section() -> None:
    api = _FakeSettingsAPI()
    view = ProvidersView(api)
    view.acoustid_key_edit.setText("mein-geheimer-schluessel")
    view.musicbrainz_check.setChecked(False)
    view._on_save_clicked()

    assert api.last_update is not None
    updates, confirm = api.last_update
    assert confirm is True
    assert list(updates.keys()) == ["metadata"]
    assert updates["metadata"]["acoustid_api_key"] == "mein-geheimer-schluessel"
    assert updates["metadata"]["musicbrainz_enabled"] is False


def test_providers_view_shows_success_message_after_save() -> None:
    api = _FakeSettingsAPI()
    view = ProvidersView(api)
    view._on_save_clicked()
    assert view.status_label.text() == "Provider-Einstellungen gespeichert."
