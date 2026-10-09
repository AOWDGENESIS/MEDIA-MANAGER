using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Backups (nav.backups, §40).
/// Pendant zu ui-reference-pyside/genesis_ui/views/backups_view.py. Betrifft
/// AUSSCHLIESSLICH DB/Konfiguration, NIEMALS Mediendateien (§6/§40).
/// Erstellen ist unkritisch; Wiederherstellen ersetzt die AKTIVE Datenbank
/// und erfordert daher eine explizite Bestaetigung (Prinzip #6, §44).
/// </summary>
public partial class MainWindow
{
    private async Task ShowBackupsAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("backups_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("backups_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var buttonRow = new StackPanel { Orientation = Orientation.Horizontal };
        var createDbBtn = new Button { Content = _tr.Tr("backups_view.create_db_button"), Margin = new Thickness(0, 0, 8, 0) };
        var createConfigBtn = new Button { Content = _tr.Tr("backups_view.create_config_button"), Margin = new Thickness(0, 0, 8, 0) };
        var refreshBtn = new Button { Content = _tr.Tr("backups_view.refresh_button") };
        buttonRow.Children.Add(createDbBtn);
        buttonRow.Children.Add(createConfigBtn);
        buttonRow.Children.Add(refreshBtn);
        root.Children.Add(buttonRow);

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        root.Children.Add(statusText);

        var grid = new DataGrid
        {
            AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single,
            Margin = new Thickness(0, 8, 0, 0), MaxHeight = 420,
            // CanUserSortColumns=false ist PFLICHT: restoreBtn.Click indiziert
            // unten per grid.SelectedIndex in die Liste "backups" - bei
            // aktivierter Spaltensortierung (WPF-Default: true) würde die
            // Anzeigereihenfolge vom Index der Liste abweichen und ein
            // FALSCHES Backup wiederhergestellt werden (§6/§40 - betrifft
            // die aktive Datenbank!). Gefunden im Deep-Search, behoben.
            CanUserSortColumns = false,
        };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("backups_view.col_id"), Binding = new System.Windows.Data.Binding(nameof(BackupEntry.Id)), Width = 60 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("backups_view.col_type"), Binding = new System.Windows.Data.Binding(nameof(BackupEntry.BackupType)), Width = 100 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("backups_view.col_created"), Binding = new System.Windows.Data.Binding(nameof(BackupEntry.CreatedAt)), Width = 170 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("backups_view.col_size"), Binding = new System.Windows.Data.Binding("SizeText"), Width = 90 });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("backups_view.col_path"), Binding = new System.Windows.Data.Binding(nameof(BackupEntry.Path)), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        root.Children.Add(grid);

        var restoreBtn = new Button { Content = _tr.Tr("backups_view.restore_button"), IsEnabled = false, Margin = new Thickness(0, 8, 0, 0), HorizontalAlignment = HorizontalAlignment.Left };
        root.Children.Add(restoreBtn);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        List<BackupEntry> backups = new();

        async Task ReloadAsync()
        {
            try
            {
                backups = await _api.ListBackupsAsync();
                grid.ItemsSource = backups.Select(b => new
                {
                    b.Id, b.BackupType,
                    // Python: backup["created_at"] or "-" (leer/null -> "-").
                    CreatedAt = DownloadCenterSupport.OrFallback(b.CreatedAt, "-"),
                    b.Path,
                    // DownloadCenterSupport.FormatSize ist das exakte Pendant
                    // zu _format_size() in backups_view.py (und damit auch zu
                    // download_center_view.py) - InvariantCulture statt des
                    // vorherigen lokalen, kulturabhaengigen F1-Formats.
                    SizeText = DownloadCenterSupport.FormatSize(b.SizeBytes),
                }).ToList();
                // Python setzt den Status NUR bei leerer Liste zurueck -
                // Erfolgsrueckmeldungen (create_done/restore_done) bleiben
                // nach dem Neuladen sichtbar stehen. Das vorherige
                // ": string.Empty" loeschte sie sofort wieder.
                if (backups.Count == 0) statusText.Text = _tr.Tr("backups_view.no_backups");
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("backups_view.load_failed", ("error", ex.Message));
            }
            restoreBtn.IsEnabled = false;
        }

        grid.SelectionChanged += (_, _) => restoreBtn.IsEnabled = grid.SelectedIndex >= 0;

        createDbBtn.Click += async (_, _) =>
        {
            try
            {
                await _api.CreateDbBackupAsync();
            }
            catch (Exception ex)
            {
                // Gap L (§37): Fehlerdialog wie show_api_error() in der
                // Python-Referenz - dort bricht der Fehlerfall OHNE
                // nachfolgenden Reload ab.
                ShowApiError(ex);
                return;
            }
            statusText.Text = _tr.Tr("backups_view.create_done");
            await ReloadAsync();
        };
        createConfigBtn.Click += async (_, _) =>
        {
            try
            {
                await _api.CreateConfigBackupAsync();
            }
            catch (Exception ex)
            {
                ShowApiError(ex);
                return;
            }
            statusText.Text = _tr.Tr("backups_view.create_done");
            await ReloadAsync();
        };
        refreshBtn.Click += async (_, _) => await ReloadAsync();

        restoreBtn.Click += async (_, _) =>
        {
            if (grid.SelectedIndex < 0 || grid.SelectedIndex >= backups.Count) return;
            var backup = backups[grid.SelectedIndex];
            var confirmResult = MessageBox.Show(
                _tr.Tr("backups_view.restore_confirm_text", ("backup_id", backup.Id)),
                _tr.Tr("backups_view.restore_confirm_title"),
                MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No);
            if (confirmResult != MessageBoxResult.Yes) return;
            try
            {
                await _api.RestoreBackupAsync(backup.Id, true);
            }
            catch (Exception ex)
            {
                ShowApiError(ex);
                return;
            }
            statusText.Text = _tr.Tr("backups_view.restore_done");
            await ReloadAsync();
        };

        await ReloadAsync();
    }
}
