"""Duenne FFmpeg-`loudnorm`-Anbindung (§19, ADR-0010).

Analog zu `genesis_core/scanner/ffprobe_util.py`: ruft das system-installierte
FFmpeg-Binary per `subprocess` auf, parst die Textausgabe, verschluckt keine
Fehler still (Prinzip #19/§37), bricht aber den aufrufenden Code nicht mit
einem rohen Stacktrace ab - gibt stattdessen `None`/wirft eine eigene,
spezifische Exception.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from genesis_core.logutil import get_logger

log = get_logger("LoudnessFFmpeg")

# Pass-1-Zielwerte sind fuer die reine MESSUNG irrelevant (loudnorm misst in
# Pass 1 immer die tatsaechlichen Eingangswerte, unabhaengig von I/TP/LRA) -
# sie werden trotzdem benoetigt, weil der Filter sie als Pflichtparameter
# erwartet. Plausible EBU-R128-Standardwerte als Platzhalter.
_MEASURE_PASS_DEFAULTS = {"I": -16.0, "TP": -1.5, "LRA": 11.0}

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


class FFmpegNotAvailable(RuntimeError):
    pass


class FFmpegLoudnormError(RuntimeError):
    """FFmpeg wurde ausgefuehrt, lieferte aber keinen auswertbaren Erfolg
    (Timeout, Nicht-Null-Exitcode, kein parsbarer JSON-Block)."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _parse_loudnorm_json(stderr_text: str) -> dict[str, float]:
    """Extrahiert den letzten `{...}`-JSON-Block aus der ffmpeg-stderr-Ausgabe
    (der `loudnorm`-Filter schreibt am Ende seinen Statistikblock dorthin) und
    wandelt die (von ffmpeg als Strings gelieferten) Zahlenfelder in `float`
    um. "-inf"/"inf"/"nan" werden dabei korrekt behandelt (z.B. bei komplett
    stillen Dateien)."""
    matches = _JSON_BLOCK_RE.findall(stderr_text)
    if not matches:
        raise FFmpegLoudnormError(
            "Kein JSON-Statistikblock in der ffmpeg-Ausgabe gefunden - "
            "loudnorm-Filter hat vermutlich nicht erfolgreich durchlaufen."
        )
    raw = json.loads(matches[-1])
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            try:
                parsed[key] = float(value)
            except ValueError:
                parsed[key] = float("nan")
        elif isinstance(value, (int, float)):
            parsed[key] = float(value)
        else:
            parsed[key] = value
    return parsed


def measure(path: str | Path, timeout_seconds: float = 120.0) -> dict[str, float]:
    """Fuehrt NUR Pass 1 von `loudnorm` aus (reine Messung, keine
    Ausgabedatei) und liefert die rohen Messwerte
    (`input_i`, `input_tp`, `input_lra`, `input_thresh`).

    Wirft `FFmpegNotAvailable`/`FFmpegLoudnormError` statt eine Datei mit
    unbekanntem Format still als "0 LUFS" misszuverstehen (Prinzip #19).
    """
    if not ffmpeg_available():
        raise FFmpegNotAvailable("ffmpeg wurde nicht gefunden (PATH pruefen)")

    filter_str = (
        f"loudnorm=I={_MEASURE_PASS_DEFAULTS['I']}:"
        f"TP={_MEASURE_PASS_DEFAULTS['TP']}:"
        f"LRA={_MEASURE_PASS_DEFAULTS['LRA']}:"
        "print_format=json"
    )
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
        "-af", filter_str, "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegLoudnormError(f"ffmpeg-Timeout bei der Loudness-Messung von {path}") from exc

    if result.returncode != 0:
        log.warning("ffmpeg loudnorm-Messung fehlgeschlagen fuer %s: %s", path, result.stderr[-500:])
        raise FFmpegLoudnormError(
            f"ffmpeg konnte {Path(path).name} nicht analysieren (Exitcode {result.returncode}). "
            "Moegliche Ursache: kein lesbarer Audio-Stream in der Datei."
        )
    return _parse_loudnorm_json(result.stderr)


def render_normalized(
    path: str | Path,
    output_path: str | Path,
    *,
    target_lufs: float,
    target_true_peak_dbtp: float,
    target_lra: float,
    measured: dict[str, float],
    codec_args: list[str],
    linear: bool = True,
    timeout_seconds: float = 600.0,
) -> dict[str, Any]:
    """Fuehrt Pass 2 von `loudnorm` aus: wendet die in Pass 1 gemessenen
    Werte an, um EINMALIG auf den Zielwert zu normalisieren, und schreibt das
    Ergebnis nach `output_path` (NIEMALS nach `path` - Aufrufer muss
    sicherstellen, dass `output_path != path`, siehe engine.py).

    `-n` (statt `-y`) wird bewusst als zusaetzliche Verteidigungslinie
    uebergeben: selbst wenn durch einen Programmierfehler weiter oben doch
    ein bereits existierender Pfad hereingereicht wuerde, bricht ffmpeg
    selbst lieber mit einem Fehler ab, als die Datei stillschweigend zu
    ueberschreiben (Prinzip #4/#5).
    """
    if not ffmpeg_available():
        raise FFmpegNotAvailable("ffmpeg wurde nicht gefunden (PATH pruefen)")
    if str(Path(output_path).resolve()) == str(Path(path).resolve()):
        raise ValueError("output_path darf niemals mit dem Quellpfad identisch sein")
    if Path(output_path).exists():
        raise FileExistsError(f"Zieldatei existiert bereits: {output_path}")

    filter_str = (
        f"loudnorm=I={target_lufs}:TP={target_true_peak_dbtp}:LRA={target_lra}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"linear={'true' if linear else 'false'}:print_format=json"
    )
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-n", "-i", str(path),
        "-af", filter_str, *codec_args, str(output_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegLoudnormError(f"ffmpeg-Timeout bei der Normalisierung von {path}") from exc

    if result.returncode != 0:
        log.warning("ffmpeg loudnorm-Rendering fehlgeschlagen fuer %s: %s", path, result.stderr[-800:])
        raise FFmpegLoudnormError(
            f"ffmpeg konnte {Path(path).name} nicht normalisieren (Exitcode {result.returncode})."
        )
    stats = _parse_loudnorm_json(result.stderr)
    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise FFmpegLoudnormError(
            f"ffmpeg meldete Erfolg, aber {output_path} wurde nicht (oder leer) erzeugt."
        )
    return stats
