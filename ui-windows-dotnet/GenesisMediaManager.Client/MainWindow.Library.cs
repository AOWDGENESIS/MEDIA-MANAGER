using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Bibliotheks-Drill-down
/// (nav.artists/albums/titles/genres/persons/sources), Pendant zu
/// ui-reference-pyside/genesis_ui/views/library_view.py::LibraryBrowserView
/// (§9/§62, Gap-Analyse B). Siehe LibraryBrowserSupport.cs fuer die
/// WPF-freie Render-/Formatierungslogik. EINE gemeinsame, parametrisierte
/// Methode (statt sechs fast identischer Kopien) - identische
/// Architekturentscheidung wie die Python-Referenz.
/// </summary>
public partial class MainWindow
{
    private async Task ShowLibraryAsync(string kind, string navItemKey)
    {
        var header = new TextBlock
        {
            Text = _tr.Tr(navItemKey), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 12),
        };

        var searchRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        // Platzhaltertext der Python-Referenz (setPlaceholderText) - als
        // ToolTip, da WPF-TextBoxen kein natives Placeholder-Feature haben
        // (dieselbe Konvention wie in der Suchzeile der Medientabelle).
        var searchBox = new TextBox { Width = 320, Margin = new Thickness(0, 0, 8, 0), ToolTip = _tr.Tr("library_view.search_placeholder") };
        var searchBtn = new Button { Content = _tr.Tr("library_view.search_button"), Margin = new Thickness(0, 0, 8, 0) };
        var refreshBtn = new Button { Content = _tr.Tr("library_view.refresh_button") };
        searchRow.Children.Add(searchBox);
        searchRow.Children.Add(searchBtn);
        searchRow.Children.Add(refreshBtn);

        var splitGrid = new Grid();
        splitGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        splitGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 6) };
        var listView = BuildLibraryListView(kind);
        Grid.SetColumn(listView, 0);
        listView.Margin = new Thickness(0, 0, 8, 0);

        var detailBox = new TextBox
        {
            IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            Text = _tr.Tr("library_view.detail_placeholder"),
        };
        Grid.SetColumn(detailBox, 1);

        splitGrid.Children.Add(listView);
        splitGrid.Children.Add(detailBox);

        var wrapper = new StackPanel();
        wrapper.Children.Add(header);
        wrapper.Children.Add(searchRow);
        wrapper.Children.Add(statusText);
        var contentGrid = new Grid { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        contentGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        contentGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        Grid.SetRow(wrapper, 0);
        Grid.SetRow(splitGrid, 1);
        contentGrid.Children.Add(wrapper);
        contentGrid.Children.Add(splitGrid);

        MainContent.Content = contentGrid;

        var rowsById = new Dictionary<int, object>();

        async Task ReloadAsync()
        {
            listView.Items.Clear();
            rowsById.Clear();
            detailBox.Text = _tr.Tr("library_view.detail_placeholder");
            var search = string.IsNullOrWhiteSpace(searchBox.Text) ? null : searchBox.Text.Trim();
            try
            {
                var rows = await LoadLibraryRowsAsync(kind, search);
                foreach (var (id, row) in rows)
                {
                    rowsById[id] = row;
                    listView.Items.Add(row);
                }
                statusText.Text = rows.Count == 0 ? _tr.Tr("library_view.no_items") : string.Empty;
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("library_view.load_failed", ("error", ex.Message));
            }
        }

        searchBtn.Click += async (_, _) => await ReloadAsync();
        refreshBtn.Click += async (_, _) => await ReloadAsync();
        searchBox.KeyDown += async (_, e) =>
        {
            if (e.Key == System.Windows.Input.Key.Enter) await ReloadAsync();
        };
        listView.SelectionChanged += async (_, _) =>
        {
            var id = GetRowId(kind, listView.SelectedItem);
            if (id is null || !rowsById.TryGetValue(id.Value, out var row))
            {
                detailBox.Text = _tr.Tr("library_view.detail_placeholder");
                return;
            }
            try
            {
                detailBox.Text = await RenderLibraryDetailAsync(kind, id.Value, row);
            }
            catch (Exception ex)
            {
                // Paritaet zur Python-Referenz: ZUSATZLICH zur Statusanzeige
                // im Detailbereich den zentralen Fehlerdialog zeigen (Gap L,
                // §37 - library_view.py setzt beides).
                detailBox.Text = _tr.Tr("library_view.detail_load_failed", ("error", ex.Message));
                ShowApiError(ex);
            }
        };

        await ReloadAsync();
    }

    private static int? GetRowId(string kind, object? row) => row switch
    {
        LibraryArtistSummary a => a.Id,
        LibraryAlbumSummary a => a.Id,
        LibraryTrackListEntry a => a.Id,
        LibraryGenreSummary a => a.Id,
        LibraryPersonSummary a => a.Id,
        LibrarySourceEntry a => a.Id,
        _ => null,
    };

    private async Task<string> RenderLibraryDetailAsync(string kind, int id, object row) => kind switch
    {
        "artists" => LibraryBrowserSupport.RenderArtistDetail(
            await _api.GetLibraryArtistDetailAsync(id) ?? throw new InvalidOperationException("404"), _tr),
        "albums" => LibraryBrowserSupport.RenderAlbumDetail(
            await _api.GetLibraryAlbumDetailAsync(id) ?? throw new InvalidOperationException("404"), _tr),
        "genres" => LibraryBrowserSupport.RenderGenreDetail(
            await _api.GetLibraryGenreDetailAsync(id) ?? throw new InvalidOperationException("404"), _tr),
        "persons" => LibraryBrowserSupport.RenderPersonDetail(
            await _api.GetLibraryPersonDetailAsync(id) ?? throw new InvalidOperationException("404"), _tr),
        "titles" => LibraryBrowserSupport.RenderTitleDetail((LibraryTrackListEntry)row, _tr),
        "sources" => LibraryBrowserSupport.RenderSourceDetail((LibrarySourceEntry)row, _tr),
        _ => string.Empty,
    };

    private async Task<List<(int Id, object Row)>> LoadLibraryRowsAsync(string kind, string? search)
    {
        var result = new List<(int, object)>();
        switch (kind)
        {
            case "artists":
                foreach (var a in await _api.ListLibraryArtistsAsync(search)) result.Add((a.Id, a));
                break;
            case "albums":
                foreach (var a in await _api.ListLibraryAlbumsAsync(search)) result.Add((a.Id, a));
                break;
            case "titles":
                var tracks = await _api.ListLibraryTracksAsync(search);
                foreach (var t in tracks?.Items ?? new List<LibraryTrackListEntry>()) result.Add((t.Id, t));
                break;
            case "genres":
                foreach (var g in await _api.ListLibraryGenresAsync(search)) result.Add((g.Id, g));
                break;
            case "persons":
                foreach (var p in await _api.ListLibraryPersonsAsync(search)) result.Add((p.Id, p));
                break;
            case "sources":
                var sources = await _api.ListLibrarySourcesAsync(search);
                foreach (var s in sources?.Items ?? new List<LibrarySourceEntry>()) result.Add((s.Id, s));
                break;
        }
        return result;
    }

    private ListView BuildLibraryListView(string kind)
    {
        var view = new GridView();
        var nullConverter = new LibraryNullValueConverter(_tr);
        void AddCol(string headerKey, string bindingPath) =>
            view.Columns.Add(new GridViewColumn
            {
                Header = _tr.Tr(headerKey),
                // Paritaet zu _render_cell() in library_view.py: Null-Werte
                // werden als lokalisierter Leerwert ("-") angezeigt statt
                // als leere Stelle.
                DisplayMemberBinding = new System.Windows.Data.Binding(bindingPath) { Converter = nullConverter },
                Width = 150,
            });

        switch (kind)
        {
            case "artists":
                AddCol("library_view.artists.col_name", nameof(LibraryArtistSummary.Name));
                AddCol("library_view.artists.col_sort_name", nameof(LibraryArtistSummary.SortName));
                AddCol("library_view.artists.col_albums", nameof(LibraryArtistSummary.AlbumCount));
                AddCol("library_view.artists.col_tracks", nameof(LibraryArtistSummary.TrackCount));
                break;
            case "albums":
                AddCol("library_view.albums.col_title", nameof(LibraryAlbumSummary.Title));
                AddCol("library_view.albums.col_artist", nameof(LibraryAlbumSummary.ArtistName));
                AddCol("library_view.albums.col_year", nameof(LibraryAlbumSummary.Year));
                AddCol("library_view.albums.col_tracks", nameof(LibraryAlbumSummary.TrackCount));
                break;
            case "titles":
                AddCol("library_view.titles.col_title", nameof(LibraryTrackListEntry.Title));
                AddCol("library_view.titles.col_artist", nameof(LibraryTrackListEntry.ArtistName));
                AddCol("library_view.titles.col_album", nameof(LibraryTrackListEntry.AlbumTitle));
                AddCol("library_view.titles.col_genre", nameof(LibraryTrackListEntry.GenreName));
                AddCol("library_view.titles.col_year", nameof(LibraryTrackListEntry.Year));
                break;
            case "genres":
                AddCol("library_view.genres.col_name", nameof(LibraryGenreSummary.Name));
                AddCol("library_view.genres.col_tracks", nameof(LibraryGenreSummary.TrackCount));
                break;
            case "persons":
                AddCol("library_view.persons.col_name", nameof(LibraryPersonSummary.Name));
                AddCol("library_view.persons.col_roles", nameof(LibraryPersonSummary.RoleCount));
                break;
            case "sources":
                AddCol("library_view.sources.col_filename", nameof(LibrarySourceEntry.Filename));
                AddCol("library_view.sources.col_source_name", nameof(LibrarySourceEntry.SourceName));
                AddCol("library_view.sources.col_provider", nameof(LibrarySourceEntry.ProviderName));
                AddCol("library_view.sources.col_imported_at", nameof(LibrarySourceEntry.ImportedAt));
                break;
        }
        return new ListView { View = view };
    }
}

/// <summary>
/// Paritaet zu <c>_render_cell()</c> in
/// <c>ui-reference-pyside/genesis_ui/views/library_view.py</c>: Null-Werte
/// in Tabellenzellen werden als lokalisierter Leerwert
/// (<c>library_view.value_none</c>, "-") angezeigt statt als leere Stelle.
/// WICHTIG: Wie in der Python-Referenz wird hier NUR <c>null</c> ersetzt -
/// ein leerer String wird (anders als im Detailbereich, <c>_fmt()</c>)
/// unveraendert angezeigt.
/// </summary>
internal sealed class LibraryNullValueConverter : System.Windows.Data.IValueConverter
{
    private readonly GenesisMediaManager.Client.I18n.Translator _tr;

    public LibraryNullValueConverter(GenesisMediaManager.Client.I18n.Translator tr) => _tr = tr;

    public object Convert(object? value, Type targetType, object? parameter, System.Globalization.CultureInfo culture) =>
        value is null ? _tr.Tr("library_view.value_none") : value;

    public object ConvertBack(object? value, Type targetType, object? parameter, System.Globalization.CultureInfo culture) =>
        System.Windows.Data.Binding.DoNothing;
}
