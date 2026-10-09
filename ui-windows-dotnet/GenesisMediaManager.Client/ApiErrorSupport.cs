// WPF-unabhaengige Zusammenbau-Logik des zentralen API-Fehlerdialogs
// (§37, Gap L - Pendant zu error_dialog.show_api_error() in
// ui-reference-pyside/genesis_ui/dialogs/error_dialog.py), nach demselben
// Muster wie die anderen "*Support"-Klassen hierher ausgelagert, damit sie
// im reinen net8.0-Testprojekt ohne Windows-Targeting-Pack getestet werden
// kann (ApiErrorSupportTests.cs). Die eigentliche Dialoganzeige lebt in
// MainWindow.xaml.cs::ShowApiError.
namespace GenesisMediaManager.Client;

public static class ApiErrorSupport
{
    /// <summary>
    /// Exaktes Pendant zum Textaufbau in
    /// <c>error_dialog.py::show_api_error()</c>: auf die (optionale)
    /// handlungsspezifische Meldung folgt bei vorhandener Fehler-ID eine
    /// Leerzeile + die Fehler-ID-Zeile, darunter der Loesungshinweis -
    /// genau die beiden Angaben, die der Nutzer braucht, um den Vorfall im
    /// Fehler-Center (nav.error_center) wiederzufinden, ohne selbst
    /// Logdateien durchsuchen zu muessen. Beide Zusatzzeilen werden
    /// NUR bei nicht-leeren Werten angehaengt (Python: <c>if
    /// exc.error_id:</c> / <c>if exc.solution_hint:</c>). Die Zeilen
    /// selbst werden vom Aufrufer bereits uebersetzt uebergeben
    /// (i18n-Schluessel error_dialog.error_id_line /
    /// error_dialog.solution_hint_line).
    /// </summary>
    public static string BuildApiErrorText(string message, string? errorIdLine, string? solutionHintLine)
    {
        var text = message;
        if (!string.IsNullOrEmpty(errorIdLine))
        {
            text += "\n\n" + errorIdLine;
        }
        if (!string.IsNullOrEmpty(solutionHintLine))
        {
            text += "\n" + solutionHintLine;
        }
        return text;
    }
}
