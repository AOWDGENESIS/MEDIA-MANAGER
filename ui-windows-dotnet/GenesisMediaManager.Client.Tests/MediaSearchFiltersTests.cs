// Tests fuer die WPF-/HTTP-unabhaengige Filterlogik der Medientabelle
// (MediaSearchFilters in MediaTableSupport.cs, Pendant zu
// ui-reference-pyside/genesis_ui/dialogs/search_filters_dialog.py §9,
// Gap-Analyse C). Deckt dieselben Kernfaelle ab wie
// ui-reference-pyside/tests/test_search_filters_dialog.py::
// test_count_active_filters* (ohne/mit gesetzten Werten, Leerstring/
// False zaehlen nicht), ergaenzt um ToQueryString()-Faelle (Query-
// Parameter-Namen MUESSEN exakt zu core/genesis_core/api/app.py::
// list_media passen - siehe Kommentar dort).
namespace GenesisMediaManager.Client.Tests;

public class MediaSearchFiltersTests
{
    [Fact]
    public void CountActive_AllNull_ReturnsZero()
    {
        Assert.Equal(0, new MediaSearchFilters().CountActive());
    }

    [Fact]
    public void CountActive_CountsEachSetScalarField()
    {
        var filters = new MediaSearchFilters(Year: 2020, Genre: "Pop", Source: "CD");
        Assert.Equal(3, filters.CountActive());
    }

    [Fact]
    public void CountActive_WhitespaceOnlyString_DoesNotCount()
    {
        // Pendant zu Pythons `value not in (None, "", False)` - ein nur aus
        // Leerzeichen bestehendes Textfeld ist faktisch "nicht gesetzt".
        var filters = new MediaSearchFilters(Genre: "   ");
        Assert.Equal(0, filters.CountActive());
    }

    [Fact]
    public void CountActive_BooleanFlagTrue_Counts()
    {
        var filters = new MediaSearchFilters(HasQualityIssues: true, MissingMetadata: true,
            MissingCover: true, DuplicateOnly: true);
        Assert.Equal(4, filters.CountActive());
    }

    [Fact]
    public void CountActive_BooleanFlagExplicitFalse_DoesNotCount()
    {
        // Ein per Checkbox wieder AUSGESCHALTETES Flag (explizit `false`,
        // nicht `null`) darf nicht als "aktiver Filter" mitgezaehlt werden -
        // identisch zu Pythons `value not in (None, "", False)`.
        var filters = new MediaSearchFilters(HasQualityIssues: false, DuplicateOnly: false);
        Assert.Equal(0, filters.CountActive());
    }

    [Fact]
    public void CountActive_AllFieldsSet_ReturnsNineteen()
    {
        var filters = new MediaSearchFilters(
            Year: 2020, Genre: "Pop", Extension: "mp3", MinSizeBytes: 1000, MaxSizeBytes: 2000,
            MinDurationSeconds: 10, MaxDurationSeconds: 20, Source: "CD", Person: "Jemand",
            Series: "Reihe", Season: 1, EpisodeNumber: 2, AiStatus: "ai_generated",
            MinLufs: -20, MaxLufs: -10, HasQualityIssues: true, MissingMetadata: true,
            MissingCover: true, DuplicateOnly: true);
        Assert.Equal(19, filters.CountActive());
    }

    [Fact]
    public void ToQueryString_NoFilters_ReturnsEmptyString()
    {
        Assert.Equal(string.Empty, new MediaSearchFilters().ToQueryString());
    }

    [Fact]
    public void ToQueryString_UsesExactBackendParameterNames()
    {
        // Jeder Parametername MUSS exakt zu den Query-Parametern von
        // GET /media (core/genesis_core/api/app.py::list_media) passen -
        // ein Tippfehler hier wuerde den Filter bei der Core-API still
        // ignorieren (keine Fehlermeldung, da FastAPI unbekannte
        // Query-Parameter stillschweigend verwirft).
        var filters = new MediaSearchFilters(
            Year: 2020, Genre: "Pop", Extension: "mp3", MinSizeBytes: 1000, MaxSizeBytes: 2000,
            MinDurationSeconds: 10.5, MaxDurationSeconds: 20.5, Source: "CD", Person: "Jemand",
            Series: "Reihe", Season: 1, EpisodeNumber: 2, AiStatus: "ai_generated",
            MinLufs: -20, MaxLufs: -10, HasQualityIssues: true, MissingMetadata: true,
            MissingCover: true, DuplicateOnly: true);
        var query = filters.ToQueryString();

        foreach (var expected in new[]
        {
            "year=2020", "genre=Pop", "extension=mp3", "min_size_bytes=1000", "max_size_bytes=2000",
            "min_duration_s=10.5", "max_duration_s=20.5", "source=CD", "person=Jemand", "series=Reihe",
            "season=1", "episode_number=2", "ai_status=ai_generated", "min_lufs=-20", "max_lufs=-10",
            "has_quality_issues=true", "missing_metadata=true", "missing_cover=true", "duplicate_only=true",
        })
        {
            Assert.Contains(expected, query);
        }
    }

    [Fact]
    public void ToQueryString_StartsWithAmpersandWhenNotEmpty()
    {
        // ListMediaAsync haengt ToQueryString() direkt an eine bereits
        // bestehende Query ("?limit=...&offset=...") an - ein fehlendes
        // fuehrendes "&" wuerde eine kaputte URL erzeugen.
        var query = new MediaSearchFilters(Year: 2020).ToQueryString();
        Assert.StartsWith("&", query);
    }

    [Fact]
    public void ToQueryString_EscapesSpecialCharactersInTextFields()
    {
        var query = new MediaSearchFilters(Genre: "Rock & Roll").ToQueryString();
        Assert.DoesNotContain("Rock & Roll", query);
        Assert.Contains(Uri.EscapeDataString("Rock & Roll"), query);
    }

    [Fact]
    public void ToQueryString_FalseBooleanFlags_AreOmitted()
    {
        var query = new MediaSearchFilters(HasQualityIssues: false, DuplicateOnly: false).ToQueryString();
        Assert.Equal(string.Empty, query);
    }

    [Fact]
    public void ToQueryString_UsesInvariantCultureForDecimals()
    {
        // Core-API erwartet den Punkt als Dezimaltrennzeichen unabhaengig
        // von der UI-Sprache/Systemkultur (z.B. nicht das Komma einer
        // deutschen Locale) - siehe Kommentar an ToQueryString().
        var query = new MediaSearchFilters(MinLufs: -23.5).ToQueryString();
        Assert.Contains("min_lufs=-23.5", query);
        Assert.DoesNotContain(",", query);
    }
}
