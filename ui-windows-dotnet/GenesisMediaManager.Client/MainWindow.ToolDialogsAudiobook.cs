using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using GenesisMediaManager.Client.Api;
using Microsoft.Win32;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, achter inkrementeller Schritt - Pendant zu
/// ui-reference-pyside/genesis_ui/dialogs/audiobook_dialog.py (§23, ADR-0015).
/// Tab 1 "Metadaten": zeigt bereits in der Datei eingebettete Hoerbuch-Tags
/// rein lesend an, eine Uebernahme in die DB erfordert explizite
/// Bestaetigung (Prinzip #17). Tab 2 "Kapitel": zeigt gespeicherte Kapitel,
/// erlaubt Erkennen (eingebettete Kapitelmarken) oder gleichmaessige
/// Intervall-Erzeugung als Vorschau, Uebernahme ERSETZT alle bestehenden
/// Kapitel (jeweils mit Bestaetigung), sowie Umbenennen einzelner Kapitel
/// und Export (JSON/CSV, reine Lesefunktion ohne Bestaetigungspflicht).
/// Bewusst OHNE Online-Provider (Audible etc. sind Download/Import-
/// Adapter, Phase 8).
/// </summary>
public partial class MainWindow
{
    private static string FormatMs(int? ms)
    {
        if (ms is null) return "-";
        var totalSeconds = ms.Value / 1000.0;
        var minutes = (int)(totalSeconds / 60);
        var seconds = totalSeconds % 60;
        return $"{minutes:D2}:{seconds:00.00}".Replace(',', '.');
    }

    private async System.Threading.Tasks.Task<bool> ShowAudiobookDialogAsync(int mediaId, string filename)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("audiobook_dialog.window_title", ("filename", filename)), Width = 760, Height = 660,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var root = new DockPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        dialog.Content = root;

        var closeRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 8, 0, 0) };
        var closeBtn = new Button { Content = _tr.Tr("audiobook_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        closeRow.Children.Add(closeBtn);
        DockPanel.SetDock(closeRow, Dock.Bottom);
        root.Children.Add(closeRow);

        var tabs = new TabControl();
        root.Children.Add(tabs);

        bool changed = false;
        closeBtn.Click += (_, _) => dialog.Close();

        // --- Tab 1: Metadaten ------------------------------------------------
        var metaRoot = new StackPanel { Margin = new Thickness(8) };
        metaRoot.Children.Add(new TextBlock { Text = _tr.Tr("audiobook_dialog.metadata_info"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });
        var metaStatus = new TextBlock { Text = _tr.Tr("audiobook_dialog.loading"), Margin = new Thickness(0, 0, 0, 8) };
        metaRoot.Children.Add(metaStatus);

        var titleLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var authorLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var narratorLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var seriesLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var volumeLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var publisherLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var yearLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var languageLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var descriptionLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };

        void AddFormRow(string labelKey, TextBlock value)
        {
            var row = new Grid { Margin = new Thickness(0, 2, 0, 2) };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            var label = new TextBlock { Text = _tr.Tr(labelKey) };
            Grid.SetColumn(label, 0);
            Grid.SetColumn(value, 1);
            row.Children.Add(label);
            row.Children.Add(value);
            metaRoot.Children.Add(row);
        }
        AddFormRow("audiobook_dialog.field_title", titleLabel);
        AddFormRow("audiobook_dialog.field_author", authorLabel);
        AddFormRow("audiobook_dialog.field_narrator", narratorLabel);
        AddFormRow("audiobook_dialog.field_series", seriesLabel);
        AddFormRow("audiobook_dialog.field_volume", volumeLabel);
        AddFormRow("audiobook_dialog.field_publisher", publisherLabel);
        AddFormRow("audiobook_dialog.field_year", yearLabel);
        AddFormRow("audiobook_dialog.field_language", languageLabel);
        AddFormRow("audiobook_dialog.field_description", descriptionLabel);

        var persistedLabel = new TextBlock { Text = _tr.Tr("audiobook_dialog.not_saved_yet"), TextWrapping = TextWrapping.Wrap, Foreground = System.Windows.Media.Brushes.DarkSeaGreen, Margin = new Thickness(0, 8, 0, 8) };
        metaRoot.Children.Add(persistedLabel);

        var applyTagsBtn = new Button { Content = _tr.Tr("audiobook_dialog.apply_tags_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, HorizontalAlignment = HorizontalAlignment.Left };
        metaRoot.Children.Add(applyTagsBtn);
        tabs.Items.Add(new TabItem { Header = _tr.Tr("audiobook_dialog.tab_metadata"), Content = new ScrollViewer { Content = metaRoot, VerticalScrollBarVisibility = ScrollBarVisibility.Auto } });

        var empty = _tr.Tr("common.value_empty");

        async System.Threading.Tasks.Task ReloadPersistedAsync()
        {
            try
            {
                var saved = await _api.GetAudiobookAsync(mediaId);
                persistedLabel.Text = saved is null
                    ? _tr.Tr("audiobook_dialog.not_saved_yet")
                    : _tr.Tr("audiobook_dialog.saved_summary", ("title", saved.Title ?? empty), ("author", saved.Author ?? empty));
            }
            catch (Exception) { persistedLabel.Text = _tr.Tr("audiobook_dialog.not_saved_yet"); }
        }

        async System.Threading.Tasks.Task LoadMetadataAsync()
        {
            try
            {
                var p = await _api.GetAudiobookTagsPreviewAsync(mediaId);
                if (p is null) { metaStatus.Text = _tr.Tr("audiobook_dialog.no_tags_found"); return; }
                metaStatus.Text = p.HasAnyTag ? _tr.Tr("audiobook_dialog.tags_found") : _tr.Tr("audiobook_dialog.no_tags_found");

                string WithSource(string? value, string? sourceKey, string sourceLabelKey) =>
                    value is null ? empty : (sourceKey is not null ? $"{value}  ({_tr.Tr(sourceLabelKey)})" : value);

                titleLabel.Text = p.Title ?? empty;
                authorLabel.Text = WithSource(p.Author, p.AuthorSource,
                    p.AuthorSource == "artist_field" ? "audiobook_dialog.source_artist_field" : "audiobook_dialog.source_tag");
                narratorLabel.Text = WithSource(p.Narrator, p.NarratorSource,
                    p.NarratorSource == "composer_field" ? "audiobook_dialog.source_composer_field" : "audiobook_dialog.source_tag");
                seriesLabel.Text = WithSource(p.Series, p.SeriesSource,
                    p.SeriesSource == "album_field" ? "audiobook_dialog.source_album_field" : "audiobook_dialog.source_tag");
                volumeLabel.Text = p.VolumeNumber?.ToString() ?? empty;
                publisherLabel.Text = p.Publisher ?? empty;
                yearLabel.Text = p.Year?.ToString() ?? empty;
                languageLabel.Text = p.Language ?? empty;
                descriptionLabel.Text = p.Description ?? empty;
                applyTagsBtn.IsEnabled = p.HasAnyTag;
            }
            catch (Exception ex)
            {
                metaStatus.Text = _tr.Tr("audiobook_dialog.load_failed", ("error", ex.Message));
            }
            await ReloadPersistedAsync();
        }

        applyTagsBtn.Click += async (_, _) =>
        {
            if (MessageBox.Show(_tr.Tr("audiobook_dialog.confirm_tags_text"), _tr.Tr("audiobook_dialog.confirm_tags_title"),
                    MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                await _api.ApplyAudiobookTagsAsync(mediaId, true);
                changed = true;
                await ReloadPersistedAsync();
                MessageBox.Show(_tr.Tr("audiobook_dialog.applied_text"), _tr.Tr("audiobook_dialog.applied_title"));
            }
            catch (Exception ex)
            {
                // Gap L (§37): Fehlerdialog mit Fehler-ID/Loesungshinweis wie
                // show_api_error() in der Python-Referenz.
                ShowApiError(ex, _tr.Tr("audiobook_dialog.apply_tags_failed", ("error", ex.Message)));
            }
        };

        // --- Tab 2: Kapitel ----------------------------------------------------
        var chaptersRoot = new DockPanel { Margin = new Thickness(8) };
        var chaptersCurrentLabel = new TextBlock { Text = _tr.Tr("audiobook_dialog.chapters_current_label"), Margin = new Thickness(0, 0, 0, 4) };
        DockPanel.SetDock(chaptersCurrentLabel, Dock.Top);
        chaptersRoot.Children.Add(chaptersCurrentLabel);

        // CanUserSortColumns=false ist PFLICHT: renameChapterBtn.Click
        // indiziert unten per chaptersGrid.SelectedIndex in
        // "currentChapters" - sonst koennte bei aktiver Spaltensortierung
        // das FALSCHE Kapitel umbenannt werden. Gefunden im Deep-Search,
        // behoben.
        var chaptersGrid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, CanUserAddRows = false, Height = 160, Margin = new Thickness(0, 0, 0, 8), CanUserSortColumns = false };
        chaptersGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_index"), Binding = new Binding("Index") });
        chaptersGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_title"), Binding = new Binding("Title"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        chaptersGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_start"), Binding = new Binding("Start") });
        chaptersGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_end"), Binding = new Binding("End") });
        DockPanel.SetDock(chaptersGrid, Dock.Top);
        chaptersRoot.Children.Add(chaptersGrid);

        var chapterActionRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var renameChapterBtn = new Button { Content = _tr.Tr("audiobook_dialog.rename_chapter_button"), Padding = new Thickness(8, 4, 8, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var exportJsonBtn = new Button { Content = _tr.Tr("audiobook_dialog.export_json_button"), Padding = new Thickness(8, 4, 8, 4), Margin = new Thickness(0, 0, 8, 0) };
        var exportCsvBtn = new Button { Content = _tr.Tr("audiobook_dialog.export_csv_button"), Padding = new Thickness(8, 4, 8, 4) };
        chapterActionRow.Children.Add(renameChapterBtn);
        chapterActionRow.Children.Add(exportJsonBtn);
        chapterActionRow.Children.Add(exportCsvBtn);
        DockPanel.SetDock(chapterActionRow, Dock.Top);
        chaptersRoot.Children.Add(chapterActionRow);

        var detectLabel = new TextBlock { Text = _tr.Tr("audiobook_dialog.detect_section_label"), Margin = new Thickness(0, 0, 0, 4) };
        DockPanel.SetDock(detectLabel, Dock.Top);
        chaptersRoot.Children.Add(detectLabel);
        var detectBtn = new Button { Content = _tr.Tr("audiobook_dialog.detect_button"), Padding = new Thickness(8, 4, 8, 4), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 0, 8) };
        DockPanel.SetDock(detectBtn, Dock.Top);
        chaptersRoot.Children.Add(detectBtn);

        var generateLabel = new TextBlock { Text = _tr.Tr("audiobook_dialog.generate_section_label"), Margin = new Thickness(0, 0, 0, 4) };
        DockPanel.SetDock(generateLabel, Dock.Top);
        chaptersRoot.Children.Add(generateLabel);
        var generateRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        generateRow.Children.Add(new TextBlock { Text = _tr.Tr("audiobook_dialog.interval_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        var intervalBox = new TextBox { Text = "10", Width = 60, Margin = new Thickness(0, 0, 4, 0), VerticalContentAlignment = VerticalAlignment.Center };
        generateRow.Children.Add(intervalBox);
        generateRow.Children.Add(new TextBlock { Text = _tr.Tr("audiobook_dialog.minutes_suffix"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        var generatePreviewBtn = new Button { Content = _tr.Tr("audiobook_dialog.generate_preview_button"), Padding = new Thickness(8, 4, 8, 4) };
        generateRow.Children.Add(generatePreviewBtn);
        DockPanel.SetDock(generateRow, Dock.Top);
        chaptersRoot.Children.Add(generateRow);

        var previewLabel = new TextBlock { Text = _tr.Tr("audiobook_dialog.preview_label"), Margin = new Thickness(0, 0, 0, 4) };
        DockPanel.SetDock(previewLabel, Dock.Top);
        chaptersRoot.Children.Add(previewLabel);

        var applyCandidatesRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
        var applyCandidatesBtn = new Button { Content = _tr.Tr("audiobook_dialog.apply_candidates_button"), Padding = new Thickness(8, 4, 8, 4), IsEnabled = false };
        applyCandidatesRow.Children.Add(applyCandidatesBtn);
        DockPanel.SetDock(applyCandidatesRow, Dock.Bottom);
        chaptersRoot.Children.Add(applyCandidatesRow);

        // Parity zu ui-reference-pyside (keine interaktive Spaltensortierung
        // dort implementiert, §53).
        var candidatesGrid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, CanUserAddRows = false, Margin = new Thickness(0, 0, 0, 8), CanUserSortColumns = false };
        candidatesGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_title"), Binding = new Binding("Title"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        candidatesGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_start"), Binding = new Binding("Start") });
        candidatesGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("audiobook_dialog.column_end"), Binding = new Binding("End") });
        chaptersRoot.Children.Add(candidatesGrid);

        tabs.Items.Add(new TabItem { Header = _tr.Tr("audiobook_dialog.tab_chapters"), Content = chaptersRoot });

        List<ChapterEntry> currentChapters = new();
        List<ChapterCandidate> pendingCandidates = new();
        string? pendingAction = null; // "detect" oder "generate"

        async System.Threading.Tasks.Task LoadChaptersAsync()
        {
            try
            {
                currentChapters = await _api.ListChaptersAsync(mediaId);
                chaptersGrid.ItemsSource = currentChapters.Select(c => new { c.Index, Title = c.Title ?? "", Start = FormatMs(c.StartMs), End = FormatMs(c.EndMs) }).ToList();
            }
            catch (Exception ex)
            {
                ShowApiError(ex, _tr.Tr("audiobook_dialog.load_chapters_failed", ("error", ex.Message)));
            }
        }

        chaptersGrid.SelectionChanged += (_, _) => renameChapterBtn.IsEnabled = chaptersGrid.SelectedIndex >= 0;

        void RenderCandidates()
        {
            candidatesGrid.ItemsSource = pendingCandidates.Select(c => new
            {
                Title = c.Title ?? "",
                Start = FormatMs((int)(c.StartSeconds * 1000)),
                End = c.EndSeconds is { } e ? FormatMs((int)(e * 1000)) : "",
            }).ToList();
            applyCandidatesBtn.IsEnabled = pendingCandidates.Count > 0;
        }

        detectBtn.Click += async (_, _) =>
        {
            try
            {
                var result = await _api.DetectChaptersPreviewAsync(mediaId);
                pendingCandidates = result?.Candidates ?? new List<ChapterCandidate>();
                pendingAction = "detect";
                RenderCandidates();
            }
            catch (Exception ex)
            {
                ShowApiError(ex, _tr.Tr("audiobook_dialog.detect_failed", ("error", ex.Message)));
            }
        };

        generatePreviewBtn.Click += async (_, _) =>
        {
            var interval = double.TryParse(intervalBox.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out var iv) ? iv : 10.0;
            try
            {
                var result = await _api.GenerateChaptersPreviewAsync(mediaId, interval);
                pendingCandidates = result?.Candidates ?? new List<ChapterCandidate>();
                pendingAction = "generate";
                RenderCandidates();
            }
            catch (Exception ex)
            {
                ShowApiError(ex, _tr.Tr("audiobook_dialog.generate_failed", ("error", ex.Message)));
            }
        };

        applyCandidatesBtn.Click += async (_, _) =>
        {
            if (pendingCandidates.Count == 0 || pendingAction is null) return;
            if (MessageBox.Show(_tr.Tr("audiobook_dialog.confirm_chapters_text", ("count", pendingCandidates.Count.ToString())),
                    _tr.Tr("audiobook_dialog.confirm_chapters_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                if (pendingAction == "detect")
                {
                    await _api.DetectChaptersApplyAsync(mediaId, true);
                }
                else
                {
                    var interval = double.TryParse(intervalBox.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out var iv) ? iv : 10.0;
                    await _api.GenerateChaptersApplyAsync(mediaId, interval, true);
                }
                changed = true;
                await LoadChaptersAsync();
                MessageBox.Show(_tr.Tr("audiobook_dialog.chapters_applied_text"), _tr.Tr("audiobook_dialog.applied_title"));
            }
            catch (Exception ex)
            {
                ShowApiError(ex, _tr.Tr("audiobook_dialog.apply_chapters_failed", ("error", ex.Message)));
            }
        };

        renameChapterBtn.Click += async (_, _) =>
        {
            if (chaptersGrid.SelectedIndex < 0 || chaptersGrid.SelectedIndex >= currentChapters.Count) return;
            var chapter = currentChapters[chaptersGrid.SelectedIndex];
            var newTitle = PromptForText(_tr.Tr("audiobook_dialog.rename_chapter_title"), _tr.Tr("audiobook_dialog.rename_chapter_prompt"), chapter.Title ?? "");
            if (string.IsNullOrEmpty(newTitle)) return;
            if (MessageBox.Show(_tr.Tr("audiobook_dialog.confirm_rename_text", ("title", newTitle)), _tr.Tr("audiobook_dialog.confirm_rename_title"),
                    MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                await _api.RenameChapterAsync(mediaId, chapter.Id, newTitle, true);
                changed = true;
                await LoadChaptersAsync();
            }
            catch (Exception ex)
            {
                ShowApiError(ex, _tr.Tr("audiobook_dialog.rename_failed", ("error", ex.Message)));
            }
        };

        async System.Threading.Tasks.Task ExportAsync(string format)
        {
            var saveDialog = new SaveFileDialog
            {
                Title = _tr.Tr("audiobook_dialog.export_dialog_title"),
                FileName = $"chapters.{format}",
                Filter = format == "json" ? _tr.Tr("audiobook_dialog.export_filter_json") : _tr.Tr("audiobook_dialog.export_filter_csv"),
            };
            if (saveDialog.ShowDialog() != true) return;
            try
            {
                var content = await _api.ExportChaptersAsync(mediaId, format);
                await File.WriteAllTextAsync(saveDialog.FileName, content, System.Text.Encoding.UTF8);
                MessageBox.Show(_tr.Tr("audiobook_dialog.export_done_text", ("path", saveDialog.FileName)), _tr.Tr("audiobook_dialog.export_done_title"));
            }
            catch (Exception ex)
            {
                ShowApiError(ex, _tr.Tr("audiobook_dialog.export_failed", ("error", ex.Message)));
            }
        }
        exportJsonBtn.Click += async (_, _) => await ExportAsync("json");
        exportCsvBtn.Click += async (_, _) => await ExportAsync("csv");

        await LoadMetadataAsync();
        await LoadChaptersAsync();
        dialog.ShowDialog();
        return changed;
    }
}
