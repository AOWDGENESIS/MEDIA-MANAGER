using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;
using Microsoft.Win32;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Download-/Import-Center
/// (nav.download_center/nav.import, §30-§32, ADR-0019). Pendant zu
/// ui-reference-pyside/genesis_ui/views/download_center_view.py: zwei
/// Tabs (URL/Online-Quelle, Lokale Datei). Jeder §31-Vorschauschritt
/// (erkennen/pruefen/Metadaten/Optionen) ist ein eigener expliziter
/// Knopfdruck - keine automatische Verkettung (Prinzip #4/#5/#6). Ein
/// tatsaechlicher Download/Import erfordert IMMER eine explizite
/// Bestaetigung (§56) - diese Seite laedt NIE automatisch irgendetwas
/// herunter.
/// </summary>
public partial class MainWindow
{
    private async Task ShowDownloadCenterAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("download_center.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });

        var statusBanner = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 4) };
        root.Children.Add(statusBanner);

        var legalNotice = new TextBlock { Text = _tr.Tr("download_center.legal_notice"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(legalNotice);

        var tabs = new TabControl { MinHeight = 420 };
        root.Children.Add(tabs);

        // --- Tab 1: URL / Online-Quelle --------------------------------------
        var urlTabPanel = new StackPanel { Margin = new Thickness(8) };
        var urlRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        urlRow.Children.Add(new TextBlock { Text = _tr.Tr("download_center.url_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        var urlBox = new TextBox { Width = 440 };
        urlBox.ToolTip = _tr.Tr("download_center.url_placeholder");
        urlRow.Children.Add(urlBox);
        urlTabPanel.Children.Add(urlRow);

        var buttonRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var detectBtn = new Button { Content = _tr.Tr("download_center.detect_button"), Margin = new Thickness(0, 0, 8, 0) };
        var checkBtn = new Button { Content = _tr.Tr("download_center.check_availability_button"), Margin = new Thickness(0, 0, 8, 0) };
        var metaBtn = new Button { Content = _tr.Tr("download_center.fetch_metadata_button"), Margin = new Thickness(0, 0, 8, 0) };
        var optionsBtn = new Button { Content = _tr.Tr("download_center.list_options_button") };
        buttonRow.Children.Add(detectBtn);
        buttonRow.Children.Add(checkBtn);
        buttonRow.Children.Add(metaBtn);
        buttonRow.Children.Add(optionsBtn);
        urlTabPanel.Children.Add(buttonRow);

        // CanUserSortColumns=false ist PFLICHT: unten wird per
        // optionsGrid.SelectedIndex in "lastOptions" indiziert - bei
        // aktivierter Spaltensortierung (WPF-Default: true) koennte eine
        // ANDERE Qualitaets-/Formatoption heruntergeladen werden als die
        // sichtbar ausgewaehlte. Gefunden im Deep-Search, behoben.
        var optionsGrid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, MaxHeight = 140, Margin = new Thickness(0, 0, 0, 8), CanUserSortColumns = false };
        optionsGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("download_center.options_col_label"), Binding = new System.Windows.Data.Binding("Label"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        optionsGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("download_center.options_col_size"), Binding = new System.Windows.Data.Binding("SizeText"), Width = 120 });
        urlTabPanel.Children.Add(optionsGrid);

        var importBtn = new Button { Content = _tr.Tr("download_center.import_button"), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 0, 8) };
        urlTabPanel.Children.Add(importBtn);

        var urlLog = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, MinHeight = 140 };
        urlTabPanel.Children.Add(urlLog);

        tabs.Items.Add(new TabItem { Header = _tr.Tr("download_center.tab_url"), Content = new ScrollViewer { Content = urlTabPanel } });

        // --- Tab 2: Lokale Datei ----------------------------------------------
        var localTabPanel = new StackPanel { Margin = new Thickness(8) };
        var localPathRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        localPathRow.Children.Add(new TextBlock { Text = _tr.Tr("download_center.local_file_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        var localPathBox = new TextBox { Width = 380, Margin = new Thickness(0, 0, 8, 0) };
        var browseBtn = new Button { Content = _tr.Tr("download_center.browse_button") };
        localPathRow.Children.Add(localPathBox);
        localPathRow.Children.Add(browseBtn);
        localTabPanel.Children.Add(localPathRow);

        var localImportBtn = new Button { Content = _tr.Tr("download_center.import_button"), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 0, 8) };
        localTabPanel.Children.Add(localImportBtn);

        var localLog = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, MinHeight = 140 };
        localTabPanel.Children.Add(localLog);

        tabs.Items.Add(new TabItem { Header = _tr.Tr("download_center.tab_local"), Content = new ScrollViewer { Content = localTabPanel } });

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        void Log(TextBox box, string text) => box.AppendText((box.Text.Length > 0 ? Environment.NewLine : string.Empty) + text);

        try
        {
            var providers = await _api.ListDownloadProvidersAsync();
            if (providers is null || !providers.Enabled)
            {
                statusBanner.Text = _tr.Tr("download_center.status_disabled");
            }
            else
            {
                var names = string.Join(", ", providers.Providers.Select(p => p.DisplayName));
                statusBanner.Text = _tr.Tr("download_center.status_enabled", ("providers", names));
            }
        }
        catch (Exception ex)
        {
            statusBanner.Text = ex.Message;
        }

        string? detectedProvider = null;
        List<DownloadOptionInfo> lastOptions = new();
        string? selectedOptionId = null;

        string? CurrentUrl()
        {
            var url = urlBox.Text.Trim();
            if (url.Length == 0)
            {
                MessageBox.Show(_tr.Tr("download_center.url_required"), _tr.Tr("download_center.title"));
                return null;
            }
            return url;
        }

        static string FormatDuration(double? seconds, string unknown)
        {
            if (seconds is null) return unknown;
            var total = (int)seconds.Value;
            var h = total / 3600; var m = total % 3600 / 60; var s = total % 60;
            return h > 0 ? $"{h}:{m:D2}:{s:D2}" : $"{m}:{s:D2}";
        }

        static string FormatSize(long? numBytes)
        {
            if (numBytes is null or 0) return "-";
            double size = numBytes.Value;
            foreach (var unit in new[] { "B", "KB", "MB" })
            {
                if (size < 1024) return $"{size:F1} {unit}";
                size /= 1024;
            }
            return $"{size:F1} GB";
        }

        detectBtn.Click += async (_, _) =>
        {
            var url = CurrentUrl();
            if (url is null) return;
            try
            {
                var result = await _api.DetectDownloadSourceAsync(url);
                detectedProvider = result?.ProviderId;
                Log(urlLog, detectedProvider is not null
                    ? _tr.Tr("download_center.detected_provider", ("provider", result!.DisplayName ?? "-"))
                    : _tr.Tr("download_center.detected_provider_none"));
            }
            catch (Exception ex)
            {
                Log(urlLog, _tr.Tr("download_center.detect_failed", ("error", ex.Message)));
            }
        };

        checkBtn.Click += async (_, _) =>
        {
            var url = CurrentUrl();
            if (url is null) return;
            Log(urlLog, _tr.Tr("download_center.availability_checking"));
            try
            {
                var result = await _api.CheckDownloadAvailabilityAsync(url);
                Log(urlLog, result?.Available == true
                    ? _tr.Tr("download_center.availability_available")
                    : _tr.Tr("download_center.availability_unavailable", ("reason", result?.Reason ?? "-")));
            }
            catch (Exception ex)
            {
                Log(urlLog, _tr.Tr("download_center.availability_failed", ("error", ex.Message)));
            }
        };

        metaBtn.Click += async (_, _) =>
        {
            var url = CurrentUrl();
            if (url is null) return;
            Log(urlLog, _tr.Tr("download_center.metadata_fetching"));
            try
            {
                var meta = await _api.FetchDownloadMetadataAsync(url);
                var unknown = _tr.Tr("download_center.metadata_unknown");
                Log(urlLog, _tr.Tr("download_center.metadata_title", ("title", meta?.Title ?? unknown)));
                Log(urlLog, _tr.Tr("download_center.metadata_uploader", ("uploader", meta?.Uploader ?? unknown)));
                Log(urlLog, _tr.Tr("download_center.metadata_duration", ("duration", FormatDuration(meta?.DurationSeconds, unknown))));
                Log(urlLog, _tr.Tr("download_center.metadata_license", ("license", meta?.License ?? unknown)));
            }
            catch (Exception ex)
            {
                Log(urlLog, _tr.Tr("download_center.metadata_failed", ("error", ex.Message)));
            }
        };

        optionsBtn.Click += async (_, _) =>
        {
            var url = CurrentUrl();
            if (url is null) return;
            optionsGrid.ItemsSource = null;
            lastOptions = new List<DownloadOptionInfo>();
            try
            {
                var result = await _api.ListDownloadOptionsAsync(url);
                lastOptions = result?.Options ?? new List<DownloadOptionInfo>();
                if (lastOptions.Count == 0)
                {
                    Log(urlLog, _tr.Tr("download_center.options_none"));
                    return;
                }
                optionsGrid.ItemsSource = lastOptions.Select(o => new { Label = o.Label, SizeText = FormatSize(o.ApproxSizeBytes), o.OptionId }).ToList();
                if (optionsGrid.Items.Count > 0) optionsGrid.SelectedIndex = 0;
            }
            catch (Exception ex)
            {
                Log(urlLog, _tr.Tr("download_center.options_failed", ("error", ex.Message)));
            }
        };

        optionsGrid.SelectionChanged += (_, _) =>
        {
            selectedOptionId = optionsGrid.SelectedIndex >= 0 && optionsGrid.SelectedIndex < lastOptions.Count
                ? lastOptions[optionsGrid.SelectedIndex].OptionId : null;
        };

        importBtn.Click += async (_, _) =>
        {
            var url = CurrentUrl();
            if (url is null) return;
            var optionId = selectedOptionId ?? "default";
            var confirmResult = MessageBox.Show(
                _tr.Tr("download_center.confirm_import_text", ("url", url), ("provider", detectedProvider ?? "?"), ("option", optionId)),
                _tr.Tr("download_center.confirm_import_title"), MessageBoxButton.YesNo);
            if (confirmResult != MessageBoxResult.Yes) return;
            Log(urlLog, _tr.Tr("download_center.import_running"));
            try
            {
                var result = await _api.ImportDownloadAsync(url, optionId, true);
                ReportImportResult(urlLog, result);
            }
            catch (Exception ex)
            {
                Log(urlLog, _tr.Tr("download_center.import_failed", ("error", ex.Message)));
            }
        };

        browseBtn.Click += (_, _) =>
        {
            var dialog = new OpenFileDialog { Title = _tr.Tr("download_center.browse_title") };
            if (dialog.ShowDialog() == true) localPathBox.Text = dialog.FileName;
        };

        localImportBtn.Click += async (_, _) =>
        {
            var path = localPathBox.Text.Trim();
            if (path.Length == 0)
            {
                MessageBox.Show(_tr.Tr("download_center.local_file_required"), _tr.Tr("download_center.title"));
                return;
            }
            var confirmResult = MessageBox.Show(
                _tr.Tr("download_center.confirm_local_import_text", ("path", path)),
                _tr.Tr("download_center.confirm_local_import_title"), MessageBoxButton.YesNo);
            if (confirmResult != MessageBoxResult.Yes) return;
            try
            {
                var result = await _api.ImportLocalFileAsync(path, true);
                ReportImportResult(localLog, result);
            }
            catch (Exception ex)
            {
                Log(localLog, _tr.Tr("download_center.import_failed", ("error", ex.Message)));
            }
        };

        void ReportImportResult(TextBox log, DownloadImportResult? result)
        {
            Log(log, _tr.Tr(
                "download_center.import_done",
                ("job_id", result?.JobId ?? "-"), ("media_id", result?.MediaFileId ?? 0),
                ("path", result?.AbsolutePath ?? "-")));
            if (result?.Warnings is { Count: > 0 })
            {
                Log(log, _tr.Tr("download_center.import_warnings", ("warnings", string.Join("; ", result.Warnings))));
            }
            if (!string.IsNullOrEmpty(result?.SuggestedFilename))
            {
                Log(log, _tr.Tr("download_center.suggested_filename", ("name", result.SuggestedFilename)));
            }
        }
    }
}
