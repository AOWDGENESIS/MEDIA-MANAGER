// WPF-unabhaengige Hilfslogik des Dashboards (§5, MainWindow.xaml.cs::
// ShowDashboardAsync), nach demselben Muster wie die anderen "*Support"-
// Klassen hierher ausgelagert, damit sie im reinen net8.0-Testprojekt
// ohne Windows-Targeting-Pack getestet werden kann
// (DashboardSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class DashboardSupport
{
    /// <summary>
    /// Exaktes Pendant zur Zaehler-Formatierung der Dashboard-Karten in
    /// <c>dashboard.py::refresh</c>: <c>f"{count:,}".replace(",", ".")</c>
    /// - Tausendergruppen IMMER mit Punkt ("1.234"), unabhaengig von der
    /// Systemkultur (Python ist hier ebenfalls locale-unabhaengig). Das
    /// vorher in der Ansicht verwendete Standardformat "N0" ist
    /// kulturabhaengig und zeigte unter englischer Systemkultur "1,234"
    /// (achter Befund der Locale-Fehlerklasse). Fuer die Statistik-Karten
    /// (fehlende Dateien/laufende Jobs) nutzt die Referenz bewusst das
    /// einfache <c>str(count)</c> ohne Tausendergruppen - dafuer einfach
    /// <see cref="FormatStatCount"/> verwenden.
    /// </summary>
    public static string FormatCardCount(int count) =>
        count.ToString("N0", System.Globalization.CultureInfo.InvariantCulture).Replace(",", ".");

    /// <summary>
    /// Pendant zu <c>str(summary["missing_files"])</c> usw. in
    /// <c>dashboard.py::refresh</c>: schlichte Ganzzahl OHNE
    /// Tausendergruppen, aber ebenfalls kulturunabhaengig.
    /// </summary>
    public static string FormatStatCount(int count) =>
        count.ToString(System.Globalization.CultureInfo.InvariantCulture);
}
