using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Fehler-Center (nav.error_center,
/// §37). Pendant zu ui-reference-pyside/genesis_ui/views/error_center_view.py.
/// "Geloest" markieren ist rein organisatorisch (wie bei Duplikat-Gruppen) -
/// veraendert nie Dateien/Fachdaten, nur den Eintrag selbst.
/// </summary>
public partial class MainWindow
{
    private async Task ShowErrorCenterAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("error_center_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("error_center_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var controls = new StackPanel { Orientation = Orientation.Horizontal };
        var unresolvedOnly = new CheckBox { Content = _tr.Tr("error_center_view.unresolved_only_checkbox"), IsChecked = true, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 12, 0) };
        var refreshBtn = new Button { Content = _tr.Tr("error_center_view.refresh_button") };
        controls.Children.Add(unresolvedOnly);
        controls.Children.Add(refreshBtn);
        root.Children.Add(controls);

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        root.Children.Add(statusText);

        // CanUserSortColumns=false ist PFLICHT: resolve-Button indiziert
        // unten per grid.SelectedIndex in "errors" - sonst koennte bei
        // aktiver Spaltensortierung der FALSCHE Fehler als erledigt
        // markiert werden. Gefunden im Deep-Search, behoben.
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, Margin = new Thickness(0, 8, 0, 0), MaxHeight = 320, CanUserSortColumns = false };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("error_center_view.col_error_id"), Binding = new System.Windows.Data.Binding(nameof(ErrorLogEntry.ErrorId)), Width = 220 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("error_center_view.col_timestamp"), Binding = new System.Windows.Data.Binding(nameof(ErrorLogEntry.Timestamp)), Width = 160 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("error_center_view.col_component"), Binding = new System.Windows.Data.Binding(nameof(ErrorLogEntry.Component)), Width = 140 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("error_center_view.col_message"), Binding = new System.Windows.Data.Binding(nameof(ErrorLogEntry.Message)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("error_center_view.col_resolved"), Binding = new System.Windows.Data.Binding("ResolvedText"), Width = 90 });
        root.Children.Add(grid);

        var detailBox = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, Margin = new Thickness(0, 8, 0, 0), MinHeight = 80 };
        root.Children.Add(detailBox);

        var resolveBtn = new Button { Content = _tr.Tr("error_center_view.resolve_button"), IsEnabled = false, Margin = new Thickness(0, 8, 0, 0), HorizontalAlignment = HorizontalAlignment.Left };
        root.Children.Add(resolveBtn);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        List<ErrorLogEntry> errors = new();

        void UpdateDetail()
        {
            if (grid.SelectedIndex < 0 || grid.SelectedIndex >= errors.Count)
            {
                detailBox.Text = string.Empty;
                resolveBtn.IsEnabled = false;
                return;
            }
            var error = errors[grid.SelectedIndex];
            var lines = new List<string>
            {
                _tr.Tr("error_center_view.detail_solution", ("hint", error.SolutionHint ?? "-")),
                _tr.Tr("error_center_view.detail_technical", ("details", error.TechnicalDetails ?? "-")),
            };
            if (!string.IsNullOrEmpty(error.FilePath))
            {
                lines.Add(_tr.Tr("error_center_view.detail_file_path", ("path", error.FilePath)));
            }
            detailBox.Text = string.Join(Environment.NewLine, lines);
            resolveBtn.IsEnabled = !error.Resolved;
        }

        async Task ReloadAsync()
        {
            try
            {
                errors = await _api.ListErrorsAsync(200, unresolvedOnly.IsChecked == true);
                grid.ItemsSource = errors.Select(e => new
                {
                    e.ErrorId, Timestamp = e.Timestamp ?? "-", Component = e.Component ?? "-", e.Message,
                    ResolvedText = _tr.Tr(e.Resolved ? "error_center_view.status_resolved" : "error_center_view.status_open"),
                }).ToList();
                statusText.Text = errors.Count == 0 ? _tr.Tr("error_center_view.no_errors") : string.Empty;
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("error_center_view.load_failed", ("error", ex.Message));
            }
            detailBox.Text = string.Empty;
            resolveBtn.IsEnabled = false;
        }

        grid.SelectionChanged += (_, _) => UpdateDetail();
        unresolvedOnly.Checked += async (_, _) => await ReloadAsync();
        unresolvedOnly.Unchecked += async (_, _) => await ReloadAsync();
        refreshBtn.Click += async (_, _) => await ReloadAsync();
        resolveBtn.Click += async (_, _) =>
        {
            if (grid.SelectedIndex < 0 || grid.SelectedIndex >= errors.Count) return;
            try
            {
                await _api.ResolveErrorAsync(errors[grid.SelectedIndex].ErrorId);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("dashboard.error", ("error", ex.Message));
            }
            await ReloadAsync();
        };

        await ReloadAsync();
    }
}
