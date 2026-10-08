namespace GenesisMediaManager.Client.Api;

// Gap K, achter inkrementeller Schritt - DTOs fuer die restlichen
// Medientabellen-Werkzeugdialoge (Cutter/Convert/Loudness-Normalisierung/
// KI-Metadaten/Hoerbuch-Tags+Kapitel/Film-Serien-Erkennung), Pendants zu
// ui-reference-pyside/genesis_ui/dialogs/{cutter,convert,loudness,ai,
// audiobook,video}_dialog.py. Alle "/preview"-Operationen sind rein
// lesend/berechnend (Prinzip #4/#5, erzeugen KEINE Datei/DB-Zeile), alle
// "/apply"-Operationen verlangen server-seitig `confirm=true` (Prinzip
// #17, §44) - siehe core/genesis_core/api/app.py fuer die exakten
// Feldnamen/Formen, 1:1 uebernommen.

// --- Lautheit/Normalisierung (§19, ADR-0010) --------------------------------

/// <summary>
/// Eigener, schlanker DTO statt Wiederverwendung von
/// <see cref="LoudnessEntry"/> - der <c>/loudness/analyze</c>-Endpunkt
/// liefert bewusst ein ANDERES Feld fuer die Medien-ID (<c>media_id</c>,
/// nicht <c>media_file_id</c> wie bei <c>GET /loudness</c>/
/// <c>loudness_to_dict</c>). Eine Wiederverwendung wuerde das Feld dank
/// <c>PropertyNameCaseInsensitive</c> still und unbemerkt auf <c>null</c>
/// zurueckfallen lassen (siehe Klassenkommentar in GenesisApiClient.cs zu
/// genau diesem Fehlerbild) - daher eigener Typ mit dem tatsaechlich
/// vorkommenden Feldnamen.
/// </summary>
public sealed record LoudnessAnalyzeResult(
    int Id, int MediaId, double? IntegratedLufs, double? TruePeakDbtp,
    double? LoudnessRangeLu, string? MeasuredAt);

public sealed record LoudnessNormalizePreviewRequest(
    double? TargetLufs = null, double? TargetTruePeakDbtp = null, double TargetLra = 11.0);

public sealed record LoudnessNormalizeApplyRequest(
    double? TargetLufs, double? TargetTruePeakDbtp, double TargetLra, bool Confirm);

public sealed record NormalizationPlan(
    int MediaFileId, string SourcePath, string OutputPath, double TargetLufs,
    double TargetTruePeakDbtp, double TargetLra, double MeasuredIntegratedLufs,
    double MeasuredTruePeakDbtp, double MeasuredLoudnessRangeLu, double PlannedGainDb,
    double PredictedOutputTruePeakDbtp, bool WillLikelyAlterDynamics, bool IsLossyReencode,
    string OutputFormatNote, bool HasConflict, string? ConflictReason);

public sealed record LoudnessNormalizeApplyResult(
    string JobId, int LoudnessId, string OutputPath, double AchievedIntegratedLufs,
    double AchievedTruePeakDbtp, bool UsedDynamicProcessing);

// --- Audio-Cutter (§18, ADR-0011) -------------------------------------------

public sealed record CutPreviewRequest(
    double StartSeconds, double EndSeconds, string ExportFormat = "mp3",
    double FadeInSeconds = 0.0, double FadeOutSeconds = 0.0);

public sealed record CutApplyRequest(
    double StartSeconds, double EndSeconds, string ExportFormat, double FadeInSeconds,
    double FadeOutSeconds, bool Confirm);

public sealed record CutPlan(
    int MediaFileId, string SourcePath, string OutputPath, double StartSeconds,
    double EndSeconds, double FadeInSeconds, double FadeOutSeconds, string ExportFormat,
    double SelectionDurationSeconds, bool IsLossyExport, bool HasConflict, string? ConflictReason);

public sealed record CutApplyResult(
    string JobId, int CutId, string OutputPath, double StartSeconds, double EndSeconds,
    string ExportFormat);

public sealed record CutHistoryEntry(
    int Id, int MediaFileId, string SourcePath, string OutputPath, double StartSeconds,
    double EndSeconds, double FadeInSeconds, double FadeOutSeconds, string ExportFormat,
    string? CreatedAt);

// --- Konvertierung -----------------------------------------------------------

public sealed record ConvertPreviewRequest(string TargetFormat, int? BitrateKbps = null);

public sealed record ConvertApplyRequest(string TargetFormat, int? BitrateKbps, bool Confirm);

public sealed record ConversionPlan(
    int MediaFileId, string SourcePath, string OutputPath, string SourceFormat,
    string TargetFormat, int? BitrateKbps, bool IsLossyTarget, bool IsNoOpSameFormat,
    bool HasConflict, string? ConflictReason);

public sealed record ConversionApplyResult(
    string JobId, int ConversionId, string OutputPath, string TargetFormat, int? BitrateKbps);

public sealed record ConversionHistoryEntry(
    int Id, int MediaFileId, string SourcePath, string OutputPath, string SourceFormat,
    string TargetFormat, int? BitrateKbps, string? CreatedAt);

// --- Hoerbuch-Tags & Kapitel (§23, ADR-0015) ---------------------------------

public sealed record AudiobookTagSnapshot(
    string? Title, string? Author, string? AuthorSource, string? Narrator,
    string? NarratorSource, string? Series, string? SeriesSource, int? VolumeNumber,
    string? Publisher, int? Year, string? Language, string? Description, bool HasAnyTag);

public sealed record ApplyAudiobookTagsRequest(bool Confirm);

public sealed record AudiobookInfo(
    int Id, int MediaFileId, string? Title, string? Author, string? Narrator,
    string? Publisher, string? Series, int? VolumeNumber, int? Year, string? Language,
    string? Description);

public sealed record AudiobookTagsApplyResult(string JobId, AudiobookInfo Audiobook);

public sealed record ChapterEntry(int Id, int MediaFileId, int Index, string? Title, int StartMs, int? EndMs);

public sealed record ChapterCandidate(int Index, string? Title, double StartSeconds, double? EndSeconds);

public sealed record ChapterDetectionPreview(int MediaId, List<ChapterCandidate> Candidates);

public sealed record DetectChaptersApplyRequest(bool Confirm);

public sealed record ChaptersApplyResult(string JobId, List<ChapterEntry> Chapters);

public sealed record GenerateChaptersRequest(double IntervalMinutes);

public sealed record GenerateChaptersApplyRequest(double IntervalMinutes, bool Confirm);

public sealed record RenameChapterRequest(string Title, bool Confirm);

// --- Film-/Serienerkennung (§24) ---------------------------------------------

public sealed record VideoTagSnapshot(
    string? Title, int? Year, string? Genre, string? Description,
    List<string> DirectorNames, List<string> ActorNames, string? Series,
    int? SeasonNumber, int? EpisodeNumber, bool HasAnyTag);

public sealed record EpisodeDetectionResult(
    bool IsLikelyEpisode, double Confidence, string? SeriesName, string? SeriesSource,
    int? SeasonNumber, string? SeasonSource, int? EpisodeNumber, string? EpisodeSource,
    string? Title, string? TitleSource, int? Year, string? Description);

public sealed record ApplyVideoMetadataRequest(bool Confirm);

public sealed record MovieInfo(
    int Id, int MediaFileId, string? Title, string? OriginalTitle, int? Year, string? Genre,
    int? RuntimeSeconds, string? Language, string? Description, List<string> Directors,
    List<string> Actors);

public sealed record MovieApplyResult(string JobId, MovieInfo Movie);

public sealed record EpisodeInfo(
    int Id, int MediaFileId, string? Series, int? SeasonNumber, int? EpisodeNumber,
    string? Title, int? Year, string? Description, List<string> Directors, List<string> Actors);

public sealed record EpisodeApplyResult(string JobId, EpisodeInfo Episode);

// --- KI-Metadaten (§25, ADR-0017) --------------------------------------------

public sealed record AiSuggestRequest(List<string>? Fields = null);

public sealed record AiSuggestionItem(
    string FieldName, string FieldValue, string ModelName, string? ModelVersion,
    double? Confidence, bool IsAiGenerated, string? Prompt, string? CreatedAt);

public sealed record AcceptedAiSuggestion(
    string FieldName, string FieldValue, string ModelName, string? ModelVersion,
    double? Confidence, string? Prompt);

public sealed record AiApplyRequest(List<AcceptedAiSuggestion> Accepted, bool Confirm);

public sealed record AiMetadataApplyResult(string JobId, List<AiMetadataEntry> Entries);

// --- Fingerabdruck (Vorstufe §21) + Qualitaetsanalyse (§20) ------------------

public sealed record FingerprintResult(int MediaFileId, string Algorithm, double DurationSeconds);

public sealed record QualityAnalysisResult(
    bool SuspectedUpscale, bool SuspectedTranscode, bool SuspectedCorruption,
    bool SuspectedTruncation, List<string> Notes);

// --- KI-Musik-Provenienz (§27, ADR-0017) - IMMER manuelle Nutzerangabe -------

public sealed record AiMusicInfo(
    int TrackId, int MediaFileId, string AiStatus, string? AiSource, string? AiModel,
    string? AiPrompt, string? AiCreationDate, bool? AiInstrumental, string? AiStyle,
    string? AiMood, string? AiOwner, List<string> ArtistNames);

public sealed record AiMusicApplyRequest(
    string Status, string? Source, string? Model, string? Prompt, string? CreationDate,
    bool? Instrumental, string? Style, string? Mood, string? Owner, string? ArtistName,
    bool Confirm);

public sealed record AiMusicApplyResult(string JobId, AiMusicInfo Track);
