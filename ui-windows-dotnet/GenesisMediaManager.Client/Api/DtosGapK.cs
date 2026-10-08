// Gap K, siebter inkrementeller Schritt - DTOs fuer alle bislang noch nicht
// im .NET-Client gespiegelten Core-API-Endpunkte (Bibliotheks-Drill-down,
// Duplikate, KI-Center, Voice Studio, Download-/Import-Center,
// Job-Warteschlange, Fehler-Center, Diagnose, Backups, Plugins). Siehe
// ui-reference-pyside/genesis_ui/api_client.py fuer das 1:1-Vorbild und
// docs/GAP_ANALYSIS.md Gap K fuer den Gesamtkontext. Bewusst in einer
// eigenen Datei statt in GenesisApiClient.cs, damit die ohnehin schon
// grosse Haupt-Clientdatei nicht weiter waechst (ADR: eine Datei pro
// fachlichem Bereich sobald eine Datei unhandlich gross wird).
namespace GenesisMediaManager.Client.Api;

// --- Bibliotheks-Drill-down (§9/§62, Gap-Analyse B) -------------------------

public sealed record LibraryAlbumSummary(
    int Id, string Title, int? ArtistId, string? ArtistName, int? Year, int TrackCount);

public sealed record LibraryTrackSummary(
    int Id, int MediaFileId, string? Title, int? TrackNumber, int? DiscNumber,
    double? DurationSeconds);

public sealed record LibraryArtistSummary(
    int Id, string Name, string? SortName, int AlbumCount, int TrackCount);

public sealed record LibraryArtistDetail(
    int Id, string Name, string? SortName, string? MusicbrainzId,
    List<LibraryAlbumSummary> Albums);

public sealed record LibraryAlbumDetail(
    int Id, string Title, int? ArtistId, string? ArtistName, int? Year,
    string? MusicbrainzId, List<LibraryTrackSummary> Tracks);

public sealed record LibraryTrackListEntry(
    int Id, int MediaFileId, string? Title, string? ArtistName, string? AlbumTitle,
    string? GenreName, int? Year, int? TrackNumber, double? DurationSeconds);

public sealed record LibraryTracksResponse(int Total, List<LibraryTrackListEntry> Items);

public sealed record LibraryGenreSummary(int Id, string Name, int TrackCount);

public sealed record LibraryGenreDetail(int Id, string Name, List<LibraryTrackListEntry> Tracks);

public sealed record LibraryPersonSummary(int Id, string Name, int RoleCount);

public sealed record LibraryPersonRoleEntry(
    string Role, string WorkKind, int WorkId, string? WorkTitle, int? MediaFileId);

public sealed record LibraryPersonDetail(int Id, string Name, List<LibraryPersonRoleEntry> Roles);

public sealed record LibrarySourceEntry(
    int Id, int MediaFileId, string? Filename, string? SourceName, string? ProviderName,
    string? OriginalUrl, string? OriginalId, string? ImportedAt, string? ImportMethod);

public sealed record LibrarySourcesResponse(int Total, List<LibrarySourceEntry> Items);

// --- Duplikate (§21, ADR-0013) ----------------------------------------------

public sealed record DuplicateGroupInfo(
    int Id, string Category, double Confidence, List<string>? MatchedStages, string Reason,
    bool Reviewed, string? DetectedAt, List<int> MediaFileIds);

// --- Job-Warteschlange (§35/§36) --------------------------------------------

public sealed record JobInfo(
    string Id, string JobType, string Status, string? CreatedAt, string? StartedAt,
    string? FinishedAt, int? TotalItems, int? ProcessedItems, int ErrorCount,
    int WarningCount, string? CurrentItem);

// --- Fehler-Center (§37) -----------------------------------------------------

public sealed record ErrorLogEntry(
    string ErrorId, string? Timestamp, string? Component, string? FilePath, string? Action,
    string Message, string? TechnicalDetails, string? SolutionHint, bool Resolved);

public sealed record ErrorListResponse(List<ErrorLogEntry> Errors);

// --- Diagnose (§38) -----------------------------------------------------------

public sealed record DiagnosticCheckInfo(string CheckId, string Label, string Status, string Message);

public sealed record DiagnosticsReportInfo(
    string GeneratedAt, string OverallStatus, List<DiagnosticCheckInfo> Checks);

// --- Logs (§54, Gap J) --------------------------------------------------------

public sealed record LogEntryInfo(string Timestamp, string Level, string Component, string Message);

public sealed record LogsResponse(int Total, List<LogEntryInfo> Items);

// --- Backups (§40) -------------------------------------------------------------

public sealed record BackupEntry(
    int Id, string? CreatedAt, string BackupType, string Path, string VersionLabel,
    long? SizeBytes);

public sealed record BackupListResponse(List<BackupEntry> Backups);

public sealed record RestoreBackupResult(
    int RestoredFromBackupId, string RestoredFromPath, BackupEntry PreRestoreBackup);

// --- Plugins (§34) -------------------------------------------------------------

public sealed record PluginInfo(
    string? PluginId, string? PluginKind, string? DisplayName, string? Version,
    string? Author, string? License, bool IsLocal, bool RequiresInternet,
    string? SourcePath, bool LoadedSuccessfully, string? LoadError);

public sealed record PluginsResponse(string PluginsDir, List<PluginInfo> Plugins);

// --- KI-Center (§25/§26) ------------------------------------------------------

public sealed record AiStatusInfo(
    bool Enabled, string Provider, bool IsLocal, bool RequiresInternet, bool Available,
    string? Model, string? EmbeddingModel);

public sealed record AiReindexResult(string JobId, int Total, int Embedded);

public sealed record AiSearchResultEntry(int MediaFileId, string Filename, string Kind, double Score);

public sealed record AiSearchResponse(bool Available, List<AiSearchResultEntry> Results);

// --- Voice Studio (§28/§29, ADR-0018) -----------------------------------------

public sealed record VoiceStatusInfo(
    bool Enabled, string Provider, bool IsLocal, bool RequiresInternet, bool Available);

public sealed record VoiceEngineInfo(
    string Id, string Label, bool IsLocal, bool RequiresInternet,
    string? SuggestedEngineLicense, string? Homepage, string? Notes);

public sealed record VoiceEnginesResponse(List<VoiceEngineInfo> Engines);

public sealed record VoiceProfileInfo(
    int Id, string Name, string Engine, string? ModelPath, string? Language,
    string? Description, string? ModelLicense, bool? OfflineCapable, bool? OpenSource,
    bool? CommercialUseAllowed, string? SamplePath, string? CreatedAt);

public sealed record VoiceProfilesResponse(List<VoiceProfileInfo> Profiles);

public sealed record CreateVoiceProfileRequest(
    string Name, string Engine, string? ModelPath, string? Language, string? Description,
    string? ModelLicense, bool? OfflineCapable, bool? OpenSource,
    bool? CommercialUseAllowed, string? SamplePath, bool Confirm);

public sealed record CreateVoiceProfileResult(string JobId, VoiceProfileInfo Profile);

public sealed record DeleteVoiceProfileRequest(bool Confirm, string ConfirmName);

public sealed record VoiceSynthesisInfo(
    int Id, int VoiceProfileId, string Text, string OutputPath, string ExportFormat,
    double? DurationSeconds, int? SampleRate, string? Engine, bool IsTestPhrase,
    string? CreatedAt);

public sealed record SynthesizeVoiceRequest(string Text, string ExportFormat, bool Confirm);

public sealed record SynthesizeVoiceResult(string JobId, VoiceSynthesisInfo Synthesis);

public sealed record TestVoiceProfileRequest(bool Confirm);

public sealed record VoiceSynthesesResponse(List<VoiceSynthesisInfo> Syntheses);

// --- Download-/Import-Center (§30-§32, ADR-0019) ------------------------------

public sealed record DownloadProviderInfo(string Id, string DisplayName, bool RequiresInternet);

public sealed record DownloadProvidersResponse(bool Enabled, List<DownloadProviderInfo> Providers);

public sealed record DownloadUrlRequest(string Url);

public sealed record DetectDownloadSourceResult(string? ProviderId, string? DisplayName);

public sealed record CheckDownloadAvailabilityResult(
    string? ProviderId, bool Available, string? Reason, bool RequiresLogin);

public sealed record DownloadMetadataResult(
    string? ProviderId, string? Title, string? Description, double? DurationSeconds,
    string? Uploader, string? ThumbnailUrl, string? OriginalId, string? License);

public sealed record DownloadOptionInfo(
    string OptionId, string Label, string FileExtension, long? ApproxSizeBytes,
    string? QualityNote);

public sealed record DownloadOptionsResult(string? ProviderId, List<DownloadOptionInfo> Options);

public sealed record DownloadImportRequest(string Url, string OptionId, bool Confirm);

public sealed record LocalFileImportRequest(string Path, bool Confirm);

public sealed record DownloadImportResult(
    string JobId, int MediaFileId, string AbsolutePath, int? SourceId,
    string? SuggestedFilename, bool FingerprintComputed, bool LoudnessMeasured,
    List<string>? Warnings);
