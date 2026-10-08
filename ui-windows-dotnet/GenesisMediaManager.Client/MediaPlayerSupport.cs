// WPF-unabhaengige Hilfslogik fuer den eingebetteten Medienplayer der
// Medientabelle (§60, Gap-Analyse G - Pendant zu
// ui-reference-pyside/genesis_ui/widgets/player_bar.py). Nach demselben
// Muster wie die anderen "*Support"-Klassen (MediaTableSupport.cs,
// MediaCoverSupport.cs, ...) hierher ausgelagert, damit die reine
// Formatierungslogik im net8.0-Testprojekt ohne Windows-Targeting-Pack
// getestet werden kann (MediaPlayerSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class MediaPlayerSupport
{
    /// <summary>
    /// Exaktes Pendant zu <c>format_time()</c> in
    /// <c>ui-reference-pyside/genesis_ui/widgets/player_bar.py</c>:
    /// Millisekunden -> <c>"MM:SS"</c>, mit Stundenanteil
    /// (<c>"H:MM:SS"</c>) erst ab einer Stunde (lange Hoerbuch-Kapitel/
    /// Filme, §23/§24). Negative Werte werden wie in der Python-Referenz
    /// auf 0 geklemmt (verteidigt gegen fehlerhafte Player-Zustandsdaten,
    /// Grundprinzip #16: kein Absturz, kein Unsinn in der UI).
    /// </summary>
    public static string FormatTime(long milliseconds)
    {
        if (milliseconds < 0)
        {
            milliseconds = 0;
        }
        var totalSeconds = milliseconds / 1000;
        var hours = totalSeconds / 3600;
        var minutes = (totalSeconds % 3600) / 60;
        var seconds = totalSeconds % 60;
        return hours > 0
            ? $"{hours}:{minutes:D2}:{seconds:D2}"
            : $"{minutes:D2}:{seconds:D2}";
    }
}
