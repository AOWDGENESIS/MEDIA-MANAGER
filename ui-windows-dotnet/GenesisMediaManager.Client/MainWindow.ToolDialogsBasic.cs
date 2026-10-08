using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, achter inkrementeller Schritt - Pendants zu
/// ui-reference-pyside/genesis_ui/dialogs/{rename,metadata,artwork}_dialog.py.
/// Alle drei folgen demselben Muster Vorschau/Laden -> explizite
/// Nutzerbestaetigung (Yes/No) -> Anwenden (Prinzip #17, §44) - die
/// Mediendatei wird NIE automatisch veraendert. Jede Methode liefert
/// <c>true</c> zurueck, wenn tatsaechlich etwas geaendert wurde (damit der
/// Aufrufer in MainWindow.xaml.cs die Medientabelle/Detailansicht
/// aktualisieren kann), sonst <c>false</c> (Dialog nur angesehen/
/// abgebrochen).
/// </summary>
public partial class MainWindow
{
    private const string DefaultRenameTemplate = "{track:02d} - {artist} - {title}.{ext}";

    // --- Umbenennen (Pendant zu RenamePreviewDialog, §15/§16) ---------------
    private async System.Threading.Tasks.Task<bool> ShowRenameDialogAsync(System.Collections.Generic.List<int> mediaFileIds)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("rename_dialog.window_title"), Width = 820, Height = 460,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var root = new Grid { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        dialog.Content = root;

        var info = new TextBlock { Text = _tr.Tr("rename_dialog.info", ("count", mediaFileIds.Count.ToString())), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        Grid.SetRow(info, 0);
        root.Children.Add(info);

        var templateRow = new DockPanel { Margin = new Thickness(0, 0, 0, 8) };
        var templateLabel = new TextBlock { Text = _tr.Tr("rename_dialog.template_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) };
        DockPanel.SetDock(templateLabel, Dock.Left);
        var previewBtn = new Button { Content = _tr.Tr("rename_dialog.preview_button"), Padding = new Thickness(10, 4, 10, 4) };
        DockPanel.SetDock(previewBtn, Dock.Right);
        var templateBox = new TextBox { Text = DefaultRenameTemplate, Margin = new Thickness(0, 0, 8, 0), VerticalContentAlignment = VerticalAlignment.Center };
        templateRow.Children.Add(templateLabel);
        templateRow.Children.Add(previewBtn);
        templateRow.Children.Add(templateBox);
        Grid.SetRow(templateRow, 1);
        root.Children.Add(templateRow);

        var statusLabel = new TextBlock { Text = _tr.Tr("rename_dialog.no_preview_yet"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        Grid.SetRow(statusLabel, 2);
        root.Children.Add(statusLabel);

        // Parity zu ui-reference-pyside (keine interaktive Spaltensortierung
        // dort implementiert, §53).
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, CanUserAddRows = false, Margin = new Thickness(0, 0, 0, 8), CanUserSortColumns = false };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("rename_dialog.column_old_name"), Binding = new System.Windows.Data.Binding("OldName"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("rename_dialog.column_new_name"), Binding = new System.Windows.Data.Binding("NewName"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("rename_dialog.column_status"), Binding = new System.Windows.Data.Binding("Status"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        Grid.SetRow(grid, 3);
        root.Children.Add(grid);

        var btnRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Stretch, Margin = new Thickness(0, 4, 0, 0) };
        var applyBtn = new Button { Content = _tr.Tr("rename_dialog.apply_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var cancelBtn = new Button { Content = _tr.Tr("rename_dialog.cancel_button"), Padding = new Thickness(10, 4, 10, 4), HorizontalAlignment = HorizontalAlignment.Right };
        btnRow.Children.Add(applyBtn);
        btnRow.Children.Add(new Grid { Width = 400 });
        btnRow.Children.Add(cancelBtn);
        Grid.SetRow(btnRow, 4);
        root.Children.Add(btnRow);

        List<RenamePreviewItem> previewItems = new();

        async System.Threading.Tasks.Task RunPreviewAsync()
        {
            var template = templateBox.Text.Trim();
            if (string.IsNullOrEmpty(template))
            {
                statusLabel.Text = _tr.Tr("rename_dialog.template_empty");
                applyBtn.IsEnabled = false;
                return;
            }
            try
            {
                previewItems = await _api.RenamePreviewAsync(mediaFileIds, template);
            }
            catch (Exception ex)
            {
                statusLabel.Text = _tr.Tr("rename_dialog.template_invalid", ("error", ex.Message));
                applyBtn.IsEnabled = false;
                grid.ItemsSource = null;
                return;
            }

            var actionable = previewItems.Count(i => i.IsActionable);
            statusLabel.Text = _tr.Tr("rename_dialog.summary", ("count", previewItems.Count.ToString()), ("actionable", actionable.ToString()));

            string FileName(string path) => path.Replace('\\', '/').Split('/').Last();
            var rows = previewItems.Select(item =>
            {
                string status;
                if (!string.IsNullOrEmpty(item.TemplateError)) status = _tr.Tr("rename_dialog.status_error", ("error", item.TemplateError));
                else if (item.HasConflict) status = _tr.Tr("rename_dialog.status_conflict", ("reason", item.ConflictReason ?? ""));
                else if (item.IsIdentical) status = _tr.Tr("rename_dialog.status_identical");
                else if (item.EmptyFields.Count > 0) status = _tr.Tr("rename_dialog.status_ready_with_warning", ("fields", string.Join(", ", item.EmptyFields)));
                else status = _tr.Tr("rename_dialog.status_ready");
                return new { OldName = FileName(item.OldAbsolutePath), NewName = FileName(item.NewAbsolutePath), Status = status };
            }).ToList();
            grid.ItemsSource = rows;
            applyBtn.IsEnabled = actionable > 0;
        }

        previewBtn.Click += async (_, _) => await RunPreviewAsync();
        cancelBtn.Click += (_, _) => dialog.Close();

        bool changed = false;
        applyBtn.Click += async (_, _) =>
        {
            var actionable = previewItems.Count(i => i.IsActionable);
            if (MessageBox.Show(
                    _tr.Tr("rename_dialog.confirm_text", ("count", actionable.ToString())),
                    _tr.Tr("rename_dialog.confirm_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No)
                != MessageBoxResult.Yes)
            {
                return;
            }
            try
            {
                var result = await _api.RenameApplyAsync(mediaFileIds, templateBox.Text.Trim(), true);
                var applied = result?.Results.Count(r => r.Applied) ?? 0;
                var total = result?.Results.Count ?? 0;
                changed = applied > 0;
                MessageBox.Show(
                    _tr.Tr("rename_dialog.done_text", ("applied", applied.ToString()), ("total", total.ToString())),
                    _tr.Tr("rename_dialog.done_title"));
                dialog.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("rename_dialog.apply_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        await RunPreviewAsync();
        dialog.ShowDialog();
        return changed;
    }

    // --- Metadaten-Vorschlaege (Pendant zu MetadataSuggestionsDialog, §10/§11) ---
    private async System.Threading.Tasks.Task<bool> ShowMetadataSuggestionsDialogAsync(int mediaId, string filename)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("metadata_dialog.window_title", ("filename", filename)), Width = 780, Height = 400,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var root = new Grid { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        dialog.Content = root;

        var info = new TextBlock { Text = _tr.Tr("metadata_dialog.info"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        Grid.SetRow(info, 0);
        root.Children.Add(info);

        var statusLabel = new TextBlock { Text = _tr.Tr("metadata_dialog.loading"), Margin = new Thickness(0, 0, 0, 8) };
        Grid.SetRow(statusLabel, 1);
        root.Children.Add(statusLabel);

        // CanUserSortColumns=false ist PFLICHT: applyBtn.Click indiziert
        // unten per grid.SelectedIndex in "suggestions" - sonst koennte bei
        // aktiver Spaltensortierung der FALSCHE Metadaten-Treffer uebernommen
        // werden. Gefunden im Deep-Search, behoben.
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, CanUserAddRows = false, SelectionMode = DataGridSelectionMode.Single, Margin = new Thickness(0, 0, 0, 8), CanUserSortColumns = false };
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_provider"), Binding = new System.Windows.Data.Binding("Provider") });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_confidence"), Binding = new System.Windows.Data.Binding("ConfidenceText") });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_title"), Binding = new System.Windows.Data.Binding("Title") });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_artist"), Binding = new System.Windows.Data.Binding("Artist") });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_album"), Binding = new System.Windows.Data.Binding("Album") });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_year"), Binding = new System.Windows.Data.Binding("Year") });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("metadata_dialog.column_track"), Binding = new System.Windows.Data.Binding("Track") });
        Grid.SetRow(grid, 2);
        root.Children.Add(grid);

        var btnRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 8, 0, 0) };
        var applyBtn = new Button { Content = _tr.Tr("metadata_dialog.apply_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var closeBtn = new Button { Content = _tr.Tr("metadata_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        btnRow.Children.Add(applyBtn);
        btnRow.Children.Add(closeBtn);
        Grid.SetRow(btnRow, 3);
        root.Children.Add(btnRow);

        List<MetadataSuggestion> suggestions = new();
        grid.SelectionChanged += (_, _) => applyBtn.IsEnabled = grid.SelectedIndex >= 0;
        closeBtn.Click += (_, _) => dialog.Close();

        bool applied = false;
        applyBtn.Click += async (_, _) =>
        {
            if (grid.SelectedIndex < 0 || grid.SelectedIndex >= suggestions.Count) return;
            var match = suggestions[grid.SelectedIndex].Match;
            if (MessageBox.Show(
                    _tr.Tr("metadata_dialog.confirm_text",
                        ("title", match.Title ?? ""), ("artist", match.Artist ?? ""), ("album", match.Album ?? ""),
                        ("confidence", $"{match.Confidence:P0}")),
                    _tr.Tr("metadata_dialog.confirm_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No)
                != MessageBoxResult.Yes)
            {
                return;
            }
            try
            {
                await _api.ApplyMetadataSuggestionAsync(mediaId, match, true);
                applied = true;
                MessageBox.Show(_tr.Tr("metadata_dialog.applied_text"), _tr.Tr("metadata_dialog.applied_title"));
                dialog.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("metadata_dialog.apply_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        try
        {
            suggestions = await _api.GetMetadataSuggestionsAsync(mediaId);
            if (suggestions.Count == 0)
            {
                statusLabel.Text = _tr.Tr("metadata_dialog.none_found");
            }
            else
            {
                statusLabel.Text = _tr.Tr("metadata_dialog.found_count", ("count", suggestions.Count.ToString()));
                grid.ItemsSource = suggestions.Select(s => new
                {
                    s.Match.Provider,
                    ConfidenceText = $"{s.Match.Confidence:P0}",
                    s.Match.Title,
                    s.Match.Artist,
                    s.Match.Album,
                    Year = s.Match.Year?.ToString() ?? "",
                    Track = s.Match.TrackNumber?.ToString() ?? "",
                }).ToList();
            }
        }
        catch (Exception ex)
        {
            statusLabel.Text = _tr.Tr("metadata_dialog.load_failed", ("error", ex.Message));
        }

        dialog.ShowDialog();
        return applied;
    }

    // --- Artwork (Pendant zu ArtworkDialog, §22) ----------------------------
    private async System.Threading.Tasks.Task<bool> ShowArtworkDialogAsync(int mediaId, string filename)
    {
        const double previewSize = 320;
        var dialog = new Window
        {
            Title = _tr.Tr("artwork_dialog.window_title", ("filename", filename)), Width = 420, Height = 540,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var root = new StackPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        dialog.Content = root;

        var statusLabel = new TextBlock { Text = _tr.Tr("artwork_dialog.loading"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(statusLabel);

        var imageBorder = new Border { BorderBrush = System.Windows.Media.Brushes.Gray, BorderThickness = new Thickness(1), Width = previewSize, Height = previewSize, Margin = new Thickness(0, 0, 0, 8) };
        var image = new Image { Stretch = System.Windows.Media.Stretch.Uniform };
        var imageText = new TextBlock { TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Center, TextWrapping = TextWrapping.Wrap, Visibility = Visibility.Collapsed };
        var imageGrid = new Grid();
        imageGrid.Children.Add(image);
        imageGrid.Children.Add(imageText);
        imageBorder.Child = imageGrid;
        root.Children.Add(imageBorder);

        var btnRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var fetchBtn = new Button { Content = _tr.Tr("artwork_dialog.fetch_button"), Padding = new Thickness(10, 4, 10, 4), Margin = new Thickness(0, 0, 8, 0) };
        var embedBtn = new Button { Content = _tr.Tr("artwork_dialog.embed_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var closeBtn = new Button { Content = _tr.Tr("artwork_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        btnRow.Children.Add(fetchBtn);
        btnRow.Children.Add(embedBtn);
        btnRow.Children.Add(closeBtn);
        root.Children.Add(btnRow);

        var infoText = new TextBlock { Text = _tr.Tr("artwork_dialog.info"), TextWrapping = TextWrapping.Wrap, Opacity = 0.8 };
        root.Children.Add(infoText);

        void ShowBytes(byte[] data)
        {
            try
            {
                var bitmap = new BitmapImage();
                using var stream = new MemoryStream(data);
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.StreamSource = stream;
                bitmap.EndInit();
                bitmap.Freeze();
                image.Source = bitmap;
                image.Visibility = Visibility.Visible;
                imageText.Visibility = Visibility.Collapsed;
            }
            catch (Exception)
            {
                image.Visibility = Visibility.Collapsed;
                imageText.Text = _tr.Tr("artwork_dialog.image_unloadable");
                imageText.Visibility = Visibility.Visible;
            }
        }

        async System.Threading.Tasks.Task LoadEmbeddedAsync()
        {
            try
            {
                var result = await _api.GetArtworkBytesAsync(mediaId);
                if (result is null)
                {
                    statusLabel.Text = _tr.Tr("artwork_dialog.none_embedded");
                    image.Visibility = Visibility.Collapsed;
                    imageText.Text = _tr.Tr("artwork_dialog.no_cover_placeholder");
                    imageText.Visibility = Visibility.Visible;
                    return;
                }
                statusLabel.Text = _tr.Tr("artwork_dialog.current_embedded");
                ShowBytes(result.Value.Data);
            }
            catch (Exception ex)
            {
                statusLabel.Text = _tr.Tr("artwork_dialog.load_failed", ("error", ex.Message));
            }
        }

        int? pendingArtworkId = null;
        bool changed = false;

        fetchBtn.Click += async (_, _) =>
        {
            try
            {
                var result = await _api.FetchArtworkOnlineAsync(mediaId);
                if (result is null) return;
                pendingArtworkId = result.ArtworkId;
                try
                {
                    var data = await File.ReadAllBytesAsync(result.CachedPath);
                    statusLabel.Text = _tr.Tr("artwork_dialog.fetched_not_embedded");
                    ShowBytes(data);
                    embedBtn.IsEnabled = true;
                }
                catch (Exception ex)
                {
                    MessageBox.Show(_tr.Tr("artwork_dialog.cache_read_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("artwork_dialog.fetch_failed_text", ("error", ex.Message)), _tr.Tr("artwork_dialog.fetch_failed_title"));
            }
        };

        embedBtn.Click += async (_, _) =>
        {
            if (pendingArtworkId is null) return;
            if (MessageBox.Show(_tr.Tr("artwork_dialog.confirm_text"), _tr.Tr("artwork_dialog.confirm_title"),
                    MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
            {
                return;
            }
            try
            {
                await _api.EmbedArtworkAsync(mediaId, pendingArtworkId.Value, true);
                changed = true;
                embedBtn.IsEnabled = false;
                MessageBox.Show(_tr.Tr("artwork_dialog.embedded_text"), _tr.Tr("artwork_dialog.embedded_title"));
                await LoadEmbeddedAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("artwork_dialog.embed_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        closeBtn.Click += (_, _) => dialog.Close();

        await LoadEmbeddedAsync();
        dialog.ShowDialog();
        return changed;
    }
}
