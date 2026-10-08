"""Eingebauter, einfacher Medienplayer für die Bibliothek (§60, Gap-Analyse
Gap G).

Bisher existierte Wiedergabe nur eng an einzelne Werkzeuge gekoppelt (Cutter-
Vorschau in `dialogs/cutter_dialog.py`, TTS-Testwiedergabe in
`views/voice_studio_view.py`) - es gab keine Play/Pause/Stop/Seek/Lautstärke-
Komponente, die ein BELIEBIGES Bibliotheksmedium direkt abspielt. Dieses
Widget schließt das: eine persistente Leiste, die unten in `MediaTableView`
eingebettet wird und per `load_and_play()` auf einen beliebigen, bereits
lokal vorhandenen Dateipfad umschaltet.

Rein lesend/anzeigend (Prinzip #4/#5) - Wiedergabe verändert nie die
abgespielte Datei, daher ohne Bestätigungsdialog nutzbar, genau wie die
bereits bestehende Cutter-/Voice-Studio-Vorschau.

In der Linux-Sandbox ohne Audiogerät ist die tatsächliche Tonausgabe nicht
hörbar prüfbar (siehe PROGRESS.md) - die Verdrahtung selbst (Quelle setzen,
Play/Pause/Stop, Suchleiste, Lautstärke, Zeit-/Fehleranzeige) ist aber
sowohl konstruktions- als auch offscreen-testbar und wird entsprechend
getestet (`tests/test_player_bar.py`).
"""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from genesis_ui.i18n import tr
from genesis_ui.widgets import set_plain_text

#: Medienarten, bei denen zusätzlich zur Tonspur ein Bild gezeigt wird
#: (§24 Film/Serie). Fuer alle anderen Arten bleibt das Videofenster
#: ausgeblendet, um Platz zu sparen - reine Audiowiedergabe braucht kein
#: Bildfenster.
VIDEO_KINDS = frozenset({"movie", "episode"})


def format_time(milliseconds: int) -> str:
    """`12345` ms -> `"00:12"`. Reine Funktion, unabhaengig von Qt-Instanzen
    testbar - Stunden werden nur ausgegeben, wenn die Datei laenger als eine
    Stunde ist (z.B. lange Hoerbuch-Kapitel/Filme, §23/§24)."""
    if milliseconds < 0:
        milliseconds = 0
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class PlayerBarWidget(QWidget):
    """Persistente Wiedergabeleiste - eine Instanz pro `MediaTableView`,
    wird bei jedem Klick auf "Abspielen" per `load_and_play()` auf das
    jeweils ausgewählte Medium umgeschaltet (kein eigener Dialog, bewusst
    immer sichtbar wie bei einem echten Musik-/Medienplayer, §60)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(0.8)

        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumHeight(220)
        self._video_widget.setVisible(False)
        self._player.setVideoOutput(self._video_widget)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        root.addWidget(self._video_widget)

        self.title_label = QLabel(tr("player_bar.no_media"))
        root.addWidget(self.title_label)

        controls = QHBoxLayout()
        self.play_pause_btn = QPushButton(tr("player_bar.play_button"))
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        self.stop_btn = QPushButton(tr("player_bar.stop_button"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        controls.addWidget(self.play_pause_btn)
        controls.addWidget(self.stop_btn)

        self.position_label = QLabel("00:00")
        controls.addWidget(self.position_label)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self._on_seek_slider_moved)
        controls.addWidget(self.seek_slider, stretch=1)

        self.duration_label = QLabel("00:00")
        controls.addWidget(self.duration_label)

        controls.addWidget(QLabel(tr("player_bar.volume_label")))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(120)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        controls.addWidget(self.volume_slider)

        root.addLayout(controls)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.errorOccurred.connect(self._on_error_occurred)

    # -- Oeffentliche API ----------------------------------------------------

    def load_and_play(self, absolute_path: str, title: str, kind: str | None = None) -> None:
        """Schaltet die Leiste auf eine neue Datei um und startet sofort die
        Wiedergabe (bewusstes, einzelnes Nutzer-Ereignis "Abspielen"
        geklickt - kein unerwartetes Autoplay beim bloßen Auswählen einer
        Zeile in der Tabelle)."""
        self._video_widget.setVisible(kind in VIDEO_KINDS)
        set_plain_text(self.title_label, tr("player_bar.now_playing", title=title))
        self.status_label.setText("")
        self._player.setSource(QUrl.fromLocalFile(absolute_path))
        self._player.play()
        self.play_pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.seek_slider.setEnabled(True)

    def stop_and_clear(self) -> None:
        """Wird aufgerufen, wenn die Bibliotheksliste neu geladen wird
        (`MediaTableView.refresh()`) - verhindert, dass weiter eine Datei
        spielt, die ggf. gar nicht mehr in der aktuellen Trefferliste ist."""
        self._player.stop()
        self._player.setSource(QUrl())
        self.title_label.setText(tr("player_bar.no_media"))
        self.status_label.setText("")
        self.play_pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.seek_slider.setEnabled(False)
        self.seek_slider.setRange(0, 0)
        self.position_label.setText("00:00")
        self.duration_label.setText("00:00")
        self._video_widget.setVisible(False)

    # -- Interne Slots -------------------------------------------------------

    def _on_play_pause_clicked(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_stop_clicked(self) -> None:
        self._player.stop()

    def _on_seek_slider_moved(self, position_ms: int) -> None:
        self._player.setPosition(position_ms)

    def _on_volume_changed(self, value: int) -> None:
        self._audio_output.setVolume(value / 100.0)

    def _on_position_changed(self, position_ms: int) -> None:
        self.position_label.setText(format_time(position_ms))
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position_ms)

    def _on_duration_changed(self, duration_ms: int) -> None:
        self.duration_label.setText(format_time(duration_ms))
        self.seek_slider.setRange(0, max(duration_ms, 0))

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setText(tr("player_bar.pause_button"))
        else:
            self.play_pause_btn.setText(tr("player_bar.play_button"))

    def _on_error_occurred(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        # Kein stiller Fehlschlag (Grundprinzip): Wiedergabefehler (z.B.
        # fehlendes Codec-Plugin, kaputte Datei) werden sichtbar gemacht
        # statt einfach stumm zu bleiben.
        self.status_label.setText(tr("player_bar.playback_error", error=error_string))
