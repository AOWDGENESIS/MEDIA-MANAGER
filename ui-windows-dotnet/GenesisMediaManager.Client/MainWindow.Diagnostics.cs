using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Diagnose (nav.diagnostics, §38).
/// Pendant zu ui-reference-pyside/genesis_ui/views/diagnostics_view.py.
/// Rein lesender Gesundheitsbericht - veraendert NIE etwas; eine
/// tatsaechliche Reparatur geschieht ausschliesslich ueber den separaten
/// "Scan &amp; Repair"-Arbeitsablauf (§39), nicht von hier aus.
/// </summary>
public partial class MainWindow
{
    private static readonly IReadOnlyDictionary<string, string> DiagnosticsStatusKeys = new Dictionary<string, string>
    {
        ["ok"] = "diagnostics_view.status_ok",
        ["warning"] = "diagnostics_view.status_warning",
        ["error"] = "diagnostics_view.status_error",
    };

    private async Task ShowDiagnosticsAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("diagnostics_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("diagnostics_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var runBtn = new Button { Content = _tr.Tr("diagnostics_view.run_button"), HorizontalAlignment = HorizontalAlignment.Left };
        root.Children.Add(runBtn);

        var overallText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap };
        root.Children.Add(overallText);
        root.Children.Add(statusText);

        var grid = new DataGrid
        {
            AutoGenerateColumns = false, IsReadOnly = true, Margin = new Thickness(0, 8, 0, 0),
            MaxHeight = 520,
            // Parity zu ui-reference-pyside (keine interaktive Spalten-
            // sortierung dort implementiert, §53).
            CanUserSortColumns = false,
        };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("diagnostics_view.col_check"), Binding = new System.Windows.Data.Binding(nameof(DiagnosticCheckInfo.Label)), Width = 220 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("diagnostics_view.col_status"), Binding = new System.Windows.Data.Binding("StatusLabel"), Width = 100 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("diagnostics_view.col_message"), Binding = new System.Windows.Data.Binding(nameof(DiagnosticCheckInfo.Message)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        root.Children.Add(grid);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        async Task ReloadAsync()
        {
            runBtn.IsEnabled = false;
            statusText.Text = _tr.Tr("diagnostics_view.running");
            try
            {
                var report = await _api.RunDiagnosticsAsync();
                runBtn.IsEnabled = true;
                statusText.Text = string.Empty;
                if (report is null) return;
                var overallKey = DiagnosticsStatusKeys.TryGetValue(report.OverallStatus, out var k) ? k : report.OverallStatus;
                overallText.Text = _tr.Tr(
                    "diagnostics_view.overall_status", ("status", _tr.Tr(overallKey)), ("generated_at", report.GeneratedAt));
                grid.ItemsSource = report.Checks.Select(c => new
                {
                    c.Label,
                    c.Message,
                    StatusLabel = _tr.Tr(DiagnosticsStatusKeys.TryGetValue(c.Status, out var sk) ? sk : c.Status),
                }).ToList();
            }
            catch (Exception ex)
            {
                runBtn.IsEnabled = true;
                statusText.Text = string.Empty;
                overallText.Text = _tr.Tr("dashboard.error", ("error", ex.Message));
            }
        }

        runBtn.Click += async (_, _) => await ReloadAsync();
        await ReloadAsync();
    }
}
