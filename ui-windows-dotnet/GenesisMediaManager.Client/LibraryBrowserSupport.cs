// Reine Hilfslogik der Bibliotheks-Drill-down-Ansicht (MainWindow.xaml.cs ::
// ShowLibraryAsync), bewusst OHNE WPF-Abhaengigkeit ausgelagert (gleiches
// Muster wie MediaTableSupport.cs) - Pendant zu
// ui-reference-pyside/genesis_ui/views/library_view.py (§9/§62,
// Gap-Analyse B). EINE gemeinsame View/Hilfsklasse fuer alle sechs Kinds
// (artists/albums/titles/genres/persons/sources) statt sechs fast
// identischer Kopien - identische Architekturentscheidung wie die
// Python-Referenz.
using GenesisMediaManager.Client.Api;
using GenesisMediaManager.Client.I18n;

namespace GenesisMediaManager.Client;

public static class LibraryBrowserSupport
{
    /// <summary>Entspricht den ("nav.xxx", "library", "&lt;kind&gt;")-Eintraegen
    /// in ui-reference-pyside/genesis_ui/main_window.py::NAV_STRUCTURE.</summary>
    public static readonly IReadOnlyDictionary<string, string> LibraryKindByNavKey = new Dictionary<string, string>
    {
        ["nav.artists"] = "artists",
        ["nav.albums"] = "albums",
        ["nav.titles"] = "titles",
        ["nav.genres"] = "genres",
        ["nav.persons"] = "persons",
        ["nav.sources"] = "sources",
    };

    private static readonly IReadOnlyDictionary<string, string> RoleKeys = new Dictionary<string, string>
    {
        ["artist"] = "library_view.persons.role_artist",
        ["actor"] = "library_view.persons.role_actor",
        ["director"] = "library_view.persons.role_director",
        ["author"] = "library_view.persons.role_author",
        ["narrator"] = "library_view.persons.role_narrator",
        ["composer"] = "library_view.persons.role_composer",
        ["publisher"] = "library_view.persons.role_publisher",
    };

    private static readonly IReadOnlyDictionary<string, string> WorkKindKeys = new Dictionary<string, string>
    {
        ["movie"] = "library_view.persons.work_movie",
        ["episode"] = "library_view.persons.work_episode",
        ["audiobook"] = "library_view.persons.work_audiobook",
        ["track"] = "library_view.persons.work_track",
    };

    public static string Fmt(object? value, Translator tr) =>
        value is null || (value is string s && s.Length == 0) ? tr.Tr("library_view.value_none") : value.ToString()!;

    public static string FmtDuration(double? seconds, Translator tr)
    {
        if (seconds is null) return tr.Tr("library_view.value_none");
        var total = (int)Math.Round(seconds.Value);
        var minutes = total / 60;
        var secs = total % 60;
        return $"{minutes}:{secs:D2}";
    }

    public static string RenderArtistDetail(LibraryArtistDetail detail, Translator tr)
    {
        var lines = new List<string>
        {
            tr.Tr("library_view.artists.detail_name", ("value", Fmt(detail.Name, tr))),
            tr.Tr("library_view.artists.detail_sort_name", ("value", Fmt(detail.SortName, tr))),
            tr.Tr("library_view.artists.detail_musicbrainz_id", ("value", Fmt(detail.MusicbrainzId, tr))),
            string.Empty,
            tr.Tr("library_view.artists.detail_albums_header", ("count", detail.Albums.Count)),
        };
        if (detail.Albums.Count == 0)
        {
            lines.Add(tr.Tr("library_view.artists.detail_albums_none"));
        }
        foreach (var album in detail.Albums)
        {
            lines.Add(tr.Tr(
                "library_view.artists.detail_album_entry",
                ("title", Fmt(album.Title, tr)), ("year", Fmt(album.Year, tr)), ("count", album.TrackCount)));
        }
        return string.Join(Environment.NewLine, lines);
    }

    public static string RenderAlbumDetail(LibraryAlbumDetail detail, Translator tr)
    {
        var lines = new List<string>
        {
            tr.Tr("library_view.albums.detail_title", ("value", Fmt(detail.Title, tr))),
            tr.Tr("library_view.albums.detail_artist", ("value", Fmt(detail.ArtistName, tr))),
            tr.Tr("library_view.albums.detail_year", ("value", Fmt(detail.Year, tr))),
            tr.Tr("library_view.albums.detail_musicbrainz_id", ("value", Fmt(detail.MusicbrainzId, tr))),
            string.Empty,
            tr.Tr("library_view.albums.detail_tracks_header", ("count", detail.Tracks.Count)),
        };
        if (detail.Tracks.Count == 0)
        {
            lines.Add(tr.Tr("library_view.albums.detail_tracks_none"));
        }
        foreach (var t in detail.Tracks)
        {
            var disc = t.DiscNumber ?? 1;
            var number = t.TrackNumber is null ? "?" : t.TrackNumber.ToString();
            lines.Add(tr.Tr(
                "library_view.albums.detail_track_entry",
                ("position", $"{disc}.{number}"), ("title", Fmt(t.Title, tr)),
                ("duration", FmtDuration(t.DurationSeconds, tr))));
        }
        return string.Join(Environment.NewLine, lines);
    }

    public static string RenderTitleDetail(LibraryTrackListEntry row, Translator tr) => string.Join(
        Environment.NewLine,
        new[]
        {
            tr.Tr("library_view.titles.detail_title", ("value", Fmt(row.Title, tr))),
            tr.Tr("library_view.titles.detail_artist", ("value", Fmt(row.ArtistName, tr))),
            tr.Tr("library_view.titles.detail_album", ("value", Fmt(row.AlbumTitle, tr))),
            tr.Tr("library_view.titles.detail_genre", ("value", Fmt(row.GenreName, tr))),
            tr.Tr("library_view.titles.detail_year", ("value", Fmt(row.Year, tr))),
            tr.Tr("library_view.titles.detail_track_number", ("value", Fmt(row.TrackNumber, tr))),
            tr.Tr("library_view.titles.detail_duration", ("value", FmtDuration(row.DurationSeconds, tr))),
            tr.Tr("library_view.titles.detail_media_file_id", ("value", Fmt(row.MediaFileId, tr))),
        });

    public static string RenderGenreDetail(LibraryGenreDetail detail, Translator tr)
    {
        var lines = new List<string>
        {
            tr.Tr("library_view.genres.detail_name", ("value", Fmt(detail.Name, tr))),
            string.Empty,
            tr.Tr("library_view.genres.detail_tracks_header", ("count", detail.Tracks.Count)),
        };
        if (detail.Tracks.Count == 0)
        {
            lines.Add(tr.Tr("library_view.genres.detail_tracks_none"));
        }
        foreach (var t in detail.Tracks)
        {
            var album = string.IsNullOrEmpty(t.AlbumTitle) ? tr.Tr("library_view.genres.no_album") : t.AlbumTitle;
            lines.Add(tr.Tr(
                "library_view.genres.detail_track_entry",
                ("title", Fmt(t.Title, tr)), ("artist", Fmt(t.ArtistName, tr)), ("album", album!)));
        }
        return string.Join(Environment.NewLine, lines);
    }

    public static string RenderPersonDetail(LibraryPersonDetail detail, Translator tr)
    {
        var lines = new List<string>
        {
            tr.Tr("library_view.persons.detail_name", ("value", Fmt(detail.Name, tr))),
            string.Empty,
            tr.Tr("library_view.persons.detail_roles_header", ("count", detail.Roles.Count)),
        };
        if (detail.Roles.Count == 0)
        {
            lines.Add(tr.Tr("library_view.persons.detail_roles_none"));
        }
        foreach (var r in detail.Roles)
        {
            var roleLabel = tr.Tr(RoleKeys.TryGetValue(r.Role, out var rk) ? rk : "library_view.value_none");
            var workLabel = tr.Tr(WorkKindKeys.TryGetValue(r.WorkKind, out var wk) ? wk : "library_view.value_none");
            lines.Add(tr.Tr(
                "library_view.persons.detail_role_entry",
                ("role", roleLabel), ("work_kind", workLabel), ("title", Fmt(r.WorkTitle, tr))));
        }
        return string.Join(Environment.NewLine, lines);
    }

    public static string RenderSourceDetail(LibrarySourceEntry row, Translator tr) => string.Join(
        Environment.NewLine,
        new[]
        {
            tr.Tr("library_view.sources.detail_filename", ("value", Fmt(row.Filename, tr))),
            tr.Tr("library_view.sources.detail_source_name", ("value", Fmt(row.SourceName, tr))),
            tr.Tr("library_view.sources.detail_provider", ("value", Fmt(row.ProviderName, tr))),
            tr.Tr("library_view.sources.detail_url", ("value", Fmt(row.OriginalUrl, tr))),
            tr.Tr("library_view.sources.detail_original_id", ("value", Fmt(row.OriginalId, tr))),
            tr.Tr("library_view.sources.detail_imported_at", ("value", Fmt(row.ImportedAt, tr))),
            tr.Tr("library_view.sources.detail_import_method", ("value", Fmt(row.ImportMethod, tr))),
            tr.Tr("library_view.sources.detail_media_file_id", ("value", Fmt(row.MediaFileId, tr))),
        });
}
