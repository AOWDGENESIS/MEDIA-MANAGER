"""Konvertierungs-Engine: Auswahl -> Vorschau/Plan -> Bestaetigung -> Anwenden.

Nutzt den gemeinsamen Formatkatalog `genesis_core.audio_formats` (ADR-0011)
statt einer eigenen Codec-Tabelle - Konvertierung ist der dritte Verbraucher
nach Loudness-Engine und Audio-Cutter.

Sicherheitsmechanik (Prinzip #4/#5/#17, §44), identisch zu Loudness/Cutter:
1. `plan_conversion` ist reine Berechnung (KEIN ffmpeg-Aufruf) - validiert die
   Anfrage (Zielformat unterstuetzt, optionale Bitrate nur fuer verlustbehaftete
   Formate sinnvoll) und zeigt den geplanten Ausgabepfad samt etwaiger
   Konflikte/Hinweise BEVOR irgendetwas passiert.
2. `apply_conversion` erfordert IMMER `user_confirmed=True` und schreibt NIE
   in die Originaldatei - das Ergebnis ist IMMER eine neue Datei neben dem
   Original. Rollback ist dadurch denkbar einfach: die neu erzeugte Datei
   loeschen, das Original war nie betroffen.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from genesis_core.audio_formats import AudioFormatSpec, spec_for_name
from genesis_core.convert import ffmpeg_convert
from genesis_core.logutil import get_logger

log = get_logger("ConvertEngine")


class InvalidConversionRequestError(ValueError):
    """Die angeforderte Konvertierung (Zielformat/Bitrate) ist nicht
    gueltig - wird NIE stillschweigend korrigiert (Prinzip #17)."""


class ConversionApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `apply_conversion` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #17/§44, hart im Code erzwungen)."""


class ConversionRenderError(RuntimeError):
    """Die eigentliche Konvertierung (ffmpeg-Rendering) ist fehlgeschlagen -
    wird NIE stillschweigend verschluckt (Prinzip #19)."""


@dataclasses.dataclass
class ConversionPlan:
    media_file_id: int
    source_path: str
    output_path: str
    source_format: str
    target_format: str
    bitrate_kbps: int | None
    is_lossy_target: bool
    is_no_op_same_format: bool
    has_conflict: bool
    conflict_reason: str | None


@dataclasses.dataclass
class ConversionResult:
    media_file_id: int
    output_path: str
    target_format: str
    bitrate_kbps: int | None


def _codec_args_with_bitrate(spec: AudioFormatSpec, bitrate_kbps: int | None) -> list[str]:
    """Ersetzt den in `AudioFormatSpec.ffmpeg_codec_args` fest hinterlegten
    Bitrate-Wert (falls vorhanden) durch eine vom Nutzer gewaehlte Bitrate.
    Fuer verlustfreie Formate (kein `-b:a` in den Default-Argumenten) wird
    eine angeforderte Bitrate ignoriert (sie haette dort keine Wirkung)."""
    args = list(spec.ffmpeg_codec_args)
    if bitrate_kbps is None or "-b:a" not in args:
        return args
    idx = args.index("-b:a")
    args[idx + 1] = f"{bitrate_kbps}k"
    return args


def plan_conversion(
    media_file_id: int,
    source_path: str,
    target_format: str,
    bitrate_kbps: int | None = None,
) -> ConversionPlan:
    """Reine Berechnung (KEIN ffmpeg-Aufruf) - siehe Moduldocstring."""
    target_format = target_format.lower()
    try:
        spec = spec_for_name(target_format)
    except ValueError as exc:
        raise InvalidConversionRequestError(str(exc)) from exc

    if bitrate_kbps is not None and bitrate_kbps <= 0:
        raise InvalidConversionRequestError("Die Bitrate muss größer als 0 sein.")

    src = Path(source_path)
    source_format = src.suffix.lstrip(".").lower()
    is_no_op_same_format = source_format == spec.name and bitrate_kbps is None
    output_path = src.with_name(f"{src.stem}.converted.{spec.extension.lstrip('.')}")
    has_conflict = output_path.exists()
    conflict_reason = f"Zieldatei existiert bereits: {output_path.name}" if has_conflict else None

    return ConversionPlan(
        media_file_id=media_file_id,
        source_path=str(source_path),
        output_path=str(output_path),
        source_format=source_format,
        target_format=spec.name,
        bitrate_kbps=bitrate_kbps,
        is_lossy_target=spec.is_lossy,
        is_no_op_same_format=is_no_op_same_format,
        has_conflict=has_conflict,
        conflict_reason=conflict_reason,
    )


def apply_conversion(plan: ConversionPlan, user_confirmed: bool = False) -> ConversionResult:
    """Fuehrt die Konvertierung tatsaechlich aus. Erfordert
    `user_confirmed=True` (Prinzip #17/§44) und lehnt einen bekannten
    Konflikt (Zieldatei existiert bereits) hart ab, statt sie zu
    ueberschreiben."""
    if not user_confirmed:
        raise ConversionApplyNotConfirmedError(
            "apply_conversion erfordert user_confirmed=True (erst nach "
            "expliziter Nutzerbestaetigung der Vorschau aufrufen)."
        )
    if plan.has_conflict:
        raise FileExistsError(plan.conflict_reason)

    spec = spec_for_name(plan.target_format)
    codec_args = _codec_args_with_bitrate(spec, plan.bitrate_kbps)
    try:
        ffmpeg_convert.render_conversion(plan.source_path, plan.output_path, codec_args=codec_args)
    except (ffmpeg_convert.FFmpegNotAvailable, ffmpeg_convert.FFmpegConvertError) as exc:
        raise ConversionRenderError(str(exc)) from exc

    return ConversionResult(
        media_file_id=plan.media_file_id,
        output_path=plan.output_path,
        target_format=plan.target_format,
        bitrate_kbps=plan.bitrate_kbps,
    )
