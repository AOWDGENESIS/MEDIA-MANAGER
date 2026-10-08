"""Smoke-Tests fuer die Phase-9-Haertungsansichten: Job-Warteschlange
(§35/§36), Fehler-Center (§37), Diagnose (§38), Backups (§40), Plugins
(§34). Laeuft unter QT_QPA_PLATFORM=offscreen (siehe
test_download_center_view.py fuer das etablierte Testmuster) mit Fake-
API-Clients statt eines echten Core Service.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox

from genesis_ui.api_client import GenesisAPIError
from genesis_ui.views.backups_view import BackupsView
from genesis_ui.views.diagnostics_view import DiagnosticsView
from genesis_ui.views.error_center_view import ErrorCenterView
from genesis_ui.views.job_queue_view import JobQueueView
from genesis_ui.views.plugins_view import PluginsView


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def _no_blocking_dialogs(monkeypatch):
    """QMessageBox.exec()/question() wuerden unter offscreen auf eine nie
    kommende Nutzerinteraktion warten - defensiv immer "Ja"/OK simulieren,
    damit Tests, die versehentlich einen Dialog ausloesen, nicht haengen."""
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Ok)


# --- Job-Warteschlange -------------------------------------------------------

class _FakeJobsAPI:
    def __init__(self):
        self._jobs = {
            "JOB-1": {
                "id": "JOB-1", "job_type": "scan", "status": "running",
                "created_at": "2026-01-01T00:00:00", "started_at": None, "finished_at": None,
                "total_items": 10, "processed_items": 4, "error_count": 0, "warning_count": 1,
                "current_item": "/music/a.mp3",
            },
            "JOB-2": {
                "id": "JOB-2", "job_type": "rename", "status": "paused",
                "created_at": "2026-01-01T00:00:00", "started_at": None, "finished_at": None,
                "total_items": 0, "processed_items": 0, "error_count": 0, "warning_count": 0,
                "current_item": None,
            },
        }
        self.actions: list[tuple[str, str]] = []

    def list_jobs(self, limit: int = 100) -> list[dict]:
        return list(self._jobs.values())

    def pause_job(self, job_id: str) -> dict:
        self.actions.append(("pause", job_id))
        self._jobs[job_id]["status"] = "paused"
        return self._jobs[job_id]

    def resume_job(self, job_id: str) -> dict:
        self.actions.append(("resume", job_id))
        self._jobs[job_id]["status"] = "running"
        return self._jobs[job_id]

    def cancel_job(self, job_id: str) -> dict:
        self.actions.append(("cancel", job_id))
        self._jobs[job_id]["status"] = "cancelled"
        return self._jobs[job_id]


def test_job_queue_view_lists_jobs_and_enables_actions_by_status() -> None:
    api = _FakeJobsAPI()
    view = JobQueueView(api)
    assert view.tree.topLevelItemCount() == 2

    running_item = view.tree.topLevelItem(0)
    view.tree.setCurrentItem(running_item)
    assert view.pause_btn.isEnabled()
    assert not view.resume_btn.isEnabled()
    assert view.cancel_btn.isEnabled()

    paused_item = view.tree.topLevelItem(1)
    view.tree.setCurrentItem(paused_item)
    assert not view.pause_btn.isEnabled()
    assert view.resume_btn.isEnabled()


def test_job_queue_view_pause_and_cancel_call_api() -> None:
    api = _FakeJobsAPI()
    view = JobQueueView(api)
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    view._on_pause_clicked()
    assert ("pause", "JOB-1") in api.actions

    view._on_cancel_clicked()  # QMessageBox.question gemockt -> Yes
    assert ("cancel", "JOB-1") in api.actions


def test_job_queue_view_handles_load_failure_without_crashing() -> None:
    class _FailingAPI:
        def list_jobs(self, limit: int = 100):
            raise GenesisAPIError("Core Service nicht erreichbar")

    view = JobQueueView(_FailingAPI())
    assert "Core Service nicht erreichbar" in view.status_label.text()


# --- Fehler-Center -----------------------------------------------------------

class _FakeErrorsAPI:
    def __init__(self):
        self.resolved: list[str] = []

    def list_errors(self, limit: int = 200, unresolved_only: bool = True) -> list[dict]:
        rows = [
            {
                "error_id": "ERR-20260101-0001", "timestamp": "2026-01-01T00:00:00",
                "component": "api:/scan", "file_path": "/music/a.mp3", "action": "POST",
                "message": "Unerwarteter Fehler", "technical_details": "Traceback...",
                "solution_hint": "Erneut versuchen.", "resolved": False,
            },
        ]
        if unresolved_only:
            return [r for r in rows if not r["resolved"]]
        return rows

    def resolve_error(self, error_id: str) -> dict:
        self.resolved.append(error_id)
        return {"error_id": error_id, "resolved": True}


def test_error_center_view_lists_and_resolves() -> None:
    api = _FakeErrorsAPI()
    view = ErrorCenterView(api)
    assert view.tree.topLevelItemCount() == 1
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    assert "Erneut versuchen" in view.detail_label.text()
    assert view.resolve_btn.isEnabled()
    view._on_resolve_clicked()
    assert api.resolved == ["ERR-20260101-0001"]


# --- Diagnose -----------------------------------------------------------------

class _FakeDiagnosticsAPI:
    def run_diagnostics(self) -> dict:
        return {
            "generated_at": "2026-01-01T00:00:00",
            "overall_status": "warning",
            "checks": [
                {"check_id": "db", "label": "Datenbank", "status": "ok", "message": "OK"},
                {"check_id": "plugins", "label": "Plugins", "status": "warning",
                 "message": "1 Plugin fehlgeschlagen"},
            ],
        }


def test_diagnostics_view_shows_checks() -> None:
    view = DiagnosticsView(_FakeDiagnosticsAPI())
    assert view.tree.topLevelItemCount() == 2
    assert "warning" not in view.overall_label.text()  # uebersetzt, nicht roh


# --- Backups ------------------------------------------------------------------

class _FakeBackupsAPI:
    def __init__(self):
        self.created: list[str] = []
        self.restored: list[int] = []

    def list_backups(self, backup_type=None, limit=50) -> list[dict]:
        return [
            {"id": 1, "backup_type": "database", "created_at": "2026-01-01T00:00:00",
             "size_bytes": 2048, "path": "/data/backups/db_1.sqlite"},
        ]

    def create_db_backup(self) -> dict:
        self.created.append("db")
        return {}

    def restore_backup(self, backup_id: int, *, confirm: bool) -> dict:
        assert confirm is True
        self.restored.append(backup_id)
        return {}


def test_backups_view_lists_and_restores() -> None:
    api = _FakeBackupsAPI()
    view = BackupsView(api)
    assert view.tree.topLevelItemCount() == 1
    view.tree.setCurrentItem(view.tree.topLevelItem(0))
    view._on_restore_clicked()  # QMessageBox.question gemockt -> Yes
    assert api.restored == [1]


def test_backups_view_create_db_backup_calls_api() -> None:
    api = _FakeBackupsAPI()
    view = BackupsView(api)
    view._on_create_db_clicked()
    assert api.created == ["db"]


# --- Plugins ------------------------------------------------------------------

class _FakePluginsAPI:
    def __init__(self):
        self.reloaded = False

    def list_plugins(self) -> dict:
        return {
            "plugins_dir": "/data/plugins",
            "plugins": [
                {"plugin_id": "example-pipe-separated-exporter", "plugin_kind": "exporter",
                 "display_name": "Pipe Exporter", "version": "0.1.0", "author": "GENESIS",
                 "license": "MIT", "loaded_successfully": True, "load_error": None},
                {"plugin_id": "broken_example", "plugin_kind": "unknown",
                 "display_name": "?", "version": "?", "author": "?", "license": "?",
                 "loaded_successfully": False, "load_error": "RuntimeError: absichtlich kaputt"},
            ],
        }

    def reload_plugins(self) -> dict:
        self.reloaded = True
        return self.list_plugins()


def test_plugins_view_shows_working_and_broken_plugin() -> None:
    api = _FakePluginsAPI()
    view = PluginsView(api)
    assert view.tree.topLevelItemCount() == 2
    statuses = [view.tree.topLevelItem(i).text(6) for i in range(2)]
    assert any("absichtlich kaputt" in s for s in statuses)


def test_plugins_view_reload_button_calls_api() -> None:
    api = _FakePluginsAPI()
    view = PluginsView(api)
    view._on_reload_clicked()
    assert api.reloaded is True
