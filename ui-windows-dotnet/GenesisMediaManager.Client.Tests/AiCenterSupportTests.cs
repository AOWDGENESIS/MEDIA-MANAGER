// Tests fuer AiCenterSupport.FormatScore (§25/§26, ADR-0017) - die
// Erwartungswerte sind 1:1 aus Pythons f"{score:.0%}" abgeleitet
// (ai_center_view.py::_on_search_clicked), inklusive des "half to even"-
// Rundungsverhaltens bei exakt halben Prozentwerten.
namespace GenesisMediaManager.Client.Tests;

public class AiCenterSupportTests
{
    [Theory]
    [InlineData(0.0, "0%")]
    [InlineData(0.5, "50%")]
    [InlineData(0.876, "88%")]
    [InlineData(0.99, "99%")]
    [InlineData(1.0, "100%")]
    public void FormatScore_RoundsToWholePercentWithoutSpace(double score, string expected)
    {
        // Python: f"{0.876:.0%}" -> "88%" - KEIN Leerzeichen vor dem
        // Prozentzeichen (das waere die de-DE-Variante von .NETs "P0").
        Assert.Equal(expected, AiCenterSupport.FormatScore(score));
    }

    [Theory]
    [InlineData(0.875, "88%")] // 87.5 -> "half to even" -> 88 (gerade)
    [InlineData(0.125, "12%")] // 12.5 -> "half to even" -> 12 (gerade)
    public void FormatScore_HalfValues_RoundHalfToEvenLikePython(double score, string expected)
    {
        Assert.Equal(expected, AiCenterSupport.FormatScore(score));
    }

    [Fact]
    public void FormatScore_IsCultureIndependent()
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
            Assert.Equal("87%", AiCenterSupport.FormatScore(0.87));
        }
        finally
        {
            System.Threading.Thread.CurrentThread.CurrentCulture = previous;
        }
    }
}
