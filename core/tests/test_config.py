from genesis_core.config import Settings


def test_default_settings_are_privacy_friendly():
    """Prinzip #56: Offline, keine Telemetrie, keine Cloud-KI per Default."""
    s = Settings()
    assert s.privacy.telemetry_enabled is False
    assert s.privacy.allow_cloud_ai is False
    assert s.privacy.allow_automatic_downloads is False
    assert s.privacy.allow_automatic_deletion is False
    assert s.privacy.allow_automatic_overwrite is False
    assert s.ai.enabled is False
    assert s.loudness.overwrite_originals is False
    assert s.metadata.enabled is False  # kein Online-Abgleich ohne Zustimmung (§56)


def test_settings_roundtrip_yaml(tmp_path):
    s = Settings()
    s.paths.data_dir = tmp_path
    s.paths.media_folders = [tmp_path / "Music"]
    config_path = tmp_path / "config.yaml"
    s.save(config_path)

    loaded = Settings.load(config_path)
    assert str(loaded.paths.data_dir) == str(tmp_path)
    assert loaded.paths.media_folders == [tmp_path / "Music"]


def test_load_creates_default_when_missing(tmp_path):
    config_path = tmp_path / "does_not_exist" / "config.yaml"
    loaded = Settings.load(config_path)
    assert config_path.exists()
    assert loaded.general.language == "de"


def test_load_recovers_from_corrupted_yaml(tmp_path):
    """Deep-Review-Regressionstest (Sitzung 2, Fund NIEDRIG-MITTEL): eine
    kaputte config.yaml darf die App nicht mit einem rohen Stacktrace zum
    Absturz bringen (§37). Stattdessen: Defaults verwenden, kaputte Datei
    als Backup sichern (Prinzip #4 - nichts wird stillschweigend geloescht)."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(": this is not valid yaml: [[[", encoding="utf-8")

    loaded = Settings.load(config_path)

    assert loaded.general.language == "de"  # Default statt Absturz
    backups = list(tmp_path.glob("config.broken-*.yaml"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == ": this is not valid yaml: [[["
    # Eine frische, gueltige config.yaml wurde an der Original-Stelle abgelegt
    assert config_path.exists()
    Settings.load(config_path)  # laedt jetzt wieder normal, ohne Fehler


def test_load_recovers_from_unknown_fields_type_error(tmp_path):
    """Auch ein Typfehler (z.B. String statt Zahl) darf nicht crashen."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "loudness:\n  target_lufs: \"nicht-eine-zahl\"\n", encoding="utf-8"
    )

    loaded = Settings.load(config_path)
    assert loaded.loudness.target_lufs == -14.0  # Default
