// Tests fuer die WPF-unabhaengige Player-Hilfslogik (MediaPlayerSupport.cs
// und MediaSearchFiltersSupport.ParseLufsOrDefault in
// MediaFileActionsSupport.cs). Beide stehen im direkten Parity-Vergleich zu
// ui-reference-pyside/genesis_ui/widgets/player_bar.py (format_time) bzw.
// ui-reference-pyside/genesis_ui/dialogs/search_filters_dialog.py
// (min_lufs/max_lufs-Spinboxen) - die Erwartungswerte sind daher bewusst
// 1:1 aus dem Verhalten dieser Python-Referenzen abgeleitet.
namespace GenesisMediaManager.Client.Tests;

public class MediaPlayerSupportTests
{
    [Theory]
    [InlineData(0, "00:00")]
    [InlineData(12345, "00:12")]          // Beispiel aus dem player_bar.py-Docstring
    [InlineData(59_999, "00:59")]
    [InlineData(60_000, "01:00")]
    [InlineData(3_599_999, "59:59")]
    public void FormatTime_UnderOneHour_ReturnsMinutesSeconds(long milliseconds, string expected)
    {
        Assert.Equal(expected, MediaPlayerSupport.FormatTime(milliseconds));
    }

    [Theory]
    [InlineData(3_600_000, "1:00:00")]
    [InlineData(3_661_000, "1:01:01")]
    [InlineData(86_399_999, "23:59:59")]
    public void FormatTime_OneHourOrMore_IncludesHoursWithoutPadding(long milliseconds, string expected)
    {
        // Python: f"{hours}:{minutes:02d}:{seconds:02d}" - Stunden OHNE
        // Nullpadding, Minuten/Sekunden zweistellig.
        Assert.Equal(expected, MediaPlayerSupport.FormatTime(milliseconds));
    }

    [Theory]
    [InlineData(-1, "00:00")]
    [InlineData(-12345, "00:00")]
    public void FormatTime_NegativeValues_ClampToZero(long milliseconds, string expected)
    {
        // Pendant zu `if milliseconds < 0: milliseconds = 0` in
        // player_bar.py::format_time.
        Assert.Equal(expected, MediaPlayerSupport.FormatTime(milliseconds));
    }
}

public class MediaSearchFiltersSupportLufsTests
{
    [Fact]
    public void ParseLufsOrDefault_Zero_IsAValidLufsBoundAndKept()
    {
        // Deep-Review-Fund: Die 0 ist ein gueltiger LUFS-Grenzwert
        // ("mindestens/höchstens 0 LUFS") und darf NICHT wie bei den
        // uebrigen Zahlenfeldern als "nicht gesetzt" verworfen werden -
        // die Python-Spinboxen geben den Wert ebenfalls unveraendert weiter.
        Assert.Equal(0.0, MediaSearchFiltersSupport.ParseLufsOrDefault("0", -60));
        Assert.Equal(0.0, MediaSearchFiltersSupport.ParseLufsOrDefault("0", 10));
    }

    [Theory]
    [InlineData("-16.5", -16.5)]
    [InlineData("-60", -60)]
    [InlineData("10", 10)]
    public void ParseLufsOrDefault_ValidValues_AreParsedInvariantCulture(string text, double expected)
    {
        Assert.Equal(expected, MediaSearchFiltersSupport.ParseLufsOrDefault(text, -60));
    }

    [Theory]
    [InlineData("-80", -60)] // unterhalb des Spinbox-Bereichs -> clampen
    [InlineData("25", 10)]   // oberhalb des Spinbox-Bereichs -> clampen
    public void ParseLufsOrDefault_OutOfRangeValues_AreClampedToSpinboxRange(string text, double expected)
    {
        Assert.Equal(expected, MediaSearchFiltersSupport.ParseLufsOrDefault(text, -60));
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("abc")]
    [InlineData("1,5")] // Komma-Dezimaltrennzeichen ist hier ungueltig (InvariantCulture)
    public void ParseLufsOrDefault_EmptyOrInvalidInput_FallsBackToDefault(string text)
    {
        Assert.Equal(-60, MediaSearchFiltersSupport.ParseLufsOrDefault(text, -60));
        Assert.Equal(10, MediaSearchFiltersSupport.ParseLufsOrDefault(text, 10));
    }

    [Fact]
    public void ParseLufsOrDefault_NullText_FallsBackToDefault()
    {
        Assert.Equal(-60, MediaSearchFiltersSupport.ParseLufsOrDefault(null, -60));
    }
}
