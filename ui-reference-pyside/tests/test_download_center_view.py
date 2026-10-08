"""Smoke-Test fuer `DownloadCenterView` (§30-§32, Phase 8, ADR-0019).

Laeuft unter QT_QPA_PLATFORM=offscreen (siehe PROGRESS.md - Hinweis zur
Qt-Testausfuehrung in dieser Sandbox). Nutzt einen Fake-API-Client statt
eines echten laufenden Core-Service (reine UI-Verdrahtungspruefung,
kein Netzwerk-/Prozess-Overhead in der Testsuite).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from genesis_ui.views.download_center_view import DownloadCenterView


class _FakeAPI:
    def __init__(self):
        self.imported_urls: list[str] = []
        self.imported_local_paths: list[str] = []

    def list_download_providers(self) -> dict:
        return {
            "enabled": True,
            "providers": [
                {"id": "local_file", "display_name": "Lokale Datei", "requires_internet": False},
                {"id": "spotify", "display_name": "Spotify", "requires_internet": False},
            ],
        }

    def detect_download_source(self, url: str) -> dict:
        if "spotify" in url:
            return {"provider_id": "spotify", "display_name": "Spotify"}
        return {"provider_id": "direct_url", "display_name": "Direkte Medien-URL"}

    def check_download_availability(self, url: str) -> dict:
        if "spotify" in url:
            return {"provider_id": "spotify", "available": False, "reason": "DRM-geschuetzt"}
        return {"provider_id": "direct_url", "available": True, "reason": None}

    def fetch_download_metadata(self, url: str) -> dict:
        return {"title": "Test", "uploader": "Test-Uploader", "duration_seconds": 125, "license": None}

    def list_download_options(self, url: str) -> dict:
        return {
            "provider_id": "direct_url",
            "options": [
                {"option_id": "default", "label": "Original", "approx_size_bytes": 1024 * 1024},
            ],
        }

    def import_download(self, url: str, *, option_id: str = "default", confirm: bool) -> dict:
        assert confirm is True
        self.imported_urls.append(url)
        return {
            "job_id": "JOB-TEST-00001", "media_file_id": 1,
            "absolute_path": "/tmp/fake/out.mp3", "suggested_filename": "out.mp3", "warnings": [],
        }

    def import_local_file(self, path: str, *, confirm: bool) -> dict:
        assert confirm is True
        self.imported_local_paths.append(path)
        return {
            "job_id": "JOB-TEST-00002", "media_file_id": 2,
            "absolute_path": "/tmp/fake/local.wav", "suggested_filename": None, "warnings": [],
        }


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_view_instantiates_and_shows_status() -> None:
    view = DownloadCenterView(_FakeAPI())
    assert "Lokale Datei" in view.status_banner.text()


def test_detect_and_availability_flow_for_blocked_source() -> None:
    view = DownloadCenterView(_FakeAPI())
    view.url_edit.setText("https://open.spotify.com/track/abc")
    view._on_detect_clicked()
    assert view._detected_provider == "spotify"
    view._on_check_availability_clicked()
    log_text = view.url_result_log.toPlainText()
    assert "DRM-geschuetzt" in log_text


def test_list_options_populates_tree() -> None:
    view = DownloadCenterView(_FakeAPI())
    view.url_edit.setText("https://example.com/file.mp3")
    view._on_list_options_clicked()
    assert view.options_tree.topLevelItemCount() == 1
    assert view._selected_option_id == "default"


def test_url_required_without_crashing_on_empty_input(monkeypatch) -> None:
    view = DownloadCenterView(_FakeAPI())
    # QMessageBox.warning würde unter offscreen auf Interaktion warten -
    # fuer den Test wird nur geprueft, dass kein Absturz/Exception auftritt.
    import genesis_ui.views.download_center_view as mod

    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: None)
    view.url_edit.setText("")
    view._on_detect_clicked()  # darf nicht werfen


def test_local_file_required_without_crashing(monkeypatch) -> None:
    view = DownloadCenterView(_FakeAPI())
    import genesis_ui.views.download_center_view as mod

    monkeypatch.setattr(mod.QMessageBox, "warning", lambda *a, **k: None)
    view.local_path_edit.setText("")
    view._on_local_import_clicked()  # darf nicht werfen
