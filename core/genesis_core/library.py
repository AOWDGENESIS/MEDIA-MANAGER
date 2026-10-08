"""Bibliotheks-Drill-down (§9/§62, Gap-Analyse B).

Rein lesende Aggregations-/Browsing-Abfragen (Prinzip #4/#5 - veraendert
nichts) oberhalb der bereits bestehenden Datenmodelle (`genesis_core.db.
models`) - es werden KEINE neuen Tabellen eingefuehrt. Schliesst die bisher
als reine Navigations-Platzhalter verdrahteten Bibliotheksseiten
(Interpreten/Alben/Titel/Genres/Personen/Quellen) mit echten Daten.

Bekannte, bewusst nicht "behobene" Modellgrenze: `Track` hat keine direkte
Fremdschluessel-Beziehung zu `Artist` - nur ueber `Track.album_id ->
Album.artist_id` (plus das reine Freitextfeld `Track.album_artist`). Ein
Titel ohne zugeordnetes Album taucht daher in `list_artists()`/
`get_artist_detail()` nicht unter seinem Interpreten auf (wohl aber in
`list_tracks()`, wo `album_artist` als Fallback verwendet wird). Das ist
eine bestehende Grenze des Datenmodells, keine neue Einschraenkung dieses
Moduls - eine Erweiterung des Schemas waere eine eigene, groessere
Entscheidung ausserhalb des Umfangs dieser Gap-Schliessung.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from genesis_core.db.models import (
    AIStatus,
    Album,
    Artist,
    Artwork,
    Audiobook,
    DuplicateGroup,
    DuplicateGroupMember,
    Episode,
    Genre,
    Loudness,
    MediaFile,
    MediaKind,
    Movie,
    Person,
    PersonRole,
    Podcast,
    PodcastEpisode,
    Series,
    Source,
    TechnicalMetadata,
    Track,
)

# --- Interpreten --------------------------------------------------------------


@dataclass
class ArtistSummary:
    id: int
    name: str
    sort_name: str | None
    album_count: int
    track_count: int


@dataclass
class AlbumSummary:
    id: int
    title: str
    artist_id: int | None
    artist_name: str | None
    year: int | None
    track_count: int


@dataclass
class ArtistDetail:
    id: int
    name: str
    sort_name: str | None
    musicbrainz_id: str | None
    albums: list[AlbumSummary] = field(default_factory=list)


def list_artists(session: Session, search: str | None = None) -> list[ArtistSummary]:
    stmt = (
        select(
            Artist.id,
            Artist.name,
            Artist.sort_name,
            func.count(func.distinct(Album.id)).label("album_count"),
            func.count(func.distinct(Track.id)).label("track_count"),
        )
        .outerjoin(Album, Album.artist_id == Artist.id)
        .outerjoin(Track, Track.album_id == Album.id)
        .group_by(Artist.id)
        .order_by(func.coalesce(Artist.sort_name, Artist.name))
    )
    if search:
        stmt = stmt.where(Artist.name.ilike(f"%{search}%"))
    rows = session.execute(stmt).all()
    return [
        ArtistSummary(
            id=r.id, name=r.name, sort_name=r.sort_name,
            album_count=r.album_count, track_count=r.track_count,
        )
        for r in rows
    ]


def get_artist_detail(session: Session, artist_id: int) -> ArtistDetail | None:
    artist = session.get(Artist, artist_id)
    if artist is None:
        return None
    album_rows = session.execute(
        select(
            Album.id, Album.title, Album.year,
            func.count(Track.id).label("track_count"),
        )
        .outerjoin(Track, Track.album_id == Album.id)
        .where(Album.artist_id == artist_id)
        .group_by(Album.id)
        .order_by(Album.year, Album.title)
    ).all()
    albums = [
        AlbumSummary(
            id=r.id, title=r.title, artist_id=artist_id, artist_name=artist.name,
            year=r.year, track_count=r.track_count,
        )
        for r in album_rows
    ]
    return ArtistDetail(
        id=artist.id, name=artist.name, sort_name=artist.sort_name,
        musicbrainz_id=artist.musicbrainz_id, albums=albums,
    )


# --- Alben ----------------------------------------------------------------


@dataclass
class TrackSummary:
    id: int
    media_file_id: int
    title: str | None
    track_number: int | None
    disc_number: int | None
    duration_seconds: float | None


@dataclass
class AlbumDetail:
    id: int
    title: str
    artist_id: int | None
    artist_name: str | None
    year: int | None
    musicbrainz_id: str | None
    tracks: list[TrackSummary] = field(default_factory=list)


def list_albums(session: Session, search: str | None = None) -> list[AlbumSummary]:
    stmt = (
        select(
            Album.id, Album.title, Album.artist_id, Artist.name.label("artist_name"),
            Album.year, func.count(Track.id).label("track_count"),
        )
        .outerjoin(Artist, Album.artist_id == Artist.id)
        .outerjoin(Track, Track.album_id == Album.id)
        .group_by(Album.id)
        .order_by(Album.year, Album.title)
    )
    if search:
        stmt = stmt.where(Album.title.ilike(f"%{search}%"))
    rows = session.execute(stmt).all()
    return [
        AlbumSummary(
            id=r.id, title=r.title, artist_id=r.artist_id, artist_name=r.artist_name,
            year=r.year, track_count=r.track_count,
        )
        for r in rows
    ]


def get_album_detail(session: Session, album_id: int) -> AlbumDetail | None:
    album = session.get(Album, album_id)
    if album is None:
        return None
    artist_name = album.artist.name if album.artist_id and album.artist else None
    track_rows = session.execute(
        select(Track)
        .where(Track.album_id == album_id)
        .order_by(Track.disc_number, Track.track_number)
    ).scalars().all()
    tracks = [
        TrackSummary(
            id=t.id, media_file_id=t.media_file_id, title=t.title,
            track_number=t.track_number, disc_number=t.disc_number,
            duration_seconds=t.duration_seconds,
        )
        for t in track_rows
    ]
    return AlbumDetail(
        id=album.id, title=album.title, artist_id=album.artist_id, artist_name=artist_name,
        year=album.year, musicbrainz_id=album.musicbrainz_id, tracks=tracks,
    )


# --- Titel (flache Track-Liste) --------------------------------------------


@dataclass
class TrackListEntry:
    id: int
    media_file_id: int
    title: str | None
    artist_name: str | None
    album_title: str | None
    genre_name: str | None
    year: int | None
    track_number: int | None
    duration_seconds: float | None


def list_tracks(
    session: Session, search: str | None = None, limit: int = 200, offset: int = 0,
) -> tuple[int, list[TrackListEntry]]:
    """§9 "Titel" - flache, durchsuchbare Liste ueber ALLE Musiktitel
    (unabhaengig davon, ob einem Album zugeordnet)."""
    stmt = (
        select(Track, Album.title.label("album_title"), Artist.name.label("artist_name"),
               Genre.name.label("genre_name"))
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(Artist, Album.artist_id == Artist.id)
        .outerjoin(Genre, Track.genre_id == Genre.id)
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (Track.title.ilike(like)) | (Album.title.ilike(like)) | (Artist.name.ilike(like))
        )
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(Track.title).offset(offset).limit(limit)
    rows = session.execute(stmt).all()
    entries = [
        TrackListEntry(
            id=t.id, media_file_id=t.media_file_id, title=t.title,
            artist_name=artist_name or t.album_artist, album_title=album_title,
            genre_name=genre_name, year=t.year, track_number=t.track_number,
            duration_seconds=t.duration_seconds,
        )
        for t, album_title, artist_name, genre_name in rows
    ]
    return total, entries


# --- Genres -----------------------------------------------------------------


@dataclass
class GenreSummary:
    id: int
    name: str
    track_count: int


@dataclass
class GenreDetail:
    id: int
    name: str
    tracks: list[TrackListEntry] = field(default_factory=list)


def list_genres(session: Session, search: str | None = None) -> list[GenreSummary]:
    stmt = (
        select(Genre.id, Genre.name, func.count(Track.id).label("track_count"))
        .outerjoin(Track, Track.genre_id == Genre.id)
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    if search:
        stmt = stmt.where(Genre.name.ilike(f"%{search}%"))
    rows = session.execute(stmt).all()
    return [GenreSummary(id=r.id, name=r.name, track_count=r.track_count) for r in rows]


def get_genre_detail(session: Session, genre_id: int) -> GenreDetail | None:
    genre = session.get(Genre, genre_id)
    if genre is None:
        return None
    rows = session.execute(
        select(Track, Album.title.label("album_title"), Artist.name.label("artist_name"))
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(Artist, Album.artist_id == Artist.id)
        .where(Track.genre_id == genre_id)
        .order_by(Track.title)
    ).all()
    tracks = [
        TrackListEntry(
            id=t.id, media_file_id=t.media_file_id, title=t.title,
            artist_name=artist_name or t.album_artist, album_title=album_title,
            genre_name=genre.name, year=t.year, track_number=t.track_number,
            duration_seconds=t.duration_seconds,
        )
        for t, album_title, artist_name in rows
    ]
    return GenreDetail(id=genre.id, name=genre.name, tracks=tracks)


# --- Personen (Wissensgraph §63) -------------------------------------------


@dataclass
class PersonSummary:
    id: int
    name: str
    role_count: int


@dataclass
class PersonRoleEntry:
    role: str
    work_kind: str
    work_id: int
    work_title: str | None
    media_file_id: int | None


@dataclass
class PersonDetail:
    id: int
    name: str
    roles: list[PersonRoleEntry] = field(default_factory=list)


def list_persons(session: Session, search: str | None = None) -> list[PersonSummary]:
    stmt = (
        select(Person.id, Person.name, func.count(PersonRole.id).label("role_count"))
        .outerjoin(PersonRole, PersonRole.person_id == Person.id)
        .group_by(Person.id)
        .order_by(Person.name)
    )
    if search:
        stmt = stmt.where(Person.name.ilike(f"%{search}%"))
    rows = session.execute(stmt).all()
    return [PersonSummary(id=r.id, name=r.name, role_count=r.role_count) for r in rows]


def get_person_detail(session: Session, person_id: int) -> PersonDetail | None:
    person = session.get(Person, person_id)
    if person is None:
        return None
    roles: list[PersonRoleEntry] = []
    for pr in person.roles:
        if pr.movie_id is not None:
            movie = session.get(Movie, pr.movie_id)
            roles.append(PersonRoleEntry(
                role=pr.role.value, work_kind="movie", work_id=pr.movie_id,
                work_title=movie.title if movie else None,
                media_file_id=movie.media_file_id if movie else None,
            ))
        elif pr.episode_id is not None:
            episode = session.get(Episode, pr.episode_id)
            roles.append(PersonRoleEntry(
                role=pr.role.value, work_kind="episode", work_id=pr.episode_id,
                work_title=episode.title if episode else None,
                media_file_id=episode.media_file_id if episode else None,
            ))
        elif pr.audiobook_id is not None:
            audiobook = session.get(Audiobook, pr.audiobook_id)
            roles.append(PersonRoleEntry(
                role=pr.role.value, work_kind="audiobook", work_id=pr.audiobook_id,
                work_title=audiobook.title if audiobook else None,
                media_file_id=audiobook.media_file_id if audiobook else None,
            ))
        elif pr.track_id is not None:
            track = session.get(Track, pr.track_id)
            roles.append(PersonRoleEntry(
                role=pr.role.value, work_kind="track", work_id=pr.track_id,
                work_title=track.title if track else None,
                media_file_id=track.media_file_id if track else None,
            ))
    return PersonDetail(id=person.id, name=person.name, roles=roles)


# --- Quellen (§32) ------------------------------------------------------------


@dataclass
class SourceEntry:
    id: int
    media_file_id: int
    filename: str | None
    source_name: str | None
    provider_name: str | None
    original_url: str | None
    original_id: str | None
    imported_at: str | None
    import_method: str | None


def list_sources(
    session: Session, search: str | None = None, limit: int = 200, offset: int = 0,
) -> tuple[int, list[SourceEntry]]:
    stmt = select(Source, MediaFile.filename).join(
        MediaFile, Source.media_file_id == MediaFile.id
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (Source.source_name.ilike(like))
            | (Source.provider_name.ilike(like))
            | (MediaFile.filename.ilike(like))
        )
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(Source.imported_at.desc()).offset(offset).limit(limit)
    rows = session.execute(stmt).all()
    entries = [
        SourceEntry(
            id=s.id, media_file_id=s.media_file_id, filename=filename,
            source_name=s.source_name, provider_name=s.provider_name,
            original_url=s.original_url, original_id=s.original_id,
            imported_at=s.imported_at.isoformat() if s.imported_at else None,
            import_method=s.import_method,
        )
        for s, filename in rows
    ]
    return total, entries


# --- Erweiterte Suche/Filter (§9, Gap-Analyse C) -----------------------------
#
# Loest Gap C: `GET /media` filterte bisher nur nach `kind` und einem reinen
# Dateiname-/Pfad-Substring. §9 fordert deutlich mehr Such-/Filterfelder
# (Interpret, Album, Genre, Autor, Sprecher, Serie, Staffel, Episode, Quelle,
# Jahr, KI-Status, Format, Dateigroesse, Dauer, Lautheit, Qualitaetsverdacht,
# fehlende Metadaten, fehlendes Cover, Duplikate). Rein lesend (Prinzip
# #4/#5) - veraendert keine Datensaetze, baut nur eine erweiterte Abfrage.
#
# Ein-zu-viele-Beziehungen (Source, PersonRole-Pfade, Loudness, Duplikate,
# Artwork) werden bewusst als EXISTS-/IN-Unterabfragen angehaengt statt als
# JOIN, damit eine `MediaFile`-Zeile mit z.B. drei Quellen nicht dreifach in
# der Trefferliste auftaucht.


def _person_match_subquery(name_like: str):
    """Liefert eine Liste passender `media_file_id`s fuer eine Personensuche
    (§63 Wissensgraph) - eine Person kann ueber vier verschiedene Wege mit
    einer Mediendatei verknuepft sein (Film, Episode, Hoerbuch, Musiktitel),
    je nachdem, in welcher Rolle (Autor/Sprecher/Regisseur/Schauspieler/
    Komponist/Verlag/Interpret) sie auftritt."""
    return (
        select(Movie.media_file_id)
        .join(PersonRole, PersonRole.movie_id == Movie.id)
        .join(Person, Person.id == PersonRole.person_id)
        .where(Person.name.ilike(name_like))
        .union(
            select(Episode.media_file_id)
            .join(PersonRole, PersonRole.episode_id == Episode.id)
            .join(Person, Person.id == PersonRole.person_id)
            .where(Person.name.ilike(name_like)),
            select(Audiobook.media_file_id)
            .join(PersonRole, PersonRole.audiobook_id == Audiobook.id)
            .join(Person, Person.id == PersonRole.person_id)
            .where(Person.name.ilike(name_like)),
            select(Track.media_file_id)
            .join(PersonRole, PersonRole.track_id == Track.id)
            .join(Person, Person.id == PersonRole.person_id)
            .where(Person.name.ilike(name_like)),
        )
    )


def _series_match_subquery(name_like: str):
    """`Series` wird sowohl von Hoerbuch-Reihen als auch von TV-Serien
    genutzt (`genesis_core.db.models.Series`-Docstring) - beide Pfade
    werden hier beruecksichtigt."""
    return select(Audiobook.media_file_id).join(
        Series, Series.id == Audiobook.series_id
    ).where(Series.name.ilike(name_like)).union(
        select(Episode.media_file_id)
        .join(Series, Series.id == Episode.series_id)
        .where(Series.name.ilike(name_like))
    )


def build_media_search_statement(
    *,
    kind: MediaKind | None = None,
    search: str | None = None,
    year: int | None = None,
    genre: str | None = None,
    extension: str | None = None,
    min_size_bytes: int | None = None,
    max_size_bytes: int | None = None,
    min_duration_s: float | None = None,
    max_duration_s: float | None = None,
    source: str | None = None,
    person: str | None = None,
    series: str | None = None,
    season: int | None = None,
    episode_number: int | None = None,
    ai_status: str | None = None,
    min_lufs: float | None = None,
    max_lufs: float | None = None,
    has_quality_issues: bool | None = None,
    missing_metadata: bool | None = None,
    missing_cover: bool | None = None,
    duplicate_only: bool | None = None,
):
    """Baut die vollstaendige, gefilterte `MediaFile`-Abfrage fuer `GET
    /media` (§9). Gibt ein SQLAlchemy-`Select` zurueck, das der Aufrufer noch
    mit `.offset()`/`.limit()` versehen und ausfuehren muss (identisches
    Muster zum bisherigen, einfacheren `list_media`-Code in `api/app.py`)."""
    stmt = select(MediaFile).where(MediaFile.is_missing == False)

    if kind is not None:
        stmt = stmt.where(MediaFile.kind == kind)

    if extension:
        stmt = stmt.where(MediaFile.extension.ilike(extension.lstrip(".")))

    if min_size_bytes is not None:
        stmt = stmt.where(MediaFile.size_bytes >= min_size_bytes)
    if max_size_bytes is not None:
        stmt = stmt.where(MediaFile.size_bytes <= max_size_bytes)

    if year is not None:
        year_media_ids = (
            select(Track.media_file_id).where(Track.year == year)
            .union(
                select(Audiobook.media_file_id).where(Audiobook.year == year),
                select(Movie.media_file_id).where(Movie.year == year),
                select(Episode.media_file_id).where(Episode.year == year),
            )
        )
        stmt = stmt.where(MediaFile.id.in_(select(year_media_ids.subquery().c.media_file_id)))

    if genre:
        like = f"%{genre}%"
        genre_media_ids = (
            select(Track.media_file_id)
            .join(Genre, Genre.id == Track.genre_id)
            .where(Genre.name.ilike(like))
            .union(select(Movie.media_file_id).where(Movie.genre.ilike(like)))
        )
        stmt = stmt.where(MediaFile.id.in_(select(genre_media_ids.subquery().c.media_file_id)))

    if source:
        like = f"%{source}%"
        source_media_ids = select(Source.media_file_id).where(
            or_(Source.source_name.ilike(like), Source.provider_name.ilike(like))
        )
        stmt = stmt.where(MediaFile.id.in_(source_media_ids))

    if person:
        like = f"%{person}%"
        stmt = stmt.where(
            MediaFile.id.in_(select(_person_match_subquery(like).subquery().c.media_file_id))
        )

    if series:
        like = f"%{series}%"
        stmt = stmt.where(
            MediaFile.id.in_(select(_series_match_subquery(like).subquery().c.media_file_id))
        )

    if season is not None:
        stmt = stmt.where(
            MediaFile.id.in_(select(Episode.media_file_id).where(Episode.season_number == season))
        )

    if episode_number is not None:
        stmt = stmt.where(
            MediaFile.id.in_(
                select(Episode.media_file_id).where(Episode.episode_number == episode_number)
            )
        )

    if ai_status:
        try:
            status_enum = AIStatus(ai_status)
        except ValueError:
            status_enum = None
        if status_enum is not None:
            stmt = stmt.where(
                MediaFile.id.in_(
                    select(Track.media_file_id).where(Track.ai_status == status_enum)
                )
            )

    if min_duration_s is not None or max_duration_s is not None:
        duration_media_ids = select(Track.media_file_id)
        if min_duration_s is not None:
            duration_media_ids = duration_media_ids.where(
                Track.duration_seconds >= min_duration_s
            )
        if max_duration_s is not None:
            duration_media_ids = duration_media_ids.where(
                Track.duration_seconds <= max_duration_s
            )
        technical_media_ids = select(TechnicalMetadata.media_file_id)
        if min_duration_s is not None:
            technical_media_ids = technical_media_ids.where(
                TechnicalMetadata.duration_seconds >= min_duration_s
            )
        if max_duration_s is not None:
            technical_media_ids = technical_media_ids.where(
                TechnicalMetadata.duration_seconds <= max_duration_s
            )
        combined = duration_media_ids.union(technical_media_ids)
        stmt = stmt.where(MediaFile.id.in_(select(combined.subquery().c.media_file_id)))

    if min_lufs is not None or max_lufs is not None:
        lufs_media_ids = select(Loudness.media_file_id)
        if min_lufs is not None:
            lufs_media_ids = lufs_media_ids.where(Loudness.integrated_lufs >= min_lufs)
        if max_lufs is not None:
            lufs_media_ids = lufs_media_ids.where(Loudness.integrated_lufs <= max_lufs)
        stmt = stmt.where(MediaFile.id.in_(lufs_media_ids))

    if has_quality_issues:
        stmt = stmt.where(
            MediaFile.id.in_(
                select(TechnicalMetadata.media_file_id).where(
                    or_(
                        TechnicalMetadata.suspected_transcode == True,
                        TechnicalMetadata.suspected_upscale == True,
                        TechnicalMetadata.suspected_corruption == True,
                        TechnicalMetadata.suspected_truncation == True,
                    )
                )
            )
        )

    if missing_cover:
        stmt = stmt.where(
            MediaFile.id.not_in(select(Artwork.media_file_id))
        )

    if duplicate_only:
        stmt = stmt.where(
            MediaFile.id.in_(
                select(DuplicateGroupMember.media_file_id)
                .join(DuplicateGroup, DuplicateGroup.id == DuplicateGroupMember.duplicate_group_id)
                .where(DuplicateGroup.reviewed == False)
            )
        )

    if missing_metadata:
        # "Fehlende Metadaten" bedeutet je nach Art einen fehlenden Titel -
        # das zentrale, fuer alle Arten vorhandene Pflichtfeld (§9/§14).
        missing_media_ids = (
            select(Track.media_file_id).where(Track.title.is_(None))
            .union(
                select(Audiobook.media_file_id).where(Audiobook.title.is_(None)),
                select(Movie.media_file_id).where(Movie.title.is_(None)),
                select(Episode.media_file_id).where(Episode.title.is_(None)),
                select(PodcastEpisode.media_file_id).where(PodcastEpisode.title.is_(None)),
            )
        )
        stmt = stmt.where(
            MediaFile.id.in_(select(missing_media_ids.subquery().c.media_file_id))
        )

    if search:
        like = f"%{search}%"
        text_match_media_ids = (
            select(Track.media_file_id).where(Track.title.ilike(like))
            .union(
                select(Track.media_file_id)
                .join(Album, Album.id == Track.album_id)
                .where(Album.title.ilike(like)),
                select(Track.media_file_id)
                .join(Album, Album.id == Track.album_id)
                .join(Artist, Artist.id == Album.artist_id)
                .where(Artist.name.ilike(like)),
                select(Track.media_file_id).where(Track.album_artist.ilike(like)),
                select(Track.media_file_id)
                .join(Genre, Genre.id == Track.genre_id)
                .where(Genre.name.ilike(like)),
                select(Audiobook.media_file_id).where(
                    or_(
                        Audiobook.title.ilike(like),
                        Audiobook.author.ilike(like),
                        Audiobook.narrator.ilike(like),
                    )
                ),
                select(Movie.media_file_id).where(
                    or_(Movie.title.ilike(like), Movie.original_title.ilike(like))
                ),
                select(Episode.media_file_id).where(Episode.title.ilike(like)),
                select(Episode.media_file_id)
                .join(Series, Series.id == Episode.series_id)
                .where(Series.name.ilike(like)),
                select(Audiobook.media_file_id)
                .join(Series, Series.id == Audiobook.series_id)
                .where(Series.name.ilike(like)),
                select(PodcastEpisode.media_file_id).where(PodcastEpisode.title.ilike(like)),
                select(PodcastEpisode.media_file_id)
                .join(Podcast, Podcast.id == PodcastEpisode.podcast_id)
                .where(Podcast.name.ilike(like)),
                select(Source.media_file_id).where(
                    or_(Source.source_name.ilike(like), Source.provider_name.ilike(like))
                ),
                select(_person_match_subquery(like).subquery().c.media_file_id),
            )
        )
        stmt = stmt.where(
            or_(
                MediaFile.filename.ilike(like),
                MediaFile.absolute_path.ilike(like),
                MediaFile.id.in_(select(text_match_media_ids.subquery().c.media_file_id)),
            )
        )

    return stmt
