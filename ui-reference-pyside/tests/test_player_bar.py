"""Tests für `PlayerBarWidget` (§60, Gap-Analyse G - eingebauter
Bibliotheksplayer).

Tatsächliche Tonausgabe ist in der Linux-Sandbox ohne Audiogerät nicht
hörbar prüfbar (siehe PROGRESS.md) - getestet wird daher die Verdrahtung:
Zustandsuebergaenge, Zeit-/Lautstaerke-/Fehleranzeige, Video-Sichtbarkeit.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from genesis_ui.widgets.player_bar import PlayerBarWidget, format_time  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_format_time_without_hours():
    assert format_time(0) == "00:00"
    assert format_time(12345) == "00:12"
    assert format_time(65000) == "01:05"


def test_format_time_with_hours():
    assert format_time(3661000) == "1:01:01"


def test_format_time_clamps_negative():
    assert format_time(-500) == "00:00"


def test_initial_state_disabled(qapp):
    pb = PlayerBarWidget()
    assert not pb.play_pause_btn.isEnabled()
    assert not pb.stop_btn.isEnabled()
    assert not pb.seek_slider.isEnabled()
    assert pb._video_widget.isHidden()
    assert pb.title_label.text() == "Keine Wiedergabe aktiv."


def test_duration_and_position_update_labels_and_slider(qapp):
    pb = PlayerBarWidget()
    pb._on_duration_changed(125_000)
    assert pb.duration_label.text() == "02:05"
    assert pb.seek_slider.maximum() == 125_000
    pb._on_position_changed(30_000)
    assert pb.position_label.text() == "00:30"
    assert pb.seek_slider.value() == 30_000


def test_position_update_does_not_fight_user_drag(qapp):
    pb = PlayerBarWidget()
    pb._on_duration_changed(60_000)
    pb.seek_slider.setSliderDown(True)
    pb.seek_slider.setValue(10_000)
    pb._on_position_changed(55_000)
    # Waehrend der Nutzer selbst zieht, darf ein Positions-Update von Qt
    # nicht den Schieberegler unter seiner Maus wegreissen.
    assert pb.seek_slider.value() == 10_000
    pb.seek_slider.setSliderDown(False)


def test_volume_slider_maps_to_0_1_range(qapp):
    pb = PlayerBarWidget()
    pb._on_volume_changed(50)
    assert pb._audio_output.volume() == pytest.approx(0.5)
    pb._on_volume_changed(0)
    assert pb._audio_output.volume() == pytest.approx(0.0)
    pb._on_volume_changed(100)
    assert pb._audio_output.volume() == pytest.approx(1.0)


def test_error_occurred_shown_not_silent(qapp):
    pb = PlayerBarWidget()
    pb._on_error_occurred(None, "Codec nicht unterstützt")
    assert "Codec nicht unterstützt" in pb.status_label.text()


def test_stop_and_clear_resets_everything(qapp):
    pb = PlayerBarWidget()
    pb._on_duration_changed(60_000)
    pb._on_position_changed(10_000)
    pb.play_pause_btn.setEnabled(True)
    pb.stop_btn.setEnabled(True)
    pb.seek_slider.setEnabled(True)
    pb._video_widget.setVisible(True)
    pb.status_label.setText("irgendein Fehler")

    pb.stop_and_clear()

    assert pb.title_label.text() == "Keine Wiedergabe aktiv."
    assert pb.status_label.text() == ""
    assert not pb.play_pause_btn.isEnabled()
    assert not pb.stop_btn.isEnabled()
    assert not pb.seek_slider.isEnabled()
    assert pb.seek_slider.maximum() == 0
    assert pb.position_label.text() == "00:00"
    assert pb.duration_label.text() == "00:00"
    assert pb._video_widget.isHidden()


def test_load_and_play_enables_controls_and_sets_title(qapp):
    pb = PlayerBarWidget()
    pb.load_and_play("/tmp/does-not-matter.mp3", "Mein Titel.mp3", kind="music")
    assert "Mein Titel.mp3" in pb.title_label.text()
    assert pb.play_pause_btn.isEnabled()
    assert pb.stop_btn.isEnabled()
    assert pb.seek_slider.isEnabled()
    assert pb._video_widget.isHidden()  # "music" ist kein Video-Kind


def test_load_and_play_shows_video_widget_for_movie_kind(qapp):
    pb = PlayerBarWidget()
    pb.load_and_play("/tmp/does-not-matter.mp4", "Mein Film.mp4", kind="movie")
    assert not pb._video_widget.isHidden()


def test_load_and_play_hides_video_widget_for_non_video_kind(qapp):
    pb = PlayerBarWidget()
    pb.load_and_play("/tmp/x.mp4", "x.mp4", kind="movie")
    assert not pb._video_widget.isHidden()
    pb.load_and_play("/tmp/y.mp3", "y.mp3", kind="music")
    assert pb._video_widget.isHidden()
