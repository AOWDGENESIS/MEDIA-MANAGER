// Paritaets- und Locale-Tests fuer VoiceStudioSupport.cs - das WPF-freie
// Pendant zu den Formatierungen in voice_studio_view.py::_reload_history.
// Die de-DE-Kulturtests spiegeln den wiederkehrenden Befund: .NET-
// Standardformate sind kulturabhaengig, Python-f-Strings sind es nicht.
using System.Globalization;
using Xunit;

namespace GenesisMediaManager.Client.Tests;

public class VoiceStudioSupportTests
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
    public void DurationFormatsWithInvariantDecimalPoint()
    {
        // f"{3.5:.1f}s" -> "3.5s" auch unter deutscher Kultur; das alte
        // $"{r.DurationSeconds:F1}s" haette dort "3,5s" ergeben.
        Assert.Equal("3.5s", RunUnderDeDe(() => VoiceStudioSupport.FormatHistoryDuration(3.5)));
        Assert.Equal("3.5s", VoiceStudioSupport.FormatHistoryDuration(3.5));
        Assert.Equal("10.0s", RunUnderDeDe(() => VoiceStudioSupport.FormatHistoryDuration(10.0)));
    }

    [Fact]
    public void DurationNullOrZeroFallsBackToDash()
    {
        // Python: f"{...}" if r.get("duration_seconds") else "-" - sowohl
        // None als auch 0.0 (falsy!) ergeben "-".
        Assert.Equal("-", VoiceStudioSupport.FormatHistoryDuration(null));
        Assert.Equal("-", VoiceStudioSupport.FormatHistoryDuration(0.0));
    }

    [Fact]
    public void CreatedAtIsTruncatedToNineteenCharsBeforeReplacingT()
    {
        // (r.get("created_at") or "")[:19].replace("T", " ")
        Assert.Equal(
            "2026-10-08 12:34:56",
            VoiceStudioSupport.FormatHistoryCreatedAt("2026-10-08T12:34:56.789012+00:00"));
        Assert.Equal(
            "2026-10-08 12:34:56",
            VoiceStudioSupport.FormatHistoryCreatedAt("2026-10-08T12:34:56"));
    }

    [Fact]
    public void CreatedAtNullOrShortValuesAreSafe()
    {
        Assert.Equal(string.Empty, VoiceStudioSupport.FormatHistoryCreatedAt(null));
        Assert.Equal(string.Empty, VoiceStudioSupport.FormatHistoryCreatedAt(""));
        Assert.Equal("2026-10-08", VoiceStudioSupport.FormatHistoryCreatedAt("2026-10-08"));
    }
}
