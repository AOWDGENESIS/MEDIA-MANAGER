using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Plugins (nav.plugins, §34).
/// Pendant zu ui-reference-pyside/genesis_ui/views/plugins_view.py. Zeigt
/// ALLE beim Start gefundenen Plugins - auch fehlgeschlagene, mit
/// Klartext-Fehlermeldung (§34/§37 "keine stillen Fehlschlaege"). "Neu
/// laden" ist unkritisch (liest nur erneut ein) - keine Bestaetigung noetig.
/// </summary>
public partial class MainWindow
{
    private async Task ShowPluginsAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("plugins_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("plugins_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var reloadBtn = new Button { Content = _tr.Tr("plugins_view.reload_button"), HorizontalAlignment = HorizontalAlignment.Left };
        root.Children.Add(reloadBtn);

        var dirText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap };
        root.Children.Add(dirText);
        root.Children.Add(statusText);

        // Parity zu ui-reference-pyside (keine interaktive Spaltensortierung
        // dort implementiert, §53).
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, Margin = new Thickness(0, 8, 0, 0), MaxHeight = 520, CanUserSortColumns = false };
        void Col(string headerKey, string path, double width = 120) =>
            grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr(headerKey), Binding = new System.Windows.Data.Binding(path), Width = width });
        Col("plugins_view.col_id", "PluginId");
        Col("plugins_view.col_kind", "PluginKind");
        // Python streckt die Namensspalte (setSectionResizeMode(2, Stretch));
        // die Statusspalte bekommt ZUSAETZLICH Star-Breite, damit die
        // Klartext-load_error-Meldungen (§34 "kaputte Plugins sichtbar
        // machen") nicht abgeschnitten werden.
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("plugins_view.col_name"), Binding = new System.Windows.Data.Binding("DisplayName"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        Col("plugins_view.col_version", "Version", 90);
        Col("plugins_view.col_author", "Author", 140);
        Col("plugins_view.col_license", "License", 110);
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("plugins_view.col_status"), Binding = new System.Windows.Data.Binding("StatusText"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        root.Children.Add(grid);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        void Render(PluginsResponse result)
        {
            dirText.Text = _tr.Tr("plugins_view.plugins_dir_label", ("path", result.PluginsDir));
            grid.ItemsSource = result.Plugins.Select(p => new
            {
                // OrFallback statt ?? - Python nutzt hier durchgaengig "or"
                // (plugin["author"] or "-"), d.h. auch der LEERSTRING wird
                // zu "-" (Paritaets-Idiom aus DownloadCenterSupport).
                PluginId = DownloadCenterSupport.OrFallback(p.PluginId, "-"),
                PluginKind = DownloadCenterSupport.OrFallback(p.PluginKind, "-"),
                DisplayName = DownloadCenterSupport.OrFallback(p.DisplayName, "-"),
                Version = DownloadCenterSupport.OrFallback(p.Version, "-"),
                Author = DownloadCenterSupport.OrFallback(p.Author, "-"),
                License = DownloadCenterSupport.OrFallback(p.License, "-"),
                StatusText = BuildStatusText(p),
            }).ToList();
            statusText.Text = result.Plugins.Count == 0 ? _tr.Tr("plugins_view.no_plugins") : string.Empty;
        }

        string BuildStatusText(PluginInfo p)
        {
            var text = _tr.Tr(p.LoadedSuccessfully ? "plugins_view.status_loaded" : "plugins_view.status_failed");
            if (!p.LoadedSuccessfully && !string.IsNullOrEmpty(p.LoadError)) text = $"{text}: {p.LoadError}";
            return text;
        }

        async Task ReloadAsync()
        {
            try
            {
                var result = await _api.ListPluginsAsync();
                if (result is not null) Render(result);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("plugins_view.load_failed", ("error", ex.Message));
            }
        }

        reloadBtn.Click += async (_, _) =>
        {
            try
            {
                var result = await _api.ReloadPluginsAsync();
                if (result is not null) Render(result);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("plugins_view.load_failed", ("error", ex.Message));
            }
        };

        await ReloadAsync();
    }
}
