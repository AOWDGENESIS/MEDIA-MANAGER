// Tests fuer die WPF-unabhaengige Hilfslogik der Einstellungen-Ansicht
// (SettingsViewSupport.cs). Spiegelt die Kernfaelle, die auf Python-Seite in
// ui-reference-pyside/tests/test_settings_view.py abgedeckt sind, soweit sie
// sich ohne echten WPF-Control-Baum pruefen lassen (Umwandlung
// SettingsResponse -> Formularwerte und zurueck in eine PATCH-Payload mit
// den exakt richtigen snake_case-Schluesseln, sowie die Medienordner-Listen-
// Hilfslogik).
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client.Tests;

public class SettingsViewSupportTests
{
    private static SettingsResponse SampleSettings() => new(
        General: new GeneralSettings("de", false, true),
        Paths: new PathsSettingsInfo(new List<string> { "/music", "/audiobooks" }),
        Ai: new AiSettingsInfo(false, "null", "http://127.0.0.1:11434", "qwen2.5:0.5b", 30.0, "all-minilm"),
        Voice: new VoiceSettingsInfo(false, "null", "wav"),
        Loudness: new LoudnessSettingsInfo(-14.0, -1.0, false),
        Download: new DownloadSettingsInfo(false, true, true, null, 4096, 1024, 20.0),
        Privacy: new PrivacySettingsInfo(false, false, false, false, false),
        Metadata: new MetadataSettingsInfo(false, false, false, string.Empty, false, string.Empty, 10.0, 0.5));

    [Fact]
    public void FromSettingsResponse_CopiesAllCoveredFields()
    {
        var values = SettingsViewSupport.FromSettingsResponse(SampleSettings());

        Assert.Equal("de", values.Language);
        Assert.True(values.RequireConfirmationForBulkChanges);
        Assert.Equal(new[] { "/music", "/audiobooks" }, values.MediaFolders);
        Assert.False(values.AiEnabled);
        Assert.Equal("null", values.AiProvider);
        Assert.Equal("http://127.0.0.1:11434", values.AiEndpoint);
        Assert.Equal("qwen2.5:0.5b", values.AiModel);
        Assert.Equal(30.0, values.AiTimeoutSeconds);
        Assert.False(values.VoiceEnabled);
        Assert.Equal("null", values.VoiceProvider);
        Assert.Equal("wav", values.VoiceDefaultExportFormat);
        Assert.Equal(-14.0, values.LoudnessTargetLufs);
        Assert.Equal(-1.0, values.LoudnessTargetTruePeakDbtp);
        Assert.False(values.LoudnessOverwriteOriginals);
        Assert.False(values.DownloadEnabled);
        Assert.True(values.DownloadEnableYoutube);
        Assert.True(values.DownloadEnableTiktok);
        Assert.Equal(string.Empty, values.DownloadDir);
        Assert.Equal(4096, values.DownloadMaxSizeMb);
        Assert.Equal(1024, values.DownloadMinFreeDiskMb);
        Assert.Equal(20.0, values.DownloadTimeoutSeconds);
        Assert.False(values.PrivacyAllowCloudAi);
    }

    [Fact]
    public void FromSettingsResponse_KeepsNonEmptyDownloadsDirAsIs()
    {
        var settings = SampleSettings() with
        {
            Download = new DownloadSettingsInfo(true, true, true, "/data/downloads", 4096, 1024, 20.0),
        };
        var values = SettingsViewSupport.FromSettingsResponse(settings);

        Assert.Equal("/data/downloads", values.DownloadDir);
    }

    [Fact]
    public void BuildUpdatePayload_UsesExactSnakeCaseKeysExpectedByCoreApi()
    {
        var values = SettingsViewSupport.FromSettingsResponse(SampleSettings());
        var payload = SettingsViewSupport.BuildUpdatePayload(values);

        Assert.True(payload.ContainsKey("general"));
        Assert.True(payload.ContainsKey("paths"));
        Assert.True(payload.ContainsKey("ai"));
        Assert.True(payload.ContainsKey("voice"));
        Assert.True(payload.ContainsKey("loudness"));
        Assert.True(payload.ContainsKey("download"));
        Assert.True(payload.ContainsKey("privacy"));

        var general = Assert.IsType<Dictionary<string, object>>(payload["general"]);
        Assert.Equal("de", general["language"]);
        Assert.True((bool)general["require_confirmation_for_bulk_changes"]);

        var paths = Assert.IsType<Dictionary<string, object>>(payload["paths"]);
        Assert.Equal(new[] { "/music", "/audiobooks" }, (List<string>)paths["media_folders"]);

        var ai = Assert.IsType<Dictionary<string, object>>(payload["ai"]);
        Assert.Equal("null", ai["provider"]);
        Assert.Equal(30.0, ai["timeout_seconds"]);

        var voice = Assert.IsType<Dictionary<string, object>>(payload["voice"]);
        Assert.Equal("wav", voice["default_export_format"]);

        var loudness = Assert.IsType<Dictionary<string, object>>(payload["loudness"]);
        Assert.Equal(-14.0, loudness["target_lufs"]);
        Assert.Equal(-1.0, loudness["target_true_peak_dbtp"]);

        var download = Assert.IsType<Dictionary<string, object>>(payload["download"]);
        Assert.Equal(4096, download["max_download_size_mb"]);
        Assert.Null(download["downloads_dir"]);

        var privacy = Assert.IsType<Dictionary<string, object>>(payload["privacy"]);
        Assert.False((bool)privacy["telemetry_enabled"]);
    }

    [Fact]
    public void BuildUpdatePayload_SendsNonEmptyDownloadsDirUnchanged()
    {
        var values = SettingsViewSupport.FromSettingsResponse(SampleSettings()) with
        {
            DownloadDir = "/data/downloads",
        };
        var payload = SettingsViewSupport.BuildUpdatePayload(values);
        var download = (Dictionary<string, object>)payload["download"];

        Assert.Equal("/data/downloads", download["downloads_dir"]);
    }

    [Fact]
    public void BuildUpdatePayload_ReflectsChangedValues()
    {
        var baseValues = SettingsViewSupport.FromSettingsResponse(SampleSettings());
        var changed = baseValues with { Language = "en", AiEnabled = true, PrivacyAllowCloudAi = true };

        var payload = SettingsViewSupport.BuildUpdatePayload(changed);
        var general = (Dictionary<string, object>)payload["general"];
        var ai = (Dictionary<string, object>)payload["ai"];
        var privacy = (Dictionary<string, object>)payload["privacy"];

        Assert.Equal("en", general["language"]);
        Assert.True((bool)ai["enabled"]);
        Assert.True((bool)privacy["allow_cloud_ai"]);
    }

    [Fact]
    public void AddFolderIfMissing_AppendsNewFolder()
    {
        var existing = new List<string> { "/music" };
        var result = SettingsViewSupport.AddFolderIfMissing(existing, "/audiobooks");

        Assert.Equal(new[] { "/music", "/audiobooks" }, result);
        // Urspruengliche Liste bleibt unveraendert (keine Mutation des Inputs).
        Assert.Equal(new[] { "/music" }, existing);
    }

    [Fact]
    public void AddFolderIfMissing_DoesNotDuplicateExistingFolder()
    {
        var existing = new List<string> { "/music", "/audiobooks" };
        var result = SettingsViewSupport.AddFolderIfMissing(existing, "/music");

        Assert.Equal(new[] { "/music", "/audiobooks" }, result);
    }
}
