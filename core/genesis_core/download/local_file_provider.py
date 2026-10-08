"""Import bereits lokal vorhandener Dateien (§30, Quelle "lokale Dateien").

Dies ist kein "Download" im eigentlichen Sinn, sondern ein kontrollierter
IMPORT: die Originaldatei wird niemals verschoben oder veraendert (Prinzip
#4/#5), sondern unverändert in den Downloads-/Import-Zwischenordner KOPIERT.
Von dort uebernimmt die Download-Engine dieselbe Analyse-/Scan-Kette wie bei
jedem anderen Import (§31).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from genesis_core.download.base import (
    AvailabilityResult,
    DownloadedFile,
    DownloadError,
    DownloadOption,
    DownloadProvider,
    SourceMetadata,
)
from genesis_core.scanner.classify import is_supported_media_extension


class LocalFileProvider(DownloadProvider):
    provider_id = "local_file"
    display_name = "Lokale Datei"
    requires_internet = False

    def matches(self, url: str) -> bool:
        if url.startswith("file://"):
            return True
        # Ein einfacher lokaler Pfad (kein "schema://") wird ebenfalls als
        # lokale Datei behandelt - alle anderen Provider erwarten http(s).
        return "://" not in url

    def _resolve(self, url: str) -> Path:
        raw = url.removeprefix("file://")
        return Path(raw).expanduser()

    def check_availability(self, url: str) -> AvailabilityResult:
        path = self._resolve(url)
        if not path.is_file():
            return AvailabilityResult(available=False, reason=f"Datei nicht gefunden: {path}")
        if not is_supported_media_extension(path.suffix.lower()):
            return AvailabilityResult(
                available=False,
                reason=f"Dateityp {path.suffix!r} wird nicht als Medienformat erkannt",
            )
        return AvailabilityResult(available=True)

    def fetch_metadata(self, url: str) -> SourceMetadata:
        path = self._resolve(url)
        if not path.is_file():
            raise DownloadError(f"Datei nicht gefunden: {path}")
        stat = path.stat()
        return SourceMetadata(
            title=path.stem,
            original_id=str(path.resolve()),
            extra={"size_bytes": stat.st_size, "extension": path.suffix.lower()},
        )

    def list_options(self, url: str) -> list[DownloadOption]:
        path = self._resolve(url)
        size = path.stat().st_size if path.is_file() else None
        return [
            DownloadOption(
                option_id="copy",
                label="Unveraendert kopieren",
                file_extension=path.suffix.lower(),
                approx_size_bytes=size,
            )
        ]

    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        src = self._resolve(url)
        if not src.is_file():
            raise DownloadError(f"Datei nicht gefunden: {src}")
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        # Namenskollision: niemals eine bestehende Datei im Zielordner
        # stillschweigend ueberschreiben (Prinzip #5).
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1
        shutil.copy2(src, dest)
        return DownloadedFile(
            path=dest, original_id=str(src.resolve()), suggested_title=src.stem
        )
