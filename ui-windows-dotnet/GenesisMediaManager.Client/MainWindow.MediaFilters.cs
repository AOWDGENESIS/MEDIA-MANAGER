using System;
using System.Windows;
using System.Windows.Controls;

namespace GenesisMediaManager.Client;

// MediaFileActions und MediaSearchFiltersSupport (beide WPF-unabhaengig)
// wurden nach MediaFileActionsSupport.cs ausgelagert, damit sie im reinen
// net8.0-Testprojekt ohne Windows-Targeting-Pack getestet werden koennen
// (siehe Kommentar dort).

public partial class MainWindow
{
    // --- Filter-Dialog (Pendant zu
    // ui-reference-pyside/genesis_ui/dialogs/search_filters_dialog.py, §9,
    // Gap-Analyse C) ----------------------------------------------------
    //
    // Liefert `null` bei Abbruch (Dialog per "Abbrechen"/Fenster-X
    // geschlossen - vorhandene Filter bleiben unveraendert), sonst die
    // (ggf. leere) neue Filterkombination. Rein lesend/filternd
    // (Grundprinzip #4/#5) - sendet nur zusaetzliche Query-Parameter an
    // den bereits bestehenden `GET /media`-Endpunkt, veraendert keine
    // Datensaetze.
    private MediaSearchFilters? ShowMediaFiltersDialog(MediaSearchFilters? initial)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("search_filters_dialog.window_title"),
            Width = 480, Height = 640,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
            ResizeMode = ResizeMode.CanResize,
        };

        var outer = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        outer.Content = root;
        dialog.Content = outer;

        GroupBox Group(string titleKey)
        {
            var box = new GroupBox { Header = _tr.Tr(titleKey), Margin = new Thickness(0, 0, 0, 10) };
            root.Children.Add(box);
            return box;
        }

        Grid FormRow(Panel container, string labelKey, UIElement field)
        {
            var row = new Grid { Margin = new Thickness(0, 2, 0, 2) };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(170) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            var label = new TextBlock { Text = _tr.Tr(labelKey), VerticalAlignment = VerticalAlignment.Center };
            Grid.SetColumn(label, 0);
            Grid.SetColumn(field, 1);
            row.Children.Add(label);
            row.Children.Add(field);
            container.Children.Add(row);
            return row;
        }

        // --- Textfilter ---------------------------------------------------
        var textGroup = Group("search_filters_dialog.group_text");
        var textStack = new StackPanel();
        textGroup.Content = textStack;
        var genreBox = new TextBox { Text = initial?.Genre ?? string.Empty };
        FormRow(textStack, "search_filters_dialog.genre_label", genreBox);
        var sourceBox = new TextBox { Text = initial?.Source ?? string.Empty };
        FormRow(textStack, "search_filters_dialog.source_label", sourceBox);
        var personBox = new TextBox { Text = initial?.Person ?? string.Empty };
        FormRow(textStack, "search_filters_dialog.person_label", personBox);
        var seriesBox = new TextBox { Text = initial?.Series ?? string.Empty };
        FormRow(textStack, "search_filters_dialog.series_label", seriesBox);
        var extensionBox = new TextBox { Text = initial?.Extension ?? string.Empty, ToolTip = "mp3, mp4, m4b, …" };
        FormRow(textStack, "search_filters_dialog.extension_label", extensionBox);

        // --- Zahlen-/Bereichsfilter ----------------------------------------
        var numGroup = Group("search_filters_dialog.group_numeric");
        var numStack = new StackPanel();
        numGroup.Content = numStack;

        var yearBox = new TextBox { Text = initial?.Year?.ToString() ?? string.Empty, ToolTip = _tr.Tr("search_filters_dialog.any_value") };
        FormRow(numStack, "search_filters_dialog.year_label", yearBox);

        var seasonRow = new DockPanel();
        var seasonBox = new TextBox { Width = 90, Margin = new Thickness(0, 0, 8, 0), Text = initial?.Season?.ToString() ?? string.Empty };
        var episodeBox = new TextBox { Width = 90, Text = initial?.EpisodeNumber?.ToString() ?? string.Empty };
        seasonRow.Children.Add(seasonBox);
        seasonRow.Children.Add(episodeBox);
        FormRow(numStack, "search_filters_dialog.season_episode_label", seasonRow);

        var sizeRow = new DockPanel();
        var minSizeMbBox = new TextBox { Width = 100, Margin = new Thickness(0, 0, 8, 0), Text = initial?.MinSizeBytes is { } minB ? (minB / 1_000_000.0).ToString(System.Globalization.CultureInfo.InvariantCulture) : string.Empty };
        var maxSizeMbBox = new TextBox { Width = 100, Text = initial?.MaxSizeBytes is { } maxB ? (maxB / 1_000_000.0).ToString(System.Globalization.CultureInfo.InvariantCulture) : string.Empty };
        sizeRow.Children.Add(minSizeMbBox);
        sizeRow.Children.Add(maxSizeMbBox);
        FormRow(numStack, "search_filters_dialog.size_range_label", sizeRow);

        var durationRow = new DockPanel();
        var minDurationBox = new TextBox { Width = 100, Margin = new Thickness(0, 0, 8, 0), Text = initial?.MinDurationSeconds?.ToString(System.Globalization.CultureInfo.InvariantCulture) ?? string.Empty };
        var maxDurationBox = new TextBox { Width = 100, Text = initial?.MaxDurationSeconds?.ToString(System.Globalization.CultureInfo.InvariantCulture) ?? string.Empty };
        durationRow.Children.Add(minDurationBox);
        durationRow.Children.Add(maxDurationBox);
        FormRow(numStack, "search_filters_dialog.duration_range_label", durationRow);

        var lufsEnabled = initial?.MinLufs is not null || initial?.MaxLufs is not null;
        var lufsRow = new DockPanel();
        var minLufsBox = new TextBox { Width = 100, Margin = new Thickness(0, 0, 8, 0), Text = (initial?.MinLufs ?? -60).ToString(System.Globalization.CultureInfo.InvariantCulture) };
        var maxLufsBox = new TextBox { Width = 100, Text = (initial?.MaxLufs ?? 10).ToString(System.Globalization.CultureInfo.InvariantCulture) };
        lufsRow.Children.Add(minLufsBox);
        lufsRow.Children.Add(maxLufsBox);
        FormRow(numStack, "search_filters_dialog.lufs_range_label", lufsRow);
        var lufsEnabledCheck = new CheckBox { Content = _tr.Tr("search_filters_dialog.lufs_enabled_label"), IsChecked = lufsEnabled, Margin = new Thickness(0, 2, 0, 2) };
        numStack.Children.Add(lufsEnabledCheck);

        // --- KI-Status ------------------------------------------------------
        var choiceGroup = Group("search_filters_dialog.group_choice");
        var choiceStack = new StackPanel();
        choiceGroup.Content = choiceStack;
        var aiStatusChoices = new (string Value, string LabelKey)[]
        {
            ("", "search_filters_dialog.ai_status_any"),
            ("ai_generated", "search_filters_dialog.ai_status_ai_generated"),
            ("human_generated", "search_filters_dialog.ai_status_human_generated"),
            ("hybrid", "search_filters_dialog.ai_status_hybrid"),
            ("unknown", "search_filters_dialog.ai_status_unknown"),
        };
        var aiStatusCombo = new ComboBox { Width = 220 };
        foreach (var (value, labelKey) in aiStatusChoices)
        {
            aiStatusCombo.Items.Add(new ComboBoxItem { Content = _tr.Tr(labelKey), Tag = value });
        }
        aiStatusCombo.SelectedIndex = Math.Max(0, Array.FindIndex(aiStatusChoices, c => c.Value == (initial?.AiStatus ?? "")));
        FormRow(choiceStack, "search_filters_dialog.ai_status_label", aiStatusCombo);

        // --- Weitere Filter (Checkboxen) ------------------------------------
        var flagsGroup = Group("search_filters_dialog.group_flags");
        var flagsStack = new StackPanel();
        flagsGroup.Content = flagsStack;
        var qualityIssuesCheck = new CheckBox { Content = _tr.Tr("search_filters_dialog.quality_issues_label"), IsChecked = initial?.HasQualityIssues ?? false, Margin = new Thickness(0, 2, 0, 2) };
        var missingMetadataCheck = new CheckBox { Content = _tr.Tr("search_filters_dialog.missing_metadata_label"), IsChecked = initial?.MissingMetadata ?? false, Margin = new Thickness(0, 2, 0, 2) };
        var missingCoverCheck = new CheckBox { Content = _tr.Tr("search_filters_dialog.missing_cover_label"), IsChecked = initial?.MissingCover ?? false, Margin = new Thickness(0, 2, 0, 2) };
        var duplicateOnlyCheck = new CheckBox { Content = _tr.Tr("search_filters_dialog.duplicate_only_label"), IsChecked = initial?.DuplicateOnly ?? false, Margin = new Thickness(0, 2, 0, 2) };
        flagsStack.Children.Add(qualityIssuesCheck);
        flagsStack.Children.Add(missingMetadataCheck);
        flagsStack.Children.Add(missingCoverCheck);
        flagsStack.Children.Add(duplicateOnlyCheck);

        // --- Buttons (Reset/OK/Abbrechen) -----------------------------------
        var buttonRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 12, 0, 0) };
        // Qt liefert fuer QDialogButtonBox.Reset/Ok/Cancel seine eigenen,
        // bereits lokalisierten Standardtexte (kein eigener tr()-Schluessel
        // im Python-Original noetig) - hier daher wie an der bestehenden
        // Praezedenz in MainWindow.VoiceStudio.cs schlicht fest verdrahtet.
        var resetBtn = new Button { Content = _tr.Tr("common.button_reset"), Padding = new Thickness(12, 4, 12, 4), Margin = new Thickness(0, 0, 8, 0) };
        var cancelBtn = new Button { Content = _tr.Tr("common.button_cancel"), Padding = new Thickness(12, 4, 12, 4), Margin = new Thickness(0, 0, 8, 0), IsCancel = true };
        var okBtn = new Button { Content = _tr.Tr("common.button_ok"), Padding = new Thickness(12, 4, 12, 4), IsDefault = true };
        buttonRow.Children.Add(resetBtn);
        buttonRow.Children.Add(cancelBtn);
        buttonRow.Children.Add(okBtn);
        root.Children.Add(buttonRow);

        resetBtn.Click += (_, _) =>
        {
            genreBox.Text = sourceBox.Text = personBox.Text = seriesBox.Text = extensionBox.Text = string.Empty;
            yearBox.Text = seasonBox.Text = episodeBox.Text = string.Empty;
            minSizeMbBox.Text = maxSizeMbBox.Text = minDurationBox.Text = maxDurationBox.Text = string.Empty;
            minLufsBox.Text = "-60";
            maxLufsBox.Text = "10";
            lufsEnabledCheck.IsChecked = false;
            aiStatusCombo.SelectedIndex = 0;
            qualityIssuesCheck.IsChecked = false;
            missingMetadataCheck.IsChecked = false;
            missingCoverCheck.IsChecked = false;
            duplicateOnlyCheck.IsChecked = false;
        };

        bool accepted = false;
        okBtn.Click += (_, _) => { accepted = true; dialog.Close(); };
        cancelBtn.Click += (_, _) => dialog.Close();

        dialog.ShowDialog();
        if (!accepted) return null;

        static int? ParseIntOrNull(string text) => int.TryParse(text, out var v) && v != 0 ? v : null;
        static double? ParseDoubleOrNull(string text) =>
            double.TryParse(text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var v) && v != 0 ? v : null;
        static long? ParseMbToBytesOrNull(string text) =>
            double.TryParse(text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var v) && v > 0
                ? (long)(v * 1_000_000) : null;

        var aiStatusValue = (aiStatusCombo.SelectedItem as ComboBoxItem)?.Tag as string;

        return new MediaSearchFilters(
            Year: ParseIntOrNull(yearBox.Text),
            Genre: string.IsNullOrWhiteSpace(genreBox.Text) ? null : genreBox.Text.Trim(),
            Extension: string.IsNullOrWhiteSpace(extensionBox.Text) ? null : extensionBox.Text.Trim(),
            MinSizeBytes: ParseMbToBytesOrNull(minSizeMbBox.Text),
            MaxSizeBytes: ParseMbToBytesOrNull(maxSizeMbBox.Text),
            MinDurationSeconds: ParseDoubleOrNull(minDurationBox.Text),
            MaxDurationSeconds: ParseDoubleOrNull(maxDurationBox.Text),
            Source: string.IsNullOrWhiteSpace(sourceBox.Text) ? null : sourceBox.Text.Trim(),
            Person: string.IsNullOrWhiteSpace(personBox.Text) ? null : personBox.Text.Trim(),
            Series: string.IsNullOrWhiteSpace(seriesBox.Text) ? null : seriesBox.Text.Trim(),
            Season: ParseIntOrNull(seasonBox.Text),
            EpisodeNumber: ParseIntOrNull(episodeBox.Text),
            AiStatus: string.IsNullOrWhiteSpace(aiStatusValue) ? null : aiStatusValue,
            MinLufs: lufsEnabledCheck.IsChecked == true ? MediaSearchFiltersSupport.ParseLufsOrDefault(minLufsBox.Text, -60) : null,
            MaxLufs: lufsEnabledCheck.IsChecked == true ? MediaSearchFiltersSupport.ParseLufsOrDefault(maxLufsBox.Text, 10) : null,
            HasQualityIssues: qualityIssuesCheck.IsChecked == true ? true : null,
            MissingMetadata: missingMetadataCheck.IsChecked == true ? true : null,
            MissingCover: missingCoverCheck.IsChecked == true ? true : null,
            DuplicateOnly: duplicateOnlyCheck.IsChecked == true ? true : null);
    }
}
