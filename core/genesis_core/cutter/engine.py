"""Audio-Cutter-Engine: Auswahl -> Vorschau/Plan -> Bestaetigung -> Anwenden
(§18, ADR-0011).

Sicherheitsmechanik (Prinzip #4/#5/#17, §18, §44), analog zur
Loudness-Engine:
1. `generate_waveform_image` ist rein LESEND/visualisierend - erzeugt nur ein
   neues PNG neben der Audiodatei, veraendert das Original nicht.
2. `plan_cut` ist reine Berechnung (KEIN ffmpeg-Aufruf) - validiert die
   Auswahl (Start < Ende, Fades passen in die Selektion, Zielformat
   unterstuetzt), zeigt den geplanten Ausgabepfad und etwaige Konflikte
   BEVOR irgendetwas passiert.
3. `apply_cut` erfordert IMMER `user_confirmed=True` und schreibt NIE in die
   Originaldatei - das Ergebnis ist IMMER eine neue Datei neben dem Original.
   Rollback ist dadurch denkbar einfach: die neu erzeugte Datei loeschen, das
   Original war nie betroffen.

Hinweis zu "Stream Copy" (kein unnoetiges Neukodieren, §18): nach
Sandbox-Tests (siehe ffmpeg_cutter.py-Modulddocstring fuer Details) wird
bewusst IMMER ueber Audiofilter (`atrim`/`afade`) re-enkodiert statt ueber
Demuxer-seitiges Stream-Copy - das ist fuer verlustfreie Zielformate
(WAV/FLAC) qualitativ verlustfrei und liefert zuverlaessig exakte
Schnittpositionen, waehrend der getestete Stream-Copy-Pfad das in diesem
ffmpeg-Build nicht zuverlaessig erfuellte (siehe ADR-0011).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from genesis_core.audio_formats import CUTTER_MINIMUM_EXPORT_FORMATS, spec_for_name
from genesis_core.cutter import ffmpeg_cutter
from genesis_core.logutil import get_logger

log = get_logger("CutterEngine")


class InvalidCutSelectionError(ValueError):
    """Die angeforderte Auswahl (Start/Ende/Fades) ist nicht gueltig -
    wird NIE stillschweigend korrigiert (Prinzip #17), sondern dem Nutzer
    als Fehler gemeldet."""


class CutApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `apply_cut` ohne `user_confirmed=True` aufgerufen
    wird (Prinzip #17/§44, hart im Code erzwungen)."""


class WaveformGenerationError(RuntimeError):
    """Waveform-Rendering fehlgeschlagen (ffmpeg fehlt/Timeout/kein lesbarer
    Audio-Stream)."""


class CutRenderError(RuntimeError):
    """Der eigentliche Schnitt (ffmpeg-Rendering) ist fehlgeschlagen (ffmpeg
    fehlt/Timeout/Fehler) - wird NIE stillschweigend verschluckt (Prinzip
    #19)."""


@dataclasses.dataclass
class CutPlan:
    media_file_id: int
    source_path: str
    output_path: str
    start_seconds: float
    end_seconds: float
    fade_in_seconds: float
    fade_out_seconds: float
    export_format: str
    selection_duration_seconds: float
    is_lossy_export: bool
    has_conflict: bool
    conflict_reason: str | None


@dataclasses.dataclass
class CutResult:
    media_file_id: int
    output_path: str
    start_seconds: float
    end_seconds: float
    fade_in_seconds: float
    fade_out_seconds: float
    export_format: str


def generate_waveform_image(
    source_path: str | Path,
    output_png: str | Path,
    *,
    width: int = 1200,
    height: int = 200,
) -> Path:
    """Erzeugt ein Waveform-Vorschaubild. Rein lesend - siehe Moduldocstring.
    Wirft `WaveformGenerationError` statt eine fehlgeschlagene Erzeugung
    still zu ignorieren (Prinzip #19)."""
    try:
        ffmpeg_cutter.render_waveform_image(source_path, output_png, width=width, height=height)
    except (ffmpeg_cutter.FFmpegNotAvailable, ffmpeg_cutter.FFmpegCutterError) as exc:
        raise WaveformGenerationError(str(exc)) from exc
    return Path(output_png)


def _validate_selection(
    start_seconds: float,
    end_seconds: float,
    fade_in_seconds: float,
    fade_out_seconds: float,
    source_duration_seconds: float | None,
) -> None:
    if start_seconds < 0:
        raise InvalidCutSelectionError("Der Startzeitpunkt darf nicht negativ sein.")
    if end_seconds <= start_seconds:
        raise InvalidCutSelectionError("Der Endzeitpunkt muss nach dem Startzeitpunkt liegen.")
    if source_duration_seconds is not None and end_seconds > source_duration_seconds + 0.001:
        raise InvalidCutSelectionError(
            f"Der Endzeitpunkt ({end_seconds}s) liegt hinter dem Dateiende "
            f"({source_duration_seconds}s)."
        )
    if fade_in_seconds < 0 or fade_out_seconds < 0:
        raise InvalidCutSelectionError("Fade-Laengen duerfen nicht negativ sein.")
    duration = end_seconds - start_seconds
    if fade_in_seconds + fade_out_seconds > duration:
        raise InvalidCutSelectionError(
            "Fade-In und Fade-Out zusammen duerfen nicht laenger als die Auswahl selbst sein."
        )


def plan_cut(
    media_file_id: int,
    source_path: str,
    start_seconds: float,
    end_seconds: float,
    export_format: str,
    fade_in_seconds: float = 0.0,
    fade_out_seconds: float = 0.0,
    source_duration_seconds: float | None = None,
) -> CutPlan:
    """Reine Berechnung (KEIN ffmpeg-Aufruf) - siehe Moduldocstring."""
    export_format = export_format.lower()
    if export_format not in CUTTER_MINIMUM_EXPORT_FORMATS and export_format not in (
        "ogg", "opus", "m4a", "aac",
    ):
        raise InvalidCutSelectionError(
            f"Exportformat '{export_format}' wird vom Cutter nicht unterstuetzt."
        )
    _validate_selection(start_seconds, end_seconds, fade_in_seconds, fade_out_seconds, source_duration_seconds)

    spec = spec_for_name(export_format)
    src = Path(source_path)
    output_path = src.with_name(f"{src.stem}.cut.{spec.extension.lstrip('.')}")
    has_conflict = output_path.exists()
    conflict_reason = f"Zieldatei existiert bereits: {output_path.name}" if has_conflict else None

    return CutPlan(
        media_file_id=media_file_id,
        source_path=str(source_path),
        output_path=str(output_path),
        start_seconds=round(start_seconds, 3),
        end_seconds=round(end_seconds, 3),
        fade_in_seconds=round(fade_in_seconds, 3),
        fade_out_seconds=round(fade_out_seconds, 3),
        export_format=export_format,
        selection_duration_seconds=round(end_seconds - start_seconds, 3),
        is_lossy_export=spec.is_lossy,
        has_conflict=has_conflict,
        conflict_reason=conflict_reason,
    )


def apply_cut(plan: CutPlan, user_confirmed: bool = False) -> CutResult:
    """Fuehrt den Schnitt tatsaechlich aus. Erfordert `user_confirmed=True`
    (Prinzip #17/§44) und lehnt einen bekannten Konflikt (Zieldatei existiert
    bereits) hart ab, statt sie zu ueberschreiben."""
    if not user_confirmed:
        raise CutApplyNotConfirmedError(
            "apply_cut erfordert user_confirmed=True (erst nach expliziter "
            "Nutzerbestaetigung der Vorschau aufrufen)."
        )
    if plan.has_conflict:
        raise FileExistsError(plan.conflict_reason)

    spec = spec_for_name(plan.export_format)
    try:
        ffmpeg_cutter.render_cut(
            plan.source_path,
            plan.output_path,
            start_seconds=plan.start_seconds,
            end_seconds=plan.end_seconds,
            fade_in_seconds=plan.fade_in_seconds,
            fade_out_seconds=plan.fade_out_seconds,
            codec_args=list(spec.ffmpeg_codec_args),
        )
    except (ffmpeg_cutter.FFmpegNotAvailable, ffmpeg_cutter.FFmpegCutterError) as exc:
        raise CutRenderError(str(exc)) from exc

    return CutResult(
        media_file_id=plan.media_file_id,
        output_path=plan.output_path,
        start_seconds=plan.start_seconds,
        end_seconds=plan.end_seconds,
        fade_in_seconds=plan.fade_in_seconds,
        fade_out_seconds=plan.fade_out_seconds,
        export_format=plan.export_format,
    )
