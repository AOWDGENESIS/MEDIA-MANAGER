using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - KI-Center (nav.ai_metadata, §25
/// Transparenz, §26, ADR-0017). Pendant zu
/// ui-reference-pyside/genesis_ui/views/ai_center_view.py: Status + lokale
/// semantische Suche. Pro-Datei-KI-Vorschlaege (§25) und KI-Musik-Angaben
/// (§27) bleiben bewusst im Medientabellen-Kontextmenue/-Werkzeugdialog
/// (noch nicht Teil dieses Schritts) - identische Architekturentscheidung
/// wie die Python-Referenz. Reindex ist additiv/unkritisch (kein confirm,
/// Prinzip #17 gilt fuer Metadaten-Uebernahmen, nicht fuer einen reinen
/// Suchindex).
/// </summary>
public partial class MainWindow
{
    private async Task ShowAiCenterAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("ai_center.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });

        var statusBanner = new TextBlock { TextWrapping = TextWrapping.Wrap, Text = _tr.Tr("ai_dialog.loading"), Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(statusBanner);

        var reindexRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var reindexBtn = new Button { Content = _tr.Tr("ai_center.reindex_button"), Margin = new Thickness(0, 0, 8, 0) };
        var reindexStatus = new TextBlock { VerticalAlignment = VerticalAlignment.Center };
        reindexRow.Children.Add(reindexBtn);
        reindexRow.Children.Add(reindexStatus);
        root.Children.Add(reindexRow);

        var searchRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var queryBox = new TextBox { Width = 400, Margin = new Thickness(0, 0, 8, 0) };
        queryBox.ToolTip = _tr.Tr("ai_center.query_placeholder");
        var searchBtn = new Button { Content = _tr.Tr("ai_center.search_button") };
        searchRow.Children.Add(queryBox);
        searchRow.Children.Add(searchBtn);
        root.Children.Add(searchRow);

        var searchStatus = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(searchStatus);

        // CanUserSortColumns=false: Parity zu ui-reference-pyside (keine
        // interaktive Spaltensortierung dort implementiert, §53).
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, MaxHeight = 400, CanUserSortColumns = false };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("ai_center.col_filename"), Binding = new System.Windows.Data.Binding(nameof(AiSearchResultEntry.Filename)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("ai_center.col_kind"), Binding = new System.Windows.Data.Binding("KindLabel"), Width = 140 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("ai_center.col_score"), Binding = new System.Windows.Data.Binding("ScoreText"), Width = 90 });
        root.Children.Add(grid);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        try
        {
            var status = await _api.GetAiStatusAsync();
            if (status is null || !status.Enabled)
            {
                statusBanner.Text = _tr.Tr("ai_dialog.status_disabled");
            }
            else if (!status.Available)
            {
                statusBanner.Text = _tr.Tr("ai_dialog.status_unavailable", ("provider", status.Provider));
            }
            else
            {
                statusBanner.Text = _tr.Tr("ai_dialog.status_active", ("provider", status.Provider), ("model", status.EmbeddingModel ?? "-"));
            }
        }
        catch (Exception ex)
        {
            statusBanner.Text = _tr.Tr("ai_dialog.status_load_failed", ("error", ex.Message));
        }

        reindexBtn.Click += async (_, _) =>
        {
            reindexStatus.Text = _tr.Tr("ai_center.reindexing");
            try
            {
                var stats = await _api.ReindexAiSearchAsync();
                reindexStatus.Text = _tr.Tr("ai_center.reindex_done", ("embedded", stats?.Embedded ?? 0), ("total", stats?.Total ?? 0));
            }
            catch (Exception ex)
            {
                reindexStatus.Text = _tr.Tr("ai_center.reindex_failed", ("error", ex.Message));
            }
        };

        async Task SearchAsync()
        {
            var query = queryBox.Text.Trim();
            if (query.Length == 0) return;
            grid.ItemsSource = null;
            AiSearchResponse? result;
            try
            {
                result = await _api.AiSemanticSearchAsync(query);
            }
            catch (Exception ex)
            {
                searchStatus.Text = _tr.Tr("ai_center.search_failed", ("error", ex.Message));
                return;
            }
            if (result is null || !result.Available)
            {
                searchStatus.Text = _tr.Tr("ai_center.search_unavailable");
                return;
            }
            if (result.Results.Count == 0)
            {
                searchStatus.Text = _tr.Tr("ai_center.no_results");
                return;
            }
            searchStatus.Text = _tr.Tr("ai_center.results_found", ("count", result.Results.Count));
            grid.ItemsSource = result.Results.Select(r => new
            {
                r.Filename,
                KindLabel = _tr.Tr(MediaTableSupport.MediaKindLabelKey(r.Kind)),
                // Invariantes "87%"-Format wie Pythons f"{score:.0%}"
                // (siehe AiCenterSupport.FormatScore; "{...:P0}" waere
                // systemkulturabhaengig, z.B. "87 %" unter de-DE).
                ScoreText = AiCenterSupport.FormatScore(r.Score),
            }).ToList();
        }

        searchBtn.Click += async (_, _) => await SearchAsync();
        queryBox.KeyDown += async (_, e) => { if (e.Key == System.Windows.Input.Key.Enter) await SearchAsync(); };
    }
}
