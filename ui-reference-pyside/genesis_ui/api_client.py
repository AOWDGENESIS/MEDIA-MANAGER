"""Duenner HTTP-Client zur lokalen GENESIS Core API (ADR-0001).

Die UI enthaelt bewusst KEINE Fachlogik - sie ruft ausschliesslich die vom
Core Service bereitgestellte REST-API auf. Das gilt identisch fuer den
spaeteren .NET-Client (siehe ARCHITECTURE.md).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

# ADR-0006 (Deep Review Sitzung 2): Die lokale API verlangt seit dieser
# Aenderung ein Shared-Secret-Token (Header X-Genesis-Token), um Drive-by-
# Localhost-/JSON-CSRF-Anfragen von im Browser geoeffneten Fremdseiten
# abzuwehren (blosses Binden an 127.0.0.1 reicht dafuer NICHT aus).
#
# Diese UI ist bewusst ein reiner Praesentations-Client ohne Abhaengigkeit
# auf genesis_core (Architekturregel, siehe ARCHITECTURE.md) - deshalb wird
# der Speicherort der Token-Datei hier bewusst MINIMAL dupliziert statt
# importiert. Muss synchron bleiben mit:
#   - genesis_core.config.default_data_dir()
#   - genesis_core.api.security.TOKEN_FILENAME
TOKEN_FILENAME = "api_token.txt"


def _default_data_dir() -> Path:
    env_override = os.environ.get("GENESIS_DATA_DIR")
    if env_override:
        return Path(env_override).expanduser()
    appdata = os.environ.get("APPDATA")  # Windows
    if appdata:
        return Path(appdata) / "GenesisMediaManager"
    return Path.home() / ".genesis-media-manager"


def _read_api_token() -> str | None:
    token_path = _default_data_dir() / TOKEN_FILENAME
    if not token_path.exists():
        return None
    token = token_path.read_text(encoding="utf-8").strip()
    return token or None


class GenesisAPIError(RuntimeError):
    """§37 - transportiert neben der reinen Textmeldung (fuer bestehende
    `str(exc)`-Aufrufstellen unveraendert nutzbar) zusaetzlich die
    strukturierten Felder aus dem zentralen Fehlerformat, FALLS die Core-
    API sie mitgeliefert hat (nur bei echten, unerwarteten 500ern aus dem
    globalen Exception-Handler - normale 4xx-Validierungsfehler haben
    i.d.R. nur `detail`, kein `error_id`). `error_dialog.show_api_error`
    nutzt das, um dem Nutzer eine nachschlagbare Fehler-ID anzuzeigen statt
    nur eines nackten Fehlertexts."""

    def __init__(self, message: str, *, error_id: str | None = None,
                 solution_hint: str | None = None):
        super().__init__(message)
        self.error_id = error_id
        self.solution_hint = solution_hint


class GenesisAPIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8420"):
        self.base_url = base_url.rstrip("/")
        token = _read_api_token()
        headers = {"X-Genesis-Token": token} if token else {}
        if token is None:
            # Kein hartes Scheitern hier - der Core Service liefert bei
            # jedem geschuetzten Aufruf ohnehin einen klaren 401-Fehler mit
            # deutscher Fehlermeldung. So bleibt z.B. /health weiterhin ohne
            # Token erreichbar (siehe genesis_core/api/security.py).
            pass
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0, headers=headers)

    def health(self) -> dict:
        return self._get("/health")

    def dashboard_summary(self) -> dict:
        return self._get("/dashboard/summary")

    def list_media(self, kind: str | None = None, search: str | None = None,
                    limit: int = 200, offset: int = 0, **filters: Any) -> dict:
        """§9 (Gap-Analyse Gap C) - `**filters` reicht beliebige der vom
        Backend unterstuetzten erweiterten Suchparameter unveraendert durch
        (`year`, `genre`, `extension`, `min_size_bytes`, `max_size_bytes`,
        `min_duration_s`, `max_duration_s`, `source`, `person`, `series`,
        `season`, `episode_number`, `ai_status`, `min_lufs`, `max_lufs`,
        `has_quality_issues`, `missing_metadata`, `missing_cover`,
        `duplicate_only`) - `None`-Werte werden weggelassen, damit nicht
        gesetzte Filter das Backend nicht unnoetig einschraenken."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if kind:
            params["kind"] = kind
        if search:
            params["search"] = search
        for key, value in filters.items():
            if value is not None:
                params[key] = value
        return self._get("/media", params=params)

    def media_detail(self, media_id: int) -> dict:
        return self._get(f"/media/{media_id}")

    def get_logs(
        self,
        level: str | None = None,
        component: str | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        """§54 (Gap-Analyse Gap J) - rein lesender Zugriff auf die bereits
        bestehenden Logdateien (aktuell + rotierte Backups)."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if level:
            params["level"] = level
        if component:
            params["component"] = component
        if search:
            params["search"] = search
        return self._get("/logs", params=params)

    def trigger_scan(self, directories: list[str]) -> dict:
        return self._post("/scan", json={"directories": directories})

    def get_settings(self) -> dict:
        """Lesender Zugriff auf die aktuellen Core-Einstellungen (u.a.
        `general.language` fuer §53-Sprachumschaltung)."""
        return self._get("/settings")

    def update_settings(self, updates: dict, *, confirm: bool) -> dict:
        """§55 - partielles PATCH der Konfiguration (Gap-Analyse A). `updates`
        muss NUR die tatsaechlich zu aendernden, verschachtelten Felder
        enthalten (z.B. `{"ai": {"enabled": True}}`) - alles andere bleibt
        unveraendert. Liefert `{"settings": ..., "restart_required": bool,
        "job_id": ...}`."""
        return self._patch("/settings", json={"updates": updates, "confirm": confirm})

    # --- Bibliotheks-Drill-down (§9/§62, Gap-Analyse B) ----------------------
    # Rein lesende Browsing-Aufrufe fuer die Interpreten-/Alben-/Titel-/
    # Genre-/Personen-/Quellen-Seiten.

    def list_library_artists(self, search: str | None = None) -> list[dict]:
        params = {"search": search} if search else None
        return self._get("/library/artists", params=params)

    def get_library_artist_detail(self, artist_id: int) -> dict:
        return self._get(f"/library/artists/{artist_id}")

    def list_library_albums(self, search: str | None = None) -> list[dict]:
        params = {"search": search} if search else None
        return self._get("/library/albums", params=params)

    def get_library_album_detail(self, album_id: int) -> dict:
        return self._get(f"/library/albums/{album_id}")

    def list_library_tracks(self, search: str | None = None, limit: int = 200,
                             offset: int = 0) -> dict:
        params = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        return self._get("/library/tracks", params=params)

    def list_library_genres(self, search: str | None = None) -> list[dict]:
        params = {"search": search} if search else None
        return self._get("/library/genres", params=params)

    def get_library_genre_detail(self, genre_id: int) -> dict:
        return self._get(f"/library/genres/{genre_id}")

    def list_library_persons(self, search: str | None = None) -> list[dict]:
        params = {"search": search} if search else None
        return self._get("/library/persons", params=params)

    def get_library_person_detail(self, person_id: int) -> dict:
        return self._get(f"/library/persons/{person_id}")

    def list_library_sources(self, search: str | None = None, limit: int = 200,
                              offset: int = 0) -> dict:
        params = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        return self._get("/library/sources", params=params)

    # --- Phase 2: Metadaten-Vorschlaege (§10/§11/§17) -----------------------

    def get_metadata_suggestions(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/metadata-suggestions")["suggestions"]

    def apply_metadata_suggestion(self, media_id: int, match: dict, *, confirm: bool) -> dict:
        """`confirm` muss vom Aufrufer NUR True sein, nachdem der Nutzer den
        Vorschlag in der UI tatsaechlich bestaetigt hat (Prinzip #17, §44)."""
        return self._post(
            f"/media/{media_id}/metadata-suggestions/apply",
            json={"match": match, "confirm": confirm},
        )

    # --- Phase 2: Umbenennen (§15/§16) ---------------------------------------

    def rename_preview(self, media_file_ids: list[int], template: str) -> list[dict]:
        return self._post(
            "/rename/preview", json={"media_file_ids": media_file_ids, "template": template}
        )["items"]

    def rename_apply(self, media_file_ids: list[int], template: str, *, confirm: bool) -> dict:
        """`confirm` muss vom Aufrufer NUR True sein, nachdem der Nutzer die
        Vorschau tatsaechlich bestaetigt hat (Prinzip #16/#17, §44)."""
        return self._post(
            "/rename/apply",
            json={"media_file_ids": media_file_ids, "template": template, "confirm": confirm},
        )

    # --- Phase 2: Artwork (§22) -----------------------------------------------

    def get_artwork_bytes(self, media_id: int) -> tuple[bytes, str] | None:
        try:
            resp = self._client.get(f"/media/{media_id}/artwork")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "image/jpeg")
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    def fetch_artwork_online(self, media_id: int) -> dict:
        return self._post(f"/media/{media_id}/artwork/fetch-online", json={})

    def embed_artwork(self, media_id: int, artwork_id: int, *, confirm: bool) -> dict:
        return self._post(
            f"/media/{media_id}/artwork/embed",
            json={"artwork_id": artwork_id, "confirm": confirm},
        )

    # --- Phase 3: Loudness (§19, ADR-0010) -------------------------------------

    def analyze_loudness(self, media_id: int) -> dict:
        """Reine Messung (kein confirm noetig - veraendert die Datei nicht,
        Prinzip #4/#5)."""
        return self._post(f"/media/{media_id}/loudness/analyze", json={})

    def list_loudness(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/loudness")

    def preview_loudness_normalization(
        self, media_id: int, *, target_lufs: float | None = None,
        target_true_peak_dbtp: float | None = None, target_lra: float = 11.0,
    ) -> dict:
        """Reine Berechnung - erzeugt keine Datei. Fehlende Zielwerte lassen
        den Core Service die konfigurierten Standardwerte
        (Settings.loudness) verwenden."""
        return self._post(
            f"/media/{media_id}/loudness/normalize/preview",
            json={
                "target_lufs": target_lufs,
                "target_true_peak_dbtp": target_true_peak_dbtp,
                "target_lra": target_lra,
            },
        )

    def apply_loudness_normalization(
        self, media_id: int, *, target_lufs: float | None, target_true_peak_dbtp: float | None,
        target_lra: float = 11.0, confirm: bool,
    ) -> dict:
        """`confirm` muss vom Aufrufer NUR True sein, nachdem der Nutzer die
        Vorschau tatsaechlich bestaetigt hat (Prinzip #17, §44). Erzeugt
        IMMER eine NEUE Datei - das Original wird nie veraendert (ADR-0010)."""
        return self._post(
            f"/media/{media_id}/loudness/normalize/apply",
            json={
                "target_lufs": target_lufs,
                "target_true_peak_dbtp": target_true_peak_dbtp,
                "target_lra": target_lra,
                "confirm": confirm,
            },
        )

    # --- Phase 3: Audio-Cutter (§18, ADR-0011) ---------------------------------

    def get_cutter_waveform_bytes(self, media_id: int) -> bytes:
        """Liefert das Waveform-PNG. Rein lesend (Prinzip #4/#5) - wirft bei
        Fehlern (z.B. kein lesbarer Audio-Stream) eine `GenesisAPIError`
        statt stillschweigend ein leeres Bild zu liefern."""
        try:
            resp = self._client.get(f"/media/{media_id}/cutter/waveform")
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    def list_cuts(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/cutter")

    def preview_cut(
        self, media_id: int, *, start_seconds: float, end_seconds: float,
        export_format: str, fade_in_seconds: float = 0.0, fade_out_seconds: float = 0.0,
    ) -> dict:
        """Reine Berechnung - erzeugt keine Datei (Prinzip #4/#5)."""
        return self._post(
            f"/media/{media_id}/cutter/preview",
            json={
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "export_format": export_format,
                "fade_in_seconds": fade_in_seconds,
                "fade_out_seconds": fade_out_seconds,
            },
        )

    def apply_cut(
        self, media_id: int, *, start_seconds: float, end_seconds: float,
        export_format: str, fade_in_seconds: float = 0.0, fade_out_seconds: float = 0.0,
        confirm: bool,
    ) -> dict:
        """`confirm` muss vom Aufrufer NUR True sein, nachdem der Nutzer die
        Vorschau tatsaechlich bestaetigt hat (Prinzip #17, §44). Erzeugt
        IMMER eine NEUE Datei - das Original wird nie veraendert (ADR-0011)."""
        return self._post(
            f"/media/{media_id}/cutter/apply",
            json={
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "export_format": export_format,
                "fade_in_seconds": fade_in_seconds,
                "fade_out_seconds": fade_out_seconds,
                "confirm": confirm,
            },
        )

    # --- Phase 3: Konvertierungs-Werkzeug (nav.convert) ------------------------

    def list_conversions(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/convert")

    def preview_conversion(
        self, media_id: int, *, target_format: str, bitrate_kbps: int | None = None,
    ) -> dict:
        """Reine Berechnung - erzeugt keine Datei (Prinzip #4/#5)."""
        return self._post(
            f"/media/{media_id}/convert/preview",
            json={"target_format": target_format, "bitrate_kbps": bitrate_kbps},
        )

    def apply_conversion(
        self, media_id: int, *, target_format: str, bitrate_kbps: int | None = None, confirm: bool,
    ) -> dict:
        """`confirm` muss vom Aufrufer NUR True sein, nachdem der Nutzer die
        Vorschau tatsaechlich bestaetigt hat (Prinzip #17, §44). Erzeugt
        IMMER eine NEUE Datei - das Original wird nie veraendert."""
        return self._post(
            f"/media/{media_id}/convert/apply",
            json={"target_format": target_format, "bitrate_kbps": bitrate_kbps, "confirm": confirm},
        )

    # --- Phase 3: Audio-Fingerprinting (Vorstufe fuer §21) ----------------------

    def compute_fingerprint(self, media_id: int) -> dict:
        """Analyse (kein `confirm` noetig) - veraendert keine Mediendatei."""
        return self._post(f"/media/{media_id}/fingerprint")

    def get_fingerprint(self, media_id: int) -> dict | None:
        return self._get(f"/media/{media_id}/fingerprint")

    # --- Phase 3: Qualitätsanalyse (§20, ADR-0014) -------------------------------

    def analyze_quality(self, media_id: int) -> dict:
        """Analyse (kein `confirm` noetig) - veraendert keine Mediendatei,
        Ergebnis ist ein VERDACHT, kein Fakt (§20)."""
        return self._post(f"/media/{media_id}/quality/analyze")

    def get_quality(self, media_id: int) -> dict | None:
        return self._get(f"/media/{media_id}/quality")

    # --- Phase 3: Duplikaterkennung (§21, ADR-0013) -----------------------------

    def scan_duplicates(self, kind: str | None = None) -> list[dict]:
        """Reine Analyse (Prinzip #4/#5) - veraendert/loescht KEINE Mediendatei.
        `kind` schraenkt optional auf eine Medienart ein (z.B. "music")."""
        return self._post("/duplicates/scan", json={"kind": kind})

    def list_duplicates(self, reviewed: bool | None = None) -> list[dict]:
        params = {} if reviewed is None else {"reviewed": reviewed}
        return self._get("/duplicates", params=params)

    def review_duplicate_group(self, group_id: int) -> dict:
        return self._post(f"/duplicates/{group_id}/review")

    def unreview_duplicate_group(self, group_id: int) -> dict:
        return self._post(f"/duplicates/{group_id}/unreview")

    # --- Phase 4: Hörbücher & Kapitel (§23, ADR-0015) ----------------------------

    def get_audiobook_tags_preview(self, media_id: int) -> dict:
        """Vorschau - liest bereits eingebettete Tags (kein `confirm` nötig,
        veraendert nichts)."""
        return self._get(f"/media/{media_id}/audiobook/tags")

    def apply_audiobook_tags(self, media_id: int, *, confirm: bool) -> dict:
        return self._post(
            f"/media/{media_id}/audiobook/tags/apply", json={"confirm": confirm}
        )

    def get_audiobook(self, media_id: int) -> dict | None:
        return self._get(f"/media/{media_id}/audiobook")

    def list_chapters(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/chapters")

    def detect_chapters_preview(self, media_id: int) -> dict:
        return self._post(f"/media/{media_id}/chapters/detect")

    def detect_chapters_apply(self, media_id: int, *, confirm: bool) -> dict:
        return self._post(
            f"/media/{media_id}/chapters/detect/apply", json={"confirm": confirm}
        )

    def generate_chapters_preview(self, media_id: int, *, interval_minutes: float) -> dict:
        return self._post(
            f"/media/{media_id}/chapters/generate",
            json={"interval_minutes": interval_minutes},
        )

    def generate_chapters_apply(
        self, media_id: int, *, interval_minutes: float, confirm: bool
    ) -> dict:
        return self._post(
            f"/media/{media_id}/chapters/generate/apply",
            json={"interval_minutes": interval_minutes, "confirm": confirm},
        )

    def rename_chapter(self, media_id: int, chapter_id: int, *, title: str, confirm: bool) -> dict:
        return self._patch(
            f"/media/{media_id}/chapters/{chapter_id}",
            json={"title": title, "confirm": confirm},
        )

    def export_chapters_text(self, media_id: int, *, fmt: str) -> str:
        """Reine Lesefunktion - kein `confirm` nötig (wie andere Exporte)."""
        try:
            resp = self._client.get(
                f"/media/{media_id}/chapters/export", params={"format": fmt}
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    # --- Phase 5: Filme & Serien (§24, ADR-0016) --------------------------------

    def get_video_tags_preview(self, media_id: int) -> dict:
        """Vorschau - liest bereits eingebettete Tags (kein `confirm` nötig,
        veraendert nichts)."""
        return self._get(f"/media/{media_id}/video/tags")

    def detect_episode_preview(self, media_id: int) -> dict:
        """Film-vs-Episode-Erkennung (Tags + Dateipfad-Muster) - reine
        Analyse, kein `confirm` nötig."""
        return self._post(f"/media/{media_id}/video/episode-detection")

    def apply_movie_metadata(self, media_id: int, *, confirm: bool) -> dict:
        return self._post(f"/media/{media_id}/movie/apply", json={"confirm": confirm})

    def get_movie(self, media_id: int) -> dict | None:
        return self._get(f"/media/{media_id}/movie")

    def apply_episode_metadata(self, media_id: int, *, confirm: bool) -> dict:
        return self._post(f"/media/{media_id}/episode/apply", json={"confirm": confirm})

    def get_episode(self, media_id: int) -> dict | None:
        return self._get(f"/media/{media_id}/episode")

    # --- Phase 6: KI-Metadaten/-Suche/-Musik (§25/§26/§27, ADR-0017) -----------

    def get_ai_status(self) -> dict:
        """Transparenz ueber den aktiven KI-Provider (lokal/offline,
        erreichbar, Modell) - wird in der UI immer sichtbar angezeigt."""
        return self._get("/ai/status")

    def suggest_ai_metadata(self, media_id: int, fields: list[str] | None = None) -> list[dict]:
        """Reine Vorschau - kein `confirm` noetig, nichts wird gespeichert."""
        return self._post(f"/media/{media_id}/ai/suggest", json={"fields": fields})

    def apply_ai_metadata(self, media_id: int, accepted: list[dict], *, confirm: bool) -> dict:
        return self._post(
            f"/media/{media_id}/ai/apply", json={"accepted": accepted, "confirm": confirm}
        )

    def get_ai_metadata(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/ai/metadata")

    def get_ai_music(self, media_id: int) -> dict | None:
        return self._get(f"/media/{media_id}/ai-music")

    def apply_ai_music(self, media_id: int, data: dict, *, confirm: bool) -> dict:
        payload = dict(data)
        payload["confirm"] = confirm
        return self._post(f"/media/{media_id}/ai-music/apply", json=payload)

    def reindex_ai_search(self) -> dict:
        return self._post("/ai/search/reindex")

    def ai_semantic_search(self, query: str, top_k: int = 20) -> dict:
        return self._post("/ai/search", json={"query": query, "top_k": top_k})

    # --- Phase 7: Voice Studio (§28/§29, ADR-0018) -----------------------------

    def get_voice_status(self) -> dict:
        """Transparenz ueber die aktive TTS-Engine (lokal/offline,
        erreichbar) - wird in der UI immer sichtbar angezeigt (§28)."""
        return self._get("/voice/status")

    def get_voice_engines(self) -> list[dict]:
        """Unverbindlicher Katalog bekannter Engines fuer das
        Anlage-Formular (Vorschlagswerte, kein Automatismus)."""
        return self._get("/voice/engines")["engines"]

    def list_voice_profiles(self) -> list[dict]:
        return self._get("/voice/profiles")["profiles"]

    def get_voice_profile(self, profile_id: int) -> dict:
        return self._get(f"/voice/profiles/{profile_id}")

    def create_voice_profile(self, data: dict, *, confirm: bool) -> dict:
        payload = dict(data)
        payload["confirm"] = confirm
        return self._post("/voice/profiles", json=payload)

    def delete_voice_profile(self, profile_id: int, *, confirm: bool, confirm_name: str) -> dict:
        return self._delete(
            f"/voice/profiles/{profile_id}",
            json={"confirm": confirm, "confirm_name": confirm_name},
        )

    def synthesize_voice(
        self, profile_id: int, text: str, *, export_format: str = "wav", confirm: bool
    ) -> dict:
        return self._post(
            f"/voice/profiles/{profile_id}/synthesize",
            json={"text": text, "export_format": export_format, "confirm": confirm},
        )

    def test_voice_profile(self, profile_id: int, *, confirm: bool) -> dict:
        return self._post(f"/voice/profiles/{profile_id}/test", json={"confirm": confirm})

    def list_voice_syntheses(self, profile_id: int | None = None) -> list[dict]:
        params = {"profile_id": profile_id} if profile_id is not None else None
        return self._get("/voice/syntheses", params=params)["syntheses"]

    def get_voice_synthesis_audio(self, synthesis_id: int) -> bytes:
        try:
            resp = self._client.get(f"/voice/syntheses/{synthesis_id}/audio")
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    # -- Download-/Import-Center (§30-§32, ADR-0019) ------------------------
    # §31-Workflow: detect/availability/metadata/options sind reine
    # Vorschau-Aufrufe (kein confirm), erst import/import_local_file fuehrt
    # tatsaechlich etwas aus (confirm=True Pflicht).

    def list_download_providers(self) -> dict:
        return self._get("/download/providers")

    def detect_download_source(self, url: str) -> dict:
        return self._post("/download/detect", json={"url": url})

    def check_download_availability(self, url: str) -> dict:
        return self._post("/download/availability", json={"url": url})

    def fetch_download_metadata(self, url: str) -> dict:
        return self._post("/download/metadata", json={"url": url})

    def list_download_options(self, url: str) -> dict:
        return self._post("/download/options", json={"url": url})

    def import_download(self, url: str, *, option_id: str = "default", confirm: bool) -> dict:
        return self._post(
            "/download/import",
            json={"url": url, "option_id": option_id, "confirm": confirm},
        )

    def import_local_file(self, path: str, *, confirm: bool) -> dict:
        return self._post("/import/local-file", json={"path": path, "confirm": confirm})

    def list_media_sources(self, media_id: int) -> list[dict]:
        return self._get(f"/media/{media_id}/sources")["sources"]

    def _get(self, path: str, **kwargs):
        try:
            resp = self._client.get(path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    def _post(self, path: str, **kwargs):
        try:
            resp = self._client.post(path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    def _patch(self, path: str, **kwargs):
        try:
            resp = self._client.patch(path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    def _delete(self, path: str, **kwargs):
        try:
            resp = self._client.request("DELETE", path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise _build_api_error(exc) from exc
        except httpx.HTTPError as exc:
            raise GenesisAPIError(str(exc)) from exc

    # --- §35/§36 Job-Warteschlange -----------------------------------------

    def list_jobs(self, limit: int = 50) -> list[dict]:
        return self._get("/jobs", params={"limit": limit})

    def get_job(self, job_id: str) -> dict:
        return self._get(f"/jobs/{job_id}")

    def pause_job(self, job_id: str) -> dict:
        return self._post(f"/jobs/{job_id}/pause")

    def resume_job(self, job_id: str) -> dict:
        return self._post(f"/jobs/{job_id}/resume")

    def cancel_job(self, job_id: str) -> dict:
        return self._post(f"/jobs/{job_id}/cancel")

    # --- §37 Fehler-Center ---------------------------------------------------

    def list_errors(self, limit: int = 100, unresolved_only: bool = False) -> list[dict]:
        return self._get(
            "/errors", params={"limit": limit, "unresolved_only": unresolved_only}
        )["errors"]

    def resolve_error(self, error_id: str) -> dict:
        return self._post(f"/errors/{error_id}/resolve")

    # --- §38 Diagnostics -----------------------------------------------------

    def run_diagnostics(self) -> dict:
        return self._get("/diagnostics")

    # --- §40 Backup ------------------------------------------------------------

    def list_backups(self, backup_type: str | None = None, limit: int = 50) -> list[dict]:
        params = {"limit": limit}
        if backup_type:
            params["backup_type"] = backup_type
        return self._get("/backup", params=params)["backups"]

    def create_db_backup(self) -> dict:
        return self._post("/backup/db")

    def create_config_backup(self) -> dict:
        return self._post("/backup/config")

    def restore_backup(self, backup_id: int, *, confirm: bool) -> dict:
        return self._post(f"/backup/{backup_id}/restore", json={"confirm": confirm})

    # --- §34 Plugin-System -----------------------------------------------------

    def list_plugins(self) -> dict:
        return self._get("/plugins")

    def reload_plugins(self) -> dict:
        return self._post("/plugins/reload")


def _build_api_error(exc: httpx.HTTPStatusError) -> GenesisAPIError:
    """Baut aus einer HTTP-Fehlerantwort eine `GenesisAPIError`. Erkennt
    BEIDE vom Core Service verwendeten Fehlerformate (§37):
    1. `{"detail": "..."}` - normale, erwartete Validierungsfehler
       (HTTPException aus einem einzelnen Endpunkt, z.B. 404/403/422).
    2. `{"error_id", "message", "solution_hint", ...}` - ein echter,
       unerwarteter Fehler, den der globale Exception-Handler abgefangen
       hat. Nur in diesem Fall gibt es eine nachschlagbare Fehler-ID, die
       im Fehler-Center wiederzufinden ist."""
    try:
        body = exc.response.json()
    except ValueError:
        return GenesisAPIError(str(exc))

    if isinstance(body, dict) and "error_id" in body:
        message = body.get("message") or str(exc)
        return GenesisAPIError(
            message, error_id=body.get("error_id"), solution_hint=body.get("solution_hint")
        )

    if isinstance(body, dict) and body.get("detail"):
        return GenesisAPIError(str(body["detail"]))

    return GenesisAPIError(str(exc))
