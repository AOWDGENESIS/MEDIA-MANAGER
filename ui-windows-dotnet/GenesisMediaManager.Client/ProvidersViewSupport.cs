// Reine Hilfslogik der Metadaten-Provider-Ansicht (MainWindow.xaml.cs ::
// ShowProvidersAsync), bewusst OHNE jede WPF-Abhaengigkeit ausgelagert
// (gleiches Muster wie SettingsViewSupport.cs/MediaTableSupport.cs) - nur so
// kann GenesisMediaManager.Client.Tests (reines net8.0) diese Logik ohne
// echten WPF-Control-Baum testen.
//
// Betrifft die ONLINE-Metadatenabgleich-Provider (MusicBrainz, AcoustID,
// Cover Art Archive) - zu unterscheiden von den Download-/Import-Providern
// (YouTube/TikTok/etc., siehe SettingsViewSupport/DownloadSettingsInfo,
// deren Verwaltung bereits existiert). Nutzt denselben `PATCH /settings`-
// Endpunkt wie die Einstellungen-Ansicht, schreibt aber ausschliesslich in
// den `metadata`-Abschnitt. Siehe
// ui-reference-pyside/genesis_ui/views/providers_view.py (1:1-Vorbild).
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

public static class ProvidersViewSupport
{
    /// <summary>
    /// Baut die verschachtelte "updates"-Struktur fuer
    /// <see cref="GenesisApiClient.UpdateSettingsAsync"/> - identisch zum
    /// Python-Pendant <c>ProvidersView._on_save_clicked</c>, das ebenfalls
    /// NUR den <c>metadata</c>-Schluessel sendet (die uebrigen Abschnitte
    /// bleiben durch das PATCH-Merge-Verhalten am Core Service unberuehrt).
    /// </summary>
    public static Dictionary<string, object> BuildUpdatePayload(ProviderFormValues values) => new()
    {
        ["metadata"] = new Dictionary<string, object>
        {
            ["enabled"] = values.Enabled,
            ["musicbrainz_enabled"] = values.MusicbrainzEnabled,
            ["acoustid_enabled"] = values.AcoustidEnabled,
            ["acoustid_api_key"] = values.AcoustidApiKey,
            ["coverartarchive_enabled"] = values.CoverartarchiveEnabled,
            ["contact_email"] = values.ContactEmail,
            ["request_timeout_seconds"] = values.RequestTimeoutSeconds,
            ["min_confidence_for_suggestion"] = values.MinConfidenceForSuggestion,
        },
    };

    public static ProviderFormValues FromSettingsResponse(SettingsResponse settings) => new(
        Enabled: settings.Metadata.Enabled,
        MusicbrainzEnabled: settings.Metadata.MusicbrainzEnabled,
        AcoustidEnabled: settings.Metadata.AcoustidEnabled,
        AcoustidApiKey: settings.Metadata.AcoustidApiKey,
        CoverartarchiveEnabled: settings.Metadata.CoverartarchiveEnabled,
        ContactEmail: settings.Metadata.ContactEmail,
        RequestTimeoutSeconds: settings.Metadata.RequestTimeoutSeconds,
        MinConfidenceForSuggestion: settings.Metadata.MinConfidenceForSuggestion);
}

/// <summary>Reiner Werte-Schnappschuss der UI-Steuerelemente der
/// Metadaten-Provider-Ansicht - absichtlich ein eigener Typ statt direkter
/// WPF-Control-Zugriffe, damit <see cref="ProvidersViewSupport"/> ohne WPF
/// testbar bleibt.</summary>
public sealed record ProviderFormValues(
    bool Enabled,
    bool MusicbrainzEnabled,
    bool AcoustidEnabled,
    string AcoustidApiKey,
    bool CoverartarchiveEnabled,
    string ContactEmail,
    double RequestTimeoutSeconds,
    double MinConfidenceForSuggestion);
