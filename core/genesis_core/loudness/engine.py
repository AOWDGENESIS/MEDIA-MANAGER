"""Loudness-Engine: Messen -> Vorschlag/Vorschau -> Bestaetigung -> Anwenden.

Scope dieser ersten Version (bewusste, dokumentierte Einschraenkung, analog
zur Rename-Engine): NUR reine Audio-Medienarten (Musik, Hoerbuch, Podcast,
KI-Musik). Video-Medien (Film/Serie) werden in Phase 3 v1 NICHT unterstuetzt -
eine Normalisierung dort muesste den Videostream verlustfrei durchreichen
(`-c:v copy`) und bringt zusaetzliche Container-/Sync-Fragen mit sich, die
eine eigene, gruendlich getestete Erweiterung verdienen (Backlog, siehe
PROGRESS.md) statt sie hier nebenbei throwaway mitzuziehen.

Sicherheitsmechanik (Prinzip #4/#5/#17, §19, §44):
1. `measure_loudness` ist rein LESEND - ein `ffmpeg`-Durchlauf ohne
   Ausgabedatei, veraendert nichts.
2. `plan_normalization` ist reine Berechnung (kein ffmpeg-Aufruf) - zeigt
   Zielgewinn, geplanten Ausgabepfad und etwaige Warnungen (z.B. drohende
   Dynamikaenderung durch True-Peak-Begrenzung) BEVOR irgendetwas passiert.
3. `apply_normalization` erfordert IMMER `user_confirmed=True` und schreibt
   NIE in die Originaldatei - das Ergebnis ist IMMER eine neue Datei neben
   dem Original. Ein Rollback ist dadurch denkbar einfach: die neu erzeugte
   Datei loeschen, das Original war nie betroffen.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

from genesis_core.audio_formats import spec_for_extension
from genesis_core.db.models import MediaKind
from genesis_core.logutil import get_logger
from genesis_core.loudness import ffmpeg_loudnorm

log = get_logger("LoudnessEngine")

# Siehe Moduldocstring: Video-Normalisierung ist bewusst (noch) nicht im
# Scope. Zentral als Konstante gefuehrt, damit API/UI dieselbe Grenze
# durchsetzen, ohne sie an zwei Stellen zu duplizieren.
AUDIO_MEDIA_KINDS = frozenset(
    {MediaKind.MUSIC, MediaKind.AUDIOBOOK, MediaKind.PODCAST_EPISODE, MediaKind.AI_MUSIC}
)



class LoudnessMeasurementError(RuntimeError):
    """Messung fehlgeschlagen (ffmpeg fehlt/Timeout/kein Audio-Stream) -
    wird NIE stillschweigend als "0 LUFS" interpretiert (Prinzip #19)."""


class NormalizationApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `apply_normalization` ohne `user_confirmed=True`
    aufgerufen wird (Prinzip #17/§44, hart im Code erzwungen)."""


class UnsupportedMediaKindError(ValueError):
    """Normalisierung fuer diese Medienart ist in dieser Version nicht
    unterstuetzt (siehe AUDIO_MEDIA_KINDS/Moduldocstring)."""


@dataclasses.dataclass
class LoudnessMeasurement:
    integrated_lufs: float
    true_peak_dbtp: float
    loudness_range_lu: float
    measured_at: dt.datetime


@dataclasses.dataclass
class NormalizationPlan:
    media_file_id: int
    source_path: str
    output_path: str
    target_lufs: float
    target_true_peak_dbtp: float
    target_lra: float
    measured_integrated_lufs: float
    measured_true_peak_dbtp: float
    measured_loudness_range_lu: float
    planned_gain_db: float
    predicted_output_true_peak_dbtp: float
    will_likely_alter_dynamics: bool
    is_lossy_reencode: bool
    output_format_note: str
    has_conflict: bool
    conflict_reason: str | None


@dataclasses.dataclass
class NormalizationResult:
    media_file_id: int
    output_path: str
    achieved_integrated_lufs: float
    achieved_true_peak_dbtp: float
    used_dynamic_processing: bool


def measure_loudness(path: str | Path, timeout_seconds: float = 120.0) -> LoudnessMeasurement:
    """Misst Integrated-LUFS/True-Peak/LRA einer Audiodatei. Reine Lesung,
    veraendert nichts (Prinzip #4/#5)."""
    try:
        raw = ffmpeg_loudnorm.measure(path, timeout_seconds=timeout_seconds)
    except (ffmpeg_loudnorm.FFmpegNotAvailable, ffmpeg_loudnorm.FFmpegLoudnormError) as exc:
        raise LoudnessMeasurementError(str(exc)) from exc

    for key in ("input_i", "input_tp", "input_lra"):
        if key not in raw or raw[key] != raw[key]:  # NaN-Check (x != x nur bei NaN wahr)
            raise LoudnessMeasurementError(
                f"ffmpeg lieferte keinen gueltigen Wert fuer '{key}' - "
                "vermutlich eine komplett stille oder beschaedigte Datei."
            )
    return LoudnessMeasurement(
        integrated_lufs=raw["input_i"],
        true_peak_dbtp=raw["input_tp"],
        loudness_range_lu=raw["input_lra"],
        measured_at=dt.datetime.now(dt.UTC),
    )


def _pick_output(source_path: str) -> tuple[Path, list[str], bool, str]:
    """Waehlt Ausgabepfad (gleicher Ordner, Suffix `.normalized`), Codec und
    liefert eine fuer die UI verstaendliche Begruendung."""
    src = Path(source_path)
    ext = src.suffix.lower()
    spec, known = spec_for_extension(ext)
    codec_args = list(spec.ffmpeg_codec_args)
    if known:
        output_ext = spec.extension
        note = (
            f"Ausgabe im Originalformat ({ext}). "
            + ("Verlustbehaftetes Format - die Normalisierung bedeutet einen "
               "zusaetzlichen Kodierungsdurchlauf (Generationsverlust), "
               "da eine reine Pegelaenderung ohne Neukodierung bei "
               "komprimiertem Audio technisch nicht moeglich ist."
               if spec.is_lossy else
               "Verlustfreies Format - keine Qualitaetseinbusse durch die "
               "Neukodierung zu erwarten.")
        )
    else:
        output_ext = spec.extension
        note = (
            f"Unbekanntes/nicht abgebildetes Quellformat ({ext or 'ohne Endung'}) - "
            f"Ausgabe erfolgt verlustfrei als {spec.extension} statt im Originalformat."
        )
    output_path = src.with_name(f"{src.stem}.normalized{output_ext}")
    return output_path, codec_args, spec.is_lossy, note


def plan_normalization(
    media_file_id: int,
    source_path: str,
    media_kind: MediaKind,
    measurement: LoudnessMeasurement,
    target_lufs: float,
    target_true_peak_dbtp: float,
    target_lra: float = 11.0,
) -> NormalizationPlan:
    """Reine Berechnung (KEIN ffmpeg-Aufruf) - siehe Moduldocstring."""
    if media_kind not in AUDIO_MEDIA_KINDS:
        raise UnsupportedMediaKindError(
            f"Loudness-Normalisierung ist fuer Medienart '{media_kind.value}' in dieser "
            "Version nicht unterstuetzt (nur Musik/Hoerbuch/Podcast/KI-Musik)."
        )

    output_path, _codec_args, is_lossy, note = _pick_output(source_path)
    planned_gain_db = target_lufs - measurement.integrated_lufs
    predicted_tp = measurement.true_peak_dbtp + planned_gain_db
    # Wenn der naive (rein lineare) Gain den True-Peak-Zielwert ueberschreiten
    # wuerde, wird ffmpegs loudnorm-Filter intern auf eine dynamische
    # (limiter-aehnliche) Verarbeitung ausweichen, um den Peak trotzdem
    # einzuhalten - das aendert die Dynamik des Signals geringfuegig, statt
    # nur seinen Pegel zu verschieben. Dies wird dem Nutzer VOR der
    # Ausfuehrung transparent angezeigt (Prinzip #16), nicht erst danach.
    will_likely_alter_dynamics = predicted_tp > target_true_peak_dbtp

    has_conflict = output_path.exists()
    conflict_reason = (
        f"Zieldatei existiert bereits: {output_path.name}" if has_conflict else None
    )

    return NormalizationPlan(
        media_file_id=media_file_id,
        source_path=str(source_path),
        output_path=str(output_path),
        target_lufs=target_lufs,
        target_true_peak_dbtp=target_true_peak_dbtp,
        target_lra=target_lra,
        measured_integrated_lufs=measurement.integrated_lufs,
        measured_true_peak_dbtp=measurement.true_peak_dbtp,
        measured_loudness_range_lu=measurement.loudness_range_lu,
        planned_gain_db=round(planned_gain_db, 2),
        predicted_output_true_peak_dbtp=round(min(predicted_tp, target_true_peak_dbtp), 2)
        if will_likely_alter_dynamics else round(predicted_tp, 2),
        will_likely_alter_dynamics=will_likely_alter_dynamics,
        is_lossy_reencode=is_lossy,
        output_format_note=note,
        has_conflict=has_conflict,
        conflict_reason=conflict_reason,
    )


def apply_normalization(plan: NormalizationPlan, user_confirmed: bool = False) -> NormalizationResult:
    """Fuehrt Pass 2 aus. Erfordert `user_confirmed=True` (Prinzip #17/§44)
    und lehnt einen bekannten Konflikt (Zieldatei existiert bereits) hart ab,
    statt sie zu ueberschreiben."""
    if not user_confirmed:
        raise NormalizationApplyNotConfirmedError(
            "apply_normalization erfordert user_confirmed=True (erst nach "
            "expliziter Nutzerbestaetigung der Vorschau aufrufen)."
        )
    if plan.has_conflict:
        raise FileExistsError(plan.conflict_reason)

    _output_path, codec_args, _is_lossy, _note = _pick_output(plan.source_path)
    measured = {
        "input_i": plan.measured_integrated_lufs,
        "input_tp": plan.measured_true_peak_dbtp,
        "input_lra": plan.measured_loudness_range_lu,
        # measured_thresh wird von ffmpeg selbst aus input_i abgeleitet
        # (ca. -70 + Gate), wir reichen hier denselben Wert wie bei der
        # Pass-1-Messung ueblich durch - eine fehlende exakte Kopie des
        # Pass-1-"input_thresh"-Werts hat laut ffmpeg-Dokumentation nur
        # marginalen Einfluss auf Pass 2 (reiner Hinweiswert).
        "input_thresh": plan.measured_integrated_lufs - 24.0,
    }
    try:
        stats = ffmpeg_loudnorm.render_normalized(
            plan.source_path,
            plan.output_path,
            target_lufs=plan.target_lufs,
            target_true_peak_dbtp=plan.target_true_peak_dbtp,
            target_lra=plan.target_lra,
            measured=measured,
            codec_args=codec_args,
            linear=True,
        )
    except (ffmpeg_loudnorm.FFmpegNotAvailable, ffmpeg_loudnorm.FFmpegLoudnormError) as exc:
        raise LoudnessMeasurementError(str(exc)) from exc

    return NormalizationResult(
        media_file_id=plan.media_file_id,
        output_path=plan.output_path,
        achieved_integrated_lufs=stats.get("output_i", plan.target_lufs),
        achieved_true_peak_dbtp=stats.get("output_tp", plan.predicted_output_true_peak_dbtp),
        used_dynamic_processing=(stats.get("normalization_type") == "dynamic"),
    )
