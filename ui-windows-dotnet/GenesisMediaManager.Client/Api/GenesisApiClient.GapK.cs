using System.Net.Http;
using System.Net.Http.Json;

namespace GenesisMediaManager.Client.Api;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - zweiter Teil von
/// <see cref="GenesisApiClient"/> (<c>partial class</c>, siehe
/// Api/GenesisApiClient.cs fuer den ersten Teil/die gemeinsamen Felder
/// <c>_http</c>/<c>JsonOptions</c>/<c>EnsureSuccessWithDetailAsync</c>).
/// Spiegelt alle restlichen Methoden aus
/// ui-reference-pyside/genesis_ui/api_client.py 1:1 - Bibliotheks-
/// Drill-down, Duplikate, Job-Warteschlange, Fehler-Center, Diagnose,
/// Logs, Backups, Plugins, KI-Center, Voice Studio, Download-/
/// Import-Center. Enthaelt bewusst KEINE Fachlogik - reine HTTP-
/// Weiterleitung, identisch zum Charakter des ersten Teils.
/// </summary>
public sealed partial class GenesisApiClient
{
    // --- Bibliotheks-Drill-down (§9/§62, Gap-Analyse B) ---------------------

    public async Task<List<LibraryArtistSummary>> ListLibraryArtistsAsync(
        string? search = null, CancellationToken ct = default)
    {
        var query = BuildSearchQuery("/library/artists", search);
        return await _http.GetFromJsonAsync<List<LibraryArtistSummary>>(query, JsonOptions, ct)
            ?? new List<LibraryArtistSummary>();
    }

    public async Task<LibraryArtistDetail?> GetLibraryArtistDetailAsync(
        int artistId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<LibraryArtistDetail>($"/library/artists/{artistId}", JsonOptions, ct);

    public async Task<List<LibraryAlbumSummary>> ListLibraryAlbumsAsync(
        string? search = null, CancellationToken ct = default)
    {
        var query = BuildSearchQuery("/library/albums", search);
        return await _http.GetFromJsonAsync<List<LibraryAlbumSummary>>(query, JsonOptions, ct)
            ?? new List<LibraryAlbumSummary>();
    }

    public async Task<LibraryAlbumDetail?> GetLibraryAlbumDetailAsync(
        int albumId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<LibraryAlbumDetail>($"/library/albums/{albumId}", JsonOptions, ct);

    public async Task<LibraryTracksResponse?> ListLibraryTracksAsync(
        string? search = null, int limit = 200, int offset = 0, CancellationToken ct = default)
    {
        var query = BuildSearchQuery($"/library/tracks?limit={limit}&offset={offset}", search, "&");
        return await _http.GetFromJsonAsync<LibraryTracksResponse>(query, JsonOptions, ct);
    }

    public async Task<List<LibraryGenreSummary>> ListLibraryGenresAsync(
        string? search = null, CancellationToken ct = default)
    {
        var query = BuildSearchQuery("/library/genres", search);
        return await _http.GetFromJsonAsync<List<LibraryGenreSummary>>(query, JsonOptions, ct)
            ?? new List<LibraryGenreSummary>();
    }

    public async Task<LibraryGenreDetail?> GetLibraryGenreDetailAsync(
        int genreId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<LibraryGenreDetail>($"/library/genres/{genreId}", JsonOptions, ct);

    public async Task<List<LibraryPersonSummary>> ListLibraryPersonsAsync(
        string? search = null, CancellationToken ct = default)
    {
        var query = BuildSearchQuery("/library/persons", search);
        return await _http.GetFromJsonAsync<List<LibraryPersonSummary>>(query, JsonOptions, ct)
            ?? new List<LibraryPersonSummary>();
    }

    public async Task<LibraryPersonDetail?> GetLibraryPersonDetailAsync(
        int personId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<LibraryPersonDetail>($"/library/persons/{personId}", JsonOptions, ct);

    public async Task<LibrarySourcesResponse?> ListLibrarySourcesAsync(
        string? search = null, int limit = 200, int offset = 0, CancellationToken ct = default)
    {
        var query = BuildSearchQuery($"/library/sources?limit={limit}&offset={offset}", search, "&");
        return await _http.GetFromJsonAsync<LibrarySourcesResponse>(query, JsonOptions, ct);
    }

    private static string BuildSearchQuery(string basePath, string? search, string sep = "?") =>
        string.IsNullOrWhiteSpace(search) ? basePath : $"{basePath}{sep}search={Uri.EscapeDataString(search)}";

    // --- Duplikate (§21, ADR-0013) -------------------------------------------

    public async Task<List<DuplicateGroupInfo>> ScanDuplicatesAsync(
        string? kind = null, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/duplicates/scan", new { kind }, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<List<DuplicateGroupInfo>>(JsonOptions, ct)
            ?? new List<DuplicateGroupInfo>();
    }

    public async Task<List<DuplicateGroupInfo>> ListDuplicatesAsync(
        bool? reviewed = null, CancellationToken ct = default)
    {
        var query = reviewed is null ? "/duplicates" : $"/duplicates?reviewed={reviewed.Value.ToString().ToLowerInvariant()}";
        return await _http.GetFromJsonAsync<List<DuplicateGroupInfo>>(query, JsonOptions, ct)
            ?? new List<DuplicateGroupInfo>();
    }

    public async Task<DuplicateGroupInfo?> ReviewDuplicateGroupAsync(int groupId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/duplicates/{groupId}/review", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<DuplicateGroupInfo>(JsonOptions, ct);
    }

    public async Task<DuplicateGroupInfo?> UnreviewDuplicateGroupAsync(int groupId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/duplicates/{groupId}/unreview", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<DuplicateGroupInfo>(JsonOptions, ct);
    }

    // --- Job-Warteschlange (§35/§36) ------------------------------------------

    public async Task<List<JobInfo>> ListJobsAsync(int limit = 50, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<List<JobInfo>>($"/jobs?limit={limit}", JsonOptions, ct) ?? new List<JobInfo>();

    public async Task<JobInfo?> GetJobAsync(string jobId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<JobInfo>($"/jobs/{jobId}", JsonOptions, ct);

    public async Task<JobInfo?> PauseJobAsync(string jobId, CancellationToken ct = default) =>
        await PostJobActionAsync($"/jobs/{jobId}/pause", ct);

    public async Task<JobInfo?> ResumeJobAsync(string jobId, CancellationToken ct = default) =>
        await PostJobActionAsync($"/jobs/{jobId}/resume", ct);

    public async Task<JobInfo?> CancelJobAsync(string jobId, CancellationToken ct = default) =>
        await PostJobActionAsync($"/jobs/{jobId}/cancel", ct);

    private async Task<JobInfo?> PostJobActionAsync(string path, CancellationToken ct)
    {
        var response = await _http.PostAsync(path, EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<JobInfo>(JsonOptions, ct);
    }

    // --- Fehler-Center (§37) ----------------------------------------------------

    public async Task<List<ErrorLogEntry>> ListErrorsAsync(
        int limit = 100, bool unresolvedOnly = false, CancellationToken ct = default)
    {
        var query = $"/errors?limit={limit}&unresolved_only={unresolvedOnly.ToString().ToLowerInvariant()}";
        var parsed = await _http.GetFromJsonAsync<ErrorListResponse>(query, JsonOptions, ct);
        return parsed?.Errors ?? new List<ErrorLogEntry>();
    }

    public async Task ResolveErrorAsync(string errorId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/errors/{errorId}/resolve", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
    }

    // --- Diagnose (§38) -----------------------------------------------------------

    public async Task<DiagnosticsReportInfo?> RunDiagnosticsAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<DiagnosticsReportInfo>("/diagnostics", JsonOptions, ct);

    // --- Logs (§54, Gap J) ----------------------------------------------------------

    public async Task<LogsResponse?> GetLogsAsync(
        string? level = null, string? component = null, string? search = null,
        int limit = 200, int offset = 0, CancellationToken ct = default)
    {
        var query = $"/logs?limit={limit}&offset={offset}";
        if (!string.IsNullOrWhiteSpace(level)) query += $"&level={Uri.EscapeDataString(level)}";
        if (!string.IsNullOrWhiteSpace(component)) query += $"&component={Uri.EscapeDataString(component)}";
        if (!string.IsNullOrWhiteSpace(search)) query += $"&search={Uri.EscapeDataString(search)}";
        return await _http.GetFromJsonAsync<LogsResponse>(query, JsonOptions, ct);
    }

    // --- Backups (§40) ---------------------------------------------------------------

    public async Task<List<BackupEntry>> ListBackupsAsync(
        string? backupType = null, int limit = 50, CancellationToken ct = default)
    {
        var query = $"/backup?limit={limit}";
        if (!string.IsNullOrWhiteSpace(backupType)) query += $"&backup_type={Uri.EscapeDataString(backupType)}";
        var parsed = await _http.GetFromJsonAsync<BackupListResponse>(query, JsonOptions, ct);
        return parsed?.Backups ?? new List<BackupEntry>();
    }

    public async Task<BackupEntry?> CreateDbBackupAsync(CancellationToken ct = default)
    {
        var response = await _http.PostAsync("/backup/db", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<BackupEntry>(JsonOptions, ct);
    }

    public async Task<BackupEntry?> CreateConfigBackupAsync(CancellationToken ct = default)
    {
        var response = await _http.PostAsync("/backup/config", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<BackupEntry>(JsonOptions, ct);
    }

    /// <summary>
    /// <paramref name="confirm"/> darf vom Aufrufer NUR <c>true</c> sein,
    /// NACHDEM der Nutzer die Wiederherstellung explizit bestaetigt hat
    /// (Prinzip #6/#17, §44) - ersetzt die AKTIVE Datenbank.
    /// </summary>
    public async Task<RestoreBackupResult?> RestoreBackupAsync(
        int backupId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/backup/{backupId}/restore", new { confirm }, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<RestoreBackupResult>(JsonOptions, ct);
    }

    // --- Plugins (§34) -----------------------------------------------------------------

    public async Task<PluginsResponse?> ListPluginsAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<PluginsResponse>("/plugins", JsonOptions, ct);

    public async Task<PluginsResponse?> ReloadPluginsAsync(CancellationToken ct = default)
    {
        var response = await _http.PostAsync("/plugins/reload", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<PluginsResponse>(JsonOptions, ct);
    }

    // --- KI-Center (§25/§26) -------------------------------------------------------------

    public async Task<AiStatusInfo?> GetAiStatusAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<AiStatusInfo>("/ai/status", JsonOptions, ct);

    public async Task<AiReindexResult?> ReindexAiSearchAsync(CancellationToken ct = default)
    {
        var response = await _http.PostAsync("/ai/search/reindex", EmptyJsonContent(), ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<AiReindexResult>(JsonOptions, ct);
    }

    public async Task<AiSearchResponse?> AiSemanticSearchAsync(
        string query, int topK = 20, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            "/ai/search", new { query, top_k = topK }, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<AiSearchResponse>(JsonOptions, ct);
    }

    // --- Voice Studio (§28/§29, ADR-0018) -------------------------------------------------

    public async Task<VoiceStatusInfo?> GetVoiceStatusAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<VoiceStatusInfo>("/voice/status", JsonOptions, ct);

    public async Task<List<VoiceEngineInfo>> ListVoiceEnginesAsync(CancellationToken ct = default)
    {
        var parsed = await _http.GetFromJsonAsync<VoiceEnginesResponse>("/voice/engines", JsonOptions, ct);
        return parsed?.Engines ?? new List<VoiceEngineInfo>();
    }

    public async Task<List<VoiceProfileInfo>> ListVoiceProfilesAsync(CancellationToken ct = default)
    {
        var parsed = await _http.GetFromJsonAsync<VoiceProfilesResponse>("/voice/profiles", JsonOptions, ct);
        return parsed?.Profiles ?? new List<VoiceProfileInfo>();
    }

    public async Task<CreateVoiceProfileResult?> CreateVoiceProfileAsync(
        CreateVoiceProfileRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync("/voice/profiles", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<CreateVoiceProfileResult>(JsonOptions, ct);
    }

    /// <summary>
    /// <paramref name="confirmName"/> muss exakt dem Profilnamen
    /// entsprechen (Prinzip #6 "Loeschen = extra confirm", §28) - die
    /// Core-API lehnt andernfalls mit 403 ab.
    /// </summary>
    public async Task DeleteVoiceProfileAsync(
        int profileId, string confirmName, CancellationToken ct = default)
    {
        var request = new HttpRequestMessage(HttpMethod.Delete, $"/voice/profiles/{profileId}")
        {
            Content = JsonContent.Create(new DeleteVoiceProfileRequest(true, confirmName), options: JsonOptions),
        };
        var response = await _http.SendAsync(request, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
    }

    public async Task<SynthesizeVoiceResult?> SynthesizeVoiceAsync(
        int profileId, string text, string exportFormat = "wav", CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/voice/profiles/{profileId}/synthesize",
            new SynthesizeVoiceRequest(text, exportFormat, true), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<SynthesizeVoiceResult>(JsonOptions, ct);
    }

    public async Task<SynthesizeVoiceResult?> TestVoiceProfileAsync(
        int profileId, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/voice/profiles/{profileId}/test", new TestVoiceProfileRequest(true), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<SynthesizeVoiceResult>(JsonOptions, ct);
    }

    public async Task<List<VoiceSynthesisInfo>> ListVoiceSynthesesAsync(
        int? profileId = null, CancellationToken ct = default)
    {
        var query = profileId is null ? "/voice/syntheses" : $"/voice/syntheses?profile_id={profileId}";
        var parsed = await _http.GetFromJsonAsync<VoiceSynthesesResponse>(query, JsonOptions, ct);
        return parsed?.Syntheses ?? new List<VoiceSynthesisInfo>();
    }

    public async Task<byte[]?> GetVoiceSynthesisAudioAsync(int synthesisId, CancellationToken ct = default)
    {
        var response = await _http.GetAsync($"/voice/syntheses/{synthesisId}/audio", ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadAsByteArrayAsync(ct);
    }

    // --- Download-/Import-Center (§30-§32, ADR-0019) ---------------------------------------

    public async Task<DownloadProvidersResponse?> ListDownloadProvidersAsync(CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<DownloadProvidersResponse>("/download/providers", JsonOptions, ct);

    public async Task<DetectDownloadSourceResult?> DetectDownloadSourceAsync(
        string url, CancellationToken ct = default) =>
        await PostDownloadAsync<DetectDownloadSourceResult>("/download/detect", url, ct);

    public async Task<CheckDownloadAvailabilityResult?> CheckDownloadAvailabilityAsync(
        string url, CancellationToken ct = default) =>
        await PostDownloadAsync<CheckDownloadAvailabilityResult>("/download/availability", url, ct);

    public async Task<DownloadMetadataResult?> FetchDownloadMetadataAsync(
        string url, CancellationToken ct = default) =>
        await PostDownloadAsync<DownloadMetadataResult>("/download/metadata", url, ct);

    public async Task<DownloadOptionsResult?> ListDownloadOptionsAsync(
        string url, CancellationToken ct = default) =>
        await PostDownloadAsync<DownloadOptionsResult>("/download/options", url, ct);

    private async Task<T?> PostDownloadAsync<T>(string path, string url, CancellationToken ct)
    {
        var response = await _http.PostAsJsonAsync(path, new DownloadUrlRequest(url), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<T>(JsonOptions, ct);
    }

    /// <summary>
    /// Echter Download/Import - <paramref name="confirm"/> darf NUR
    /// <c>true</c> sein, nachdem der Nutzer explizit bestaetigt hat
    /// (Prinzip #6/#17, §56 - niemals automatischer Download).
    /// </summary>
    public async Task<DownloadImportResult?> ImportDownloadAsync(
        string url, string optionId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            "/download/import", new DownloadImportRequest(url, optionId, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<DownloadImportResult>(JsonOptions, ct);
    }

    public async Task<DownloadImportResult?> ImportLocalFileAsync(
        string path, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            "/import/local-file", new LocalFileImportRequest(path, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<DownloadImportResult>(JsonOptions, ct);
    }

    private static StringContent EmptyJsonContent() =>
        new("{}", System.Text.Encoding.UTF8, "application/json");
}
