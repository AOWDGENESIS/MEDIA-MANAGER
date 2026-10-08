"""Artwork-Ein-/Ausgabe je Containerformat. Siehe Paket-Docstring fuer die
Sicherheitsabstufung der drei Operationen."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from genesis_core.logutil import get_logger

log = get_logger("ArtworkEngine")

SUPPORTED_EMBED_EXTENSIONS = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".m4b", ".mp4"}

_MIME_TO_EXT = {"image/jpeg": ".jpg", "image/png": ".png"}

# MP4/M4A/M4B-Dateien kennen im "covr"-Atom NUR JPEG/PNG (Format-Vorgabe von
# Apple/iTunes, keine mutagen-Einschraenkung). Deep-Review-Fund (Sitzung 3,
# F-11): `_embed_mp4` hat frueher JEDEN nicht-PNG-MIME-Typ stillschweigend
# als JPEG behandelt - ein echtes GIF/WEBP/BMP-Cover (z.B. aus einer
# zukuenftigen lokalen Datei-Upload-Funktion) waere dadurch unlesbar
# eingebettet worden, ohne dass jemand gewarnt wird (Prinzip #16/#37: kein
# stiller Fehlschlag). Jetzt wird vorher hart geprueft.
_MP4_SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png"}


class ArtworkError(RuntimeError):
    """Klare, deutschsprachige Fehlermeldung statt rohem mutagen-Stacktrace
    (§37)."""


class ArtworkApplyNotConfirmedError(PermissionError):
    """`embed_artwork` veraendert die Mediendatei selbst - erfordert daher
    IMMER `user_confirmed=True` (Prinzip #17/§44), hart im Code erzwungen."""


def extract_embedded_artwork(path: str | Path) -> tuple[bytes, str] | None:
    """Liest ein evtl. bereits eingebettetes Cover aus. Liefert `None`, wenn
    keins vorhanden ist ODER das Format nicht unterstuetzt wird - das ist
    ein normaler Zustand, kein Fehler (Prinzip #16: kein erfundenes Bild)."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".mp3":
            return _extract_id3(path)
        if ext == ".flac":
            return _extract_flac(path)
        if ext in (".ogg", ".oga"):
            return _extract_ogg_vorbis(path)
        if ext in (".m4a", ".m4b", ".mp4"):
            return _extract_mp4(path)
    except Exception as exc:  # noqa: BLE001
        log.warning("Eingebettetes Artwork konnte nicht gelesen werden (%s): %s", path.name, exc)
        return None
    return None


def embed_artwork(
    path: str | Path, image_bytes: bytes, mime_type: str, *, user_confirmed: bool
) -> None:
    """Bettet ein Cover in die Mediendatei ein - VERAENDERT die Originaldatei
    (Prinzip #5), daher zwingend `user_confirmed=True`."""
    if not user_confirmed:
        raise ArtworkApplyNotConfirmedError(
            "Artwork darf nur nach expliziter Nutzerbestaetigung in eine "
            "Mediendatei eingebettet werden (Prinzip #17, §44)."
        )
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EMBED_EXTENSIONS:
        raise ArtworkError(
            f"Einbetten von Artwork wird fuer das Format '{ext}' noch nicht unterstuetzt."
        )
    try:
        if ext == ".mp3":
            _embed_id3(path, image_bytes, mime_type)
        elif ext == ".flac":
            _embed_flac(path, image_bytes, mime_type)
        elif ext in (".ogg", ".oga"):
            _embed_ogg_vorbis(path, image_bytes, mime_type)
        else:
            _embed_mp4(path, image_bytes, mime_type)
    except ArtworkError:
        raise
    except Exception as exc:
        raise ArtworkError(f"Artwork konnte nicht in {path.name} eingebettet werden: {exc}") from exc
    log.info("Artwork eingebettet: %s", path.name)


def cache_artwork(data: bytes, mime_type: str, cache_dir: str | Path) -> Path:
    """Speichert abgerufenes Artwork im GENESIS-eigenen Cache-Ordner - ruehrt
    NIEMALS eine Mediendatei an (Prinzip #4/#5). Dateiname = Inhalts-Hash,
    damit identisches Artwork nicht mehrfach gespeichert wird."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    ext = _MIME_TO_EXT.get(mime_type, ".jpg")
    digest = hashlib.sha256(data).hexdigest()[:32]
    out_path = cache_dir / f"{digest}{ext}"
    if not out_path.exists():
        out_path.write_bytes(data)
    return out_path


# --- ID3 (MP3) ---------------------------------------------------------------


def _extract_id3(path: Path) -> tuple[bytes, str] | None:
    from mutagen.id3 import ID3, ID3NoHeaderError

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return None
    apics = tags.getall("APIC")
    if not apics:
        return None
    return bytes(apics[0].data), apics[0].mime or "image/jpeg"


def _embed_id3(path: Path, image_bytes: bytes, mime_type: str) -> None:
    from mutagen.id3 import APIC, ID3, ID3NoHeaderError

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("APIC")
    tags.add(APIC(encoding=3, mime=mime_type, type=3, desc="Cover", data=image_bytes))
    tags.save(path)


# --- FLAC ---------------------------------------------------------------------


def _extract_flac(path: Path) -> tuple[bytes, str] | None:
    from mutagen.flac import FLAC

    audio = FLAC(path)
    if not audio.pictures:
        return None
    pic = audio.pictures[0]
    return bytes(pic.data), pic.mime or "image/jpeg"


def _embed_flac(path: Path, image_bytes: bytes, mime_type: str) -> None:
    from mutagen.flac import FLAC, Picture

    audio = FLAC(path)
    picture = Picture()
    picture.data = image_bytes
    picture.type = 3
    picture.mime = mime_type
    audio.clear_pictures()
    audio.add_picture(picture)
    audio.save()


# --- OGG Vorbis (METADATA_BLOCK_PICTURE, base64-kodiert) ----------------------


def _extract_ogg_vorbis(path: Path) -> tuple[bytes, str] | None:
    from mutagen.flac import Picture
    from mutagen.oggvorbis import OggVorbis

    audio = OggVorbis(path)
    values = audio.get("metadata_block_picture")
    if not values:
        return None
    picture = Picture(base64.b64decode(values[0]))
    return bytes(picture.data), picture.mime or "image/jpeg"


def _embed_ogg_vorbis(path: Path, image_bytes: bytes, mime_type: str) -> None:
    from mutagen.flac import Picture
    from mutagen.oggvorbis import OggVorbis

    picture = Picture()
    picture.data = image_bytes
    picture.type = 3
    picture.mime = mime_type
    encoded = base64.b64encode(picture.write()).decode("ascii")

    audio = OggVorbis(path)
    audio["metadata_block_picture"] = [encoded]
    audio.save()


# --- MP4/M4A/M4B ---------------------------------------------------------------


def _extract_mp4(path: Path) -> tuple[bytes, str] | None:
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(path)
    covers = audio.get("covr")
    if not covers:
        return None
    cover = covers[0]
    mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
    return bytes(cover), mime


def _embed_mp4(path: Path, image_bytes: bytes, mime_type: str) -> None:
    from mutagen.mp4 import MP4, MP4Cover

    if mime_type not in _MP4_SUPPORTED_MIME_TYPES:
        raise ArtworkError(
            f"MP4/M4A/M4B unterstuetzt nur JPEG- oder PNG-Cover, nicht "
            f"'{mime_type}'. Bitte zuerst in JPEG oder PNG konvertieren."
        )
    fmt = MP4Cover.FORMAT_PNG if mime_type == "image/png" else MP4Cover.FORMAT_JPEG
    audio = MP4(path)
    audio["covr"] = [MP4Cover(image_bytes, imageformat=fmt)]
    audio.save()
