// Tests fuer die WPF-unabhaengige Hilfslogik der Metadaten-Provider-Ansicht
// (ProvidersViewSupport.cs). Spiegelt die Kernfaelle, die auf Python-Seite in
// ui-reference-pyside/tests/test_gap_closure_settings_providers_view.py
// abgedeckt sind, soweit sie sich ohne echten WPF-Control-Baum pruefen
// lassen (Umwandlung SettingsResponse -> Formularwerte und zurueck in eine
// PATCH-Payload mit den exakt richtigen snake_case-Schluesseln, beschraenkt
// auf den "metadata"-Abschnitt).
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client.Tests;

public class ProvidersViewSupportTests
{
    private static SettingsResponse SampleSettings() => new(
        General: new GeneralSettings("de", false, true),
        Paths: new PathsSettingsInfo(new List<string> { "/music" }),
        Ai: new AiSettingsInfo(false, "null", "http://127.0.0.1:11434", "qwen2.5:0.5b", 30.0, "all-minilm"),
        Voice: new VoiceSettingsInfo(false, "null", "wav"),
        Loudness: new LoudnessSettingsInfo(-14.0, -1.0, false),
        Download: new DownloadSettingsInfo(false, true, true, null, 4096, 1024, 20.0),
        Privacy: new PrivacySettingsInfo(false, false, false, false, false),
        Metadata: new MetadataSettingsInfo(
            Enabled: true, MusicbrainzEnabled: true, AcoustidEnabled: false,
            AcoustidApiKey: "abc123", CoverartarchiveEnabled: true,
            ContactEmail: "team@example.invalid", RequestTimeoutSeconds: 15.0,
            MinConfidenceForSuggestion: 0.6));

    [Fact]
    public void FromSettingsResponse_CopiesAllMetadataFields()
    {
        var values = ProvidersViewSupport.FromSettingsResponse(SampleSettings());

        Assert.True(values.Enabled);
        Assert.True(values.MusicbrainzEnabled);
        Assert.False(values.AcoustidEnabled);
        Assert.Equal("abc123", values.AcoustidApiKey);
        Assert.True(values.CoverartarchiveEnabled);
        Assert.Equal("team@example.invalid", values.ContactEmail);
        Assert.Equal(15.0, values.RequestTimeoutSeconds);
        Assert.Equal(0.6, values.MinConfidenceForSuggestion);
    }

    [Fact]
    public void BuildUpdatePayload_OnlySendsMetadataSection()
    {
        var values = ProvidersViewSupport.FromSettingsResponse(SampleSettings());
        var payload = ProvidersViewSupport.BuildUpdatePayload(values);

        Assert.Single(payload);
        Assert.True(payload.ContainsKey("metadata"));
    }

    [Fact]
    public void BuildUpdatePayload_UsesExactSnakeCaseKeysAndValues()
    {
        var values = new ProviderFormValues(
            Enabled: true, MusicbrainzEnabled: false, AcoustidEnabled: true,
            AcoustidApiKey: "xyz", CoverartarchiveEnabled: false,
            ContactEmail: "someone@example.invalid", RequestTimeoutSeconds: 12.5,
            MinConfidenceForSuggestion: 0.75);
        var payload = ProvidersViewSupport.BuildUpdatePayload(values);

        var metadata = Assert.IsType<Dictionary<string, object>>(payload["metadata"]);
        Assert.Equal(true, metadata["enabled"]);
        Assert.Equal(false, metadata["musicbrainz_enabled"]);
        Assert.Equal(true, metadata["acoustid_enabled"]);
        Assert.Equal("xyz", metadata["acoustid_api_key"]);
        Assert.Equal(false, metadata["coverartarchive_enabled"]);
        Assert.Equal("someone@example.invalid", metadata["contact_email"]);
        Assert.Equal(12.5, metadata["request_timeout_seconds"]);
        Assert.Equal(0.75, metadata["min_confidence_for_suggestion"]);
    }
}
