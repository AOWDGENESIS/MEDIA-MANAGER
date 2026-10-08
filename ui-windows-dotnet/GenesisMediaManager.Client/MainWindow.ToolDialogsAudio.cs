using System;
using System.Globalization;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, achter inkrementeller Schritt - Pendants zu
/// ui-reference-pyside/genesis_ui/dialogs/{loudness,cutter,convert}_dialog.py
/// (§18/§19, ADR-0010/ADR-0011, Phase 3). Alle drei folgen demselben Muster
/// Erkennen/Messen -> automatische Vorschau (rein lesend/berechnend, erzeugt
/// KEINE Datei) -> explizite Nutzerbestaetigung -> Anwenden (erzeugt eine
/// NEUE Datei, das Original bleibt immer unveraendert) - Prinzip #4/#5/#17,
/// §44.
/// </summary>
public partial class MainWindow
{
    private static string Fmt(double value, string format = "F1") => value.ToString(format, CultureInfo.InvariantCulture);

    // --- Lautheit/Normalisierung (Pendant zu LoudnessDialog, §19) -----------
    private async System.Threading.Tasks.Task<bool> ShowLoudnessDialogAsync(int mediaId, string filename)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("loudness_dialog.window_title", ("filename", filename)), Width = 560, Height = 600,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var outer = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        outer.Content = root;
        dialog.Content = outer;

        var statusLabel = new TextBlock { Text = _tr.Tr("loudness_dialog.analyzing"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(statusLabel);

        var analyzeBtn = new Button { Content = _tr.Tr("loudness_dialog.analyze_button"), Padding = new Thickness(10, 4, 10, 4), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(analyzeBtn);

        var targetLufsBox = new TextBox { Margin = new Thickness(0, 0, 0, 4) };
        var targetTpBox = new TextBox { Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(new TextBlock { Text = _tr.Tr("loudness_dialog.target_lufs_label") });
        root.Children.Add(targetLufsBox);
        root.Children.Add(new TextBlock { Text = _tr.Tr("loudness_dialog.target_true_peak_label") });
        root.Children.Add(targetTpBox);

        var previewBtn = new Button { Content = _tr.Tr("loudness_dialog.preview_button"), Padding = new Thickness(10, 4, 10, 4), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(previewBtn);

        var planLabel = new TextBlock { Text = _tr.Tr("loudness_dialog.no_preview_yet"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(planLabel);

        var warningLabel = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = System.Windows.Media.Brushes.DarkOrange, Visibility = Visibility.Collapsed, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(warningLabel);

        root.Children.Add(new TextBlock { Text = _tr.Tr("loudness_dialog.history_label"), Margin = new Thickness(0, 4, 0, 4) });
        var historyList = new ListBox { Height = 140, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(historyList);

        var btnRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var applyBtn = new Button { Content = _tr.Tr("loudness_dialog.apply_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var closeBtn = new Button { Content = _tr.Tr("loudness_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        btnRow.Children.Add(applyBtn);
        btnRow.Children.Add(closeBtn);
        root.Children.Add(btnRow);

        bool targetsInitialized = false;
        bool normalizationSupported = true;
        NormalizationPlan? currentPlan = null;
        bool changed = false;

        async System.Threading.Tasks.Task ReloadHistoryAsync()
        {
            historyList.Items.Clear();
            try
            {
                var rows = await _api.ListLoudnessAsync(mediaId);
                foreach (var row in rows)
                {
                    var date = (row.MeasuredAt ?? "").Length >= 19 ? row.MeasuredAt!.Substring(0, 19).Replace('T', ' ') : row.MeasuredAt ?? "";
                    string text = row.Normalized
                        ? _tr.Tr("loudness_dialog.history_row_normalized", ("date", date), ("lufs", Fmt(row.IntegratedLufs ?? 0)), ("peak", Fmt(row.TruePeakDbtp ?? 0)), ("path", row.NormalizedOutputPath ?? ""))
                        : _tr.Tr("loudness_dialog.history_row_measured", ("date", date), ("lufs", Fmt(row.IntegratedLufs ?? 0)), ("peak", Fmt(row.TruePeakDbtp ?? 0)));
                    historyList.Items.Add(text);
                }
            }
            catch (Exception) { /* Verlauf bleibt leer - kein harter Fehler (Prinzip #16) */ }
        }

        async System.Threading.Tasks.Task RunPreviewAsync()
        {
            double? targetLufs = targetsInitialized && double.TryParse(targetLufsBox.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out var l) ? l : null;
            double? targetTp = targetsInitialized && double.TryParse(targetTpBox.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out var t) ? t : null;
            try
            {
                var plan = await _api.PreviewLoudnessNormalizationAsync(mediaId, new LoudnessNormalizePreviewRequest(targetLufs, targetTp));
                if (plan is null) return;
                currentPlan = plan;
                if (!targetsInitialized)
                {
                    targetLufsBox.Text = Fmt(plan.TargetLufs);
                    targetTpBox.Text = Fmt(plan.TargetTruePeakDbtp);
                    targetsInitialized = true;
                }
                var text = _tr.Tr("loudness_dialog.plan_summary",
                    ("gain", (plan.PlannedGainDb >= 0 ? "+" : "") + Fmt(plan.PlannedGainDb, "F2")),
                    ("target_lufs", Fmt(plan.TargetLufs)), ("target_tp", Fmt(plan.TargetTruePeakDbtp)),
                    ("predicted_tp", Fmt(plan.PredictedOutputTruePeakDbtp)), ("output_path", plan.OutputPath))
                    + "\n" + plan.OutputFormatNote;
                if (plan.WillLikelyAlterDynamics)
                {
                    warningLabel.Text = _tr.Tr("loudness_dialog.dynamics_warning");
                    warningLabel.Visibility = Visibility.Visible;
                }
                else
                {
                    warningLabel.Visibility = Visibility.Collapsed;
                }
                if (plan.HasConflict)
                {
                    text += "\n\n" + _tr.Tr("loudness_dialog.conflict_warning");
                    applyBtn.IsEnabled = false;
                }
                else
                {
                    applyBtn.IsEnabled = normalizationSupported;
                }
                planLabel.Text = text;
            }
            catch (Exception ex)
            {
                if (ex.Message.Contains("nicht unterst", StringComparison.OrdinalIgnoreCase))
                {
                    normalizationSupported = false;
                    planLabel.Text = _tr.Tr("loudness_dialog.unsupported_kind");
                    targetLufsBox.IsEnabled = targetTpBox.IsEnabled = previewBtn.IsEnabled = applyBtn.IsEnabled = false;
                }
                else
                {
                    planLabel.Text = _tr.Tr("loudness_dialog.preview_failed", ("error", ex.Message));
                }
            }
        }

        async System.Threading.Tasks.Task RunAnalysisAsync()
        {
            try
            {
                var measurement = await _api.AnalyzeLoudnessAsync(mediaId);
                if (measurement is null) return;
                statusLabel.Text = _tr.Tr("loudness_dialog.measured_label",
                    ("lufs", Fmt(measurement.IntegratedLufs ?? 0)), ("peak", Fmt(measurement.TruePeakDbtp ?? 0)),
                    ("lra", Fmt(measurement.LoudnessRangeLu ?? 0)));
            }
            catch (Exception ex)
            {
                statusLabel.Text = _tr.Tr("loudness_dialog.analyze_failed", ("error", ex.Message));
                return;
            }
            await ReloadHistoryAsync();
            await RunPreviewAsync();
        }

        analyzeBtn.Click += async (_, _) => await RunAnalysisAsync();
        previewBtn.Click += async (_, _) => await RunPreviewAsync();
        closeBtn.Click += (_, _) => dialog.Close();
        applyBtn.Click += async (_, _) =>
        {
            if (currentPlan is null) return;
            if (MessageBox.Show(_tr.Tr("loudness_dialog.confirm_text", ("output_path", currentPlan.OutputPath)),
                    _tr.Tr("loudness_dialog.confirm_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                var result = await _api.ApplyLoudnessNormalizationAsync(mediaId,
                    new LoudnessNormalizeApplyRequest(currentPlan.TargetLufs, currentPlan.TargetTruePeakDbtp, currentPlan.TargetLra, true));
                if (result is null) return;
                changed = true;
                MessageBox.Show(_tr.Tr("loudness_dialog.done_text",
                    ("lufs", Fmt(result.AchievedIntegratedLufs)), ("peak", Fmt(result.AchievedTruePeakDbtp)), ("output_path", result.OutputPath)),
                    _tr.Tr("loudness_dialog.done_title"));
                await ReloadHistoryAsync();
                await RunPreviewAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("loudness_dialog.apply_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        await RunAnalysisAsync();
        dialog.ShowDialog();
        return changed;
    }

    // --- Audio-Cutter (Pendant zu CutterDialog, §18) ------------------------
    private async System.Threading.Tasks.Task<bool> ShowCutterDialogAsync(int mediaId, string filename, string absolutePath)
    {
        double? knownDuration = null;
        try
        {
            var detail = await _api.GetMediaDetailAsync(mediaId);
            knownDuration = detail?.Technical?.DurationSeconds;
        }
        catch (Exception) { /* Dauer bleibt unbekannt - keine harte Vorbedingung (Prinzip #16) */ }

        var dialog = new Window
        {
            Title = _tr.Tr("cutter_dialog.window_title", ("filename", filename)), Width = 680, Height = 700,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var outer = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        outer.Content = root;
        dialog.Content = outer;

        var waveformImage = new Image { Height = 140, Stretch = System.Windows.Media.Stretch.Fill };
        var waveformText = new TextBlock { Text = _tr.Tr("cutter_dialog.loading_waveform"), Height = 140, Background = System.Windows.Media.Brushes.Black, Foreground = System.Windows.Media.Brushes.White, TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
        var waveformGrid = new Grid { Margin = new Thickness(0, 0, 0, 8) };
        waveformGrid.Children.Add(waveformText);
        waveformGrid.Children.Add(waveformImage);
        root.Children.Add(waveformGrid);

        var player = new MediaElement { LoadedBehavior = MediaState.Manual, UnloadedBehavior = MediaState.Manual, Source = new Uri(absolutePath), Height = 0, Visibility = Visibility.Collapsed };
        root.Children.Add(player);

        var playbackRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var playBtn = new Button { Content = _tr.Tr("cutter_dialog.play_button"), Padding = new Thickness(8, 4, 8, 4), Margin = new Thickness(0, 0, 4, 0) };
        var pauseBtn = new Button { Content = _tr.Tr("cutter_dialog.pause_button"), Padding = new Thickness(8, 4, 8, 4), Margin = new Thickness(0, 0, 4, 0) };
        var playSelectionBtn = new Button { Content = _tr.Tr("cutter_dialog.play_selection_button"), Padding = new Thickness(8, 4, 8, 4) };
        playbackRow.Children.Add(playBtn);
        playbackRow.Children.Add(pauseBtn);
        playbackRow.Children.Add(playSelectionBtn);
        root.Children.Add(playbackRow);

        var safeDuration = knownDuration is { } d && d > 0.1 ? d - 0.1 : (double?)null;
        var startBox = new TextBox { Text = "0", Margin = new Thickness(0, 0, 0, 4) };
        var endBox = new TextBox { Text = Fmt(safeDuration ?? 10.0, "F2"), Margin = new Thickness(0, 0, 0, 4) };
        var fadeInBox = new TextBox { Text = "0", Margin = new Thickness(0, 0, 0, 4) };
        var fadeOutBox = new TextBox { Text = "0", Margin = new Thickness(0, 0, 0, 4) };
        var formatCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 8) };
        foreach (var f in new[] { "mp3", "wav", "flac" }) formatCombo.Items.Add(f);
        formatCombo.SelectedIndex = 0;

        root.Children.Add(new TextBlock { Text = _tr.Tr("cutter_dialog.start_label") });
        root.Children.Add(startBox);
        root.Children.Add(new TextBlock { Text = _tr.Tr("cutter_dialog.end_label") });
        root.Children.Add(endBox);
        root.Children.Add(new TextBlock { Text = _tr.Tr("cutter_dialog.fade_in_label") });
        root.Children.Add(fadeInBox);
        root.Children.Add(new TextBlock { Text = _tr.Tr("cutter_dialog.fade_out_label") });
        root.Children.Add(fadeOutBox);
        root.Children.Add(new TextBlock { Text = _tr.Tr("cutter_dialog.format_label") });
        root.Children.Add(formatCombo);

        var planLabel = new TextBlock { Text = _tr.Tr("cutter_dialog.no_preview_yet"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(planLabel);

        root.Children.Add(new TextBlock { Text = _tr.Tr("cutter_dialog.history_label"), Margin = new Thickness(0, 4, 0, 4) });
        var historyList = new ListBox { Height = 120, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(historyList);

        var btnRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var applyBtn = new Button { Content = _tr.Tr("cutter_dialog.apply_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var closeBtn = new Button { Content = _tr.Tr("cutter_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        btnRow.Children.Add(applyBtn);
        btnRow.Children.Add(closeBtn);
        root.Children.Add(btnRow);

        CutPlan? currentPlan = null;
        bool changed = false;

        double ParseD(TextBox box, double fallback) =>
            double.TryParse(box.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : fallback;

        async System.Threading.Tasks.Task LoadWaveformAsync()
        {
            try
            {
                var data = await _api.GetCutterWaveformAsync(mediaId);
                if (data is null) { waveformText.Text = _tr.Tr("cutter_dialog.waveform_failed", ("error", "keine Daten")); return; }
                var bitmap = new BitmapImage();
                using var stream = new MemoryStream(data);
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.StreamSource = stream;
                bitmap.EndInit();
                bitmap.Freeze();
                waveformImage.Source = bitmap;
                waveformText.Visibility = Visibility.Collapsed;
            }
            catch (Exception ex)
            {
                waveformText.Text = _tr.Tr("cutter_dialog.waveform_failed", ("error", ex.Message));
            }
        }

        async System.Threading.Tasks.Task ReloadHistoryAsync()
        {
            historyList.Items.Clear();
            try
            {
                var rows = await _api.ListCutsAsync(mediaId);
                foreach (var row in rows)
                {
                    var date = (row.CreatedAt ?? "").Length >= 19 ? row.CreatedAt!.Substring(0, 19).Replace('T', ' ') : row.CreatedAt ?? "";
                    historyList.Items.Add(_tr.Tr("cutter_dialog.history_row", ("date", date), ("start", Fmt(row.StartSeconds, "F2")), ("end", Fmt(row.EndSeconds, "F2")), ("format", row.ExportFormat), ("path", row.OutputPath)));
                }
            }
            catch (Exception) { }
        }

        async System.Threading.Tasks.Task RunPreviewAsync()
        {
            try
            {
                var plan = await _api.PreviewCutAsync(mediaId, new CutPreviewRequest(
                    ParseD(startBox, 0), ParseD(endBox, 1), (string)formatCombo.SelectedItem, ParseD(fadeInBox, 0), ParseD(fadeOutBox, 0)));
                if (plan is null) return;
                currentPlan = plan;
                var text = _tr.Tr("cutter_dialog.plan_summary", ("duration", Fmt(plan.SelectionDurationSeconds, "F2")), ("format", plan.ExportFormat), ("output_path", plan.OutputPath))
                    + (plan.IsLossyExport ? "\n" + _tr.Tr("cutter_dialog.lossy_note") : "");
                if (plan.HasConflict)
                {
                    text += "\n\n" + _tr.Tr("cutter_dialog.conflict_warning");
                    applyBtn.IsEnabled = false;
                }
                else
                {
                    applyBtn.IsEnabled = true;
                }
                planLabel.Text = text;
            }
            catch (Exception ex)
            {
                currentPlan = null;
                planLabel.Text = _tr.Tr("cutter_dialog.preview_failed", ("error", ex.Message));
                applyBtn.IsEnabled = false;
            }
        }

        startBox.TextChanged += async (_, _) => await RunPreviewAsync();
        endBox.TextChanged += async (_, _) => await RunPreviewAsync();
        fadeInBox.TextChanged += async (_, _) => await RunPreviewAsync();
        fadeOutBox.TextChanged += async (_, _) => await RunPreviewAsync();
        formatCombo.SelectionChanged += async (_, _) => await RunPreviewAsync();

        playBtn.Click += (_, _) => { player.Position = TimeSpan.FromSeconds(ParseD(startBox, 0)); player.Play(); };
        pauseBtn.Click += (_, _) => player.Pause();
        playSelectionBtn.Click += (_, _) =>
        {
            player.Position = TimeSpan.FromSeconds(ParseD(startBox, 0));
            player.Play();
            var endSeconds = ParseD(endBox, 1);
            var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(100) };
            timer.Tick += (_, _) =>
            {
                if (player.Position.TotalSeconds >= endSeconds)
                {
                    player.Pause();
                    timer.Stop();
                }
            };
            timer.Start();
        };

        closeBtn.Click += (_, _) => { player.Stop(); dialog.Close(); };
        dialog.Closing += (_, _) => player.Stop();

        applyBtn.Click += async (_, _) =>
        {
            if (currentPlan is null) return;
            if (MessageBox.Show(_tr.Tr("cutter_dialog.confirm_text", ("output_path", currentPlan.OutputPath)),
                    _tr.Tr("cutter_dialog.confirm_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                var result = await _api.ApplyCutAsync(mediaId, new CutApplyRequest(
                    currentPlan.StartSeconds, currentPlan.EndSeconds, currentPlan.ExportFormat,
                    currentPlan.FadeInSeconds, currentPlan.FadeOutSeconds, true));
                if (result is null) return;
                changed = true;
                MessageBox.Show(_tr.Tr("cutter_dialog.done_text", ("output_path", result.OutputPath)), _tr.Tr("cutter_dialog.done_title"));
                await ReloadHistoryAsync();
                await RunPreviewAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("cutter_dialog.apply_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        await LoadWaveformAsync();
        await ReloadHistoryAsync();
        await RunPreviewAsync();
        dialog.ShowDialog();
        return changed;
    }

    // --- Konvertierung (Pendant zu ConvertDialog) ---------------------------
    private async System.Threading.Tasks.Task<bool> ShowConvertDialogAsync(int mediaId, string filename)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("convert_dialog.window_title", ("filename", filename)), Width = 560, Height = 600,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var outer = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        outer.Content = root;
        dialog.Content = outer;

        root.Children.Add(new TextBlock { Text = _tr.Tr("convert_dialog.format_label") });
        var formatCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 8) };
        foreach (var f in new[] { "mp3", "wav", "flac", "ogg", "opus", "m4a", "aac" }) formatCombo.Items.Add(f);
        formatCombo.SelectedIndex = 0;
        root.Children.Add(formatCombo);

        var bitrateRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        var bitrateCheck = new CheckBox { Content = _tr.Tr("convert_dialog.custom_bitrate_checkbox"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) };
        var bitrateBox = new TextBox { Text = "192", Width = 80, IsEnabled = false };
        bitrateRow.Children.Add(bitrateCheck);
        bitrateRow.Children.Add(bitrateBox);
        root.Children.Add(new TextBlock { Text = _tr.Tr("convert_dialog.bitrate_label") });
        root.Children.Add(bitrateRow);

        var planLabel = new TextBlock { Text = _tr.Tr("convert_dialog.no_preview_yet"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(planLabel);

        root.Children.Add(new TextBlock { Text = _tr.Tr("convert_dialog.history_label"), Margin = new Thickness(0, 4, 0, 4) });
        var historyList = new ListBox { Height = 140, Margin = new Thickness(0, 0, 0, 8) };
        root.Children.Add(historyList);

        var btnRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var applyBtn = new Button { Content = _tr.Tr("convert_dialog.apply_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var closeBtn = new Button { Content = _tr.Tr("convert_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        btnRow.Children.Add(applyBtn);
        btnRow.Children.Add(closeBtn);
        root.Children.Add(btnRow);

        ConversionPlan? currentPlan = null;
        bool changed = false;

        async System.Threading.Tasks.Task ReloadHistoryAsync()
        {
            historyList.Items.Clear();
            try
            {
                var rows = await _api.ListConversionsAsync(mediaId);
                foreach (var row in rows)
                {
                    var date = (row.CreatedAt ?? "").Length >= 19 ? row.CreatedAt!.Substring(0, 19).Replace('T', ' ') : row.CreatedAt ?? "";
                    var bitrateText = row.BitrateKbps is { } b ? $"{b} kbps" : "-";
                    historyList.Items.Add(_tr.Tr("convert_dialog.history_row", ("date", date), ("source", row.SourceFormat), ("target", row.TargetFormat), ("bitrate", bitrateText), ("path", row.OutputPath)));
                }
            }
            catch (Exception) { }
        }

        async System.Threading.Tasks.Task RunPreviewAsync()
        {
            var targetFormat = (string)formatCombo.SelectedItem;
            int? bitrate = bitrateCheck.IsChecked == true && int.TryParse(bitrateBox.Text, out var b) ? b : null;
            try
            {
                var plan = await _api.PreviewConversionAsync(mediaId, new ConvertPreviewRequest(targetFormat, bitrate));
                if (plan is null) return;
                currentPlan = plan;
                var text = _tr.Tr("convert_dialog.plan_summary", ("source_format", plan.SourceFormat), ("target_format", plan.TargetFormat), ("output_path", plan.OutputPath));
                if (plan.IsNoOpSameFormat) text += "\n" + _tr.Tr("convert_dialog.no_op_warning");
                if (plan.HasConflict)
                {
                    text += "\n\n" + _tr.Tr("convert_dialog.conflict_warning");
                    applyBtn.IsEnabled = false;
                }
                else
                {
                    applyBtn.IsEnabled = true;
                }
                planLabel.Text = text;
            }
            catch (Exception ex)
            {
                currentPlan = null;
                planLabel.Text = _tr.Tr("convert_dialog.preview_failed", ("error", ex.Message));
                applyBtn.IsEnabled = false;
            }
        }

        formatCombo.SelectionChanged += async (_, _) => await RunPreviewAsync();
        bitrateCheck.Checked += async (_, _) => { bitrateBox.IsEnabled = true; await RunPreviewAsync(); };
        bitrateCheck.Unchecked += async (_, _) => { bitrateBox.IsEnabled = false; await RunPreviewAsync(); };
        bitrateBox.TextChanged += async (_, _) => { if (bitrateCheck.IsChecked == true) await RunPreviewAsync(); };
        closeBtn.Click += (_, _) => dialog.Close();

        applyBtn.Click += async (_, _) =>
        {
            if (currentPlan is null) return;
            if (MessageBox.Show(_tr.Tr("convert_dialog.confirm_text", ("output_path", currentPlan.OutputPath)),
                    _tr.Tr("convert_dialog.confirm_title"), MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                var result = await _api.ApplyConversionAsync(mediaId, new ConvertApplyRequest(currentPlan.TargetFormat, currentPlan.BitrateKbps, true));
                if (result is null) return;
                changed = true;
                MessageBox.Show(_tr.Tr("convert_dialog.done_text", ("output_path", result.OutputPath)), _tr.Tr("convert_dialog.done_title"));
                await ReloadHistoryAsync();
                await RunPreviewAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("convert_dialog.apply_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        await ReloadHistoryAsync();
        await RunPreviewAsync();
        dialog.ShowDialog();
        return changed;
    }
}
