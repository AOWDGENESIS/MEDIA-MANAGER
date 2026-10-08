// Tests fuer die WPF-unabhaengige Hilfslogik der Bibliotheks-Drill-down-
// Ansicht (LibraryBrowserSupport.cs, Pendant zu
// ui-reference-pyside/genesis_ui/views/library_view.py, §9/§62,
// Gap-Analyse B). Deckt die Nav-Key->Kind-Zuordnung sowie den
// Detailtext-Aufbau fuer alle sechs Bibliotheks-"Kinds" (artists/albums/
// titles/genres/persons/sources) ab - letzte bislang ungetestete
// "Support"-Klasse im Client (gefunden im Deep-Search).
using GenesisMediaManager.Client.Api;
using GenesisMediaManager.Client.I18n;

namespace GenesisMediaManager.Client.Tests;

public class LibraryBrowserSupportTests
{
    // --- LibraryKindByNavKey ------------------------------------------------

    [Theory]
    [InlineData("nav.artists", "artists")]
    [InlineData("nav.albums", "albums")]
    [InlineData("nav.titles", "titles")]
    [InlineData("nav.genres", "genres")]
    [InlineData("nav.persons", "persons")]
    [InlineData("nav.sources", "sources")]
    public void LibraryKindByNavKey_MapsEachLibrarySectionItemToItsKind(string navKey, string expectedKind)
    {
        Assert.True(LibraryBrowserSupport.LibraryKindByNavKey.TryGetValue(navKey, out var kind));
        Assert.Equal(expectedKind, kind);
    }

    [Fact]
    public void LibraryKindByNavKey_DoesNotContainUnrelatedNavItems()
    {
        Assert.False(LibraryBrowserSupport.LibraryKindByNavKey.ContainsKey("nav.dashboard"));
        Assert.False(LibraryBrowserSupport.LibraryKindByNavKey.ContainsKey("nav.music"));
    }

    // --- Fmt / FmtDuration ---------------------------------------------------

    [Fact]
    public void Fmt_NullValue_ReturnsNoneFallback()
    {
        var tr = new Translator("de");
        Assert.Equal(tr.Tr("library_view.value_none"), LibraryBrowserSupport.Fmt(null, tr));
    }

    [Fact]
    public void Fmt_EmptyString_ReturnsNoneFallback()
    {
        var tr = new Translator("de");
        Assert.Equal(tr.Tr("library_view.value_none"), LibraryBrowserSupport.Fmt("", tr));
    }

    [Fact]
    public void Fmt_NonEmptyString_ReturnsValueItself()
    {
        var tr = new Translator("de");
        Assert.Equal("Pink Floyd", LibraryBrowserSupport.Fmt("Pink Floyd", tr));
    }

    [Fact]
    public void Fmt_IntValue_ReturnsStringRepresentation()
    {
        var tr = new Translator("de");
        Assert.Equal("1973", LibraryBrowserSupport.Fmt(1973, tr));
    }

    [Fact]
    public void FmtDuration_Null_ReturnsNoneFallback()
    {
        var tr = new Translator("de");
        Assert.Equal(tr.Tr("library_view.value_none"), LibraryBrowserSupport.FmtDuration(null, tr));
    }

    [Theory]
    [InlineData(0.0, "0:00")]
    [InlineData(5.0, "0:05")]
    [InlineData(65.0, "1:05")]
    [InlineData(600.0, "10:00")]
    [InlineData(3661.0, "61:01")]
    public void FmtDuration_FormatsSecondsAsMinutesColonSeconds(double seconds, string expected)
    {
        var tr = new Translator("de");
        Assert.Equal(expected, LibraryBrowserSupport.FmtDuration(seconds, tr));
    }

    [Fact]
    public void FmtDuration_RoundsToNearestSecond()
    {
        var tr = new Translator("de");
        Assert.Equal("1:00", LibraryBrowserSupport.FmtDuration(59.6, tr));
    }

    // --- RenderArtistDetail ---------------------------------------------------

    [Fact]
    public void RenderArtistDetail_WithoutAlbums_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var detail = new LibraryArtistDetail(1, "Pink Floyd", "Floyd, Pink", null, new List<LibraryAlbumSummary>());
        var text = LibraryBrowserSupport.RenderArtistDetail(detail, tr);

        Assert.Contains("Pink Floyd", text);
        Assert.Contains(tr.Tr("library_view.artists.detail_albums_none"), text);
    }

    [Fact]
    public void RenderArtistDetail_WithAlbums_ListsEachAlbumWithTrackCount()
    {
        var tr = new Translator("de");
        var detail = new LibraryArtistDetail(1, "Pink Floyd", null, "mb-123", new List<LibraryAlbumSummary>
        {
            new(10, "The Dark Side of the Moon", 1, "Pink Floyd", 1973, 10),
            new(11, "Wish You Were Here", 1, "Pink Floyd", 1975, 5),
        });
        var text = LibraryBrowserSupport.RenderArtistDetail(detail, tr);

        Assert.Contains("The Dark Side of the Moon", text);
        Assert.Contains("Wish You Were Here", text);
        Assert.Contains("1973", text);
        Assert.Contains("mb-123", text);
        Assert.DoesNotContain(tr.Tr("library_view.artists.detail_albums_none"), text);
    }

    [Fact]
    public void RenderArtistDetail_MissingSortNameAndMbid_ShowNoneFallback()
    {
        var tr = new Translator("de");
        var detail = new LibraryArtistDetail(1, "Unknown Artist", null, null, new List<LibraryAlbumSummary>());
        var text = LibraryBrowserSupport.RenderArtistDetail(detail, tr);

        // Fallback-Text erscheint mehrfach (Sortname + MBID + Albenliste leer).
        Assert.Contains(tr.Tr("library_view.value_none"), text);
    }

    // --- RenderAlbumDetail ------------------------------------------------

    [Fact]
    public void RenderAlbumDetail_WithoutTracks_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var detail = new LibraryAlbumDetail(1, "The Wall", 2, "Pink Floyd", 1979, null, new List<LibraryTrackSummary>());
        var text = LibraryBrowserSupport.RenderAlbumDetail(detail, tr);

        Assert.Contains("The Wall", text);
        Assert.Contains(tr.Tr("library_view.albums.detail_tracks_none"), text);
    }

    [Fact]
    public void RenderAlbumDetail_WithTracks_ShowsDiscTrackPositionAndDuration()
    {
        var tr = new Translator("de");
        var detail = new LibraryAlbumDetail(1, "The Wall", 2, "Pink Floyd", 1979, "mb-456", new List<LibraryTrackSummary>
        {
            new(100, 1000, "Another Brick in the Wall, Part 2", 5, 1, 238.0),
            new(101, 1001, null, null, 1, null),
        });
        var text = LibraryBrowserSupport.RenderAlbumDetail(detail, tr);

        Assert.Contains("1.5", text); // disc.track Position
        Assert.Contains("Another Brick in the Wall, Part 2", text);
        Assert.Contains("3:58", text); // 238s -> 3:58
        Assert.Contains("1.?", text); // fehlende Tracknummer -> "?"
    }

    [Fact]
    public void RenderAlbumDetail_MissingDiscNumber_DefaultsToDiscOne()
    {
        var tr = new Translator("de");
        var detail = new LibraryAlbumDetail(1, "Compilation", null, null, null, null, new List<LibraryTrackSummary>
        {
            new(200, 2000, "Intro", 1, null, 10.0),
        });
        var text = LibraryBrowserSupport.RenderAlbumDetail(detail, tr);

        Assert.Contains("1.1", text);
    }

    // --- RenderTitleDetail --------------------------------------------------

    [Fact]
    public void RenderTitleDetail_RendersAllFields()
    {
        var tr = new Translator("de");
        var row = new LibraryTrackListEntry(5, 50, "Money", "Pink Floyd", "The Dark Side of the Moon", "Progressive Rock", 1973, 6, 382.0);
        var text = LibraryBrowserSupport.RenderTitleDetail(row, tr);

        Assert.Contains("Money", text);
        Assert.Contains("Pink Floyd", text);
        Assert.Contains("The Dark Side of the Moon", text);
        Assert.Contains("Progressive Rock", text);
        Assert.Contains("1973", text);
        Assert.Contains("6", text);
        Assert.Contains("6:22", text); // 382s -> 6:22
        Assert.Contains("50", text); // MediaFileId
    }

    [Fact]
    public void RenderTitleDetail_MissingFields_ShowNoneFallback()
    {
        var tr = new Translator("de");
        var row = new LibraryTrackListEntry(5, 50, null, null, null, null, null, null, null);
        var text = LibraryBrowserSupport.RenderTitleDetail(row, tr);

        Assert.Contains(tr.Tr("library_view.value_none"), text);
    }

    // --- RenderGenreDetail ----------------------------------------------------

    [Fact]
    public void RenderGenreDetail_WithoutTracks_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var detail = new LibraryGenreDetail(1, "Ambient", new List<LibraryTrackListEntry>());
        var text = LibraryBrowserSupport.RenderGenreDetail(detail, tr);

        Assert.Contains("Ambient", text);
        Assert.Contains(tr.Tr("library_view.genres.detail_tracks_none"), text);
    }

    [Fact]
    public void RenderGenreDetail_TrackWithoutAlbum_ShowsNoAlbumFallback()
    {
        var tr = new Translator("de");
        var detail = new LibraryGenreDetail(1, "Ambient", new List<LibraryTrackListEntry>
        {
            new(1, 10, "Weightless", "Marconi Union", null, "Ambient", null, null, null),
        });
        var text = LibraryBrowserSupport.RenderGenreDetail(detail, tr);

        Assert.Contains("Weightless", text);
        Assert.Contains("Marconi Union", text);
        Assert.Contains(tr.Tr("library_view.genres.no_album"), text);
    }

    [Fact]
    public void RenderGenreDetail_TrackWithAlbum_ShowsAlbumTitle()
    {
        var tr = new Translator("de");
        var detail = new LibraryGenreDetail(1, "Progressive Rock", new List<LibraryTrackListEntry>
        {
            new(1, 10, "Money", "Pink Floyd", "The Dark Side of the Moon", "Progressive Rock", 1973, 6, 382.0),
        });
        var text = LibraryBrowserSupport.RenderGenreDetail(detail, tr);

        Assert.Contains("The Dark Side of the Moon", text);
        Assert.DoesNotContain(tr.Tr("library_view.genres.no_album"), text);
    }

    // --- RenderPersonDetail -------------------------------------------------

    [Fact]
    public void RenderPersonDetail_WithoutRoles_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var detail = new LibraryPersonDetail(1, "Roger Waters", new List<LibraryPersonRoleEntry>());
        var text = LibraryBrowserSupport.RenderPersonDetail(detail, tr);

        Assert.Contains("Roger Waters", text);
        Assert.Contains(tr.Tr("library_view.persons.detail_roles_none"), text);
    }

    [Theory]
    [InlineData("artist", "library_view.persons.role_artist")]
    [InlineData("actor", "library_view.persons.role_actor")]
    [InlineData("director", "library_view.persons.role_director")]
    [InlineData("author", "library_view.persons.role_author")]
    [InlineData("narrator", "library_view.persons.role_narrator")]
    [InlineData("composer", "library_view.persons.role_composer")]
    [InlineData("publisher", "library_view.persons.role_publisher")]
    public void RenderPersonDetail_KnownRole_TranslatesRoleLabel(string role, string expectedKey)
    {
        var tr = new Translator("de");
        var detail = new LibraryPersonDetail(1, "Someone", new List<LibraryPersonRoleEntry>
        {
            new(role, "track", 1, "Some Track", 42),
        });
        var text = LibraryBrowserSupport.RenderPersonDetail(detail, tr);

        Assert.Contains(tr.Tr(expectedKey), text);
    }

    [Theory]
    [InlineData("movie", "library_view.persons.work_movie")]
    [InlineData("episode", "library_view.persons.work_episode")]
    [InlineData("audiobook", "library_view.persons.work_audiobook")]
    [InlineData("track", "library_view.persons.work_track")]
    public void RenderPersonDetail_KnownWorkKind_TranslatesWorkKindLabel(string workKind, string expectedKey)
    {
        var tr = new Translator("de");
        var detail = new LibraryPersonDetail(1, "Someone", new List<LibraryPersonRoleEntry>
        {
            new("artist", workKind, 1, "Some Work", 42),
        });
        var text = LibraryBrowserSupport.RenderPersonDetail(detail, tr);

        Assert.Contains(tr.Tr(expectedKey), text);
    }

    [Fact]
    public void RenderPersonDetail_UnknownRoleAndWorkKind_FallBackToNone()
    {
        // Defensive Behandlung unerwarteter/zukuenftiger Backend-Werte -
        // KEIN Absturz, sondern "library_view.value_none" als Platzhalter.
        var tr = new Translator("de");
        var detail = new LibraryPersonDetail(1, "Someone", new List<LibraryPersonRoleEntry>
        {
            new("unknown_role", "unknown_kind", 1, "Some Work", 42),
        });
        var text = LibraryBrowserSupport.RenderPersonDetail(detail, tr);

        Assert.Contains(tr.Tr("library_view.value_none"), text);
    }

    // --- RenderSourceDetail -------------------------------------------------

    [Fact]
    public void RenderSourceDetail_RendersAllFields()
    {
        var tr = new Translator("de");
        var row = new LibrarySourceEntry(
            1, 50, "song.mp3", "YouTube-Download", "youtube",
            "https://example.invalid/x", "abc123", "2026-01-01T00:00:00", "download");
        var text = LibraryBrowserSupport.RenderSourceDetail(row, tr);

        Assert.Contains("song.mp3", text);
        Assert.Contains("YouTube-Download", text);
        Assert.Contains("youtube", text);
        Assert.Contains("https://example.invalid/x", text);
        Assert.Contains("abc123", text);
        Assert.Contains("2026-01-01T00:00:00", text);
        Assert.Contains("download", text);
        Assert.Contains("50", text);
    }

    [Fact]
    public void RenderSourceDetail_MissingFields_ShowNoneFallback()
    {
        var tr = new Translator("de");
        var row = new LibrarySourceEntry(1, 50, null, null, null, null, null, null, null);
        var text = LibraryBrowserSupport.RenderSourceDetail(row, tr);

        Assert.Contains(tr.Tr("library_view.value_none"), text);
    }
}
