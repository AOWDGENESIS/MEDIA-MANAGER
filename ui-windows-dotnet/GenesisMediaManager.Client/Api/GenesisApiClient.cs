using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace GenesisMediaManager.Client.Api;

/// <summary>
/// Wird geworfen, wenn die Core-API einen Fehlerstatuscode liefert. Extrahiert
/// FastAPIs <c>{"detail": "..."}</c>-Feld, damit die UI dieselbe klare
/// deutschsprachige Fehlermeldung anzeigen kann wie der Python-Client
/// (siehe ui-reference-pyside/genesis_ui/api_client.py::_extract_detail).
/// </summary>
public sealed class GenesisApiException : Exception
{
    public GenesisApiException(string message) : base(message) { }
}

/// <summary>
/// Duenner HTTP-Client zur lokalen GENESIS Core API (siehe ARCHITECTURE.md,
/// ADR-0001). Enthaelt bewusst KEINE Fachlogik - identisch zum Python-
/// Pendant in ui-reference-pyside/genesis_ui/api_client.py.
/// </summary>
public sealed partial class GenesisApiClient : IDisposable
{
    private readonly HttpClient _http;

    // KRITISCH (Deep-Review-Fund, Sitzung 3): Die Core-API liefert/erwartet
    // ausschliesslich snake_case-JSON-Feldnamen (FastAPI-Standard, z.B.
    // "job_id", "absolute_path"), waehrend die C#-Records hier aus
    // Sprachkonventionsgruenden PascalCase verwenden (z.B. "JobId"). OHNE
    // eine explizite Namenszuordnung matcht System.Text.Json diese Namen
    // NICHT automatisch - es wirft dabei auch KEINEN Fehler, sondern laesst
    // die betroffenen Properties still auf ihrem Default-Wert (null/0/false)
    // stehen. Das waere ein klassischer stiller Fehler (Verstoss gegen
    // §37 "keine stillen Fehlschlaege") und haette JEDE Antwort dieses
    // Clients unbemerkt kaputt gemacht. Deshalb MUSS jeder Serialisierungs-/
    // Deserialisierungsaufruf in dieser Klasse explizit `JsonOptions`
    // uebergeben - niemals die parameterlosen Ueberladungen verwenden.
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    // Datei-/Ordnername der API-Token-Datei. ADR-0006 (Deep Review Sitzung
    // 2): die lokale API verlangt seit dieser Aenderung ein Shared-Secret-
    // Token (Header X-Genesis-Token), um Drive-by-Localhost-/JSON-CSRF-
    // Anfragen von im Browser geoeffneten Fremdseiten abzuwehren (blosses
    // Binden an 127.0.0.1 reicht dafuer NICHT aus). Muss synchron bleiben
    // mit genesis_core.config.default_data_dir() und
    // genesis_core.api.security.TOKEN_FILENAME (Python-Seite).
    private const string TokenFileName = "api_token.txt";

    public GenesisApiClient(string baseUrl = "http://127.0.0.1:8420")
    {
        _http = new HttpClient { BaseAddress = new Uri(baseUrl) };
        var token = TryReadApiToken();
        if (!string.IsNullOrEmpty(token))
        {
            _http.DefaultRequestHeaders.Add("X-Genesis-Token", token);
        }
        // Kein hartes Scheitern, falls die Token-Datei (noch) fehlt: der
        // Core Service liefert bei jedem geschuetzten Aufruf ohnehin einen
        // klaren 401-Fehler; /health bleibt bewusst ungeschuetzt erreichbar.
    }

    private static string? TryReadApiToken()
    {
        try
        {
            var dataDir = ResolveDataDir();
            var tokenPath = Path.Combine(dataDir, TokenFileName);
            return File.Exists(tokenPath) ? File.ReadAllText(tokenPath).Trim() : null;
        }
        catch (IOException)
        {
            return null;
        }
    }

    private static string ResolveDataDir()
    {
        var envOverride = Environment.GetEnvironmentVariable("GENESIS_DATA_DIR");
        if (!string.IsNullOrEmpty(envOverride)) return envOverride;

        var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        return Path.Combine(appData, "GenesisMediaManager");
    }

    private static async Task EnsureSuccessWithDetailAsync(HttpResponseMessage response, CancellationToken ct)
    {
        if (response.IsSuccessStatusCode) return;

        string? detail = null;
        try
        {
            var body = await response.Content.ReadAsStringAsync(ct);
            if (!string.IsNullOrWhiteSpace(body))
            {
                using var doc = JsonDocument.Parse(body);
                if (doc.RootElement.TryGetProperty("detail", out var detailElement))
                {
                    detail = detailElement.ToString();
                }
            }
        }
        catch (JsonException)
        {
            // Antwort war kein JSON - faellt unten auf den rohen Statuscode zurueck.
        }

        throw new GenesisApiException(
            detail ?? $"Core-API-Fehler: HTTP {(int)response.StatusCode} {response.ReasonPhrase}");
    }

    public async Task<HealthResponse?> GetHealthAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<HealthResponse>("/health", JsonOptions, ct);

    public async Task<DashboardSummary?> GetDashboardSummaryAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<DashboardSummary>("/dashboard/summary", JsonOptions, ct);

    /// <summary>
    /// Liest die volle Core-Konfiguration (GET /settings, token-geschuetzt).
    /// Die UI nutzt davon aktuell ausschliesslich <c>General.Language</c>
    /// zum Setzen der Oberflaechensprache beim Start (§53) - schreibender
    /// Zugriff auf Einstellungen ist erst Phase 9 (Einstellungen-Ansicht)
    /// vorgesehen, siehe identischer Hinweis in
    /// ui-reference-pyside/genesis_ui/api_client.py::get_settings.
    /// Unbekannte JSON-Felder (z.B. "loudness", "providers", ...) werden
    /// von System.Text.Json standardmaessig ignoriert, nicht als Fehler
    /// behandelt - das Record hier muss daher NICHT die volle Config
    /// abbilden.
    /// </summary>
    // ConfigureAwait(false) ist hier (anders als sonst im Projekt ueblich)
    // bewusst noetig: MainWindow.ApplyLanguageFromSettings() ruft diese
    // Methode synchron per ".GetAwaiter().GetResult()" auf dem UI-Thread
    // auf (noch bevor InitializeComponent() lief). OHNE ConfigureAwait(false)
    // wuerde die interne Fortsetzung versuchen, auf genau diesen (dann
    // blockierten) UI-Thread zurueckzukehren - klassisches Sync-over-
    // Async-Deadlock (Deep-Review-Fund waehrend der Fehlersuche zum
    // MissingMethodException-Absturz, siehe App.xaml.cs). Andere Aufrufer
    // dieser Methode (normales "await" in async-void-Handlern) sind davon
    // nicht betroffen - ConfigureAwait wirkt nur auf Fortsetzungen
    // INNERHALB dieser Methode, nicht auf das Verhalten des Aufrufers.
    public async Task<SettingsResponse?> GetSettingsAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<SettingsResponse>("/settings", JsonOptions, ct)
            .ConfigureAwait(false);

    /// <summary>
    /// Schreibender Zugriff auf die Konfiguration (schliesst Gap A/§55 auf
    /// Python-Seite; hier erster Schritt der Gap-K-Parity-Arbeit).
    /// <paramref name="updates"/> folgt derselben verschachtelten Struktur
    /// wie die Antwort von <see cref="GetSettingsAsync"/>, z.B.
    /// <c>{"ai": {"enabled": true}}</c> - bewusst ein loses
    /// <c>Dictionary&lt;string, object&gt;</c> mit EXPLIZITEN snake_case-
    /// Schluesseln statt eines reflektierten Records: bei einem
    /// Dictionary&lt;string, object&gt; greift `JsonNamingPolicy` NICHT auf
    /// die Schluessel (nur auf echte Record-/Klassen-Properties) - wuerde
    /// man hier PascalCase-Schluessel verwenden, kaeme am Core-Service ein
    /// stillschweigend ignoriertes, falsch benanntes Feld an (siehe
    /// Klassenkommentar oben zu `JsonOptions`).
    /// <paramref name="confirm"/> darf NUR <c>true</c> sein, NACHDEM der
    /// Nutzer die Aenderung in der UI explizit bestaetigt hat (Prinzip #17,
    /// §44) - identisch zum Verhalten in
    /// ui-reference-pyside/genesis_ui/views/settings_view.py::_on_save_clicked.
    /// </summary>
    public async Task<SettingsUpdateResult?> UpdateSettingsAsync(
        Dictionary<string, object> updates, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PatchAsJsonAsync(
            "/settings", new SettingsUpdateRequest(updates, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<SettingsUpdateResult>(JsonOptions, ct);
    }

    public async Task<MediaListResponse?> ListMediaAsync(
        string? kind = null, string? search = null, int limit = 200, int offset = 0,
        MediaSearchFilters? filters = null, CancellationToken ct = default)
    {
        var query = $"/media?limit={limit}&offset={offset}";
        if (!string.IsNullOrWhiteSpace(kind)) query += $"&kind={Uri.EscapeDataString(kind)}";
        if (!string.IsNullOrWhiteSpace(search)) query += $"&search={Uri.EscapeDataString(search)}";
        if (filters is not null) query += filters.ToQueryString();
        return await _http.GetFromJsonAsync<MediaListResponse>(query, JsonOptions, ct);
    }

    public async Task<MediaDetail?> GetMediaDetailAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<MediaDetail>($"/media/{mediaId}", JsonOptions, ct);

    // --- Erweiterung des zentralen Detailpanels (Gap K, dritter
    // inkrementeller Schritt) - spiegelt die vier zusaetzlichen Abrufe in
    // ui-reference-pyside/genesis_ui/views/media_table.py::
    // _on_selection_changed (Qualitaet/Loudness/KI/Quelle), siehe §59. Alle
    // vier sind bewusst rein lesend (keine Confirm-Pflicht) - identisch zum
    // Charakter der Python-Aufrufe. --------------------------------------

    /// <summary>Liefert <c>null</c>, wenn fuer dieses Medium noch keine
    /// Qualitaetsanalyse durchgefuehrt wurde (die Core-API liefert dafuer
    /// bewusst ein JSON-<c>null</c> mit Status 200, keinen 404 - kein
    /// Fehlerfall, sondern "noch nicht analysiert").</summary>
    public async Task<QualityInfo?> GetQualityAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<QualityInfo?>($"/media/{mediaId}/quality", JsonOptions, ct);

    /// <summary>Volle Mess-/Normalisierungshistorie, neueste zuerst (§44).</summary>
    public async Task<List<LoudnessEntry>> ListLoudnessAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<List<LoudnessEntry>>($"/media/{mediaId}/loudness", JsonOptions, ct)
        ?? new List<LoudnessEntry>();

    public async Task<List<AiMetadataEntry>> GetAiMetadataAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<List<AiMetadataEntry>>($"/media/{mediaId}/ai/metadata", JsonOptions, ct)
        ?? new List<AiMetadataEntry>();

    public async Task<List<MediaSourceEntry>> ListMediaSourcesAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.GetFromJsonAsync<MediaSourcesResponse>(
            $"/media/{mediaId}/sources", JsonOptions, ct);
        return response?.Sources ?? new List<MediaSourceEntry>();
    }

    public async Task<ScanResponse?> TriggerScanAsync(IEnumerable<string> directories, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/scan", new { directories }, JsonOptions, ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<ScanResponse>(JsonOptions, ct);
    }

    // --- Phase 2: Metadaten-Vorschlaege (§10/§11/§17) -----------------------

    public async Task<List<MetadataSuggestion>> GetMetadataSuggestionsAsync(
        int mediaId, CancellationToken ct = default)
    {
        var response = await _http.GetAsync($"/media/{mediaId}/metadata-suggestions", ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        var parsed = await response.Content.ReadFromJsonAsync<MetadataSuggestionsResponse>(
            JsonOptions, ct);
        return parsed?.Suggestions ?? new List<MetadataSuggestion>();
    }

    /// <summary>
    /// <paramref name="confirm"/> darf vom Aufrufer NUR <c>true</c> sein,
    /// NACHDEM der Nutzer den Vorschlag in der UI tatsaechlich bestaetigt
    /// hat (Prinzip #17, §44) - kein automatisches Uebernehmen.
    /// </summary>
    public async Task<ApplyMetadataSuggestionResult?> ApplyMetadataSuggestionAsync(
        int mediaId, RecordingMatch match, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/metadata-suggestions/apply",
            new ApplyMetadataSuggestionRequest(match, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ApplyMetadataSuggestionResult>(
            JsonOptions, ct);
    }

    // --- Phase 2: Umbenennen (§15/§16) ---------------------------------------

    public async Task<List<RenamePreviewItem>> RenamePreviewAsync(
        IEnumerable<int> mediaFileIds, string template, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            "/rename/preview", new RenamePreviewRequest(mediaFileIds.ToList(), template), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        var parsed = await response.Content.ReadFromJsonAsync<RenamePreviewResponse>(
            JsonOptions, ct);
        return parsed?.Items ?? new List<RenamePreviewItem>();
    }

    /// <summary>
    /// <paramref name="confirm"/> darf vom Aufrufer NUR <c>true</c> sein,
    /// NACHDEM der Nutzer die zuvor angezeigte Vorschau tatsaechlich
    /// bestaetigt hat (Prinzip #16/#17, §44).
    /// </summary>
    public async Task<RenameApplyResponse?> RenameApplyAsync(
        IEnumerable<int> mediaFileIds, string template, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            "/rename/apply", new RenameApplyRequest(mediaFileIds.ToList(), template, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<RenameApplyResponse>(JsonOptions, ct);
    }

    // --- Phase 2: Artwork (§22) -----------------------------------------------

    /// <summary>Liefert (Bilddaten, MIME-Typ), oder <c>null</c>, wenn kein
    /// eingebettetes Artwork existiert (404 ist hier ein normaler Fall, kein
    /// Fehler - kein erfundenes Platzhalterbild, Prinzip #16).</summary>
    public async Task<(byte[] Data, string MimeType)?> GetArtworkBytesAsync(
        int mediaId, CancellationToken ct = default)
    {
        var response = await _http.GetAsync($"/media/{mediaId}/artwork", ct);
        if (response.StatusCode == System.Net.HttpStatusCode.NotFound) return null;
        await EnsureSuccessWithDetailAsync(response, ct);
        var bytes = await response.Content.ReadAsByteArrayAsync(ct);
        var mimeType = response.Content.Headers.ContentType?.MediaType ?? "image/jpeg";
        return (bytes, mimeType);
    }

    public async Task<FetchArtworkOnlineResult?> FetchArtworkOnlineAsync(
        int mediaId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync(
            $"/media/{mediaId}/artwork/fetch-online",
            new StringContent("{}", System.Text.Encoding.UTF8, "application/json"), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<FetchArtworkOnlineResult>(JsonOptions, ct);
    }

    /// <summary>
    /// <paramref name="confirm"/> darf vom Aufrufer NUR <c>true</c> sein,
    /// NACHDEM der Nutzer das Einbetten explizit bestaetigt hat (Prinzip
    /// #17, §44) - das Einbetten veraendert die Mediendatei selbst.
    /// </summary>
    public async Task<EmbedArtworkResult?> EmbedArtworkAsync(
        int mediaId, int artworkId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/artwork/embed", new EmbedArtworkRequest(artworkId, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<EmbedArtworkResult>(JsonOptions, ct);
    }

    public void Dispose() => _http.Dispose();
}

public sealed record HealthResponse(
    string Status, string Version, bool SafeTestMode, string AiProvider, bool AiAvailable);

public sealed record DashboardSummary(
    Dictionary<string, int> CountsByKind, int Total, int MissingFiles,
    int NotYetAnalyzed, int RunningJobs);

// --- GET/PATCH /settings (nur die fuer die UI aktuell relevanten Felder;
// volles Schema siehe core/genesis_core/config/__init__.py::Settings -
// Medienordner/Sprachausgabe/Download-Center sind fuer die WPF-Oberflaeche
// noch nicht abgebildet, siehe docs/GAP_ANALYSIS.md Gap K) -------------

public sealed record GeneralSettings(
    string Language, bool SafeTestMode, bool RequireConfirmationForBulkChanges);

public sealed record PathsSettingsInfo(List<string> MediaFolders);

public sealed record AiSettingsInfo(
    bool Enabled, string Provider, string Endpoint, string Model,
    double TimeoutSeconds, string EmbeddingModel);

public sealed record VoiceSettingsInfo(bool Enabled, string Provider, string DefaultExportFormat);

public sealed record LoudnessSettingsInfo(
    double TargetLufs, double TargetTruePeakDbtp, bool OverwriteOriginals);

public sealed record DownloadSettingsInfo(
    bool Enabled, bool EnableYoutube, bool EnableTiktok, string? DownloadsDir,
    int MaxDownloadSizeMb, int MinFreeDiskMb, double RequestTimeoutSeconds);

public sealed record PrivacySettingsInfo(
    bool TelemetryEnabled, bool AllowCloudAi, bool AllowAutomaticDownloads,
    bool AllowAutomaticDeletion, bool AllowAutomaticOverwrite);

/// <summary>
/// §10/§11, Gap-Analyse I - betrifft die ONLINE-Metadatenabgleich-Provider
/// (MusicBrainz/AcoustID/Cover Art Archive), zu unterscheiden von den
/// Download-/Import-Providern (YouTube/TikTok/...), die bereits ueber
/// <see cref="DownloadSettingsInfo"/> abgebildet sind. Siehe
/// ui-reference-pyside/genesis_ui/views/providers_view.py.
/// </summary>
public sealed record MetadataSettingsInfo(
    bool Enabled, bool MusicbrainzEnabled, bool AcoustidEnabled, string AcoustidApiKey,
    bool CoverartarchiveEnabled, string ContactEmail, double RequestTimeoutSeconds,
    double MinConfidenceForSuggestion);

public sealed record SettingsResponse(
    GeneralSettings General, PathsSettingsInfo Paths, AiSettingsInfo Ai, VoiceSettingsInfo Voice,
    LoudnessSettingsInfo Loudness, DownloadSettingsInfo Download, PrivacySettingsInfo Privacy,
    MetadataSettingsInfo Metadata);

public sealed record SettingsUpdateRequest(Dictionary<string, object> Updates, bool Confirm);

public sealed record SettingsUpdateResult(SettingsResponse Settings, bool RestartRequired, string JobId);

public sealed record MediaItem(
    int Id, string AbsolutePath, string Directory, string Filename, string Extension,
    string Kind, long SizeBytes, string? Mtime, string? ContentHashSha256, bool IsMissing,
    string? LastScannedAt);

public sealed record MediaListResponse(int Total, List<MediaItem> Items);

public sealed record TechnicalMetadata(
    string? ContainerFormat, string? AudioCodec, string? VideoCodec, int? BitrateKbps,
    int? SampleRateHz, int? Channels, double? DurationSeconds, int? ResolutionWidth,
    int? ResolutionHeight, double? Fps, bool? Hdr, int? ChaptersCount);

public sealed record TrackInfo(
    int Id, string? Title, int? AlbumId, string? AlbumArtist, int? TrackNumber,
    int? DiscNumber, int? Year, string? Source, double? Confidence, bool IsUserConfirmed);

public sealed record MediaDetail(
    int Id, string AbsolutePath, string Directory, string Filename, string Extension,
    string Kind, long SizeBytes, string? Mtime, string? ContentHashSha256, bool IsMissing,
    string? LastScannedAt, bool FileExistsOnDisk, TechnicalMetadata? Technical,
    TrackInfo? Track, bool HasEmbeddedArtwork);

// --- Erweiterung des zentralen Detailpanels (§59: Qualitaet/Loudness/KI/
// Quelle) - spiegelt core/genesis_core/api/app.py::get_quality/
// list_loudness/ai_metadata_endpoint/list_media_sources_endpoint. --------

public sealed record QualityInfo(
    int MediaFileId, bool SuspectedUpscale, bool SuspectedTranscode, bool SuspectedCorruption,
    bool SuspectedTruncation, List<string> Notes);

public sealed record LoudnessEntry(
    int Id, int MediaFileId, double? IntegratedLufs, double? TruePeakDbtp, double? LoudnessRangeLu,
    double? TargetLufsUsed, double? TargetTruePeakDbtpUsed, bool Normalized,
    string? NormalizedOutputPath, string? MeasuredAt);

public sealed record AiMetadataEntry(
    int Id, int MediaFileId, string FieldName, string FieldValue, bool IsAiGenerated,
    string? ModelName, string? ModelVersion, double? Confidence, string? Prompt,
    string? CreatedAt, bool AcceptedByUser);

public sealed record MediaSourceEntry(
    int Id, int MediaFileId, string? SourceName, string? ProviderName, string? OriginalUrl,
    string? OriginalId, string? ImportedAt, string? ImportMethod);

public sealed record MediaSourcesResponse(List<MediaSourceEntry> Sources);

public sealed record ScanResponse(string JobId, object Result);

// --- Phase 2: Metadaten-Vorschlaege --------------------------------------

public sealed record RecordingMatch(
    string Provider, double Confidence, string? Title = null, string? Artist = null,
    string? Album = null, int? Year = null, int? TrackNumber = null,
    string? MusicbrainzRecordingId = null, string? MusicbrainzReleaseId = null,
    string? MusicbrainzArtistId = null);

public sealed record ExistingTagsInfo(string? Title, string? Artist, string? Album);

public sealed record MetadataSuggestion(string Method, RecordingMatch Match, ExistingTagsInfo ExistingTags);

public sealed record MetadataSuggestionsResponse(int MediaId, List<MetadataSuggestion> Suggestions);

public sealed record ApplyMetadataSuggestionRequest(RecordingMatch Match, bool Confirm);

public sealed record ApplyMetadataSuggestionResult(string JobId, TrackInfo Track);

// --- Phase 2: Umbenennen --------------------------------------------------

public sealed record RenamePreviewRequest(List<int> MediaFileIds, string Template);

public sealed record RenamePreviewItem(
    int MediaFileId, string OldAbsolutePath, string NewAbsolutePath, List<string> EmptyFields,
    bool HasConflict, string? ConflictReason, bool IsIdentical, string? TemplateError,
    bool IsActionable);

public sealed record RenamePreviewResponse(List<RenamePreviewItem> Items);

public sealed record RenameApplyRequest(List<int> MediaFileIds, string Template, bool Confirm);

public sealed record RenameApplyResultItem(
    int MediaFileId, bool Applied, string OldAbsolutePath, string NewAbsolutePath, string? Reason);

public sealed record RenameApplyResponse(string JobId, List<RenameApplyResultItem> Results);

// --- Phase 2: Artwork ------------------------------------------------------

public sealed record FetchArtworkOnlineResult(int ArtworkId, string CachedPath, string MimeType);

public sealed record EmbedArtworkRequest(int ArtworkId, bool Confirm);

public sealed record EmbedArtworkResult(string JobId, bool Embedded);

