"""Konfigurationssystem (Originalauftrag §55, Default-Werte §56).

Alle wichtigen Einstellungen sind hier zentral definiert und werden aus einer
YAML-Datei geladen/gespeichert (spaeter: ueber die GUI editierbar, keine
manuelle Dateibearbeitung noetig). Defaults sind bewusst datenschutz- und
offline-freundlich (§56): kein Telemetrie, keine Cloud-KI, keine automatischen
Loeschungen/Ueberschreibungen/Downloads.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import shutil
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

_log = logging.getLogger("genesis_core.config")


def default_data_dir() -> Path:
    """Plattformunabhaengiger Standard-Datenordner fuer GENESIS.

    Unter Windows spaeter z.B. %APPDATA%/GenesisMediaManager. Im Sandbox/Dev-
    Betrieb unter Linux: ~/.genesis-media-manager (dot-Ordner, siehe
    Ressourcen-Disziplin - klein halten, keine Mediendateien hier ablegen).
    """
    env_override = os.environ.get("GENESIS_DATA_DIR")
    if env_override:
        return Path(env_override).expanduser()
    appdata = os.environ.get("APPDATA")  # Windows
    if appdata:
        return Path(appdata) / "GenesisMediaManager"
    return Path.home() / ".genesis-media-manager"


class AISettings(BaseModel):
    """Lokale KI-Anbindung (§25, §46). Kein Cloud-Zwang."""

    enabled: bool = False  # Nutzer muss KI bewusst aktivieren (§56)
    provider: Literal["null", "ollama"] = "null"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:0.5b"
    timeout_seconds: float = 30.0
    # Separates (kleineres) Modell fuer lokale Embeddings/semantische Suche
    # (§26) - Text-Generierungsmodelle unterstuetzen i.d.R. keine
    # /api/embed-Anfragen; dedizierte Embedding-Modelle wie "all-minilm"
    # sind winzig (~45 MB) und laufen auch auf bescheidener Hardware.
    embedding_model: str = "all-minilm"


class VoiceSettings(BaseModel):
    """Lokales Voice Studio / TTS (§28/§29). Kein Cloud-Zwang, Standard AUS -
    der Nutzer muss lokale Sprachsynthese bewusst aktivieren (§56), auch wenn
    sie rein lokal verarbeitet (keine Cloud-Variante existiert ueberhaupt)."""

    enabled: bool = False
    provider: Literal["null", "piper"] = "null"
    default_export_format: Literal["wav", "mp3", "flac"] = "wav"


class LoudnessSettings(BaseModel):
    """§19 - konfigurierbare Zielwerte, Originale nie ungefragt ueberschreiben."""

    target_lufs: float = -14.0
    target_true_peak_dbtp: float = -1.0
    overwrite_originals: bool = False  # Prinzip #5


class MetadataSettings(BaseModel):
    """Online-Metadatenabgleich (§10/§11). Standardmaessig AUS (§56, Prinzip
    "kein Internetzwang") - der Nutzer muss den Online-Abgleich bewusst
    aktivieren. Auch bei enabled=True bleibt jeder Treffer nur ein
    Vorschlag mit Konfidenzwert (Prinzip #17) - niemals eine automatische
    Uebernahme.
    """

    enabled: bool = False
    musicbrainz_enabled: bool = True
    acoustid_enabled: bool = True
    # AcoustID verlangt einen persoenlichen, kostenlosen API-Key
    # (https://acoustid.org/api-key) - GENESIS liefert keinen mit
    # (kein eingebettetes Geheimnis, jeder Nutzer registriert sich selbst).
    acoustid_api_key: str = ""
    coverartarchive_enabled: bool = True
    # Pflichtangabe der MusicBrainz-API-Richtlinie fuer den User-Agent-Header
    # (https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting) - ohne
    # aussagekraeftigen User-Agent drohen IP-Sperren fuer alle Nutzer.
    contact_email: str = ""
    request_timeout_seconds: float = 10.0
    # Vorschlaege unterhalb dieser Konfidenz werden dem Nutzer gar nicht erst
    # angezeigt (weniger Rauschen), OBERHALB davon ist es trotzdem nur ein
    # Vorschlag, nie eine automatische Uebernahme (Prinzip #17).
    min_confidence_for_suggestion: float = 0.4


class DownloadSettings(BaseModel):
    """Download-/Import-Center (§30-§32). Standard AUS (§56, kein
    Internetzwang) - der Nutzer muss das Herunterladen von Fremdinhalten
    bewusst aktivieren, obwohl einzelne Provider (z.B. lokale Dateien) gar
    keine Internetverbindung benoetigen.

    WICHTIG (§30): keine DRM-Umgehung, keine unsichere Speicherung von
    Zugangsdaten/Cookies. GENESIS speichert fuer keinen Provider ueberhaupt
    Zugangsdaten - Dienste, die ein Login/DRM voraussetzen (Spotify,
    Audible, Pocket FM), werden stattdessen als nicht unterstuetzt erkannt
    und entsprechend gemeldet (siehe genesis_core.download.drm_blocked),
    niemals durch Umgehungsversuche "geloest".
    """

    enabled: bool = False
    # None => paths.data_dir / "downloads" (siehe AppState.download_output_dir).
    # Bewusst NICHT automatisch in einen vorhandenen media_folders-Eintrag
    # kopiert - Downloads landen zunaechst in einem eigenen, klar erkennbaren
    # Zwischenordner; der Nutzer entscheidet selbst, wie/ob er sie in seine
    # bestehende Bibliotheksstruktur einsortiert (Prinzip #4/#5, keine
    # ungefragte Vermischung mit bereits organisierten Ordnern).
    downloads_dir: Path | None = None
    # Sicherheitsobergrenze gegen versehentliche/missbraeuchliche
    # Riesen-Downloads (§ Speicherplatzpruefung vor grossen Operationen).
    max_download_size_mb: int = 4096
    # Nach dem Download muss mindestens so viel freier Speicher auf dem
    # Zieldatentraeger uebrig bleiben.
    min_free_disk_mb: int = 1024
    enable_youtube: bool = True
    enable_tiktok: bool = True
    # Zeitlimit fuer Netzwerkoperationen (Verfuegbarkeitspruefung,
    # Metadatenabruf) - verhindert haengende UI bei nicht erreichbaren
    # Diensten.
    request_timeout_seconds: float = 20.0


class PrivacySettings(BaseModel):
    """§45, §56 - datenschutzfreundliche Defaults."""

    telemetry_enabled: bool = False
    allow_cloud_ai: bool = False
    allow_automatic_downloads: bool = False
    allow_automatic_deletion: bool = False
    allow_automatic_overwrite: bool = False


class PathSettings(BaseModel):
    data_dir: Path = Field(default_factory=default_data_dir)
    database_path: Path | None = None  # None => data_dir / "genesis.db"
    backup_dir: Path | None = None  # None => data_dir / "backups"
    temp_dir: Path | None = None  # None => data_dir / "temp"
    log_dir: Path | None = None  # None => data_dir / "logs"
    media_folders: list[Path] = Field(default_factory=list)

    def resolved_database_path(self) -> Path:
        return self.database_path or (self.data_dir / "genesis.db")

    def resolved_backup_dir(self) -> Path:
        return self.backup_dir or (self.data_dir / "backups")

    def resolved_temp_dir(self) -> Path:
        return self.temp_dir or (self.data_dir / "temp")

    def resolved_log_dir(self) -> Path:
        return self.log_dir or (self.data_dir / "logs")


class GeneralSettings(BaseModel):
    language: Literal["de", "en", "ja", "ru"] = "de"
    safe_test_mode: bool = False  # §51 - wird von der Testsuite erzwungen
    require_confirmation_for_bulk_changes: bool = True  # Prinzip #6


class Settings(BaseModel):
    """Wurzel-Konfigurationsobjekt. Wird als YAML persistiert."""

    general: GeneralSettings = Field(default_factory=GeneralSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    ai: AISettings = Field(default_factory=AISettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    download: DownloadSettings = Field(default_factory=DownloadSettings)
    loudness: LoudnessSettings = Field(default_factory=LoudnessSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Laedt die Konfiguration. Faellt bei einer beschaedigten/ungueltigen
        config.yaml NIEMALS mit einem rohen Stacktrace aus (§37,
        Deep-Review-Fund Sitzung 2: fehlende Fehlerbehandlung um
        yaml.safe_load/Pydantic-Validierung). Stattdessen: Warnung loggen,
        die kaputte Datei als .broken-<Zeitstempel> sichern (nichts wird
        stillschweigend geloescht, Prinzip #4) und mit sauberen
        Standardwerten weiterarbeiten - besser eine lauffaehige App mit
        Default-Einstellungen als ein Absturz beim Start.
        """
        path = path or (default_data_dir() / "config.yaml")
        if not path.exists():
            settings = cls()
            settings.save(path)
            return settings

        try:
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return cls.model_validate(raw)
        except (yaml.YAMLError, ValidationError, OSError, UnicodeDecodeError) as exc:
            _log.warning(
                "Konfigurationsdatei %s ist beschaedigt oder ungueltig (%s: %s) - "
                "sichere sie und verwende Standardeinstellungen.",
                path, type(exc).__name__, exc,
            )
            # Bewusst lokale (naive) Zeit statt UTC: dient ausschliesslich
            # als fuer Menschen lesbares Zeitstempel-Suffix im Dateinamen
            # beim Durchsuchen des eigenen Dateisystems, wird nie geparst
            # oder mit anderen Zeitstempeln verglichen (Deep-Review
            # Sitzung 13, DTZ005 bewusst nicht befolgt).
            backup_path = path.with_suffix(
                f".broken-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}{path.suffix}"  # noqa: DTZ005
            )
            try:
                shutil.copy2(path, backup_path)
            except OSError:
                pass  # Sicherung fehlgeschlagen ist kein Grund, den Start zu verhindern
            settings = cls()
            settings.save(path)
            return settings

    def save(self, path: Path | None = None) -> Path:
        path = path or (self.paths.data_dir / "config.yaml")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                self.model_dump(mode="json"), f, allow_unicode=True, sort_keys=False
            )
        return path

    def resolved_downloads_dir(self) -> Path:
        """§30-§32 - Zielordner fuer heruntergeladene/importierte Dateien,
        bewusst getrennt von den vom Nutzer konfigurierten media_folders
        (siehe DownloadSettings-Docstring)."""
        return self.download.downloads_dir or (self.paths.data_dir / "downloads")

    def ensure_directories(self) -> None:
        for d in (
            self.paths.data_dir,
            self.paths.resolved_backup_dir(),
            self.paths.resolved_temp_dir(),
            self.paths.resolved_log_dir(),
            self.resolved_downloads_dir(),
        ):
            Path(d).mkdir(parents=True, exist_ok=True)
