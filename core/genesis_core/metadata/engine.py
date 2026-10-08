"""Metadata-Engine (§10/§11) - Erkennung, Konfidenzbewertung, Vorschlag.

Ablauf exakt nach dem projektweiten Grundprinzip:
    Erkennen -> Analysieren -> Vorschlag -> Confidence -> Vorschau ->
    Benutzerfreigabe -> Aenderung -> Protokoll -> Rollback-Moeglichkeit

Diese Engine deckt "Erkennen -> Vorschlag -> Confidence" ab
(`suggest_for_media_file`) sowie "Aenderung" (`apply_suggestion`) - die
Protokollierung fuer Rollback erfolgt bewusst NICHT hier, sondern in der
aufrufenden API-Schicht via `JobManager.record_history` (siehe
core/genesis_core/api/app.py). Grund: `apply_suggestion` haelt nur EINE
Datenbank-Transaktion offen; wuerde sie zusaetzlich `JobManager.record_history`
aufrufen (das intern eine EIGENE, zweite Transaktion/Session eroeffnet und
sofort committet), koennte das bei SQLite trotz WAL-Modus zu
"database is locked" fuehren, weil die aeussere Transaktion noch offen ist,
waehrend die innere ebenfalls schreiben will. Klare Trennung: eine
Engine-Funktion = eine Transaktion.

KEIN Provider/Diese Engine schreibt JEMALS automatisch, ohne dass
`user_confirmed=True` explizit von der aufrufenden Stelle (die selbst nur
nach echter Nutzerinteraktion True setzen darf) uebergeben wird (Prinzip
#17, §44).
"""
from __future__ import annotations

import dataclasses

from sqlalchemy import select

from genesis_core.config import MetadataSettings
from genesis_core.db.models import Album, Artist, MediaFile, Track
from genesis_core.fingerprint import FingerprintError, compute_fingerprint
from genesis_core.logutil import get_logger
from genesis_core.metadata.tag_reader import ExistingTags, read_existing_tags
from genesis_core.providers import ProviderBundle, ProviderError, ProviderNotConfiguredError
from genesis_core.providers.base import RecordingMatch

log = get_logger("MetadataEngine")

# Text-Suche ist strukturell unsicherer als ein Audio-Fingerprint-Treffer
# (Titel/Interpret koennen mehrdeutig sein, Cover-Versionen etc.) - dieser
# Faktor ist eine bewusste, dokumentierte HEURISTIK, keine gemessene
# Grosse. Er druecke lediglich aus: "auch ein 100%-Text-Treffer ist weniger
# verlaesslich als ein Fingerprint-Treffer mit demselben Score".
TEXT_SEARCH_CONFIDENCE_PENALTY = 0.85

MAX_FINGERPRINT_CANDIDATES_TO_ENRICH = 3


class MetadataApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn `apply_suggestion` ohne `user_confirmed=True`
    aufgerufen wird - harte Absicherung von Prinzip #17/§44 direkt im Code,
    nicht nur per Konvention."""


@dataclasses.dataclass
class MetadataSuggestion:
    media_file_id: int
    match: RecordingMatch
    method: str  # "fingerprint" oder "text_search"
    existing_tags: ExistingTags


class MetadataEngine:
    def __init__(self, providers: ProviderBundle, settings: MetadataSettings):
        self.providers = providers
        self.settings = settings

    def suggest_for_media_file(self, media_file: MediaFile) -> list[MetadataSuggestion]:
        """Liefert eine nach Konfidenz sortierte Liste moeglicher Treffer.
        Liefert NIEMALS erfundene Daten - eine leere Liste bedeutet "kein
        ausreichend sicherer Treffer gefunden", nicht "hier ist ein Rateergebnis"
        (Prinzip #16)."""
        if not self.settings.enabled:
            raise ProviderNotConfiguredError(
                "Online-Metadatenabgleich ist deaktiviert (Einstellungen -> "
                "Metadaten -> aktivieren)."
            )

        existing_tags = read_existing_tags(media_file.absolute_path)
        candidates, method = self._collect_candidates(media_file, existing_tags)

        filtered = [
            c for c in candidates if c.confidence >= self.settings.min_confidence_for_suggestion
        ]
        filtered.sort(key=lambda c: c.confidence, reverse=True)

        return [
            MetadataSuggestion(
                media_file_id=media_file.id, match=c, method=method, existing_tags=existing_tags
            )
            for c in filtered
        ]

    def _collect_candidates(
        self, media_file: MediaFile, existing_tags: ExistingTags
    ) -> tuple[list[RecordingMatch], str]:
        fingerprint_candidates = self._try_fingerprint_lookup(media_file)
        if fingerprint_candidates:
            return fingerprint_candidates, "fingerprint"

        text_candidates = self._try_text_search(existing_tags)
        return text_candidates, "text_search"

    def _try_fingerprint_lookup(self, media_file: MediaFile) -> list[RecordingMatch]:
        if self.providers.acoustid is None or not self.providers.acoustid.is_configured():
            return []

        try:
            fp = compute_fingerprint(media_file.absolute_path)
        except FingerprintError as exc:
            log.info("Kein Fingerprint fuer %s: %s", media_file.filename, exc)
            return []

        try:
            acoustid_matches = self.providers.acoustid.lookup(fp.fingerprint_data, fp.duration_seconds)
        except ProviderError as exc:
            log.warning("AcoustID-Abfrage fehlgeschlagen fuer %s: %s", media_file.filename, exc)
            return []

        enriched: list[RecordingMatch] = []
        for match in acoustid_matches[:MAX_FINGERPRINT_CANDIDATES_TO_ENRICH]:
            enriched.append(self._enrich_with_musicbrainz(match))
        return enriched

    def _enrich_with_musicbrainz(self, match: RecordingMatch) -> RecordingMatch:
        """Reichert einen AcoustID-Treffer um Album/Jahr/Tracknummer via
        MusicBrainz an. Schlaegt die Anreicherung fehl, wird der
        AcoustID-Treffer unveraendert zurueckgegeben (bessere unvollstaendige
        Daten als gar kein Vorschlag) - der Fehler wird geloggt, nicht
        verschluckt."""
        if self.providers.musicbrainz is None or not match.musicbrainz_recording_id:
            return match
        try:
            mb_match = self.providers.musicbrainz.lookup_recording(match.musicbrainz_recording_id)
        except ProviderError as exc:
            log.warning(
                "MusicBrainz-Anreicherung fehlgeschlagen fuer %s: %s",
                match.musicbrainz_recording_id, exc,
            )
            return match
        if mb_match is None:
            return match
        # Konfidenz bewusst vom AcoustID-Fingerprint-Treffer uebernehmen
        # (verlaesslicher als MusicBrainz' reiner Text-Score), nur die
        # inhaltlichen Felder von MusicBrainz uebernehmen.
        return dataclasses.replace(
            mb_match, confidence=match.confidence, provider="acoustid+musicbrainz"
        )

    def _try_text_search(self, existing_tags: ExistingTags) -> list[RecordingMatch]:
        if self.providers.musicbrainz is None or not existing_tags.title:
            return []
        try:
            matches = self.providers.musicbrainz.search_recordings(
                artist=existing_tags.artist, title=existing_tags.title
            )
        except ProviderError as exc:
            log.warning("MusicBrainz-Textsuche fehlgeschlagen: %s", exc)
            return []
        return [
            dataclasses.replace(m, confidence=m.confidence * TEXT_SEARCH_CONFIDENCE_PENALTY)
            for m in matches
        ]

    def apply_suggestion(
        self, session, media_file_id: int, suggestion: MetadataSuggestion, *, user_confirmed: bool
    ) -> Track:
        """Uebernimmt einen Vorschlag in die Datenbank. Erfordert IMMER
        `user_confirmed=True` (Prinzip #17/§44) - der Aufrufer darf dies nur
        nach einer echten Nutzerbestaetigung setzen, niemals als Default.
        Gibt vorher/nachher-Zustand nicht selbst weg (siehe Moduldocstring) -
        die aufrufende Stelle erstellt daraus bei Bedarf einen
        Protokolleintrag (`JobManager.record_history`).
        """
        if not user_confirmed:
            raise MetadataApplyNotConfirmedError(
                "Ein Metadatenvorschlag darf nur nach expliziter "
                "Nutzerbestaetigung uebernommen werden (Prinzip #17, §44)."
            )

        media_file = session.get(MediaFile, media_file_id)
        if media_file is None:
            raise ValueError(f"MediaFile {media_file_id} nicht gefunden.")

        match = suggestion.match

        artist_obj = self._get_or_create_artist(session, match)
        album_obj = self._get_or_create_album(session, match, artist_obj)

        track = session.execute(
            select(Track).where(Track.media_file_id == media_file_id)
        ).scalar_one_or_none()
        if track is None:
            track = Track(media_file_id=media_file_id)
            session.add(track)

        if match.title:
            track.title = match.title
        if album_obj is not None:
            track.album_id = album_obj.id
        if match.artist:
            track.album_artist = match.artist
        if match.track_number is not None:
            track.track_number = match.track_number
        if match.year is not None:
            track.year = match.year
        track.source = f"provider:{match.provider}"
        track.confidence = match.confidence
        track.is_user_confirmed = True

        session.flush()
        log.info(
            "Metadatenvorschlag uebernommen fuer MediaFile %d: %s - %s (Konfidenz %.2f)",
            media_file_id, match.artist, match.title, match.confidence,
        )
        return track

    @staticmethod
    def _get_or_create_artist(session, match: RecordingMatch) -> Artist | None:
        if not match.artist:
            return None
        artist = session.execute(
            select(Artist).where(Artist.name == match.artist)
        ).scalar_one_or_none()
        if artist is None:
            artist = Artist(name=match.artist, musicbrainz_id=match.musicbrainz_artist_id)
            session.add(artist)
            session.flush()
        elif match.musicbrainz_artist_id and not artist.musicbrainz_id:
            artist.musicbrainz_id = match.musicbrainz_artist_id
        return artist

    @staticmethod
    def _get_or_create_album(session, match: RecordingMatch, artist: Artist | None) -> Album | None:
        if not match.album:
            return None
        query = select(Album).where(Album.title == match.album)
        if artist is not None:
            query = query.where(Album.artist_id == artist.id)
        album = session.execute(query).scalar_one_or_none()
        if album is None:
            album = Album(
                title=match.album,
                artist_id=artist.id if artist else None,
                year=match.year,
                musicbrainz_id=match.musicbrainz_release_id,
            )
            session.add(album)
            session.flush()
        elif match.musicbrainz_release_id and not album.musicbrainz_id:
            album.musicbrainz_id = match.musicbrainz_release_id
        return album
