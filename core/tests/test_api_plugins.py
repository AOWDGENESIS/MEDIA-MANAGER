"""API-Tests fuer das Plugin-System (§34)."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings

EXAMPLES_DIR = (
    Path(__file__).resolve().parents[1] / "genesis_core" / "plugins" / "examples"
)


def _make_app(tmp_path: Path, *, with_examples: bool = False):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    settings.ensure_directories()
    if with_examples:
        dest = settings.paths.data_dir / "plugins"
        dest.mkdir(parents=True, exist_ok=True)
        for example in EXAMPLES_DIR.iterdir():
            if example.is_dir():
                shutil.copytree(example, dest / example.name)
    return create_app(settings)


def _client(app) -> TestClient:
    client = TestClient(app, raise_server_exceptions=False)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def test_list_plugins_empty_by_default(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    resp = client.get("/plugins")
    assert resp.status_code == 200
    assert resp.json()["plugins"] == []


def test_list_plugins_shows_working_and_broken_example(tmp_path: Path) -> None:
    app = _make_app(tmp_path, with_examples=True)
    client = _client(app)
    resp = client.get("/plugins")
    assert resp.status_code == 200
    plugins = resp.json()["plugins"]

    working = next(p for p in plugins if p["plugin_id"] == "example-pipe-separated-exporter")
    assert working["loaded_successfully"] is True

    broken = next(p for p in plugins if p["plugin_id"] == "broken_example")
    assert broken["loaded_successfully"] is False
    assert broken["load_error"] is not None


def test_export_via_plugin_endpoint_works(tmp_path: Path) -> None:
    app = _make_app(tmp_path, with_examples=True)
    client = _client(app)
    state = app.state.genesis

    from genesis_core.db.models import MediaFile, MediaKind

    with state.db.session() as session:
        session.add(
            MediaFile(
                absolute_path="/music/a.mp3", directory="/music", filename="a.mp3",
                extension=".mp3", kind=MediaKind.MUSIC, size_bytes=10,
            )
        )

    resp = client.get("/plugins/export/example-pipe-separated-exporter")
    assert resp.status_code == 200
    assert "a.mp3" in resp.text
    assert "|" in resp.text
    # Deep-Review-Fund (Sitzung 11): file_extension() wurde vorher nie
    # aufgerufen - jetzt muss ein passender Dateiname im Header stehen.
    assert resp.headers["content-disposition"] == 'attachment; filename="export.psv"'


def test_export_via_unknown_plugin_returns_404(tmp_path: Path) -> None:
    app = _make_app(tmp_path, with_examples=True)
    client = _client(app)
    resp = client.get("/plugins/export/does-not-exist")
    assert resp.status_code == 404


def test_reload_plugins_picks_up_new_plugin_without_restart(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    client = _client(app)
    state = app.state.genesis

    assert client.get("/plugins").json()["plugins"] == []

    dest = state.plugins_dir / "example_exporter"
    shutil.copytree(EXAMPLES_DIR / "example_exporter", dest)

    resp = client.post("/plugins/reload")
    assert resp.status_code == 200
    ids = {p["plugin_id"] for p in resp.json()["plugins"]}
    assert "example-pipe-separated-exporter" in ids


def test_diagnostics_reflects_broken_plugin_as_warning(tmp_path: Path) -> None:
    app = _make_app(tmp_path, with_examples=True)
    client = _client(app)
    resp = client.get("/diagnostics")
    assert resp.status_code == 200
    plugin_check = next(c for c in resp.json()["checks"] if c["check_id"] == "plugins")
    assert plugin_check["status"] == "warning"
