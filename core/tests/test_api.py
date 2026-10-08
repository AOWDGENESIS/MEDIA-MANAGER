from pathlib import Path

from fastapi.testclient import TestClient

from genesis_core.api.app import create_app
from genesis_core.config import Settings


def _make_app(tmp_path: Path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.general.safe_test_mode = True
    return create_app(settings)


def _make_client(tmp_path: Path) -> TestClient:
    """Authentifizierter Test-Client (Normalfall): liest das vom Core Service
    erzeugte API-Token direkt aus dem AppState und sendet es als Default-
    Header mit - so wie es ein echter UI-Client via api_token.txt tut
    (ADR-0006)."""
    app = _make_app(tmp_path)
    client = TestClient(app)
    client.headers["X-Genesis-Token"] = app.state.genesis.api_token
    return client


def test_health_endpoint(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["safe_test_mode"] is True
    assert body["ai_provider"] == "null"  # KI standardmaessig deaktiviert (§56)


def test_health_endpoint_requires_no_token(tmp_path: Path):
    """/health bleibt bewusst oeffentlich erreichbar (reiner Liveness-Check,
    ADR-0006) - auch OHNE Token."""
    app = _make_app(tmp_path)
    unauthenticated_client = TestClient(app)
    resp = unauthenticated_client.get("/health")
    assert resp.status_code == 200


def test_settings_endpoint_returns_general_language_for_ui_startup(tmp_path: Path):
    """Neuer Endpunkt (Sitzung 4, i18n-Infrastruktur, §53): Die UI liest
    hierueber beim Start `general.language`, um den Translator korrekt zu
    initialisieren. Nur-lesend, erfordert aber das Token (mehr Detail als
    /health)."""
    client = _make_client(tmp_path)
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["general"]["language"] == "de"  # Default gemaess §53
    assert "loudness" in body  # bestaetigt, dass die volle Konfiguration kommt


def test_settings_endpoint_requires_token(tmp_path: Path):
    app = _make_app(tmp_path)
    unauthenticated_client = TestClient(app)
    resp = unauthenticated_client.get("/settings")
    assert resp.status_code in (401, 403)


def test_patch_settings_requires_token(tmp_path: Path):
    app = _make_app(tmp_path)
    unauthenticated_client = TestClient(app)
    resp = unauthenticated_client.patch(
        "/settings", json={"updates": {"ai": {"enabled": True}}, "confirm": True}
    )
    assert resp.status_code in (401, 403)


def test_patch_settings_requires_confirm(tmp_path: Path):
    """Prinzip #17 - wie jede aendernde Aktion braucht auch ein
    Settings-Update eine explizite Nutzerbestaetigung (Gap-Analyse A)."""
    client = _make_client(tmp_path)
    resp = client.patch("/settings", json={"updates": {"ai": {"enabled": True}}})
    assert resp.status_code == 422
    assert "confirm" in resp.json()["detail"].lower()

    resp = client.get("/settings")
    assert resp.json()["ai"]["enabled"] is False  # unveraendert


def test_patch_settings_applies_partial_nested_update_and_persists(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.patch(
        "/settings",
        json={"updates": {"ai": {"enabled": True, "model": "qwen2.5:7b"}}, "confirm": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["settings"]["ai"]["enabled"] is True
    assert body["settings"]["ai"]["model"] == "qwen2.5:7b"
    # Alle nicht erwaehnten Felder (auch innerhalb von "ai") bleiben erhalten -
    # echte PATCH- statt PUT-Semantik.
    assert body["settings"]["ai"]["provider"] == "null"
    assert body["restart_required"] is False
    assert "job_id" in body

    # Wirkt sofort auf den laufenden Prozess (kein Neustart noetig) ...
    resp = client.get("/settings")
    assert resp.json()["ai"]["enabled"] is True

    # ... UND wurde tatsaechlich auf die Platte geschrieben (§55 - kein
    # manuelles config.yaml-Editieren mehr noetig, aber die Datei muss
    # trotzdem den neuen Zustand widerspiegeln, z.B. fuer den naechsten
    # Prozessstart).
    config_path = tmp_path / "config.yaml"
    assert config_path.exists()
    assert "enabled: true" in config_path.read_text(encoding="utf-8")


def test_patch_settings_does_not_touch_unrelated_sections(tmp_path: Path):
    client = _make_client(tmp_path)
    before = client.get("/settings").json()
    client.patch(
        "/settings",
        json={"updates": {"loudness": {"target_lufs": -16.0}}, "confirm": True},
    )
    after = client.get("/settings").json()
    assert after["loudness"]["target_lufs"] == -16.0
    # Andere Bereiche (z.B. "download", "privacy") unveraendert.
    assert after["download"] == before["download"]
    assert after["privacy"] == before["privacy"]


def test_patch_settings_rejects_invalid_value(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.patch(
        "/settings",
        json={"updates": {"ai": {"provider": "definitiv-kein-gueltiger-provider"}}, "confirm": True},
    )
    assert resp.status_code == 422

    # Die ungueltige Anfrage darf keine Teilaenderung hinterlassen haben.
    resp = client.get("/settings")
    assert resp.json()["ai"]["provider"] == "null"


def test_patch_settings_on_paths_section_reports_restart_required(tmp_path: Path):
    """paths.* (ausser media_folders) wird bewusst NICHT live auf laufende
    Singletons (DB-Handle etc.) angewendet (Risiko eines inkonsistenten
    Zustands) - der Core Service meldet stattdessen ehrlich, dass ein
    Neustart noetig ist."""
    client = _make_client(tmp_path)
    other_log_dir = str(tmp_path / "andere-logs")
    resp = client.patch(
        "/settings",
        json={"updates": {"paths": {"log_dir": other_log_dir}}, "confirm": True},
    )
    assert resp.status_code == 200
    assert resp.json()["restart_required"] is True


def test_patch_settings_media_folders_alone_does_not_require_restart(tmp_path: Path):
    """`media_folders` ist eine reine GUI-Merkliste (der eigentliche Scan
    bekommt seine Zielordner als expliziten Request-Parameter, siehe
    POST /scan) - beeinflusst kein Laufzeit-Singleton, braucht also KEINEN
    Neustart (sonst wuerde das blosse Hinzufuegen eines Ordners in der
    Settings-UI faelschlich einen Neustart suggerieren)."""
    client = _make_client(tmp_path)
    other_dir = str(tmp_path / "andere-mediensammlung")
    resp = client.patch(
        "/settings",
        json={"updates": {"paths": {"media_folders": [other_dir]}}, "confirm": True},
    )
    assert resp.status_code == 200
    assert resp.json()["restart_required"] is False
    assert resp.json()["settings"]["paths"]["media_folders"] == [other_dir]


def test_patch_settings_download_dir_change_applies_live_without_restart(tmp_path: Path):
    """`download.downloads_dir` liegt bewusst NICHT unter `paths.*` (siehe
    DownloadSettings-Docstring) - eine Aenderung muss daher sofort auf den
    laufenden `download_output_dir`/`download_engine` wirken, ohne
    `restart_required` zu melden."""
    client = _make_client(tmp_path)
    new_dir = str(tmp_path / "eigener-download-ordner")
    resp = client.patch(
        "/settings",
        json={"updates": {"download": {"downloads_dir": new_dir}}, "confirm": True},
    )
    assert resp.status_code == 200
    assert resp.json()["restart_required"] is False
    app = client.app
    state = app.state.genesis
    assert str(state.download_output_dir) == new_dir
    assert str(state.download_engine.output_dir) == new_dir


def test_patch_settings_creates_job_history_entry(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.patch(
        "/settings",
        json={"updates": {"voice": {"enabled": True}}, "confirm": True},
    )
    job_id = resp.json()["job_id"]
    job_resp = client.get(f"/jobs/{job_id}")
    assert job_resp.status_code == 200
    assert job_resp.json()["job_type"] == "settings_update"
    assert job_resp.json()["status"] == "completed"


def test_protected_endpoints_reject_missing_or_wrong_token(tmp_path: Path):
    """Deep-Review-Regressionstest (Sitzung 2, Fund HOCH): die lokale API
    darf mutierende/analysierende Endpunkte NICHT ohne gueltiges Token
    ausfuehren - sonst waere sie ueber Drive-by-Localhost-/JSON-CSRF-
    Anfragen aus dem Browser heraus missbrauchbar (ADR-0006)."""
    app = _make_app(tmp_path)

    no_token_client = TestClient(app)
    resp = no_token_client.get("/dashboard/summary")
    assert resp.status_code == 401

    wrong_token_client = TestClient(app)
    wrong_token_client.headers["X-Genesis-Token"] = "definitiv-falsches-token"
    resp = wrong_token_client.get("/dashboard/summary")
    assert resp.status_code == 401

    resp = no_token_client.post("/scan", json={"directories": []})
    assert resp.status_code == 401

    resp = no_token_client.get("/media")
    assert resp.status_code == 401

    resp = no_token_client.get("/jobs")
    assert resp.status_code == 401


def test_scan_and_dashboard_and_media_endpoints(tmp_path: Path, test_library_root: Path):
    client = _make_client(tmp_path)

    scan_resp = client.post("/scan", json={"directories": [str(test_library_root)]})
    assert scan_resp.status_code == 200
    scan_body = scan_resp.json()
    assert scan_body["result"]["files_found"] >= 6

    dashboard_resp = client.get("/dashboard/summary")
    assert dashboard_resp.status_code == 200
    dashboard = dashboard_resp.json()
    assert dashboard["total"] >= 6

    media_resp = client.get("/media")
    assert media_resp.status_code == 200
    media_list = media_resp.json()
    assert media_list["total"] >= 6

    first_id = media_list["items"][0]["id"]
    detail_resp = client.get(f"/media/{first_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "absolute_path" in detail
    assert detail["file_exists_on_disk"] is True

    jobs_resp = client.get("/jobs")
    assert jobs_resp.status_code == 200
    assert len(jobs_resp.json()) >= 1


def test_media_not_found_returns_404(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.get("/media/99999")
    assert resp.status_code == 404


def test_api_token_file_is_written_with_restrictive_permissions(tmp_path: Path):
    """Das Token wird persistiert (ueberlebt einen Neustart des Core
    Service) und ist auf POSIX-Systemen nur fuer den Besitzer lesbar."""
    import stat

    app = _make_app(tmp_path)
    token_path = tmp_path / "api_token.txt"
    assert token_path.exists()
    assert token_path.read_text(encoding="utf-8").strip() == app.state.genesis.api_token

    mode = stat.S_IMODE(token_path.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR
