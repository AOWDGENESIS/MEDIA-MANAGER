// Reine Hilfslogik der Einstellungen-Ansicht (MainWindow.xaml.cs ::
// ShowSettingsAsync), bewusst OHNE jede WPF-Abhaengigkeit ausgelagert
// (gleiches Muster wie MediaTableSupport.cs/Translator.cs) - nur so kann
// GenesisMediaManager.Client.Tests (reines net8.0) diese Logik ohne echten
// WPF-Control-Baum testen.
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

public static class SettingsViewSupport
{
    /// <summary>
    /// Baut die verschachtelte "updates"-Struktur fuer
    /// <see cref="GenesisApiClient.UpdateSettingsAsync"/> aus den aktuell in
    /// der UI sichtbaren Werten. Es werden bewusst ALLE Felder der in
    /// diesem ersten Inkrement abgedeckten Abschnitte (Allgemein/KI/
    /// Lautheit/Datenschutz) mitgesendet, nicht nur tatsaechlich geaenderte
    /// - das `PATCH /settings`-Merge-Verhalten am Core Service ueberschreibt
    /// dann unveraenderte Felder einfach mit ihrem bisherigen Wert, was
    /// nebenwirkungsfrei ist UND die Implementierung deutlich einfacher
    /// haelt als ein echtes Dirty-Field-Tracking. WICHTIG: die Schluessel
    /// MUESSEN exakt die snake_case-Namen aus
    /// core/genesis_core/config/__init__.py tragen (siehe Kommentar bei
    /// <see cref="GenesisApiClient.UpdateSettingsAsync"/> dazu, warum ein
    /// Dictionary hier KEINE automatische Namenskonvertierung bekommt).
    /// </summary>
    public static Dictionary<string, object> BuildUpdatePayload(SettingsFormValues values) => new()
    {
        ["general"] = new Dictionary<string, object>
        {
            ["language"] = values.Language,
            ["require_confirmation_for_bulk_changes"] = values.RequireConfirmationForBulkChanges,
        },
        ["paths"] = new Dictionary<string, object>
        {
            ["media_folders"] = values.MediaFolders,
        },
        ["ai"] = new Dictionary<string, object>
        {
            ["enabled"] = values.AiEnabled,
            ["provider"] = values.AiProvider,
            ["endpoint"] = values.AiEndpoint,
            ["model"] = values.AiModel,
            // Paritaet zu settings_view.py::_on_save_clicked - das Feld war
            // hier (und in der Ansicht) uebersehen worden, sodass der Wert
            // beim Speichern nie mitgesendet wurde.
            ["embedding_model"] = values.AiEmbeddingModel,
            ["timeout_seconds"] = values.AiTimeoutSeconds,
        },
        ["voice"] = new Dictionary<string, object>
        {
            ["enabled"] = values.VoiceEnabled,
            ["provider"] = values.VoiceProvider,
            ["default_export_format"] = values.VoiceDefaultExportFormat,
        },
        ["loudness"] = new Dictionary<string, object>
        {
            ["target_lufs"] = values.LoudnessTargetLufs,
            ["target_true_peak_dbtp"] = values.LoudnessTargetTruePeakDbtp,
            ["overwrite_originals"] = values.LoudnessOverwriteOriginals,
        },
        ["download"] = new Dictionary<string, object>
        {
            ["enabled"] = values.DownloadEnabled,
            ["enable_youtube"] = values.DownloadEnableYoutube,
            ["enable_tiktok"] = values.DownloadEnableTiktok,
            // Leerstring bedeutet "kein eigener Downloadordner gesetzt" -
            // wird als `null` gesendet (=> Core-Default data_dir/downloads),
            // identisch zum Verhalten von
            // ui-reference-pyside/genesis_ui/views/settings_view.py
            // (`self.download_dir_edit.text() or None`).
            ["downloads_dir"] = string.IsNullOrWhiteSpace(values.DownloadDir) ? null! : values.DownloadDir,
            ["max_download_size_mb"] = values.DownloadMaxSizeMb,
            ["min_free_disk_mb"] = values.DownloadMinFreeDiskMb,
            ["request_timeout_seconds"] = values.DownloadTimeoutSeconds,
        },
        ["privacy"] = new Dictionary<string, object>
        {
            ["telemetry_enabled"] = values.PrivacyTelemetryEnabled,
            ["allow_cloud_ai"] = values.PrivacyAllowCloudAi,
            ["allow_automatic_downloads"] = values.PrivacyAllowAutomaticDownloads,
            ["allow_automatic_deletion"] = values.PrivacyAllowAutomaticDeletion,
            ["allow_automatic_overwrite"] = values.PrivacyAllowAutomaticOverwrite,
        },
    };

    public static SettingsFormValues FromSettingsResponse(SettingsResponse settings) => new(
        Language: settings.General.Language,
        RequireConfirmationForBulkChanges: settings.General.RequireConfirmationForBulkChanges,
        MediaFolders: new List<string>(settings.Paths.MediaFolders),
        AiEnabled: settings.Ai.Enabled,
        AiProvider: settings.Ai.Provider,
        AiEndpoint: settings.Ai.Endpoint,
        AiModel: settings.Ai.Model,
        AiEmbeddingModel: settings.Ai.EmbeddingModel,
        AiTimeoutSeconds: settings.Ai.TimeoutSeconds,
        VoiceEnabled: settings.Voice.Enabled,
        VoiceProvider: settings.Voice.Provider,
        VoiceDefaultExportFormat: settings.Voice.DefaultExportFormat,
        LoudnessTargetLufs: settings.Loudness.TargetLufs,
        LoudnessTargetTruePeakDbtp: settings.Loudness.TargetTruePeakDbtp,
        LoudnessOverwriteOriginals: settings.Loudness.OverwriteOriginals,
        DownloadEnabled: settings.Download.Enabled,
        DownloadEnableYoutube: settings.Download.EnableYoutube,
        DownloadEnableTiktok: settings.Download.EnableTiktok,
        DownloadDir: settings.Download.DownloadsDir ?? string.Empty,
        DownloadMaxSizeMb: settings.Download.MaxDownloadSizeMb,
        DownloadMinFreeDiskMb: settings.Download.MinFreeDiskMb,
        DownloadTimeoutSeconds: settings.Download.RequestTimeoutSeconds,
        PrivacyTelemetryEnabled: settings.Privacy.TelemetryEnabled,
        PrivacyAllowCloudAi: settings.Privacy.AllowCloudAi,
        PrivacyAllowAutomaticDownloads: settings.Privacy.AllowAutomaticDownloads,
        PrivacyAllowAutomaticDeletion: settings.Privacy.AllowAutomaticDeletion,
        PrivacyAllowAutomaticOverwrite: settings.Privacy.AllowAutomaticOverwrite);

    /// <summary>
    /// Fuegt <paramref name="directory"/> der Ordnerliste hinzu, FALLS noch
    /// nicht vorhanden (identisches Verhalten zu
    /// ui-reference-pyside/genesis_ui/views/settings_view.py::
    /// _on_add_folder_clicked - keine Duplikate in der reinen Merkliste).
    /// Rein lesend/listenverwaltend, keine Dateisystem-Nebenwirkung.
    /// </summary>
    public static List<string> AddFolderIfMissing(IReadOnlyList<string> existing, string directory)
    {
        if (existing.Contains(directory)) return new List<string>(existing);
        var result = new List<string>(existing) { directory };
        return result;
    }
}

/// <summary>Reiner Werte-Schnappschuss der UI-Steuerelemente der
/// Einstellungen-Ansicht - absichtlich ein eigener Typ statt direkter
/// WPF-Control-Zugriffe, damit <see cref="SettingsViewSupport"/> ohne WPF
/// testbar bleibt.</summary>
public sealed record SettingsFormValues(
    string Language,
    bool RequireConfirmationForBulkChanges,
    List<string> MediaFolders,
    bool AiEnabled,
    string AiProvider,
    string AiEndpoint,
    string AiModel,
    string AiEmbeddingModel,
    double AiTimeoutSeconds,
    bool VoiceEnabled,
    string VoiceProvider,
    string VoiceDefaultExportFormat,
    double LoudnessTargetLufs,
    double LoudnessTargetTruePeakDbtp,
    bool LoudnessOverwriteOriginals,
    bool DownloadEnabled,
    bool DownloadEnableYoutube,
    bool DownloadEnableTiktok,
    string DownloadDir,
    int DownloadMaxSizeMb,
    int DownloadMinFreeDiskMb,
    double DownloadTimeoutSeconds,
    bool PrivacyTelemetryEnabled,
    bool PrivacyAllowCloudAi,
    bool PrivacyAllowAutomaticDownloads,
    bool PrivacyAllowAutomaticDeletion,
    bool PrivacyAllowAutomaticOverwrite);
