"""Tests fuer die Download-/Import-Center-API (§30-§32, ADR-0019)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import DownloadSettings, Settings
from genesis_core.download.base import (
    AvailabilityResult,
    DownloadedFile,
    DownloadOption,
    DownloadProvider,
    SourceMetadata,
)
from genesis_core.download.engine import DownloadEngine


def _make_test_audio(path: Path, duration: int = 6) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-ac", "1", "-ar", "22050", str(path),
        ],
        check=True, capture_output=True,
    )


class _StubProvider(DownloadProvider):
    provider_id = "stub"
    display_name = "Stub"
    requires_internet = False

    def __init__(self, src_path: Path, available: bool = True):
        self.src_path = src_path
        self.available = available

    def matches(self, url: str) -> bool:
        return url.startswith("stub://")

    def check_availability(self, url: str) -> AvailabilityResult:
        if not self.available:
            return AvailabilityResult(available=False, reason="Stub absichtlich gesperrt")
        return AvailabilityResult(available=True)

    def fetch_metadata(self, url: str) -> SourceMetadata:
        return SourceMetadata(title="API-Stub-Titel", original_id="api-stub-1")

    def list_options(self, url: str) -> list[DownloadOption]:
        return [DownloadOption(option_id="default", label="Original", file_extension=".wav")]

    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "api_stub_downloaded.wav"
        dest.write_bytes(self.src_path.read_bytes())
        return DownloadedFile(path=dest, original_id="api-stub-1", suggested_title="API Titel")


def _make_app(tmp_path: Path, stub_available: bool = True):
    settings = Settings()
    settings.paths.data_dir = tmp_path / "data"
    settings.general.safe_test_mode = True
    app = create_app(settings)

    src = tmp_path / "src.wav"
    _make_test_audio(src)
    stub = _StubProvider(src, available=stub_available)
    state = app.state.genesis
    state.download_providers = {"stub": stub, **state.download_providers}
    state.download_engine = DownloadEngine(
        state.db, state.download_providers, state.download_output_dir,
        DownloadSettings(min_free_disk_mb=1), state.jobs,
    )
    return app


def _client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def test_list_providers_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.get("/download/providers")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["providers"]}
    assert {"stub", "spotify", "audible", "pocket_fm", "youtube", "tiktok", "direct_url", "local_file"} <= ids


def test_detect_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/download/detect", json={"url": "stub://xyz"})
    assert resp.status_code == 200
    assert resp.json()["provider_id"] == "stub"

    resp2 = client.post("/download/detect", json={"url": "https://open.spotify.com/track/1"})
    assert resp2.json()["provider_id"] == "spotify"


def test_availability_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/download/availability", json={"url": "stub://xyz"})
    assert resp.status_code == 200
    assert resp.json()["available"] is True

    resp2 = client.post(
        "/download/availability", json={"url": "https://open.spotify.com/track/1"}
    )
    body = resp2.json()
    assert body["available"] is False
    assert "DRM" in body["reason"]


def test_metadata_endpoint_for_drm_blocked_returns_403(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post(
        "/download/metadata", json={"url": "https://www.audible.de/pd/xyz"}
    )
    assert resp.status_code == 403


def test_metadata_endpoint_for_unknown_url_returns_404(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/download/metadata", json={"url": "ftp://example.com/x"})
    assert resp.status_code == 404


def test_import_requires_confirm(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/download/import", json={"url": "stub://xyz", "confirm": False})
    assert resp.status_code == 422


def test_import_full_flow_creates_media_file_and_source(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.post("/download/import", json={"url": "stub://xyz", "confirm": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["media_file_id"] > 0
    assert body["suggested_filename"] == "API Titel.wav"

    sources_resp = client.get(f"/media/{body['media_file_id']}/sources")
    assert sources_resp.status_code == 200
    sources = sources_resp.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["provider_name"] == "stub"
    assert sources[0]["original_url"] == "stub://xyz"


def test_import_rejects_when_provider_unavailable(tmp_path: Path) -> None:
    app = _make_app(tmp_path, stub_available=False)
    client = _client(app)
    resp = client.post("/download/import", json={"url": "stub://xyz", "confirm": True})
    assert resp.status_code == 403


def test_local_file_import_endpoint(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    local_src = tmp_path / "local_import_src.wav"
    _make_test_audio(local_src)

    resp = client.post(
        "/import/local-file", json={"path": str(local_src), "confirm": True}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["media_file_id"] > 0
    assert local_src.exists()  # Original unveraendert (Prinzip #4)


def test_local_file_import_requires_confirm(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    local_src = tmp_path / "local_import_src2.wav"
    _make_test_audio(local_src)
    resp = client.post(
        "/import/local-file", json={"path": str(local_src), "confirm": False}
    )
    assert resp.status_code == 422


def test_download_import_requires_token(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = TestClient(app)  # kein Token-Header
    resp = client.post("/download/import", json={"url": "stub://xyz", "confirm": True})
    assert resp.status_code in (401, 403)
