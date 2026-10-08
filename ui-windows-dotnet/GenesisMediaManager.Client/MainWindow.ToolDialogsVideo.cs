using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, achter inkrementeller Schritt - Pendant zu
/// ui-reference-pyside/genesis_ui/dialogs/video_dialog.py (§24, ADR-0016).
/// Tab 1 "Film": zeigt bereits eingebettete Film-Tags rein lesend an, Tab 2
/// "Serie/Episode": Film-vs-Episode-Erkennung (Tags + Dateipfad-Muster,
/// jeweils mit Confidence + Herkunftsangabe). Der Nutzer entscheidet SELBST,
/// welcher der beiden Faelle zutrifft und bestaetigt die Uebernahme
/// explizit (Prinzip #17) - kein automatisches Umschalten der Medienart.
/// Bewusst OHNE Online-Provider (TMDb/IMDb etc. sind Download/Import-
/// Adapter, Phase 8).
/// </summary>
public partial class MainWindow
{
    private async System.Threading.Tasks.Task<bool> ShowVideoDialogAsync(int mediaId, string filename)
    {
        var dialog = new Window
        {
            Title = _tr.Tr("video_dialog.window_title", ("filename", filename)), Width = 720, Height = 580,
            Owner = this, WindowStartupLocation = WindowStartupLocation.CenterOwner,
        };
        var root = new DockPanel { Margin = new Thickness(12), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        dialog.Content = root;

        var closeRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 8, 0, 0) };
        var closeBtn = new Button { Content = _tr.Tr("video_dialog.close_button"), Padding = new Thickness(10, 4, 10, 4) };
        closeRow.Children.Add(closeBtn);
        DockPanel.SetDock(closeRow, Dock.Bottom);
        root.Children.Add(closeRow);

        var tabs = new TabControl();
        root.Children.Add(tabs);
        bool changed = false;
        closeBtn.Click += (_, _) => dialog.Close();
        var empty = _tr.Tr("common.value_empty");

        void AddFormRow(Panel container, string labelKey, TextBlock value)
        {
            var row = new Grid { Margin = new Thickness(0, 2, 0, 2) };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            var label = new TextBlock { Text = _tr.Tr(labelKey) };
            Grid.SetColumn(label, 0);
            Grid.SetColumn(value, 1);
            row.Children.Add(label);
            row.Children.Add(value);
            container.Children.Add(row);
        }

        // --- Tab 1: Film -------------------------------------------------------
        var movieRoot = new StackPanel { Margin = new Thickness(8) };
        movieRoot.Children.Add(new TextBlock { Text = _tr.Tr("video_dialog.movie_info"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });
        var movieStatus = new TextBlock { Text = _tr.Tr("video_dialog.loading"), Margin = new Thickness(0, 0, 0, 8) };
        movieRoot.Children.Add(movieStatus);

        var movieTitleLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var movieYearLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var movieGenreLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var movieDirectorLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var movieActorsLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var movieDescriptionLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        AddFormRow(movieRoot, "video_dialog.field_title", movieTitleLabel);
        AddFormRow(movieRoot, "video_dialog.field_year", movieYearLabel);
        AddFormRow(movieRoot, "video_dialog.field_genre", movieGenreLabel);
        AddFormRow(movieRoot, "video_dialog.field_director", movieDirectorLabel);
        AddFormRow(movieRoot, "video_dialog.field_actors", movieActorsLabel);
        AddFormRow(movieRoot, "video_dialog.field_description", movieDescriptionLabel);

        var moviePersistedLabel = new TextBlock { Text = _tr.Tr("video_dialog.not_saved_yet"), TextWrapping = TextWrapping.Wrap, Foreground = System.Windows.Media.Brushes.DarkSeaGreen, Margin = new Thickness(0, 8, 0, 8) };
        movieRoot.Children.Add(moviePersistedLabel);
        var applyMovieBtn = new Button { Content = _tr.Tr("video_dialog.apply_movie_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, HorizontalAlignment = HorizontalAlignment.Left };
        movieRoot.Children.Add(applyMovieBtn);
        tabs.Items.Add(new TabItem { Header = _tr.Tr("video_dialog.tab_movie"), Content = new ScrollViewer { Content = movieRoot, VerticalScrollBarVisibility = ScrollBarVisibility.Auto } });

        async System.Threading.Tasks.Task ReloadPersistedMovieAsync()
        {
            try
            {
                var saved = await _api.GetMovieAsync(mediaId);
                moviePersistedLabel.Text = saved is null
                    ? _tr.Tr("video_dialog.not_saved_yet")
                    : _tr.Tr("video_dialog.movie_saved_summary", ("title", saved.Title ?? empty), ("year", saved.Year?.ToString() ?? empty));
            }
            catch (Exception) { moviePersistedLabel.Text = _tr.Tr("video_dialog.not_saved_yet"); }
        }

        async System.Threading.Tasks.Task LoadMovieTabAsync()
        {
            try
            {
                var tags = await _api.GetVideoTagsPreviewAsync(mediaId);
                if (tags is null) { movieStatus.Text = _tr.Tr("video_dialog.no_tags_found"); return; }
                movieStatus.Text = tags.HasAnyTag ? _tr.Tr("video_dialog.tags_found") : _tr.Tr("video_dialog.no_tags_found");
                movieTitleLabel.Text = tags.Title ?? empty;
                movieYearLabel.Text = tags.Year?.ToString() ?? empty;
                movieGenreLabel.Text = tags.Genre ?? empty;
                movieDirectorLabel.Text = tags.DirectorNames.Count > 0 ? string.Join(", ", tags.DirectorNames) : empty;
                movieActorsLabel.Text = tags.ActorNames.Count > 0 ? string.Join(", ", tags.ActorNames) : empty;
                movieDescriptionLabel.Text = tags.Description ?? empty;
                applyMovieBtn.IsEnabled = tags.HasAnyTag;
            }
            catch (Exception ex)
            {
                movieStatus.Text = _tr.Tr("video_dialog.load_failed", ("error", ex.Message));
            }
            await ReloadPersistedMovieAsync();
        }

        applyMovieBtn.Click += async (_, _) =>
        {
            if (MessageBox.Show(_tr.Tr("video_dialog.confirm_movie_text"), _tr.Tr("video_dialog.confirm_movie_title"),
                    MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                await _api.ApplyMovieMetadataAsync(mediaId, true);
                changed = true;
                await ReloadPersistedMovieAsync();
                MessageBox.Show(_tr.Tr("video_dialog.movie_applied_text"), _tr.Tr("video_dialog.applied_title"));
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("video_dialog.apply_movie_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        // --- Tab 2: Serie/Episode ------------------------------------------------
        var episodeRoot = new StackPanel { Margin = new Thickness(8) };
        episodeRoot.Children.Add(new TextBlock { Text = _tr.Tr("video_dialog.episode_info"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) });
        var episodeStatus = new TextBlock { Text = _tr.Tr("video_dialog.loading"), Margin = new Thickness(0, 0, 0, 8) };
        episodeRoot.Children.Add(episodeStatus);

        var episodeSeriesLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var episodeSeasonLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var episodeNumberLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var episodeTitleLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var episodeConfidenceLabel = new TextBlock { TextWrapping = TextWrapping.Wrap };
        AddFormRow(episodeRoot, "video_dialog.field_series", episodeSeriesLabel);
        AddFormRow(episodeRoot, "video_dialog.field_season", episodeSeasonLabel);
        AddFormRow(episodeRoot, "video_dialog.field_episode_number", episodeNumberLabel);
        AddFormRow(episodeRoot, "video_dialog.field_title", episodeTitleLabel);
        AddFormRow(episodeRoot, "video_dialog.field_confidence", episodeConfidenceLabel);

        var episodePersistedLabel = new TextBlock { Text = _tr.Tr("video_dialog.not_saved_yet"), TextWrapping = TextWrapping.Wrap, Foreground = System.Windows.Media.Brushes.DarkSeaGreen, Margin = new Thickness(0, 8, 0, 8) };
        episodeRoot.Children.Add(episodePersistedLabel);
        var applyEpisodeBtn = new Button { Content = _tr.Tr("video_dialog.apply_episode_button"), Padding = new Thickness(10, 4, 10, 4), IsEnabled = false, HorizontalAlignment = HorizontalAlignment.Left };
        episodeRoot.Children.Add(applyEpisodeBtn);
        tabs.Items.Add(new TabItem { Header = _tr.Tr("video_dialog.tab_episode"), Content = new ScrollViewer { Content = episodeRoot, VerticalScrollBarVisibility = ScrollBarVisibility.Auto } });

        async System.Threading.Tasks.Task ReloadPersistedEpisodeAsync()
        {
            try
            {
                var saved = await _api.GetEpisodeAsync(mediaId);
                episodePersistedLabel.Text = saved is null
                    ? _tr.Tr("video_dialog.not_saved_yet")
                    : _tr.Tr("video_dialog.episode_saved_summary",
                        ("series", saved.Series ?? empty), ("season", saved.SeasonNumber?.ToString() ?? empty), ("episode", saved.EpisodeNumber?.ToString() ?? empty));
            }
            catch (Exception) { episodePersistedLabel.Text = _tr.Tr("video_dialog.not_saved_yet"); }
        }

        async System.Threading.Tasks.Task LoadEpisodeTabAsync()
        {
            try
            {
                var result = await _api.DetectEpisodePreviewAsync(mediaId);
                if (result is null) { episodeStatus.Text = _tr.Tr("video_dialog.episode_unlikely"); return; }
                episodeStatus.Text = result.IsLikelyEpisode ? _tr.Tr("video_dialog.episode_likely") : _tr.Tr("video_dialog.episode_unlikely");

                string WithSource(string? value, string? source) =>
                    value is null ? empty : (source is not null ? $"{value}  ({_tr.Tr($"video_dialog.source_{source}")})" : value);

                episodeSeriesLabel.Text = WithSource(result.SeriesName, result.SeriesSource);
                episodeSeasonLabel.Text = WithSource(result.SeasonNumber?.ToString(), result.SeasonSource);
                episodeNumberLabel.Text = WithSource(result.EpisodeNumber?.ToString(), result.EpisodeSource);
                episodeTitleLabel.Text = WithSource(result.Title, result.TitleSource);
                episodeConfidenceLabel.Text = $"{result.Confidence:P0}";
                applyEpisodeBtn.IsEnabled = result.IsLikelyEpisode;
            }
            catch (Exception ex)
            {
                episodeStatus.Text = _tr.Tr("video_dialog.load_failed", ("error", ex.Message));
            }
            await ReloadPersistedEpisodeAsync();
        }

        applyEpisodeBtn.Click += async (_, _) =>
        {
            if (MessageBox.Show(_tr.Tr("video_dialog.confirm_episode_text"), _tr.Tr("video_dialog.confirm_episode_title"),
                    MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                return;
            try
            {
                await _api.ApplyEpisodeMetadataAsync(mediaId, true);
                changed = true;
                await ReloadPersistedEpisodeAsync();
                MessageBox.Show(_tr.Tr("video_dialog.episode_applied_text"), _tr.Tr("video_dialog.applied_title"));
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("video_dialog.apply_episode_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };

        await LoadMovieTabAsync();
        await LoadEpisodeTabAsync();
        dialog.ShowDialog();
        return changed;
    }
}
