"""Regressionstests für die Einbindung der neuen `PlayerBarWidget` (§60,
Gap-Analyse Gap G) in `MediaTableView`.

Folgt dem in `test_gap_closure_detail_view.py` etablierten Muster: Fake-API
statt echtem Core-Service, `QT_QPA_PLATFORM=offscreen`. `player_bar.play()`
selbst wird NICHT wirklich aufgerufen/geprüft (keine hörbare Wiedergabe in
der Sandbox verifizierbar) - stattdessen wird `load_and_play` per
monkeypatch durch eine aufzeichnende Fake-Funktion ersetzt und nur die
Verdrahtung (welcher Pfad/Titel/welche Art wird übergeben, wann ist der
Button aktiv) geprüft.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.views.media_table import MediaTableView  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeAPI:
    """Liefert zwei Testdateien unterschiedlicher Art (Musikstück + Film),
    um die kind-abhängige Video-Sichtbarkeit und die Mehrfachauswahl-Regel
    (Abspielen nur bei genau einer ausgewählten Zeile) zu prüfen."""

    def list_media(self, kind=None, search=None, limit=500):
        return {
            "items": [
                {
                    "id": 1,
                    "kind": "track",
                    "filename": "song.mp3",
                    "extension": "mp3",
                    "size_bytes": 12345,
                    "absolute_path": "/tmp/song.mp3",
                },
                {
                    "id": 2,
                    "kind": "movie",
                    "filename": "film.mp4",
                    "extension": "mp4",
                    "size_bytes": 999999,
                    "absolute_path": "/tmp/film.mp4",
                },
            ]
        }

    def media_detail(self, media_id: int) -> dict:
        filename = "song.mp3" if media_id == 1 else "film.mp4"
        return {
            "absolute_path": f"/tmp/{filename}",
            "file_exists_on_disk": True,
            "filename": filename,
            "directory": "/tmp",
            "size_bytes": 12345,
            "extension": filename.rsplit(".", 1)[-1],
            "mtime": "2026-01-01T00:00:00",
            "content_hash_sha256": "abc123",
            "technical": {"duration_s": 180},
            "track": None,
            "has_embedded_artwork": False,
        }

    def get_quality(self, media_id: int):
        return None

    def get_artwork_bytes(self, media_id: int):
        return None

    def list_loudness(self, media_id: int) -> list[dict]:
        return []

    def get_ai_metadata(self, media_id: int) -> list[dict]:
        return []

    def list_media_sources(self, media_id: int) -> list[dict]:
        return []


def _build_view() -> MediaTableView:
    view = MediaTableView(_FakeAPI(), None, "Alle Medien")
    view.refresh()
    return view


def test_player_bar_is_embedded_and_initially_idle():
    view = _build_view()
    assert view.player_bar is not None
    assert not view.play_btn.isEnabled()


def test_play_button_enabled_only_for_single_selection():
    view = _build_view()
    view.table.selectRow(0)
    view._on_selection_changed()
    assert view.play_btn.isEnabled()

    view.table.selectAll()
    view._on_selection_changed()
    assert not view.play_btn.isEnabled()

    view.table.clearSelection()
    view._on_selection_changed()
    assert not view.play_btn.isEnabled()


def test_clicking_play_loads_selected_track_into_player_bar(monkeypatch):
    view = _build_view()
    calls = []
    monkeypatch.setattr(
        view.player_bar,
        "load_and_play",
        lambda path, title, kind=None: calls.append((path, title, kind)),
    )

    view.table.selectRow(0)
    view._on_selection_changed()
    view._on_play_clicked()

    assert calls == [("/tmp/song.mp3", "song.mp3", "track")]


def test_clicking_play_passes_movie_kind_for_video_file(monkeypatch):
    view = _build_view()
    calls = []
    monkeypatch.setattr(
        view.player_bar,
        "load_and_play",
        lambda path, title, kind=None: calls.append((path, title, kind)),
    )

    view.table.selectRow(1)
    view._on_selection_changed()
    view._on_play_clicked()

    assert calls == [("/tmp/film.mp4", "film.mp4", "movie")]


def test_play_clicked_without_selection_is_a_no_op(monkeypatch):
    view = _build_view()
    calls = []
    monkeypatch.setattr(
        view.player_bar,
        "load_and_play",
        lambda path, title, kind=None: calls.append((path, title, kind)),
    )

    view.table.clearSelection()
    view._on_play_clicked()

    assert calls == []


def test_refresh_stops_and_clears_player_bar(monkeypatch):
    view = _build_view()
    calls = []
    monkeypatch.setattr(view.player_bar, "stop_and_clear", lambda: calls.append("stopped"))

    view.refresh()

    assert calls == ["stopped"]
