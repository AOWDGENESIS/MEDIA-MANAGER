"""Diagnostics-Modul (§38).

Liefert einen schnellen, rein LESENDEN Gesundheitsbericht ueber die
wichtigsten Teilsysteme von GENESIS (Datenbank, Speicherplatz,
Medienordner, externe Werkzeuge wie ffmpeg/fpcalc, Provider, KI/TTS,
Plugins, Dateirechte, verwaiste Datenbankeintraege).

Wichtig (Prinzip #4/#5, wie ueberall in GENESIS): Diagnostics AENDERT
NICHTS. Sie deckt nur Probleme auf und beschreibt sie verstaendlich -
eine tatsaechliche Reparatur (z.B. Entfernen verwaister Datenbankzeilen,
erneutes Verlinken fehlender Dateien) geschieht ausschliesslich ueber
den separaten Scan & Repair-Workflow (genesis_core.repair, §39) mit
Plan -> Vorschau -> ausdrueckliche Bestaetigung -> Ausfuehrung.

Jeder einzelne Check ist bewusst defensiv geschrieben: ein nicht
uebergebener/nicht konfigurierter Provider fuehrt NIE zu einem Absturz
der gesamten Diagnose, sondern lediglich zu einem einzelnen Check mit
Status "warning" bzw. einer neutralen "nicht geprueft"-Meldung.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text

from genesis_core.config import Settings
from genesis_core.db import Database
from genesis_core.db.models import (
    AIEmbedding,
    AIMetadata,
    Artwork,
    Audiobook,
    AudioConversion,
    AudioCut,
    Chapter,
    DuplicateGroupMember,
    Episode,
    Fingerprint,
    Loudness,
    MediaFile,
    Movie,
    PodcastEpisode,
    Source,
    TechnicalMetadata,
    Track,
)
from genesis_core.logutil import get_logger
from genesis_core.storage import check_free_space

log = get_logger("Diagnostics")

# Unterhalb dieser freien Speicherkapazitaet auf dem Datenverzeichnis-
# Laufwerk wird gewarnt (reine Diagnose-Schwelle, unabhaengig von den
# operationsspezifischen Schwellen in genesis_core.storage/config).
DIAGNOSTICS_MIN_FREE_MB = 500

# Tabellen mit einer media_file_id-Fremdschluesselspalte, die bei
# geloeschten/verwaisten MediaFile-Zeilen auf "Geisterdaten" ueberprueft
# werden (§38 "verwaiste Datenbankeintraege", §39 Scan & Repair nutzt
# dieselbe Liste + `find_orphaned_rows` unten fuer die tatsaechliche
# Bereinigung). Bewusst als Liste von (Label, Modellklasse)-Paaren statt
# Introspektion ueber alle Modelle, damit neue, bewusst NICHT fuer diesen
# Check relevante Tabellen nicht versehentlich mit aufgenommen werden.
ORPHAN_CHECK_TABLES: list[tuple[str, Any]] = [
    ("tracks", Track),
    ("technical_metadata", TechnicalMetadata),
    ("fingerprints", Fingerprint),
    ("loudness", Loudness),
    ("artwork", Artwork),
    ("sources", Source),
    ("ai_metadata", AIMetadata),
    ("audio_cuts", AudioCut),
    ("audio_conversions", AudioConversion),
    ("chapters", Chapter),
    ("audiobooks", Audiobook),
    ("movies", Movie),
    ("episodes", Episode),
    ("podcast_episodes", PodcastEpisode),
    ("duplicate_group_members", DuplicateGroupMember),
    ("ai_embeddings", AIEmbedding),
]


@dataclasses.dataclass
class DiagnosticCheck:
    check_id: str
    label: str
    status: str  # "ok" | "warning" | "error"
    message: str
    details: dict | None = None


@dataclasses.dataclass
class DiagnosticsReport:
    generated_at: str
    checks: list[DiagnosticCheck]

    @property
    def overall_status(self) -> str:
        statuses = {c.status for c in self.checks}
        if "error" in statuses:
            return "error"
        if "warning" in statuses:
            return "warning"
        return "ok"


def _check_database(db: Database) -> DiagnosticCheck:
    try:
        with db.session() as session:
            integrity = session.execute(text("PRAGMA integrity_check")).scalar_one()
            total_files = session.execute(select(func.count()).select_from(MediaFile)).scalar_one()
        if integrity != "ok":
            return DiagnosticCheck(
                "database", "Datenbank", "error",
                f"SQLite meldet Integritaetsprobleme: {integrity}",
                {"integrity_check": integrity},
            )
        return DiagnosticCheck(
            "database", "Datenbank", "ok",
            f"Datenbank ist konsistent ({total_files} Mediendatei(en) erfasst).",
            {"total_media_files": total_files},
        )
    except Exception as exc:  # noqa: BLE001 - Diagnose darf nie selbst abstuerzen
        log.error("Datenbank-Check fehlgeschlagen: %s", exc)
        return DiagnosticCheck(
            "database", "Datenbank", "error", f"Datenbank nicht pruefbar: {exc}",
        )


def _check_storage(settings: Settings) -> DiagnosticCheck:
    try:
        result = check_free_space(settings.paths.data_dir, required_bytes=0)
        free_mb = result.free_mb
        if free_mb < DIAGNOSTICS_MIN_FREE_MB:
            return DiagnosticCheck(
                "storage", "Speicherplatz", "warning",
                f"Nur noch {free_mb:.0f} MB frei auf {result.path} "
                f"(Warnschwelle: {DIAGNOSTICS_MIN_FREE_MB} MB).",
                {"free_mb": free_mb, "path": result.path},
            )
        return DiagnosticCheck(
            "storage", "Speicherplatz", "ok",
            f"{free_mb:.0f} MB frei auf {result.path}.",
            {"free_mb": free_mb, "path": result.path},
        )
    except OSError as exc:
        return DiagnosticCheck(
            "storage", "Speicherplatz", "error", f"Speicherplatz nicht pruefbar: {exc}",
        )


def _check_media_folders(settings: Settings) -> DiagnosticCheck:
    folders = settings.paths.media_folders
    if not folders:
        return DiagnosticCheck(
            "media_folders", "Medienordner", "warning",
            "Keine Medienordner konfiguriert - es kann noch kein Scan laufen.",
        )
    missing = [str(f) for f in folders if not Path(f).exists()]
    if missing:
        return DiagnosticCheck(
            "media_folders", "Medienordner", "error",
            f"{len(missing)} von {len(folders)} konfigurierten Medienordner(n) "
            "nicht erreichbar (z.B. externe Festplatte getrennt?).",
            {"missing": missing},
        )
    return DiagnosticCheck(
        "media_folders", "Medienordner", "ok",
        f"Alle {len(folders)} konfigurierten Medienordner sind erreichbar.",
    )


def _check_media_engine() -> DiagnosticCheck:
    tools = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "fpcalc": shutil.which("fpcalc"),
    }
    missing = [name for name, path in tools.items() if not path]
    if missing:
        return DiagnosticCheck(
            "media_engine", "Medien-Werkzeuge (ffmpeg/fpcalc)", "warning",
            "Folgende externe Werkzeuge wurden nicht im PATH gefunden: "
            f"{', '.join(missing)}. Betroffene Funktionen (technische "
            "Analyse, Lautheit, Schnitt, Fingerprinting) sind eingeschraenkt.",
            {"tools": tools},
        )
    return DiagnosticCheck(
        "media_engine", "Medien-Werkzeuge (ffmpeg/fpcalc)", "ok",
        "ffmpeg, ffprobe und fpcalc sind verfuegbar.", {"tools": tools},
    )


def _check_metadata_providers(settings: Settings) -> DiagnosticCheck:
    if not settings.metadata.enabled:
        return DiagnosticCheck(
            "metadata_providers", "Online-Metadaten-Provider", "ok",
            "Online-Metadatenabgleich ist deaktiviert (Offline-Standard, §56) - "
            "kein Fehlerzustand.",
        )
    enabled = {
        "musicbrainz": settings.metadata.musicbrainz_enabled,
        "acoustid": settings.metadata.acoustid_enabled,
        "coverartarchive": settings.metadata.coverartarchive_enabled,
    }
    active = [name for name, on in enabled.items() if on]
    return DiagnosticCheck(
        "metadata_providers", "Online-Metadaten-Provider", "ok",
        f"Aktiviert: {', '.join(active) if active else 'keiner'} "
        "(tatsaechliche Erreichbarkeit wird erst bei Nutzung geprueft).",
        {"enabled": enabled},
    )


def _check_ai(settings: Settings, ai_provider: Any | None) -> DiagnosticCheck:
    if not settings.ai.enabled:
        return DiagnosticCheck(
            "ai", "KI-Anbindung", "ok",
            "KI-Funktionen sind deaktiviert (Offline-Standard, §56) - kein Fehlerzustand.",
        )
    if ai_provider is None:
        return DiagnosticCheck(
            "ai", "KI-Anbindung", "warning", "KI ist aktiviert, aber kein Provider uebergeben.",
        )
    try:
        available = ai_provider.is_available()
    except Exception as exc:  # noqa: BLE001
        return DiagnosticCheck(
            "ai", "KI-Anbindung", "error", f"KI-Provider-Pruefung fehlgeschlagen: {exc}",
        )
    name = getattr(ai_provider, "name", "unbekannt")
    if available:
        return DiagnosticCheck(
            "ai", "KI-Anbindung", "ok", f"KI-Provider '{name}' ist erreichbar.",
            {"provider": name},
        )
    return DiagnosticCheck(
        "ai", "KI-Anbindung", "warning",
        f"KI-Provider '{name}' ist aktiviert, aber aktuell nicht erreichbar "
        "(z.B. Ollama/LM Studio nicht gestartet).",
        {"provider": name},
    )


def _check_tts(settings: Settings, tts_provider: Any | None) -> DiagnosticCheck:
    if not settings.voice.enabled:
        return DiagnosticCheck(
            "tts", "Voice Studio / TTS", "ok",
            "Voice Studio ist deaktiviert - kein Fehlerzustand.",
        )
    if tts_provider is None:
        return DiagnosticCheck(
            "tts", "Voice Studio / TTS", "warning",
            "Voice Studio ist aktiviert, aber kein Provider uebergeben.",
        )
    try:
        available = tts_provider.is_available()
    except Exception as exc:  # noqa: BLE001
        return DiagnosticCheck(
            "tts", "Voice Studio / TTS", "error", f"TTS-Provider-Pruefung fehlgeschlagen: {exc}",
        )
    name = getattr(tts_provider, "name", "unbekannt")
    status = "ok" if available else "warning"
    message = (
        f"TTS-Provider '{name}' ist einsatzbereit."
        if available
        else f"TTS-Provider '{name}' ist aktuell nicht einsatzbereit (z.B. Modell fehlt)."
    )
    return DiagnosticCheck("tts", "Voice Studio / TTS", status, message, {"provider": name})


def _check_download_providers(download_providers: dict | None) -> DiagnosticCheck:
    if not download_providers:
        return DiagnosticCheck(
            "download_providers", "Download-/Import-Provider", "warning",
            "Keine Download-/Import-Provider registriert.",
        )
    names = sorted(download_providers.keys())
    return DiagnosticCheck(
        "download_providers", "Download-/Import-Provider", "ok",
        f"{len(names)} Provider registriert: {', '.join(names)} "
        "(tatsaechliche Erreichbarkeit wird erst bei Nutzung geprueft).",
        {"providers": names},
    )


def _check_plugins(plugin_registry: Any | None) -> DiagnosticCheck:
    if plugin_registry is None:
        return DiagnosticCheck(
            "plugins", "Plugins", "ok", "Kein Plugin-System aktiv geladen - kein Fehlerzustand.",
        )
    try:
        loaded = plugin_registry.list_plugins()
    except Exception as exc:  # noqa: BLE001
        return DiagnosticCheck(
            "plugins", "Plugins", "error", f"Plugin-Registry nicht abfragbar: {exc}",
        )
    failed = [p for p in loaded if getattr(p, "load_error", None)]
    if failed:
        return DiagnosticCheck(
            "plugins", "Plugins", "warning",
            f"{len(failed)} von {len(loaded)} Plugin(s) konnten nicht geladen werden "
            "(Host blieb stabil, siehe jeweilige load_error).",
            {"failed": [getattr(p, "plugin_id", "?") for p in failed]},
        )
    return DiagnosticCheck(
        "plugins", "Plugins", "ok", f"{len(loaded)} Plugin(s) geladen, keine Fehler.",
    )


def _check_file_permissions(settings: Settings) -> DiagnosticCheck:
    probe = settings.paths.data_dir / ".genesis_diagnostics_probe"
    try:
        probe.write_text("probe", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return DiagnosticCheck(
            "file_permissions", "Dateiberechtigungen", "error",
            f"Datenverzeichnis {settings.paths.data_dir} ist nicht beschreibbar: {exc}",
        )
    return DiagnosticCheck(
        "file_permissions", "Dateiberechtigungen", "ok",
        f"Datenverzeichnis {settings.paths.data_dir} ist beschreibbar.",
    )


def find_orphaned_rows(db: Database) -> dict[str, list[int]]:
    """Ermittelt je ueberwachter Tabelle die IDs von Zeilen, deren
    media_file_id auf keine (mehr) existierende MediaFile zeigt (z.B.
    Ueberbleibsel nach einem manuellen Eingriff in der Datenbank
    ausserhalb von GENESIS). Rein lesend (Prinzip #4/#5) - wird sowohl von
    `_check_orphaned_entries` (nur Zaehlung/Meldung) als auch von
    `genesis_core.repair` (tatsaechliche, bestaetigte Bereinigung) genutzt,
    damit beide Stellen garantiert dieselbe Definition von "verwaist"
    verwenden."""
    with db.session() as session:
        known_ids = set(session.execute(select(MediaFile.id)).scalars().all())
        orphans: dict[str, list[int]] = {}
        for label, model in ORPHAN_CHECK_TABLES:
            rows = session.execute(select(model.id, model.media_file_id)).all()
            orphan_ids = [rid for rid, mid in rows if mid is not None and mid not in known_ids]
            if orphan_ids:
                orphans[label] = orphan_ids
        return orphans


def _check_orphaned_entries(db: Database) -> DiagnosticCheck:
    try:
        orphans = find_orphaned_rows(db)
    except Exception as exc:  # noqa: BLE001
        return DiagnosticCheck(
            "orphaned_entries", "Verwaiste Datenbankeintraege", "error",
            f"Pruefung fehlgeschlagen: {exc}",
        )
    if orphans:
        counts = {label: len(ids) for label, ids in orphans.items()}
        total = sum(counts.values())
        return DiagnosticCheck(
            "orphaned_entries", "Verwaiste Datenbankeintraege", "warning",
            f"{total} verwaiste Eintraege gefunden (ohne zugehoerige Mediendatei). "
            "Koennen ueber Scan & Repair bereinigt werden.",
            {"orphans_by_table": counts},
        )
    return DiagnosticCheck(
        "orphaned_entries", "Verwaiste Datenbankeintraege", "ok",
        "Keine verwaisten Datenbankeintraege gefunden.",
    )


def run_diagnostics(
    db: Database,
    settings: Settings,
    *,
    ai_provider: Any | None = None,
    tts_provider: Any | None = None,
    download_providers: dict | None = None,
    plugin_registry: Any | None = None,
) -> DiagnosticsReport:
    """Fuehrt alle Diagnose-Checks aus (§38). Rein lesend, voellig
    ungefaehrlich, kann beliebig oft wiederholt werden (z.B. per Knopf im
    Diagnostics-Bildschirm oder periodisch im Hintergrund)."""
    checks = [
        _check_database(db),
        _check_storage(settings),
        _check_media_folders(settings),
        _check_media_engine(),
        _check_metadata_providers(settings),
        _check_ai(settings, ai_provider),
        _check_tts(settings, tts_provider),
        _check_download_providers(download_providers),
        _check_plugins(plugin_registry),
        _check_file_permissions(settings),
        _check_orphaned_entries(db),
    ]
    return DiagnosticsReport(
        generated_at=dt.datetime.now(dt.UTC).isoformat(), checks=checks,
    )


__all__ = [
    "DIAGNOSTICS_MIN_FREE_MB",
    "ORPHAN_CHECK_TABLES",
    "DiagnosticCheck",
    "DiagnosticsReport",
    "find_orphaned_rows",
    "run_diagnostics",
]
