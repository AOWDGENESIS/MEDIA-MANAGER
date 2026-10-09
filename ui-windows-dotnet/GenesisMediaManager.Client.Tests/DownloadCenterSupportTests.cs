// Tests fuer DownloadCenterSupport.cs (§30-§32, ADR-0019) - die
// Erwartungswerte sind 1:1 aus _format_duration/_format_size in
// download_center_view.py abgeleitet, ergaenzt um das Python-`or`-
// Fallback-Idiom (OrFallback).
namespace GenesisMediaManager.Client.Tests;

public class DownloadCenterSupportTests
{
    [Fact]
    public void FormatDuration_Null_ReturnsUnknownText()
    {
        Assert.Equal("unbekannt", DownloadCenterSupport.FormatDuration(null, "unbekannt"));
    }

    [Theory]
    [InlineData(0, "0:00")]
    [InlineData(59, "0:59")]
    [InlineData(61, "1:01")]
    [InlineData(3599, "59:59")]
    public void FormatDuration_UnderOneHour_MinutesColonSeconds(double seconds, string expected)
    {
        Assert.Equal(expected, DownloadCenterSupport.FormatDuration(seconds, "-"));
    }

    [Theory]
    [InlineData(3600, "1:00:00")]
    [InlineData(3661, "1:01:01")]
    public void FormatDuration_OneHourOrMore_IncludesHours(double seconds, string expected)
    {
        Assert.Equal(expected, DownloadCenterSupport.FormatDuration(seconds, "-"));
    }

    [Fact]
    public void FormatDuration_TruncatesInsteadOfRoundingLikePythonInt()
    {
        // Python: int(90.7) == 90 -> "1:30" (TRUNKIERUNG, kein Runden).
        Assert.Equal("1:30", DownloadCenterSupport.FormatDuration(90.7, "-"));
    }

    [Theory]
    [InlineData(null, "-")]
    [InlineData(0, "-")]
    public void FormatSize_NullOrZero_ReturnsDash(long? numBytes, string expected)
    {
        Assert.Equal(expected, DownloadCenterSupport.FormatSize(numBytes));
    }

    [Theory]
    [InlineData(1, "1.0 B")]
    [InlineData(1023, "1023.0 B")]
    [InlineData(1024, "1.0 KB")]
    [InlineData(1536, "1.5 KB")]
    [InlineData(1048576, "1.0 MB")]
    [InlineData(1073741824, "1.0 GB")]
    public void FormatSize_Uses1024StepsWithOneDecimal(long numBytes, string expected)
    {
        Assert.Equal(expected, DownloadCenterSupport.FormatSize(numBytes));
    }

    [Fact]
    public void FormatSize_IsCultureIndependent()
    {
        // Python: f"{size:.1f}" ist locale-unabhaengig ("1.5 KB") - unter
        // deutschem Windows wuerde Interpolationsformat sonst "1,5 KB"
        // zeigen (derselbe Befundtyp wie bei der Confidence-Anzeige).
        var previous = System.Threading.Thread.CurrentThread.CurrentCulture;
        try
        {
            System.Threading.Thread.CurrentThread.CurrentCulture =
                System.Globalization.CultureInfo.GetCultureInfo("de-DE");
            Assert.Equal("1.5 KB", DownloadCenterSupport.FormatSize(1536));
        }
        finally
        {
            System.Threading.Thread.CurrentThread.CurrentCulture = previous;
        }
    }

    [Theory]
    [InlineData(null, "Fallback", "Fallback")]
    [InlineData("", "Fallback", "Fallback")]
    [InlineData("Wert", "Fallback", "Wert")]
    public void OrFallback_NullOrEmpty_UsesFallback(string? value, string fallback, string expected)
    {
        // Pendant zu Pythons `x or fallback` (None UND "" sind falsy).
        Assert.Equal(expected, DownloadCenterSupport.OrFallback(value, fallback));
    }
}
