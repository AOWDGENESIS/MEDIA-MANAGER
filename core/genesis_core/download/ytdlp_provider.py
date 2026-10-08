"""YouTube/TikTok-Adapter auf Basis von yt-dlp (Unlicense, siehe
licenses/THIRD-PARTY-LICENSES.md).

WICHTIG (§30, harte Grenze): yt-dlp ruft ausschliesslich Formate/Daten ab,
die der jeweilige Dienst einem gewoehnlichen, nicht angemeldeten Browser
ohnehin ausliefert - es wird KEINE DRM-Verschluesselung (z.B. Widevine)
umgangen und es werden KEINE Zugangsdaten/Cookies verwendet oder
gespeichert. Premium-/bezahlpflichtige/DRM-geschuetzte Inhalte, die yt-dlp
nicht ohne Login/DRM-Umgehung extrahieren kann, werden von yt-dlp selbst mit
einem Fehler quittiert - dieser wird hier als normales "nicht verfuegbar"
nach oben gereicht (§31 "Wenn ein Dienst keinen zulaessigen Download
ermoeglicht, muss die Anwendung dies erkennen und entsprechend melden").

TikTok-Hinweis: TikToks Erkennung/Blockaden aendern sich haeufig; der
Adapter wird daher bewusst als "experimentell/best effort" gefuehrt (siehe
`is_experimental`) - schlaegt die Extraktion fehl, wird dies als normale
Nichtverfuegbarkeit gemeldet, nie als Absturz.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from genesis_core.download.base import (
    AvailabilityResult,
    DownloadedFile,
    DownloadError,
    DownloadOption,
    DownloadProvider,
    SourceMetadata,
)
from genesis_core.logutil import get_logger

log = get_logger("YtDlpProvider")

try:
    import yt_dlp

    YT_DLP_AVAILABLE = True
except ImportError:  # pragma: no cover - Umgebungen ohne optionale Abhaengigkeit
    yt_dlp = None  # type: ignore[assignment]
    YT_DLP_AVAILABLE = False


class YtDlpProvider(DownloadProvider):
    """Generische Basis fuer alle von yt-dlp unterstuetzten Plattformen.
    YouTube/TikTok sind konkrete, parametrisierte Instanzen davon."""

    requires_internet = True
    url_patterns: ClassVar[list[str]] = []
    is_experimental: bool = False

    def __init__(self, provider_id: str, display_name: str, url_patterns: list[str],
                 is_experimental: bool = False):
        self.provider_id = provider_id
        self.display_name = display_name
        self.url_patterns = url_patterns
        self.is_experimental = is_experimental

    def matches(self, url: str) -> bool:
        return any(re.search(pattern, url) for pattern in self.url_patterns)

    def _unavailable_reason(self) -> str | None:
        if not YT_DLP_AVAILABLE:
            return (
                "yt-dlp ist nicht installiert - dieser Adapter benoetigt das optionale "
                "Paket 'yt-dlp' (Unlicense)."
            )
        return None

    def check_availability(self, url: str) -> AvailabilityResult:
        reason = self._unavailable_reason()
        if reason:
            return AvailabilityResult(available=False, reason=reason)
        try:
            self._extract_info(url, download=False)
        except DownloadError as exc:
            return AvailabilityResult(available=False, reason=str(exc))
        return AvailabilityResult(available=True)

    def _extract_info(self, url: str, download: bool) -> dict:
        assert yt_dlp is not None
        opts = {"quiet": True, "no_warnings": True, "skip_download": not download}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=download)
                if info is None:
                    raise DownloadError("yt-dlp lieferte keine Informationen zurueck")
                return info
        except yt_dlp.utils.DownloadError as exc:  # type: ignore[union-attr]
            # yt-dlp meldet DRM-/Login-/Regionssperren ueber dieselbe
            # Exception-Klasse mit einer menschenlesbaren Meldung - wir
            # reichen diese unveraendert weiter statt sie zu verschlucken.
            raise DownloadError(f"yt-dlp konnte die Quelle nicht verarbeiten: {exc}") from exc

    def fetch_metadata(self, url: str) -> SourceMetadata:
        reason = self._unavailable_reason()
        if reason:
            raise DownloadError(reason)
        info = self._extract_info(url, download=False)
        return SourceMetadata(
            title=info.get("title"),
            description=info.get("description"),
            duration_seconds=info.get("duration"),
            uploader=info.get("uploader"),
            thumbnail_url=info.get("thumbnail"),
            original_id=info.get("id"),
            license=info.get("license"),
            extra={"webpage_url": info.get("webpage_url")},
        )

    def list_options(self, url: str) -> list[DownloadOption]:
        reason = self._unavailable_reason()
        if reason:
            raise DownloadError(reason)
        info = self._extract_info(url, download=False)
        options: list[DownloadOption] = []
        for fmt in info.get("formats", []) or []:
            has_audio = fmt.get("acodec") not in (None, "none")
            has_video = fmt.get("vcodec") not in (None, "none")
            if not has_audio and not has_video:
                continue
            size = fmt.get("filesize") or fmt.get("filesize_approx")
            kind = "Audio+Video" if (has_audio and has_video) else ("Audio" if has_audio else "Video")
            options.append(
                DownloadOption(
                    option_id=str(fmt.get("format_id")),
                    label=f"{kind} - {fmt.get('ext')} "
                    f"({fmt.get('format_note') or fmt.get('resolution') or fmt.get('abr')})",
                    file_extension=f".{fmt.get('ext')}" if fmt.get("ext") else "",
                    approx_size_bytes=size,
                    quality_note=kind,
                )
            )
        if not options:
            options.append(
                DownloadOption(option_id="best", label="Beste verfuegbare Qualitaet", file_extension="")
            )
        return options

    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        reason = self._unavailable_reason()
        if reason:
            raise DownloadError(reason)
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        assert yt_dlp is not None
        outtmpl = str(dest_dir / "%(title).150B [%(id)s].%(ext)s")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": option_id if option_id not in ("default", "best") else "best",
            "outtmpl": outtmpl,
            "noplaylist": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_path = Path(ydl.prepare_filename(info))
        except yt_dlp.utils.DownloadError as exc:  # type: ignore[union-attr]
            raise DownloadError(f"yt-dlp-Download fehlgeschlagen: {exc}") from exc

        if not final_path.exists():
            raise DownloadError(f"yt-dlp meldete Erfolg, Datei fehlt aber: {final_path}")
        return DownloadedFile(
            path=final_path, original_id=info.get("id"), suggested_title=info.get("title")
        )


def build_youtube_provider() -> YtDlpProvider:
    return YtDlpProvider(
        provider_id="youtube",
        display_name="YouTube",
        url_patterns=[r"(?:youtube\.com|youtu\.be)/"],
    )


def build_tiktok_provider() -> YtDlpProvider:
    return YtDlpProvider(
        provider_id="tiktok",
        display_name="TikTok",
        url_patterns=[r"tiktok\.com/"],
        is_experimental=True,
    )
