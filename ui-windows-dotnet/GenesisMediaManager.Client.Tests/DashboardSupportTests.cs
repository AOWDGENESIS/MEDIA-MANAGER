// Paritaets- und Locale-Tests fuer DashboardSupport.cs - Erwartungswerte
// 1:1 aus dashboard.py::refresh() abgeleitet:
// f"{count:,}".replace(",", ".") fuer die Medien-/Gesamt-Karten und
// str(count) fuer die Statistik-Karten.
using System.Globalization;
using Xunit;

namespace GenesisMediaManager.Client.Tests;

public class DashboardSupportTests
{
    private static string RunUnderEnUs(Func<string> action)
    {
        var previous = CultureInfo.CurrentCulture;
        CultureInfo.CurrentCulture = new CultureInfo("en-US");
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
    public void CardCountUsesDotThousandsSeparator()
    {
        // Python: f"{1234:,}".replace(",", ".") -> "1.234"
        Assert.Equal("1.234", DashboardSupport.FormatCardCount(1234));
        Assert.Equal("1.234.567", DashboardSupport.FormatCardCount(1234567));
        Assert.Equal("0", DashboardSupport.FormatCardCount(0));
        Assert.Equal("999", DashboardSupport.FormatCardCount(999));
    }

    [Fact]
    public void CardCountIsLocaleIndependent()
    {
        // Das vorherige "N0" zeigte unter en-US "1,234" statt "1.234".
        Assert.Equal("1.234", RunUnderEnUs(() => DashboardSupport.FormatCardCount(1234)));
    }

    [Fact]
    public void StatCountHasNoThousandsSeparator()
    {
        // Python: str(summary["missing_files"]) -> "1234" (keine Gruppen).
        Assert.Equal("1234", DashboardSupport.FormatStatCount(1234));
        Assert.Equal("0", DashboardSupport.FormatStatCount(0));
    }
}
