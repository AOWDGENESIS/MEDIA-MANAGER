"""Direkter Download einer Medien-URL per HTTP(S) (§30, Quelle "direkte
Medien-URLs"). Reiner, unauffaelliger Stream-Download ueber httpx - kein
DRM, kein Login, keine Zugangsdaten."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from genesis_core.download.base import (
    AvailabilityResult,
    DownloadedFile,
    DownloadError,
    DownloadOption,
    DownloadProvider,
    SourceMetadata,
)
from genesis_core.logutil import get_logger
from genesis_core.scanner.classify import is_supported_media_extension

log = get_logger("DirectURLProvider")

_DEFAULT_HEADERS = {"User-Agent": "GENESIS-Media-Manager/0.1 (+https://localhost, offline tool)"}


class DirectURLProvider(DownloadProvider):
    provider_id = "direct_url"
    display_name = "Direkte Medien-URL"
    requires_internet = True

    def __init__(self, timeout_seconds: float = 20.0, max_size_bytes: int | None = None):
        self.timeout_seconds = timeout_seconds
        self.max_size_bytes = max_size_bytes

    def matches(self, url: str) -> bool:
        return url.startswith(("http://", "https://"))

    def _filename_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        name = unquote(Path(parsed.path).name)
        return name or "download"

    def check_availability(self, url: str) -> AvailabilityResult:
        try:
            with httpx.Client(timeout=self.timeout_seconds, headers=_DEFAULT_HEADERS) as client:
                resp = client.head(url, follow_redirects=True)
                if resp.status_code >= 400:
                    # Manche Server lehnen HEAD ab, aber erlauben GET -
                    # ein kleiner Range-GET als Rueckfallebene.
                    resp = client.get(
                        url, follow_redirects=True, headers={"Range": "bytes=0-0"}
                    )
                if resp.status_code >= 400:
                    return AvailabilityResult(
                        available=False, reason=f"HTTP-Status {resp.status_code}"
                    )
                return AvailabilityResult(available=True)
        except httpx.HTTPError as exc:
            return AvailabilityResult(available=False, reason=f"Nicht erreichbar: {exc}")

    def fetch_metadata(self, url: str) -> SourceMetadata:
        try:
            with httpx.Client(timeout=self.timeout_seconds, headers=_DEFAULT_HEADERS) as client:
                resp = client.head(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise DownloadError(f"Metadaten nicht abrufbar: {exc}") from exc

        size = resp.headers.get("content-length")
        return SourceMetadata(
            title=self._filename_from_url(url),
            original_id=url,
            extra={
                "content_type": resp.headers.get("content-type"),
                "size_bytes": int(size) if size and size.isdigit() else None,
            },
        )

    def list_options(self, url: str) -> list[DownloadOption]:
        meta = self.fetch_metadata(url)
        name = meta.title or "download"
        ext = Path(name).suffix.lower()
        return [
            DownloadOption(
                option_id="default",
                label="Original",
                file_extension=ext,
                approx_size_bytes=meta.extra.get("size_bytes"),
            )
        ]

    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = self._filename_from_url(url)
        if not is_supported_media_extension(Path(filename).suffix.lower()):
            # Trotzdem herunterladen erlauben (z.B. generische .bin-URLs),
            # aber klar protokollieren - die Analysephase danach wird eine
            # nicht unterstuetzte Erweiterung ohnehin erkennen und melden.
            log.warning(
                "URL-Dateiendung %r wird nicht als Medienformat erkannt: %s",
                Path(filename).suffix, url,
            )
        dest = dest_dir / filename
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
            counter += 1

        downloaded_bytes = 0
        try:
            with httpx.Client(
                timeout=self.timeout_seconds, headers=_DEFAULT_HEADERS, follow_redirects=True
            ) as client, client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    raise DownloadError(f"HTTP-Status {resp.status_code} bei {url}")
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                        downloaded_bytes += len(chunk)
                        if (
                            self.max_size_bytes is not None
                            and downloaded_bytes > self.max_size_bytes
                        ):
                            fh.close()
                            dest.unlink(missing_ok=True)
                            raise DownloadError(
                                "Download abgebrochen: konfiguriertes Groessenlimit "
                                f"({self.max_size_bytes} Bytes) ueberschritten."
                            )
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            dest.unlink(missing_ok=True)
            raise DownloadError(f"Download fehlgeschlagen: {exc}") from exc

        return DownloadedFile(path=dest, original_id=url, suggested_title=Path(filename).stem)
