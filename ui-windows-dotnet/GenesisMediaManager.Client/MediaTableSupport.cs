// Reine Hilfslogik der Medientabellen-Ansicht (MainWindow.xaml.cs ::
// ShowMediaTableAsync), bewusst OHNE jede WPF-Abhaengigkeit ausgelagert
// (gleiches Muster wie Translator.cs) - nur so kann
// GenesisMediaManager.Client.Tests (reines net8.0, kein
// EnableWindowsTargeting noetig) diese Logik auf jedem Betriebssystem ohne
// Windows-Targeting-Pack testen (siehe Kommentar in
// GenesisMediaManager.Client.Tests.csproj).
using GenesisMediaManager.Client.Api;
using GenesisMediaManager.Client.I18n;

namespace GenesisMediaManager.Client;

public static class MediaTableSupport
{
    /// <summary>
    /// Entspricht 1:1 den ("nav.xxx", "media", "&lt;kind-oder-null&gt;")-
    /// Eintraegen in ui-reference-pyside/genesis_ui/main_window.py::
    /// NAV_STRUCTURE - "nav.search" liefert bewusst KEINEN kind-Filter
    /// (zeigt alle Arten, identisch zur Python-Referenz-UI).
    /// </summary>
    public static readonly IReadOnlyDictionary<string, string?> MediaKindByNavKey = new Dictionary<string, string?>
    {
        ["nav.music"] = "music",
        ["nav.audiobook"] = "audiobook",
        ["nav.movie"] = "movie",
        ["nav.episode"] = "episode",
        ["nav.podcast"] = "podcast_episode",
        ["nav.ai_music"] = "ai_music",
        ["nav.unknown"] = "unknown",
        ["nav.search"] = null,
    };

    /// <summary>Entspricht MEDIA_KIND_LABEL_KEYS in
    /// ui-reference-pyside/genesis_ui/i18n.py - Medienart-Code (z.B. aus
    /// einem KI-Suchtreffer oder einer Duplikatgruppe) auf den
    /// zugehoerigen i18n-Navigationsschluessel. Unbekannte Codes liefern
    /// den Code selbst zurueck (kein stiller Fehlschlag, Prinzip #37).</summary>
    public static string MediaKindLabelKey(string kind) => kind switch
    {
        "music" => "nav.music",
        "audiobook" => "nav.audiobook",
        "movie" => "nav.movie",
        "episode" => "nav.episode",
        "podcast_episode" => "nav.podcast",
        "ai_music" => "nav.ai_music",
        "unknown" => "nav.unknown",
        _ => kind,
    };

    /// <summary>
    /// Baut denselben Detailtext wie
    /// ui-reference-pyside/genesis_ui/views/media_table.py (Pfad/Groesse/
    /// Format/Technik/Track-Metadaten, sowie - seit Gap K Schritt 4 - auch
    /// Qualitaetspruefung/Loudness/KI-Analyse/Quellen-Abschnitt). Die vier
    /// zusaetzlichen Parameter sind bewusst optional mit Default <c>null</c>,
    /// damit bestehende Aufrufer/Tests, die nur den Basis-Detailtext
    /// brauchen, unveraendert bleiben.
    /// </summary>
    public static string BuildMediaDetailText(
        MediaDetail detail, Translator tr,
        QualityInfo? quality = null,
        IReadOnlyList<LoudnessEntry>? loudnessHistory = null,
        IReadOnlyList<AiMetadataEntry>? aiEntries = null,
        IReadOnlyList<MediaSourceEntry>? sources = null)
    {
        var yes = tr.Tr("common.value_yes");
        var no = tr.Tr("common.value_no");
        var empty = tr.Tr("common.value_empty");
        const string d = "media_table.detail";
        var existsText = detail.FileExistsOnDisk ? yes : tr.Tr($"{d}.exists_no");

        var lines = new List<string>
        {
            tr.Tr($"{d}.path_header"),
            $"  {detail.AbsolutePath}",
            tr.Tr($"{d}.exists_on_disk", ("status", existsText)),
            string.Empty,
            tr.Tr($"{d}.filename", ("value", detail.Filename)),
            tr.Tr($"{d}.directory", ("value", detail.Directory)),
            tr.Tr($"{d}.size", ("value", detail.SizeBytes.ToString("N0"))),
            tr.Tr($"{d}.format", ("value", detail.Extension)),
            tr.Tr($"{d}.modified", ("value", detail.Mtime ?? empty)),
            tr.Tr($"{d}.sha256", ("value", detail.ContentHashSha256 ?? empty)),
            string.Empty,
        };

        if (detail.Technical is { } t)
        {
            lines.Add(tr.Tr($"{d}.technical_header"));
            void AddIfPresent(string label, object? value)
            {
                if (value is not null) lines.Add($"  {label}: {value}");
            }
            AddIfPresent("container_format", t.ContainerFormat);
            AddIfPresent("audio_codec", t.AudioCodec);
            AddIfPresent("video_codec", t.VideoCodec);
            AddIfPresent("bitrate_kbps", t.BitrateKbps);
            AddIfPresent("sample_rate_hz", t.SampleRateHz);
            AddIfPresent("channels", t.Channels);
            AddIfPresent("duration_seconds", t.DurationSeconds);
            AddIfPresent("resolution", t.ResolutionWidth is not null && t.ResolutionHeight is not null
                ? $"{t.ResolutionWidth}x{t.ResolutionHeight}" : null);
            AddIfPresent("fps", t.Fps);
            AddIfPresent("hdr", t.Hdr);
            AddIfPresent("chapters_count", t.ChaptersCount);
            lines.Add(string.Empty);
        }

        // §59/§20 "QUALITAETSANALYSE" - identisch zu
        // media_table.py::_on_selection_changed: der GESAMTE Abschnitt
        // (inkl. Kopfzeile) entfaellt, wenn noch keine Analyse vorliegt -
        // anders als Loudness/KI/Quelle unten, die immer eine Kopfzeile mit
        // "none"-Fallback zeigen.
        if (quality is not null)
        {
            lines.Add(tr.Tr($"{d}.quality_header"));
            lines.Add($"  {tr.Tr($"{d}.quality_flag_upscale")}: {(quality.SuspectedUpscale ? yes : no)}");
            lines.Add($"  {tr.Tr($"{d}.quality_flag_transcode")}: {(quality.SuspectedTranscode ? yes : no)}");
            lines.Add($"  {tr.Tr($"{d}.quality_flag_corruption")}: {(quality.SuspectedCorruption ? yes : no)}");
            lines.Add($"  {tr.Tr($"{d}.quality_flag_truncation")}: {(quality.SuspectedTruncation ? yes : no)}");
            foreach (var note in quality.Notes) lines.Add($"  - {note}");
            lines.Add(string.Empty);
        }

        if (detail.Track is { } track)
        {
            var confirmed = track.IsUserConfirmed ? tr.Tr($"{d}.confirmed_yes") : tr.Tr($"{d}.confirmed_no");
            lines.Add(tr.Tr($"{d}.metadata_header"));
            lines.Add(tr.Tr($"{d}.title", ("value", track.Title ?? empty)));
            lines.Add(tr.Tr(
                $"{d}.track_disc",
                ("track", track.TrackNumber?.ToString() ?? empty),
                ("disc", track.DiscNumber?.ToString() ?? empty)));
            lines.Add(tr.Tr($"{d}.year", ("value", track.Year?.ToString() ?? empty)));
            lines.Add(tr.Tr($"{d}.source", ("value", track.Source ?? empty)));
            lines.Add(tr.Tr($"{d}.confidence", ("value", track.Confidence?.ToString() ?? empty)));
            lines.Add(tr.Tr($"{d}.user_confirmed", ("value", confirmed)));
        }
        else
        {
            lines.Add(tr.Tr($"{d}.metadata_none"));
        }
        lines.Add(string.Empty);

        var embedded = detail.HasEmbeddedArtwork ? yes : no;
        lines.Add(tr.Tr($"{d}.embedded_artwork", ("value", embedded)));
        lines.Add(string.Empty);

        // §59 "LOUDNESS" - identisch zu media_table.py::_on_selection_changed:
        // Kopfzeile wird IMMER angezeigt, mit "noch nicht analysiert" als
        // Fallback (anders als der Qualitaets-Abschnitt unten, der bei
        // Abwesenheit komplett entfaellt).
        lines.Add(tr.Tr($"{d}.loudness_header"));
        if (loudnessHistory is { Count: > 0 })
        {
            var latest = loudnessHistory[0]; // API liefert neueste zuerst
            lines.Add(tr.Tr($"{d}.loudness_integrated", ("value", FormatNullable(latest.IntegratedLufs, empty))));
            lines.Add(tr.Tr($"{d}.loudness_true_peak", ("value", FormatNullable(latest.TruePeakDbtp, empty))));
            lines.Add(tr.Tr($"{d}.loudness_lra", ("value", FormatNullable(latest.LoudnessRangeLu, empty))));
            lines.Add(tr.Tr($"{d}.loudness_normalized", ("value", latest.Normalized ? yes : no)));
        }
        else
        {
            lines.Add(tr.Tr($"{d}.loudness_none"));
        }
        lines.Add(string.Empty);

        // §59/§25 "KI-ANALYSE" - jeder Eintrag IMMER mit Modell/Confidence/
        // Uebernahme-Status, nie ohne diese Herkunft (Prinzip #9/#17).
        lines.Add(tr.Tr($"{d}.ai_header"));
        if (aiEntries is { Count: > 0 })
        {
            foreach (var entry in aiEntries)
            {
                lines.Add(tr.Tr(
                    $"{d}.ai_entry",
                    ("field", entry.FieldName),
                    ("value", entry.FieldValue),
                    ("model", entry.ModelName ?? empty),
                    ("confidence", FormatNullable(entry.Confidence, empty)),
                    ("accepted", entry.AcceptedByUser ? yes : no)));
            }
        }
        else
        {
            lines.Add(tr.Tr($"{d}.ai_none"));
        }
        lines.Add(string.Empty);

        // §59/§32 "QUELLE" - Herkunft eines importierten Mediums.
        lines.Add(tr.Tr($"{d}.source_header"));
        if (sources is { Count: > 0 })
        {
            foreach (var source in sources)
            {
                lines.Add(tr.Tr(
                    $"{d}.source_entry",
                    ("name", source.SourceName ?? empty),
                    ("provider", source.ProviderName ?? empty),
                    ("imported_at", source.ImportedAt ?? empty)));
            }
        }
        else
        {
            lines.Add(tr.Tr($"{d}.source_none"));
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatNullable(double? value, string empty) =>
        value?.ToString(System.Globalization.CultureInfo.InvariantCulture) ?? empty;
}

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Pendant zu
/// ui-reference-pyside/genesis_ui/dialogs/search_filters_dialog.py (§9,
/// Gap-Analyse C). Alle Felder optional/<c>null</c> = "kein Filter
/// gesetzt" - identisch zum Verhalten der 19 optionalen Query-Parameter an
/// <c>GET /media</c> (core/genesis_core/api/app.py::list_media). Als
/// eigener, von <see cref="GenesisApiClient"/> unabhaengiger Typ ausgelegt,
/// damit <see cref="ToQueryString"/> UND <see cref="CountActive"/> ohne
/// WPF/HTTP testbar sind.
/// </summary>
public sealed record MediaSearchFilters(
    int? Year = null,
    string? Genre = null,
    string? Extension = null,
    long? MinSizeBytes = null,
    long? MaxSizeBytes = null,
    double? MinDurationSeconds = null,
    double? MaxDurationSeconds = null,
    string? Source = null,
    string? Person = null,
    string? Series = null,
    int? Season = null,
    int? EpisodeNumber = null,
    string? AiStatus = null,
    double? MinLufs = null,
    double? MaxLufs = null,
    bool? HasQualityIssues = null,
    bool? MissingMetadata = null,
    bool? MissingCover = null,
    bool? DuplicateOnly = null)
{
    /// <summary>
    /// Baut den Query-String-Anhang (inkl. fuehrendem <c>&amp;</c> je
    /// gesetztem Feld) fuer <see cref="GenesisApiClient.ListMediaAsync"/>.
    /// Nutzt <see cref="System.Globalization.CultureInfo.InvariantCulture"/>
    /// fuer Zahlen (die Core-API erwartet Punkt als Dezimaltrennzeichen,
    /// unabhaengig von der UI-Sprache/Systemkultur).
    /// </summary>
    public string ToQueryString()
    {
        var culture = System.Globalization.CultureInfo.InvariantCulture;
        var parts = new List<string>();
        void AddStr(string key, string? value)
        {
            if (!string.IsNullOrWhiteSpace(value)) parts.Add($"{key}={Uri.EscapeDataString(value)}");
        }
        void AddNum(string key, object? value)
        {
            if (value is not null) parts.Add($"{key}={Convert.ToString(value, culture)}");
        }
        void AddBool(string key, bool? value)
        {
            if (value is true) parts.Add($"{key}=true");
        }
        AddNum("year", Year);
        AddStr("genre", Genre);
        AddStr("extension", Extension);
        AddNum("min_size_bytes", MinSizeBytes);
        AddNum("max_size_bytes", MaxSizeBytes);
        AddNum("min_duration_s", MinDurationSeconds);
        AddNum("max_duration_s", MaxDurationSeconds);
        AddStr("source", Source);
        AddStr("person", Person);
        AddStr("series", Series);
        AddNum("season", Season);
        AddNum("episode_number", EpisodeNumber);
        AddStr("ai_status", AiStatus);
        AddNum("min_lufs", MinLufs);
        AddNum("max_lufs", MaxLufs);
        AddBool("has_quality_issues", HasQualityIssues);
        AddBool("missing_metadata", MissingMetadata);
        AddBool("missing_cover", MissingCover);
        AddBool("duplicate_only", DuplicateOnly);
        return parts.Count == 0 ? string.Empty : "&" + string.Join("&", parts);
    }

    /// <summary>
    /// Entspricht <c>count_active_filters()</c> in
    /// search_filters_dialog.py - fuer die Statusanzeige "Filter aktiv (n)"
    /// neben dem Such-/Filter-Button.
    /// </summary>
    public int CountActive()
    {
        var values = new object?[]
        {
            Year, Genre, Extension, MinSizeBytes, MaxSizeBytes, MinDurationSeconds,
            MaxDurationSeconds, Source, Person, Series, Season, EpisodeNumber, AiStatus,
            MinLufs, MaxLufs,
        };
        var count = values.Count(v => v is not null && !(v is string s && string.IsNullOrWhiteSpace(s)));
        if (HasQualityIssues is true) count++;
        if (MissingMetadata is true) count++;
        if (MissingCover is true) count++;
        if (DuplicateOnly is true) count++;
        return count;
    }
}
