"""Datenbankschema fuer GENESIS Media Manager.

Deckt die in Originalauftrag §7 geforderte Mindest-Entitaetsliste ab:
Media/Files, Artists, Albums, Tracks, Genres, Persons, Books, Audiobooks,
Series, Episodes, Movies, Podcasts, Chapters, Sources, Providers, Tags,
Artwork, Fingerprints, Loudness, TechnicalMetadata, AIMetadata,
VoiceProfiles, ProcessingJobs, ProcessingHistory, Backups, Licenses,
Settings.

Wichtige Prinzipien, die sich direkt im Schema niederschlagen:
- Prinzip #14/#15: ``MediaFile.absolute_path`` ist Pflichtfeld & eindeutig -
  die DB ist niemals die einzige Quelle, jede Datei bleibt ueber ihren realen
  Pfad referenziert.
- Prinzip #9/#16/#17: jede automatisch erzeugte Information (``AIMetadata``,
  aber auch Felder wie ``Track.source``/``confidence``) traegt Herkunft und
  Konfidenz; unsichere Ergebnisse ueberschreiben nutzergesetzte Werte nicht
  automatisch (das wird in der Metadata-Engine/Application-Schicht erzwungen,
  nicht nur im Schema).
- Prinzip #4/#43: ``MediaFile.is_missing`` markiert verschwundene Dateien statt
  sie zu loeschen.
"""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from genesis_core.db.base import Base, TimestampMixin


class MediaKind(str, enum.Enum):
    MUSIC = "music"
    AUDIOBOOK = "audiobook"
    MOVIE = "movie"
    EPISODE = "episode"
    PODCAST_EPISODE = "podcast_episode"
    AI_MUSIC = "ai_music"
    UNKNOWN = "unknown"


class AIStatus(str, enum.Enum):
    """§27 - AI Generated / Human Generated / Hybrid / Unknown."""

    AI_GENERATED = "ai_generated"
    HUMAN_GENERATED = "human_generated"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class PersonRoleType(str, enum.Enum):
    """§63 Wissensgraph: Person -> Artist/Actor/Director/Author/Speaker."""

    ARTIST = "artist"
    ACTOR = "actor"
    DIRECTOR = "director"
    AUTHOR = "author"
    NARRATOR = "narrator"
    COMPOSER = "composer"
    PUBLISHER = "publisher"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Zentrale Datei-/Medientabelle (Prinzip #14/#15)
# ---------------------------------------------------------------------------


class MediaFile(Base, TimestampMixin):
    """Die physische Datei. Jede Mediendatei existiert genau einmal hier.

    Niemals durch einen Scan veraendert (§6) - nur gelesen und beschrieben.
    """

    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    absolute_path: Mapped[str] = mapped_column(String(4096), unique=True, index=True)
    directory: Mapped[str] = mapped_column(String(4096), index=True)
    filename: Mapped[str] = mapped_column(String(1024))
    extension: Mapped[str] = mapped_column(String(32), index=True)

    kind: Mapped[MediaKind] = mapped_column(
        Enum(MediaKind), default=MediaKind.UNKNOWN, index=True
    )

    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mtime: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    content_hash_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    first_seen_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )
    last_scanned_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    is_missing: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    missing_since: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    # Ergebnis der letzten Klassifikation/Analyse (rein informativ, aendert
    # nie die Datei selbst).
    last_scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    tracks: Mapped[list[Track]] = relationship(back_populates="media_file")
    technical: Mapped[TechnicalMetadata] = relationship(
        back_populates="media_file", uselist=False
    )
    loudness_entries: Mapped[list[Loudness]] = relationship(back_populates="media_file")
    fingerprints: Mapped[list[Fingerprint]] = relationship(back_populates="media_file")
    audio_cuts: Mapped[list[AudioCut]] = relationship(back_populates="media_file")
    audio_conversions: Mapped[list[AudioConversion]] = relationship(back_populates="media_file")
    ai_metadata: Mapped[list[AIMetadata]] = relationship(back_populates="media_file")
    embeddings: Mapped[list[AIEmbedding]] = relationship(back_populates="media_file")
    sources: Mapped[list[Source]] = relationship(back_populates="media_file")
    chapters: Mapped[list[Chapter]] = relationship(back_populates="media_file")
    artwork: Mapped[list[Artwork]] = relationship(back_populates="media_file")


# ---------------------------------------------------------------------------
# Musik
# ---------------------------------------------------------------------------


class Genre(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Artist(Base, TimestampMixin):
    __tablename__ = "artists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    sort_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    albums: Mapped[list[Album]] = relationship(back_populates="artist")


class Album(Base, TimestampMixin):
    __tablename__ = "albums"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    artist_id: Mapped[int | None] = mapped_column(ForeignKey("artists.id"), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    artist: Mapped[Artist] = relationship(back_populates="albums")
    tracks: Mapped[list[Track]] = relationship(back_populates="album")


class Track(Base, TimestampMixin):
    """Musik-Titel-Metadaten fuer eine MediaFile (§14 Tag-Felder)."""

    __tablename__ = "tracks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id"), unique=True, index=True
    )

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    album_id: Mapped[int | None] = mapped_column(ForeignKey("albums.id"), nullable=True)
    album_artist: Mapped[str | None] = mapped_column(String(512), nullable=True)
    track_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disc_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genre_id: Mapped[int | None] = mapped_column(ForeignKey("genres.id"), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    composer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    copyright: Mapped[str | None] = mapped_column(String(512), nullable=True)
    lyrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Herkunft/Konfidenz der Metadaten (Prinzip #9/#16/#17)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    # KI-Musik-spezifische Felder (§27) - IMMER eine manuelle Nutzerangabe
    # (GENESIS kann KI-Urheberschaft nicht selbst feststellen), siehe
    # ai/music_provenance.py. "Kuenstlername" wird bewusst NICHT hier als
    # weiteres Textfeld dupliziert, sondern ueber eine PersonRole
    # (role=ARTIST, track_id=...) abgebildet - konsistent mit dem
    # Wissensgraph-Muster aus §63/Phase 5 (Regisseur/Schauspieler).
    ai_status: Mapped[AIStatus] = mapped_column(Enum(AIStatus), default=AIStatus.UNKNOWN)
    ai_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_creation_date: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    ai_instrumental: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_style: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_mood: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="tracks")
    album: Mapped[Album] = relationship(back_populates="tracks")


# ---------------------------------------------------------------------------
# Personen (Wissensgraph §63)
# ---------------------------------------------------------------------------


class Person(Base, TimestampMixin):
    __tablename__ = "persons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)

    roles: Mapped[list[PersonRole]] = relationship(back_populates="person")


class PersonRole(Base):
    """Verknuepft eine Person mit einer Rolle in Bezug auf ein Werk.

    Generisch gehalten (nullable FKs), damit derselbe Mensch z.B. als Autor
    eines Hoerbuchs UND als Sprecher eines anderen auftauchen kann (§63).
    """

    __tablename__ = "person_roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), index=True)
    role: Mapped[PersonRoleType] = mapped_column(Enum(PersonRoleType))

    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episodes.id"), nullable=True)
    audiobook_id: Mapped[int | None] = mapped_column(ForeignKey("audiobooks.id"), nullable=True)
    track_id: Mapped[int | None] = mapped_column(ForeignKey("tracks.id"), nullable=True)

    person: Mapped[Person] = relationship(back_populates="roles")


# ---------------------------------------------------------------------------
# Hoerbuecher (§23)
# ---------------------------------------------------------------------------


class Series(Base):
    """Generische Reihe - fuer Hoerbuch-Reihen UND TV-Serien nutzbar."""

    __tablename__ = "series"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    audiobooks: Mapped[list[Audiobook]] = relationship(back_populates="series")
    episodes: Mapped[list[Episode]] = relationship(back_populates="series")


class Audiobook(Base, TimestampMixin):
    __tablename__ = "audiobooks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id"), unique=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(512), nullable=True)
    narrator: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(512), nullable=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("series.id"), nullable=True)
    volume_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    series: Mapped[Series] = relationship(back_populates="audiobooks")


# ---------------------------------------------------------------------------
# Film & Serie (§24)
# ---------------------------------------------------------------------------


class Movie(Base, TimestampMixin):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id"), unique=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    runtime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Episode(Base, TimestampMixin):
    __tablename__ = "episodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id"), unique=True, index=True
    )
    series_id: Mapped[int | None] = mapped_column(ForeignKey("series.id"), nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    series: Mapped[Series] = relationship(back_populates="episodes")


# ---------------------------------------------------------------------------
# Podcast (§ Podcasts)
# ---------------------------------------------------------------------------


class Podcast(Base):
    __tablename__ = "podcasts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)

    episodes: Mapped[list[PodcastEpisode]] = relationship(back_populates="podcast")


class PodcastEpisode(Base, TimestampMixin):
    __tablename__ = "podcast_episodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id"), unique=True, index=True
    )
    podcast_id: Mapped[int] = mapped_column(ForeignKey("podcasts.id"))
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    publish_date: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    podcast: Mapped[Podcast] = relationship(back_populates="episodes")


# ---------------------------------------------------------------------------
# Kapitel (Hoerbuch/Film, §18/§23/§60)
# ---------------------------------------------------------------------------


class Chapter(Base):
    __tablename__ = "chapters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="chapters")


# ---------------------------------------------------------------------------
# Quellen & Provider (§10, §32)
# ---------------------------------------------------------------------------


class Provider(Base):
    """Registrierte Metadaten-/Download-/AI-/Artwork-Provider (§10, §34)."""

    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    provider_type: Mapped[str] = mapped_column(String(64))  # metadata/fingerprint/ai/...
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_internet: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Source(Base, TimestampMixin):
    """Herkunft einer importierten Datei (§32)."""

    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    original_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imported_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    import_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="sources")


# ---------------------------------------------------------------------------
# Tags, Artwork
# ---------------------------------------------------------------------------


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)


class Artwork(Base, TimestampMixin):
    """§22 Artwork Engine."""

    __tablename__ = "artwork"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id"), nullable=True, index=True
    )
    album_id: Mapped[int | None] = mapped_column(ForeignKey("albums.id"), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    # Deep-Review-Fund (Sitzung 3, F-11): Ohne dieses Feld musste der
    # tatsaechliche MIME-Typ beim spaeteren Einbetten aus der Cache-Datei-
    # Endung GERATEN werden (verlustbehaftet/fehleranfaellig) - jetzt wird
    # der vom Provider gelieferte MIME-Typ direkt mitgespeichert.
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="unknown")

    media_file: Mapped[MediaFile] = relationship(back_populates="artwork")


# ---------------------------------------------------------------------------
# Fingerprint (§12/§13), Loudness (§19), TechnicalMetadata
# ---------------------------------------------------------------------------


class Fingerprint(Base, TimestampMixin):
    __tablename__ = "fingerprints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)
    algorithm: Mapped[str] = mapped_column(String(64))  # z.B. "chromaprint"
    fingerprint_data: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="fingerprints")


class Loudness(Base, TimestampMixin):
    """§19 - LUFS/True-Peak-Messungen UND Normalisierungs-Ergebnisse.

    Jede Messung (Analyse) UND jede tatsaechlich durchgefuehrte Normalisierung
    erzeugt eine NEUE Zeile (volle Historie statt Ueberschreiben einer
    einzelnen "aktuellen" Zeile) - konsistent mit dem projektweiten Prinzip
    "jede Aenderung ist protokolliert/nachvollziehbar" (§44). Fuer eine reine
    Messung bleibt `normalized=False` und `target_lufs_used=None`; fuer eine
    angewendete Normalisierung wird `normalized=True` und `target_lufs_used`
    gesetzt (siehe genesis_core/loudness/engine.py).
    """

    __tablename__ = "loudness"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)
    integrated_lufs: Mapped[float | None] = mapped_column(Float, nullable=True)
    true_peak_dbtp: Mapped[float | None] = mapped_column(Float, nullable=True)
    loudness_range_lu: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Reserviert fuer eine kuenftige ergaenzende Sample-Peak-Messung (ohne
    # Oversampling) als Vergleichswert - die aktuelle, auf ffmpegs
    # `loudnorm`-Filter basierende Engine (ADR-0010) liefert nur True Peak
    # und befuellt dieses Feld daher bewusst NICHT (bleibt NULL).
    peak_dbfs: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_lufs_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_true_peak_dbtp_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized: Mapped[bool] = mapped_column(Boolean, default=False)
    # Bei normalized=True: Pfad der NEU erzeugten Datei (Original bleibt
    # unangetastet, Prinzip #4/#5 - siehe ADR-0010).
    normalized_output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    measured_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="loudness_entries")


class AudioCut(Base, TimestampMixin):
    """§18 - Ergebnisse des grafischen Audio-Cutters.

    Analog zu `Loudness`: jeder tatsaechlich ausgefuehrte Schnitt erzeugt
    eine NEUE Zeile (volle Historie, §44) statt eine bestehende zu
    ueberschreiben. Es gibt bewusst keine "reine Messung" wie bei Loudness -
    das Pendant dazu ist die rein lesende Waveform-Erzeugung
    (`genesis_core.cutter.engine.generate_waveform_image`), die NICHTS in die
    Datenbank schreibt, weil sie kein Ergebnis/keine Entscheidung darstellt,
    sondern nur eine Visualisierungshilfe ist.
    """

    __tablename__ = "audio_cuts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)
    source_path: Mapped[str] = mapped_column(String(1024))
    # Bei normalized=True analog: Original bleibt unangetastet, das Ergebnis
    # ist IMMER eine neue Datei (Prinzip #4/#5 - siehe ADR-0011).
    output_path: Mapped[str] = mapped_column(String(1024))
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    fade_in_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    fade_out_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    export_format: Mapped[str] = mapped_column(String(16))

    media_file: Mapped[MediaFile] = relationship(back_populates="audio_cuts")


class AudioConversion(Base, TimestampMixin):
    """Konvertierungs-Werkzeug (nav.convert) - Ergebnisse von
    Formatkonvertierungen.

    Analog zu `AudioCut`/`Loudness`: jede tatsaechlich ausgefuehrte
    Konvertierung erzeugt eine NEUE Zeile (volle Historie, §44). Original
    bleibt immer unangetastet (Prinzip #4/#5) - das Ergebnis ist immer eine
    neue Datei (`<stem>.converted.<ext>`).
    """

    __tablename__ = "audio_conversions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)
    source_path: Mapped[str] = mapped_column(String(1024))
    output_path: Mapped[str] = mapped_column(String(1024))
    source_format: Mapped[str] = mapped_column(String(16))
    target_format: Mapped[str] = mapped_column(String(16))
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="audio_conversions")


class DuplicateGroup(Base, TimestampMixin):
    """§21 - Ergebnis eines Duplikaterkennungs-Laufs (reine Analyse, Prinzip
    #4/#5 - es gibt bewusst KEINE Loeschfunktion, "Niemals automatisch
    löschen").

    Jeder Scan-Lauf ersetzt alle NICHT ueberprueften (`reviewed=False`)
    Gruppen durch die frisch erkannten (siehe
    `genesis_core.api.app::run_duplicate_scan`) - bereits vom Nutzer
    ueberprueft/verworfene Gruppen (`reviewed=True`) bleiben unangetastet,
    damit dieselbe Meldung nicht bei jedem erneuten Scan wieder auftaucht.
    """

    __tablename__ = "duplicate_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    matched_stages_json: Mapped[list] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )

    members: Mapped[list[DuplicateGroupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DuplicateGroupMember(Base, TimestampMixin):
    """Mitgliedschaft einer Mediendatei in einer erkannten Duplikatgruppe.
    Modelliert als N-zu-N-Verknuepfung (statt eines starren Paars), damit
    eine spaetere Erweiterung auf echte Mehr-Weg-Cluster (transitive
    Huelle mehrerer paarweiser Treffer) moeglich ist, ohne das Schema zu
    aendern - diese Version befuellt pro Gruppe bewusst nur zwei
    Mitglieder (ein erkanntes Paar), siehe ADR-0013."""

    __tablename__ = "duplicate_group_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duplicate_group_id: Mapped[int] = mapped_column(
        ForeignKey("duplicate_groups.id"), index=True
    )
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)

    group: Mapped[DuplicateGroup] = relationship(back_populates="members")
    media_file: Mapped[MediaFile] = relationship()


class TechnicalMetadata(Base, TimestampMixin):
    """Technische Analyse (§20, plus Video-Technik §3 Filme)."""

    __tablename__ = "technical_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(
        ForeignKey("media_files.id"), unique=True, index=True
    )

    container_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    video_codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bitrate_kbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    hdr: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    subtitles_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    languages_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chapters_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Qualitaets-/Verdachtsmomente (§20) - explizit als Verdacht markiert
    suspected_transcode: Mapped[bool] = mapped_column(Boolean, default=False)
    suspected_upscale: Mapped[bool] = mapped_column(Boolean, default=False)
    suspected_corruption: Mapped[bool] = mapped_column(Boolean, default=False)
    suspected_truncation: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_ffprobe_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    media_file: Mapped[MediaFile] = relationship(back_populates="technical")


# ---------------------------------------------------------------------------
# KI-Metadaten (§25) - generisches Key/Value-Modell mit Pflicht-Herkunftsfeldern
# ---------------------------------------------------------------------------


class AIMetadata(Base):
    """Jeder KI-Vorschlag (Genre, Stimmung, Sprache, Instrumente, ...).

    Bewusst generisch (EAV) statt starrer Spalten, weil §25 eine offene Liste
    moeglicher Vorschlagsfelder nennt und neue Provider/Modelle neue Felder
    liefern koennen, ohne das Schema aendern zu muessen (Prinzip #13).
    Jeder Eintrag MUSS is_ai_generated=True tragen (Prinzip #9) und wird nie
    automatisch als bestaetigte Metadatenquelle behandelt, bis ein Nutzer
    zustimmt (Prinzip #17, siehe metadata/engine.py).
    """

    __tablename__ = "ai_metadata"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)

    field_name: Mapped[str] = mapped_column(String(128))  # z.B. "genre", "mood"
    field_value: Mapped[str] = mapped_column(Text)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    model_name: Mapped[str] = mapped_column(String(255))
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )
    accepted_by_user: Mapped[bool] = mapped_column(Boolean, default=False)

    media_file: Mapped[MediaFile] = relationship(back_populates="ai_metadata")


class AIEmbedding(Base):
    """Lokaler Embedding-Vektor fuer die semantische Suche (§26).

    Bewusst EIN Eintrag pro (media_file_id, model_name) - ein Reindex
    ersetzt den vorhandenen Vektor, statt Historie anzusammeln (reine
    Such-Cache-Tabelle, kein Audit-Trail wie bei AIMetadata). `source_
    text_hash` erlaubt es, unveraendert gebliebene Mediendateien beim
    Reindex zu ueberspringen (§57 Performance bei grossen Bibliotheken).
    Erzeugt/aktualisiert ausschliesslich durch ai/search.py - niemals
    Grundlage fuer automatische Metadatenaenderungen (Prinzip #17).
    """

    __tablename__ = "ai_embeddings"
    __table_args__ = (UniqueConstraint("media_file_id", "model_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_file_id: Mapped[int] = mapped_column(ForeignKey("media_files.id"), index=True)

    model_name: Mapped[str] = mapped_column(String(255))
    dimension: Mapped[int] = mapped_column(Integer)
    vector_json: Mapped[list] = mapped_column(JSON)
    source_text_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )

    media_file: Mapped[MediaFile] = relationship(back_populates="embeddings")


# ---------------------------------------------------------------------------
# Voice Studio (§28/§29)
# ---------------------------------------------------------------------------


class VoiceProfile(Base, TimestampMixin):
    """Ein Stimmprofil (§28). Jedes Profil macht die vier Pflichtangaben aus
    dem Originalauftrag explizit sichtbar: Engine, Modell-Lizenz, Offline-
    Faehigkeit, Open-Source-Status, kommerzielle Nutzbarkeit - siehe
    ADR-0018. Diese Felder werden NIE automatisch/stillschweigend ermittelt;
    `genesis_core.voice.catalog` liefert lediglich UNVERBINDLICHE
    Vorschlagswerte fuer bekannte Engines, die der Nutzer beim Anlegen
    ausdruecklich bestaetigen oder aendern muss (Prinzip #9/#17)."""

    __tablename__ = "voice_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    engine: Mapped[str] = mapped_column(String(128))
    # Pfad zur lokalen Modelldatei (z.B. Piper .onnx). Optional, da
    # zukuenftige Engines ggf. kein externes Modell brauchen.
    model_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offline_capable: Mapped[bool] = mapped_column(Boolean, default=True)
    open_source: Mapped[bool] = mapped_column(Boolean, default=True)
    commercial_use_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Rein informative/optionale Referenz-Sprachprobe (z.B. hochgeladene
    # Aufnahme, "Stimme aufnehmen" / "Sprachproben verwalten" aus §28). Wird
    # von der aktuellen Piper-Engine NICHT fuer Voice-Cloning verwendet
    # (Piper synthetisiert aus vortrainierten Modellen, kein Cloning aus
    # kurzen Samples) - siehe ADR-0018 Backlog. Wird beim Loeschen des
    # Profils NIE automatisch von der Platte entfernt (Prinzip #4).
    sample_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    syntheses: Mapped[list[VoiceSynthesis]] = relationship(
        back_populates="voice_profile", cascade="all, delete-orphan"
    )


class VoiceSynthesis(Base, TimestampMixin):
    """Jede tatsaechlich erzeugte TTS-Ausgabe (§28 \"Text-to-Speech\"/\"Audio
    exportieren\") erzeugt eine neue Zeile (volle Historie, analog zu
    `AudioCut`/`Loudness`) statt etwas zu ueberschreiben. Der Audio-Export
    ist IMMER eine neue Datei - nichts Bestehendes wird je veraendert."""

    __tablename__ = "voice_syntheses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voice_profile_id: Mapped[int] = mapped_column(
        ForeignKey("voice_profiles.id"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    output_path: Mapped[str] = mapped_column(String(4096))
    export_format: Mapped[str] = mapped_column(String(16))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine: Mapped[str] = mapped_column(String(128))
    is_test_phrase: Mapped[bool] = mapped_column(Boolean, default=False)

    voice_profile: Mapped[VoiceProfile] = relationship(back_populates="syntheses")


# ---------------------------------------------------------------------------
# Jobs, Verlauf, Backups, Lizenzen, Settings (§17/§35/§36/§40/§33)
# ---------------------------------------------------------------------------


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # z.B. JOB-20260930-00127
    job_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    created_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    current_item: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    history: Mapped[list[ProcessingHistory]] = relationship(back_populates="job")


class ProcessingHistory(Base):
    """Rollback-Grundlage (§17): jede Einzelaenderung innerhalb eines Jobs."""

    __tablename__ = "processing_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    media_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_files.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64))  # rename/tag_update/delete/...
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )
    user_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)

    job: Mapped[ProcessingJob] = relationship(back_populates="history")


class Backup(Base):
    __tablename__ = "backups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )
    backup_type: Mapped[str] = mapped_column(String(64))  # db/config/rename_journal
    path: Mapped[str] = mapped_column(String(4096))
    version_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ErrorLog(Base):
    """§37 Fehlerbehandlung - "keine stillen Fehler". Jeder unerwartete
    Fehler bekommt eine eindeutige, dem Nutzer mitteilbare Error-ID
    (analog zu den JOB-IDs, siehe `genesis_core.errors`) sowie alle laut
    Originalauftrag geforderten Felder (Zeit/Komponente/Datei/Aktion/
    Fehlermeldung/technische Details/Lösungsvorschlag). Erwartete,
    bewusst gestaltete Validierungsfehler (z.B. "confirm fehlt" -> 422)
    landen NICHT hier - diese Tabelle ist für echte, unerwartete Fehler
    gedacht (siehe globaler Exception-Handler in api/app.py)."""

    __tablename__ = "error_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    error_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        default=lambda: dt.datetime.now(dt.UTC)
    )
    component: Mapped[str] = mapped_column(String(128))
    file_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    action: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    technical_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class LicenseEntry(Base):
    """§33 License Center - eine Zeile pro Abhaengigkeit/Modell."""

    __tablename__ = "licenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dependency_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    usage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redistribution_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    commercial_use_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class SettingRecord(Base):
    """Ergaenzende Laufzeit-Settings in der DB (Haupt-Settings leben in
    config.yaml, siehe genesis_core.config - diese Tabelle ist fuer
    Settings gedacht, die pro Bibliothek/Installation in der DB selbst
    sinnvoller aufgehoben sind, z.B. zuletzt genutzte UI-Filter)."""

    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
