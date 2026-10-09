// WPF-unabhaengige Hilfslogik des KI-Centers (§25/§26, ADR-0017,
// MainWindow.AiCenter.cs), nach demselben Muster wie die anderen
// "*Support"-Klassen (MediaTableSupport.cs, DuplicatesSupport.cs, ...)
// hierher ausgelagert, damit sie im reinen net8.0-Testprojekt ohne
// Windows-Targeting-Pack getestet werden kann (AiCenterSupportTests.cs).
namespace GenesisMediaManager.Client;

public static class AiCenterSupport
{
    /// <summary>
    /// Exaktes Pendant zu Pythons <c>f"{score:.0%}"</c> in
    /// <c>ai_center_view.py::_on_search_clicked</c>: Prozentanzeige ohne
    /// Nachkommastellen und OHNE Leerzeichen vor dem Prozentzeichen
    /// ("87%"), "half to even" bei exakt halben Werten. Bewusst
    /// InvariantCulture: Das vorher in der Ansicht verwendete
    /// <c>"{...:P0}"</c> erzeugte die Variante der System-Locale (z.B.
    /// "87 %" mit Leerzeichen unter deutschem Windows) - derselbe
    /// Befundtyp wie DuplicatesSupport.FormatConfidence (dort liegt die
    /// identische Formatregel fuer die Duplikat-Confidence; die beiden
    /// bleiben bewusst getrennt, gemaess ADR-0009 "geteilt wird nur das
    /// Datenformat, nicht der Code").
    /// </summary>
    public static string FormatScore(double score) =>
        score.ToString("0%", System.Globalization.CultureInfo.InvariantCulture);
}
