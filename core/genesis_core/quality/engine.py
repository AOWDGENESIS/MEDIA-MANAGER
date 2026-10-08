"""Qualitätsanalyse (§20, ADR-0014).

Reine, read-only Interpretationsschicht ueber bereits vorhandene technische
Daten (TechnicalMetadata, aus dem Scanner/ffprobe), optional ergaenzt um die
zuletzt gemessene Lautheit (Loudness-Engine, §19) und die vom Tag deklarierte
Dauer (Track.duration_seconds). Berechnet SELBST keine neuen ffprobe-/
ffmpeg-Werte - das ist bereits Aufgabe des Scanners bzw. der Loudness-Engine.

**Zwingend (§20): Jedes Ergebnis ist ein VERDACHT, keine Tatsache.** Die
Engine gibt daher niemals "Datei ist beschädigt" o.ae. als Fakt aus, sondern
immer in der Form "Verdacht auf ...". Alle vier Signale koennen false
positives erzeugen (siehe Docstrings der einzelnen Pruefungen) - das ist
bewusst in Kauf genommen, denn das Ziel ist ein Hinweis fuer den Nutzer,
keine automatische Entscheidung (Prinzip #16/#17 - niemals automatisch
verändern/löschen aufgrund eines Verdachts).

Vier Verdachtskategorien (§20, wortgleich):
- suspected_upscale      ("verdächtige Upscales")
- suspected_transcode    ("ungewöhnliche Transcodierungen")
- suspected_corruption   ("beschädigte Dateien")
- suspected_truncation   ("abgeschnittene Dateien")

Bewusste Einschränkung (siehe ADR-0014): eine vollständige
Transcode-/Upscale-Erkennung muesste das Frequenzspektrum der eigentlichen
Audiodaten analysieren (z.B. eine fuer 128-kbps-MP3 typische Tiefpassgrenze
bei ca. 16 kHz, die nach Hochskalieren auf FLAC/320kbps weiterhin sichtbar
bleibt). Das erfordert eine eigene FFT-/DSP-Implementierung und ist bewusst
NICHT Teil dieser ersten Version - die Engine arbeitet ausschliesslich mit
bereits bekannten Metadaten (Containerformat/Codec/Bitrate/Samplerate/
Bittiefe/Dauer), was einen soliden, aber begrenzten Teil der Faelle abdeckt.
"""
from __future__ import annotations

import dataclasses

# Codec-Familien, die zu einer Dateiendung "passen" - eine Abweichung ist ein
# starkes, gut belegbares Signal fuer eine ungewoehnliche Transcodierung
# (z.B. eine als .flac benannte Datei, die tatsaechlich MP3-Daten enthaelt -
# oft das Ergebnis eines Lossy->Lossless-"Upscales" mit anschliessender
# Umbenennung).
_PCM_CODECS = {
    "pcm_s8", "pcm_u8", "pcm_s16le", "pcm_s16be", "pcm_s24le", "pcm_s24be",
    "pcm_s32le", "pcm_s32be", "pcm_f32le", "pcm_f32be", "pcm_f64le", "pcm_f64be",
}
_EXTENSION_CODEC_FAMILIES: dict[str, set[str]] = {
    "mp3": {"mp3"},
    "flac": {"flac"},
    "wav": _PCM_CODECS,
    "wave": _PCM_CODECS,
    "aiff": _PCM_CODECS,
    "aif": _PCM_CODECS,
    "m4a": {"aac", "alac"},
    "aac": {"aac"},
    "ogg": {"vorbis", "opus", "flac"},
    "oga": {"vorbis", "opus", "flac"},
    "opus": {"opus"},
    "wma": {"wmav1", "wmav2", "wmapro", "wmalossless"},
    "alac": {"alac"},
}

# Codecs, bei denen eine echte verlustfreie Kompression stattfindet (anders
# als rohes PCM, dessen Bitrate IMMER exakt durch Samplerate/Bittiefe/Kanaele
# vorgegeben ist und daher kein Upscale-Indiz liefern kann).
_COMPRESSED_LOSSLESS_CODECS = {"flac", "alac"}

# Unterhalb dieses Anteils der theoretischen Roh-PCM-Bitrate ist eine
# Kompression fuer echtes, verlustfrei codiertes Audiomaterial unueblich
# (typische FLAC-Kompression liegt bei 50-70% der Roh-Bitrate) - ein noch
# niedrigerer Wert deutet darauf hin, dass der eigentliche Informationsgehalt
# schon vorher durch eine verlustbehaftete Kompression reduziert wurde
# (klassisches "MP3 -> FLAC"-Upscale).
_UPSCALE_RATIO_THRESHOLD = 0.35

# Eine Tag-Dauer, die mehr als diesen Anteil UND mehr als diese absolute
# Sekundenzahl ueber der technisch gemessenen Dauer liegt, gilt als
# Hinweis auf eine abgeschnittene Datei (reine Rundungsdifferenzen sollen
# nicht faelschlich als Verdacht gewertet werden).
_TRUNCATION_RELATIVE_THRESHOLD = 0.10
_TRUNCATION_ABSOLUTE_MIN_SECONDS = 2.0


@dataclasses.dataclass(frozen=True)
class QualitySnapshot:
    """Unveraenderlicher Schnappschuss aller fuer die Qualitaetsanalyse
    relevanten, BEREITS BEKANNTEN Felder - entkoppelt die Logik bewusst von
    der ORM-Session (testbar ohne DB), analog zu
    `genesis_core.duplicates.MediaSnapshot`."""

    media_file_id: int
    extension: str
    container_format: str | None
    audio_codec: str | None
    bitrate_kbps: int | None
    sample_rate_hz: int | None
    bit_depth: int | None
    channels: int | None
    duration_seconds: float | None
    tag_duration_seconds: float | None
    size_bytes: int | None
    last_scan_error: str | None
    integrated_lufs: float | None
    true_peak_dbtp: float | None


@dataclasses.dataclass
class QualityReport:
    media_file_id: int
    suspected_upscale: bool
    suspected_transcode: bool
    suspected_corruption: bool
    suspected_truncation: bool
    notes: list[str]


def _normalize_extension(extension: str) -> str:
    return extension.lower().lstrip(".")


def _check_corruption(snapshot: QualitySnapshot, notes: list[str]) -> bool:
    """Deutliche technische Fehlanzeichen - KEIN Beweis fuer tatsaechliche
    Beschaedigung (z.B. kann ein kurzzeitig gesperrter Datenträger beim Scan
    denselben Effekt haben), daher stets als Verdacht formuliert."""
    suspected = False
    if snapshot.last_scan_error:
        suspected = True
        notes.append(
            f"Verdacht auf Beschädigung: Scanner meldete einen Fehler beim letzten "
            f"Einlesen ({snapshot.last_scan_error})."
        )
    size_present = snapshot.size_bytes is not None and snapshot.size_bytes > 0
    if size_present and (snapshot.duration_seconds is None or snapshot.duration_seconds <= 0):
        suspected = True
        notes.append(
            "Verdacht auf Beschädigung: Datei enthält Daten, aber es konnte keine "
            "gültige Dauer ermittelt werden."
        )
    return suspected


def _check_truncation(snapshot: QualitySnapshot, notes: list[str]) -> bool:
    """Vergleicht die vom Tag deklarierte Dauer mit der technisch gemessenen
    - NUR ein Indiz, kein Beweis (Tags können veraltet/falsch sein)."""
    if snapshot.tag_duration_seconds is None or snapshot.duration_seconds is None:
        return False
    diff = snapshot.tag_duration_seconds - snapshot.duration_seconds
    if diff <= _TRUNCATION_ABSOLUTE_MIN_SECONDS:
        return False
    if diff <= _TRUNCATION_RELATIVE_THRESHOLD * snapshot.tag_duration_seconds:
        return False
    notes.append(
        f"Verdacht auf abgeschnittene Datei: Tag gibt {snapshot.tag_duration_seconds:.1f}s an, "
        f"tatsächlich gemessen wurden nur {snapshot.duration_seconds:.1f}s."
    )
    return True


def _check_transcode(snapshot: QualitySnapshot, notes: list[str]) -> bool:
    """Dateiendung vs. tatsächlich enthaltenem Codec - ein Codec, der nicht
    zur Endung passt, ist ein belastbares (aber nicht zwingendes - z.B. Ogg
    kann mehrere Codecs enthalten) Signal fuer eine ungewöhnliche
    Umcodierung/Umbenennung."""
    if snapshot.audio_codec is None:
        return False
    ext = _normalize_extension(snapshot.extension)
    expected = _EXTENSION_CODEC_FAMILIES.get(ext)
    if expected is None:
        return False  # unbekannte/nicht katalogisierte Endung - keine Aussage möglich
    if snapshot.audio_codec in expected:
        return False
    notes.append(
        f"Verdacht auf ungewöhnliche Transcodierung: Dateiendung '.{ext}' erwartet "
        f"üblicherweise einen anderen Codec, tatsächlich enthalten ist "
        f"'{snapshot.audio_codec}'."
    )
    return True


def _check_upscale(snapshot: QualitySnapshot, notes: list[str]) -> bool:
    """Nur fuer echte, komprimierende verlustfreie Codecs (FLAC/ALAC)
    sinnvoll - rohes PCM hat eine durch das Format fest vorgegebene Bitrate
    und liefert daher kein Kompressions-Indiz."""
    if snapshot.audio_codec not in _COMPRESSED_LOSSLESS_CODECS:
        return False
    if (
        snapshot.bitrate_kbps is None
        or snapshot.sample_rate_hz is None
        or snapshot.channels is None
    ):
        return False
    bit_depth = snapshot.bit_depth or 16  # konservative Annahme, falls unbekannt
    raw_pcm_kbps = snapshot.sample_rate_hz * bit_depth * snapshot.channels / 1000
    if raw_pcm_kbps <= 0:
        return False
    ratio = snapshot.bitrate_kbps / raw_pcm_kbps
    if ratio >= _UPSCALE_RATIO_THRESHOLD:
        return False
    notes.append(
        f"Verdacht auf verdächtiges Upscale: verlustfrei codierte Datei "
        f"({snapshot.audio_codec}) hat nur {snapshot.bitrate_kbps} kbps bei "
        f"theoretisch {raw_pcm_kbps:.0f} kbps unkomprimiertem PCM "
        f"({ratio:.0%} - ungewöhnlich niedrig für echtes verlustfreies Material, "
        f"könnte auf eine ursprünglich verlustbehaftete Quelle hindeuten)."
    )
    return True


def _add_loudness_notes(snapshot: QualitySnapshot, notes: list[str]) -> None:
    """Rein informativ (§20 nennt "Peak, Loudness" explizit als zu
    analysierende Werte) - erzeugt KEIN eigenes suspected_*-Flag, da Lautheit
    allein kein Qualitätsmangel ist, sondern eine bewusste künstlerische/
    technische Entscheidung sein kann."""
    if snapshot.true_peak_dbtp is not None and snapshot.true_peak_dbtp > 0.0:
        notes.append(
            f"Hinweis: True Peak liegt bei {snapshot.true_peak_dbtp:.2f} dBTP über "
            "Vollaussteuerung (0 dBTP) - mögliches Clipping/Intersample-Übersteuern."
        )
    if snapshot.integrated_lufs is not None and snapshot.integrated_lufs < -40.0:
        notes.append(
            f"Hinweis: integrierte Lautheit sehr niedrig ({snapshot.integrated_lufs:.1f} LUFS) "
            "- möglicherweise (fast) stille Aufnahme oder Messfehler."
        )


def analyze_quality(snapshot: QualitySnapshot) -> QualityReport:
    """Fuehrt alle vier Verdachtsprüfungen durch und liefert einen
    QualityReport. Liefert bei fehlenden Eingangsdaten (z.B. noch keine
    TechnicalMetadata vorhanden) niedrigere Aussagekraft, aber NIEMALS einen
    falsch-positiven Verdacht nur wegen fehlender Daten (Prinzip #17 -
    fehlende Information führt zu "kein Befund", nie zu einer Vermutung)."""
    notes: list[str] = []
    suspected_corruption = _check_corruption(snapshot, notes)
    suspected_truncation = _check_truncation(snapshot, notes)
    suspected_transcode = _check_transcode(snapshot, notes)
    suspected_upscale = _check_upscale(snapshot, notes)
    _add_loudness_notes(snapshot, notes)

    if not notes:
        notes.append("Keine Auffälligkeiten festgestellt (Analyse, keine Garantie).")

    return QualityReport(
        media_file_id=snapshot.media_file_id,
        suspected_upscale=suspected_upscale,
        suspected_transcode=suspected_transcode,
        suspected_corruption=suspected_corruption,
        suspected_truncation=suspected_truncation,
        notes=notes,
    )
