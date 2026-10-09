// WPF-unabhaengige Hilfslogik der Job-Warteschlange (§35/§36,
// MainWindow.JobQueue.cs), nach demselben Muster wie die anderen
// "*Support"-Klassen hierher ausgelagert, damit sie im reinen
// net8.0-Testprojekt ohne Windows-Targeting-Pack getestet werden kann
// (JobQueueSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class JobQueueSupport
{
    /// <summary>
    /// Exaktes Pendant zur Fortschritts-Spalte in
    /// <c>job_queue_view.py::_reload</c>:
    /// <c>f"{processed}/{total} ({processed / total:.0%})"</c> wenn
    /// <c>total &gt; 0</c>, sonst der "unbekannt"-Text. Der Prozentanteil
    /// laeuft ueber <see cref="AiCenterSupport.FormatScore"/> (Custom-
    /// Format "0%", InvariantCulture, "half to even" wie Python): das
    /// vorher in der Ansicht verwendete Standardformat <c>P0</c> ist
    /// kulturabhaengig und zeigte unter deutschem Windows "42 %" statt
    /// Pythons "42%" (sechster Befund der Locale-Fehlerklasse).
    /// Kein Clamping: auch &gt;100% wird wie in der Referenz angezeigt.
    /// </summary>
    public static string FormatProgressText(int processed, int total, string unknownText)
    {
        if (total <= 0)
        {
            return unknownText;
        }
        return $"{processed}/{total} ({AiCenterSupport.FormatScore((double)processed / total)})";
    }
}
