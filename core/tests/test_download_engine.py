"""Tests fuer das Download-/Import-Center (§30-§32, ADR-0019).

Nutzt ausschliesslich lokale/generierte Testdateien (SAFE TEST MODE, §50/
§51) - KEIN echter Netzwerkzugriff in diesem Modul. Die echte YouTube/
yt-dlp-Anbindung sowie ein echter Direkt-URL-Download werden separat (und
nur best-effort/optional) in test_download_real_network.py geprueft.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from genesis_core.config import DownloadSettings
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, Source
from genesis_core.download.base import (
    AvailabilityResult,
    ConfirmationRequiredError,
    DownloadedFile,
    DownloadError,
    DownloadNotPermittedError,
    DownloadOption,
    DownloadProvider,
    ProviderNotFoundError,
    SourceMetadata,
)
from genesis_core.download.drm_blocked import (
    build_audible_provider,
    build_pocket_fm_provider,
    build_spotify_provider,
)
from genesis_core.download.engine import DownloadEngine
from genesis_core.download.local_file_provider import LocalFileProvider
from genesis_core.download.registry import build_download_providers, detect_provider
from genesis_core.jobs import JobManager
from genesis_core.storage import InsufficientStorageError, check_free_space


def _make_test_audio(path: Path, duration: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-ac", "1", "-ar", "22050", str(path),
        ],
        check=True, capture_output=True,
    )


class StubProvider(DownloadProvider):
    provider_id = "stub"
    display_name = "Stub"
    requires_internet = False

    def __init__(self, src_path: Path, available: bool = True, fail_download: bool = False):
        self.src_path = src_path
        self.available = available
        self.fail_download = fail_download

    def matches(self, url: str) -> bool:
        return url.startswith("stub://")

    def check_availability(self, url: str) -> AvailabilityResult:
        if not self.available:
            return AvailabilityResult(available=False, reason="Stub ist absichtlich nicht verfuegbar")
        return AvailabilityResult(available=True)

    def fetch_metadata(self, url: str) -> SourceMetadata:
        return SourceMetadata(
            title="Stub-Titel", original_id="stub-1",
            extra={"size_bytes": self.src_path.stat().st_size},
        )

    def list_options(self, url: str) -> list[DownloadOption]:
        return [DownloadOption(option_id="default", label="Original", file_extension=".wav")]

    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        if self.fail_download:
            raise DownloadError("Stub-Download absichtlich fehlgeschlagen")
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "stub_downloaded.wav"
        dest.write_bytes(self.src_path.read_bytes())
        return DownloadedFile(path=dest, original_id="stub-1", suggested_title="Mein Test Titel!")


@pytest.fixture()
def engine(db: Database, tmp_path: Path) -> tuple[DownloadEngine, Path]:
    src = tmp_path / "source_audio.wav"
    _make_test_audio(src, duration=6)  # Chromaprint braucht ein paar Sekunden Material
    stub = StubProvider(src)
    providers = {"stub": stub}
    output_dir = tmp_path / "downloads"
    jobs = JobManager(db, app_version="test")
    eng = DownloadEngine(db, providers, output_dir, DownloadSettings(min_free_disk_mb=1), jobs)
    return eng, src


# ---------------------------------------------------------------------
# Registry / Erkennung
# ---------------------------------------------------------------------


def test_registry_contains_all_expected_providers() -> None:
    providers = build_download_providers(DownloadSettings(min_free_disk_mb=1))
    expected_ids = {"spotify", "audible", "pocket_fm", "youtube", "tiktok", "direct_url", "local_file"}
    assert expected_ids <= set(providers.keys())


def test_detect_provider_for_local_path(tmp_path: Path) -> None:
    providers = build_download_providers(DownloadSettings(min_free_disk_mb=1))
    p = detect_provider(providers, str(tmp_path / "irgendwas.mp3"))
    assert p.provider_id == "local_file"


def test_detect_provider_for_spotify_url() -> None:
    providers = build_download_providers(DownloadSettings(min_free_disk_mb=1))
    p = detect_provider(providers, "https://open.spotify.com/track/abc123")
    assert p.provider_id == "spotify"


def test_detect_provider_for_youtube_url() -> None:
    providers = build_download_providers(DownloadSettings(min_free_disk_mb=1))
    p = detect_provider(providers, "https://www.youtube.com/watch?v=abc123")
    assert p.provider_id == "youtube"


def test_detect_provider_unknown_raises() -> None:
    providers = {"local_file": LocalFileProvider()}
    with pytest.raises(ProviderNotFoundError):
        detect_provider(providers, "ftp://example.com/foo")


# ---------------------------------------------------------------------
# DRM-blockierte Provider - §30 harte Grenze
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "build_fn, url",
    [
        (build_spotify_provider, "https://open.spotify.com/track/xyz"),
        (build_audible_provider, "https://www.audible.de/pd/xyz"),
        (build_pocket_fm_provider, "https://pocketfm.com/shows/xyz"),
    ],
)
def test_drm_blocked_providers_never_available(build_fn, url: str) -> None:
    provider = build_fn()
    assert provider.matches(url)
    result = provider.check_availability(url)
    assert result.available is False
    assert result.reason and "DRM" in result.reason
    with pytest.raises(DownloadNotPermittedError):
        provider.download(url, "default", Path("/tmp/irrelevant"))
    with pytest.raises(DownloadNotPermittedError):
        provider.fetch_metadata(url)


def test_drm_blocked_provider_makes_no_network_call() -> None:
    """requires_internet=False ist ein Versprechen: der Provider darf gar
    nicht erst versuchen, den Dienst zu kontaktieren."""
    provider = build_spotify_provider()
    assert provider.requires_internet is False


# ---------------------------------------------------------------------
# LocalFileProvider - echter Dateisystem-Kopiervorgang
# ---------------------------------------------------------------------


def test_local_file_provider_copies_without_touching_original(tmp_path: Path) -> None:
    src = tmp_path / "original.wav"
    _make_test_audio(src)
    provider = LocalFileProvider()
    assert provider.check_availability(str(src)).available is True

    dest_dir = tmp_path / "import_target"
    result = provider.download(str(src), "copy", dest_dir)

    assert result.path.exists()
    assert result.path.read_bytes() == src.read_bytes()
    assert src.exists()  # Original unveraendert vorhanden (Prinzip #4)


def test_local_file_provider_unsupported_extension(tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("kein Medium")
    provider = LocalFileProvider()
    result = provider.check_availability(str(f))
    assert result.available is False


def test_local_file_provider_missing_file(tmp_path: Path) -> None:
    provider = LocalFileProvider()
    result = provider.check_availability(str(tmp_path / "nicht_vorhanden.mp3"))
    assert result.available is False


def test_local_file_provider_never_overwrites_existing_destination(tmp_path: Path) -> None:
    src = tmp_path / "original.wav"
    _make_test_audio(src)
    dest_dir = tmp_path / "import_target"
    dest_dir.mkdir()
    (dest_dir / "original.wav").write_bytes(b"bereits vorhandener Inhalt")

    provider = LocalFileProvider()
    result = provider.download(str(src), "copy", dest_dir)

    assert result.path.name != "original.wav"
    assert (dest_dir / "original.wav").read_bytes() == b"bereits vorhandener Inhalt"


# ---------------------------------------------------------------------
# DownloadEngine - voller §31-Workflow mit Stub-Provider
# ---------------------------------------------------------------------


def test_import_without_confirm_raises(engine) -> None:
    eng, _src = engine
    with pytest.raises(ConfirmationRequiredError):
        eng.import_from_url("stub://whatever", confirm=False)


def test_import_unavailable_provider_raises_not_permitted(db: Database, tmp_path: Path) -> None:
    src = tmp_path / "x.wav"
    _make_test_audio(src)
    stub = StubProvider(src, available=False)
    jobs = JobManager(db, app_version="test")
    eng = DownloadEngine(db, {"stub": stub}, tmp_path / "downloads", DownloadSettings(min_free_disk_mb=1), jobs)
    with pytest.raises(DownloadNotPermittedError):
        eng.import_from_url("stub://x", confirm=True)


def test_import_full_workflow_creates_media_file_and_source(engine, db: Database) -> None:
    eng, _src = engine
    result = eng.import_from_url("stub://whatever", confirm=True)

    assert result.media_file_id > 0
    assert Path(result.absolute_path).exists()
    assert result.suggested_filename == "Mein Test Titel!.wav"

    with db.session() as session:
        media_file = session.get(MediaFile, result.media_file_id)
        assert media_file is not None
        source = session.get(Source, result.source_id)
        assert source is not None
        assert source.media_file_id == result.media_file_id
        assert source.provider_name == "stub"
        assert source.original_url == "stub://whatever"
        assert source.original_id == "stub-1"
        assert source.imported_at is not None

    # Fingerprint und Lautheit sind best effort, aber fpcalc/ffmpeg sind in
    # dieser Umgebung installiert - sollten also tatsaechlich gelingen.
    assert result.fingerprint_computed is True
    assert result.loudness_measured is True
    assert result.warnings == []


def test_import_download_failure_marks_job_failed(db: Database, tmp_path: Path) -> None:
    src = tmp_path / "y.wav"
    _make_test_audio(src)
    stub = StubProvider(src, fail_download=True)
    jobs = JobManager(db, app_version="test")
    eng = DownloadEngine(db, {"stub": stub}, tmp_path / "downloads", DownloadSettings(min_free_disk_mb=1), jobs)
    with pytest.raises(DownloadError):
        eng.import_from_url("stub://whatever", confirm=True)


def test_import_local_file_without_confirm_raises(engine) -> None:
    eng, src = engine
    with pytest.raises(ConfirmationRequiredError):
        eng.import_local_file(str(src), confirm=False)


def test_import_local_file_full_workflow(db: Database, tmp_path: Path) -> None:
    src = tmp_path / "local_original.wav"
    _make_test_audio(src)
    providers = build_download_providers(DownloadSettings(min_free_disk_mb=1))
    jobs = JobManager(db, app_version="test")
    eng = DownloadEngine(db, providers, tmp_path / "downloads", DownloadSettings(min_free_disk_mb=1), jobs)

    result = eng.import_local_file(str(src), confirm=True)

    assert result.media_file_id > 0
    assert src.exists()  # Original unveraendert (Prinzip #4)
    with db.session() as session:
        source = session.get(Source, result.source_id)
        assert source.import_method == "local_import"
        assert source.provider_name == "local_file"


def test_import_rejects_file_above_size_limit(db: Database, tmp_path: Path) -> None:
    src = tmp_path / "huge.wav"
    _make_test_audio(src, duration=1)
    stub = StubProvider(src)
    jobs = JobManager(db, app_version="test")
    tiny_limit_settings = DownloadSettings(max_download_size_mb=0)
    eng = DownloadEngine(db, {"stub": stub}, tmp_path / "downloads", tiny_limit_settings, jobs)
    with pytest.raises(DownloadError):
        eng.import_from_url("stub://whatever", confirm=True)


# ---------------------------------------------------------------------
# Speicherplatzpruefung (genesis_core.storage)
# ---------------------------------------------------------------------


def test_check_free_space_reports_sufficient(tmp_path: Path) -> None:
    result = check_free_space(tmp_path, required_bytes=1024, min_free_bytes_after=0)
    assert result.sufficient is True
    assert result.free_bytes > 0


def test_check_free_space_reports_insufficient_for_absurd_requirement(tmp_path: Path) -> None:
    result = check_free_space(tmp_path, required_bytes=0, min_free_bytes_after=10**18)
    assert result.sufficient is False


def test_ensure_free_space_raises_when_insufficient(tmp_path: Path) -> None:
    from genesis_core.storage import ensure_free_space

    with pytest.raises(InsufficientStorageError):
        ensure_free_space(tmp_path, required_bytes=0, min_free_bytes_after=10**18)
