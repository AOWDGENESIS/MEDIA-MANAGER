// WPF-unabhaengige Hilfslogik des Download-/Import-Centers (§30-§32,
// ADR-0019, MainWindow.DownloadCenter.cs), nach demselben Muster wie die
// anderen "*Support"-Klassen (MediaTableSupport.cs, DuplicatesSupport.cs,
// ...) hierher ausgelagert, damit sie im reinen net8.0-Testprojekt ohne
// Windows-Targeting-Pack getestet werden kann
// (DownloadCenterSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class DownloadCenterSupport
{
    /// <summary>
    /// Exaktes Pendant zu <c>_format_duration()</c> in
    /// <c>download_center_view.py</c>: <c>null</c> -> der uebergebene
    /// "unbekannt"-Text; sonst Ganzzahl-TRUNKIERUNG (Pythons
    /// <c>int(seconds)</c>, KEIN Runden) und <c>"H:MM:SS"</c> bzw.
    /// <c>"M:SS"</c> (Stunden nur bei Bedarf).
    /// </summary>
    public static string FormatDuration(double? seconds, string unknownText)
    {
        if (seconds is null) return unknownText;
        var total = (int)seconds.Value;
        var hours = total / 3600;
        var minutes = total % 3600 / 60;
        var secs = total % 60;
        return hours > 0 ? $"{hours}:{minutes:D2}:{secs:D2}" : $"{minutes}:{secs:D2}";
    }

    /// <summary>
    /// Exaktes Pendant zu <c>_format_size()</c> in
    /// <c>download_center_view.py</c>: <c>null</c>/0 -> "-", sonst
    /// 1024er-Stufen B/KB/MB/GB mit EINER Nachkommastelle ("1.5 KB").
    /// Bewusst InvariantCulture: Pythons f"{size:.1f}" ist ebenfalls
    /// locale-unabhaengig - das vorher in der Ansicht verwendete
    /// Interpolationsformat zeigte unter deutschem Windows "1,5 MB" und
    /// wich damit von der Python-Referenz-UI ab (derselbe Befundtyp wie
    /// DuplicatesSupport.FormatConfidence).
    /// </summary>
    public static string FormatSize(long? numBytes)
    {
        if (numBytes is null or 0) return "-";
        double size = numBytes.Value;
        foreach (var unit in new[] { "B", "KB", "MB" })
        {
            if (size < 1024)
            {
                return $"{size.ToString("F1", System.Globalization.CultureInfo.InvariantCulture)} {unit}";
            }
            size /= 1024;
        }
        return $"{size.ToString("F1", System.Globalization.CultureInfo.InvariantCulture)} GB";
    }

    /// <summary>
    /// Pendant zu Pythons <c>x or fallback</c>-Idiom auf Textfeldern in
    /// <c>download_center_view.py</c> (z.B. <c>meta.get("title") or
    /// unknown</c>, <c>selected_option_id or "default"</c>): sowohl
    /// <c>null</c> als auch der LEERSTRING gelten als "nicht vorhanden"
    /// und werden durch den Fallback ersetzt. Das vorher in der Ansicht
    /// verwendete C#-<c>??</c> liess Leerstrings dagegen durchrutschen.
    /// </summary>
    public static string OrFallback(string? value, string fallback) =>
        string.IsNullOrEmpty(value) ? fallback : value;
}
