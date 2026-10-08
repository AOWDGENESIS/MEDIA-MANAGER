"""Lokale REST-API des GENESIS Core Service (ADR-0001).

Bindet ausschliesslich an 127.0.0.1 (siehe scripts/run_api.py). Wird von
beiden UI-Clients (PySide6-Referenz, .NET-WPF-Ziel) gleichermassen genutzt.
OpenAPI-Schema wird von FastAPI automatisch unter /docs bereitgestellt -
Grundlage fuer einen generierten C#-Client (siehe ARCHITECTURE.md).
"""
from __future__ import annotations

import dataclasses
import datetime as dt_module
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select

from genesis_core import __version__
from genesis_core import library as library_module
from genesis_core.ai import build_ai_provider
from genesis_core.ai.base import AISuggestion
from genesis_core.ai.engine import (
    AIApplyNotConfirmedError,
    list_ai_metadata,
)
from genesis_core.ai.engine import (
    apply_suggestions as ai_apply_suggestions,
)
from genesis_core.ai.engine import (
    suggest_metadata as ai_suggest_metadata,
)
from genesis_core.ai.music_provenance import (
    AIMusicApplyNotConfirmedError,
    AIMusicProvenanceInput,
    apply_ai_music_provenance,
    artist_names_for_track,
    get_ai_music_provenance,
)
from genesis_core.ai.search import reindex_all, semantic_search
from genesis_core.api.security import load_or_create_token, make_token_dependency
from genesis_core.artwork import (
    ArtworkError,
    cache_artwork,
    embed_artwork,
    extract_embedded_artwork,
)
from genesis_core.audiobook import (
    AudiobookApplyNotConfirmedError,
    ChapterDetectionError,
    apply_audiobook_tags,
    detect_chapters,
    export_chapters_csv,
    export_chapters_json,
    generate_fixed_interval_chapters,
    read_audiobook_tags,
    replace_chapters,
)
from genesis_core.backup import (
    BackupError,
    BackupRestoreNotConfirmedError,
    create_config_backup,
    create_db_backup,
    list_backups,
    restore_db_backup,
)
from genesis_core.config import Settings
from genesis_core.convert import (
    ConversionApplyNotConfirmedError,
    ConversionRenderError,
    InvalidConversionRequestError,
    apply_conversion,
    plan_conversion,
)
from genesis_core.cutter import (
    CutApplyNotConfirmedError,
    CutRenderError,
    InvalidCutSelectionError,
    WaveformGenerationError,
    apply_cut,
    generate_waveform_image,
    plan_cut,
)
from genesis_core.db import Database
from genesis_core.db.models import (
    AIMetadata,
    AIStatus,
    Album,
    Artwork,
    Audiobook,
    AudioConversion,
    AudioCut,
    Backup,
    Chapter,
    DuplicateGroup,
    DuplicateGroupMember,
    Episode,
    ErrorLog,
    Fingerprint,
    JobStatus,
    Loudness,
    MediaFile,
    MediaKind,
    Movie,
    Person,
    PersonRole,
    PersonRoleType,
    ProcessingJob,
    Source,
    TechnicalMetadata,
    Track,
    VoiceProfile,
    VoiceSynthesis,
)
from genesis_core.diagnostics import DiagnosticsReport, run_diagnostics
from genesis_core.download import (
    ConfirmationRequiredError as DownloadConfirmationRequiredError,
)
from genesis_core.download import (
    DownloadEngine,
    DownloadError,
    DownloadNotPermittedError,
    build_download_providers,
)
from genesis_core.download import (
    ProviderNotFoundError as DownloadProviderNotFoundError,
)
from genesis_core.download import (
    SourceMetadata as DownloadSourceMetadata,
)
from genesis_core.duplicates import MediaSnapshot, find_duplicate_candidates
from genesis_core.errors import list_errors, log_exception, mark_resolved
from genesis_core.exporter import build_export_rows, to_csv, to_json, to_m3u, to_xml
from genesis_core.fingerprint import FingerprintError, compute_fingerprint
from genesis_core.jobs import JobCancelledError, JobManager, JobTransitionError
from genesis_core.logutil import configure_logging, get_logger
from genesis_core.logutil.reader import read_log_entries
from genesis_core.loudness import (
    LoudnessMeasurement as LoudnessMeasurementSnapshot,
)
from genesis_core.loudness import (
    LoudnessMeasurementError,
    NormalizationApplyNotConfirmedError,
    apply_normalization,
    measure_loudness,
    plan_normalization,
)
from genesis_core.loudness.engine import UnsupportedMediaKindError
from genesis_core.metadata import MetadataEngine, MetadataSuggestion
from genesis_core.metadata.engine import MetadataApplyNotConfirmedError
from genesis_core.metadata.tag_reader import ExistingTags
from genesis_core.plugins import LoadedPlugin, PluginRegistry
from genesis_core.providers import ProviderError, ProviderNotConfiguredError, build_providers
from genesis_core.providers.base import RecordingMatch
from genesis_core.quality import QualitySnapshot, analyze_quality
from genesis_core.relocate import (
    RelocationApplyNotConfirmedError,
    RelocationCandidate,
    apply_relocations,
    find_relocation_candidates,
)
from genesis_core.rename import (
    RenameApplyNotConfirmedError,
    RenameBatchFailedError,
    apply_renames,
    preview_renames,
)
from genesis_core.rename.templates import RenameTemplateError
from genesis_core.repair import (
    RepairExecuteNotConfirmedError,
    RepairPlanItem,
    execute_repairs,
    plan_repairs,
    preview_repairs,
)
from genesis_core.scanner.scanner import scan_directories
from genesis_core.storage import InsufficientStorageError
from genesis_core.video import (
    VideoApplyNotConfirmedError,
    apply_episode_metadata,
    apply_movie_metadata,
    detect_episode,
    read_video_tags,
)
from genesis_core.voice import TTSProviderUnavailableError, build_tts_provider
from genesis_core.voice.catalog import ENGINE_CATALOG
from genesis_core.voice.engine import (
    VoiceApplyNotConfirmedError,
    VoiceDeleteNotConfirmedError,
    VoiceProfileInput,
    VoiceProfileNotFoundError,
    VoiceSynthesisError,
    create_voice_profile,
    delete_voice_profile,
    get_test_phrase_for_language,
    list_syntheses,
    list_voice_profiles,
    synthesize_text,
)

log = get_logger("API")


class ScanRequest(BaseModel):
    """Auf Modulebene definiert (nicht lokal in create_app), da FastAPI in
    Kombination mit ``from __future__ import annotations`` lokal
    verschachtelte Pydantic-Modelle nicht zuverlaessig als Body erkennt
    (String-Annotationen koennen dann nicht gegen die Funktions-Closure
    aufgeloest werden) - siehe PROGRESS.md Fehlerhistorie."""

    directories: list[str]
    compute_hash: bool = True
    run_ffprobe: bool = True


class SettingsUpdateRequest(BaseModel):
    """§55 - partielles PATCH der Konfiguration (Gap-Analyse A). `updates`
    folgt derselben verschachtelten Struktur wie GET /settings, z.B.
    {"ai": {"enabled": true}} - absichtlich ein loses dict statt eines
    vollstaendig typisierten verschachtelten Modells, damit echte
    PATCH-Semantik (nur die erwaehnten Blaetter aendern sich) moeglich ist,
    ohne dass der Aufrufer jedes Mal das komplette Settings-Objekt erneut
    mitsenden muss."""

    updates: dict[str, Any]
    confirm: bool = False


class RecordingMatchPayload(BaseModel):
    """Spiegelt genesis_core.providers.base.RecordingMatch - wird vom Client
    unveraendert aus der GET-.../metadata-suggestions-Antwort zurueckgeschickt,
    wenn er einen Vorschlag uebernehmen moechte (kein serverseitiger
    Vorschlags-Cache noetig)."""

    provider: str
    confidence: float
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    track_number: int | None = None
    musicbrainz_recording_id: str | None = None
    musicbrainz_release_id: str | None = None
    musicbrainz_artist_id: str | None = None


class ApplyMetadataSuggestionRequest(BaseModel):
    match: RecordingMatchPayload
    # Muss vom Client explizit auf True gesetzt werden, NACHDEM der Nutzer
    # den Vorschlag in der UI bestaetigt hat (Prinzip #17, §44). Es gibt
    # bewusst keinen Default, der eine automatische Uebernahme ermoeglicht.
    confirm: bool = False


class RenamePreviewRequest(BaseModel):
    media_file_ids: list[int]
    template: str


class RenameApplyRequest(BaseModel):
    media_file_ids: list[int]
    template: str
    confirm: bool = False


class EmbedArtworkRequest(BaseModel):
    artwork_id: int
    confirm: bool = False


class LoudnessNormalizePreviewRequest(BaseModel):
    """Zielwerte sind optional - fehlen sie, werden die konfigurierten
    Standardwerte aus `Settings.loudness` verwendet (§19)."""

    target_lufs: float | None = None
    target_true_peak_dbtp: float | None = None
    target_lra: float = 11.0


class LoudnessNormalizeApplyRequest(LoudnessNormalizePreviewRequest):
    confirm: bool = False


class CutPreviewRequest(BaseModel):
    """§18 - Auswahl fuer den Audio-Cutter. `export_format` ist ein Name aus
    `genesis_core.audio_formats.FORMATS_BY_NAME` (mind. mp3/wav/flac, §18)."""

    start_seconds: float
    end_seconds: float
    export_format: str = "mp3"
    fade_in_seconds: float = 0.0
    fade_out_seconds: float = 0.0


class CutApplyRequest(CutPreviewRequest):
    confirm: bool = False


class ConvertPreviewRequest(BaseModel):
    """nav.convert - Zielformat ist ein Name aus
    `genesis_core.audio_formats.FORMATS_BY_NAME`. `bitrate_kbps` ist optional
    und wirkt nur bei verlustbehafteten Zielformaten."""

    target_format: str
    bitrate_kbps: int | None = None


class ConvertApplyRequest(ConvertPreviewRequest):
    confirm: bool = False


class DuplicateScanRequest(BaseModel):
    """§21 - optionaler Scope-Filter fuer einen Duplikaterkennungs-Lauf.
    Ohne Angabe wird die gesamte (nicht fehlende) Bibliothek durchsucht."""

    kind: str | None = None


class ApplyAudiobookTagsRequest(BaseModel):
    """§23 - der Client schickt bewusst KEINE Metadaten-Werte mit, sondern
    nur die Bestaetigung. Der Server liest die Tags beim Anwenden ERNEUT
    direkt aus der Datei (wie bei der GET-Vorschau) - Defense-in-Depth,
    analog zur Lehre aus Deep-Review-Fund F-12 (Client-Payload nicht
    blind uebernehmen)."""

    confirm: bool = False


class DetectChaptersApplyRequest(BaseModel):
    confirm: bool = False


class GenerateChaptersRequest(BaseModel):
    """§23 (optional) - erzeugt GLEICHMAESSIGE Intervall-Kapitel, siehe
    genesis_core/audiobook/engine.py Moduldocstring."""

    interval_minutes: float = 10.0


class GenerateChaptersApplyRequest(GenerateChaptersRequest):
    confirm: bool = False


class RenameChapterRequest(BaseModel):
    title: str
    confirm: bool = False


class ApplyVideoMetadataRequest(BaseModel):
    """§24 - der Client schickt bewusst KEINE Metadaten-Werte mit, sondern
    nur die Bestaetigung. Der Server liest Tags/Dateipfad beim Anwenden
    ERNEUT selbst aus (Defense-in-Depth, analog ADR-0015)."""

    confirm: bool = False


class AISuggestRequest(BaseModel):
    """§25 - leerer Body = alle Standardfelder (SUGGESTABLE_FIELDS)."""

    fields: list[str] | None = None


class AcceptedAISuggestion(BaseModel):
    """Ein vom Nutzer in der Vorschau akzeptierter KI-Vorschlag. Der Client
    schickt das exakte Vorschlagsobjekt aus der Preview-Antwort zurueck -
    der Server erfindet nichts neu, uebernimmt aber bewusst NICHT
    automatisch alle Vorschlaege (Prinzip #17: nur was explizit markiert
    wurde)."""

    field_name: str
    field_value: str
    model_name: str
    model_version: str | None = None
    confidence: float | None = None
    prompt: str | None = None


class AIApplyRequest(BaseModel):
    accepted: list[AcceptedAISuggestion]
    confirm: bool = False


class AIMusicApplyRequest(BaseModel):
    """§27 - IMMER eine manuelle Nutzerangabe, niemals ein KI-Vorschlag."""

    status: Literal["ai_generated", "human_generated", "hybrid", "unknown"]
    source: str | None = None
    model: str | None = None
    prompt: str | None = None
    creation_date: dt_module.datetime | None = None
    instrumental: bool | None = None
    style: str | None = None
    mood: str | None = None
    owner: str | None = None
    artist_name: str | None = None
    confirm: bool = False


class AISearchRequest(BaseModel):
    query: str
    top_k: int = 20


class CreateVoiceProfileRequest(BaseModel):
    """§28 - alle vier Pflichtangaben (Engine/Lizenz/Offline/Open-Source)
    sowie die kommerzielle Nutzbarkeit muessen vom Client explizit
    mitgeschickt werden (keine stillschweigenden Defaults aus einem
    Katalog, Prinzip #9/#17) - `GET /voice/engines` liefert dafuer nur
    unverbindliche Vorschlagswerte fuer das Formular."""

    name: str
    engine: str
    model_path: str | None = None
    language: str | None = None
    description: str | None = None
    model_license: str | None = None
    offline_capable: bool = True
    open_source: bool = True
    commercial_use_allowed: bool | None = None
    sample_path: str | None = None
    confirm: bool = False


class DeleteVoiceProfileRequest(BaseModel):
    """§28/Prinzip #6: Loeschen = extra confirm - `confirm_name` muss exakt
    dem Profilnamen entsprechen, zusaetzlich zu `confirm=True`."""

    confirm: bool = False
    confirm_name: str | None = None


class VoiceSynthesizeRequest(BaseModel):
    text: str
    export_format: str = "wav"
    confirm: bool = False


class VoiceTestRequest(BaseModel):
    confirm: bool = False


class DownloadUrlRequest(BaseModel):
    """§31 - reine Vorschau-Schritte (Erkennen/Verfuegbarkeit/Metadaten/
    Optionen) brauchen keine Bestaetigung (Prinzip #4/#5)."""

    url: str


class DownloadImportRequest(BaseModel):
    url: str
    option_id: str = "default"
    confirm: bool = False


class LocalFileImportRequest(BaseModel):
    path: str
    confirm: bool = False


class RestoreBackupRequest(BaseModel):
    """§40 - eine Wiederherstellung ueberschreibt die aktive Datenbank und
    ist damit eine ECHTE Aenderung, braucht daher IMMER eine Bestaetigung."""

    confirm: bool = False


class RepairPlanItemRef(BaseModel):
    """Minimaler Verweis auf einen Plan-Eintrag (§39) - der Client sendet
    nur action_type+target zurueck, die zusaetzlichen Felder (count/
    estimated_bytes/description) werden serverseitig ohnehin neu ermittelt."""

    action_type: str
    target: str


class RepairPreviewRequest(BaseModel):
    items: list[RepairPlanItemRef]


class RepairTempFileRef(BaseModel):
    path: str
    size_bytes: int
    modified_at: str
    age_seconds: float


class RepairPreviewItemRef(BaseModel):
    action_type: str
    target: str
    row_ids: list[int] = []
    temp_files: list[RepairTempFileRef] = []


class RepairExecuteRequest(BaseModel):
    items: list[RepairPreviewItemRef]
    confirm: bool = False


class RelocateScanRequest(BaseModel):
    """§43 - rein lesend, braucht keine Bestaetigung."""

    search_roots: list[str]
    use_fingerprint: bool = False


class RelocationCandidateRef(BaseModel):
    media_file_id: int
    old_absolute_path: str
    new_absolute_path: str
    match_method: str
    confidence: float


class RelocateApplyRequest(BaseModel):
    candidates: list[RelocationCandidateRef]
    confirm: bool = False


class AppState:
    """Haelt Singletons (DB, Settings, JobManager) fuer die Lebensdauer des
    Prozesses. Bewusst simpel gehalten (kein globaler Zustand ausserhalb
    dieser Klasse), damit Tests eine eigene, isolierte Instanz erzeugen
    koennen (SAFE TEST MODE, §51)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        settings.ensure_directories()
        configure_logging(log_dir=settings.paths.resolved_log_dir())
        self.db = Database(settings.paths.resolved_database_path())
        self.jobs = JobManager(self.db, app_version=__version__)
        self.ai_provider = build_ai_provider(settings.ai)
        self.tts_provider = build_tts_provider(settings.voice)
        # §28 "Audio exportieren" - erzeugte Sprachausgaben landen in einem
        # eigenen Unterordner des Datenverzeichnisses (analog zu
        # waveform_cache/artwork_cache), NIEMALS im Ordner einer
        # Original-Mediendatei (Prinzip #4/#5).
        self.voice_output_dir = settings.paths.data_dir / "voice_output"
        # ADR-0006 (Deep Review Sitzung 2): lokales Shared-Secret-Token gegen
        # Drive-by-Localhost-/JSON-CSRF-Anfragen von im Browser geoeffneten
        # Fremdseiten. Siehe genesis_core/api/security.py fuer Details.
        self.api_token = load_or_create_token(settings.paths.data_dir)
        # Phase 2: Online-Metadaten (§10) - Provider sind bewusst None/inaktiv,
        # solange settings.metadata.enabled=False (§56, kein Internetzwang).
        self.providers = build_providers(settings.metadata)
        self.metadata_engine = MetadataEngine(self.providers, settings.metadata)
        self.artwork_cache_dir = settings.paths.data_dir / "artwork_cache"
        # §18 Audio Cutter: Waveform-Bilder sind reine, jederzeit neu
        # erzeugbare Visualisierungs-Caches (keine Nutzerdaten) - duerfen
        # daher im Unterschied zu Original-/Exportdateien freizuegig
        # ueberschrieben werden.
        self.cutter_waveform_dir = settings.paths.data_dir / "waveform_cache"
        # §30-§32 Download-/Import-Center - Provider sind rein lokal
        # instanziiert (kein Netzwerkaufruf bei der Erstellung); ob ein
        # Provider tatsaechlich online ist, zeigt erst check_availability().
        self.download_output_dir = settings.resolved_downloads_dir()
        self.download_providers = build_download_providers(settings.download)
        self.download_engine = DownloadEngine(
            self.db,
            self.download_providers,
            self.download_output_dir,
            settings.download,
            self.jobs,
        )
        # §34 Plugin-System: Nutzer legen eigene Plugins explizit in diesem
        # Unterordner des Datenverzeichnisses ab - es gibt KEIN automatisches
        # Einsammeln von Plugins aus beliebigen Orten (Prinzip #4/#5, keine
        # ungefragte Codeausfuehrung). Die mitgelieferten Beispiel-Plugins
        # unter genesis_core/plugins/examples/ werden hier bewusst NICHT
        # automatisch geladen (sind reine Dokumentation/Testgrundlage).
        self.plugins_dir = settings.paths.data_dir / "plugins"
        self.plugin_registry = PluginRegistry()
        self.plugin_registry.discover_and_load(self.plugins_dir)

    def apply_settings_update(self, new_settings: Settings) -> bool:
        """§55 - wendet eine bereits validierte+gespeicherte Konfiguration
        auf den LAUFENDEN Prozess an (kein Neustart fuer die meisten
        Einstellungen noetig, Gap-Analyse A).

        Provider-Objekte (KI/TTS/Metadaten/Download) sind laut ihren
        eigenen `build_*()`-Fabriken rein lokale, ohne Netzwerkaufruf
        instanziierte Objekte (siehe Docstrings in `__init__` oben) - sie
        koennen daher jederzeit gefahrlos neu erzeugt werden.

        `paths.*` wird bewusst NICHT hot-reloaded: ein laufender
        `Database`-Handle live auf eine andere `database_path` umzubiegen
        (oder Log-/Cache-Verzeichnisse mitten im Betrieb zu wechseln,
        waehrend ggf. Jobs/Hintergrundoperationen laufen) waere riskant
        und koennte zu inkonsistentem Zustand fuehren. Stattdessen wird
        die neue Konfiguration zwar auf Platte gespeichert (wirkt beim
        naechsten Start), der laufende Prozess meldet aber
        `restart_required=True` zurueck, statt eine Teil-Migration
        vorzutaeuschen, die nicht wirklich vollstaendig stattgefunden hat
        (Grundprinzip: nichts vortaeuschen, was nicht tatsaechlich
        geschehen ist).
        """
        # `media_folders` ist rein eine von der GUI verwaltete Merkliste
        # (der eigentliche Scan nimmt seine Zielordner direkt als
        # Request-Parameter entgegen, siehe POST /scan) - sie beeinflusst
        # KEIN zur Prozesslaufzeit instanziiertes Singleton und darf daher
        # aus dem Neustart-Vergleich ausgenommen werden, sonst wuerde die
        # UI faelschlich einen Neustart verlangen, nur weil der Nutzer
        # einen Ordner zur Liste hinzugefuegt hat.
        old_paths = self.settings.paths.model_dump()
        new_paths = new_settings.paths.model_dump()
        old_paths.pop("media_folders", None)
        new_paths.pop("media_folders", None)
        restart_required = old_paths != new_paths
        self.settings = new_settings
        self.ai_provider = build_ai_provider(new_settings.ai)
        self.tts_provider = build_tts_provider(new_settings.voice)
        self.providers = build_providers(new_settings.metadata)
        self.metadata_engine = MetadataEngine(self.providers, new_settings.metadata)
        # `download.downloads_dir` liegt (bewusst, siehe DownloadSettings-
        # Docstring) NICHT unter `paths.*` und loest daher kein
        # `restart_required` aus - muss hier also tatsaechlich neu
        # berechnet werden, sonst wuerde eine Aenderung erst nach einem
        # Neustart wirken, obwohl die UI faelschlich "sofort wirksam"
        # suggeriert.
        self.download_output_dir = new_settings.resolved_downloads_dir()
        new_settings.ensure_directories()
        self.download_providers = build_download_providers(new_settings.download)
        self.download_engine = DownloadEngine(
            self.db,
            self.download_providers,
            self.download_output_dir,
            new_settings.download,
            self.jobs,
        )
        return restart_required


def _deep_merge_dict(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Rekursives Merge fuer das partielle Settings-PATCH (Gap-Analyse A):
    nur die in `updates` tatsaechlich enthaltenen Blaetter werden ersetzt,
    alle anderen, nicht erwaehnten Felder bleiben unveraendert (echte
    PATCH- statt PUT-Semantik)."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    state = AppState(settings)

    app = FastAPI(
        title="GENESIS Media Manager - Core API",
        version=__version__,
        description=(
            "Lokale, offline-first REST-API (nur 127.0.0.1). Siehe "
            "ARCHITECTURE.md im Projekt-Root fuer den Gesamtkontext."
        ),
    )
    app.state.genesis = state

    def get_state() -> AppState:
        return app.state.genesis

    require_token = Depends(make_token_dependency(state.api_token))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """§37 "keine stillen Fehler" - faengt JEDE sonst unbehandelte
        Exception ab, BEVOR sie als nackte, kontextlose 500-Antwort beim
        Client ankäme. Erwartete Validierungsfehler (HTTPException, z.B.
        422/403/404 aus den einzelnen Endpunkten) durchlaufen diesen
        Handler NICHT (FastAPI behandelt sie bereits vorher separat) - hier
        landen ausschliesslich echte, unerwartete Fehler.

        Antwortformat folgt bewusst dem §37-Beispiel aus dem
        Originalauftrag (Fehlermeldung, Grund/technische Details,
        Loesungsvorschlag, Error-ID zum Nachverfolgen/Melden)."""
        record = log_exception(
            state.db,
            component=f"api:{request.url.path}",
            exc=exc,
            action=request.method,
            solution_hint=(
                "Bitte erneut versuchen. Falls der Fehler wiederholt auftritt, die "
                "Error-ID im Diagnose-/Fehler-Center nachschlagen oder im Log "
                "(siehe Einstellungen > Logs) die technischen Details einsehen."
            ),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_id": record.error_id,
                "timestamp": record.timestamp,
                "component": record.component,
                "message": "Ein unerwarteter Fehler ist aufgetreten. Es wurden keine "
                "Dateien veraendert.",
                "solution_hint": record.solution_hint,
            },
        )

    @app.get("/health")
    # Bewusst OHNE Token-Pflicht: reiner Liveness-Check ohne aendernde
    # Wirkung und ohne schuetzenswerte Daten (ADR-0006) - so kann die UI vor
    # dem Einlesen des Tokens bereits pruefen, ob der Core-Service laeuft.
    def health(state: AppState = Depends(get_state)) -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "safe_test_mode": state.settings.general.safe_test_mode,
            "ai_provider": state.ai_provider.name,
            "ai_available": state.ai_provider.is_available(),
        }

    @app.get("/settings", dependencies=[require_token])
    def get_settings_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Nur-lesender Zugriff auf die aktuelle Konfiguration (Analyse-
        Charakter, kein Confirm noetig, Prinzip #6). Dient u.a. der
        Sprachauswahl (§53) beim Start der UI. Schreibzugriff (vollstaendige
        GUI-basierte Konfiguration statt manuellem config.yaml-Editieren,
        §52-Geist) ist seit Schliessung von Gap A (docs/GAP_ANALYSIS.md)
        ueber `PATCH /settings` (siehe `update_settings_endpoint` direkt
        darunter) verfuegbar - NICHT mehr Teil dieses rein lesenden
        Endpunkts."""
        return state.settings.model_dump()

    @app.patch("/settings", dependencies=[require_token])
    def update_settings_endpoint(
        req: SettingsUpdateRequest, state: AppState = Depends(get_state),
    ) -> dict:
        """Settings aendern (schliesst Gap A aus docs/GAP_ANALYSIS.md).
        `updates` ist ein PARTIELLES, beliebig tief verschachteltes Objekt
        in derselben Struktur wie die Antwort von GET /settings, z.B.
        {"ai": {"enabled": true}} - nicht erwaehnte Felder bleiben
        unveraendert (Prinzip #4/#5: keine ungefragten Nebenwirkungen).

        Erfordert wie jede aendernde Aktion im Projekt confirm=true
        (Prinzip #17)."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - Einstellungen aendern braucht eine "
                "explizite Nutzerbestaetigung (Prinzip #17).",
            )
        before = state.settings.model_dump(mode="json")
        merged = _deep_merge_dict(before, req.updates)
        try:
            new_settings = Settings.model_validate(merged)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=f"Ungueltige Einstellungen: {exc}"
            ) from exc

        new_settings.save()
        new_settings.ensure_directories()
        restart_required = state.apply_settings_update(new_settings)
        after = new_settings.model_dump(mode="json")

        job_id = state.jobs.create_job(
            "settings_update", params={"changed_top_level_keys": list(req.updates.keys())}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="settings_update", before=before, after=after,
            user_action="Nutzer hat Einstellungen geaendert",
        )
        state.jobs.complete(job_id)

        return {
            "settings": after,
            "restart_required": restart_required,
            "job_id": job_id,
        }

    @app.get("/dashboard/summary", dependencies=[require_token])
    def dashboard_summary(state: AppState = Depends(get_state)) -> dict:
        """§5 Dashboard - Uebersicht ueber die komplette Bibliothek."""
        with state.db.session() as session:
            counts = dict(
                session.execute(
                    select(MediaFile.kind, func.count(MediaFile.id))
                    .where(MediaFile.is_missing == False)
                    .group_by(MediaFile.kind)
                ).all()
            )
            total = sum(counts.values())
            missing = session.execute(
                select(func.count(MediaFile.id)).where(MediaFile.is_missing == True)
            ).scalar_one()
            no_technical = session.execute(
                select(func.count(MediaFile.id)).where(
                    MediaFile.is_missing == False,
                    ~MediaFile.id.in_(select(TechnicalMetadata.media_file_id)),
                )
            ).scalar_one()
            running_jobs = session.execute(
                select(func.count(ProcessingJob.id)).where(
                    ProcessingJob.status == JobStatus.RUNNING
                )
            ).scalar_one()

        return {
            "counts_by_kind": {k.value: v for k, v in counts.items()},
            "total": total,
            "missing_files": missing,
            "not_yet_analyzed": no_technical,
            "running_jobs": running_jobs,
        }

    @app.post("/scan", dependencies=[require_token])
    def trigger_scan(req: ScanRequest, state: AppState = Depends(get_state)) -> dict:
        """Startet einen (fuer Phase 1 synchronen) Scan. Read-only, veraendert
        nie eine Mediendatei (Prinzip #4/#5, §6 letzter Satz)."""
        job_id = state.jobs.create_job("scan", params=req.model_dump())
        state.jobs.start(job_id)
        try:
            result = scan_directories(
                state.db,
                [Path(d) for d in req.directories],
                compute_hash=req.compute_hash,
                run_ffprobe=req.run_ffprobe,
            )
        except Exception as exc:
            state.jobs.fail(job_id, str(exc))
            raise HTTPException(status_code=500, detail=f"Scan fehlgeschlagen: {exc}") from exc

        state.jobs.report_progress(
            job_id, processed_items=result.files_found, error_delta=len(result.errors)
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "result": dataclass_to_dict(result)}

    @app.get("/media", dependencies=[require_token])
    def list_media(
        kind: MediaKind | None = None,
        search: str | None = Query(
            default=None,
            description=(
                "Freitextsuche ueber Dateiname/Pfad sowie Titel/Interpret/Album/"
                "Genre/Autor/Sprecher/Regisseur/Schauspieler/Serie/Quelle (§9)"
            ),
        ),
        year: int | None = Query(default=None, description="Erscheinungsjahr (§9)"),
        genre: str | None = Query(default=None, description="Genre-Name, Teilstring (§9)"),
        extension: str | None = Query(
            default=None, description="Dateiformat/-endung ohne Punkt, z.B. 'mp3' (§9)"
        ),
        min_size_bytes: int | None = Query(default=None, description="Dateigroesse Minimum (§9)"),
        max_size_bytes: int | None = Query(default=None, description="Dateigroesse Maximum (§9)"),
        min_duration_s: float | None = Query(default=None, description="Dauer Minimum in s (§9)"),
        max_duration_s: float | None = Query(default=None, description="Dauer Maximum in s (§9)"),
        source: str | None = Query(
            default=None, description="Quelle/Provider, Teilstring (§9/§32)"
        ),
        person: str | None = Query(
            default=None,
            description="Person (Autor/Sprecher/Regisseur/Schauspieler/...), Teilstring (§9/§63)",
        ),
        series: str | None = Query(default=None, description="Serie/Reihe, Teilstring (§9)"),
        season: int | None = Query(default=None, description="Staffelnummer (§9)"),
        episode_number: int | None = Query(default=None, description="Episodennummer (§9)"),
        ai_status: str | None = Query(
            default=None,
            description=(
                "KI-Status eines Musiktitels: ai_generated/human_generated/hybrid/"
                "unknown (§9/§27)"
            ),
        ),
        min_lufs: float | None = Query(default=None, description="Integrierte Lautheit Minimum (§9/§19)"),
        max_lufs: float | None = Query(default=None, description="Integrierte Lautheit Maximum (§9/§19)"),
        has_quality_issues: bool | None = Query(
            default=None, description="Nur Dateien mit Qualitaetsverdacht (§9/§20)"
        ),
        missing_metadata: bool | None = Query(
            default=None, description="Nur Dateien ohne Titel-Metadaten (§9)"
        ),
        missing_cover: bool | None = Query(
            default=None, description="Nur Dateien ohne Cover/Artwork (§9)"
        ),
        duplicate_only: bool | None = Query(
            default=None, description="Nur Dateien in einer (noch nicht geprueften) Duplikatgruppe (§9/§21)"
        ),
        limit: int = 100,
        offset: int = 0,
        state: AppState = Depends(get_state),
    ) -> dict:
        """§9 - Globale Suche/Filter ueber die gesamte Bibliothek.

        Erweitert um Gap-Analyse Gap C: zuvor filterte dieser Endpunkt nur
        nach `kind` und einem reinen Dateiname-/Pfad-Substring. Die
        eigentliche Abfrage (inkl. aller Joins/Teilabfragen ueber
        Track/Album/Artist/Genre/Person/Series/Source/TechnicalMetadata/
        Loudness/Artwork/DuplicateGroup) lebt in
        `genesis_core.library.build_media_search_statement` - rein lesend,
        veraendert keine Datensaetze (Prinzip #4/#5).
        """
        with state.db.session() as session:
            stmt = library_module.build_media_search_statement(
                kind=kind,
                search=search,
                year=year,
                genre=genre,
                extension=extension,
                min_size_bytes=min_size_bytes,
                max_size_bytes=max_size_bytes,
                min_duration_s=min_duration_s,
                max_duration_s=max_duration_s,
                source=source,
                person=person,
                series=series,
                season=season,
                episode_number=episode_number,
                ai_status=ai_status,
                min_lufs=min_lufs,
                max_lufs=max_lufs,
                has_quality_issues=has_quality_issues,
                missing_metadata=missing_metadata,
                missing_cover=missing_cover,
                duplicate_only=duplicate_only,
            )
            total = session.execute(
                select(func.count()).select_from(stmt.subquery())
            ).scalar_one()
            rows = session.execute(stmt.offset(offset).limit(limit)).scalars().all()
            items = [media_file_to_dict(m) for m in rows]
        return {"total": total, "items": items}

    @app.get("/media/{media_id}", dependencies=[require_token])
    def get_media_detail(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """§8/§59 - vollstaendige Detailansicht inkl. physischem Dateipfad."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            detail = media_file_to_dict(media_file)
            detail["technical"] = (
                _technical_to_dict(media_file.technical) if media_file.technical else None
            )
            detail["file_exists_on_disk"] = Path(media_file.absolute_path).exists()
            track = session.execute(
                select(Track).where(Track.media_file_id == media_id)
            ).scalar_one_or_none()
            detail["track"] = track_to_dict(track)
            has_artwork = extract_embedded_artwork(media_file.absolute_path) is not None
            detail["has_embedded_artwork"] = has_artwork
        return detail

    # -- Bibliotheks-Drill-down (§9/§62, Gap-Analyse B) -------------------
    # Rein lesende Browsing-Endpunkte oberhalb bestehender Tabellen
    # (genesis_core.library) - loesen die bisherigen reinen
    # Navigations-Platzhalter fuer Interpreten/Alben/Titel/Genres/
    # Personen/Quellen ab.

    @app.get("/library/artists", dependencies=[require_token])
    def list_library_artists(
        search: str | None = Query(default=None), state: AppState = Depends(get_state)
    ) -> list[dict]:
        with state.db.session() as session:
            return [dataclasses.asdict(a) for a in library_module.list_artists(session, search)]

    @app.get("/library/artists/{artist_id}", dependencies=[require_token])
    def get_library_artist_detail(artist_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            detail = library_module.get_artist_detail(session, artist_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Interpret nicht gefunden")
            return dataclasses.asdict(detail)

    @app.get("/library/albums", dependencies=[require_token])
    def list_library_albums(
        search: str | None = Query(default=None), state: AppState = Depends(get_state)
    ) -> list[dict]:
        with state.db.session() as session:
            return [dataclasses.asdict(a) for a in library_module.list_albums(session, search)]

    @app.get("/library/albums/{album_id}", dependencies=[require_token])
    def get_library_album_detail(album_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            detail = library_module.get_album_detail(session, album_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Album nicht gefunden")
            return dataclasses.asdict(detail)

    @app.get("/library/tracks", dependencies=[require_token])
    def list_library_tracks(
        search: str | None = Query(default=None),
        limit: int = 200,
        offset: int = 0,
        state: AppState = Depends(get_state),
    ) -> dict:
        with state.db.session() as session:
            total, items = library_module.list_tracks(session, search, limit, offset)
            return {"total": total, "items": [dataclasses.asdict(i) for i in items]}

    @app.get("/library/genres", dependencies=[require_token])
    def list_library_genres(
        search: str | None = Query(default=None), state: AppState = Depends(get_state)
    ) -> list[dict]:
        with state.db.session() as session:
            return [dataclasses.asdict(g) for g in library_module.list_genres(session, search)]

    @app.get("/library/genres/{genre_id}", dependencies=[require_token])
    def get_library_genre_detail(genre_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            detail = library_module.get_genre_detail(session, genre_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Genre nicht gefunden")
            return dataclasses.asdict(detail)

    @app.get("/library/persons", dependencies=[require_token])
    def list_library_persons(
        search: str | None = Query(default=None), state: AppState = Depends(get_state)
    ) -> list[dict]:
        with state.db.session() as session:
            return [dataclasses.asdict(p) for p in library_module.list_persons(session, search)]

    @app.get("/library/persons/{person_id}", dependencies=[require_token])
    def get_library_person_detail(person_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            detail = library_module.get_person_detail(session, person_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Person nicht gefunden")
            return dataclasses.asdict(detail)

    @app.get("/library/sources", dependencies=[require_token])
    def list_library_sources(
        search: str | None = Query(default=None),
        limit: int = 200,
        offset: int = 0,
        state: AppState = Depends(get_state),
    ) -> dict:
        with state.db.session() as session:
            total, items = library_module.list_sources(session, search, limit, offset)
            return {"total": total, "items": [dataclasses.asdict(i) for i in items]}

    @app.get("/jobs", dependencies=[require_token])
    def list_jobs(limit: int = 50, state: AppState = Depends(get_state)) -> list[dict]:
        jobs = state.jobs.list_jobs(limit=limit)
        return [job_to_dict(j) for j in jobs]

    @app.get("/jobs/{job_id}", dependencies=[require_token])
    def get_job(job_id: str, state: AppState = Depends(get_state)) -> dict:
        job = state.jobs.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        return job_to_dict(job)

    @app.post("/jobs/{job_id}/pause", dependencies=[require_token])
    def pause_job_endpoint(job_id: str, state: AppState = Depends(get_state)) -> dict:
        """§35/§36 - laengere Batch-Jobs (z.B. Scan & Repair, Stapel-
        Neuberechnung) pruefen diesen Status kooperativ zwischen einzelnen
        Elementen (siehe `JobManager.cooperative_checkpoint`). Deep-Review-
        Fund (Sitzung 11): `pause/resume/cancel` pruefen jetzt serverseitig
        den tatsaechlichen Statusuebergang (`JobTransitionError` -> 409),
        statt den vom Client behaupteten Zustand blind zu uebernehmen -
        verhindert, dass ein bereits beendeter Job faelschlich wieder als
        'laeuft' erscheint."""
        job = state.jobs.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        try:
            state.jobs.pause(job_id)
        except JobTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return job_to_dict(state.jobs.get_job(job_id))

    @app.post("/jobs/{job_id}/resume", dependencies=[require_token])
    def resume_job_endpoint(job_id: str, state: AppState = Depends(get_state)) -> dict:
        job = state.jobs.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        try:
            state.jobs.resume(job_id)
        except JobTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return job_to_dict(state.jobs.get_job(job_id))

    @app.post("/jobs/{job_id}/cancel", dependencies=[require_token])
    def cancel_job_endpoint(job_id: str, state: AppState = Depends(get_state)) -> dict:
        job = state.jobs.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job nicht gefunden")
        try:
            state.jobs.cancel(job_id)
        except JobTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return job_to_dict(state.jobs.get_job(job_id))

    # --- §37 Fehlerbehandlung - zentrales Error-Center ----------------------

    @app.get("/errors", dependencies=[require_token])
    def list_errors_endpoint(
        limit: int = 100, unresolved_only: bool = False, state: AppState = Depends(get_state)
    ) -> dict:
        rows = list_errors(state.db, limit=limit, unresolved_only=unresolved_only)
        return {"errors": [error_log_to_dict(r) for r in rows]}

    @app.post("/errors/{error_id}/resolve", dependencies=[require_token])
    def resolve_error_endpoint(error_id: str, state: AppState = Depends(get_state)) -> dict:
        found = mark_resolved(state.db, error_id)
        if not found:
            raise HTTPException(status_code=404, detail="Error-ID nicht gefunden")
        return {"error_id": error_id, "resolved": True}

    # --- §38 Diagnostics -----------------------------------------------------

    @app.get("/diagnostics", dependencies=[require_token])
    def run_diagnostics_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Rein lesender Gesundheitsbericht (Prinzip #4/#5) - veraendert nichts.
        Eine tatsaechliche Reparatur gefundener Probleme erfolgt ausschliesslich
        ueber /repair/* (§39)."""
        report = run_diagnostics(
            state.db, state.settings,
            ai_provider=state.ai_provider, tts_provider=state.tts_provider,
            download_providers=state.download_providers,
            plugin_registry=state.plugin_registry,
        )
        return diagnostics_report_to_dict(report)

    # --- §54 Log-Viewer (Gap-Analyse Gap J) -----------------------------------

    @app.get("/logs", dependencies=[require_token])
    def get_logs(
        level: str | None = Query(
            default=None,
            description="Mindest-Log-Level (TRACE/DEBUG/INFO/WARNING/ERROR/CRITICAL), §54",
        ),
        component: str | None = Query(
            default=None, description="Teilstring-Filter auf die Komponente, z.B. 'MediaScanner'"
        ),
        search: str | None = Query(default=None, description="Teilstring-Filter auf die Meldung"),
        limit: int = 200,
        offset: int = 0,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Rein lesender Zugriff (Prinzip #4/#5) auf die bereits bestehenden,
        von `configure_logging()` erzeugten Logdateien (aktuell + rotierte
        Backups). Schliesst Gap J: strukturiertes Logging existierte
        bereits, aber es gab weder API noch GUI, um es tatsaechlich
        einzusehen. Neueste Eintraege zuerst, siehe
        `genesis_core.logutil.reader.read_log_entries`.
        """
        total, entries = read_log_entries(
            state.settings.paths.resolved_log_dir(),
            level=level,
            component=component,
            search=search,
            limit=limit,
            offset=offset,
        )
        return {"total": total, "items": [dataclasses.asdict(e) for e in entries]}

    # --- §40 Backup ----------------------------------------------------------

    @app.post("/backup/db", dependencies=[require_token])
    def create_db_backup_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Unkritisch (erzeugt nur eine zusaetzliche Kopie) - braucht keine
        Bestaetigung, im Unterschied zur Wiederherstellung."""
        try:
            result = create_db_backup(state.db, state.settings)
        except BackupError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return backup_result_to_dict(result)

    @app.post("/backup/config", dependencies=[require_token])
    def create_config_backup_endpoint(state: AppState = Depends(get_state)) -> dict:
        try:
            result = create_config_backup(state.db, state.settings)
        except BackupError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return backup_result_to_dict(result)

    @app.get("/backup", dependencies=[require_token])
    def list_backups_endpoint(
        backup_type: str | None = None, limit: int = 50, state: AppState = Depends(get_state)
    ) -> dict:
        rows = list_backups(state.db, backup_type=backup_type, limit=limit)
        return {"backups": [backup_to_dict(b) for b in rows]}

    @app.post("/backup/{backup_id}/restore", dependencies=[require_token])
    def restore_db_backup_endpoint(
        backup_id: int, req: RestoreBackupRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """ECHTE, destruktive Aenderung an der aktiven Datenbank - braucht
        IMMER `confirm=True` (Prinzip #6, §44)."""
        try:
            result = restore_db_backup(
                state.db, state.settings, backup_id, user_confirmed=req.confirm
            )
        except BackupRestoreNotConfirmedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except BackupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "restored_from_backup_id": result.restored_from_backup_id,
            "restored_from_path": result.restored_from_path,
            "pre_restore_backup": backup_result_to_dict(result.pre_restore_backup),
        }

    # --- §39 Scan & Repair -----------------------------------------------------

    @app.get("/repair/plan", dependencies=[require_token])
    def plan_repairs_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Schritt 1 (Erkennen/Analysieren) - rein lesend (Prinzip #4/#5)."""
        plan = plan_repairs(state.db, state.settings)
        return {
            "generated_at": plan.generated_at,
            "items": [dataclasses.asdict(i) for i in plan.items],
        }

    @app.post("/repair/preview", dependencies=[require_token])
    def preview_repairs_endpoint(
        req: RepairPreviewRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Schritt 2 (Vorschau) - loest die ausgewaehlten Plan-Eintraege in
        konkrete betroffene Zeilen/Dateien auf. Rein lesend."""
        plan_items = [
            RepairPlanItem(
                action_type=i.action_type, target=i.target, count=0,
                estimated_bytes=None, description="",
            )
            for i in req.items
        ]
        preview = preview_repairs(state.db, state.settings, plan_items)
        return repair_preview_to_dict(preview)

    @app.post("/repair/execute", dependencies=[require_token])
    def execute_repairs_endpoint(
        req: RepairExecuteRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Schritt 3 (Aenderung + Protokoll) - erfordert IMMER `confirm=True`
        (Prinzip #6, §44). Laeuft als regulaerer, pausier-/abbrechbarer Job
        (§35/§36) mit vorherigem Sicherheits-Backup (§40)."""
        preview = repair_preview_from_request(req)
        job_id = state.jobs.create_job(
            "scan_and_repair", params={"item_count": len(req.items)}
        )
        state.jobs.start(job_id)
        try:
            result = execute_repairs(
                state.db, state.settings, state.jobs, job_id, preview,
                user_confirmed=req.confirm,
            )
        except RepairExecuteNotConfirmedError as exc:
            state.jobs.fail(job_id, str(exc))
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except JobCancelledError as exc:
            state.jobs.cancel(job_id)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        state.jobs.complete(job_id)
        return {
            "job_id": result.job_id,
            "backup": backup_result_to_dict(result.backup),
            "actions": [dataclasses.asdict(a) for a in result.actions],
        }

    # --- §42 Export (JSON/CSV/XML/M3U/M3U8) -----------------------------------

    @app.get("/export", dependencies=[require_token])
    def export_media_endpoint(
        format: Literal["json", "csv", "xml", "m3u", "m3u8"] = Query(default="json"),
        media_file_ids: list[int] | None = Query(default=None),
        extended_playlist: bool = True,
        state: AppState = Depends(get_state),
    ):
        """Rein lesend (Prinzip #4/#5) - kein `confirm` noetig, wie jeder
        andere Export in GENESIS (siehe /media/{id}/chapters/export)."""
        rows = build_export_rows(state.db, media_file_ids=media_file_ids)
        if format == "csv":
            return Response(content=to_csv(rows), media_type="text/csv")
        if format == "xml":
            return Response(content=to_xml(rows), media_type="application/xml")
        if format in ("m3u", "m3u8"):
            media_type = "audio/mpegurl" if format == "m3u" else "application/vnd.apple.mpegurl"
            return Response(content=to_m3u(rows, extended=extended_playlist), media_type=media_type)
        return Response(content=to_json(rows), media_type="application/json")

    # --- §43 Pfad-Relokation ---------------------------------------------------

    @app.post("/relocate/scan", dependencies=[require_token])
    def relocate_scan_endpoint(
        req: RelocateScanRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Schritt 1+2 (Erkennen/Vorschlag) - rein lesend. Durchsucht die
        angegebenen Verzeichnisse nach Dateien, die zu als vermisst
        markierten Mediendateien passen koennten (§43)."""
        candidates = find_relocation_candidates(
            state.db, req.search_roots, use_fingerprint=req.use_fingerprint
        )
        return {"candidates": [dataclasses.asdict(c) for c in candidates]}

    @app.post("/relocate/apply", dependencies=[require_token])
    def relocate_apply_endpoint(
        req: RelocateApplyRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Schritt 3 (Aenderung + Protokoll) - erfordert IMMER `confirm=true`
        (Prinzip #6, §44). Jeder Kandidat wird vor der Uebernahme erneut
        geprueft (Zieldatei muss noch existieren) - keine blinde Ausfuehrung
        einer evtl. veralteten Vorschau."""
        candidates = [
            RelocationCandidate(
                media_file_id=c.media_file_id, old_absolute_path=c.old_absolute_path,
                new_absolute_path=c.new_absolute_path, match_method=c.match_method,
                confidence=c.confidence,
            )
            for c in req.candidates
        ]
        try:
            results = apply_relocations(state.db, candidates, user_confirmed=req.confirm)
        except RelocationApplyNotConfirmedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        job_id = state.jobs.create_job(
            "relocate", params={"candidate_count": len(req.candidates)}
        )
        state.jobs.start(job_id)
        applied_count = 0
        for result in results:
            if result.applied:
                applied_count += 1
            state.jobs.record_history(
                job_id, action="relocate", media_file_id=result.media_file_id,
                before={"absolute_path": result.old_absolute_path},
                after={"absolute_path": result.new_absolute_path} if result.applied else None,
                user_action="Nutzer hat Pfad-Relokations-Vorschlag bestaetigt",
                warning=None if result.applied else result.reason,
            )
        state.jobs.report_progress(job_id, processed_items=applied_count)
        state.jobs.complete(job_id)
        return {
            "job_id": job_id,
            "results": [dataclasses.asdict(r) for r in results],
        }

    # --- §34 Plugin-System -----------------------------------------------------

    @app.get("/plugins", dependencies=[require_token])
    def list_plugins_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Zeigt ALLE beim Start gefundenen Plugins - erfolgreich geladene
        UND fehlgeschlagene (mit `load_error`, sichtbar statt stillschweigend
        ignoriert, §34/§37)."""
        plugins = state.plugin_registry.list_plugins()
        return {"plugins_dir": str(state.plugins_dir), "plugins": [plugin_to_dict(p) for p in plugins]}

    @app.post("/plugins/reload", dependencies=[require_token])
    def reload_plugins_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Unkritisch (laedt nur neu ein, veraendert keine Nutzerdaten) -
        braucht keine Bestaetigung. Nuetzlich, nachdem der Nutzer ein neues
        Plugin in `plugins_dir` abgelegt hat, ohne den Core Service neu
        starten zu muessen."""
        plugins = state.plugin_registry.discover_and_load(state.plugins_dir)
        return {"plugins_dir": str(state.plugins_dir), "plugins": [plugin_to_dict(p) for p in plugins]}

    @app.get("/plugins/export/{plugin_id}", dependencies=[require_token])
    def export_via_plugin_endpoint(
        plugin_id: str, media_file_ids: list[int] | None = Query(default=None),
        state: AppState = Depends(get_state),
    ):
        """Nutzt ein geladenes Exporter-Plugin (§34) anstelle der fest
        eingebauten Formate aus /export (§42). Ein zur Laufzeit
        fehlschlagendes Plugin liefert einen 500 mit Klartextmeldung statt
        den Host mitzureissen (siehe `PluginRegistry.call_exporter`).

        Deep-Review-Fund (Sitzung 11): `file_extension()` wurde bisher nur
        in der Plugin-Schnittstelle definiert, aber nie tatsaechlich
        aufgerufen - der Client bekam immer `text/plain` ohne Dateinamen-
        Vorschlag. `safe_export_filename()` ruft sie jetzt auf, behandelt
        den Rueckgabewert aber genau wie jeden anderen Plugin-Code als
        NICHT vertrauenswuerdig (sanitisiert/validiert, sicherer Fallback
        bei Fehlschlag) - `media_type` bleibt bewusst immer `text/plain`
        (nie z.B. `text/html`), damit ein Plugin niemals aktiven Inhalt im
        Browser-Kontext ausloesen kann, falls der Endpunkt je direkt
        aufgerufen wird."""
        plugin = state.plugin_registry.find_exporter(plugin_id)
        if plugin is None:
            raise HTTPException(status_code=404, detail=f"Exporter-Plugin '{plugin_id}' nicht gefunden.")
        rows = build_export_rows(state.db, media_file_ids=media_file_ids)
        content, error = state.plugin_registry.call_exporter(plugin_id, rows)
        if error is not None:
            raise HTTPException(status_code=500, detail=f"Plugin-Export fehlgeschlagen: {error}")
        filename = state.plugin_registry.safe_export_filename(plugin_id)
        return Response(
            content=content, media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # --- Phase 2: Metadaten-Vorschlaege (§10/§11/§17) -----------------------

    @app.get("/media/{media_id}/metadata-suggestions", dependencies=[require_token])
    def get_metadata_suggestions(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Erkennen -> Vorschlag -> Confidence. Schreibt NICHTS (Prinzip #4/#17)."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            try:
                suggestions = state.metadata_engine.suggest_for_media_file(media_file)
            except ProviderNotConfiguredError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "media_id": media_id,
            "suggestions": [suggestion_to_dict(s) for s in suggestions],
        }

    @app.post(
        "/media/{media_id}/metadata-suggestions/apply", dependencies=[require_token]
    )
    def apply_metadata_suggestion(
        media_id: int, req: ApplyMetadataSuggestionRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Aenderung - erfordert `confirm=true` vom Client, was nur nach echter
        Nutzerbestaetigung in der UI gesetzt werden darf (Prinzip #17, §44)."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine Metadatenuebernahme "
                "braucht eine explizite Nutzerbestaetigung (Prinzip #17).",
            )
        # Deep-Review-Fund (Sitzung 3, F-12): `req.match` kommt vollstaendig
        # vom Client (so wie er ihn zuvor per GET .../metadata-suggestions
        # erhalten hat) und wird NICHT serverseitig gegen eine zwischen-
        # gespeicherte, tatsaechlich generierte Vorschlagsliste abgeglichen.
        # `confirm=true` beweist nur, dass der Nutzer IRGENDETWAS bestaetigt
        # hat - nicht, dass der eingereichte `match` wirklich der zuvor vom
        # Server mit ausreichender Konfidenz generierte Vorschlag ist (z.B.
        # bei einem Client-Bug oder einer manipulierten Anfrage). Als
        # zusaetzliche serverseitige Haertung (Defense-in-Depth, auch wenn
        # das lokale Token bereits vor fremden Angreifern schuetzt) wird der
        # konfigurierte Mindest-Konfidenzwert hier ERNEUT durchgesetzt, statt
        # sich allein auf die Filterung in `suggest_for_media_file` zu
        # verlassen.
        if req.match.confidence < state.settings.metadata.min_confidence_for_suggestion:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Konfidenz {req.match.confidence:.2f} liegt unter dem "
                    f"konfigurierten Mindestwert "
                    f"{state.settings.metadata.min_confidence_for_suggestion:.2f} "
                    "(Einstellungen -> Metadaten) - Uebernahme abgelehnt "
                    "(Prinzip #17)."
                ),
            )
        match = RecordingMatch(**req.match.model_dump())
        suggestion = MetadataSuggestion(
            media_file_id=media_id, match=match, method="api", existing_tags=ExistingTags()
        )
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            existing_track = session.execute(
                select(Track).where(Track.media_file_id == media_id)
            ).scalar_one_or_none()
            before = track_to_dict(existing_track) if existing_track else None
            try:
                track = state.metadata_engine.apply_suggestion(
                    session, media_id, suggestion, user_confirmed=True
                )
            except MetadataApplyNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            after = track_to_dict(track)

        job_id = state.jobs.create_job(
            "metadata_apply", params={"media_file_id": media_id, "provider": match.provider}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="metadata_apply", media_file_id=media_id,
            before=before, after=after, user_action="Nutzer hat Metadatenvorschlag bestaetigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "track": after}

    # --- Phase 2: Umbenennen (§15/§16) ---------------------------------------

    @app.post("/rename/preview", dependencies=[require_token])
    def rename_preview(req: RenamePreviewRequest, state: AppState = Depends(get_state)) -> dict:
        """Rein lesend - berechnet Zielnamen und erkennt Konflikte, veraendert
        nichts (Prinzip #4/#16: Vorschau ist Pflicht vor Massenaenderungen)."""
        try:
            with state.db.session() as session:
                items = preview_renames(session, req.media_file_ids, req.template)
        except RenameTemplateError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"items": [rename_preview_item_to_dict(i) for i in items]}

    @app.post("/rename/apply", dependencies=[require_token])
    def rename_apply(req: RenameApplyRequest, state: AppState = Depends(get_state)) -> dict:
        """Aenderung - erfordert `confirm=true`. Die Vorschau wird HIER erneut
        (serverseitig, gegen den aktuellen Zustand) berechnet statt einer vom
        Client mitgeschickten Vorschau zu vertrauen - vermeidet, dass ein
        zwischenzeitlich veraltetes Vorschau-Ergebnis blind ausgefuehrt wird."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine Umbenennung braucht eine "
                "explizite Nutzerbestaetigung der zuvor gezeigten Vorschau (§16/§44).",
            )
        try:
            with state.db.session() as session:
                items = preview_renames(session, req.media_file_ids, req.template)
                results = apply_renames(session, items, user_confirmed=True)
        except RenameTemplateError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RenameApplyNotConfirmedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RenameBatchFailedError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        job_id = state.jobs.create_job(
            "rename", params={"template": req.template, "media_file_ids": req.media_file_ids}
        )
        state.jobs.start(job_id)
        applied_count = 0
        for result in results:
            if result.applied:
                applied_count += 1
            state.jobs.record_history(
                job_id,
                action="rename",
                media_file_id=result.media_file_id,
                before={"absolute_path": result.old_absolute_path},
                after={"absolute_path": result.new_absolute_path} if result.applied else None,
                user_action="Nutzer hat Umbenennen-Vorschau bestaetigt",
                warning=None if result.applied else result.reason,
            )
        state.jobs.report_progress(job_id, processed_items=applied_count)
        state.jobs.complete(job_id)
        return {"job_id": job_id, "results": [rename_apply_result_to_dict(r) for r in results]}

    # --- Phase 2: Artwork (§22) ----------------------------------------------

    @app.get("/media/{media_id}/artwork", dependencies=[require_token])
    def get_artwork(media_id: int, state: AppState = Depends(get_state)):
        """Liest ausschliesslich bereits eingebettetes Artwork (Prinzip #4/#5).
        404, wenn keins vorhanden ist - kein erfundenes Platzhalterbild."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            path = media_file.absolute_path
        result = extract_embedded_artwork(path)
        if result is None:
            raise HTTPException(status_code=404, detail="Kein eingebettetes Artwork vorhanden")
        data, mime = result
        return Response(content=data, media_type=mime)

    @app.post("/media/{media_id}/artwork/fetch-online", dependencies=[require_token])
    def fetch_artwork_online(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Holt (nur) ein Vorschlags-Cover von Cover Art Archive und legt es im
        GENESIS-eigenen Cache ab - ruehrt die Mediendatei NICHT an (Prinzip
        #4/#5). Das eigentliche Einbetten ist ein separater, bestaetigungs-
        pflichtiger Schritt (siehe /artwork/embed)."""
        if state.providers.coverartarchive is None:
            raise HTTPException(
                status_code=409,
                detail="Cover Art Archive ist deaktiviert (Einstellungen -> Metadaten).",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            track = session.execute(
                select(Track).where(Track.media_file_id == media_id)
            ).scalar_one_or_none()
            album = session.get(Album, track.album_id) if (track and track.album_id) else None
            release_mbid = album.musicbrainz_id if album else None
            if not release_mbid:
                raise HTTPException(
                    status_code=409,
                    detail="Kein bekanntes MusicBrainz-Album fuer dieses Medium - "
                    "zuerst einen Metadatenvorschlag uebernehmen.",
                )
            try:
                fetched = state.providers.coverartarchive.fetch_front_cover(release_mbid)
            except ProviderError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            if fetched is None:
                raise HTTPException(
                    status_code=404, detail="Cover Art Archive hat kein Cover fuer dieses Album."
                )
            data, mime = fetched
            cached_path = cache_artwork(data, mime, state.artwork_cache_dir)

            artwork = Artwork(
                media_file_id=media_id, album_id=track.album_id if track else None,
                file_path=str(cached_path), mime_type=mime, embedded=False,
                source="coverartarchive", status="suggested",
            )
            session.add(artwork)
            session.flush()
            artwork_id = artwork.id
        return {"artwork_id": artwork_id, "cached_path": str(cached_path), "mime_type": mime}

    @app.post("/media/{media_id}/artwork/embed", dependencies=[require_token])
    def embed_artwork_endpoint(
        media_id: int, req: EmbedArtworkRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Aenderung an der Mediendatei selbst - erfordert `confirm=true`
        (Prinzip #17, §44)."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - Artwork-Einbettung veraendert "
                "die Mediendatei und braucht eine explizite Nutzerbestaetigung.",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            artwork = session.get(Artwork, req.artwork_id)
            if media_file is None or artwork is None or artwork.media_file_id != media_id:
                raise HTTPException(status_code=404, detail="Medium oder Artwork nicht gefunden")
            if not artwork.file_path or not Path(artwork.file_path).exists():
                raise HTTPException(status_code=410, detail="Zwischengespeichertes Artwork fehlt")

            data = Path(artwork.file_path).read_bytes()
            # Deep-Review-Fund (Sitzung 3, F-11): frueher wurde der MIME-Typ
            # hier blind aus der Cache-Datei-ENDUNG geraten statt den vom
            # Provider tatsaechlich gelieferten Wert zu verwenden - das
            # konnte z.B. ein PNG als "image/jpeg" fehlkennzeichnen. Fallback
            # auf die alte Rate-Logik nur fuer evtl. aeltere Artwork-Zeilen
            # ohne gespeicherten mime_type (Datenbestand vor diesem Fix).
            mime = artwork.mime_type or (
                "image/png" if artwork.file_path.endswith(".png") else "image/jpeg"
            )
            try:
                embed_artwork(media_file.absolute_path, data, mime, user_confirmed=True)
            except ArtworkError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            artwork.embedded = True
            artwork.status = "embedded"

        job_id = state.jobs.create_job("artwork_embed", params={"media_file_id": media_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="artwork_embed", media_file_id=media_id,
            before={"embedded": False}, after={"embedded": True},
            user_action="Nutzer hat Artwork-Einbettung bestaetigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "embedded": True}

    # --- Phase 3: Loudness-Engine (§19, ADR-0010) ----------------------------

    @app.post("/media/{media_id}/loudness/analyze", dependencies=[require_token])
    def analyze_loudness(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Reine Messung (Integrated LUFS / True Peak / LRA) - veraendert die
        Mediendatei NICHT, braucht daher keine Bestaetigung (Prinzip #4/#5,
        gleiche Risikoklasse wie die automatische ffprobe-Technikanalyse)."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
        try:
            measurement = measure_loudness(absolute_path)
        except LoudnessMeasurementError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with state.db.session() as session:
            row = Loudness(
                media_file_id=media_id,
                integrated_lufs=measurement.integrated_lufs,
                true_peak_dbtp=measurement.true_peak_dbtp,
                loudness_range_lu=measurement.loudness_range_lu,
                normalized=False,
                measured_at=measurement.measured_at,
            )
            session.add(row)
            session.flush()
            loudness_id = row.id
        return {
            "id": loudness_id,
            "media_id": media_id,
            "integrated_lufs": measurement.integrated_lufs,
            "true_peak_dbtp": measurement.true_peak_dbtp,
            "loudness_range_lu": measurement.loudness_range_lu,
            "measured_at": measurement.measured_at.isoformat(),
        }

    @app.get("/media/{media_id}/loudness", dependencies=[require_token])
    def list_loudness(media_id: int, state: AppState = Depends(get_state)) -> list[dict]:
        """Volle Mess-/Normalisierungshistorie, neueste zuerst (§44)."""
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            rows = session.execute(
                select(Loudness)
                .where(Loudness.media_file_id == media_id)
                .order_by(Loudness.measured_at.desc())
            ).scalars().all()
        return [loudness_to_dict(r) for r in rows]

    def _load_media_for_loudness(media_id: int, state: AppState) -> MediaFile:
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            latest = session.execute(
                select(Loudness)
                .where(Loudness.media_file_id == media_id)
                .order_by(Loudness.measured_at.desc())
            ).scalars().first()
            if latest is None or latest.integrated_lufs is None:
                raise HTTPException(
                    status_code=409,
                    detail="Noch keine Loudness-Messung fuer dieses Medium vorhanden - "
                    "zuerst /loudness/analyze aufrufen.",
                )
            # Werte werden hier bewusst aus der SESSION herausgeloest (reine
            # Python-Objekte statt ORM-Instanz), damit sie nach Schliessen der
            # Session (with-Block-Ende) noch sicher verwendbar sind.
            media_file_snapshot = media_file
            measurement_snapshot = LoudnessMeasurementSnapshot(
                integrated_lufs=latest.integrated_lufs,
                true_peak_dbtp=latest.true_peak_dbtp,
                loudness_range_lu=latest.loudness_range_lu or 0.0,
                measured_at=latest.measured_at,
            )
            kind = media_file_snapshot.kind
            absolute_path = media_file_snapshot.absolute_path
        return kind, absolute_path, measurement_snapshot

    @app.post("/media/{media_id}/loudness/normalize/preview", dependencies=[require_token])
    def preview_loudness_normalization(
        media_id: int,
        req: LoudnessNormalizePreviewRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Reine Berechnung - erzeugt KEINE Datei (Prinzip #4/#5)."""
        kind, absolute_path, measurement = _load_media_for_loudness(media_id, state)
        target_lufs = req.target_lufs if req.target_lufs is not None else state.settings.loudness.target_lufs
        target_tp = (
            req.target_true_peak_dbtp
            if req.target_true_peak_dbtp is not None
            else state.settings.loudness.target_true_peak_dbtp
        )
        try:
            plan = plan_normalization(
                media_id, absolute_path, kind, measurement, target_lufs, target_tp, req.target_lra,
            )
        except UnsupportedMediaKindError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return dataclasses.asdict(plan)

    @app.post("/media/{media_id}/loudness/normalize/apply", dependencies=[require_token])
    def apply_loudness_normalization(
        media_id: int,
        req: LoudnessNormalizeApplyRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Aenderung (neue Datei wird erzeugt) - erfordert `confirm=true`
        (Prinzip #17, §44). Das ORIGINAL wird dabei nie veraendert
        (ADR-0010)."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - die Normalisierung erzeugt eine neue "
                "Audiodatei und braucht eine explizite Nutzerbestaetigung.",
            )
        kind, absolute_path, measurement = _load_media_for_loudness(media_id, state)
        target_lufs = req.target_lufs if req.target_lufs is not None else state.settings.loudness.target_lufs
        target_tp = (
            req.target_true_peak_dbtp
            if req.target_true_peak_dbtp is not None
            else state.settings.loudness.target_true_peak_dbtp
        )
        try:
            plan = plan_normalization(
                media_id, absolute_path, kind, measurement, target_lufs, target_tp, req.target_lra,
            )
        except UnsupportedMediaKindError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if plan.has_conflict:
            raise HTTPException(status_code=409, detail=plan.conflict_reason)

        try:
            result = apply_normalization(plan, user_confirmed=True)
        except NormalizationApplyNotConfirmedError as exc:  # pragma: no cover - defensiv
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LoudnessMeasurementError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        measured_at = dt_module.datetime.now(dt_module.UTC)
        with state.db.session() as session:
            row = Loudness(
                media_file_id=media_id,
                integrated_lufs=result.achieved_integrated_lufs,
                true_peak_dbtp=result.achieved_true_peak_dbtp,
                loudness_range_lu=plan.target_lra,
                target_lufs_used=plan.target_lufs,
                target_true_peak_dbtp_used=plan.target_true_peak_dbtp,
                normalized=True,
                normalized_output_path=result.output_path,
                measured_at=measured_at,
            )
            session.add(row)
            session.flush()
            loudness_id = row.id

        job_id = state.jobs.create_job(
            "loudness_normalize", params={"media_file_id": media_id, "output_path": result.output_path}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="loudness_normalize", media_file_id=media_id,
            before={"absolute_path": plan.source_path, "integrated_lufs": plan.measured_integrated_lufs},
            after={"output_path": result.output_path, "integrated_lufs": result.achieved_integrated_lufs},
            user_action="Nutzer hat Loudness-Normalisierung bestaetigt",
            warning="Dynamik wurde angepasst (True-Peak-Begrenzung)"
            if result.used_dynamic_processing else None,
        )
        state.jobs.complete(job_id)
        return {
            "job_id": job_id,
            "loudness_id": loudness_id,
            "output_path": result.output_path,
            "achieved_integrated_lufs": result.achieved_integrated_lufs,
            "achieved_true_peak_dbtp": result.achieved_true_peak_dbtp,
            "used_dynamic_processing": result.used_dynamic_processing,
        }

    # --- Phase 3: Audio-Cutter (§18, ADR-0011) --------------------------------

    @app.get("/media/{media_id}/cutter/waveform", dependencies=[require_token])
    def get_cutter_waveform(media_id: int, state: AppState = Depends(get_state)):
        """Liefert ein Waveform-PNG zur Visualisierung im Cutter-Dialog.
        Rein lesend (Prinzip #4/#5) - erzeugt KEINE DB-Zeile (siehe
        `AudioCut`-Moduldocstring). Wird fuer dieselbe Medien-ID
        wiederverwendet (Cache), solange sie existiert."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path

        cache_path = state.cutter_waveform_dir / f"{media_id}.png"
        if not cache_path.exists():
            state.cutter_waveform_dir.mkdir(parents=True, exist_ok=True)
            try:
                generate_waveform_image(absolute_path, cache_path)
            except WaveformGenerationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        return Response(content=cache_path.read_bytes(), media_type="image/png")

    def _load_media_for_cutter(media_id: int, state: AppState) -> tuple[str, float | None]:
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
            tech = session.execute(
                select(TechnicalMetadata).where(TechnicalMetadata.media_file_id == media_id)
            ).scalars().first()
            known_duration = tech.duration_seconds if tech is not None else None
        return absolute_path, known_duration

    @app.post("/media/{media_id}/cutter/preview", dependencies=[require_token])
    def preview_cut(
        media_id: int,
        req: CutPreviewRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Reine Berechnung - erzeugt KEINE Datei (Prinzip #4/#5)."""
        absolute_path, known_duration = _load_media_for_cutter(media_id, state)
        try:
            plan = plan_cut(
                media_id, absolute_path, req.start_seconds, req.end_seconds, req.export_format,
                fade_in_seconds=req.fade_in_seconds, fade_out_seconds=req.fade_out_seconds,
                source_duration_seconds=known_duration,
            )
        except InvalidCutSelectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:  # unbekanntes Zielformat (spec_for_name)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return dataclasses.asdict(plan)

    @app.post("/media/{media_id}/cutter/apply", dependencies=[require_token])
    def apply_cut_endpoint(
        media_id: int,
        req: CutApplyRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Aenderung (neue Datei wird erzeugt) - erfordert `confirm=true`
        (Prinzip #17, §44). Das ORIGINAL wird dabei nie veraendert
        (ADR-0011)."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - der Schnitt erzeugt eine neue "
                "Audiodatei und braucht eine explizite Nutzerbestaetigung.",
            )
        absolute_path, known_duration = _load_media_for_cutter(media_id, state)
        try:
            plan = plan_cut(
                media_id, absolute_path, req.start_seconds, req.end_seconds, req.export_format,
                fade_in_seconds=req.fade_in_seconds, fade_out_seconds=req.fade_out_seconds,
                source_duration_seconds=known_duration,
            )
        except InvalidCutSelectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if plan.has_conflict:
            raise HTTPException(status_code=409, detail=plan.conflict_reason)

        try:
            result = apply_cut(plan, user_confirmed=True)
        except CutApplyNotConfirmedError as exc:  # pragma: no cover - defensiv
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except CutRenderError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with state.db.session() as session:
            row = AudioCut(
                media_file_id=media_id,
                source_path=plan.source_path,
                output_path=result.output_path,
                start_seconds=result.start_seconds,
                end_seconds=result.end_seconds,
                fade_in_seconds=result.fade_in_seconds,
                fade_out_seconds=result.fade_out_seconds,
                export_format=result.export_format,
            )
            session.add(row)
            session.flush()
            cut_id = row.id

        job_id = state.jobs.create_job(
            "audio_cut", params={"media_file_id": media_id, "output_path": result.output_path}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="audio_cut", media_file_id=media_id,
            before={"absolute_path": plan.source_path},
            after={
                "output_path": result.output_path,
                "start_seconds": result.start_seconds,
                "end_seconds": result.end_seconds,
            },
            user_action="Nutzer hat Audio-Schnitt bestaetigt",
        )
        state.jobs.complete(job_id)
        return {
            "job_id": job_id,
            "cut_id": cut_id,
            "output_path": result.output_path,
            "start_seconds": result.start_seconds,
            "end_seconds": result.end_seconds,
            "export_format": result.export_format,
        }

    @app.get("/media/{media_id}/cutter", dependencies=[require_token])
    def list_cuts(media_id: int, state: AppState = Depends(get_state)) -> list[dict]:
        """Volle Schnitt-Historie, neueste zuerst (§44)."""
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            rows = session.execute(
                select(AudioCut)
                .where(AudioCut.media_file_id == media_id)
                .order_by(AudioCut.created_at.desc())
            ).scalars().all()
        return [cut_to_dict(r) for r in rows]

    # --- Phase 3: Konvertierungs-Werkzeug (nav.convert) -----------------------

    def _load_media_for_convert(media_id: int, state: AppState) -> str:
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            return media_file.absolute_path

    @app.post("/media/{media_id}/convert/preview", dependencies=[require_token])
    def preview_conversion(
        media_id: int,
        req: ConvertPreviewRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Reine Berechnung - erzeugt KEINE Datei (Prinzip #4/#5)."""
        absolute_path = _load_media_for_convert(media_id, state)
        try:
            plan = plan_conversion(media_id, absolute_path, req.target_format, req.bitrate_kbps)
        except InvalidConversionRequestError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return dataclasses.asdict(plan)

    @app.post("/media/{media_id}/convert/apply", dependencies=[require_token])
    def apply_conversion_endpoint(
        media_id: int,
        req: ConvertApplyRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Aenderung (neue Datei wird erzeugt) - erfordert `confirm=true`
        (Prinzip #17, §44). Das ORIGINAL wird dabei nie veraendert."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - die Konvertierung erzeugt eine neue "
                "Datei und braucht eine explizite Nutzerbestaetigung.",
            )
        absolute_path = _load_media_for_convert(media_id, state)
        try:
            plan = plan_conversion(media_id, absolute_path, req.target_format, req.bitrate_kbps)
        except InvalidConversionRequestError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if plan.has_conflict:
            raise HTTPException(status_code=409, detail=plan.conflict_reason)

        try:
            result = apply_conversion(plan, user_confirmed=True)
        except ConversionApplyNotConfirmedError as exc:  # pragma: no cover - defensiv
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ConversionRenderError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with state.db.session() as session:
            row = AudioConversion(
                media_file_id=media_id,
                source_path=plan.source_path,
                output_path=result.output_path,
                source_format=plan.source_format,
                target_format=result.target_format,
                bitrate_kbps=result.bitrate_kbps,
            )
            session.add(row)
            session.flush()
            conversion_id = row.id

        job_id = state.jobs.create_job(
            "audio_convert", params={"media_file_id": media_id, "output_path": result.output_path}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="audio_convert", media_file_id=media_id,
            before={"absolute_path": plan.source_path, "source_format": plan.source_format},
            after={"output_path": result.output_path, "target_format": result.target_format},
            user_action="Nutzer hat Konvertierung bestaetigt",
        )
        state.jobs.complete(job_id)
        return {
            "job_id": job_id,
            "conversion_id": conversion_id,
            "output_path": result.output_path,
            "target_format": result.target_format,
            "bitrate_kbps": result.bitrate_kbps,
        }

    @app.get("/media/{media_id}/convert", dependencies=[require_token])
    def list_conversions(media_id: int, state: AppState = Depends(get_state)) -> list[dict]:
        """Volle Konvertierungs-Historie, neueste zuerst (§44)."""
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            rows = session.execute(
                select(AudioConversion)
                .where(AudioConversion.media_file_id == media_id)
                .order_by(AudioConversion.created_at.desc())
            ).scalars().all()
        return [conversion_to_dict(r) for r in rows]

    # --- Phase 3: Audio-Fingerprinting (Vorstufe fuer §21/AcoustID) -----------
    #
    # Bisher wurde `compute_fingerprint()` nur TRANSIENT innerhalb der
    # Metadaten-Vorschlagsengine (AcoustID-Abgleich) aufgerufen, ohne das
    # Ergebnis zu speichern (siehe genesis_core/metadata/engine.py). Fuer die
    # Duplikaterkennungs-Stufe 5 (§21) wird ein PERSISTIERTER Fingerprint
    # benoetigt - dieser Endpunkt berechnet ihn explizit und legt ihn in der
    # `fingerprints`-Tabelle ab (Analyse, kein `confirm` noetig - es wird
    # keine Mediendatei veraendert, nur ein technischer Wert ermittelt).

    @app.post("/media/{media_id}/fingerprint", dependencies=[require_token])
    def compute_and_store_fingerprint(media_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path

        try:
            result = compute_fingerprint(absolute_path)
        except FingerprintError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with state.db.session() as session:
            existing = session.execute(
                select(Fingerprint)
                .where(Fingerprint.media_file_id == media_id)
                .where(Fingerprint.algorithm == result.algorithm)
            ).scalars().first()
            if existing is not None:
                existing.fingerprint_data = result.fingerprint_data
                existing.duration_seconds = result.duration_seconds
            else:
                session.add(
                    Fingerprint(
                        media_file_id=media_id, algorithm=result.algorithm,
                        fingerprint_data=result.fingerprint_data,
                        duration_seconds=result.duration_seconds,
                    )
                )
            session.flush()
        return {
            "media_file_id": media_id,
            "algorithm": result.algorithm,
            "duration_seconds": result.duration_seconds,
        }

    @app.get("/media/{media_id}/fingerprint", dependencies=[require_token])
    def get_fingerprint(media_id: int, state: AppState = Depends(get_state)) -> dict | None:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            row = session.execute(
                select(Fingerprint)
                .where(Fingerprint.media_file_id == media_id)
                .order_by(Fingerprint.created_at.desc())
            ).scalars().first()
            if row is None:
                return None
            return {
                "media_file_id": media_id,
                "algorithm": row.algorithm,
                "duration_seconds": row.duration_seconds,
            }

    # --- Phase 3: Duplikaterkennung (§21, ADR-0013) ---------------------------

    @app.post("/duplicates/scan", dependencies=[require_token])
    def scan_duplicates(
        req: DuplicateScanRequest,
        state: AppState = Depends(get_state),
    ) -> list[dict]:
        """Reine Analyse (Prinzip #4/#5) - erzeugt/veraendert/loescht KEINE
        Mediendatei. Ersetzt alle noch NICHT ueberprueften Gruppen durch die
        frisch erkannten; bereits ueberprueft/verworfene Gruppen
        (`reviewed=True`) bleiben unangetastet (siehe DuplicateGroup-Docstring).
        """
        with state.db.session() as session:
            query = select(MediaFile).where(MediaFile.is_missing.is_(False))
            if req.kind:
                try:
                    query = query.where(MediaFile.kind == MediaKind(req.kind))
                except ValueError as exc:
                    raise HTTPException(
                        status_code=422, detail=f"Unbekannte Medienart: {req.kind}"
                    ) from exc
            media_files = session.execute(query).scalars().all()

            snapshots: list[MediaSnapshot] = []
            for mf in media_files:
                technical = mf.technical
                fingerprint_row = session.execute(
                    select(Fingerprint)
                    .where(Fingerprint.media_file_id == mf.id)
                    .where(Fingerprint.algorithm == "chromaprint")
                    .order_by(Fingerprint.created_at.desc())
                ).scalars().first()
                track = mf.tracks[0] if mf.tracks else None
                album_title = None
                if track is not None and track.album_id is not None:
                    album = session.get(Album, track.album_id)
                    album_title = album.title if album else None

                snapshots.append(
                    MediaSnapshot(
                        media_file_id=mf.id,
                        absolute_path=mf.absolute_path,
                        size_bytes=mf.size_bytes,
                        content_hash_sha256=mf.content_hash_sha256,
                        duration_seconds=technical.duration_seconds if technical else None,
                        audio_codec=technical.audio_codec if technical else None,
                        sample_rate_hz=technical.sample_rate_hz if technical else None,
                        channels=technical.channels if technical else None,
                        fingerprint=fingerprint_row.fingerprint_data if fingerprint_row else None,
                        title=track.title if track else None,
                        artist=track.album_artist if track else None,
                        album=album_title,
                    )
                )

            candidates = find_duplicate_candidates(snapshots)

            # Bereits ueberpruefte Gruppen (reviewed=True) unangetastet lassen;
            # alles andere wird durch den frischen Scan ersetzt (siehe oben).
            stale_groups = session.execute(
                select(DuplicateGroup).where(DuplicateGroup.reviewed.is_(False))
            ).scalars().all()
            for group in stale_groups:
                session.delete(group)
            session.flush()

            created_groups: list[DuplicateGroup] = []
            for candidate in candidates:
                group = DuplicateGroup(
                    category=candidate.category.value,
                    confidence=candidate.confidence,
                    matched_stages_json=candidate.matched_stages,
                    reason=candidate.reason,
                    reviewed=False,
                )
                session.add(group)
                session.flush()
                session.add(DuplicateGroupMember(duplicate_group_id=group.id, media_file_id=candidate.media_file_id_a))
                session.add(DuplicateGroupMember(duplicate_group_id=group.id, media_file_id=candidate.media_file_id_b))
                created_groups.append(group)
            session.flush()
            result = [duplicate_group_to_dict(g) for g in created_groups]

        job_id = state.jobs.create_job(
            "duplicate_scan", params={"kind": req.kind, "scanned_files": len(snapshots)}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="duplicate_scan", media_file_id=None,
            before=None,
            after={"groups_found": len(result)},
            user_action="Automatischer Duplikat-Scan (reine Analyse, keine Dateiaenderung)",
        )
        state.jobs.complete(job_id)
        return result

    @app.get("/duplicates", dependencies=[require_token])
    def list_duplicates(
        reviewed: bool | None = Query(default=None),
        state: AppState = Depends(get_state),
    ) -> list[dict]:
        with state.db.session() as session:
            query = select(DuplicateGroup).order_by(DuplicateGroup.confidence.desc())
            if reviewed is not None:
                query = query.where(DuplicateGroup.reviewed.is_(reviewed))
            groups = session.execute(query).scalars().all()
            return [duplicate_group_to_dict(g) for g in groups]

    @app.post("/duplicates/{group_id}/review", dependencies=[require_token])
    def review_duplicate_group(group_id: int, state: AppState = Depends(get_state)) -> dict:
        """Markiert eine Gruppe als ueberprueft/verworfen - rein organisatorisch,
        veraendert KEINE Mediendatei und ist jederzeit per `/unreview`
        rueckgaengig zu machen (daher ohne `confirm`-Pflicht, anders als
        tatsaechliche Dateiaenderungen)."""
        with state.db.session() as session:
            group = session.get(DuplicateGroup, group_id)
            if group is None:
                raise HTTPException(status_code=404, detail="Duplikatgruppe nicht gefunden")
            group.reviewed = True
            session.flush()
            return duplicate_group_to_dict(group)

    @app.post("/duplicates/{group_id}/unreview", dependencies=[require_token])
    def unreview_duplicate_group(group_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            group = session.get(DuplicateGroup, group_id)
            if group is None:
                raise HTTPException(status_code=404, detail="Duplikatgruppe nicht gefunden")
            group.reviewed = False
            session.flush()
            return duplicate_group_to_dict(group)

    # --- Phase 3: Qualitätsanalyse (§20, ADR-0014) -----------------------------

    @app.post("/media/{media_id}/quality/analyze", dependencies=[require_token])
    def analyze_quality_endpoint(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Reine Interpretation bereits vorhandener Daten (Prinzip #4/#5) -
        verändert/löscht KEINE Mediendatei, kein `confirm` nötig (wie
        `/loudness/analyze`). Ergebnis ist immer ein VERDACHT, niemals ein
        Fakt (§20) - siehe genesis_core/quality/engine.py."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            technical = media_file.technical
            if technical is None:
                raise HTTPException(
                    status_code=422,
                    detail="Noch keine technische Analyse vorhanden - zuerst einen Scan "
                    "durchführen.",
                )
            track = media_file.tracks[0] if media_file.tracks else None
            latest_loudness = session.execute(
                select(Loudness)
                .where(Loudness.media_file_id == media_id)
                .order_by(Loudness.created_at.desc())
            ).scalars().first()

            snapshot = QualitySnapshot(
                media_file_id=media_id,
                extension=media_file.extension,
                container_format=technical.container_format,
                audio_codec=technical.audio_codec,
                bitrate_kbps=technical.bitrate_kbps,
                sample_rate_hz=technical.sample_rate_hz,
                bit_depth=technical.bit_depth,
                channels=technical.channels,
                duration_seconds=technical.duration_seconds,
                tag_duration_seconds=track.duration_seconds if track else None,
                size_bytes=media_file.size_bytes,
                last_scan_error=media_file.last_scan_error,
                integrated_lufs=latest_loudness.integrated_lufs if latest_loudness else None,
                true_peak_dbtp=latest_loudness.true_peak_dbtp if latest_loudness else None,
            )
            report = analyze_quality(snapshot)

            technical.suspected_upscale = report.suspected_upscale
            technical.suspected_transcode = report.suspected_transcode
            technical.suspected_corruption = report.suspected_corruption
            technical.suspected_truncation = report.suspected_truncation
            technical.quality_notes = "\n".join(report.notes)
            session.flush()

        return dataclasses.asdict(report)

    @app.get("/media/{media_id}/quality", dependencies=[require_token])
    def get_quality(media_id: int, state: AppState = Depends(get_state)) -> dict | None:
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            technical = media_file.technical
            if technical is None or technical.quality_notes is None:
                return None
            return {
                "media_file_id": media_id,
                "suspected_upscale": technical.suspected_upscale,
                "suspected_transcode": technical.suspected_transcode,
                "suspected_corruption": technical.suspected_corruption,
                "suspected_truncation": technical.suspected_truncation,
                "notes": technical.quality_notes.split("\n"),
            }

    # --- Phase 4: Hörbücher & Kapitel (§23, ADR-0015) --------------------------
    #
    # Bewusst OHNE Online-Provider (Audible/OpenLibrary etc. sind
    # Download/Import-Adapter, Phase 8) - siehe Moduldocstring in
    # genesis_core/audiobook/engine.py. Erkennen->Vorschlag->Bestaetigung-
    # Fluss analog zur MetadataEngine (Prinzip #17).

    @app.get("/media/{media_id}/audiobook/tags", dependencies=[require_token])
    def get_audiobook_tags_preview(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Vorschau - liest bereits eingebettete Tags, schreibt NICHTS."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
        snapshot = read_audiobook_tags(absolute_path)
        return dataclasses.asdict(snapshot)

    @app.post("/media/{media_id}/audiobook/tags/apply", dependencies=[require_token])
    def apply_audiobook_tags_endpoint(
        media_id: int, req: ApplyAudiobookTagsRequest, state: AppState = Depends(get_state)
    ) -> dict:
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine Hörbuch-Metadatenübernahme "
                "braucht eine explizite Nutzerbestätigung (Prinzip #17).",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
            snapshot = read_audiobook_tags(absolute_path)
            existing = session.execute(
                select(Audiobook).where(Audiobook.media_file_id == media_id)
            ).scalar_one_or_none()
            before = audiobook_to_dict(existing) if existing else None
            try:
                audiobook = apply_audiobook_tags(session, media_id, snapshot, user_confirmed=True)
            except AudiobookApplyNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            after = audiobook_to_dict(audiobook)

        job_id = state.jobs.create_job("audiobook_tags_apply", params={"media_file_id": media_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="audiobook_tags_apply", media_file_id=media_id,
            before=before, after=after,
            user_action="Nutzer hat Hörbuch-Tag-Übernahme bestätigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "audiobook": after}

    @app.get("/media/{media_id}/audiobook", dependencies=[require_token])
    def get_audiobook(media_id: int, state: AppState = Depends(get_state)) -> dict | None:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            row = session.execute(
                select(Audiobook).where(Audiobook.media_file_id == media_id)
            ).scalar_one_or_none()
            return audiobook_to_dict(row) if row else None

    @app.get("/media/{media_id}/chapters", dependencies=[require_token])
    def list_chapters(media_id: int, state: AppState = Depends(get_state)) -> list[dict]:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            rows = session.execute(
                select(Chapter).where(Chapter.media_file_id == media_id).order_by(Chapter.index)
            ).scalars().all()
            return [chapter_to_dict(r) for r in rows]

    @app.post("/media/{media_id}/chapters/detect", dependencies=[require_token])
    def detect_chapters_preview(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Vorschau - liest bereits eingebettete Kapitelmarken, schreibt NICHTS."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
        try:
            candidates = detect_chapters(absolute_path)
        except ChapterDetectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "media_id": media_id,
            "candidates": [dataclasses.asdict(c) for c in candidates],
        }

    @app.post("/media/{media_id}/chapters/detect/apply", dependencies=[require_token])
    def detect_chapters_apply(
        media_id: int, req: DetectChaptersApplyRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Ersetzt ALLE bestehenden Kapitel durch die frisch erkannten -
        erfordert `confirm=true` (Prinzip #17, §44)."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - das Übernehmen erkannter Kapitel "
                "ersetzt bestehende Kapitel und braucht eine explizite "
                "Nutzerbestätigung (Prinzip #17).",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
            try:
                candidates = detect_chapters(absolute_path)
            except ChapterDetectionError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            rows = replace_chapters(session, media_id, candidates)
            result = [chapter_to_dict(r) for r in rows]

        job_id = state.jobs.create_job(
            "chapters_detect_apply", params={"media_file_id": media_id, "count": len(result)}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="chapters_detect_apply", media_file_id=media_id,
            before=None, after={"chapters": result},
            user_action="Nutzer hat erkannte Kapitel übernommen",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "chapters": result}

    @app.post("/media/{media_id}/chapters/generate", dependencies=[require_token])
    def generate_chapters_preview(
        media_id: int, req: GenerateChaptersRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Vorschau - reine Berechnung GLEICHMAESSIGER Intervall-Kapitel,
        schreibt NICHTS (siehe Moduldocstring audiobook/engine.py)."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            technical = media_file.technical
            if technical is None or not technical.duration_seconds:
                raise HTTPException(
                    status_code=422,
                    detail="Keine bekannte Dauer vorhanden - zuerst einen Scan durchführen.",
                )
            duration_seconds = technical.duration_seconds
        try:
            candidates = generate_fixed_interval_chapters(duration_seconds, req.interval_minutes)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "media_id": media_id,
            "candidates": [dataclasses.asdict(c) for c in candidates],
        }

    @app.post("/media/{media_id}/chapters/generate/apply", dependencies=[require_token])
    def generate_chapters_apply(
        media_id: int, req: GenerateChaptersApplyRequest, state: AppState = Depends(get_state)
    ) -> dict:
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - das Erzeugen von Intervall-Kapiteln "
                "ersetzt bestehende Kapitel und braucht eine explizite "
                "Nutzerbestätigung (Prinzip #17).",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            technical = media_file.technical
            if technical is None or not technical.duration_seconds:
                raise HTTPException(
                    status_code=422,
                    detail="Keine bekannte Dauer vorhanden - zuerst einen Scan durchführen.",
                )
            try:
                candidates = generate_fixed_interval_chapters(
                    technical.duration_seconds, req.interval_minutes
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            rows = replace_chapters(session, media_id, candidates)
            result = [chapter_to_dict(r) for r in rows]

        job_id = state.jobs.create_job(
            "chapters_generate_apply",
            params={"media_file_id": media_id, "interval_minutes": req.interval_minutes},
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="chapters_generate_apply", media_file_id=media_id,
            before=None, after={"chapters": result},
            user_action=f"Nutzer hat Intervall-Kapitel ({req.interval_minutes} Min.) übernommen",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "chapters": result}

    @app.patch("/media/{media_id}/chapters/{chapter_id}", dependencies=[require_token])
    def rename_chapter(
        media_id: int, chapter_id: int, req: RenameChapterRequest,
        state: AppState = Depends(get_state),
    ) -> dict:
        """Einfacher Titel-Edit - geht trotzdem durch das Bestaetigungsmuster
        (Prinzip #17) fuer Konsistenz mit dem projektweiten Sicherheitsmodell."""
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - Kapitel umbenennen braucht eine "
                "explizite Nutzerbestätigung (Prinzip #17).",
            )
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            chapter = session.get(Chapter, chapter_id)
            if chapter is None or chapter.media_file_id != media_id:
                raise HTTPException(status_code=404, detail="Kapitel nicht gefunden")
            before = chapter_to_dict(chapter)
            chapter.title = req.title
            session.flush()
            after = chapter_to_dict(chapter)

        job_id = state.jobs.create_job(
            "chapter_rename", params={"media_file_id": media_id, "chapter_id": chapter_id}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="chapter_rename", media_file_id=media_id,
            before=before, after=after,
            user_action=f"Nutzer hat Kapitel {chapter_id} umbenannt",
        )
        state.jobs.complete(job_id)
        return after

    @app.get("/media/{media_id}/chapters/export", dependencies=[require_token])
    def export_chapters(
        media_id: int, format: Literal["json", "csv"] = Query(default="json"),
        state: AppState = Depends(get_state),
    ):
        """Reine Lesefunktion - kein `confirm` nötig (wie andere Exporte)."""
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            rows = session.execute(
                select(Chapter).where(Chapter.media_file_id == media_id).order_by(Chapter.index)
            ).scalars().all()
            if format == "csv":
                content = export_chapters_csv(rows)
                return Response(content=content, media_type="text/csv")
            content = export_chapters_json(rows)
            return Response(content=content, media_type="application/json")

    # --- Phase 5: Filme & Serien (§24, ADR-0016) --------------------------------
    #
    # Bewusst OHNE Online-Provider (TMDb/IMDb/OMDb etc. sind
    # Download/Import-Adapter, Phase 8) - siehe Moduldocstring in
    # genesis_core/video/engine.py. Der Scanner klassifiziert ALLE
    # Video-Dateien zunaechst konservativ als MediaKind.MOVIE (siehe
    # scanner/classify.py); die eigentliche Film-/Serien-Unterscheidung
    # erfolgt erst hier, ueber einen Erkennen->Vorschlag->Bestaetigung-Fluss.

    @app.get("/media/{media_id}/video/tags", dependencies=[require_token])
    def get_video_tags_preview(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Vorschau - liest bereits eingebettete Tags, schreibt NICHTS."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
        snapshot = read_video_tags(absolute_path)
        return dataclasses.asdict(snapshot)

    @app.post("/media/{media_id}/video/episode-detection", dependencies=[require_token])
    def detect_episode_preview(media_id: int, state: AppState = Depends(get_state)) -> dict:
        """Vorschau - Film vs. Serie-Episode-Erkennung (Tags + Dateipfad-
        Muster), schreibt NICHTS."""
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
        result = detect_episode(absolute_path)
        return dataclasses.asdict(result)

    @app.post("/media/{media_id}/movie/apply", dependencies=[require_token])
    def apply_movie_metadata_endpoint(
        media_id: int, req: ApplyVideoMetadataRequest, state: AppState = Depends(get_state)
    ) -> dict:
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine Film-Metadatenübernahme "
                "braucht eine explizite Nutzerbestätigung (Prinzip #17).",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
            snapshot = read_video_tags(absolute_path)
            try:
                movie = apply_movie_metadata(session, media_id, snapshot, user_confirmed=True)
            except VideoApplyNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            after = movie_to_dict(session, movie)

        job_id = state.jobs.create_job("movie_apply", params={"media_file_id": media_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="movie_apply", media_file_id=media_id,
            before=None, after=after, user_action="Nutzer hat Film-Metadatenübernahme bestätigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "movie": after}

    @app.get("/media/{media_id}/movie", dependencies=[require_token])
    def get_movie(media_id: int, state: AppState = Depends(get_state)) -> dict | None:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            row = session.execute(
                select(Movie).where(Movie.media_file_id == media_id)
            ).scalar_one_or_none()
            return movie_to_dict(session, row) if row else None

    @app.post("/media/{media_id}/episode/apply", dependencies=[require_token])
    def apply_episode_metadata_endpoint(
        media_id: int, req: ApplyVideoMetadataRequest, state: AppState = Depends(get_state)
    ) -> dict:
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine Episoden-Metadatenübernahme "
                "braucht eine explizite Nutzerbestätigung (Prinzip #17).",
            )
        with state.db.session() as session:
            media_file = session.get(MediaFile, media_id)
            if media_file is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            absolute_path = media_file.absolute_path
            result = detect_episode(absolute_path)
            try:
                episode = apply_episode_metadata(session, media_id, result, user_confirmed=True)
            except VideoApplyNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            after = episode_to_dict(session, episode)

        job_id = state.jobs.create_job("episode_apply", params={"media_file_id": media_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="episode_apply", media_file_id=media_id,
            before=None, after=after,
            user_action="Nutzer hat Episoden-Metadatenübernahme bestätigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "episode": after}

    @app.get("/media/{media_id}/episode", dependencies=[require_token])
    def get_episode(media_id: int, state: AppState = Depends(get_state)) -> dict | None:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            row = session.execute(
                select(Episode).where(Episode.media_file_id == media_id)
            ).scalar_one_or_none()
            return episode_to_dict(session, row) if row else None

    # -----------------------------------------------------------------
    # KI-Metadaten (§25, ADR-0017) - Erkennen->Vorschlag->Confidence hier,
    # Bestaetigung+Speicherung ueber /apply. NullAIProvider (Standard,
    # ai.enabled=False) liefert immer leere Vorschlagslisten (§56).
    # -----------------------------------------------------------------

    @app.post("/media/{media_id}/ai/suggest", dependencies=[require_token])
    def ai_suggest_endpoint(
        media_id: int, req: AISuggestRequest, state: AppState = Depends(get_state)
    ) -> list[dict]:
        with state.db.session() as session:
            try:
                suggestions = ai_suggest_metadata(
                    session, media_id, state.ai_provider, fields=req.fields
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return [dataclasses.asdict(s) for s in suggestions]

    @app.post("/media/{media_id}/ai/apply", dependencies=[require_token])
    def ai_apply_endpoint(
        media_id: int, req: AIApplyRequest, state: AppState = Depends(get_state)
    ) -> dict:
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine KI-Metadatenübernahme "
                "braucht eine explizite Nutzerbestätigung (Prinzip #17).",
            )
        accepted = [
            AISuggestion(
                field_name=a.field_name, field_value=a.field_value, model_name=a.model_name,
                model_version=a.model_version, confidence=a.confidence, prompt=a.prompt,
            )
            for a in req.accepted
        ]
        with state.db.session() as session:
            try:
                saved = ai_apply_suggestions(session, media_id, accepted, confirm=True)
            except AIApplyNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            after = [ai_metadata_to_dict(e) for e in saved]

        job_id = state.jobs.create_job("ai_metadata_apply", params={"media_file_id": media_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="ai_metadata_apply", media_file_id=media_id,
            before=None, after={"entries": after},
            user_action="Nutzer hat KI-Metadatenübernahme bestätigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "entries": after}

    @app.get("/media/{media_id}/ai/metadata", dependencies=[require_token])
    def ai_metadata_endpoint(media_id: int, state: AppState = Depends(get_state)) -> list[dict]:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            return [ai_metadata_to_dict(e) for e in list_ai_metadata(session, media_id)]

    @app.get("/ai/status", dependencies=[require_token])
    def ai_status_endpoint(state: AppState = Depends(get_state)) -> dict:
        """Transparenz ueber den aktuell aktiven KI-Provider (Prinzip #9) -
        Engine, lokal/offline-Status und Erreichbarkeit."""
        return {
            "enabled": state.settings.ai.enabled,
            "provider": state.ai_provider.name,
            "is_local": state.ai_provider.is_local,
            "requires_internet": state.ai_provider.requires_internet,
            "available": state.ai_provider.is_available(),
            "model": state.settings.ai.model,
            "embedding_model": state.settings.ai.embedding_model,
        }

    # -----------------------------------------------------------------
    # KI-Musik-Provenienz (§27, ADR-0017) - IMMER manuelle Nutzerangabe.
    # -----------------------------------------------------------------

    @app.get("/media/{media_id}/ai-music", dependencies=[require_token])
    def get_ai_music_endpoint(media_id: int, state: AppState = Depends(get_state)) -> dict | None:
        with state.db.session() as session:
            if session.get(MediaFile, media_id) is None:
                raise HTTPException(status_code=404, detail="Medium nicht gefunden")
            track = get_ai_music_provenance(session, media_id)
            return ai_music_to_dict(session, track) if track else None

    @app.post("/media/{media_id}/ai-music/apply", dependencies=[require_token])
    def apply_ai_music_endpoint(
        media_id: int, req: AIMusicApplyRequest, state: AppState = Depends(get_state)
    ) -> dict:
        if not req.confirm:
            raise HTTPException(
                status_code=422,
                detail="confirm=true erforderlich - eine KI-Musik-Angabe braucht eine "
                "explizite Nutzerbestätigung (Prinzip #17).",
            )
        data = AIMusicProvenanceInput(
            status=AIStatus(req.status), source=req.source, model=req.model, prompt=req.prompt,
            creation_date=req.creation_date, instrumental=req.instrumental, style=req.style,
            mood=req.mood, owner=req.owner, artist_name=req.artist_name,
        )
        with state.db.session() as session:
            try:
                track = apply_ai_music_provenance(session, media_id, data, confirm=True)
            except AIMusicApplyNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            after = ai_music_to_dict(session, track)

        job_id = state.jobs.create_job("ai_music_apply", params={"media_file_id": media_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="ai_music_apply", media_file_id=media_id,
            before=None, after=after,
            user_action="Nutzer hat KI-Musik-Herkunft bestätigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "track": after}

    # -----------------------------------------------------------------
    # Lokale semantische Suche (§26, ADR-0017) - Brute-Force-Kosinus-
    # Aehnlichkeit ueber zwischengespeicherte Embeddings. Reindex ist eine
    # additive Cache-Operation (kein confirm noetig, Prinzip #17 gilt fuer
    # Metadatenaenderungen, nicht fuer einen reinen Suchindex).
    # -----------------------------------------------------------------

    @app.post("/ai/search/reindex", dependencies=[require_token])
    def ai_reindex_endpoint(state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            stats = reindex_all(session, state.ai_provider)
        job_id = state.jobs.create_job("ai_search_reindex", params=stats)
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="ai_search_reindex", media_file_id=None,
            before=None, after=stats, user_action="Automatischer KI-Suchindex-Reindex",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, **stats}

    @app.post("/ai/search", dependencies=[require_token])
    def ai_search_endpoint(req: AISearchRequest, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            results = semantic_search(session, state.ai_provider, req.query, top_k=req.top_k)
            return {
                "available": state.ai_provider.is_available(),
                "results": [dataclasses.asdict(r) for r in results],
            }

    # -----------------------------------------------------------------
    # Voice Studio (§28/§29, ADR-0018) - lokale TTS-Engine, Profilverwaltung,
    # Sprachsynthese. Dieselben Endpunkte sind zugleich die lokale
    # "GENESIS Voice API" fuer ANDERE lokale Anwendungen (§29) - siehe
    # scripts/genesis_voice_cli.py fuer ein konkretes Beispiel eines
    # externen Konsumenten (Architektur: Andere Anwendung -> diese API ->
    # Voice Engine -> Audio).
    # -----------------------------------------------------------------

    @app.get("/voice/status", dependencies=[require_token])
    def voice_status_endpoint(state: AppState = Depends(get_state)) -> dict:
        """§28 Transparenzpflicht auf Engine-Ebene (Welche Engine? Offline?
        Open Source?). Lizenz-/Kommerz-Angaben sind PRO PROFIL unter
        `/voice/profiles` zu finden (eine Engine kann mehrere Modelle mit
        unterschiedlichen Modell-Lizenzen bedienen, siehe ADR-0018)."""
        return {
            "enabled": state.settings.voice.enabled,
            "provider": state.tts_provider.name,
            "is_local": state.tts_provider.is_local,
            "requires_internet": state.tts_provider.requires_internet,
            "available": state.tts_provider.is_available(),
        }

    @app.get("/voice/engines", dependencies=[require_token])
    def voice_engines_endpoint() -> dict:
        """Nur-lesender Katalog bekannter Engines mit UNVERBINDLICHEN
        Vorschlagswerten fuers Anlage-Formular (Prinzip #9/#17) - siehe
        `genesis_core.voice.catalog`."""
        return {
            "engines": [
                {
                    "id": e.id,
                    "label": e.label,
                    "is_local": e.is_local,
                    "requires_internet": e.requires_internet,
                    "suggested_engine_license": e.suggested_engine_license,
                    "homepage": e.homepage,
                    "notes": e.notes,
                }
                for e in ENGINE_CATALOG
            ]
        }

    @app.get("/voice/profiles", dependencies=[require_token])
    def list_voice_profiles_endpoint(state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            return {"profiles": [voice_profile_to_dict(p) for p in list_voice_profiles(session)]}

    @app.post("/voice/profiles", dependencies=[require_token])
    def create_voice_profile_endpoint(
        req: CreateVoiceProfileRequest, state: AppState = Depends(get_state)
    ) -> dict:
        data = VoiceProfileInput(
            name=req.name, engine=req.engine, model_path=req.model_path,
            language=req.language, description=req.description,
            model_license=req.model_license, offline_capable=req.offline_capable,
            open_source=req.open_source, commercial_use_allowed=req.commercial_use_allowed,
            sample_path=req.sample_path,
        )
        with state.db.session() as session:
            try:
                profile = create_voice_profile(session, data, confirm=req.confirm)
            except VoiceApplyNotConfirmedError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            after = voice_profile_to_dict(profile)

        job_id = state.jobs.create_job("voice_profile_create", params={"name": req.name})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="voice_profile_create", media_file_id=None,
            before=None, after=after, user_action="Nutzer hat Voice-Profil angelegt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "profile": after}

    @app.get("/voice/profiles/{profile_id}", dependencies=[require_token])
    def get_voice_profile_endpoint(profile_id: int, state: AppState = Depends(get_state)) -> dict:
        with state.db.session() as session:
            profile = session.get(VoiceProfile, profile_id)
            if profile is None:
                raise HTTPException(status_code=404, detail="Voice-Profil nicht gefunden")
            return voice_profile_to_dict(profile)

    @app.delete("/voice/profiles/{profile_id}", dependencies=[require_token])
    def delete_voice_profile_endpoint(
        profile_id: int, req: DeleteVoiceProfileRequest, state: AppState = Depends(get_state)
    ) -> dict:
        with state.db.session() as session:
            profile = session.get(VoiceProfile, profile_id)
            before = voice_profile_to_dict(profile) if profile else None
            try:
                delete_voice_profile(
                    session, profile_id, confirm=req.confirm, confirm_name=req.confirm_name
                )
            except VoiceProfileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except VoiceApplyNotConfirmedError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except VoiceDeleteNotConfirmedError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

        job_id = state.jobs.create_job("voice_profile_delete", params={"profile_id": profile_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="voice_profile_delete", media_file_id=None,
            before=before, after=None, user_action="Nutzer hat Voice-Profil geloescht",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id}

    @app.post("/voice/profiles/{profile_id}/synthesize", dependencies=[require_token])
    def synthesize_voice_endpoint(
        profile_id: int, req: VoiceSynthesizeRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """Aenderung (neue Datei wird erzeugt) - erfordert `confirm=true`
        (Prinzip #17, §44). Keine Sprachdaten verlassen dabei jemals den
        lokalen Rechner (§28, §56)."""
        with state.db.session() as session:
            try:
                row = synthesize_text(
                    session, state.tts_provider, profile_id, req.text,
                    output_dir=state.voice_output_dir, export_format=req.export_format,
                    confirm=req.confirm,
                )
            except VoiceApplyNotConfirmedError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except VoiceProfileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except TTSProviderUnavailableError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except (VoiceSynthesisError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            after = voice_synthesis_to_dict(row)

        job_id = state.jobs.create_job(
            "voice_synthesize", params={"profile_id": profile_id, "export_format": req.export_format}
        )
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="voice_synthesize", media_file_id=None,
            before=None, after=after, user_action="Nutzer hat Sprachsynthese bestaetigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "synthesis": after}

    @app.post("/voice/profiles/{profile_id}/test", dependencies=[require_token])
    def test_voice_profile_endpoint(
        profile_id: int, req: VoiceTestRequest, state: AppState = Depends(get_state)
    ) -> dict:
        """§28 "Voice Profile testen" - synthetisiert einen festen,
        kurzen Testsatz in der Profilsprache (Default Englisch)."""
        with state.db.session() as session:
            profile = session.get(VoiceProfile, profile_id)
            if profile is None:
                raise HTTPException(status_code=404, detail="Voice-Profil nicht gefunden")
            phrase = get_test_phrase_for_language(profile.language)
            try:
                row = synthesize_text(
                    session, state.tts_provider, profile_id, phrase,
                    output_dir=state.voice_output_dir, export_format="wav",
                    confirm=req.confirm, is_test_phrase=True,
                )
            except VoiceApplyNotConfirmedError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except TTSProviderUnavailableError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except (VoiceSynthesisError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            after = voice_synthesis_to_dict(row)

        job_id = state.jobs.create_job("voice_test", params={"profile_id": profile_id})
        state.jobs.start(job_id)
        state.jobs.record_history(
            job_id, action="voice_test", media_file_id=None,
            before=None, after=after, user_action="Nutzer hat Voice-Profil-Test bestaetigt",
        )
        state.jobs.complete(job_id)
        return {"job_id": job_id, "synthesis": after}

    @app.get("/voice/syntheses", dependencies=[require_token])
    def list_voice_syntheses_endpoint(
        profile_id: int | None = Query(default=None), state: AppState = Depends(get_state)
    ) -> dict:
        """Reine Lesefunktion (Historie vergangener Sprachausgaben) - kein
        `confirm` noetig."""
        with state.db.session() as session:
            rows = list_syntheses(session, profile_id=profile_id)
            return {"syntheses": [voice_synthesis_to_dict(r) for r in rows]}

    @app.get("/voice/syntheses/{synthesis_id}/audio", dependencies=[require_token])
    def get_voice_synthesis_audio_endpoint(
        synthesis_id: int, state: AppState = Depends(get_state)
    ):
        with state.db.session() as session:
            row = session.get(VoiceSynthesis, synthesis_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Sprachausgabe nicht gefunden")
            output_path = Path(row.output_path)
            export_format = row.export_format
        if not output_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Audiodatei wurde nicht (mehr) auf der Platte gefunden.",
            )
        media_type = {
            "wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac",
        }.get(export_format, "application/octet-stream")
        return Response(content=output_path.read_bytes(), media_type=media_type)

    # -----------------------------------------------------------------
    # Download-/Import-Center (§30-§32, ADR-0019) - §31-Workflow:
    # Erkennen -> Verfuegbarkeit -> Metadaten -> Optionen (alles reine
    # Vorschau, kein confirm) -> Import (confirm=True, fuehrt den
    # eigentlichen Download/die DB-/Dateisystem-Aenderung aus).
    # -----------------------------------------------------------------

    @app.get("/download/providers", dependencies=[require_token])
    def list_download_providers_endpoint(state: AppState = Depends(get_state)) -> dict:
        return {
            "enabled": state.settings.download.enabled,
            "providers": [
                {
                    "id": p.provider_id,
                    "display_name": p.display_name,
                    "requires_internet": p.requires_internet,
                }
                for p in state.download_providers.values()
            ],
        }

    @app.post("/download/detect", dependencies=[require_token])
    def detect_download_source_endpoint(
        req: DownloadUrlRequest, state: AppState = Depends(get_state)
    ) -> dict:
        try:
            provider = state.download_engine.detect(req.url)
        except DownloadProviderNotFoundError:
            return {"provider_id": None, "display_name": None}
        return {"provider_id": provider.provider_id, "display_name": provider.display_name}

    @app.post("/download/availability", dependencies=[require_token])
    def check_download_availability_endpoint(
        req: DownloadUrlRequest, state: AppState = Depends(get_state)
    ) -> dict:
        try:
            provider, availability = state.download_engine.check_availability(req.url)
        except DownloadProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "provider_id": provider.provider_id,
            "available": availability.available,
            "reason": availability.reason,
            "requires_login": availability.requires_login,
        }

    @app.post("/download/metadata", dependencies=[require_token])
    def fetch_download_metadata_endpoint(
        req: DownloadUrlRequest, state: AppState = Depends(get_state)
    ) -> dict:
        try:
            provider, meta = state.download_engine.fetch_metadata(req.url)
        except DownloadProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DownloadNotPermittedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DownloadError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"provider_id": provider.provider_id, **download_metadata_to_dict(meta)}

    @app.post("/download/options", dependencies=[require_token])
    def list_download_options_endpoint(
        req: DownloadUrlRequest, state: AppState = Depends(get_state)
    ) -> dict:
        try:
            provider, options = state.download_engine.list_options(req.url)
        except DownloadProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DownloadNotPermittedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DownloadError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "provider_id": provider.provider_id,
            "options": [dataclasses.asdict(o) for o in options],
        }

    @app.post("/download/import", dependencies=[require_token])
    def import_download_endpoint(
        req: DownloadImportRequest, state: AppState = Depends(get_state)
    ) -> dict:
        try:
            result = state.download_engine.import_from_url(
                req.url, option_id=req.option_id, confirm=req.confirm
            )
        except DownloadConfirmationRequiredError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DownloadNotPermittedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DownloadProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InsufficientStorageError as exc:
            raise HTTPException(status_code=507, detail=str(exc)) from exc
        except DownloadError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return download_import_result_to_dict(result)

    @app.post("/import/local-file", dependencies=[require_token])
    def import_local_file_endpoint(
        req: LocalFileImportRequest, state: AppState = Depends(get_state)
    ) -> dict:
        try:
            result = state.download_engine.import_local_file(req.path, confirm=req.confirm)
        except DownloadConfirmationRequiredError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DownloadNotPermittedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except InsufficientStorageError as exc:
            raise HTTPException(status_code=507, detail=str(exc)) from exc
        except DownloadError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return download_import_result_to_dict(result)

    @app.get("/media/{media_id}/sources", dependencies=[require_token])
    def list_media_sources_endpoint(
        media_id: int, state: AppState = Depends(get_state)
    ) -> dict:
        """§32 Quellenverwaltung - Herkunftsnachweis(e) einer Mediendatei."""
        with state.db.session() as session:
            rows = session.execute(
                select(Source).where(Source.media_file_id == media_id)
            ).scalars().all()
            return {"sources": [source_to_dict(s) for s in rows]}

    return app


def dataclass_to_dict(obj) -> dict:
    import dataclasses as _dc

    return _dc.asdict(obj)


def media_file_to_dict(m: MediaFile) -> dict:
    return {
        "id": m.id,
        "absolute_path": m.absolute_path,
        "directory": m.directory,
        "filename": m.filename,
        "extension": m.extension,
        "kind": m.kind.value,
        "size_bytes": m.size_bytes,
        "mtime": m.mtime.isoformat() if m.mtime else None,
        "content_hash_sha256": m.content_hash_sha256,
        "is_missing": m.is_missing,
        "last_scanned_at": m.last_scanned_at.isoformat() if m.last_scanned_at else None,
    }


def _technical_to_dict(t) -> dict:
    return {
        "container_format": t.container_format,
        "audio_codec": t.audio_codec,
        "video_codec": t.video_codec,
        "bitrate_kbps": t.bitrate_kbps,
        "sample_rate_hz": t.sample_rate_hz,
        "channels": t.channels,
        "duration_seconds": t.duration_seconds,
        "resolution_width": t.resolution_width,
        "resolution_height": t.resolution_height,
        "fps": t.fps,
        "hdr": t.hdr,
        "chapters_count": t.chapters_count,
    }


def suggestion_to_dict(s) -> dict:
    m = s.match
    return {
        "method": s.method,
        "match": {
            "provider": m.provider,
            "confidence": m.confidence,
            "title": m.title,
            "artist": m.artist,
            "album": m.album,
            "year": m.year,
            "track_number": m.track_number,
            "musicbrainz_recording_id": m.musicbrainz_recording_id,
            "musicbrainz_release_id": m.musicbrainz_release_id,
            "musicbrainz_artist_id": m.musicbrainz_artist_id,
        },
        "existing_tags": {
            "title": s.existing_tags.title,
            "artist": s.existing_tags.artist,
            "album": s.existing_tags.album,
        },
    }


def track_to_dict(t) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.id,
        "title": t.title,
        "album_id": t.album_id,
        "album_artist": t.album_artist,
        "track_number": t.track_number,
        "disc_number": t.disc_number,
        "year": t.year,
        "source": t.source,
        "confidence": t.confidence,
        "is_user_confirmed": t.is_user_confirmed,
    }


def rename_preview_item_to_dict(i) -> dict:
    return {
        "media_file_id": i.media_file_id,
        "old_absolute_path": i.old_absolute_path,
        "new_absolute_path": i.new_absolute_path,
        "empty_fields": i.empty_fields,
        "has_conflict": i.has_conflict,
        "conflict_reason": i.conflict_reason,
        "is_identical": i.is_identical,
        "template_error": i.template_error,
        "is_actionable": i.is_actionable,
    }


def rename_apply_result_to_dict(r) -> dict:
    return {
        "media_file_id": r.media_file_id,
        "applied": r.applied,
        "old_absolute_path": r.old_absolute_path,
        "new_absolute_path": r.new_absolute_path,
        "reason": r.reason,
    }


def loudness_to_dict(r: Loudness) -> dict:
    return {
        "id": r.id,
        "media_file_id": r.media_file_id,
        "integrated_lufs": r.integrated_lufs,
        "true_peak_dbtp": r.true_peak_dbtp,
        "loudness_range_lu": r.loudness_range_lu,
        "target_lufs_used": r.target_lufs_used,
        "target_true_peak_dbtp_used": r.target_true_peak_dbtp_used,
        "normalized": r.normalized,
        "normalized_output_path": r.normalized_output_path,
        "measured_at": r.measured_at.isoformat() if r.measured_at else None,
    }


def source_to_dict(s: Source) -> dict:
    """§32 Quellenverwaltung."""
    return {
        "id": s.id,
        "media_file_id": s.media_file_id,
        "source_name": s.source_name,
        "provider_name": s.provider_name,
        "original_url": s.original_url,
        "original_id": s.original_id,
        "imported_at": s.imported_at.isoformat() if s.imported_at else None,
        "import_method": s.import_method,
    }


def download_metadata_to_dict(meta: DownloadSourceMetadata) -> dict:
    return {
        "title": meta.title,
        "description": meta.description,
        "duration_seconds": meta.duration_seconds,
        "uploader": meta.uploader,
        "thumbnail_url": meta.thumbnail_url,
        "original_id": meta.original_id,
        "license": meta.license,
        "extra": meta.extra,
    }


def download_import_result_to_dict(r) -> dict:
    return {
        "job_id": r.job_id,
        "media_file_id": r.media_file_id,
        "absolute_path": r.absolute_path,
        "source_id": r.source_id,
        "suggested_filename": r.suggested_filename,
        "fingerprint_computed": r.fingerprint_computed,
        "loudness_measured": r.loudness_measured,
        "warnings": r.warnings,
    }


def cut_to_dict(r: AudioCut) -> dict:
    return {
        "id": r.id,
        "media_file_id": r.media_file_id,
        "source_path": r.source_path,
        "output_path": r.output_path,
        "start_seconds": r.start_seconds,
        "end_seconds": r.end_seconds,
        "fade_in_seconds": r.fade_in_seconds,
        "fade_out_seconds": r.fade_out_seconds,
        "export_format": r.export_format,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def conversion_to_dict(r: AudioConversion) -> dict:
    return {
        "id": r.id,
        "media_file_id": r.media_file_id,
        "source_path": r.source_path,
        "output_path": r.output_path,
        "source_format": r.source_format,
        "target_format": r.target_format,
        "bitrate_kbps": r.bitrate_kbps,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def audiobook_to_dict(a: Audiobook) -> dict:
    return {
        "id": a.id,
        "media_file_id": a.media_file_id,
        "title": a.title,
        "author": a.author,
        "narrator": a.narrator,
        "publisher": a.publisher,
        "series": a.series.name if a.series is not None else None,
        "volume_number": a.volume_number,
        "year": a.year,
        "language": a.language,
        "description": a.description,
    }


def _person_names_for_role(
    session, *, role: PersonRoleType, movie_id: int | None = None, episode_id: int | None = None,
) -> list[str]:
    query = select(Person.name).join(PersonRole, PersonRole.person_id == Person.id).where(
        PersonRole.role == role
    )
    if movie_id is not None:
        query = query.where(PersonRole.movie_id == movie_id)
    if episode_id is not None:
        query = query.where(PersonRole.episode_id == episode_id)
    return list(session.execute(query).scalars().all())


def movie_to_dict(session, m: Movie) -> dict:
    return {
        "id": m.id,
        "media_file_id": m.media_file_id,
        "title": m.title,
        "original_title": m.original_title,
        "year": m.year,
        "genre": m.genre,
        "runtime_seconds": m.runtime_seconds,
        "language": m.language,
        "description": m.description,
        "directors": _person_names_for_role(session, role=PersonRoleType.DIRECTOR, movie_id=m.id),
        "actors": _person_names_for_role(session, role=PersonRoleType.ACTOR, movie_id=m.id),
    }


def episode_to_dict(session, e: Episode) -> dict:
    return {
        "id": e.id,
        "media_file_id": e.media_file_id,
        "series": e.series.name if e.series is not None else None,
        "season_number": e.season_number,
        "episode_number": e.episode_number,
        "title": e.title,
        "year": e.year,
        "description": e.description,
        "directors": _person_names_for_role(
            session, role=PersonRoleType.DIRECTOR, episode_id=e.id
        ),
        "actors": _person_names_for_role(session, role=PersonRoleType.ACTOR, episode_id=e.id),
    }


def chapter_to_dict(c: Chapter) -> dict:
    return {
        "id": c.id,
        "media_file_id": c.media_file_id,
        "index": c.index,
        "title": c.title,
        "start_ms": c.start_ms,
        "end_ms": c.end_ms,
    }


def duplicate_group_to_dict(g: DuplicateGroup) -> dict:
    return {
        "id": g.id,
        "category": g.category,
        "confidence": g.confidence,
        "matched_stages": g.matched_stages_json,
        "reason": g.reason,
        "reviewed": g.reviewed,
        "detected_at": g.detected_at.isoformat() if g.detected_at else None,
        "media_file_ids": [m.media_file_id for m in g.members],
    }


def job_to_dict(j: ProcessingJob) -> dict:
    return {
        "id": j.id,
        "job_type": j.job_type,
        "status": j.status.value,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        "total_items": j.total_items,
        "processed_items": j.processed_items,
        "error_count": j.error_count,
        "warning_count": j.warning_count,
        "current_item": j.current_item,
    }


def error_log_to_dict(e: ErrorLog) -> dict:
    """§37 - vollstaendiger Kontext fuer das Error-Center."""
    return {
        "error_id": e.error_id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "component": e.component,
        "file_path": e.file_path,
        "action": e.action,
        "message": e.message,
        "technical_details": e.technical_details,
        "solution_hint": e.solution_hint,
        "resolved": e.resolved,
    }


def diagnostics_report_to_dict(report: DiagnosticsReport) -> dict:
    """§38 - vollstaendiger Gesundheitsbericht fuer den Diagnostics-
    Bildschirm."""
    return {
        "generated_at": report.generated_at,
        "overall_status": report.overall_status,
        "checks": [dataclasses.asdict(c) for c in report.checks],
    }


def backup_result_to_dict(r) -> dict:
    return dataclasses.asdict(r)


def backup_to_dict(b: Backup) -> dict:
    """§40 - Eintrag aus der Backup-Historie (Datenbank/Konfiguration,
    niemals Mediendateien)."""
    return {
        "id": b.id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "backup_type": b.backup_type,
        "path": b.path,
        "version_label": b.version_label,
        "size_bytes": b.size_bytes,
    }


def plugin_to_dict(p: LoadedPlugin) -> dict:
    """§34 - zeigt auch fehlgeschlagene Plugins mit Klartext-`load_error`,
    statt sie stillschweigend zu verstecken (Prinzip "keine stillen
    Fehlschläge")."""
    return {
        "plugin_id": p.plugin_id,
        "plugin_kind": p.plugin_kind,
        "display_name": p.display_name,
        "version": p.version,
        "author": p.author,
        "license": p.license,
        "is_local": p.is_local,
        "requires_internet": p.requires_internet,
        "source_path": p.source_path,
        "loaded_successfully": p.loaded_successfully,
        "load_error": p.load_error,
    }


def repair_preview_to_dict(preview) -> dict:
    return {
        "generated_at": preview.generated_at,
        "items": [dataclasses.asdict(i) for i in preview.items],
    }


def repair_preview_from_request(req: RepairExecuteRequest):
    """Baut die vom Client in /repair/preview erhaltene und (ggf. vom
    Nutzer in der UI ausgewaehlte) Teilmenge wieder in echte
    `RepairPreviewItem`/`TempFileCandidate`-Objekte um, damit
    `execute_repairs` exakt auf derselben, bereits gezeigten Vorschau
    arbeitet (Prinzip #17 - keine erneute, moeglicherweise abweichende
    Neuberechnung kurz vor der Ausfuehrung)."""
    from genesis_core.repair import RepairPreview, RepairPreviewItem
    from genesis_core.storage import TempFileCandidate

    items = [
        RepairPreviewItem(
            action_type=i.action_type,
            target=i.target,
            row_ids=list(i.row_ids),
            temp_files=[
                TempFileCandidate(
                    path=t.path, size_bytes=t.size_bytes,
                    modified_at=t.modified_at, age_seconds=t.age_seconds,
                )
                for t in i.temp_files
            ],
        )
        for i in req.items
    ]
    return RepairPreview(
        generated_at=dt_module.datetime.now(dt_module.UTC).isoformat(), items=items
    )


def ai_metadata_to_dict(e: AIMetadata) -> dict:
    """§25 - immer mit voller Herkunft (AI generated/Model/Version/
    Timestamp/Confidence), wie von der Spezifikation verlangt."""
    return {
        "id": e.id,
        "media_file_id": e.media_file_id,
        "field_name": e.field_name,
        "field_value": e.field_value,
        "is_ai_generated": e.is_ai_generated,
        "model_name": e.model_name,
        "model_version": e.model_version,
        "confidence": e.confidence,
        "prompt": e.prompt,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "accepted_by_user": e.accepted_by_user,
    }


def voice_profile_to_dict(p: VoiceProfile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "engine": p.engine,
        "model_path": p.model_path,
        "language": p.language,
        "description": p.description,
        "model_license": p.model_license,
        "offline_capable": p.offline_capable,
        "open_source": p.open_source,
        "commercial_use_allowed": p.commercial_use_allowed,
        "sample_path": p.sample_path,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def voice_synthesis_to_dict(s: VoiceSynthesis) -> dict:
    return {
        "id": s.id,
        "voice_profile_id": s.voice_profile_id,
        "text": s.text,
        "output_path": s.output_path,
        "export_format": s.export_format,
        "duration_seconds": s.duration_seconds,
        "sample_rate": s.sample_rate,
        "engine": s.engine,
        "is_test_phrase": s.is_test_phrase,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def ai_music_to_dict(session, t: Track) -> dict:
    """§27 - KI-Musik-Provenienz; `artist_names` kommt aus dem
    Wissensgraph (PersonRole, konsistent mit Phase 5/§63)."""
    return {
        "track_id": t.id,
        "media_file_id": t.media_file_id,
        "ai_status": t.ai_status.value,
        "ai_source": t.ai_source,
        "ai_model": t.ai_model,
        "ai_prompt": t.ai_prompt,
        "ai_creation_date": t.ai_creation_date.isoformat() if t.ai_creation_date else None,
        "ai_instrumental": t.ai_instrumental,
        "ai_style": t.ai_style,
        "ai_mood": t.ai_mood,
        "ai_owner": t.ai_owner,
        "artist_names": artist_names_for_track(session, t.id),
    }
