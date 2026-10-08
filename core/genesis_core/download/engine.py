"""Download-/Import-Engine (§30-§32): orchestriert den kompletten
Workflow aus §31:

    URL eingeben -> Quelle erkennen -> Provider auswaehlen ->
    Verfuegbarkeit pruefen -> Metadaten abrufen -> Downloadoptionen
    anzeigen -> Benutzer bestaetigt -> Download -> Datei analysieren ->
    Metadaten ergaenzen -> Fingerprint -> Lautheit analysieren ->
    Dateiname bestimmen -> Bibliothek importieren

Bewusste Scope-Entscheidung (siehe ADR-0019): Die ersten vier Schritte
("Quelle erkennen" bis "Downloadoptionen anzeigen") sind reine
Vorschau-Operationen ohne jede Seitenwirkung (Prinzip #4/#5) und daher ohne
`confirm` aufrufbar. Erst `import_from_url`/`import_local_file` fuehrt den
eigentlichen Download/die eigentliche Dateisystem-/DB-Aenderung aus und
verlangt `confirm=True` (Prinzip #6).

"Datei analysieren" wird durch Wiederverwendung des bestehenden,
rein lesenden Scanners (genesis_core.scanner.scan_directories) erledigt -
keine Doppelimplementierung der technischen Analyse. Fingerprint und
Lautheitsmessung sind bewusst BEST EFFORT (ein fehlendes fpcalc/ffmpeg
laesst den Import nicht fehlschlagen, sondern erzeugt nur eine Warnung) -
siehe gleiches Muster in den bestehenden Fingerprint-/Lautheits-Endpunkten.
Die automatische Umbenennung gemaess Vorlage wird NICHT ausgefuehrt (das
blterebt ein expliziter, vom Nutzer bestaetigter Schritt ueber die
bestehende Umbenennungs-Vorschau/Anwendung, §15) - die Engine liefert hier
nur einen bereits dateisystemsicheren Namensvorschlag mit.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

from sqlalchemy import select

from genesis_core.config import DownloadSettings
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, Source
from genesis_core.download.base import (
    AvailabilityResult,
    ConfirmationRequiredError,
    DownloadedFile,
    DownloadError,
    DownloadOption,
    DownloadProvider,
    ProviderNotFoundError,
    SourceMetadata,
)
from genesis_core.download.registry import detect_provider
from genesis_core.fingerprint import FingerprintError, compute_fingerprint, is_fpcalc_available
from genesis_core.jobs import JobManager
from genesis_core.logutil import get_logger
from genesis_core.loudness.engine import measure_loudness
from genesis_core.rename.templates import sanitize_filename_component
from genesis_core.scanner.scanner import scan_directories
from genesis_core.storage import ensure_free_space

log = get_logger("DownloadEngine")


@dataclasses.dataclass
class ImportResult:
    job_id: str
    media_file_id: int
    absolute_path: str
    source_id: int
    suggested_filename: str | None
    fingerprint_computed: bool
    loudness_measured: bool
    warnings: list[str]


class DownloadEngine:
    def __init__(
        self,
        db: Database,
        providers: dict[str, DownloadProvider],
        output_dir: Path,
        settings: DownloadSettings,
        jobs: JobManager,
    ):
        self.db = db
        self.providers = providers
        self.output_dir = Path(output_dir)
        self.settings = settings
        self.jobs = jobs

    # -- reine Vorschau-Schritte (kein confirm noetig, Prinzip #4/#5) ------

    def detect(self, url: str) -> DownloadProvider:
        return detect_provider(self.providers, url)

    def check_availability(self, url: str) -> tuple[DownloadProvider, AvailabilityResult]:
        provider = self.detect(url)
        return provider, provider.check_availability(url)

    def fetch_metadata(self, url: str) -> tuple[DownloadProvider, SourceMetadata]:
        provider = self.detect(url)
        return provider, provider.fetch_metadata(url)

    def list_options(self, url: str) -> tuple[DownloadProvider, list[DownloadOption]]:
        provider = self.detect(url)
        return provider, provider.list_options(url)

    # -- Import (schreibend, verlangt confirm=True) ------------------------

    def import_from_url(
        self,
        url: str,
        option_id: str = "default",
        confirm: bool = False,
        import_method: str = "download",
    ) -> ImportResult:
        if not confirm:
            raise ConfirmationRequiredError(
                "Download/Import erfordert eine explizite Bestaetigung (confirm=true)."
            )
        provider = self.detect(url)
        availability = provider.check_availability(url)
        if not availability.available:
            from genesis_core.download.base import DownloadNotPermittedError

            raise DownloadNotPermittedError(
                availability.reason or "Quelle meldet: Download nicht verfuegbar."
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            meta = provider.fetch_metadata(url)
        except DownloadError:
            meta = SourceMetadata()

        self._preflight_storage(meta)

        job_id = self.jobs.create_job(
            "download_import",
            params={"url": url, "provider": provider.provider_id, "option_id": option_id},
        )
        self.jobs.start(job_id)
        try:
            downloaded = provider.download(url, option_id, self.output_dir)
        except DownloadError as exc:
            self.jobs.fail(job_id, str(exc))
            raise

        result = self._finish_import(
            job_id=job_id,
            downloaded=downloaded,
            source_name=provider.display_name,
            provider_name=provider.provider_id,
            original_url=url,
            import_method=import_method,
        )
        return result

    def import_local_file(self, path: str, confirm: bool = False) -> ImportResult:
        if not confirm:
            raise ConfirmationRequiredError(
                "Der Import einer lokalen Datei erfordert eine explizite Bestaetigung "
                "(confirm=true)."
            )
        provider = self.providers.get("local_file")
        if provider is None:  # pragma: no cover - sollte durch Registry immer vorhanden sein
            raise ProviderNotFoundError("local_file-Provider ist nicht registriert")

        availability = provider.check_availability(path)
        if not availability.available:
            from genesis_core.download.base import DownloadNotPermittedError

            raise DownloadNotPermittedError(availability.reason or "Datei nicht verfuegbar.")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        meta = provider.fetch_metadata(path)
        self._preflight_storage(meta)

        job_id = self.jobs.create_job("local_file_import", params={"path": path})
        self.jobs.start(job_id)
        try:
            downloaded = provider.download(path, "copy", self.output_dir)
        except DownloadError as exc:
            self.jobs.fail(job_id, str(exc))
            raise

        return self._finish_import(
            job_id=job_id,
            downloaded=downloaded,
            source_name="Lokale Datei",
            provider_name="local_file",
            original_url=path,
            import_method="local_import",
        )

    # -- interne Hilfsfunktionen --------------------------------------------

    def _preflight_storage(self, meta: SourceMetadata) -> None:
        estimated_size = meta.extra.get("size_bytes") if meta and meta.extra else None
        required = int(estimated_size) if estimated_size else 0
        max_allowed = self.settings.max_download_size_mb * 1024 * 1024
        if required and required > max_allowed:
            raise DownloadError(
                f"Angekuendigte Dateigroesse ({required / (1024 * 1024):.1f} MB) "
                f"ueberschreitet das konfigurierte Limit "
                f"({self.settings.max_download_size_mb} MB)."
            )
        # Wirft bei Bedarf selbst InsufficientStorageError - absichtlich
        # ungefangen, damit sie unveraendert an den Aufrufer durchgereicht
        # wird (Deep-Review Sitzung 13: vorheriger try/except-Block war ein
        # reiner no-op-Re-raise ohne zusaetzliche Behandlung).
        ensure_free_space(
            self.output_dir,
            required_bytes=required or (64 * 1024 * 1024),  # grobe Mindestannahme
            min_free_bytes_after=self.settings.min_free_disk_mb * 1024 * 1024,
        )

    def _finish_import(
        self,
        job_id: str,
        downloaded: DownloadedFile,
        source_name: str,
        provider_name: str,
        original_url: str,
        import_method: str,
    ) -> ImportResult:
        warnings: list[str] = []
        absolute_path = str(downloaded.path.resolve())

        # "Datei analysieren" + "Metadaten ergaenzen" (technisch) - reine
        # Wiederverwendung des bestehenden, rein lesenden Scanners.
        scan_directories(self.db, [downloaded.path.parent], compute_hash=True, run_ffprobe=True)

        with self.db.session() as session:
            media_file = session.execute(
                select(MediaFile).where(MediaFile.absolute_path == absolute_path)
            ).scalar_one_or_none()
            if media_file is None:
                self.jobs.fail(job_id, "Datei nach Download nicht im Scan gefunden")
                raise DownloadError(
                    f"Heruntergeladene Datei wurde beim Scan nicht gefunden: {absolute_path}"
                )
            media_file_id = media_file.id

        # "Fingerprint" - best effort, blockiert den Import nicht.
        fingerprint_ok = False
        if is_fpcalc_available():
            try:
                fp = compute_fingerprint(downloaded.path)
                with self.db.session() as session:
                    from genesis_core.db.models import Fingerprint

                    session.add(
                        Fingerprint(
                            media_file_id=media_file_id,
                            algorithm=fp.algorithm,
                            fingerprint_data=fp.fingerprint_data,
                            duration_seconds=fp.duration_seconds,
                        )
                    )
                fingerprint_ok = True
            except FingerprintError as exc:
                warnings.append(f"Fingerprint nicht erzeugt: {exc}")
        else:
            warnings.append("Fingerprint uebersprungen: fpcalc (Chromaprint) nicht verfuegbar")

        # "Lautheit analysieren" - best effort, nur MESSUNG, keine
        # Normalisierung/Veraenderung der Datei (Prinzip #5).
        loudness_ok = False
        try:
            measurement = measure_loudness(downloaded.path)
            with self.db.session() as session:
                from genesis_core.db.models import Loudness

                session.add(
                    Loudness(
                        media_file_id=media_file_id,
                        integrated_lufs=measurement.integrated_lufs,
                        true_peak_dbtp=measurement.true_peak_dbtp,
                        loudness_range_lu=measurement.loudness_range_lu,
                        measured_at=measurement.measured_at,
                        normalized=False,
                    )
                )
            loudness_ok = True
        except Exception as exc:  # noqa: BLE001 - bewusst best effort, siehe Moduldocstring
            warnings.append(f"Lautheitsmessung uebersprungen: {exc}")

        # "Dateiname bestimmen" - nur ein dateisystemsicherer VORSCHLAG,
        # keine automatische Umbenennung (Prinzip #6/#17, §15 bleibt
        # eigenstaendig fuer die tatsaechliche Anwendung zustaendig).
        title = downloaded.suggested_title or downloaded.path.stem
        suggested_filename = sanitize_filename_component(title) + downloaded.path.suffix.lower()

        # "Quellenverwaltung" (§32) - Herkunft wird dauerhaft gespeichert.
        with self.db.session() as session:
            source = Source(
                media_file_id=media_file_id,
                source_name=source_name,
                provider_name=provider_name,
                original_url=original_url,
                original_id=downloaded.original_id,
                imported_at=dt.datetime.now(dt.UTC),
                import_method=import_method,
            )
            session.add(source)
            session.flush()
            source_id = source.id

        self.jobs.record_history(
            job_id,
            action="download_import",
            media_file_id=media_file_id,
            after={
                "absolute_path": absolute_path,
                "provider": provider_name,
                "original_url": original_url,
                "fingerprint_computed": fingerprint_ok,
                "loudness_measured": loudness_ok,
            },
            user_action="Nutzer hat Download/Import bestaetigt",
            warning="; ".join(warnings) if warnings else None,
        )
        self.jobs.complete(job_id)

        log.info(
            "Import abgeschlossen: %s (Provider=%s, MediaFile=%d, Fingerprint=%s, Lautheit=%s)",
            absolute_path, provider_name, media_file_id, fingerprint_ok, loudness_ok,
        )

        return ImportResult(
            job_id=job_id,
            media_file_id=media_file_id,
            absolute_path=absolute_path,
            source_id=source_id,
            suggested_filename=suggested_filename,
            fingerprint_computed=fingerprint_ok,
            loudness_measured=loudness_ok,
            warnings=warnings,
        )
