using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using GenesisMediaManager.Client.Api;
using Microsoft.Win32;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Voice Studio
/// (nav.voice_studio/nav.tts, §28/§29, ADR-0018). Pendant zu
/// ui-reference-pyside/genesis_ui/views/voice_studio_view.py: zwei Tabs
/// (Profile, Text-zu-Sprache). Profile sind eine projektweite Ressource
/// (nicht an eine Mediendatei gebunden). Anlegen/Loeschen/Synthese sind
/// Aenderungen und erfordern eine explizite Bestaetigung; Loeschen
/// zusaetzlich die exakte Wiederholung des Profilnamens (§28/Prinzip #6
/// "Loeschen = extra confirm"). Keine Sprachdaten verlassen dabei jemals
/// automatisch den lokalen Rechner (§28/§56).
/// </summary>
public partial class MainWindow
{
    private static string YesNoStatic(bool? value, GenesisMediaManager.Client.I18n.Translator tr) => value switch
    {
        true => tr.Tr("common.value_yes"),
        false => tr.Tr("common.value_no"),
        _ => tr.Tr("voice_studio.unknown"),
    };

    private async Task ShowVoiceStudioAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("voice_studio.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        var statusBanner = new TextBlock { TextWrapping = TextWrapping.Wrap, Text = _tr.Tr("ai_dialog.loading"), Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(statusBanner);

        var tabs = new TabControl { MinHeight = 480 };
        root.Children.Add(tabs);

        var profiles = new List<VoiceProfileInfo>();
        var engineCatalog = new List<VoiceEngineInfo>();

        // --- Tab 1: Profile ----------------------------------------------------
        var profilesPanel = new StackPanel { Margin = new Thickness(8) };
        // CanUserSortColumns=false ist PFLICHT: deleteProfileBtn.Click
        // indiziert unten per profilesGrid.SelectedIndex in "profiles" -
        // sonst koennte bei aktiver Spaltensortierung das FALSCHE
        // Sprachprofil geloescht werden. Gefunden im Deep-Search, behoben.
        var profilesGrid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, MaxHeight = 220, Margin = new Thickness(0, 0, 0, 8), CanUserSortColumns = false };
        void PCol(string headerKey, string path, double width) =>
            profilesGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr(headerKey), Binding = new System.Windows.Data.Binding(path), Width = width });
        PCol("voice_studio.col_name", "Name", 160);
        PCol("voice_studio.col_engine", "Engine", 100);
        PCol("voice_studio.col_language", "Language", 90);
        PCol("voice_studio.col_license", "License", 120);
        PCol("voice_studio.col_offline", "Offline", 70);
        PCol("voice_studio.col_open_source", "OpenSource", 90);
        PCol("voice_studio.col_commercial", "Commercial", 90);
        profilesPanel.Children.Add(profilesGrid);

        var profileButtonRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var newProfileBtn = new Button { Content = _tr.Tr("voice_studio.new_profile_button"), Margin = new Thickness(0, 0, 8, 0) };
        var deleteProfileBtn = new Button { Content = _tr.Tr("voice_studio.delete_profile_button"), IsEnabled = false };
        profileButtonRow.Children.Add(newProfileBtn);
        profileButtonRow.Children.Add(deleteProfileBtn);
        profilesPanel.Children.Add(profileButtonRow);

        var newProfileGroup = new GroupBox { Header = _tr.Tr("voice_studio.new_profile_group_title"), Visibility = Visibility.Collapsed };
        var form = new StackPanel();
        var nameEdit = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
        var engineCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 4) };
        var modelPathEdit = new TextBox();
        var browseModelBtn = new Button { Content = _tr.Tr("voice_studio.browse_button"), Margin = new Thickness(4, 0, 0, 0) };
        var modelPathRow = new DockPanel { Margin = new Thickness(0, 0, 0, 4) };
        DockPanel.SetDock(browseModelBtn, Dock.Right);
        modelPathRow.Children.Add(browseModelBtn);
        modelPathRow.Children.Add(modelPathEdit);
        // Python setzt hier einen echten Platzhaltertext
        // (setPlaceholderText "de / en / ja / ru ..."); WPF-TextBoxen
        // kennen das nicht, daher die Haus-Konvention ToolTip
        // (vgl. MainWindow.Library.cs::searchBox).
        var languageEdit = new TextBox { Margin = new Thickness(0, 0, 0, 4), ToolTip = "de / en / ja / ru ..." };
        var descriptionEdit = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
        var licenseEdit = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
        var offlineCheck = new CheckBox { Content = _tr.Tr("voice_studio.field_offline_capable"), IsChecked = true, Margin = new Thickness(0, 0, 0, 4) };
        var openSourceCheck = new CheckBox { Content = _tr.Tr("voice_studio.field_open_source"), IsChecked = true, Margin = new Thickness(0, 0, 0, 4) };
        var commercialCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 4) };
        commercialCombo.Items.Add(_tr.Tr("voice_studio.unknown"));
        commercialCombo.Items.Add(_tr.Tr("common.value_yes"));
        commercialCombo.Items.Add(_tr.Tr("common.value_no"));
        commercialCombo.SelectedIndex = 0;
        var samplePathEdit = new TextBox();
        var browseSampleBtn = new Button { Content = _tr.Tr("voice_studio.browse_button"), Margin = new Thickness(4, 0, 0, 0) };
        var samplePathRow = new DockPanel { Margin = new Thickness(0, 0, 0, 4) };
        DockPanel.SetDock(browseSampleBtn, Dock.Right);
        samplePathRow.Children.Add(browseSampleBtn);
        samplePathRow.Children.Add(samplePathEdit);
        var engineNotesLabel = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = Brushes.SteelBlue, Margin = new Thickness(0, 0, 0, 4) };
        var createBtn = new Button { Content = _tr.Tr("voice_studio.create_button"), HorizontalAlignment = HorizontalAlignment.Left };

        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_name"), nameEdit));
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_engine"), engineCombo));
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_model_path"), modelPathRow));
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_language"), languageEdit));
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_description"), descriptionEdit));
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_model_license"), licenseEdit));
        form.Children.Add(offlineCheck);
        form.Children.Add(openSourceCheck);
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_commercial_use"), commercialCombo));
        form.Children.Add(BuildLabeledRow(_tr.Tr("voice_studio.field_sample_path"), samplePathRow));
        form.Children.Add(engineNotesLabel);
        form.Children.Add(createBtn);
        newProfileGroup.Content = form;
        profilesPanel.Children.Add(newProfileGroup);

        tabs.Items.Add(new TabItem { Header = _tr.Tr("voice_studio.tab_profiles"), Content = new ScrollViewer { Content = profilesPanel } });

        // --- Tab 2: Text-zu-Sprache ---------------------------------------------
        var ttsPanel = new StackPanel { Margin = new Thickness(8) };
        var profileRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 4) };
        profileRow.Children.Add(new TextBlock { Text = _tr.Tr("voice_studio.field_profile"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        var ttsProfileCombo = new ComboBox { Width = 260 };
        profileRow.Children.Add(ttsProfileCombo);
        ttsPanel.Children.Add(profileRow);

        var disclosureLabel = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = Brushes.SteelBlue, Margin = new Thickness(0, 0, 0, 4) };
        ttsPanel.Children.Add(disclosureLabel);

        var textEdit = new TextBox { AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, MinHeight = 100, Margin = new Thickness(0, 0, 0, 4) };
        textEdit.ToolTip = _tr.Tr("voice_studio.text_placeholder");
        ttsPanel.Children.Add(textEdit);

        var controlsRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 4) };
        controlsRow.Children.Add(new TextBlock { Text = _tr.Tr("voice_studio.field_export_format"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        var exportFormatCombo = new ComboBox { Width = 90, Margin = new Thickness(0, 0, 8, 0) };
        foreach (var fmt in new[] { "wav", "mp3", "flac" }) exportFormatCombo.Items.Add(fmt);
        exportFormatCombo.SelectedIndex = 0;
        var synthesizeBtn = new Button { Content = _tr.Tr("voice_studio.synthesize_button"), Margin = new Thickness(0, 0, 8, 0) };
        var testBtn = new Button { Content = _tr.Tr("voice_studio.test_button") };
        controlsRow.Children.Add(exportFormatCombo);
        controlsRow.Children.Add(synthesizeBtn);
        controlsRow.Children.Add(testBtn);
        ttsPanel.Children.Add(controlsRow);

        var synthesisStatus = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 4) };
        ttsPanel.Children.Add(synthesisStatus);

        var playbackRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 4) };
        var playBtn = new Button { Content = _tr.Tr("voice_studio.play_button"), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var pauseBtn = new Button { Content = _tr.Tr("voice_studio.pause_button") };
        playbackRow.Children.Add(playBtn);
        playbackRow.Children.Add(pauseBtn);
        ttsPanel.Children.Add(playbackRow);

        var player = new MediaElement { LoadedBehavior = MediaState.Manual, UnloadedBehavior = MediaState.Manual, Visibility = Visibility.Collapsed };
        player.Unloaded += (_, _) =>
        {
            // Ansicht verlassen (Navigation): Wiedergabe stoppen, damit nach
            // dem Seitenwechsel nichts unsichtbar im Hintergrund weiterspielt -
            // in der Python-Referenz stirbt der QMediaPlayer mit der Ansicht,
            // hier muss das MediaElement explizit gestoppt werden
            // (gleiches Idiom wie MediaElement in MainWindow.xaml.cs).
            player.Stop();
        };
        ttsPanel.Children.Add(player);

        ttsPanel.Children.Add(new TextBlock { Text = _tr.Tr("voice_studio.history_title"), Margin = new Thickness(0, 4, 0, 4), FontWeight = FontWeights.SemiBold });
        // CanUserSortColumns=false ist PFLICHT: die "Abspielen/Oeffnen"-
        // Aktion indiziert unten per historyGrid.SelectedIndex in "history" -
        // sonst koennte bei aktiver Spaltensortierung die FALSCHE
        // Synthese-Ausgabedatei geoeffnet werden. Gefunden im Deep-Search,
        // behoben.
        var historyGrid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, MaxHeight = 220, CanUserSortColumns = false };
        historyGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("voice_studio.col_created_at"), Binding = new System.Windows.Data.Binding("CreatedAt"), Width = 150 });
        historyGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("voice_studio.col_text"), Binding = new System.Windows.Data.Binding("TextPreview"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        historyGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("voice_studio.col_format"), Binding = new System.Windows.Data.Binding("ExportFormat"), Width = 70 });
        historyGrid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("voice_studio.col_duration"), Binding = new System.Windows.Data.Binding("DurationText"), Width = 80 });
        ttsPanel.Children.Add(historyGrid);

        tabs.Items.Add(new TabItem { Header = _tr.Tr("voice_studio.tab_tts"), Content = new ScrollViewer { Content = ttsPanel } });

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        string? lastOutputPath = null;
        List<VoiceSynthesisInfo> history = new();

        // --- Status/Engine-Katalog laden -----------------------------------
        try
        {
            var status = await _api.GetVoiceStatusAsync();
            statusBanner.Text = status is null || !status.Enabled
                ? _tr.Tr("voice_studio.status_disabled")
                : !status.Available
                    ? _tr.Tr("voice_studio.status_unavailable", ("provider", status.Provider))
                    : _tr.Tr("voice_studio.status_active", ("provider", status.Provider));
        }
        catch (Exception ex)
        {
            statusBanner.Text = _tr.Tr("ai_dialog.status_load_failed", ("error", ex.Message));
        }

        try
        {
            engineCatalog = await _api.ListVoiceEnginesAsync();
        }
        catch (Exception)
        {
            engineCatalog = new List<VoiceEngineInfo>();
        }
        foreach (var e in engineCatalog) engineCombo.Items.Add(e.Label);
        if (engineCombo.Items.Count > 0) engineCombo.SelectedIndex = 0;

        void UpdateEngineNotes()
        {
            var idx = engineCombo.SelectedIndex;
            if (idx < 0 || idx >= engineCatalog.Count) { engineNotesLabel.Text = string.Empty; return; }
            var entry = engineCatalog[idx];
            engineNotesLabel.Text = _tr.Tr(
                "voice_studio.engine_notes", ("license", entry.SuggestedEngineLicense ?? "-"), ("notes", entry.Notes ?? "-"));
        }
        engineCombo.SelectionChanged += (_, _) => UpdateEngineNotes();
        UpdateEngineNotes();

        async Task ReloadHistoryAsync()
        {
            historyGrid.ItemsSource = null;
            if (ttsProfileCombo.SelectedIndex < 0 || ttsProfileCombo.SelectedIndex >= profiles.Count) return;
            var profileId = profiles[ttsProfileCombo.SelectedIndex].Id;
            try
            {
                history = await _api.ListVoiceSynthesesAsync(profileId);
            }
            catch (Exception)
            {
                history = new List<VoiceSynthesisInfo>();
            }
            historyGrid.ItemsSource = history.Select(r => new
            {
                // Beide Zellen in VoiceStudioSupport (Paritaet zu
                // _reload_history in voice_studio_view.py +
                // InvariantCulture, damit unter de-DE nicht "3,5s"
                // statt "3.5s" angezeigt wird).
                CreatedAt = VoiceStudioSupport.FormatHistoryCreatedAt(r.CreatedAt),
                TextPreview = r.Text.Length <= 60 ? r.Text : r.Text[..57] + "...",
                r.ExportFormat,
                DurationText = VoiceStudioSupport.FormatHistoryDuration(r.DurationSeconds),
            }).ToList();
        }

        void UpdateDisclosure()
        {
            if (ttsProfileCombo.SelectedIndex < 0 || ttsProfileCombo.SelectedIndex >= profiles.Count)
            {
                disclosureLabel.Text = string.Empty;
                return;
            }
            var p = profiles[ttsProfileCombo.SelectedIndex];
            disclosureLabel.Text = _tr.Tr(
                "voice_studio.profile_disclosure",
                ("engine", p.Engine), ("license", DownloadCenterSupport.OrFallback(p.ModelLicense, _tr.Tr("voice_studio.unknown"))),
                ("offline", YesNoStatic(p.OfflineCapable, _tr)), ("open_source", YesNoStatic(p.OpenSource, _tr)),
                ("commercial", YesNoStatic(p.CommercialUseAllowed, _tr)));
        }

        ttsProfileCombo.SelectionChanged += async (_, _) => { UpdateDisclosure(); await ReloadHistoryAsync(); };

        async Task ReloadProfilesAsync()
        {
            try
            {
                profiles = await _api.ListVoiceProfilesAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("voice_studio.load_profiles_failed", ("error", ex.Message)));
                profiles = new List<VoiceProfileInfo>();
            }
            profilesGrid.ItemsSource = profiles.Select(p => new
            {
                // OrFallback statt ?? - Python nutzt hier "or" (leerer
                // String wird ebenfalls zu "-", Zeilen 319-320 der Referenz).
                p.Name, p.Engine, Language = DownloadCenterSupport.OrFallback(p.Language, "-"),
                License = DownloadCenterSupport.OrFallback(p.ModelLicense, "-"),
                Offline = YesNoStatic(p.OfflineCapable, _tr), OpenSource = YesNoStatic(p.OpenSource, _tr),
                Commercial = YesNoStatic(p.CommercialUseAllowed, _tr),
            }).ToList();

            var previousId = ttsProfileCombo.SelectedIndex >= 0 && ttsProfileCombo.SelectedIndex < profiles.Count
                ? (int?)profiles[ttsProfileCombo.SelectedIndex].Id : null;
            ttsProfileCombo.Items.Clear();
            foreach (var p in profiles) ttsProfileCombo.Items.Add(p.Name);
            var restoreIndex = previousId is null ? -1 : profiles.FindIndex(p => p.Id == previousId);
            ttsProfileCombo.SelectedIndex = restoreIndex >= 0 ? restoreIndex : (profiles.Count > 0 ? 0 : -1);
            UpdateDisclosure();
            await ReloadHistoryAsync();
        }

        newProfileBtn.Click += (_, _) =>
        {
            newProfileGroup.Visibility = newProfileGroup.Visibility == Visibility.Visible ? Visibility.Collapsed : Visibility.Visible;
        };

        browseModelBtn.Click += (_, _) =>
        {
            var dlg = new OpenFileDialog { Title = _tr.Tr("voice_studio.browse_model_title") };
            if (dlg.ShowDialog() == true) modelPathEdit.Text = dlg.FileName;
        };
        browseSampleBtn.Click += (_, _) =>
        {
            var dlg = new OpenFileDialog { Title = _tr.Tr("voice_studio.browse_sample_title") };
            if (dlg.ShowDialog() == true) samplePathEdit.Text = dlg.FileName;
        };

        createBtn.Click += async (_, _) =>
        {
            var name = nameEdit.Text.Trim();
            if (name.Length == 0)
            {
                MessageBox.Show(_tr.Tr("voice_studio.name_required"), _tr.Tr("common.error_title"));
                return;
            }
            var engineId = engineCombo.SelectedIndex >= 0 && engineCombo.SelectedIndex < engineCatalog.Count
                ? engineCatalog[engineCombo.SelectedIndex].Id : "piper";
            bool? commercial = commercialCombo.SelectedIndex switch { 1 => true, 2 => false, _ => null };

            var confirmResult = MessageBox.Show(
                _tr.Tr(
                    "voice_studio.confirm_create_text", ("name", name), ("engine", engineId),
                    ("license", string.IsNullOrWhiteSpace(licenseEdit.Text) ? _tr.Tr("voice_studio.unknown") : licenseEdit.Text.Trim()),
                    ("offline", YesNoStatic(offlineCheck.IsChecked, _tr)), ("open_source", YesNoStatic(openSourceCheck.IsChecked, _tr)),
                    ("commercial", YesNoStatic(commercial, _tr))),
                _tr.Tr("voice_studio.confirm_create_title"), MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No);
            if (confirmResult != MessageBoxResult.Yes) return;

            try
            {
                await _api.CreateVoiceProfileAsync(new CreateVoiceProfileRequest(
                    name, engineId,
                    string.IsNullOrWhiteSpace(modelPathEdit.Text) ? null : modelPathEdit.Text.Trim(),
                    string.IsNullOrWhiteSpace(languageEdit.Text) ? null : languageEdit.Text.Trim(),
                    string.IsNullOrWhiteSpace(descriptionEdit.Text) ? null : descriptionEdit.Text.Trim(),
                    string.IsNullOrWhiteSpace(licenseEdit.Text) ? null : licenseEdit.Text.Trim(),
                    offlineCheck.IsChecked, openSourceCheck.IsChecked, commercial,
                    string.IsNullOrWhiteSpace(samplePathEdit.Text) ? null : samplePathEdit.Text.Trim(), true));
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("voice_studio.create_failed", ("error", ex.Message)));
                return;
            }

            nameEdit.Clear(); modelPathEdit.Clear(); languageEdit.Clear(); descriptionEdit.Clear();
            licenseEdit.Clear(); samplePathEdit.Clear();
            newProfileGroup.Visibility = Visibility.Collapsed;
            await ReloadProfilesAsync();
        };

        profilesGrid.SelectionChanged += (_, _) => deleteProfileBtn.IsEnabled = profilesGrid.SelectedIndex >= 0;

        deleteProfileBtn.Click += async (_, _) =>
        {
            if (profilesGrid.SelectedIndex < 0 || profilesGrid.SelectedIndex >= profiles.Count) return;
            var profile = profiles[profilesGrid.SelectedIndex];
            var confirmResult = MessageBox.Show(
                _tr.Tr("voice_studio.confirm_delete_text", ("name", profile.Name)),
                _tr.Tr("voice_studio.confirm_delete_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No);
            if (confirmResult != MessageBoxResult.Yes) return;

            var typedName = PromptForText(
                _tr.Tr("voice_studio.confirm_delete_name_title"),
                _tr.Tr("voice_studio.confirm_delete_name_prompt", ("name", profile.Name)));
            if (typedName is null) return;
            if (typedName != profile.Name)
            {
                MessageBox.Show(_tr.Tr("voice_studio.delete_name_mismatch"), _tr.Tr("common.error_title"));
                return;
            }

            try
            {
                await _api.DeleteVoiceProfileAsync(profile.Id, typedName);
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("voice_studio.delete_failed", ("error", ex.Message)));
                return;
            }
            await ReloadProfilesAsync();
        };

        async Task RunSynthesisAsync(bool isTest)
        {
            if (ttsProfileCombo.SelectedIndex < 0 || ttsProfileCombo.SelectedIndex >= profiles.Count)
            {
                MessageBox.Show(_tr.Tr("voice_studio.no_profile_selected"), _tr.Tr("common.error_title"));
                return;
            }
            var confirmResult = MessageBox.Show(
                _tr.Tr("voice_studio.confirm_synthesize_text"), _tr.Tr("voice_studio.confirm_synthesize_title"),
                MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No);
            if (confirmResult != MessageBoxResult.Yes) return;

            var profileId = profiles[ttsProfileCombo.SelectedIndex].Id;
            synthesisStatus.Text = _tr.Tr("voice_studio.synthesizing");
            try
            {
                var result = isTest
                    ? await _api.TestVoiceProfileAsync(profileId)
                    : await _api.SynthesizeVoiceAsync(profileId, textEdit.Text.Trim(), (string)exportFormatCombo.SelectedItem);
                if (result?.Synthesis is not null)
                {
                    lastOutputPath = result.Synthesis.OutputPath;
                    playBtn.IsEnabled = true;
                    synthesisStatus.Text = _tr.Tr(
                        "voice_studio.synthesize_done",
                        ("duration", result.Synthesis.DurationSeconds ?? 0.0), ("path", result.Synthesis.OutputPath));
                }
                await ReloadHistoryAsync();
            }
            catch (Exception ex)
            {
                synthesisStatus.Text = _tr.Tr("voice_studio.synthesize_failed", ("error", ex.Message));
            }
        }

        synthesizeBtn.Click += async (_, _) =>
        {
            if (textEdit.Text.Trim().Length == 0)
            {
                MessageBox.Show(_tr.Tr("voice_studio.text_required"), _tr.Tr("common.error_title"));
                return;
            }
            await RunSynthesisAsync(false);
        };
        testBtn.Click += async (_, _) => await RunSynthesisAsync(true);

        historyGrid.SelectionChanged += (_, _) =>
        {
            if (historyGrid.SelectedIndex >= 0 && historyGrid.SelectedIndex < history.Count)
            {
                lastOutputPath = history[historyGrid.SelectedIndex].OutputPath;
                playBtn.IsEnabled = true;
            }
        };

        playBtn.Click += (_, _) =>
        {
            if (string.IsNullOrEmpty(lastOutputPath) || !File.Exists(lastOutputPath)) return;
            player.Source = new Uri(lastOutputPath);
            player.Play();
        };
        pauseBtn.Click += (_, _) => player.Pause();

        await ReloadProfilesAsync();
    }

    /// <summary>Einfacher Texteingabe-Dialog (Pendant zu Qts QInputDialog.getText,
    /// §28 "Loeschen = exakte Namenswiederholung"). Liefert <c>null</c>
    /// bei Abbruch, sonst den eingegebenen (ggf. leeren) Text.</summary>
    private string? PromptForText(string title, string prompt, string initialText = "")
    {
        var window = new Window
        {
            Title = title, Width = 420, Height = 160, WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Owner = this, ResizeMode = ResizeMode.NoResize,
        };
        var panel = new StackPanel { Margin = new Thickness(16) };
        panel.Children.Add(new TextBlock { Text = prompt, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });
        var input = new TextBox { Text = initialText };
        panel.Children.Add(input);
        var buttonRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 12, 0, 0) };
        var okBtn = new Button { Content = _tr.Tr("common.button_ok"), Width = 80, Margin = new Thickness(0, 0, 8, 0), IsDefault = true };
        var cancelBtn = new Button { Content = _tr.Tr("common.button_cancel"), Width = 80, IsCancel = true };
        buttonRow.Children.Add(okBtn);
        buttonRow.Children.Add(cancelBtn);
        panel.Children.Add(buttonRow);
        window.Content = panel;

        string? result = null;
        okBtn.Click += (_, _) => { result = input.Text; window.DialogResult = true; };
        cancelBtn.Click += (_, _) => window.DialogResult = false;
        return window.ShowDialog() == true ? result : null;
    }
}
