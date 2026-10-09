using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Log-Viewer (nav.logs, §54,
/// Gap-Analyse Gap J). Pendant zu
/// ui-reference-pyside/genesis_ui/views/log_viewer_view.py. Rein lesender
/// Zugriff (Prinzip #4/#5) - es gibt keine Moeglichkeit, Logeintraege ueber
/// die GUI zu loeschen oder zu veraendern.
/// </summary>
public partial class MainWindow
{
    private static readonly string[] LogLevelChoices = { "", "TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL" };
    private static readonly string[] FirstLineSeparators = { "\r\n", "\n", "\r" };
    private const int LogPageSize = 200;

    private async Task ShowLogViewerAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("log_viewer_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("log_viewer_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var controls = new StackPanel { Orientation = Orientation.Horizontal };
        controls.Children.Add(new TextBlock { Text = _tr.Tr("log_viewer_view.level_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 4, 0) });
        var levelCombo = new ComboBox { Width = 110, Margin = new Thickness(0, 0, 8, 0) };
        foreach (var value in LogLevelChoices)
        {
            levelCombo.Items.Add(new ComboBoxItem { Content = value == "" ? _tr.Tr("log_viewer_view.level_any") : value, Tag = value });
        }
        levelCombo.SelectedIndex = 0;
        var componentBox = new TextBox { Width = 160, Margin = new Thickness(0, 0, 8, 0) };
        componentBox.ToolTip = _tr.Tr("log_viewer_view.component_placeholder");
        var searchBox = new TextBox { Width = 200, Margin = new Thickness(0, 0, 8, 0) };
        searchBox.ToolTip = _tr.Tr("log_viewer_view.search_placeholder");
        var refreshBtn = new Button { Content = _tr.Tr("log_viewer_view.refresh_button") };
        controls.Children.Add(levelCombo);
        controls.Children.Add(componentBox);
        controls.Children.Add(searchBox);
        controls.Children.Add(refreshBtn);
        root.Children.Add(controls);

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        root.Children.Add(statusText);

        // CanUserSortColumns=false ist PFLICHT: die Detailanzeige indiziert
        // unten per grid.SelectedIndex in "currentItems" - sonst koennte bei
        // aktiver Spaltensortierung der FALSCHE Log-Eintrag im Detailbereich
        // angezeigt werden. Gefunden im Deep-Search, behoben.
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, Margin = new Thickness(0, 8, 0, 0), MaxHeight = 380, CanUserSortColumns = false };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("log_viewer_view.col_timestamp"), Binding = new System.Windows.Data.Binding(nameof(LogEntryInfo.Timestamp)), Width = 170 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("log_viewer_view.col_level"), Binding = new System.Windows.Data.Binding(nameof(LogEntryInfo.Level)), Width = 90 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("log_viewer_view.col_component"), Binding = new System.Windows.Data.Binding(nameof(LogEntryInfo.Component)), Width = 160 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("log_viewer_view.col_message"), Binding = new System.Windows.Data.Binding("FirstLine"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        root.Children.Add(grid);

        var detailBox = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, Margin = new Thickness(0, 8, 0, 0), MinHeight = 100 };
        root.Children.Add(detailBox);

        var pagination = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
        var prevBtn = new Button { Content = _tr.Tr("log_viewer_view.previous_page_button"), Margin = new Thickness(0, 0, 8, 0) };
        var nextBtn = new Button { Content = _tr.Tr("log_viewer_view.next_page_button") };
        pagination.Children.Add(prevBtn);
        pagination.Children.Add(nextBtn);
        root.Children.Add(pagination);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        var offset = 0;
        var total = 0;
        List<LogEntryInfo> currentItems = new();

        async Task FetchAndRenderAsync()
        {
            var level = (levelCombo.SelectedItem as ComboBoxItem)?.Tag as string;
            try
            {
                var data = await _api.GetLogsAsync(
                    string.IsNullOrEmpty(level) ? null : level,
                    string.IsNullOrWhiteSpace(componentBox.Text) ? null : componentBox.Text.Trim(),
                    string.IsNullOrWhiteSpace(searchBox.Text) ? null : searchBox.Text.Trim(),
                    LogPageSize, offset);
                total = data?.Total ?? 0;
                currentItems = data?.Items ?? new List<LogEntryInfo>();
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("log_viewer_view.error_api", ("error", ex.Message));
                return;
            }

            grid.ItemsSource = currentItems.Select(e => new
            {
                e.Timestamp, e.Level, Component = e.Component.Trim(),
                // Python nutzt splitlines()[0] - trennt an \n, \r\n UND \r.
                // Ein reines Split('\n') liesse \r-Reste stehen und wuerde
                // bei \r-Zeilenumbruechen die ganze Meldung zeigen.
                FirstLine = string.IsNullOrEmpty(e.Message)
                    ? string.Empty
                    : e.Message.Split(FirstLineSeparators, StringSplitOptions.None)[0],
            }).ToList();

            var shownFrom = currentItems.Count > 0 ? offset + 1 : 0;
            var shownTo = offset + currentItems.Count;
            statusText.Text = _tr.Tr(
                "log_viewer_view.status_summary", ("shown_from", shownFrom), ("shown_to", shownTo), ("total", total));
            prevBtn.IsEnabled = offset > 0;
            nextBtn.IsEnabled = offset + LogPageSize < total;
            detailBox.Text = string.Empty;
        }

        async Task ReloadAsync()
        {
            offset = 0;
            await FetchAndRenderAsync();
        }

        levelCombo.SelectionChanged += async (_, _) => await ReloadAsync();
        componentBox.KeyDown += async (_, e) => { if (e.Key == System.Windows.Input.Key.Enter) await ReloadAsync(); };
        searchBox.KeyDown += async (_, e) => { if (e.Key == System.Windows.Input.Key.Enter) await ReloadAsync(); };
        refreshBtn.Click += async (_, _) => await ReloadAsync();
        prevBtn.Click += async (_, _) => { offset = Math.Max(0, offset - LogPageSize); await FetchAndRenderAsync(); };
        nextBtn.Click += async (_, _) =>
        {
            if (offset + LogPageSize < total) { offset += LogPageSize; await FetchAndRenderAsync(); }
        };
        grid.SelectionChanged += (_, _) =>
        {
            if (grid.SelectedIndex >= 0 && grid.SelectedIndex < currentItems.Count)
            {
                detailBox.Text = currentItems[grid.SelectedIndex].Message;
            }
            else
            {
                detailBox.Text = string.Empty;
            }
        };

        await ReloadAsync();
    }
}
