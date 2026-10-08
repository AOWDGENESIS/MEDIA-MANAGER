"""Duenne FFmpeg-Anbindung des Konvertierungs-Werkzeugs.

Analog zu `genesis_core/cutter/ffmpeg_cutter.py`/`loudness/ffmpeg_loudnorm.py`:
ruft das system-installierte FFmpeg-Binary per `subprocess` auf, verschluckt
keine Fehler still (Prinzip #19/§37).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegNotAvailable(RuntimeError):
    pass


class FFmpegConvertError(RuntimeError):
    """FFmpeg wurde ausgefuehrt, lieferte aber keinen auswertbaren Erfolg."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def render_conversion(
    path: str | Path,
    output_path: str | Path,
    *,
    codec_args: list[str],
    timeout_seconds: float = 600.0,
) -> None:
    """Konvertiert `path` nach `output_path` mit den gegebenen
    Codec-Argumenten. Schreibt NIEMALS nach `path` (Aufrufer muss
    sicherstellen, dass `output_path != path`, siehe engine.py).

    `-n` (statt `-y`) ist eine zusaetzliche Verteidigungslinie: selbst bei
    einem Programmierfehler weiter oben bricht ffmpeg lieber ab, als eine
    bereits existierende Datei stillschweigend zu ueberschreiben
    (Prinzip #4/#5).
    """
    if not ffmpeg_available():
        raise FFmpegNotAvailable("ffmpeg wurde nicht gefunden (PATH pruefen)")
    if str(Path(output_path).resolve()) == str(Path(path).resolve()):
        raise ValueError("output_path darf niemals mit dem Quellpfad identisch sein")
    if Path(output_path).exists():
        raise FileExistsError(f"Zieldatei existiert bereits: {output_path}")

    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-n", "-i", str(path), *codec_args, str(output_path)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegConvertError(f"ffmpeg-Timeout bei der Konvertierung von {path}") from exc

    if result.returncode != 0:
        raise FFmpegConvertError(
            f"ffmpeg konnte {Path(path).name} nicht konvertieren (Exitcode {result.returncode}): "
            f"{result.stderr[-500:]}"
        )
    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise FFmpegConvertError(
            f"ffmpeg meldete Erfolg, aber {output_path} wurde nicht (oder leer) erzeugt."
        )
