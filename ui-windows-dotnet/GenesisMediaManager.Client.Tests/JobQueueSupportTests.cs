// Paritaets- und Locale-Tests fuer JobQueueSupport.cs - das WPF-freie
// Pendant zur Fortschritts-Spalte in job_queue_view.py::_reload. Der
// Prozentanteil erbt das "0%"/half-even-Verhalten von
// AiCenterSupport.FormatScore (dort bereits ausfuehrlich getestet,
// inkl. 0.875->"88%" und 0.125->"12%"); hier geht es um den
// Gesamtstring und die Kultur-Unabhaengigkeit unter de-DE.
using System.Globalization;
using Xunit;

namespace GenesisMediaManager.Client.Tests;

public class JobQueueSupportTests
{
    private static string RunUnderDeDe(Func<string> action)
    {
        var previous = CultureInfo.CurrentCulture;
        CultureInfo.CurrentCulture = new CultureInfo("de-DE");
        try
        {
            return action();
        }
        finally
        {
            CultureInfo.CurrentCulture = previous;
        }
    }

    [Fact]
    public void ProgressTextMatchesPythonFormat()
    {
        // f"{3}/{10} ({3/10:.0%})" -> "3/10 (30%)"
        Assert.Equal("3/10 (30%)", JobQueueSupport.FormatProgressText(3, 10, "?"));
        Assert.Equal("0/10 (0%)", JobQueueSupport.FormatProgressText(0, 10, "?"));
        Assert.Equal("10/10 (100%)", JobQueueSupport.FormatProgressText(10, 10, "?"));
    }

    [Fact]
    public void ProgressTextIsLocaleIndependent()
    {
        // Pythons :.0% ist locale-unabhaengig ("42%"); das vorher in der
        // Ansicht verwendete Standardformat P0 zeigte unter deutschem
        // Windows "42 %" (mit Leerzeichen) und wiche damit ab.
        Assert.Equal("42/100 (42%)", RunUnderDeDe(() => JobQueueSupport.FormatProgressText(42, 100, "?")));
    }

    [Fact]
    public void ProgressTextRoundsHalfToEvenLikePython()
    {
        // 1/8 = 12.5% -> Python :.0% rundet "half to even" auf 12%.
        Assert.Equal("1/8 (12%)", RunUnderDeDe(() => JobQueueSupport.FormatProgressText(1, 8, "?")));
        // 3/8 = 37.5% -> 38% (gerade Nachbarseite).
        Assert.Equal("3/8 (38%)", JobQueueSupport.FormatProgressText(3, 8, "?"));
    }

    [Fact]
    public void UnknownTotalFallsBackToUnknownText()
    {
        // Python: f"..." if total > 0 else tr("progress_unknown")
        Assert.Equal("?", JobQueueSupport.FormatProgressText(0, 0, "?"));
        Assert.Equal("unbekannt", JobQueueSupport.FormatProgressText(5, 0, "unbekannt"));
    }
}
