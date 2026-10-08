using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using GenesisMediaManager.Client.Api;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Job-Warteschlange (nav.job_queue,
/// §35/§36). Pendant zu ui-reference-pyside/genesis_ui/views/job_queue_view.py.
/// Zeigt ALLE Hintergrund-Jobs mit Fortschritt; Pause/Fortsetzen/Abbrechen
/// setzen nur den gewuenschten Zielstatus - die eigentliche kooperative
/// Pruefung findet im Core Service statt (siehe JobManager). Aktualisiert
/// sich automatisch alle zwei Sekunden, identisch zur Python-Referenz
/// (QTimer dort, DispatcherTimer hier), solange die Seite aktiv angezeigt
/// wird (Timer wird beim Verlassen der Seite gestoppt, siehe Tick-Handler-
/// Abmeldung ueber MainContent-Wechsel).
/// </summary>
public partial class MainWindow
{
    private static readonly IReadOnlyDictionary<string, string> JobStatusKeys = new Dictionary<string, string>
    {
        ["pending"] = "job_queue_view.status_pending",
        ["running"] = "job_queue_view.status_running",
        ["paused"] = "job_queue_view.status_paused",
        ["completed"] = "job_queue_view.status_completed",
        ["failed"] = "job_queue_view.status_failed",
        ["cancelled"] = "job_queue_view.status_cancelled",
    };

    private static readonly HashSet<string> ActiveJobStatuses = new() { "pending", "running", "paused" };

    private DispatcherTimer? _jobQueueTimer;

    private sealed record JobQueueRow(
        string Id, string JobType, string StatusText, string ProgressText,
        int ErrorCount, int WarningCount, string CreatedAt);

    private async Task ShowJobQueueAsync()
    {
        _jobQueueTimer?.Stop();

        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("job_queue_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock { Text = _tr.Tr("job_queue_view.intro_note"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });

        var refreshBtn = new Button { Content = _tr.Tr("job_queue_view.refresh_button"), HorizontalAlignment = HorizontalAlignment.Left };
        root.Children.Add(refreshBtn);

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        root.Children.Add(statusText);

        // Parity zu ui-reference-pyside (keine interaktive Spaltensortierung
        // dort implementiert, §53). Hier zwar unkritisch, da die Selektion
        // ueber SelectedItem als JobQueueRow erfolgt (sortierresistent),
        // aber fuer Konsistenz trotzdem deaktiviert.
        var grid = new DataGrid { AutoGenerateColumns = false, IsReadOnly = true, SelectionMode = DataGridSelectionMode.Single, Margin = new Thickness(0, 8, 0, 0), MaxHeight = 320, CanUserSortColumns = false };
        void Col(string headerKey, string path, double width) =>
            grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr(headerKey), Binding = new System.Windows.Data.Binding(path), Width = width });
        Col("job_queue_view.col_id", "Id", 160);
        grid.Columns.Add(new DataGridTextColumn { Header = _tr.Tr("job_queue_view.col_type"), Binding = new System.Windows.Data.Binding("JobType"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        Col("job_queue_view.col_status", "StatusText", 110);
        Col("job_queue_view.col_progress", "ProgressText", 130);
        Col("job_queue_view.col_errors", "ErrorCount", 70);
        Col("job_queue_view.col_warnings", "WarningCount", 80);
        Col("job_queue_view.col_created", "CreatedAt", 170);
        root.Children.Add(grid);

        var currentItemText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        var progressBar = new ProgressBar { Height = 18, Margin = new Thickness(0, 4, 0, 8) };
        root.Children.Add(currentItemText);
        root.Children.Add(progressBar);

        var actionRow = new StackPanel { Orientation = Orientation.Horizontal };
        var pauseBtn = new Button { Content = _tr.Tr("job_queue_view.pause_button"), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var resumeBtn = new Button { Content = _tr.Tr("job_queue_view.resume_button"), IsEnabled = false, Margin = new Thickness(0, 0, 8, 0) };
        var cancelBtn = new Button { Content = _tr.Tr("job_queue_view.cancel_button"), IsEnabled = false };
        actionRow.Children.Add(pauseBtn);
        actionRow.Children.Add(resumeBtn);
        actionRow.Children.Add(cancelBtn);
        root.Children.Add(actionRow);

        MainContent.Content = new ScrollViewer { Content = root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        Dictionary<string, JobInfo> jobsById = new();
        string? selectedJobId = null;

        void UpdateDetailPanel()
        {
            var job = selectedJobId is not null && jobsById.TryGetValue(selectedJobId, out var j) ? j : null;
            if (job is null)
            {
                currentItemText.Text = string.Empty;
                progressBar.IsIndeterminate = false;
                progressBar.Value = 0;
                pauseBtn.IsEnabled = false;
                resumeBtn.IsEnabled = false;
                cancelBtn.IsEnabled = false;
                return;
            }
            currentItemText.Text = _tr.Tr("job_queue_view.current_item_label", ("item", job.CurrentItem ?? "-"));
            var total = job.TotalItems ?? 0;
            var processed = job.ProcessedItems ?? 0;
            if (total > 0)
            {
                progressBar.IsIndeterminate = false;
                progressBar.Minimum = 0;
                progressBar.Maximum = total;
                progressBar.Value = Math.Min(processed, total);
            }
            else
            {
                progressBar.IsIndeterminate = true;
            }
            pauseBtn.IsEnabled = job.Status == "running";
            resumeBtn.IsEnabled = job.Status == "paused";
            cancelBtn.IsEnabled = ActiveJobStatuses.Contains(job.Status);
        }

        async Task ReloadAsync()
        {
            var previouslySelected = selectedJobId;
            try
            {
                var jobs = await _api.ListJobsAsync(100);
                jobsById = jobs.ToDictionary(j => j.Id);
                grid.ItemsSource = jobs.Select(j =>
                {
                    var total = j.TotalItems ?? 0;
                    var processed = j.ProcessedItems ?? 0;
                    var progressText = total > 0
                        ? $"{processed}/{total} ({(double)processed / total:P0})"
                        : _tr.Tr("job_queue_view.progress_unknown");
                    return new JobQueueRow(
                        j.Id, j.JobType, _tr.Tr(JobStatusKeys.TryGetValue(j.Status, out var sk) ? sk : j.Status),
                        progressText, j.ErrorCount, j.WarningCount, j.CreatedAt ?? "-");
                }).ToList();
                statusText.Text = jobs.Count == 0 ? _tr.Tr("job_queue_view.no_jobs") : string.Empty;
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("job_queue_view.load_failed", ("error", ex.Message));
                return;
            }

            selectedJobId = jobsById.ContainsKey(previouslySelected ?? string.Empty) ? previouslySelected : null;
            UpdateDetailPanel();
        }

        grid.SelectionChanged += (_, _) =>
        {
            selectedJobId = (grid.SelectedItem as JobQueueRow)?.Id;
            UpdateDetailPanel();
        };
        refreshBtn.Click += async (_, _) => await ReloadAsync();

        async Task RunJobActionAsync(Func<string, CancellationToken, Task<JobInfo?>> action)
        {
            if (selectedJobId is null) return;
            try
            {
                await action(selectedJobId, default);
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("dashboard.error", ("error", ex.Message));
            }
            await ReloadAsync();
        }

        pauseBtn.Click += async (_, _) => await RunJobActionAsync(_api.PauseJobAsync);
        resumeBtn.Click += async (_, _) => await RunJobActionAsync(_api.ResumeJobAsync);
        cancelBtn.Click += async (_, _) =>
        {
            if (selectedJobId is null) return;
            var confirmResult = MessageBox.Show(
                _tr.Tr("job_queue_view.cancel_confirm_text", ("job_id", selectedJobId)),
                _tr.Tr("job_queue_view.cancel_confirm_title"),
                MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No);
            if (confirmResult != MessageBoxResult.Yes) return;
            await RunJobActionAsync(_api.CancelJobAsync);
        };

        _jobQueueTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
        _jobQueueTimer.Tick += async (_, _) => await ReloadAsync();
        _jobQueueTimer.Start();

        await ReloadAsync();
    }
}
