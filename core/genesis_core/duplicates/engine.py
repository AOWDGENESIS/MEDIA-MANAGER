"""Mehrstufige Duplikaterkennung (§21, ADR-0013).

Reine, read-only Analyse (Prinzip #4/#5) - vergleicht ausschliesslich bereits
in der Datenbank vorhandene Informationen (Dateihash, Groesse, Dauer,
technische Parameter, Audio-Fingerprint, Metadaten) miteinander. Greift NIE
auf den Dateiinhalt direkt zu und veraendert/loescht NIEMALS eine Datei
(§21: "Niemals automatisch löschen" - diese Engine bietet daher bewusst
GAR KEINE Loeschfunktion an, nur Erkennung + Kategorisierung + Protokoll).

Mehrstufige Pruefung in der von §21 vorgegebenen Reihenfolge:
1. Dateihash (content_hash_sha256)   - identisch => Exaktes Duplikat
2. Groesse (size_bytes)              - Teil der "wahrscheinliches Duplikat"-Heuristik
3. Dauer (duration_seconds)          - mit kleiner Tolerenz (Encoding-Rundung)
4. technische Parameter (Codec/Samplerate/Kanaele)
5. Audio-Fingerprint (Chromaprint)   - erkennt denselben Inhalt ueber
                                        Formate/Encodings hinweg
6. Metadaten (Titel/Interpret/Album) - nur als zusaetzliches, bestaerkendes
                                        Signal (Confidence-Bonus), niemals
                                        allein ausschlaggebend

Vier Ergebniskategorien (§21, wortgleich uebernommen):
- EXACT_DUPLICATE               ("Exaktes Duplikat")
- PROBABLE_DUPLICATE            ("wahrscheinliches Duplikat")
- SAME_CONTENT_DIFFERENT_FORMAT ("gleicher Inhalt / anderes Format")
- SIMILAR_CONTENT               ("ähnlicher Inhalt")

Bewusste Vereinfachung (siehe ADR-0013 fuer die volle Begruendung): die
Fingerprint-Stufe vergleicht den von Chromaprint gelieferten, komprimierten
Fingerprint-STRING auf exakte Gleichheit, statt ihn in sein rohes
32-Bit-Integer-Array zu dekomprimieren und eine Hamming-Distanz-basierte
Aehnlichkeit zu berechnen. Empirisch (Sandbox-Test) liefert Chromaprint fuer
DIESELBE Aufnahme in unterschiedlichen Formaten/Bitrates einen BYTE-IDENTISCHEN
Fingerprint-String - das deckt die Kategorie "gleicher Inhalt / anderes
Format" zuverlaessig ab. Eine echte Fuzzy-Teilaehnlichkeit (z.B. leicht
unterschiedliches Mastering) wuerde eine eigene, von Grund auf neu
geschriebene Nachimplementierung von Chromaprints proprietaerem
Kompressionsformat erfordern (keine verlaessliche, gepflegte Python-Bibliothek
dafuer offline verfuegbar) - das Risiko einer fehlerhaften Nachimplementierung,
die unbemerkt falsche "Aehnlichkeits"-Ergebnisse als Fakt praesentiert, wiegt
schwerer als der Nutzen. Diese Version erkennt "ähnlicher Inhalt" daher nur
dort, wo Fingerprints exakt uebereinstimmen, aber Dauer/technische Parameter
abweichen (z.B. unterschiedlich getrimmte Version derselben Aufnahme) -
dokumentiertes Backlog fuer eine spaetere, eigens getestete Erweiterung.
"""
from __future__ import annotations

import dataclasses
import enum

DEFAULT_DURATION_TOLERANCE_SECONDS = 1.0


class DuplicateCategory(str, enum.Enum):
    EXACT_DUPLICATE = "exact_duplicate"
    PROBABLE_DUPLICATE = "probable_duplicate"
    SAME_CONTENT_DIFFERENT_FORMAT = "same_content_different_format"
    SIMILAR_CONTENT = "similar_content"


@dataclasses.dataclass(frozen=True)
class MediaSnapshot:
    """Unveraenderlicher Schnappschuss der fuer die Duplikaterkennung
    relevanten Felder EINER Mediendatei - entkoppelt die reine
    Vergleichslogik bewusst von der ORM-Session (testbar ohne DB)."""

    media_file_id: int
    absolute_path: str
    size_bytes: int | None
    content_hash_sha256: str | None
    duration_seconds: float | None
    audio_codec: str | None
    sample_rate_hz: int | None
    channels: int | None
    fingerprint: str | None
    title: str | None
    artist: str | None
    album: str | None


@dataclasses.dataclass
class DuplicateCandidate:
    media_file_id_a: int
    media_file_id_b: int
    category: DuplicateCategory
    confidence: float
    matched_stages: list[str]
    reason: str


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _duration_tolerance(a: float, b: float) -> float:
    """Encoding-/Container-Rundung kann die gemessene Dauer um Bruchteile
    einer Sekunde verschieben, selbst bei identischem Inhalt (siehe
    ADR-0011-Messungen) - relative Toleranz fuer laengere Dateien, aber
    mindestens die absolute Standardtoleranz fuer kurze Clips."""
    return max(DEFAULT_DURATION_TOLERANCE_SECONDS, 0.01 * max(a, b))


def compare_pair(
    a: MediaSnapshot, b: MediaSnapshot,
) -> DuplicateCandidate | None:
    """Vergleicht genau ZWEI Mediendateien stufenweise. Liefert `None`, wenn
    keine der vier Kategorien zutrifft (also KEIN Duplikatverdacht)."""
    if a.media_file_id == b.media_file_id:
        raise ValueError("Eine Datei kann nicht mit sich selbst verglichen werden.")

    matched_stages: list[str] = []

    # Stufe 1+2: Dateihash (impliziert gleiche Groesse bei SHA-256-Kollisionsfreiheit)
    hash_match = (
        a.content_hash_sha256 is not None
        and a.content_hash_sha256 == b.content_hash_sha256
    )
    if hash_match:
        return DuplicateCandidate(
            media_file_id_a=min(a.media_file_id, b.media_file_id),
            media_file_id_b=max(a.media_file_id, b.media_file_id),
            category=DuplicateCategory.EXACT_DUPLICATE,
            confidence=1.0,
            matched_stages=["hash", "size"],
            reason="Identischer Dateihash (SHA-256) - byteidentische Datei.",
        )

    size_match = (
        a.size_bytes is not None and b.size_bytes is not None and a.size_bytes == b.size_bytes
    )
    if size_match:
        matched_stages.append("size")

    duration_match = (
        a.duration_seconds is not None
        and b.duration_seconds is not None
        and abs(a.duration_seconds - b.duration_seconds)
        <= _duration_tolerance(a.duration_seconds, b.duration_seconds)
    )
    if duration_match:
        matched_stages.append("duration")

    technical_match = (
        a.audio_codec is not None
        and a.audio_codec == b.audio_codec
        and a.sample_rate_hz is not None
        and a.sample_rate_hz == b.sample_rate_hz
        and a.channels is not None
        and a.channels == b.channels
    )
    if technical_match:
        matched_stages.append("technical_params")

    fingerprint_match = (
        a.fingerprint is not None and a.fingerprint == b.fingerprint
    )
    if fingerprint_match:
        matched_stages.append("fingerprint")

    metadata_match = (
        _normalize_text(a.title) is not None
        and _normalize_text(a.title) == _normalize_text(b.title)
        and _normalize_text(a.artist) == _normalize_text(b.artist)
        and _normalize_text(a.album) == _normalize_text(b.album)
    )
    if metadata_match:
        matched_stages.append("metadata")

    metadata_bonus = 0.05 if metadata_match else 0.0

    if duration_match and technical_match:
        confidence = min(1.0, 0.80 + (0.1 if size_match else 0.0) + metadata_bonus)
        return DuplicateCandidate(
            media_file_id_a=min(a.media_file_id, b.media_file_id),
            media_file_id_b=max(a.media_file_id, b.media_file_id),
            category=DuplicateCategory.PROBABLE_DUPLICATE,
            confidence=round(confidence, 2),
            matched_stages=matched_stages,
            reason="Gleiche Dauer und gleiche technische Parameter (Codec/Samplerate/"
            "Kanäle) bei unterschiedlichem Dateihash - vermutlich unabhängig "
            "erzeugte Kopie derselben Quelle.",
        )

    if fingerprint_match and duration_match and not technical_match:
        confidence = min(1.0, 0.85 + metadata_bonus)
        return DuplicateCandidate(
            media_file_id_a=min(a.media_file_id, b.media_file_id),
            media_file_id_b=max(a.media_file_id, b.media_file_id),
            category=DuplicateCategory.SAME_CONTENT_DIFFERENT_FORMAT,
            confidence=round(confidence, 2),
            matched_stages=matched_stages,
            reason="Identischer Audio-Fingerprint und gleiche Dauer, aber andere "
            "technische Parameter - vermutlich dieselbe Aufnahme in einem "
            "anderen Format/Encoding.",
        )

    if fingerprint_match and not duration_match:
        confidence = min(1.0, 0.55 + metadata_bonus)
        return DuplicateCandidate(
            media_file_id_a=min(a.media_file_id, b.media_file_id),
            media_file_id_b=max(a.media_file_id, b.media_file_id),
            category=DuplicateCategory.SIMILAR_CONTENT,
            confidence=round(confidence, 2),
            matched_stages=matched_stages,
            reason="Übereinstimmender Audio-Fingerprint, aber abweichende Dauer - "
            "möglicherweise eine gekürzte/erweiterte Version derselben "
            "Aufnahme (Verdacht, keine Gewissheit).",
        )

    return None


def find_duplicate_candidates(snapshots: list[MediaSnapshot]) -> list[DuplicateCandidate]:
    """Vergleicht ALLE Paare innerhalb der gegebenen Liste (O(n²) - siehe
    Moduldocstring/ADR-0013 fuer den bewusst verschobenen
    Performance-Kompromiss bei sehr grossen Bibliotheken, §57) und liefert
    alle gefundenen Duplikat-Kandidaten, nach Confidence absteigend
    sortiert."""
    results: list[DuplicateCandidate] = []
    for i in range(len(snapshots)):
        for j in range(i + 1, len(snapshots)):
            candidate = compare_pair(snapshots[i], snapshots[j])
            if candidate is not None:
                results.append(candidate)
    results.sort(key=lambda c: c.confidence, reverse=True)
    return results
