using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using GenesisMediaManager.Client.Api;
using GenesisMediaManager.Client.I18n;

namespace GenesisMediaManager.Client;

public partial class MainWindow : Window
{
    private readonly GenesisApiClient _api = new();
    private readonly Translator _tr = Translator.Default;

    // Navigationsstruktur 1:1 wie in ui-reference-pyside/genesis_ui/main_window.py
    // (Originalauftrag §4) - bei Aenderungen dort bitte hier synchron halten.
    // ADR-0009: dieselben i18n-Schluessel (i18n/<sprache>.json) wie die
    // PySide6-Referenz-UI, KEINE hartcodierten Strings mehr (§53). Der
    // Navigationsbaum traegt den Schluessel (nicht den uebersetzten Text)
    // als Tag, damit "Dashboard" erkannt wird, egal in welcher Sprache die
    // Oberflaeche gerade laeuft.
    private static readonly (string SectionKey, string[] ItemKeys)[] NavStructure =
    {
        ("nav.section_dashboard", new[] { "nav.dashboard" }),
        ("nav.section_media", new[]
        {
            "nav.music", "nav.audiobook", "nav.movie", "nav.episode",
            "nav.podcast", "nav.ai_music", "nav.unknown",
        }),
        ("nav.section_library", new[]
        {
            "nav.search", "nav.artists", "nav.albums", "nav.titles",
            "nav.genres", "nav.persons", "nav.sources",
        }),
        ("nav.section_tools", new[]
        {
            "nav.media_analysis", "nav.metadata_editor", "nav.rename", "nav.loudness",
            "nav.cutter", "nav.convert", "nav.audio_recognition", "nav.duplicates",
            "nav.quality_check", "nav.artwork",
        }),
        ("nav.section_download_import", new[] { "nav.download_center", "nav.import", "nav.sources" }),
        ("nav.section_ai", new[] { "nav.ai_metadata", "nav.ai_audio_analysis", "nav.voice_studio", "nav.tts" }),
        ("nav.section_system", new[]
        {
            "nav.settings", "nav.databases", "nav.providers", "nav.plugins",
            "nav.licenses", "nav.logs", "nav.backups", "nav.diagnostics",
            "nav.job_queue", "nav.error_center",
        }),
    };

    public MainWindow(string apiBaseUrl = "http://127.0.0.1:8420")
    {
        _api = new GenesisApiClient(apiBaseUrl);
        ApplyLanguageFromSettings();
        InitializeComponent();
        Title = _tr.Tr("app.window_title");
        BuildNavigation();
        // Deep-Review-Hinweis (Sitzung 2, Profil C#/.NET): dies sind
        // "async void"-artige Event-Handler (der Lambda-Rueckgabetyp ist
        // technisch void, der Delegat aber async). Das ist im Allgemeinen
        // riskant, weil eine nicht abgefangene Exception im async-Teil den
        // WPF-Dispatcher direkt zum Absturz bringen kann (sie kann von
        // keinem umgebenden try/catch mehr gefangen werden). Hier ist es
        // aktuell sicher, WEIL ShowDashboardAsync()/OnNavigationSelectedAsync()
        // ihrerseits ihre gesamte Fehlerbehandlung intern per try/catch
        // abschliessen (siehe unten) und selbst NIE eine Exception nach
        // aussen werfen. Wird eine der beiden Methoden spaeter erweitert,
        // MUSS diese Eigenschaft erhalten bleiben - sonst zuerst auf
        // ein explizites async-Command-Pattern (z.B. IAsyncRelayCommand)
        // umstellen statt direkt an das Event zu haengen.
        Loaded += async (_, _) => await ShowDashboardAsync();
    }

    /// <summary>
    /// Liest `general.language` beim Start einmalig vom Core Service (§53:
    /// Sprache ist eine GUI-Einstellung, kein manuell editiertes
    /// Konfigurationsfeld) - identisches Verhalten zu
    /// ui-reference-pyside/genesis_ui/main_window.py::_apply_language_from_settings.
    /// Ist die API beim Start nicht erreichbar oder liefert sie einen
    /// Fehler, bleibt es beim Default (Deutsch) - kein Absturz, kein
    /// stiller Blockzustand (Prinzip "kein stiller Fehlschlag", aber auch
    /// kein harter Start-Abbruch nur wegen einer (noch) nicht laufenden
    /// Core-API).
    /// </summary>
    private void ApplyLanguageFromSettings()
    {
        try
        {
            var settings = _api.GetSettingsAsync().GetAwaiter().GetResult();
            if (settings?.General?.Language is { } language)
            {
                Translator.ConfigureDefaultLanguage(language);
            }
        }
        catch (Exception)
        {
            // Bewusst breit gefangen: Sprachumschaltung ist ein rein
            // kosmetisches Startverhalten, darf den App-Start nie verhindern.
        }
    }

    private static string NavIcon(string key) => key switch
    {
        "nav.dashboard" => "\uE80F",
        "nav.music" => "\uE8D6",
        "nav.audiobook" => "\uE7F6",
        "nav.movie" => "\uE714",
        "nav.episode" => "\uE7F4",
        "nav.podcast" => "\uE720",
        "nav.ai_music" => "\uE8D6",
        "nav.unknown" => "\uE946",
        "nav.search" => "\uE721",
        "nav.artists" => "\uE77B",
        "nav.albums" => "\uE8D6",
        "nav.titles" => "\uE8A5",
        "nav.genres" => "\uE8EC",
        "nav.persons" => "\uE77B",
        "nav.sources" => "\uE71B",
        "nav.media_analysis" => "\uE9D9",
        "nav.metadata_editor" => "\uE70F",
        "nav.rename" => "\uE8AC",
        "nav.loudness" => "\uE767",
        "nav.cutter" => "\uE8BB",
        "nav.convert" => "\uE8AB",
        "nav.audio_recognition" => "\uE8D6",
        "nav.duplicates" => "\uE8DE",
        "nav.quality_check" => "\uE73E",
        "nav.artwork" => "\uE91B",
        "nav.download_center" => "\uE896",
        "nav.import" => "\uE8E5",
        "nav.ai_metadata" => "\uE70F",
        "nav.ai_audio_analysis" => "\uE8D6",
        "nav.voice_studio" => "\uE767",
        "nav.tts" => "\uE8D6",
        "nav.settings" => "\uE713",
        "nav.databases" => "\uE7B8",
        "nav.providers" => "\uE71B",
        "nav.plugins" => "\uE74C",
        "nav.licenses" => "\uE8A5",
        "nav.logs" => "\u7B97",
        "nav.backups" => "\uE777",
        "nav.diagnostics" => "\uE9D9",
        "nav.job_queue" => "\uE823",
        "nav.error_center" => "\uEA39",
        _ => "\uE10F",
    };

    private void BuildNavigation()
    {
        foreach (var (sectionKey, itemKeys) in NavStructure)
        {
            var sectionHeader = new TextBlock
            {
                Text = _tr.Tr(sectionKey).ToUpperInvariant(),
                FontSize = 10,
                FontWeight = FontWeights.SemiBold,
                Foreground = (Brush)Application.Current.Resources["TextMutedBrush"],
                Margin = new Thickness(12, 10, 0, 4),
            };
            var sectionItem = new TreeViewItem
            {
                Header = sectionHeader,
                IsExpanded = true,
                IsHitTestVisible = false,
            };
            foreach (var itemKey in itemKeys)
            {
                var icon = new TextBlock
                {
                    Text = NavIcon(itemKey),
                    FontFamily = new FontFamily("Segoe MDL2 Assets"),
                    FontSize = 16,
                    Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"],
                };
                var label = new TextBlock
                {
                    Text = _tr.Tr(itemKey),
                    FontSize = 13,
                    VerticalAlignment = VerticalAlignment.Center,
                };
                var child = new TreeViewItem
                {
                    Header = label,
                    Tag = itemKey,
                };
                child.Tag = itemKey;
                child.SetValue(FrameworkElement.ToolTipProperty, _tr.Tr(itemKey));
                // The template uses Tag as the icon content, so keep the i18n key
                // in the header element and expose the icon through Header's Tag.
                child.Resources["NavigationIcon"] = icon;
                child.Header = new StackPanel
                {
                    Orientation = Orientation.Horizontal,
                    Children = { icon, new TextBlock { Text = _tr.Tr(itemKey), Margin = new Thickness(10, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center } },
                };
                child.Selected += async (_, _) => await OnNavigationSelectedAsync(itemKey);
                sectionItem.Items.Add(child);
            }
            NavTree.Items.Add(sectionItem);
        }
    }

    private void ProfileButton_Click(object sender, RoutedEventArgs e)
    {
        foreach (var item in NavTree.Items.OfType<TreeViewItem>())
        {
            foreach (var child in item.Items.OfType<TreeViewItem>())
            {
                if (child.Tag is "nav.settings")
                {
                    child.IsSelected = true;
                    return;
                }
            }
        }
    }

    private async Task OnNavigationSelectedAsync(string itemKey)
    {
        // Der Job-Warteschlange-Autoaktualisierungstimer (siehe
        // MainWindow.JobQueue.cs) darf nicht weiterlaufen, sobald der
        // Nutzer die Seite verlaesst - sonst liefen unnoetige API-Aufrufe
        // im Hintergrund weiter. ShowJobQueueAsync() startet ihn bei Bedarf
        // selbst wieder.
        if (itemKey != "nav.job_queue")
        {
            _jobQueueTimer?.Stop();
        }

        if (itemKey == "nav.dashboard")
        {
            await ShowDashboardAsync();
        }
        else if (itemKey == "nav.settings")
        {
            await ShowSettingsAsync();
        }
        else if (itemKey == "nav.providers")
        {
            await ShowProvidersAsync();
        }
        else if (MediaTableSupport.MediaKindByNavKey.TryGetValue(itemKey, out var kind))
        {
            await ShowMediaTableAsync(itemKey, kind);
        }
        else if (LibraryBrowserSupport.LibraryKindByNavKey.TryGetValue(itemKey, out var libraryKind))
        {
            await ShowLibraryAsync(libraryKind, itemKey);
        }
        else if (itemKey == "nav.duplicates")
        {
            await ShowDuplicatesAsync();
        }
        else if (itemKey == "nav.download_center" || itemKey == "nav.import")
        {
            await ShowDownloadCenterAsync();
        }
        else if (itemKey == "nav.ai_metadata")
        {
            await ShowAiCenterAsync();
        }
        else if (itemKey == "nav.voice_studio" || itemKey == "nav.tts")
        {
            await ShowVoiceStudioAsync();
        }
        else if (itemKey == "nav.plugins")
        {
            await ShowPluginsAsync();
        }
        else if (itemKey == "nav.logs")
        {
            await ShowLogViewerAsync();
        }
        else if (itemKey == "nav.backups")
        {
            await ShowBackupsAsync();
        }
        else if (itemKey == "nav.diagnostics")
        {
            await ShowDiagnosticsAsync();
        }
        else if (itemKey == "nav.job_queue")
        {
            await ShowJobQueueAsync();
        }
        else if (itemKey == "nav.error_center")
        {
            await ShowErrorCenterAsync();
        }
        else
        {
            MainContent.Content = new TextBlock
            {
                Text = _tr.Tr("app.placeholder_note"),
                TextWrapping = TextWrapping.Wrap,
            };
        }
    }

    private async Task ShowDashboardAsync()
    {
        try
        {
            var summary = await _api.GetDashboardSummaryAsync();
            var health = await _api.GetHealthAsync();
            UpdateConnectionStatus(health);

            var root = new ScrollViewer
            {
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            };
            var panel = new StackPanel
            {
                Background = (Brush)Application.Current.Resources["BackgroundBrush"],
            };

            var heading = new TextBlock
            {
                Text = _tr.Tr("dashboard.title"),
                FontSize = 30,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 4, 0, 4),
            };
            panel.Children.Add(heading);

            if (summary is not null)
            {
                var subtitle = new TextBlock
                {
                    Text = _tr.Tr("dashboard.card_total") + ": " + summary.Total.ToString("N0"),
                    FontSize = 13,
                    Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"],
                    Margin = new Thickness(0, 0, 0, 20),
                };
                panel.Children.Add(subtitle);

                var cards = new UniformGrid { Columns = 4, Rows = 1, Margin = new Thickness(0, 0, 0, 18) };
                AddDashboardCard(cards, _tr.Tr("nav.music"), summary.CountsByKind.GetValueOrDefault("music"), "\uE8D6", 0);
                AddDashboardCard(cards, _tr.Tr("nav.audiobook"), summary.CountsByKind.GetValueOrDefault("audiobook"), "\uE7F6", 1);
                AddDashboardCard(cards, _tr.Tr("nav.movie"), summary.CountsByKind.GetValueOrDefault("movie"), "\uE714", 2);
                AddDashboardCard(cards, _tr.Tr("nav.episode"), summary.CountsByKind.GetValueOrDefault("episode"), "\uE7F4", 3);
                panel.Children.Add(cards);

                var actionBar = new WrapPanel { Margin = new Thickness(0, 0, 0, 20) };
                AddPillButton(actionBar, "\uE8D6", _tr.Tr("nav.music"), () => SelectNavigation("nav.music"));
                AddPillButton(actionBar, "\uE721", _tr.Tr("nav.search"), () => SelectNavigation("nav.search"));
                AddPillButton(actionBar, "\uE8A5", _tr.Tr("nav.metadata_editor"), () => SelectNavigation("nav.metadata_editor"));
                AddPillButton(actionBar, "\uE713", _tr.Tr("nav.settings"), () => SelectNavigation("nav.settings"));
                panel.Children.Add(actionBar);

                var statsGrid = new UniformGrid { Columns = 3, Rows = 1, Margin = new Thickness(0, 0, 0, 18) };
                AddStatCard(statsGrid, _tr.Tr("dashboard.card_missing"), summary.MissingFiles, "\uE8A7");
                AddStatCard(statsGrid, _tr.Tr("dashboard.card_not_analyzed"), summary.NotYetAnalyzed, "\uE9D9");
                AddStatCard(statsGrid, _tr.Tr("dashboard.card_running_jobs"), summary.RunningJobs, "\uE823");
                panel.Children.Add(statsGrid);
            }

            if (health is not null)
            {
                var status = new Border
                {
                    Background = (Brush)Application.Current.Resources["SurfaceBrush"],
                    BorderBrush = (Brush)Application.Current.Resources["BorderBrush"],
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(16),
                    Padding = new Thickness(16, 12),
                };
                status.Child = new TextBlock
                {
                    Text = _tr.Tr("dashboard.status",
                        ("version", health.Version),
                        ("ai_provider", health.AiProvider),
                        ("ai_status", _tr.Tr(health.AiAvailable ? "dashboard.ai_reachable" : "dashboard.ai_unreachable")),
                        ("mode", _tr.Tr(health.SafeTestMode ? "app.state_on" : "app.state_off"))),
                    Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"],
                    TextWrapping = TextWrapping.Wrap,
                };
                panel.Children.Add(status);
            }

            root.Content = panel;
            MainContent.Content = root;
        }
        catch (Exception ex)
        {
            UpdateConnectionStatus(null);
            MainContent.Content = new Border
            {
                Background = (Brush)Application.Current.Resources["SurfaceBrush"],
                BorderBrush = (Brush)Application.Current.Resources["BorderBrush"],
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(16),
                Padding = new Thickness(20),
                Child = new TextBlock
                {
                    Text = _tr.Tr("dashboard.error", ("error", ex.Message)),
                    TextWrapping = TextWrapping.Wrap,
                },
            };
        }
    }

    private void UpdateConnectionStatus(HealthResponse? health)
    {
        if (ConnectionStatusText is null || ConnectionDot is null) return;
        if (health is null)
        {
            ConnectionStatusText.Text = _tr.Tr("app.unreachable_short");
            ConnectionStatusText.Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"];
            ConnectionDot.Fill = (Brush)Application.Current.Resources["TextMutedBrush"];
            return;
        }
        ConnectionStatusText.Text = _tr.Tr("app.connected_short");
        ConnectionStatusText.ToolTip = _tr.Tr("app.status_connected", ("version", health.Version), ("mode", _tr.Tr(health.SafeTestMode ? "app.state_on" : "app.state_off")));
        ConnectionStatusText.Foreground = (Brush)Application.Current.Resources["SuccessTextBrush"];
        ConnectionDot.Fill = (Brush)Application.Current.Resources["SuccessBrush"];
    }

    private void AddDashboardCard(Panel parent, string title, int value, string iconGlyph, int accentIndex)
    {
        var card = new Border
        {
            Background = (Brush)Application.Current.Resources["CardBrush"],
            BorderBrush = (Brush)Application.Current.Resources["BorderBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(18),
            Margin = new Thickness(0, 0, 10, 0),
            Padding = new Thickness(18),
            MinHeight = 132,
        };
        var grid = new Grid();
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var top = new DockPanel();
        var icon = new Border
        {
            Width = 38, Height = 38, CornerRadius = new CornerRadius(11),
            Background = (Brush)Application.Current.Resources["AccentSoftBrush"],
            Child = new TextBlock
            {
                Text = iconGlyph, FontFamily = new FontFamily("Segoe MDL2 Assets"), FontSize = 18,
                Foreground = (Brush)Application.Current.Resources["AccentBrush"],
                HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center,
            },
        };
        DockPanel.SetDock(icon, Dock.Right);
        top.Children.Add(icon);
        top.Children.Add(new TextBlock { Text = title, FontSize = 13, Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"], VerticalAlignment = VerticalAlignment.Center });
        grid.Children.Add(top);
        var valueText = new TextBlock
        {
            Text = value.ToString("N0"), FontSize = 34, FontWeight = FontWeights.Bold,
            Foreground = (Brush)Application.Current.Resources["AccentBrush"], VerticalAlignment = VerticalAlignment.Center,
        };
        Grid.SetRow(valueText, 1);
        grid.Children.Add(valueText);
        var line = new Border { Height = 3, CornerRadius = new CornerRadius(2), Background = (Brush)Application.Current.Resources["AccentGradientBrush"], HorizontalAlignment = HorizontalAlignment.Left, Width = 48 };
        Grid.SetRow(line, 2);
        grid.Children.Add(line);
        card.Child = grid;
        parent.Children.Add(card);
    }

    private void AddStatCard(Panel parent, string title, int value, string iconGlyph)
    {
        var card = new Border
        {
            Background = (Brush)Application.Current.Resources["SurfaceBrush"],
            BorderBrush = (Brush)Application.Current.Resources["BorderBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(16),
            Margin = new Thickness(0, 0, 10, 0),
            Padding = new Thickness(16),
        };
        var stack = new StackPanel();
        stack.Children.Add(new TextBlock { Text = iconGlyph, FontFamily = new FontFamily("Segoe MDL2 Assets"), FontSize = 16, Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"] });
        stack.Children.Add(new TextBlock { Text = value.ToString("N0"), FontSize = 24, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 6, 0, 2) });
        stack.Children.Add(new TextBlock { Text = title, FontSize = 12, Foreground = (Brush)Application.Current.Resources["TextSecondaryBrush"] });
        card.Child = stack;
        parent.Children.Add(card);
    }

    private void AddPillButton(Panel parent, string iconGlyph, string text, Action action)
    {
        var button = new Button { Style = (Style)Application.Current.Resources["PillButtonStyle"], Margin = new Thickness(0, 0, 8, 8) };
        var row = new StackPanel { Orientation = Orientation.Horizontal };
        row.Children.Add(new TextBlock { Text = iconGlyph, FontFamily = new FontFamily("Segoe MDL2 Assets"), FontSize = 14, Margin = new Thickness(0, 0, 8, 0) });
        row.Children.Add(new TextBlock { Text = text, VerticalAlignment = VerticalAlignment.Center });
        button.Content = row;
        button.Click += (_, _) => action();
        parent.Children.Add(button);
    }

    private void SelectNavigation(string key)
    {
        foreach (var section in NavTree.Items.OfType<TreeViewItem>())
        {
            foreach (var child in section.Items.OfType<TreeViewItem>())
            {
                if (child.Tag is string tag && tag == key)
                {
                    child.IsSelected = true;
                    return;
                }
            }
        }
    }

    // --- Medientabelle (Gap K, inkrementelle Parity-Arbeit) ------------------
    //
    // Erste von mehreren geplanten WPF-Ansichten jenseits des Dashboards
    // (Nutzerentscheidung: "inkrementell", siehe DECISIONS.md/PROGRESS.md
    // Sitzung 14). Deckt dieselbe "/media"+"/media/{id}"-API ab wie
    // ui-reference-pyside/genesis_ui/views/media_table.py, aber bewusst mit
    // reduziertem Funktionsumfang in diesem ersten Schritt: Suche, Tabelle,
    // Detailpanel (Pfad/Groesse/Format/Technik/Track-Metadaten). NOCH NICHT
    // enthalten (bewusst zurueckgestellt fuer eine Folge-Session, siehe
    // GAP_ANALYSIS.md Gap K): Qualitaetspruefung/Loudness/KI-Analyse/
    // Quellen-Abschnitt im Detailpanel (benoetigen weitere, in
    // GenesisApiClient.cs noch fehlende Endpunkt-Methoden), Kontextmenue,
    // Mehrfachauswahl-Aktionen, erweiterte Filter (Pendant zu
    // SearchFiltersDialog), eingebetteter Player.
    private async Task ShowMediaTableAsync(string navItemKey, string? kind)
    {
        var root = new Grid { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        // Gap K, siebter inkrementeller Schritt - zusaetzliche Zeile fuer
        // die Werkzeugleiste (Filter/Datei oeffnen/Ordner oeffnen/Pfad
        // kopieren + Play/Pause/Stop) zwischen Suchzeile und Tabelle. Der
        // eingebettete Player (§60, Gap-Analyse G) hat seine eigene Zeile
        // unter dem Detailpanel (siehe RowDefinition unten).
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        // Hoehe gegenueber dem reinen Textpanel (vormals 160) vergroessert,
        // damit die Cover-Vorschau (§8/§22/§59 "COVER", Gap-Analyse D)
        // links davon Platz hat, ohne winzig zu wirken.
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(220) });
        // §60 (Gap-Analyse G) - zusaetzliche Zeile fuer die persistente
        // Wiedergabeleiste UNTER dem Detailpanel (dieselbe Position wie in
        // der Python-Referenz: root.addWidget(self.player_bar) nach dem
        // Splitter, bleibt beim Wechsel der Auswahl/beim Neuladen sichtbar).
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var title = new TextBlock
        {
            Text = _tr.Tr(navItemKey), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 12),
        };
        Grid.SetRow(title, 0);
        root.Children.Add(title);

        var searchRow = new DockPanel { Margin = new Thickness(0, 0, 0, 8) };
        var searchButton = new Button
        {
            Content = _tr.Tr("media_table.search_button"), Padding = new Thickness(12, 4, 12, 4),
        };
        DockPanel.SetDock(searchButton, Dock.Right);
        var searchBox = new TextBox
        {
            MinWidth = 240, VerticalContentAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 8, 0),
            Text = string.Empty,
        };
        // Platzhaltertext (§53-konform aus i18n) wird hier als Tag statt als
        // echtes WPF-Placeholder-Feature gesetzt, da TextBox dieses Feature
        // nativ nicht kennt - ausreichend fuer diesen ersten Inkrement.
        searchBox.ToolTip = _tr.Tr("media_table.search_placeholder");
        DockPanel.SetDock(searchBox, Dock.Left);
        searchRow.Children.Add(searchButton);
        searchRow.Children.Add(searchBox);
        Grid.SetRow(searchRow, 1);
        root.Children.Add(searchRow);

        // --- Werkzeugleiste: Filter + Datei-/Ordner-Aktionen (§8/§61, Gap-
        // Analyse C/E) + Werkzeug-Dialoge (Gap K, achter inkrementeller
        // Schritt - dieselbe Reihenfolge wie media_table.py::action_row/
        // _build_context_menu: Abspielen, Metadaten, Umbenennen, Artwork,
        // Lautheit, Cutter, Konvertieren, Fingerprint, Qualitaet, Hoerbuch,
        // Video, KI, Datei/Ordner oeffnen, Pfad kopieren). Alle bis auf
        // "Filter" sind zu Beginn deaktiviert und werden erst durch
        // UpdateButtonStates() (siehe unten, ausgeloest bei jeder
        // Aenderung der Tabellenauswahl) passend (de)aktiviert - identisch
        // zur anfaenglichen setEnabled(False) + _on_selection_changed() in
        // der Python-Referenz. ----------------------------------------------
        var filtersBtn = new Button { Content = _tr.Tr("media_table.filters_button"), Margin = new Thickness(0, 0, 8, 0) };
        var openFileBtn = new Button { Content = _tr.Tr("media_table.open_file_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var openFolderBtn = new Button { Content = _tr.Tr("media_table.open_folder_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var copyPathBtn = new Button { Content = _tr.Tr("media_table.copy_path_button"), Margin = new Thickness(0, 0, 16, 0), IsEnabled = false };
        var playBtn = new Button { Content = _tr.Tr("player_bar.play_button"), Margin = new Thickness(0, 0, 4, 0), IsEnabled = false };
        var pauseBtn = new Button { Content = _tr.Tr("player_bar.pause_button"), Margin = new Thickness(0, 0, 4, 0) };
        var stopBtn = new Button { Content = _tr.Tr("player_bar.stop_button"), Margin = new Thickness(0, 0, 16, 0) };
        var metadataBtn = new Button { Content = _tr.Tr("media_table.metadata_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var renameBtn = new Button { Content = _tr.Tr("media_table.rename_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var artworkBtn = new Button { Content = _tr.Tr("media_table.artwork_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var loudnessBtn = new Button { Content = _tr.Tr("media_table.loudness_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var cutterBtn = new Button { Content = _tr.Tr("media_table.cutter_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var convertBtn = new Button { Content = _tr.Tr("media_table.convert_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var fingerprintBtn = new Button { Content = _tr.Tr("media_table.fingerprint_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var qualityBtn = new Button { Content = _tr.Tr("media_table.quality_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var audiobookBtn = new Button { Content = _tr.Tr("media_table.audiobook_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var videoBtn = new Button { Content = _tr.Tr("media_table.video_button"), Margin = new Thickness(0, 0, 8, 0), IsEnabled = false };
        var aiBtn = new Button { Content = _tr.Tr("media_table.ai_button"), Margin = new Thickness(0, 0, 16, 0), IsEnabled = false };
        var toolbarRow = new WrapPanel { Margin = new Thickness(0, 0, 0, 8) };
        toolbarRow.Children.Add(filtersBtn);
        toolbarRow.Children.Add(openFileBtn);
        toolbarRow.Children.Add(openFolderBtn);
        toolbarRow.Children.Add(copyPathBtn);
        toolbarRow.Children.Add(playBtn);
        toolbarRow.Children.Add(pauseBtn);
        toolbarRow.Children.Add(stopBtn);
        toolbarRow.Children.Add(metadataBtn);
        toolbarRow.Children.Add(renameBtn);
        toolbarRow.Children.Add(artworkBtn);
        toolbarRow.Children.Add(loudnessBtn);
        toolbarRow.Children.Add(cutterBtn);
        toolbarRow.Children.Add(convertBtn);
        toolbarRow.Children.Add(fingerprintBtn);
        toolbarRow.Children.Add(qualityBtn);
        toolbarRow.Children.Add(audiobookBtn);
        toolbarRow.Children.Add(videoBtn);
        toolbarRow.Children.Add(aiBtn);
        Grid.SetRow(toolbarRow, 2);
        root.Children.Add(toolbarRow);

        // --- Persistente Wiedergabeleiste (§60, Gap-Analyse G) - Pendant zu
        // ui-reference-pyside/genesis_ui/widgets/player_bar.py. Neben den
        // Play/Pause/Stop-Buttons in der Werkzeugleiste oben (die das
        // Kontextmenue per RaiseEvent wiederverwendet, daher dort bewusst
        // NICHT dupliziert) bietet die Leiste: Titelanzeige, Suchregler
        // (Seek), Zeit-/Daueranzeige, Lautstaerkeregler, Fehleranzeige und
        // ein Videobild ausschliesslich fuer Film-/Serien-Episoden
        // (VIDEO_KINDS in player_bar.py) - reine Audiowiedergabe braucht
        // kein Bildfenster. ----------------------------------------------
        var player = new MediaElement
        {
            LoadedBehavior = MediaState.Manual,
            UnloadedBehavior = MediaState.Manual,
            Height = 0,
            Visibility = Visibility.Collapsed,
        };
        var playerTitleText = new TextBlock { Text = _tr.Tr("player_bar.no_media"), Margin = new Thickness(0, 8, 0, 2) };
        var positionLabel = new TextBlock { Text = MediaPlayerSupport.FormatTime(0), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 4, 0) };
        var durationLabel = new TextBlock { Text = MediaPlayerSupport.FormatTime(0), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(4, 0, 8, 0) };
        var seekSlider = new Slider { Minimum = 0, Maximum = 0, IsEnabled = false, VerticalAlignment = VerticalAlignment.Center };
        var volumeLabelText = new TextBlock { Text = _tr.Tr("player_bar.volume_label"), VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(8, 0, 4, 0) };
        // Default 80 = 0.8 Lautstaerke wie player_bar.py
        var volumeSlider = new Slider { Minimum = 0, Maximum = 100, Value = 80, Width = 120, VerticalAlignment = VerticalAlignment.Center };
        var playerErrorText = new TextBlock { Text = string.Empty, TextWrapping = TextWrapping.Wrap };

        var playerControlsRow = new DockPanel { Margin = new Thickness(0, 2, 0, 0) };
        playerControlsRow.Children.Add(positionLabel);
        var volumeBox = new StackPanel { Orientation = Orientation.Horizontal };
        volumeBox.Children.Add(volumeLabelText);
        volumeBox.Children.Add(volumeSlider);
        DockPanel.SetDock(volumeBox, Dock.Right);
        playerControlsRow.Children.Add(volumeBox);
        DockPanel.SetDock(durationLabel, Dock.Right);
        playerControlsRow.Children.Add(durationLabel);
        // Suchregler fuellt den verbleibenden Platz zwischen Zeit- und
        // Daueranzeige (LastChildFill-Standard des DockPanel).
        playerControlsRow.Children.Add(seekSlider);

        var playerBar = new StackPanel { Margin = new Thickness(0, 8, 0, 0) };
        playerBar.Children.Add(player);
        playerBar.Children.Add(playerTitleText);
        playerBar.Children.Add(playerControlsRow);
        playerBar.Children.Add(playerErrorText);
        Grid.SetRow(playerBar, 5);
        root.Children.Add(playerBar);

        // Wird zu Beginn von ReloadAsync() aufgerufen (Parity zu
        // stop_and_clear() in player_bar.py, aufgerufen in
        // media_table.py::refresh()) - die eigentliche Implementierung
        // wird unten bei der Player-Verdrahtung zugewiesen; die
        // Leeraktions-Vorbelegung macht die Methode unabhaengig von der
        // textuellen Reihenfolge der Initialisierungen.
        Action stopAndClearPlayer = () => { };

        var grid = new DataGrid
        {
            AutoGenerateColumns = false,
            IsReadOnly = true,
            CanUserAddRows = false,
            // Extended statt Single (Gap K, achter Schritt) - "Umbenennen"
            // wirkt wie in media_table.py auf eine Mehrfachauswahl, alle
            // anderen Werkzeuge bleiben auf Einzelauswahl beschraenkt
            // (siehe UpdateButtonStates unten).
            SelectionMode = DataGridSelectionMode.Extended,
            SelectionUnit = DataGridSelectionUnit.FullRow,
            Margin = new Thickness(0, 0, 0, 8),
            // Parity zu ui-reference-pyside (keine interaktive Spalten-
            // sortierung dort implementiert, §53). Hier zwar unkritisch, da
            // die Selektion ueber SelectedItems als MediaItem erfolgt
            // (sortierresistent), aber fuer Konsistenz trotzdem deaktiviert.
            CanUserSortColumns = false,
        };
        var thumbnailColumn = new DataGridTemplateColumn { Header = "", Width = new DataGridLength(56) };
        var thumbTemplate = new DataTemplate();
        var thumbRoot = new FrameworkElementFactory(typeof(Grid));
        thumbRoot.SetValue(FrameworkElement.WidthProperty, 38.0);
        thumbRoot.SetValue(FrameworkElement.HeightProperty, 38.0);
        thumbRoot.SetValue(FrameworkElement.MarginProperty, new Thickness(0, 2, 0, 2));
        var thumbPlaceholder = new FrameworkElementFactory(typeof(Border));
        thumbPlaceholder.SetValue(Border.BackgroundProperty, new SolidColorBrush(Color.FromRgb(39, 48, 65)));
        thumbPlaceholder.SetValue(Border.CornerRadiusProperty, new CornerRadius(9));
        var thumbGlyph = new FrameworkElementFactory(typeof(TextBlock));
        thumbGlyph.SetValue(TextBlock.TextProperty, "\uE8D6");
        thumbGlyph.SetValue(TextBlock.FontFamilyProperty, new FontFamily("Segoe MDL2 Assets"));
        thumbGlyph.SetValue(TextBlock.FontSizeProperty, 15.0);
        thumbGlyph.SetValue(TextBlock.ForegroundProperty, (Brush)Application.Current.Resources["TextSecondaryBrush"]);
        thumbGlyph.SetValue(TextBlock.HorizontalAlignmentProperty, HorizontalAlignment.Center);
        thumbGlyph.SetValue(TextBlock.VerticalAlignmentProperty, VerticalAlignment.Center);
        thumbPlaceholder.AppendChild(thumbGlyph);
        thumbRoot.AppendChild(thumbPlaceholder);
        var thumbFactory = new FrameworkElementFactory(typeof(Image));
        thumbFactory.SetValue(FrameworkElement.WidthProperty, 38.0);
        thumbFactory.SetValue(FrameworkElement.HeightProperty, 38.0);
        thumbFactory.SetValue(Image.StretchProperty, Stretch.UniformToFill);
        thumbFactory.SetValue(Image.VisibilityProperty, Visibility.Visible);
        thumbFactory.SetBinding(FrameworkElement.TagProperty, new Binding(nameof(MediaItem.Id)));
        thumbFactory.AddHandler(FrameworkElement.LoadedEvent, new RoutedEventHandler(async (sender, _) => await LoadThumbnailAsync(sender)));
        thumbRoot.AppendChild(thumbFactory);
        thumbTemplate.VisualTree = thumbRoot;
        thumbnailColumn.CellTemplate = thumbTemplate;
        grid.Columns.Add(thumbnailColumn);

        grid.Columns.Add(new DataGridTextColumn
        {
            Header = _tr.Tr("media_table.column_title"),
            Binding = new Binding(nameof(MediaItem.Filename)), Width = new DataGridLength(3, DataGridLengthUnitType.Star),
        });
        grid.Columns.Add(new DataGridTextColumn
        {
            Header = _tr.Tr("media_table.column_kind"),
            Binding = new Binding(nameof(MediaItem.Kind)), Width = DataGridLength.Auto,
        });
        var formatColumn = new DataGridTemplateColumn { Header = _tr.Tr("media_table.column_format"), Width = DataGridLength.Auto };
        var formatTemplate = new DataTemplate();
        var formatBorder = new FrameworkElementFactory(typeof(Border));
        formatBorder.SetValue(Border.BackgroundProperty, new SolidColorBrush(Color.FromRgb(55, 72, 105)));
        formatBorder.SetValue(Border.CornerRadiusProperty, new CornerRadius(8));
        formatBorder.SetValue(Border.PaddingProperty, new Thickness(8, 3, 8, 3));
        var formatText = new FrameworkElementFactory(typeof(TextBlock));
        formatText.SetValue(TextBlock.ForegroundProperty, Brushes.White);
        formatText.SetValue(TextBlock.FontSizeProperty, 11.0);
        formatText.SetBinding(TextBlock.TextProperty, new Binding(nameof(MediaItem.Extension)));
        formatBorder.AppendChild(formatText);
        formatTemplate.VisualTree = formatBorder;
        formatColumn.CellTemplate = formatTemplate;
        grid.Columns.Add(formatColumn);
        grid.Columns.Add(new DataGridTextColumn
        {
            Header = _tr.Tr("media_table.column_size"),
            Binding = new Binding(nameof(MediaItem.SizeBytes)) { StringFormat = "N0" }, Width = DataGridLength.Auto,
        });
        grid.Columns.Add(new DataGridTextColumn
        {
            Header = _tr.Tr("media_table.column_path"),
            Binding = new Binding(nameof(MediaItem.AbsolutePath)), Width = new DataGridLength(4, DataGridLengthUnitType.Star),
        });
        Grid.SetRow(grid, 3);
        root.Children.Add(grid);

        var detailPanel = new TextBox
        {
            IsReadOnly = true, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            FontFamily = new System.Windows.Media.FontFamily("Consolas"),
            Text = _tr.Tr("media_table.detail_placeholder"),
        };

        // §8/§59 - "COVER" ist laut Spezifikation der ERSTE Bestandteil der
        // Detailansicht (Gap-Analyse D: vorher wurde Artwork nirgends in
        // der UI tatsaechlich angezeigt, nur ueber den Artwork-Dialog
        // bearbeitet). Links neben dem Textpanel statt darueber platziert
        // (Anpassung an die bestehende Grid-Zeilenhoehe dieser .NET-
        // Oberflaeche, funktional identisch zum Python-Vorbild: zeigt das
        // eingebettete/gespeicherte Artwork, sonst den "kein Cover"-Text).
        const double coverSize = 200;
        var coverImage = new Image
        {
            Width = coverSize, Height = coverSize, Stretch = Stretch.Uniform,
            Margin = new Thickness(0, 0, 12, 0), Visibility = Visibility.Collapsed,
        };
        var coverPlaceholder = new TextBlock
        {
            Text = _tr.Tr("media_table.detail.no_cover"), TextWrapping = TextWrapping.Wrap,
            TextAlignment = TextAlignment.Center, VerticalAlignment = VerticalAlignment.Center,
            Width = coverSize, Height = coverSize, Margin = new Thickness(0, 0, 12, 0), Opacity = 0.7,
        };

        void ResetCover()
        {
            coverImage.Source = null;
            coverImage.Visibility = Visibility.Collapsed;
            coverPlaceholder.Visibility = Visibility.Visible;
        }

        ResetCover();

        var detailRow = new Grid();
        detailRow.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        detailRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        Grid.SetColumn(coverImage, 0);
        Grid.SetColumn(coverPlaceholder, 0);
        Grid.SetColumn(detailPanel, 1);
        detailRow.Children.Add(coverImage);
        detailRow.Children.Add(coverPlaceholder);
        detailRow.Children.Add(detailPanel);
        Grid.SetRow(detailRow, 4);
        root.Children.Add(detailRow);

        MainContent.Content = root;

        MediaSearchFilters? activeFilters = null;
        MediaItem? selectedItem = null;
        var thumbnailCache = new Dictionary<int, BitmapImage?>();

        async Task LoadThumbnailAsync(object sender)
        {
            if (sender is not Image image || image.Tag is not int mediaId) return;
            if (thumbnailCache.TryGetValue(mediaId, out var cached))
            {
                image.Source = cached;
                return;
            }
            try
            {
                var artwork = await _api.GetArtworkBytesAsync(mediaId);
                if (artwork is null || !MediaCoverSupport.LooksLikeDecodableImage(artwork.Value.Data))
                {
                    thumbnailCache[mediaId] = null;
                    return;
                }
                using var stream = new MemoryStream(artwork.Value.Data);
                var bitmap = new BitmapImage();
                bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad;
                bitmap.DecodePixelWidth = 72;
                bitmap.StreamSource = stream;
                bitmap.EndInit();
                bitmap.Freeze();
                thumbnailCache[mediaId] = bitmap;
                image.Source = bitmap;
            }
            catch
            {
                thumbnailCache[mediaId] = null;
            }
        }

        async Task ReloadAsync(string? search)
        {
            // Parity zu media_table.py::refresh(): Eine neu geladene
            // Trefferliste kann die gerade spielende Datei enthalten oder
            // auch nicht - in beiden Faellen ist "unsichtbar im Hintergrund
            // weiterspielen" das ueberraschendere Verhalten, daher wird die
            // Wiedergabe hier bewusst beendet (stop_and_clear()).
            stopAndClearPlayer();
            try
            {
                var response = await _api.ListMediaAsync(kind: kind, search: search, filters: activeFilters);
                grid.ItemsSource = response?.Items ?? new List<MediaItem>();
            }
            catch (Exception ex)
            {
                detailPanel.Text = _tr.Tr("media_table.error_api", ("error", ex.Message));
            }
        }

        searchButton.Click += async (_, _) => await ReloadAsync(searchBox.Text);
        searchBox.KeyDown += async (_, e) =>
        {
            if (e.Key == System.Windows.Input.Key.Enter)
            {
                await ReloadAsync(searchBox.Text);
            }
        };

        // --- Filter-Dialog (Pendant zu SearchFiltersDialog, §9, Gap-
        // Analyse C) --------------------------------------------------------
        filtersBtn.Click += async (_, _) =>
        {
            var result = ShowMediaFiltersDialog(activeFilters);
            if (result is null) return; // Abgebrochen - vorhandene Filter unveraendert.
            activeFilters = result == MediaSearchFiltersSupport.Empty ? null : result;
            filtersBtn.Content = activeFilters is null
                ? _tr.Tr("media_table.filters_button")
                : $"{_tr.Tr("media_table.filters_button")} ({activeFilters.CountActive()})";
            await ReloadAsync(searchBox.Text);
        };

        // --- Datei-/Ordner-Aktionen (§8/§61, Gap-Analyse E) - rein lesend/
        // anzeigend (Prinzip #4/#5), daher ohne Bestaetigungsdialog. --------
        openFileBtn.Click += (_, _) =>
        {
            if (selectedItem is null) return;
            if (!MediaFileActions.TryOpenPath(selectedItem.AbsolutePath, revealContainingFolder: false))
            {
                MessageBox.Show(
                    _tr.Tr("media_table.open_file_failed_text", ("path", selectedItem.AbsolutePath)),
                    _tr.Tr("media_table.open_file_failed_title"));
            }
        };
        openFolderBtn.Click += (_, _) =>
        {
            if (selectedItem is null) return;
            if (!MediaFileActions.TryOpenPath(selectedItem.AbsolutePath, revealContainingFolder: true))
            {
                MessageBox.Show(
                    _tr.Tr("media_table.open_folder_failed_text", ("path", selectedItem.AbsolutePath)),
                    _tr.Tr("media_table.open_folder_failed_title"));
            }
        };
        copyPathBtn.Click += (_, _) =>
        {
            if (selectedItem is null) return;
            Clipboard.SetText(selectedItem.AbsolutePath);
        };

        // --- Werkzeug-Dialoge (Gap K, achter inkrementeller Schritt) -------
        // Jeder Dialog meldet per Rueckgabewert, ob tatsaechlich etwas
        // geaendert wurde (Pendant zu `dialog.changed`/`dialog.applied` in
        // der Python-Referenz) - nur dann wird die Detailansicht neu
        // geladen, identisch zum jeweiligen `_on_..._clicked()`. Fuer
        // Umbenennen wird wie in `_on_rename_clicked()` die GESAMTE Tabelle
        // neu geladen (Dateiname/-pfad aendert sich, nicht nur Metadaten).
        List<MediaItem> SelectedItems() => grid.SelectedItems.Cast<MediaItem>().ToList();

        metadataBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowMetadataSuggestionsDialogAsync(item.Id, item.Filename))
            {
                await RefreshDetailAsync();
            }
        };
        renameBtn.Click += async (_, _) =>
        {
            var ids = SelectedItems().Select(i => i.Id).ToList();
            if (ids.Count == 0) return;
            if (await ShowRenameDialogAsync(ids))
            {
                await ReloadAsync(searchBox.Text);
            }
        };
        artworkBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowArtworkDialogAsync(item.Id, item.Filename))
            {
                await RefreshDetailAsync();
            }
        };
        loudnessBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowLoudnessDialogAsync(item.Id, item.Filename))
            {
                await RefreshDetailAsync();
            }
        };
        cutterBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowCutterDialogAsync(item.Id, item.Filename, item.AbsolutePath))
            {
                await RefreshDetailAsync();
            }
        };
        convertBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowConvertDialogAsync(item.Id, item.Filename))
            {
                await RefreshDetailAsync();
            }
        };
        fingerprintBtn.Click += async (_, _) =>
        {
            // Reine Analyse (kein confirm noetig, Prinzip #4/#5) - Vorstufe
            // fuer die Duplikaterkennung (§21, nav.duplicates).
            if (selectedItem is not { } item) return;
            try
            {
                var result = await _api.ComputeFingerprintAsync(item.Id);
                MessageBox.Show(
                    _tr.Tr("media_table.fingerprint_done_text", ("duration", result?.DurationSeconds.ToString("F1") ?? "")),
                    _tr.Tr("media_table.fingerprint_done_title"));
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("media_table.fingerprint_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
            }
        };
        qualityBtn.Click += async (_, _) =>
        {
            // Reine Analyse (kein confirm noetig) - Ergebnis ist IMMER ein
            // Verdacht, niemals ein Fakt (§20).
            if (selectedItem is not { } item) return;
            try
            {
                await _api.AnalyzeQualityAsync(item.Id);
            }
            catch (Exception ex)
            {
                MessageBox.Show(_tr.Tr("media_table.quality_failed", ("error", ex.Message)), _tr.Tr("common.error_title"));
                return;
            }
            MessageBox.Show(_tr.Tr("media_table.quality_done_text"), _tr.Tr("media_table.quality_done_title"));
            await RefreshDetailAsync();
        };
        audiobookBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowAudiobookDialogAsync(item.Id, item.Filename))
            {
                await RefreshDetailAsync();
            }
        };
        videoBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowVideoDialogAsync(item.Id, item.Filename))
            {
                await RefreshDetailAsync();
            }
        };
        aiBtn.Click += async (_, _) =>
        {
            if (selectedItem is not { } item) return;
            if (await ShowAiDialogAsync(item.Id, item.Filename, item.Kind))
            {
                await RefreshDetailAsync();
            }
        };

        // --- Eingebetteter Medienplayer (§60, Gap-Analyse G) - Pendant zu
        // player_bar.py: spielt die lokale Datei der aktuellen Auswahl
        // direkt ab (MediaElement, keine zusaetzliche Abhaengigkeit noetig),
        // mit Seek, Lautstaerke, Zeit-/Daueranzeige, Fehleranzeige und
        // Videobild fuer Film-/Serien-Medien. ---
        player.Volume = volumeSlider.Value / 100.0; // Default 0.8 wie player_bar.py
        volumeSlider.ValueChanged += (_, _) => player.Volume = volumeSlider.Value / 100.0;

        var positionTimer = new System.Windows.Threading.DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(250),
        };
        positionTimer.Tick += (_, _) =>
        {
            // Waehrend der Nutzer den Suchregler zieht, nicht
            // dazwischenfunken (Pendant zum isSliderDown()-Check in
            // player_bar.py::_on_position_changed).
            if (!seekSlider.IsMouseCaptureWithin && seekSlider.Maximum > 0)
            {
                seekSlider.Value = Math.Min(player.Position.TotalMilliseconds, seekSlider.Maximum);
            }
            positionLabel.Text = MediaPlayerSupport.FormatTime((long)player.Position.TotalMilliseconds);
        };

        player.MediaOpened += (_, _) =>
        {
            // Dauer erst nach dem Oeffnen bekannt (Pendant zu
            // durationChanged in player_bar.py).
            var durationMs = player.NaturalDuration.HasTimeSpan
                ? player.NaturalDuration.TimeSpan.TotalMilliseconds
                : 0;
            seekSlider.Maximum = Math.Max(durationMs, 0);
            seekSlider.IsEnabled = durationMs > 0;
            durationLabel.Text = MediaPlayerSupport.FormatTime((long)durationMs);
            positionTimer.Start();
        };
        player.MediaEnded += (_, _) =>
        {
            positionTimer.Stop();
            positionLabel.Text = MediaPlayerSupport.FormatTime(0);
            seekSlider.Value = 0;
        };
        player.MediaFailed += (_, e) =>
        {
            // Kein stiller Fehlschlag (Grundprinzip): Wiedergabefehler
            // (z.B. fehlendes Codec, kaputte Datei) werden sichtbar gemacht
            // statt einfach stumm zu bleiben - Pendant zu
            // player_bar.py::_on_error_occurred.
            positionTimer.Stop();
            playerErrorText.Text = _tr.Tr(
                "player_bar.playback_error",
                ("error", e.ErrorException?.Message ?? string.Empty));
        };
        seekSlider.ValueChanged += (_, _) =>
        {
            // Nur suchen, wenn der Regler gerade vom Nutzer gezogen wird -
            // das programmatische Nachfuehren im Timer-Handler darf KEIN
            // erneutes Setzen von player.Position ausloesen (Pendant zu
            // sliderMoved in player_bar.py, das ebenfalls nur bei
            // Nutzerinteraktion feuert).
            if (seekSlider.IsMouseCaptureWithin && player.NaturalDuration.HasTimeSpan)
            {
                player.Position = TimeSpan.FromMilliseconds(seekSlider.Value);
            }
        };
        player.Unloaded += (_, _) =>
        {
            // Ansicht verlassen (Navigation): Wiedergabe und Timer stoppen,
            // damit nach dem Seitenwechsel nichts unsichtbar im Hintergrund
            // weiterspielt - in der Python-Referenz wird die PlayerBar mit
            // der Ansicht zerstoert, hier muss das MediaElement explizit
            // gestoppt werden.
            positionTimer.Stop();
            player.Stop();
        };

        stopAndClearPlayer = () =>
        {
            // Parity zu player_bar.py::stop_and_clear(): Player stoppen,
            // Quelle loeschen, alle Anzeigen/Regler zuruecksetzen,
            // Videobereich ausblenden.
            positionTimer.Stop();
            player.Stop();
            player.Source = null;
            playerTitleText.Text = _tr.Tr("player_bar.no_media");
            playerErrorText.Text = string.Empty;
            seekSlider.IsEnabled = false;
            seekSlider.Maximum = 0;
            seekSlider.Value = 0;
            positionLabel.Text = MediaPlayerSupport.FormatTime(0);
            durationLabel.Text = MediaPlayerSupport.FormatTime(0);
            player.Height = 0;
            player.Visibility = Visibility.Collapsed;
        };

        playBtn.Click += (_, _) =>
        {
            if (selectedItem is null || !File.Exists(selectedItem.AbsolutePath)) return;
            // Videobild nur fuer Film-/Serien-Episoden einblenden
            // (VIDEO_KINDS in player_bar.py) - fuer alle anderen Arten
            // bleibt das Bildfenster ausgeblendet, um Platz zu sparen.
            var isVideoKind = selectedItem.Kind is "movie" or "episode";
            player.Height = isVideoKind ? 220 : 0; // setMinimumHeight(220) in player_bar.py
            player.Visibility = isVideoKind ? Visibility.Visible : Visibility.Collapsed;
            playerErrorText.Text = string.Empty;
            if (player.Source != new Uri(selectedItem.AbsolutePath))
            {
                player.Source = new Uri(selectedItem.AbsolutePath);
            }
            player.Play();
            playerTitleText.Text = _tr.Tr("player_bar.now_playing", ("title", selectedItem.Filename));
        };
        pauseBtn.Click += (_, _) => player.Pause();
        stopBtn.Click += (_, _) => player.Stop();

        // --- Aktivierung der Werkzeugleiste je nach Auswahl (Gap K, achter
        // Schritt) - Pendant zu media_table.py::_on_selection_changed().
        // Umbenennen wirkt auf eine Mehrfachauswahl (bool any), alle
        // anderen Werkzeuge nur auf eine Einzelauswahl (bool single);
        // Hoerbuch/Video zusaetzlich nur fuer die jeweils passende
        // Medienart - identische Regeln wie im Python-Vorbild. -------------
        void UpdateButtonStates()
        {
            var items = SelectedItems();
            var single = items.Count == 1;
            var any = items.Count > 0;
            playBtn.IsEnabled = single;
            metadataBtn.IsEnabled = single;
            renameBtn.IsEnabled = any;
            artworkBtn.IsEnabled = single;
            loudnessBtn.IsEnabled = single;
            cutterBtn.IsEnabled = single;
            convertBtn.IsEnabled = single;
            fingerprintBtn.IsEnabled = single;
            qualityBtn.IsEnabled = single;
            audiobookBtn.IsEnabled = single && items[0].Kind == "audiobook";
            videoBtn.IsEnabled = single && (items[0].Kind == "movie" || items[0].Kind == "episode");
            aiBtn.IsEnabled = single;
            openFileBtn.IsEnabled = single;
            openFolderBtn.IsEnabled = single;
            copyPathBtn.IsEnabled = single;
        }

        // --- Kontextmenue (§61, Gap-Analyse Gap H) - ergaenzt (ersetzt
        // nicht) die Werkzeugleiste: jeder Menuepunkt loest denselben
        // Button-Click aus wie oben (ueber RaiseEvent), es gibt also KEINE
        // zweite Implementierung derselben Aktion - identisch zum Vorbild
        // `_build_context_menu()`, das ebenfalls dieselben `_on_..._clicked`
        // Handler wiederverwendet. Ein Rechtsklick auf eine noch nicht
        // ausgewaehlte Zeile waehlt zuerst nur diese Zeile aus; ein
        // Rechtsklick innerhalb einer bestehenden Mehrfachauswahl laesst
        // diese unangetastet (uebliches Dateimanager-Verhalten). -----------
        void AddMenuItem(ContextMenu menu, Button sourceButton)
        {
            var item = new MenuItem { Header = sourceButton.Content, IsEnabled = sourceButton.IsEnabled };
            item.Click += (_, _) => sourceButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
            menu.Items.Add(item);
        }

        grid.PreviewMouseRightButtonDown += (_, e) =>
        {
            var dep = e.OriginalSource as DependencyObject;
            while (dep is not null && dep is not DataGridRow)
            {
                dep = VisualTreeHelper.GetParent(dep);
            }
            if (dep is DataGridRow { IsSelected: false } row)
            {
                grid.SelectedItems.Clear();
                row.IsSelected = true;
            }
        };
        grid.ContextMenuOpening += (_, _) =>
        {
            var menu = new ContextMenu();
            AddMenuItem(menu, playBtn);
            AddMenuItem(menu, metadataBtn);
            AddMenuItem(menu, renameBtn);
            AddMenuItem(menu, artworkBtn);
            AddMenuItem(menu, loudnessBtn);
            AddMenuItem(menu, cutterBtn);
            AddMenuItem(menu, convertBtn);
            AddMenuItem(menu, fingerprintBtn);
            AddMenuItem(menu, qualityBtn);
            AddMenuItem(menu, audiobookBtn);
            AddMenuItem(menu, videoBtn);
            AddMenuItem(menu, aiBtn);
            AddMenuItem(menu, openFileBtn);
            AddMenuItem(menu, openFolderBtn);
            AddMenuItem(menu, copyPathBtn);
            grid.ContextMenu = menu;
        };

        async Task RefreshDetailAsync()
        {
            if (selectedItem is not { } selected)
            {
                detailPanel.Text = _tr.Tr("media_table.detail_placeholder");
                ResetCover();
                return;
            }
            // §8/§59 "COVER" wird VOR dem Detailtext aktualisiert (siehe
            // Reihenfolge in media_table.py::_on_selection_changed: dort
            // ebenfalls _refresh_cover(media_id) zuerst) - eigener
            // try/catch, isoliert von den uebrigen Abschnitten, damit ein
            // nicht erreichbarer Artwork-Endpunkt die restliche
            // Detailansicht nicht verhindert.
            try
            {
                var artwork = await _api.GetArtworkBytesAsync(selected.Id);
                if (artwork is { } art && MediaCoverSupport.LooksLikeDecodableImage(art.Data))
                {
                    var bitmap = new BitmapImage();
                    using var stream = new MemoryStream(art.Data);
                    bitmap.BeginInit();
                    bitmap.CacheOption = BitmapCacheOption.OnLoad;
                    bitmap.StreamSource = stream;
                    bitmap.EndInit();
                    bitmap.Freeze();
                    coverImage.Source = bitmap;
                    coverImage.Visibility = Visibility.Visible;
                    coverPlaceholder.Visibility = Visibility.Collapsed;
                }
                else
                {
                    ResetCover();
                }
            }
            catch (Exception)
            {
                // Kaputte/nicht decodierbare Artwork-Datei ODER nicht
                // erreichbarer Endpunkt - fallen beide bewusst auf den
                // "kein Cover"-Platzhalter zurueck, STATT abzustuerzen oder
                // ein erfundenes Bild zu zeigen (Grundprinzip #16).
                ResetCover();
            }
            try
            {
                var detail = await _api.GetMediaDetailAsync(selected.Id);
                if (detail is null)
                {
                    detailPanel.Text = _tr.Tr("media_table.detail_placeholder");
                    return;
                }

                // Qualitaet/Loudness/KI/Quelle werden wie in
                // ui-reference-pyside/genesis_ui/views/media_table.py
                // JEWEILS EINZELN abgefragt und bei Fehlschlag auf einen
                // harmlosen Leerwert zurueckgefallen (ein einzelner
                // nicht erreichbarer Zusatz-Endpunkt darf die restliche
                // Detailansicht nicht verhindern, Prinzip "kein stiller
                // Komplettabsturz" - jede einzelne Sektion bleibt isoliert).
                QualityInfo? quality = null;
                try { quality = await _api.GetQualityAsync(selected.Id); } catch (Exception) { /* siehe oben */ }
                List<LoudnessEntry> loudnessHistory = new();
                try { loudnessHistory = await _api.ListLoudnessAsync(selected.Id); } catch (Exception) { }
                List<AiMetadataEntry> aiEntries = new();
                try { aiEntries = await _api.GetAiMetadataAsync(selected.Id); } catch (Exception) { }
                List<MediaSourceEntry> sources = new();
                try { sources = await _api.ListMediaSourcesAsync(selected.Id); } catch (Exception) { }

                detailPanel.Text = MediaTableSupport.BuildMediaDetailText(
                    detail, _tr, quality, loudnessHistory, aiEntries, sources);
            }
            catch (Exception ex)
            {
                detailPanel.Text = _tr.Tr("media_table.error_detail", ("error", ex.Message));
            }
        }

        grid.SelectionChanged += async (_, _) =>
        {
            var items = SelectedItems();
            selectedItem = items.Count > 0 ? items[0] : null;
            UpdateButtonStates();
            await RefreshDetailAsync();
        };

        await ReloadAsync(null);
    }

    // --- Einstellungen (Gap K, zweiter inkrementeller Parity-Schritt) -------
    //
    // Deckt denselben Kern ab wie
    // ui-reference-pyside/genesis_ui/views/settings_view.py, aber bewusst
    // nur vier von sieben dortigen Abschnitten in diesem Schritt (Allgemein/
    // KI/Lautheit/Datenschutz) - NOCH NICHT abgebildet (siehe
    // docs/GAP_ANALYSIS.md Gap K, Folgesitzung geplant): Medienordner-Liste
    // (braucht Ordner-Auswahldialog + Scan-Button), Sprachausgabe/Voice
    // Studio, Download-/Import-Center (braucht Ordner-Auswahldialog).
    // Schreibzugriff via PATCH /settings, IMMER erst nach expliziter
    // Nutzerbestaetigung (Prinzip #17, §44) - identisch zum Bestaetigungs-
    // Dialog in der Python-Referenz-UI (_on_save_clicked).
    private async Task ShowSettingsAsync()
    {
        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        scroll.Content = root;

        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("settings_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("settings_view.intro_note"), TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 16), Opacity = 0.8,
        });

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };

        MainContent.Content = scroll;

        SettingsResponse? settings;
        try
        {
            settings = await _api.GetSettingsAsync();
        }
        catch (Exception ex)
        {
            root.Children.Add(new TextBlock
            {
                Text = _tr.Tr("settings_view.load_failed", ("error", ex.Message)),
                TextWrapping = TextWrapping.Wrap,
            });
            return;
        }
        if (settings is null)
        {
            root.Children.Add(new TextBlock { Text = _tr.Tr("settings_view.load_failed", ("error", "null")) });
            return;
        }

        var languageCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 8) };
        foreach (var lang in Translator.SupportedLanguages) languageCombo.Items.Add(lang);
        languageCombo.SelectedItem = settings.General.Language;

        var requireConfirmationCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.require_confirmation_label"),
            IsChecked = settings.General.RequireConfirmationForBulkChanges, Margin = new Thickness(0, 0, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_general"), new UIElement[]
        {
            BuildLabeledRow(_tr.Tr("settings_view.language_label"), languageCombo),
            requireConfirmationCheck,
        }));

        var foldersNote = new TextBlock
        {
            Text = _tr.Tr("settings_view.media_folders_note"), TextWrapping = TextWrapping.Wrap,
            Opacity = 0.8, Margin = new Thickness(0, 0, 0, 6),
        };
        var foldersListBox = new ListBox { Height = 120, Margin = new Thickness(0, 0, 0, 6) };
        foreach (var folder in settings.Paths.MediaFolders) foldersListBox.Items.Add(folder);
        var foldersStatus = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 0) };
        var foldersButtonRow = new StackPanel { Orientation = Orientation.Horizontal };
        var addFolderButton = new Button
        {
            Content = _tr.Tr("settings_view.add_folder_button"), Padding = new Thickness(10, 4, 10, 4),
            Margin = new Thickness(0, 0, 8, 0),
        };
        var removeFolderButton = new Button
        {
            Content = _tr.Tr("settings_view.remove_folder_button"), Padding = new Thickness(10, 4, 10, 4),
            Margin = new Thickness(0, 0, 8, 0),
        };
        var scanButton = new Button
        {
            Content = _tr.Tr("settings_view.scan_button"), Padding = new Thickness(10, 4, 10, 4),
        };
        addFolderButton.Click += (_, _) =>
        {
            // Microsoft.Win32.OpenFolderDialog ist seit .NET 8 Teil von WPF
            // (kein System.Windows.Forms-Verweis noetig) - kann in dieser
            // Linux-Sandbox nicht interaktiv ausgefuehrt/getestet werden
            // (siehe README.md), kompiliert aber unter
            // -p:EnableWindowsTargeting=true fehlerfrei.
            var dialog = new Microsoft.Win32.OpenFolderDialog
            {
                Title = _tr.Tr("settings_view.add_folder_dialog_title"),
            };
            if (dialog.ShowDialog() != true || string.IsNullOrWhiteSpace(dialog.FolderName)) return;
            var existing = foldersListBox.Items.Cast<string>().ToList();
            var updated = SettingsViewSupport.AddFolderIfMissing(existing, dialog.FolderName);
            foldersListBox.Items.Clear();
            foreach (var folder in updated) foldersListBox.Items.Add(folder);
        };
        removeFolderButton.Click += (_, _) =>
        {
            foreach (var selected in foldersListBox.SelectedItems.Cast<string>().ToList())
            {
                foldersListBox.Items.Remove(selected);
            }
        };
        scanButton.Click += async (_, _) =>
        {
            var folders = foldersListBox.Items.Cast<string>().ToList();
            if (folders.Count == 0)
            {
                foldersStatus.Text = _tr.Tr("settings_view.scan_no_folders");
                return;
            }
            try
            {
                var result = await _api.TriggerScanAsync(folders);
                var filesFound = 0;
                if (result?.Result is System.Text.Json.JsonElement element &&
                    element.TryGetProperty("files_found", out var filesFoundElement))
                {
                    filesFound = filesFoundElement.GetInt32();
                }
                foldersStatus.Text = _tr.Tr("settings_view.scan_done", ("count", filesFound));
            }
            catch (Exception ex)
            {
                foldersStatus.Text = _tr.Tr("settings_view.scan_failed", ("error", ex.Message));
            }
        };
        foldersButtonRow.Children.Add(addFolderButton);
        foldersButtonRow.Children.Add(removeFolderButton);
        foldersButtonRow.Children.Add(scanButton);
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_media_folders"), new UIElement[]
        {
            foldersNote, foldersListBox, foldersButtonRow, foldersStatus,
        }));

        var aiEnabledCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.ai_enabled_label"),
            IsChecked = settings.Ai.Enabled, Margin = new Thickness(0, 0, 0, 8),
        };
        var aiProviderCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 8) };
        aiProviderCombo.Items.Add("null");
        aiProviderCombo.Items.Add("ollama");
        aiProviderCombo.SelectedItem = settings.Ai.Provider;
        var aiEndpointBox = new TextBox { Text = settings.Ai.Endpoint, Margin = new Thickness(0, 0, 0, 8) };
        var aiModelBox = new TextBox { Text = settings.Ai.Model, Margin = new Thickness(0, 0, 0, 8) };
        var aiTimeoutBox = new TextBox
        {
            Text = settings.Ai.TimeoutSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Margin = new Thickness(0, 0, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_ai"), new UIElement[]
        {
            aiEnabledCheck,
            BuildLabeledRow(_tr.Tr("settings_view.ai_provider_label"), aiProviderCombo),
            BuildLabeledRow(_tr.Tr("settings_view.ai_endpoint_label"), aiEndpointBox),
            BuildLabeledRow(_tr.Tr("settings_view.ai_model_label"), aiModelBox),
            BuildLabeledRow(_tr.Tr("settings_view.ai_timeout_label"), aiTimeoutBox),
        }));

        var voiceEnabledCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.voice_enabled_label"),
            IsChecked = settings.Voice.Enabled, Margin = new Thickness(0, 0, 0, 8),
        };
        var voiceProviderCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 8) };
        voiceProviderCombo.Items.Add("null");
        voiceProviderCombo.Items.Add("piper");
        voiceProviderCombo.SelectedItem = settings.Voice.Provider;
        var voiceExportFormatCombo = new ComboBox { Margin = new Thickness(0, 0, 0, 8) };
        voiceExportFormatCombo.Items.Add("wav");
        voiceExportFormatCombo.Items.Add("mp3");
        voiceExportFormatCombo.Items.Add("flac");
        voiceExportFormatCombo.SelectedItem = settings.Voice.DefaultExportFormat;
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_voice"), new UIElement[]
        {
            voiceEnabledCheck,
            BuildLabeledRow(_tr.Tr("settings_view.voice_provider_label"), voiceProviderCombo),
            BuildLabeledRow(_tr.Tr("settings_view.voice_export_format_label"), voiceExportFormatCombo),
        }));

        var loudnessLufsBox = new TextBox
        {
            Text = settings.Loudness.TargetLufs.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Margin = new Thickness(0, 0, 0, 8),
        };
        var loudnessTruePeakBox = new TextBox
        {
            Text = settings.Loudness.TargetTruePeakDbtp.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Margin = new Thickness(0, 0, 0, 8),
        };
        var loudnessOverwriteCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.loudness_overwrite_originals_label"),
            IsChecked = settings.Loudness.OverwriteOriginals, Margin = new Thickness(0, 0, 0, 4),
        };
        var loudnessWarning = new TextBlock
        {
            Text = _tr.Tr("settings_view.loudness_overwrite_warning"), TextWrapping = TextWrapping.Wrap,
            Opacity = 0.8, Margin = new Thickness(0, 0, 0, 8), FontStyle = FontStyles.Italic,
        };
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_loudness"), new UIElement[]
        {
            BuildLabeledRow(_tr.Tr("settings_view.loudness_target_lufs_label"), loudnessLufsBox),
            BuildLabeledRow(_tr.Tr("settings_view.loudness_target_true_peak_label"), loudnessTruePeakBox),
            loudnessOverwriteCheck,
            loudnessWarning,
        }));

        var downloadEnabledCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.download_enabled_label"),
            IsChecked = settings.Download.Enabled, Margin = new Thickness(0, 0, 0, 4),
        };
        var downloadYoutubeCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.download_enable_youtube_label"),
            IsChecked = settings.Download.EnableYoutube, Margin = new Thickness(0, 0, 0, 4),
        };
        var downloadTiktokCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.download_enable_tiktok_label"),
            IsChecked = settings.Download.EnableTiktok, Margin = new Thickness(0, 0, 0, 8),
        };
        var downloadDirBox = new TextBox
        {
            Text = settings.Download.DownloadsDir ?? string.Empty, Margin = new Thickness(0, 0, 8, 0),
            Width = 300, HorizontalAlignment = HorizontalAlignment.Left,
        };
        var downloadDirBrowseButton = new Button
        {
            Content = _tr.Tr("settings_view.download_dir_browse_button"), Padding = new Thickness(10, 4, 10, 4),
        };
        downloadDirBrowseButton.Click += (_, _) =>
        {
            var dialog = new Microsoft.Win32.OpenFolderDialog
            {
                Title = _tr.Tr("settings_view.download_dir_dialog_title"),
            };
            if (dialog.ShowDialog() == true && !string.IsNullOrWhiteSpace(dialog.FolderName))
            {
                downloadDirBox.Text = dialog.FolderName;
            }
        };
        var downloadDirRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 8) };
        downloadDirRow.Children.Add(downloadDirBox);
        downloadDirRow.Children.Add(downloadDirBrowseButton);
        var downloadMaxSizeBox = new TextBox
        {
            Text = settings.Download.MaxDownloadSizeMb.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Margin = new Thickness(0, 0, 0, 8),
        };
        var downloadMinFreeDiskBox = new TextBox
        {
            Text = settings.Download.MinFreeDiskMb.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Margin = new Thickness(0, 0, 0, 8),
        };
        var downloadTimeoutBox = new TextBox
        {
            Text = settings.Download.RequestTimeoutSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture),
            Margin = new Thickness(0, 0, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_download"), new UIElement[]
        {
            downloadEnabledCheck, downloadYoutubeCheck, downloadTiktokCheck,
            BuildLabeledRow(_tr.Tr("settings_view.download_dir_label"), downloadDirRow),
            BuildLabeledRow(_tr.Tr("settings_view.download_max_size_label"), downloadMaxSizeBox),
            BuildLabeledRow(_tr.Tr("settings_view.download_min_free_disk_label"), downloadMinFreeDiskBox),
            BuildLabeledRow(_tr.Tr("settings_view.download_timeout_label"), downloadTimeoutBox),
        }));

        var telemetryCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.privacy_telemetry_label"),
            IsChecked = settings.Privacy.TelemetryEnabled, Margin = new Thickness(0, 0, 0, 4),
        };
        var cloudAiCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.privacy_allow_cloud_ai_label"),
            IsChecked = settings.Privacy.AllowCloudAi, Margin = new Thickness(0, 0, 0, 4),
        };
        var autoDownloadsCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.privacy_allow_auto_downloads_label"),
            IsChecked = settings.Privacy.AllowAutomaticDownloads, Margin = new Thickness(0, 0, 0, 4),
        };
        var autoDeletionCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.privacy_allow_auto_deletion_label"),
            IsChecked = settings.Privacy.AllowAutomaticDeletion, Margin = new Thickness(0, 0, 0, 4),
        };
        var autoOverwriteCheck = new CheckBox
        {
            Content = _tr.Tr("settings_view.privacy_allow_auto_overwrite_label"),
            IsChecked = settings.Privacy.AllowAutomaticOverwrite, Margin = new Thickness(0, 0, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("settings_view.section_privacy"), new UIElement[]
        {
            telemetryCheck, cloudAiCheck, autoDownloadsCheck, autoDeletionCheck, autoOverwriteCheck,
        }));

        var saveButton = new Button
        {
            Content = _tr.Tr("settings_view.save_button"), Padding = new Thickness(16, 6, 16, 6),
            HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 8, 0, 0),
        };
        saveButton.Click += async (_, _) =>
        {
            var reply = MessageBox.Show(
                _tr.Tr("settings_view.save_confirm_text"), _tr.Tr("settings_view.save_confirm_title"),
                MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No);
            if (reply != MessageBoxResult.Yes) return;

            var culture = System.Globalization.CultureInfo.InvariantCulture;
            const System.Globalization.NumberStyles floatStyle = System.Globalization.NumberStyles.Float;
            if (!double.TryParse(aiTimeoutBox.Text, floatStyle, culture, out var aiTimeout) ||
                !double.TryParse(loudnessLufsBox.Text, floatStyle, culture, out var targetLufs) ||
                !double.TryParse(loudnessTruePeakBox.Text, floatStyle, culture, out var targetTruePeak) ||
                !int.TryParse(downloadMaxSizeBox.Text, out var downloadMaxSize) ||
                !int.TryParse(downloadMinFreeDiskBox.Text, out var downloadMinFreeDisk) ||
                !double.TryParse(downloadTimeoutBox.Text, floatStyle, culture, out var downloadTimeout))
            {
                statusText.Text = _tr.Tr("settings_view.save_failed", ("error", "invalid number"));
                return;
            }

            var values = new SettingsFormValues(
                Language: (string)(languageCombo.SelectedItem ?? settings.General.Language),
                RequireConfirmationForBulkChanges: requireConfirmationCheck.IsChecked ?? false,
                MediaFolders: foldersListBox.Items.Cast<string>().ToList(),
                AiEnabled: aiEnabledCheck.IsChecked ?? false,
                AiProvider: (string)(aiProviderCombo.SelectedItem ?? settings.Ai.Provider),
                AiEndpoint: aiEndpointBox.Text,
                AiModel: aiModelBox.Text,
                AiTimeoutSeconds: aiTimeout,
                VoiceEnabled: voiceEnabledCheck.IsChecked ?? false,
                VoiceProvider: (string)(voiceProviderCombo.SelectedItem ?? settings.Voice.Provider),
                VoiceDefaultExportFormat: (string)(voiceExportFormatCombo.SelectedItem ?? settings.Voice.DefaultExportFormat),
                LoudnessTargetLufs: targetLufs,
                LoudnessTargetTruePeakDbtp: targetTruePeak,
                LoudnessOverwriteOriginals: loudnessOverwriteCheck.IsChecked ?? false,
                DownloadEnabled: downloadEnabledCheck.IsChecked ?? false,
                DownloadEnableYoutube: downloadYoutubeCheck.IsChecked ?? false,
                DownloadEnableTiktok: downloadTiktokCheck.IsChecked ?? false,
                DownloadDir: downloadDirBox.Text,
                DownloadMaxSizeMb: downloadMaxSize,
                DownloadMinFreeDiskMb: downloadMinFreeDisk,
                DownloadTimeoutSeconds: downloadTimeout,
                PrivacyTelemetryEnabled: telemetryCheck.IsChecked ?? false,
                PrivacyAllowCloudAi: cloudAiCheck.IsChecked ?? false,
                PrivacyAllowAutomaticDownloads: autoDownloadsCheck.IsChecked ?? false,
                PrivacyAllowAutomaticDeletion: autoDeletionCheck.IsChecked ?? false,
                PrivacyAllowAutomaticOverwrite: autoOverwriteCheck.IsChecked ?? false);

            try
            {
                var result = await _api.UpdateSettingsAsync(
                    SettingsViewSupport.BuildUpdatePayload(values), confirm: true);
                statusText.Text = result?.RestartRequired == true
                    ? _tr.Tr("settings_view.save_done_restart_required")
                    : _tr.Tr("settings_view.save_done");
                if (values.Language != _tr.Language)
                {
                    Translator.ConfigureDefaultLanguage(values.Language);
                }
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("settings_view.save_failed", ("error", ex.Message));
            }
        };
        root.Children.Add(saveButton);
        root.Children.Add(statusText);
    }

    /// <summary>
    /// §10/§11, Gap-Analyse I - 1:1-Pendant zu
    /// ui-reference-pyside/genesis_ui/views/providers_view.py::ProvidersView.
    /// Betrifft ausschliesslich die ONLINE-Metadatenabgleich-Provider
    /// (MusicBrainz/AcoustID/Cover Art Archive), NICHT die Download-/
    /// Import-Provider (siehe "nav.download_center"). Standardmaessig ist
    /// der komplette Online-Abgleich AUS (§56, "kein Internetzwang") -
    /// selbst wenn aktiviert, bleibt laut Core-Doku jeder Treffer nur ein
    /// Vorschlag mit Konfidenzwert (Prinzip #17), niemals eine automatische
    /// Uebernahme.
    /// </summary>
    private async Task ShowProvidersAsync()
    {
        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var root = new StackPanel { Margin = new Thickness(16), Background = (System.Windows.Media.Brush)System.Windows.Application.Current.Resources["BackgroundBrush"] };
        scroll.Content = root;

        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("providers_view.title"), FontSize = 20, FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 8),
        });
        root.Children.Add(new TextBlock
        {
            Text = _tr.Tr("providers_view.intro_note"), TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 16), Opacity = 0.8,
        });

        MainContent.Content = scroll;

        SettingsResponse? settings;
        try
        {
            settings = await _api.GetSettingsAsync();
        }
        catch (Exception ex)
        {
            root.Children.Add(new TextBlock
            {
                Text = _tr.Tr("providers_view.load_failed", ("error", ex.Message)),
                TextWrapping = TextWrapping.Wrap,
            });
            return;
        }
        if (settings is null)
        {
            root.Children.Add(new TextBlock { Text = _tr.Tr("providers_view.load_failed", ("error", "null")) });
            return;
        }

        var values = ProvidersViewSupport.FromSettingsResponse(settings);

        var enabledCheck = new CheckBox
        {
            Content = _tr.Tr("providers_view.metadata_enabled_label"),
            IsChecked = values.Enabled, Margin = new Thickness(0, 0, 0, 4),
        };
        var enabledNote = new TextBlock
        {
            Text = _tr.Tr("providers_view.metadata_enabled_note"), TextWrapping = TextWrapping.Wrap,
            Opacity = 0.8, Margin = new Thickness(0, 0, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("providers_view.section_general"), new UIElement[]
        {
            enabledCheck, enabledNote,
        }));

        var musicbrainzCheck = new CheckBox
        {
            Content = _tr.Tr("providers_view.musicbrainz_enabled_label"),
            IsChecked = values.MusicbrainzEnabled, Margin = new Thickness(0, 0, 0, 8),
        };
        var acoustidCheck = new CheckBox
        {
            Content = _tr.Tr("providers_view.acoustid_enabled_label"),
            IsChecked = values.AcoustidEnabled, Margin = new Thickness(0, 0, 0, 8),
        };
        var acoustidKeyBox = new TextBox { Text = values.AcoustidApiKey };
        var acoustidKeyNote = new TextBlock
        {
            Text = _tr.Tr("providers_view.acoustid_api_key_note"), TextWrapping = TextWrapping.Wrap,
            Opacity = 0.8, Margin = new Thickness(0, 4, 0, 8),
        };
        var coverartarchiveCheck = new CheckBox
        {
            Content = _tr.Tr("providers_view.coverartarchive_enabled_label"),
            IsChecked = values.CoverartarchiveEnabled, Margin = new Thickness(0, 0, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("providers_view.section_providers"), new UIElement[]
        {
            musicbrainzCheck, acoustidCheck,
            BuildLabeledRow(_tr.Tr("providers_view.acoustid_api_key_label"), acoustidKeyBox),
            acoustidKeyNote, coverartarchiveCheck,
        }));

        var contactEmailBox = new TextBox { Text = values.ContactEmail };
        var contactEmailNote = new TextBlock
        {
            Text = _tr.Tr("providers_view.contact_email_note"), TextWrapping = TextWrapping.Wrap,
            Opacity = 0.8, Margin = new Thickness(0, 4, 0, 8),
        };
        var timeoutBox = new TextBox
        {
            Text = values.RequestTimeoutSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture),
        };
        var minConfidenceBox = new TextBox
        {
            Text = values.MinConfidenceForSuggestion.ToString(System.Globalization.CultureInfo.InvariantCulture),
        };
        var minConfidenceNote = new TextBlock
        {
            Text = _tr.Tr("providers_view.min_confidence_note"), TextWrapping = TextWrapping.Wrap,
            Opacity = 0.8, Margin = new Thickness(0, 4, 0, 8),
        };
        root.Children.Add(BuildGroup(_tr.Tr("providers_view.section_contact"), new UIElement[]
        {
            BuildLabeledRow(_tr.Tr("providers_view.contact_email_label"), contactEmailBox),
            contactEmailNote,
            BuildLabeledRow(_tr.Tr("providers_view.request_timeout_label"), timeoutBox),
            BuildLabeledRow(_tr.Tr("providers_view.min_confidence_label"), minConfidenceBox),
            minConfidenceNote,
        }));

        var statusText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };

        var buttonRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
        var saveButton = new Button
        {
            Content = _tr.Tr("providers_view.save_button"), Padding = new Thickness(16, 6, 16, 6),
            Margin = new Thickness(0, 0, 8, 0),
        };
        var reloadButton = new Button
        {
            Content = _tr.Tr("providers_view.reload_button"), Padding = new Thickness(16, 6, 16, 6),
        };
        saveButton.Click += async (_, _) =>
        {
            var reply = MessageBox.Show(
                _tr.Tr("providers_view.save_confirm_text"), _tr.Tr("providers_view.save_confirm_title"),
                MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No);
            if (reply != MessageBoxResult.Yes) return;

            var culture = System.Globalization.CultureInfo.InvariantCulture;
            const System.Globalization.NumberStyles floatStyle = System.Globalization.NumberStyles.Float;
            if (!double.TryParse(timeoutBox.Text, floatStyle, culture, out var timeout) ||
                !double.TryParse(minConfidenceBox.Text, floatStyle, culture, out var minConfidence))
            {
                statusText.Text = _tr.Tr("providers_view.save_failed", ("error", "invalid number"));
                return;
            }

            var formValues = new ProviderFormValues(
                Enabled: enabledCheck.IsChecked ?? false,
                MusicbrainzEnabled: musicbrainzCheck.IsChecked ?? false,
                AcoustidEnabled: acoustidCheck.IsChecked ?? false,
                AcoustidApiKey: acoustidKeyBox.Text,
                CoverartarchiveEnabled: coverartarchiveCheck.IsChecked ?? false,
                ContactEmail: contactEmailBox.Text,
                RequestTimeoutSeconds: timeout,
                MinConfidenceForSuggestion: minConfidence);

            try
            {
                await _api.UpdateSettingsAsync(ProvidersViewSupport.BuildUpdatePayload(formValues), confirm: true);
                statusText.Text = _tr.Tr("providers_view.save_done");
            }
            catch (Exception ex)
            {
                statusText.Text = _tr.Tr("providers_view.save_failed", ("error", ex.Message));
            }
        };
        // Entspricht ProvidersView._reload(): verwirft nicht gespeicherte
        // Aenderungen und laedt die Ansicht komplett neu vom Server.
        reloadButton.Click += async (_, _) => await ShowProvidersAsync();
        buttonRow.Children.Add(saveButton);
        buttonRow.Children.Add(reloadButton);
        root.Children.Add(buttonRow);
        root.Children.Add(statusText);
    }

    private static GroupBox BuildGroup(string header, IEnumerable<UIElement> children)
    {
        var panel = new StackPanel();
        foreach (var child in children) panel.Children.Add(child);
        return new GroupBox { Header = header, Margin = new Thickness(0, 0, 0, 12), Content = panel };
    }

    private static Grid BuildLabeledRow(string label, UIElement control)
    {
        var grid = new Grid { Margin = new Thickness(0, 0, 0, 4) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(180) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var labelBlock = new TextBlock { Text = label, VerticalAlignment = VerticalAlignment.Center };
        Grid.SetColumn(labelBlock, 0);
        Grid.SetColumn(control, 1);
        grid.Children.Add(labelBlock);
        grid.Children.Add(control);
        return grid;
    }
}
