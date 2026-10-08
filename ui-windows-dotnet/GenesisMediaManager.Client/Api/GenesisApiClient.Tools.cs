using System.Net.Http;
using System.Net.Http.Json;

namespace GenesisMediaManager.Client.Api;

/// <summary>
/// Gap K, achter inkrementeller Schritt - dritter Teil von
/// <see cref="GenesisApiClient"/> (<c>partial class</c>, siehe
/// Api/GenesisApiClient.cs fuer <c>_http</c>/<c>JsonOptions</c>/
/// <c>EnsureSuccessWithDetailAsync</c>). Deckt die restlichen
/// Medientabellen-Werkzeugdialoge ab: Audio-Cutter (§18), Konvertierung,
/// Lautheits-Normalisierung (§19), KI-Metadaten (§25), Hoerbuch-Tags +
/// Kapitel (§23), Film-/Serienerkennung (§24). Alle "/preview"-Aufrufe sind
/// rein lesend/berechnend, alle "/apply"-Aufrufe verlangen
/// <c>confirm=true</c> - der Aufrufer in MainWindow.*.cs darf dies NUR nach
/// echter Nutzerbestaetigung setzen (Prinzip #17, §44).
/// </summary>
public sealed partial class GenesisApiClient
{
    // --- Lautheit/Normalisierung (§19, ADR-0010) -----------------------------

    public async Task<LoudnessAnalyzeResult?> AnalyzeLoudnessAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/media/{mediaId}/loudness/analyze", null, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<LoudnessAnalyzeResult>(JsonOptions, ct);
    }

    public async Task<NormalizationPlan?> PreviewLoudnessNormalizationAsync(
        int mediaId, LoudnessNormalizePreviewRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/loudness/normalize/preview", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<NormalizationPlan>(JsonOptions, ct);
    }

    public async Task<LoudnessNormalizeApplyResult?> ApplyLoudnessNormalizationAsync(
        int mediaId, LoudnessNormalizeApplyRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/loudness/normalize/apply", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<LoudnessNormalizeApplyResult>(JsonOptions, ct);
    }

    // --- Audio-Cutter (§18, ADR-0011) ----------------------------------------

    public async Task<byte[]?> GetCutterWaveformAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.GetAsync($"/media/{mediaId}/cutter/waveform", ct);
        if (!response.IsSuccessStatusCode) return null;
        return await response.Content.ReadAsByteArrayAsync(ct);
    }

    public async Task<CutPlan?> PreviewCutAsync(int mediaId, CutPreviewRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync($"/media/{mediaId}/cutter/preview", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<CutPlan>(JsonOptions, ct);
    }

    public async Task<CutApplyResult?> ApplyCutAsync(int mediaId, CutApplyRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync($"/media/{mediaId}/cutter/apply", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<CutApplyResult>(JsonOptions, ct);
    }

    public async Task<List<CutHistoryEntry>> ListCutsAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<List<CutHistoryEntry>>($"/media/{mediaId}/cutter", JsonOptions, ct)
        ?? new List<CutHistoryEntry>();

    // --- Konvertierung --------------------------------------------------------

    public async Task<ConversionPlan?> PreviewConversionAsync(
        int mediaId, ConvertPreviewRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync($"/media/{mediaId}/convert/preview", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ConversionPlan>(JsonOptions, ct);
    }

    public async Task<ConversionApplyResult?> ApplyConversionAsync(
        int mediaId, ConvertApplyRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync($"/media/{mediaId}/convert/apply", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ConversionApplyResult>(JsonOptions, ct);
    }

    public async Task<List<ConversionHistoryEntry>> ListConversionsAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<List<ConversionHistoryEntry>>($"/media/{mediaId}/convert", JsonOptions, ct)
        ?? new List<ConversionHistoryEntry>();

    // --- Hoerbuch-Tags & Kapitel (§23, ADR-0015) -------------------------------

    public async Task<AudiobookTagSnapshot?> GetAudiobookTagsPreviewAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<AudiobookTagSnapshot>($"/media/{mediaId}/audiobook/tags", JsonOptions, ct);

    public async Task<AudiobookTagsApplyResult?> ApplyAudiobookTagsAsync(
        int mediaId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/audiobook/tags/apply", new ApplyAudiobookTagsRequest(confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<AudiobookTagsApplyResult>(JsonOptions, ct);
    }

    public async Task<AudiobookInfo?> GetAudiobookAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<AudiobookInfo>($"/media/{mediaId}/audiobook", JsonOptions, ct);

    public async Task<List<ChapterEntry>> ListChaptersAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<List<ChapterEntry>>($"/media/{mediaId}/chapters", JsonOptions, ct)
        ?? new List<ChapterEntry>();

    public async Task<ChapterDetectionPreview?> DetectChaptersPreviewAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/media/{mediaId}/chapters/detect", null, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ChapterDetectionPreview>(JsonOptions, ct);
    }

    public async Task<ChaptersApplyResult?> DetectChaptersApplyAsync(int mediaId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/chapters/detect/apply", new DetectChaptersApplyRequest(confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ChaptersApplyResult>(JsonOptions, ct);
    }

    public async Task<ChapterDetectionPreview?> GenerateChaptersPreviewAsync(
        int mediaId, double intervalMinutes, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/chapters/generate", new GenerateChaptersRequest(intervalMinutes), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ChapterDetectionPreview>(JsonOptions, ct);
    }

    public async Task<ChaptersApplyResult?> GenerateChaptersApplyAsync(
        int mediaId, double intervalMinutes, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/chapters/generate/apply", new GenerateChaptersApplyRequest(intervalMinutes, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ChaptersApplyResult>(JsonOptions, ct);
    }

    public async Task<ChapterEntry?> RenameChapterAsync(
        int mediaId, int chapterId, string title, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PatchAsJsonAsync(
            $"/media/{mediaId}/chapters/{chapterId}", new RenameChapterRequest(title, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<ChapterEntry>(JsonOptions, ct);
    }

    public async Task<string> ExportChaptersAsync(int mediaId, string format, CancellationToken ct = default)
    {
        var response = await _http.GetAsync($"/media/{mediaId}/chapters/export?format={format}", ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadAsStringAsync(ct);
    }

    // --- Film-/Serienerkennung (§24) --------------------------------------------

    public async Task<VideoTagSnapshot?> GetVideoTagsPreviewAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<VideoTagSnapshot>($"/media/{mediaId}/video/tags", JsonOptions, ct);

    public async Task<EpisodeDetectionResult?> DetectEpisodePreviewAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/media/{mediaId}/video/episode-detection", null, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<EpisodeDetectionResult>(JsonOptions, ct);
    }

    public async Task<MovieApplyResult?> ApplyMovieMetadataAsync(int mediaId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/movie/apply", new ApplyVideoMetadataRequest(confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<MovieApplyResult>(JsonOptions, ct);
    }

    public async Task<MovieInfo?> GetMovieAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<MovieInfo>($"/media/{mediaId}/movie", JsonOptions, ct);

    public async Task<EpisodeApplyResult?> ApplyEpisodeMetadataAsync(int mediaId, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/episode/apply", new ApplyVideoMetadataRequest(confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<EpisodeApplyResult>(JsonOptions, ct);
    }

    public async Task<EpisodeInfo?> GetEpisodeAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<EpisodeInfo>($"/media/{mediaId}/episode", JsonOptions, ct);

    // --- KI-Metadaten (§25, ADR-0017) ---------------------------------------

    public async Task<List<AiSuggestionItem>> AiSuggestAsync(
        int mediaId, List<string>? fields = null, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/ai/suggest", new AiSuggestRequest(fields), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<List<AiSuggestionItem>>(JsonOptions, ct)
            ?? new List<AiSuggestionItem>();
    }

    // --- Fingerabdruck (Vorstufe §21) + Qualitaetsanalyse (§20) --------------

    public async Task<FingerprintResult?> ComputeFingerprintAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/media/{mediaId}/fingerprint", null, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<FingerprintResult>(JsonOptions, ct);
    }

    public async Task<QualityAnalysisResult?> AnalyzeQualityAsync(int mediaId, CancellationToken ct = default)
    {
        var response = await _http.PostAsync($"/media/{mediaId}/quality/analyze", null, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<QualityAnalysisResult>(JsonOptions, ct);
    }

    public async Task<AiMetadataApplyResult?> AiApplyAsync(
        int mediaId, List<AcceptedAiSuggestion> accepted, bool confirm, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync(
            $"/media/{mediaId}/ai/apply", new AiApplyRequest(accepted, confirm), JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<AiMetadataApplyResult>(JsonOptions, ct);
    }

    // --- KI-Musik-Provenienz (§27, ADR-0017) ----------------------------------

    public async Task<AiMusicInfo?> GetAiMusicAsync(int mediaId, CancellationToken ct = default) =>
        await _http.GetFromJsonAsync<AiMusicInfo>($"/media/{mediaId}/ai-music", JsonOptions, ct);

    public async Task<AiMusicApplyResult?> ApplyAiMusicAsync(
        int mediaId, AiMusicApplyRequest request, CancellationToken ct = default)
    {
        var response = await _http.PostAsJsonAsync($"/media/{mediaId}/ai-music/apply", request, JsonOptions, ct);
        await EnsureSuccessWithDetailAsync(response, ct);
        return await response.Content.ReadFromJsonAsync<AiMusicApplyResult>(JsonOptions, ct);
    }
}
