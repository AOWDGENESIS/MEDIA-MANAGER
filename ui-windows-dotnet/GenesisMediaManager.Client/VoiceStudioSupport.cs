// WPF-unabhaengige Hilfslogik des Voice Studios (§28/§29, ADR-0018,
// MainWindow.VoiceStudio.cs), nach demselben Muster wie die anderen
// "*Support"-Klassen (MediaTableSupport.cs, DuplicatesSupport.cs, ...)
// hierher ausgelagert, damit sie im reinen net8.0-Testprojekt ohne
// Windows-Targeting-Pack getestet werden kann
// (VoiceStudioSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class VoiceStudioSupport
{
    /// <summary>
    /// Exaktes Pendant zur Dauer-Spalte in
    /// <c>voice_studio_view.py::_reload_history</c>:
    /// <c>f"{d:.1f}s" if r.get("duration_seconds") else "-"</c>. Das
    /// Python-<c>if</c> ist FALSY - sowohl <c>null</c> als auch 0.0
    /// ergeben "-". Bewusst InvariantCulture: Pythons f-String ist
    /// ebenfalls locale-unabhaengig ("3.5s"), das vorher in der Ansicht
    /// verwendete Interpolationsformat zeigte unter deutschem Windows
    /// "3,5s" (fuenfter Befund dieser Klasse).
    /// </summary>
    public static string FormatHistoryDuration(double? seconds) =>
        seconds is null || seconds == 0
            ? "-"
            : $"{seconds.Value.ToString("F1", System.Globalization.CultureInfo.InvariantCulture)}s";

    /// <summary>
    /// Exaktes Pendant zur Erstellt-Am-Spalte in
    /// <c>voice_studio_view.py::_reload_history</c>:
    /// <c>(r.get("created_at") or "")[:19].replace("T", " ")</c> - zuerst
    /// auf 19 Zeichen KUERZEN ("2026-10-08T12:34:56.789..." ->
    /// "2026-10-08T12:34:56"), DANN das T ersetzen. Das vorherige WPF
    /// ersetzte nur das T und zeigte dadurch Mikrosekunden/Zeitzonen-Reste.
    /// </summary>
    public static string FormatHistoryCreatedAt(string? createdAt)
    {
        var value = createdAt ?? string.Empty;
        if (value.Length > 19)
        {
            value = value[..19];
        }
        return value.Replace("T", " ");
    }
}
