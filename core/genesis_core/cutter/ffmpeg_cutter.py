"""Duenne FFmpeg-Anbindung des Audio-Cutters (§18, ADR-0011).

Analog zu `genesis_core/loudness/ffmpeg_loudnorm.py`: ruft das
system-installierte FFmpeg-Binary per `subprocess` auf, verschluckt keine
Fehler still (Prinzip #19/§37).

Wichtiger Implementierungs-Hinweis (siehe ADR-0011 fuer die volle
Begruendung samt Sandbox-Messungen): der Schnitt wird IMMER ueber die
Audiofilter `atrim`/`afade` re-enkodiert statt ueber die Demuxer-/Muxer-Optionen
`-ss`/`-t` mit `-c copy` ("Stream Copy"). Sandbox-Tests mit diesem
ffmpeg-Build (7.1.5) ergaben zwei Probleme mit dem Stream-Copy-Ansatz:
1. Bei unkomprimiertem WAV (PCM) ist das Ergebnis NICHT sample-genau
   (ca. 2-3% Abweichung von der angeforderten Dauer) - das widerspraeche der
   in §18 geforderten "exakten Zeitposition".
2. Bei FLAC schneidet `-c copy` mit `-ss`/`-t` ueberhaupt nicht (die
   Ausgabedatei behaelt die volle Originaldauer) - ein stiller
   Korrektheitsfehler, der in der Praxis unbemerkt eine falsche Datei
   erzeugen wuerde.
Der Filter-basierte Ansatz (`atrim`) liefert dagegen in allen getesteten
Faellen eine exakte, sample-genaue Dauer. Da WAV/FLAC verlustfreie Formate
sind, bedeutet "Re-Encode" hier KEINEN Qualitaetsverlust (bit-exaktes
PCM/verlustfreie Kompression) - nur einen (vernachlaessigbaren) zusaetzlichen
CPU-Durchlauf. Die in §18 genannte Anforderung "moeglichst ohne unnoetige
Neukodierung" wird daher als "ohne unnoetigen QUALITAETSVERLUST" ausgelegt,
nicht als "ohne jeglichen CPU-Aufwand" - siehe ADR-0011.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegNotAvailable(RuntimeError):
    pass


class FFmpegCutterError(RuntimeError):
    """FFmpeg wurde ausgefuehrt, lieferte aber keinen auswertbaren Erfolg."""


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _build_audio_filter(
    start_seconds: float,
    end_seconds: float,
    fade_in_seconds: float,
    fade_out_seconds: float,
) -> str:
    """Baut die `atrim`/`afade`-Filterkette. `asetpts=PTS-STARTPTS` ist
    zwingend noetig, damit der ausgeschnittene Abschnitt bei Zeitstempel 0
    beginnt (sonst wuerde ffmpeg versuchen, die ersten `start_seconds` als
    Stille/Luecke zu erhalten)."""
    parts = [f"atrim=start={start_seconds}:end={end_seconds}", "asetpts=PTS-STARTPTS"]
    duration = end_seconds - start_seconds
    if fade_in_seconds > 0:
        parts.append(f"afade=t=in:st=0:d={fade_in_seconds}")
    if fade_out_seconds > 0:
        fade_out_start = max(duration - fade_out_seconds, 0.0)
        parts.append(f"afade=t=out:st={fade_out_start}:d={fade_out_seconds}")
    return ",".join(parts)


def render_cut(
    path: str | Path,
    output_path: str | Path,
    *,
    start_seconds: float,
    end_seconds: float,
    fade_in_seconds: float,
    fade_out_seconds: float,
    codec_args: list[str],
    timeout_seconds: float = 600.0,
) -> None:
    """Schneidet `path` auf den Bereich [start_seconds, end_seconds) zu,
    wendet optionale Fades an und schreibt das Ergebnis nach `output_path`
    (NIEMALS nach `path` - Aufrufer muss sicherstellen, dass
    `output_path != path`, siehe engine.py).

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

    filter_str = _build_audio_filter(start_seconds, end_seconds, fade_in_seconds, fade_out_seconds)
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-n", "-i", str(path),
        "-af", filter_str, *codec_args, str(output_path),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegCutterError(f"ffmpeg-Timeout beim Schneiden von {path}") from exc

    if result.returncode != 0:
        raise FFmpegCutterError(
            f"ffmpeg konnte {Path(path).name} nicht schneiden (Exitcode {result.returncode}): "
            f"{result.stderr[-500:]}"
        )
    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise FFmpegCutterError(
            f"ffmpeg meldete Erfolg, aber {output_path} wurde nicht (oder leer) erzeugt."
        )


def render_waveform_image(
    path: str | Path,
    output_png: str | Path,
    *,
    width: int = 1200,
    height: int = 200,
    color_hex: str = "4FC3F7",
    timeout_seconds: float = 120.0,
) -> None:
    """Rendert ein Waveform-Bild (PNG) via ffmpegs `showwavespic`-Filter.
    Rein lesend/visualisierend - greift NIE auf das Original schreibend zu
    (Prinzip #4/#5) und schreibt auch keinen Eintrag in die DB (siehe
    Moduldocstring von `AudioCut` in db/models.py)."""
    if not ffmpeg_available():
        raise FFmpegNotAvailable("ffmpeg wurde nicht gefunden (PATH pruefen)")
    if Path(output_png).exists():
        raise FileExistsError(f"Zieldatei existiert bereits: {output_png}")

    filter_str = f"showwavespic=s={width}x{height}:colors=0x{color_hex}"
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-n", "-i", str(path),
        "-filter_complex", filter_str, "-frames:v", "1", str(output_png),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegCutterError(f"ffmpeg-Timeout bei der Waveform-Erzeugung von {path}") from exc

    if result.returncode != 0:
        raise FFmpegCutterError(
            f"ffmpeg konnte fuer {Path(path).name} kein Waveform-Bild erzeugen "
            f"(Exitcode {result.returncode}): {result.stderr[-500:]}"
        )
    if not Path(output_png).exists() or Path(output_png).stat().st_size == 0:
        raise FFmpegCutterError(
            f"ffmpeg meldete Erfolg, aber {output_png} wurde nicht (oder leer) erzeugt."
        )
