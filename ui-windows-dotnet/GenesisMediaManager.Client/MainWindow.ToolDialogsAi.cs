using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, achter inkrementeller Schritt - Pendant zu
/// ui-reference-pyside/genesis_ui/dialogs/ai_dialog.py (§25/§27, ADR-0017).
/// Tab 1 "KI-Vorschlaege": Erkennen -> Vorschlag -> Confidence -> explizite
/// Auswahl -> Bestaetigung -> Uebernahme (Prinzip #4/#17). Tab 2
/// "KI-Musik" (nur fuer Medienart music/ai_music sichtbar) ist IMMER eine
/// manuelle Nutzerangabe, NIE ein KI-Vorschlag (§27 - GENESIS kann
/// KI-Urheberschaft nicht selbst feststellen).
/// </summary>
public partial class MainWindow
{
    private static readonly HashSet<string> AiMusicRelevantKinds = new() { "music", "ai_music" };
    private static readonly string[] AiStatusValues = { "unknown", "human_generated", "ai_generated", "hybrid" };

    private async System.Threading.Tasks.Task<bool> ShowAiDialogAsync(int mediaId, string filename, string kind)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("ai_dialog.window_title", ("filename", filename)), Width = 760, Height = 640,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var root = new DockPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        dialog.Content = root;

        var statusBanner = new TextBlock { Text = _tr.Tr("ai_dialog.loading"), TextWrapping = TextWrapping.Wrap, Foreground = System.Windows.Media.Brushes.SteelBlue, Margin = new Thickness(0, 0, 0, 8) };
        DockPanel.SetDock(statusBanner, Dock.Top);
        root.Children.Add(statusBanner);

        var closeRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 8, 0, 0) };
        var closeBtn = new Button { Content = _tr.Tr("ai_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        closeRow.Children.Add(closeBtn);
        DockPanel.SetDock(closeRow, Dock.Bottom);
        root.Children.Add(closeRow);

        var tabs = new TabControl();
        root.Children.Add(tabs);

        bool changed = false;
        closeBtn.Click += (_, _) => dialog.Close();

        // --- Tab 1: KI-Vorschlaege (§25) -------------------------------------
        var suggestionsTabRoot = new DockPanel { Margin = new Thickness(8) };
        var suggestionsInfo = new TextBlock { Text = _tr.Tr("ai_dialog.suggestions_info"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        DockPanel.SetDock(suggestionsInfo, Dock.Top);
        suggestionsTabRoot.Children.Add(suggestionsInfo);

        var generateBtn = new Button { Content = _tr.Tr("ai_dialog.generate_button"), Padding = new Thickness(10, 4, 10, 4), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 0, 8) };
        DockPanel.SetDock(generateBtn, Dock.Top);
        suggestionsTabRoot.Children.Add(generateBtn);

        var suggestionsStatus = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        DockPanel.SetDock(suggestionsStatus, Dock.Top);
        suggestionsTabRoot.Children.Add(suggestionsStatus);

        var storedTitle = new TextBlock { Text = _tr.Tr("ai_dialog.stored_metadata_title"), FontWeight = FontWeights.Bold, Margin = new Thickness(0, 8, 0, 4) };
        DockPanel.SetDock(storedTitle, Dock.Bottom);
        var storedLabel = new TextBlock { Text = _tr.Tr("ai_dialog.no_stored_metadata"), TextWrapping = TextWrapping.Wrap };
        DockPanel.SetDock(storedLabel, Dock.Bottom);
        var applyRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
        var applySuggestionsBtn = new Button { Content = _tr.Tr("ai_dialog.apply_selected_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false };
        applyRow.Children.Add(applySuggestionsBtn);
        DockPanel.SetDock(applyRow, Dock.Bottom);
        suggestionsTabRoot.Children.Add(storedLabel);
        suggestionsTabRoot.Children.Add(storedTitle);
        suggestionsTabRoot.Children.Add(applyRow);

        var suggestionsScroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var suggestionsPanel = new StackPanel();
        suggestionsScroll.Content = suggestionsPanel;
        suggestionsTabRoot.Children.Add(suggestionsScroll);

        tabs.Items.Add(new TabItem { Header = _tr.Tr("ai_dialog.tab_suggestions"), Content = suggestionsTabRoot });

        var suggestionRows = new List<(CheckBox Box, AiSuggestionItem Item)>();

        async System.Threading.Tasks.Task ReloadStoredMetadataAsync()
        {
            try
            {
                var stored = await _api.GetAiMetadataAsync(mediaId);
                storedLabel.Text = stored.Count == 0
                    ? _tr.Tr("ai_dialog.no_stored_metadata")
                    : string.Join("\n", stored.Select(e => _tr.Tr("ai_dialog.stored_metadata_row", ("field", e.FieldName), ("value", e.FieldValue), ("model", (object?)e.ModelName ?? ""))));
            }
            catch (Exception) { storedLabel.Text = _tr.Tr("ai_dialog.no_stored_metadata"); }
        }

        generateBtn.Click += async (_, _) =>
        {
            suggestionsStatus.Text = _tr.Tr("ai_dialog.loading");
            suggestionsPanel.Children.Clear();
            suggestionRows.Clear();
            applySuggestionsBtn.IsEnabled = false;
            try
            {
                var suggestions = await _api.AiSuggestAsync(mediaId);
                if (suggestions.Count == 0)
                {
                    suggestionsStatus.Text = _tr.Tr("ai_dialog.no_suggestions");
                    return;
                }
                suggestionsStatus.Text = _tr.Tr("ai_dialog.suggestions_found", ("count", suggestions.Count.ToString()));
                foreach (var s in suggestions)
                {
                    var checkbox = new CheckBox
                    {
                        Content = _tr.Tr("ai_dialog.suggestion_row", ("field", s.FieldName), ("value", s.FieldValue), ("model", s.ModelName), ("confidence", $"{s.Confidence ?? 0:P0}")),
                        Margin = new Thickness(0, 2, 0, 2),
                    };
                    suggestionsPanel.Children.Add(checkbox);
                    suggestionRows.Add((checkbox, s));
                }
                applySuggestionsBtn.IsEnabled = true;
            }
            catch (Exception ex)
            {
                suggestionsStatus.Text = _tr.Tr("ai_dialog.generate_failed", ("error", ex.Message));
            }
        };

        applySuggestionsBtn.Click += async (_, _) =>
        {
            var accepted = suggestionRows.Where(r => r.Box.IsChecked == true).Select(r => r.Item).ToList();
            if (accepted.Count == 0)
            {
                MessageBox.Show(_tr.Tr("ai_dialog.nothing_selected_text"), _tr.Tr("ai_dialog.nothing_selected_title"));
                return;
            }
            if (MessageBox.Show(_tr.Tr("ai_dialog.confirm_apply_text", ("count", accepted.Count.ToString())),
                    _tr.Tr("ai_dialog.confirm_apply_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            var payload = accepted.Select(s => new AcceptedAiSuggestion(s.FieldName, s.FieldValue, s.ModelName, s.ModelVersion, s.Confidence, s.Prompt)).ToList();
            try
            {
                await _api.AiApplyAsync(mediaId, payload, true);
                changed = true;
                await ReloadStoredMetadataAsync();
                MessageBox.Show(_tr.Tr("ai_dialog.applied_text"), _tr.Tr("ai_dialog.applied_title"));
            }
            catch (Exception ex)
            {
                // Gap L (§37): Fehlerdialog mit Fehler-ID/Loesungshinweis wie
                // show_api_error() in der Python-Referenz.
                ShowApiError(ex, _tr.Tr("ai_dialog.apply_failed", ("error", ex.Message)));
            }
        };

        // --- Tab 2: KI-Musik (§27, nur fuer music/ai_music) -------------------
        if (AiMusicRelevantKinds.Contains(kind))
        {
            var musicTabRoot = new StackPanel { Margin = new Thickness(8) };
            musicTabRoot.Children.Add(new TextBlock { Text = _tr.Tr("ai_dialog.ai_music_info"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });
            var persistedLabel = new TextBlock { Text = _tr.Tr("ai_dialog.ai_music_not_set"), TextWrapping = TextWrapping.Wrap, Foreground = System.Windows.Media.Brushes.DarkSeaGreen, Margin = new Thickness(0, 0, 0, 8) };
            musicTabRoot.Children.Add(persistedLabel);

            var statusCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 4) };
            foreach (var v in AiStatusValues) statusCombo.Items.Add(new ComboBoxItem { Content = _tr.Tr($"ai_dialog.status_{v}"), Tag = v });
            statusCombo.SelectedIndex = 0;
            var sourceBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
            var modelBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
            var promptBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
            var styleBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
            var moodBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
            var ownerBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
            var artistBox = new TextBox { Margin = new Thickness(0, 0, 0, 8) };

            void AddField(string labelKey, UIElement field)
            {
                musicTabRoot.Children.Add(new TextBlock { Text = _tr.Tr(labelKey) });
                musicTabRoot.Children.Add(field);
            }
            AddField("ai_dialog.field_status", statusCombo);
            AddField("ai_dialog.field_source", sourceBox);
            AddField("ai_dialog.field_model", modelBox);
            AddField("ai_dialog.field_prompt", promptBox);
            AddField("ai_dialog.field_style", styleBox);
            AddField("ai_dialog.field_mood", moodBox);
            AddField("ai_dialog.field_owner", ownerBox);
            AddField("ai_dialog.field_artist_name", artistBox);

            var applyAiMusicBtn = new Button { Content = _tr.Tr("ai_dialog.apply_ai_music_button"), Padding = new Thickness(10, 4, 10, 4), HorizontalAlignment = HorizontalAlignment.Left };
            musicTabRoot.Children.Add(applyAiMusicBtn);

            async System.Threading.Tasks.Task LoadAiMusicAsync()
            {
                try
                {
                    var saved = await _api.GetAiMusicAsync(mediaId);
                    if (saved is null)
                    {
                        persistedLabel.Text = _tr.Tr("ai_dialog.ai_music_not_set");
                        return;
                    }
                    persistedLabel.Text = _tr.Tr("ai_dialog.ai_music_saved_summary", ("status", _tr.Tr($"ai_dialog.status_{saved.AiStatus}")));
                    var idx = Array.IndexOf(AiStatusValues, saved.AiStatus);
                    statusCombo.SelectedIndex = Math.Max(0, idx);
                    sourceBox.Text = saved.AiSource ?? "";
                    modelBox.Text = saved.AiModel ?? "";
                    promptBox.Text = saved.AiPrompt ?? "";
                    styleBox.Text = saved.AiStyle ?? "";
                    moodBox.Text = saved.AiMood ?? "";
                    ownerBox.Text = saved.AiOwner ?? "";
                    artistBox.Text = saved.ArtistNames.Count > 0 ? saved.ArtistNames[0] : "";
                }
                catch (Exception) { /* noch keine Angaben vorhanden - kein harter Fehler */ }
            }

            applyAiMusicBtn.Click += async (_, _) =>
            {
                if (MessageBox.Show(_tr.Tr("ai_dialog.confirm_ai_music_text"), _tr.Tr("ai_dialog.confirm_ai_music_title"),
                        MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                    return;
                var status = (string)((ComboBoxItem)statusCombo.SelectedItem).Tag;
                string? NullIfEmpty(string s) => string.IsNullOrWhiteSpace(s) ? null : s.Trim();
                try
                {
                    await _api.ApplyAiMusicAsync(mediaId, new AiMusicApplyRequest(
                        status, NullIfEmpty(sourceBox.Text), NullIfEmpty(modelBox.Text), NullIfEmpty(promptBox.Text),
                        null, null, NullIfEmpty(styleBox.Text), NullIfEmpty(moodBox.Text), NullIfEmpty(ownerBox.Text),
                        NullIfEmpty(artistBox.Text), true));
                    changed = true;
                    await LoadAiMusicAsync();
                    MessageBox.Show(_tr.Tr("ai_dialog.ai_music_applied_text"), _tr.Tr("ai_dialog.applied_title"));
                }
                catch (Exception ex)
                {
                    ShowApiError(ex, _tr.Tr("ai_dialog.apply_ai_music_failed", ("error", ex.Message)));
                }
            };

            tabs.Items.Add(new TabItem { Header = _tr.Tr("ai_dialog.tab_ai_music"), Content = musicTabRoot });
            _ = LoadAiMusicAsync();
        }

        async System.Threading.Tasks.Task LoadAiStatusAsync()
        {
            try
            {
                var status = await _api.GetAiStatusAsync();
                if (status is null) { statusBanner.Text = _tr.Tr("ai_dialog.status_load_failed", ("error", "keine Daten")); return; }
                if (!status.Enabled) statusBanner.Text = _tr.Tr("ai_dialog.status_disabled");
                else if (!status.Available) statusBanner.Text = _tr.Tr("ai_dialog.status_unavailable", ("provider", status.Provider));
                else statusBanner.Text = _tr.Tr("ai_dialog.status_active", ("provider", status.Provider), ("model", status.Model ?? ""));
            }
            catch (Exception ex)
            {
                statusBanner.Text = _tr.Tr("ai_dialog.status_load_failed", ("error", ex.Message));
            }
        }

        await LoadAiStatusAsync();
        await ReloadStoredMetadataAsync();
        dialog.ShowDialog();
        return changed;
    }
}
