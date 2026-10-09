// WPF-unabhaengige Hilfslogik der Duplikate-Ansicht (§21, ADR-0013,
// MainWindow.Duplicates.cs), nach demselben Muster wie die anderen
// "*Support"-Klassen (MediaTableSupport.cs, LibraryBrowserSupport.cs, ...)
// hierher ausgelagert, damit sie im reinen net8.0-Testprojekt ohne
// Windows-Targeting-Pack getestet werden kann (DuplicatesSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class DuplicatesSupport
{
    /// <summary>
    /// Exaktes Pendant zu Pythons <c>f"{confidence:.0%}"</c> in
    /// <c>duplicates_view.py::_reload</c>: Prozentanzeige ohne
    /// Nachkommastellen und OHNE Leerzeichen vor dem Prozentzeichen
    /// ("87%"), kaufmaennisch gerundet bzw. "half to even" bei exakt
    /// halben Werten (0.875 -> "88%", 0.125 -> "12%"). Bewusst
    /// InvariantCulture: Das vorher in der Ansicht verwendete
    /// <c>"{...:P0}"</c> erzeugte die Variante der System-Locale (z.B.
    /// "87 %" mit Leerzeichen unter deutschem Windows) - damit wich die
    /// Anzeige je nach Systemkultur von der Python-Referenz-UI ab.
    /// </summary>
    public static string FormatConfidence(double confidence) =>
        confidence.ToString("0%", System.Globalization.CultureInfo.InvariantCulture);
}
