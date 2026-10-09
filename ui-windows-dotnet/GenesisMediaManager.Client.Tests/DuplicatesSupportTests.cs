// Tests fuer DuplicatesSupport.FormatConfidence (§21, ADR-0013) - die
// Erwartungswerte sind 1:1 aus Pythons f"{confidence:.0%}" abgeleitet
// (duplicates_view.py::_reload), inklusive des "half to even"-
// Rundungsverhaltens bei exakt halben Prozentwerten.
namespace GenesisMediaManager.Client.Tests;

public class DuplicatesSupportTests
{
    [Theory]
    [InlineData(0.0, "0%")]
    [InlineData(0.5, "50%")]
    [InlineData(0.876, "88%")]
    [InlineData(0.99, "99%")]
    [InlineData(1.0, "100%")]
    public void FormatConfidence_RoundsToWholePercentWithoutSpace(double confidence, string expected)
    {
        // Python: f"{0.876:.0%}" -> "88%" - KEIN Leerzeichen vor dem
        // Prozentzeichen (das waere die de-DE-Variante von .NETs "P0").
        Assert.Equal(expected, DuplicatesSupport.FormatConfidence(confidence));
    }

    [Theory]
    [InlineData(0.875, "88%")] // 87.5 -> "half to even" -> 88 (gerade)
    [InlineData(0.125, "12%")] // 12.5 -> "half to even" -> 12 (gerade)
    public void FormatConfidence_HalfValues_RoundHalfToEvenLikePython(double confidence, string expected)
    {
        Assert.Equal(expected, DuplicatesSupport.FormatConfidence(confidence));
    }

    [Fact]
    public void FormatConfidence_IsCultureIndependent()
    {
        // Die Anzeige darf NICHT von der Systemkultur abhaengen (unter
        // deutschem Windows wuerde "P0" z.B. "87 %" mit Leerzeichen
        // liefern) - hier explizit mit einer Kultur mit abweichendem
        // Prozentmuster geprueft.
        var previous = System.Threading.Thread.CurrentThread.CurrentCulture;
        try
        {
            System.Threading.Thread.CurrentThread.CurrentCulture =
                System.Globalization.CultureInfo.GetCultureInfo("de-DE");
            Assert.Equal("87%", DuplicatesSupport.FormatConfidence(0.87));
        }
        finally
        {
            System.Threading.Thread.CurrentThread.CurrentCulture = previous;
        }
    }
}
