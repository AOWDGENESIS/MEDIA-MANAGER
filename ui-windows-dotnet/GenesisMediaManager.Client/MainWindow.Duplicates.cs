using System.Windows;
using System.Windows.Controls;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Duplikate (nav.duplicates, §21,
/// ADR-0013). Pendant zu ui-reference-pyside/genesis_ui/views/duplicates_view.py.
/// Scan ist reine Analyse (erzeugt/aendert/loescht KEINE Mediendatei,
/// Prinzip #4/#5); "geprueft" markieren ist rein organisatorisch. Es gibt
/// bewusst KEINE Loeschfunktion (§21 "Niemals automatisch loeschen").
/// </summary>
public partial class MainWindow
{
    private static readonly IReadOnlyDictionary<string, string> DuplicateCategoryKeys = new Dictionary<string, string>
    {
        ["exact_duplicate"] = "duplicates_view.category_exact",
        ["probable_duplicate"] = "duplicates_view.category_probable",
        ["same_content_different_format"] = "duplicates_view.category_same_content",
        ["similar_content"] = "duplicates_view.category_similar",
    };

    // Entspricht SCOPE_OPTIONS in duplicates_view.py: (kind, label) mit
    // kind=null als erster Eintrag ("alle Medienarten").
    private static readonly (string? Kind, string LabelKey)[] DuplicateScopeOptions =
    {
        (null, "duplicates_view.scope_all"),
        ("music", "nav.music"), ("audiobook", "nav.audiobook"), ("movie", "nav.movie"),
        ("episode", "nav.episode"), ("podcast_episode", "nav.podcast"), ("ai_music", "nav.ai_music"),
        ("unknown", "nav.unknown"),
    };

    private async Task ShowDuplicatesAsync()
    {
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("duplicates_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("duplicates_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var controls = new StackPanel { Orientation = Orientation.Horizontal };
        controls.Children.Add(new TextBlock { Text = _tr.Tr("duplicates_view.scope_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 4, 0) });
        var scopeCombo = new ComboBox { Width = 150, Margin = new Thickness(0, 0, 8, 0) };
        foreach (var (_, labelKey) in DuplicateScopeOptions) scopeCombo.Items.Add(_tr.Tr(labelKey));
        scopeCombo.SelectedIndex = 0;

        var scanBtn = new Button { Content = _tr.Tr("duplicates_view.scan_button"), Margin = new Thickness(0, 0, 8, 0) };

        var reviewedCombo = new ComboBox { Width = 150 };
        reviewedCombo.Items.Add(_tr.Tr("duplicates_view.filter_open"));
        reviewedCombo.Items.Add(_tr.Tr("duplicates_view.filter_reviewed"));
        reviewedCombo.Items.Add(_tr.Tr("duplicates_view.filter_all"));
        reviewedCombo.SelectedIndex = 0;

        controls.Children.Add(scopeCombo);
        controls.Children.Add(scanBtn);
        controls.Children.Add(reviewedCombo);
        root.Children.Add(controls);

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        root.Children.Add(statusText);

        // CanUserSortColumns=false ist PFLICHT: review/unreview indizieren
        // unten per grid.SelectedIndex in "groups" - sonst koennte bei
        // aktiver Spaltensortierung die FALSCHE Duplikatgruppe markiert
        // werden. Gefunden im Deep-Search, behoben.
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, Margin = new Thickness(0, 8, 0, 0), MaxHeight = 420, CanUserSortColumns = false };
            grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("duplicates_view.col_category"), Binding = new System.Windows.Data.Binding("Category"), Width = 180 });
            grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("duplicates_view.col_confidence"), Binding = new System.Windows.Data.Binding("Confidence"), Width = 90 });
            // Die Dateiliste einer Gruppe enthaelt einen Pfad PRO Datei
            // (zeilenweise getrennt, "\n".join(paths) in
            // duplicates_view.py::_reload) - eine reine Textspalte wuerde
            // nur die erste Zeile zeigen. Daher Template-Spalte mit
            // umbruchfaehigem TextBlock (Paritaet zur mehrzeiligen
            // QTreeWidget-Zelle der Python-Referenz; dasselbe
            // FrameworkElementFactory-Muster wie die Thumbnail-/Format-
            // Spalten in MainWindow.xaml.cs).
            var filesCell = new FrameworkElementFactory(typeof(TextBlock));
            filesCell.SetBinding(TextBlock.TextProperty, new System.Windows.Data.Binding("Files"));
            filesCell.SetValue(TextBlock.TextWrappingProperty, TextWrapping.Wrap);
            grid.Columns.Add(new DataGridTemplateColumn
            {
                Header = _tr.Tr("duplicates_view.col_files"),
                CellTemplate = filesCell,
                Width = new DataGridLength(2, DataGridLengthUnitType.Star),
            });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("duplicates_view.col_reason"), Binding = new System.Windows.Data.Binding("Reason"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("duplicates_view.col_status"), Binding = new System.Windows.Data.Binding("Status"), Width = 100 });
        root.Children.Add(grid);

        var actionRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
        var markReviewedBtn = new Button { Content = _tr.Tr("duplicates_view.mark_reviewed_button"), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var unreviewBtn = new Button { Content = _tr.Tr("duplicates_view.unreview_button"), IsEnabled = false };
        actionRow.Children.Add(markReviewedBtn);
        actionRow.Children.Add(unreviewBtn);
        root.Children.Add(actionRow);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        List<DuplicateGroupInfo> groups = new();
        var pathCache = new Dictionary<int, string>();

        async Task<string> ResolvePathAsync(int mediaFileId)
        {
            if (pathCache.TryGetValue(mediaFileId, out var cached)) return cached;
            string path;
            try
            {
                var detail = await _api.GetMediaDetailAsync(mediaFileId);
                path = detail?.AbsolutePath ?? $"#{mediaFileId}";
            }
            catch (Exception)
            {
                path = $"#{mediaFileId}";
            }
            pathCache[mediaFileId] = path;
            return path;
        }

        async Task ReloadAsync()
        {
            bool? reviewedFilter = reviewedCombo.SelectedIndex switch { 0 => false, 1 => true, _ => null };
            try
            {
                groups = await _api.ListDuplicatesAsync(reviewedFilter);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("duplicates_view.load_failed", ("error", ex.Message));
                return;
            }

            var rows = new List<object>();
            foreach (var group in groups)
            {
                var paths = new List<string>();
                foreach (var mid in group.MediaFileIds) paths.Add(await ResolvePathAsync(mid));
                var categoryKey = DuplicateCategoryKeys.TryGetValue(group.Category, out var ck) ? ck : group.Category;
                rows.Add(new
                {
                    Category = _tr.Tr(categoryKey),
                    // Invariantes "87%"-Format wie Pythons f"{confidence:.0%}"
                    // (siehe DuplicatesSupport.FormatConfidence).
                    Confidence = DuplicatesSupport.FormatConfidence(group.Confidence),
                    Files = string.Join(Environment.NewLine, paths),
                    group.Reason,
                    Status = _tr.Tr(group.Reviewed ? "duplicates_view.status_reviewed" : "duplicates_view.status_open"),
                });
            }
            grid.ItemsSource = rows;
            statusText.Text = groups.Count == 0 ? _tr.Tr("duplicates_view.no_results") : string.Empty;
            markReviewedBtn.IsEnabled = false;
            unreviewBtn.IsEnabled = false;
        }

        scanBtn.Click += async (_, _) =>
        {
            var kind = DuplicateScopeOptions[scopeCombo.SelectedIndex].Kind;
            scanBtn.IsEnabled = false;
            statusText.Text = _tr.Tr("duplicates_view.scanning");
            var scanSucceeded = false;
            try
            {
                var found = await _api.ScanDuplicatesAsync(kind);
                statusText.Text = _tr.Tr("duplicates_view.scan_done", ("count", found.Count));
                scanSucceeded = true;
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("duplicates_view.scan_failed", ("error", ex.Message));
            }
            scanBtn.IsEnabled = true;
            // Paritaet zu duplicates_view.py::_on_scan_clicked: Nach einem
            // FEHLGESCHLAGENEN Scan wird die Liste NICHT neu geladen
            // (Python kehrt dort vor self._reload() zurueck) - die
            // Fehlermeldung bleibt unvermischt mit frischen Daten stehen.
            if (scanSucceeded) await ReloadAsync();
        };

        reviewedCombo.SelectionChanged += async (_, _) => await ReloadAsync();

        grid.SelectionChanged += (_, _) =>
        {
            var hasSelection = grid.SelectedIndex >= 0 && grid.SelectedIndex < groups.Count;
            var reviewed = hasSelection && groups[grid.SelectedIndex].Reviewed;
            markReviewedBtn.IsEnabled = hasSelection && !reviewed;
            unreviewBtn.IsEnabled = hasSelection && reviewed;
        };

        // Paritaet zu duplicates_view.py::_on_mark_reviewed_clicked/
        // _on_unreview_clicked: Nach einer FEHLGESCHLAGENEN Aenderung wird
        // die Liste NICHT neu geladen (Python kehrt nach show_api_error
        // zurueck, ohne self._reload() aufzurufen); die Fehlermeldung
        // bleibt hier als Statustext sichtbar (Dialog-Anzeige ist Gap L).
        markReviewedBtn.Click += async (_, _) =>
        {
            if (grid.SelectedIndex < 0 || grid.SelectedIndex >= groups.Count) return;
            try
            {
                await _api.ReviewDuplicateGroupAsync(groups[grid.SelectedIndex].Id);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("duplicates_view.review_failed", ("error", ex.Message));
                return;
            }
            await ReloadAsync();
        };
        unreviewBtn.Click += async (_, _) =>
        {
            if (grid.SelectedIndex < 0 || grid.SelectedIndex >= groups.Count) return;
            try
            {
                await _api.UnreviewDuplicateGroupAsync(groups[grid.SelectedIndex].Id);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("duplicates_view.review_failed", ("error", ex.Message));
                return;
            }
            await ReloadAsync();
        };

        await ReloadAsync();
    }
}
