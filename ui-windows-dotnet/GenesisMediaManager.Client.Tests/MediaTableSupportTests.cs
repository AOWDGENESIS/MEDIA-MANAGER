// Tests fuer die WPF-unabhaengige Hilfslogik der Medientabellen-Ansicht
// (MediaTableSupport.cs). Spiegelt die Kernfaelle, die auf Python-Seite in
// ui-reference-pyside/tests/test_media_table*.py abgedeckt sind, soweit sie
// sich ohne echten WPF-Control-Baum pruefen lassen (Nav-Key->Kind-Mapping,
// Detailtext-Aufbau fuer verschiedene MediaDetail-Kombinationen).
using GenesisMediaManager.Client.Api;
using GenesisMediaManager.Client.I18n;

namespace GenesisMediaManager.Client.Tests;

public class MediaTableSupportTests
{
    [Theory]
    [InlineData("nav.music", "music")]
    [InlineData("nav.audiobook", "audiobook")]
    [InlineData("nav.movie", "movie")]
    [InlineData("nav.episode", "episode")]
    [InlineData("nav.podcast", "podcast_episode")]
    [InlineData("nav.ai_music", "ai_music")]
    [InlineData("nav.unknown", "unknown")]
    public void MediaKindByNavKey_MapsEachMediaSectionItemToItsKind(string navKey, string expectedKind)
    {
        Assert.True(MediaTableSupport.MediaKindByNavKey.TryGetValue(navKey, out var kind));
        Assert.Equal(expectedKind, kind);
    }

    [Fact]
    public void MediaKindByNavKey_SearchHasNoKindFilter()
    {
        Assert.True(MediaTableSupport.MediaKindByNavKey.TryGetValue("nav.search", out var kind));
        Assert.Null(kind);
    }

    [Fact]
    public void MediaKindByNavKey_DoesNotContainUnrelatedNavItems()
    {
        Assert.False(MediaTableSupport.MediaKindByNavKey.ContainsKey("nav.dashboard"));
        Assert.False(MediaTableSupport.MediaKindByNavKey.ContainsKey("nav.settings"));
    }

    // --- MediaKindLabelKey (gefunden im Deep-Search: bislang ungetestet) ----

    [Theory]
    [InlineData("music", "nav.music")]
    [InlineData("audiobook", "nav.audiobook")]
    [InlineData("movie", "nav.movie")]
    [InlineData("episode", "nav.episode")]
    [InlineData("podcast_episode", "nav.podcast")]
    [InlineData("ai_music", "nav.ai_music")]
    [InlineData("unknown", "nav.unknown")]
    public void MediaKindLabelKey_MapsEachKindToItsNavI18nKey(string kind, string expectedNavKey)
    {
        Assert.Equal(expectedNavKey, MediaTableSupport.MediaKindLabelKey(kind));
    }

    [Theory]
    [InlineData("music")]
    [InlineData("audiobook")]
    [InlineData("movie")]
    [InlineData("episode")]
    [InlineData("podcast_episode")]
    [InlineData("ai_music")]
    [InlineData("unknown")]
    public void MediaKindLabelKey_IsExactInverseOfMediaKindByNavKey(string kind)
    {
        // MediaKindByNavKey bildet nav-Schluessel -> kind ab,
        // MediaKindLabelKey bildet kind -> nav-Schluessel ab - beide muessen
        // zueinander konsistent sein, sonst zeigt z.B. das KI-Center
        // (MainWindow.AiCenter.cs) einen anderen Medienart-Namen an als die
        // Medientabelle fuer denselben Code.
        var navKey = MediaTableSupport.MediaKindLabelKey(kind);
        Assert.True(MediaTableSupport.MediaKindByNavKey.TryGetValue(navKey, out var roundTrippedKind));
        Assert.Equal(kind, roundTrippedKind);
    }

    [Fact]
    public void MediaKindLabelKey_UnknownCode_ReturnsCodeItselfAsFallback()
    {
        // Prinzip #37 (kein stiller Fehlschlag): ein unbekannter/zukuenftiger
        // Backend-Kind-Code wird nicht verschluckt, sondern 1:1
        // durchgereicht - der Translator zeigt ihn dann unuebersetzt an,
        // statt z.B. eine KeyNotFoundException zu werfen oder leer zu
        // bleiben.
        Assert.Equal("some_future_kind", MediaTableSupport.MediaKindLabelKey("some_future_kind"));
        Assert.Equal(string.Empty, MediaTableSupport.MediaKindLabelKey(string.Empty));
    }

    private static MediaDetail MinimalDetail(
        TechnicalMetadata? technical = null, TrackInfo? track = null, bool hasEmbeddedArtwork = false) =>
        new(
            Id: 1, AbsolutePath: "/music/a.flac", Directory: "/music", Filename: "a.flac",
            Extension: "flac", Kind: "music", SizeBytes: 123456, Mtime: "2026-01-01T00:00:00",
            ContentHashSha256: "abc123", IsMissing: false, LastScannedAt: "2026-01-01T00:00:00",
            FileExistsOnDisk: true, Technical: technical, Track: track,
            HasEmbeddedArtwork: hasEmbeddedArtwork);

    [Fact]
    public void BuildMediaDetailText_IncludesPathAndBasicFields()
    {
        var tr = new Translator("de");
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr);

        Assert.Contains("/music/a.flac", text);
        Assert.Contains("a.flac", text);
        Assert.Contains("/music", text);
        Assert.Contains("flac", text);
        Assert.Contains("abc123", text);
    }

    [Fact]
    public void BuildMediaDetailText_WithoutTrack_ShowsMetadataNone()
    {
        var tr = new Translator("de");
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr);

        Assert.Contains(tr.Tr("media_table.detail.metadata_none"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithTrack_ShowsTitleAndConfirmedState()
    {
        var tr = new Translator("de");
        var track = new TrackInfo(
            Id: 1, Title: "Mein Titel", AlbumId: null, AlbumArtist: "Band", TrackNumber: 3,
            DiscNumber: 1, Year: 2020, Source: "musicbrainz", Confidence: 0.9, IsUserConfirmed: true);
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(track: track), tr);

        Assert.Contains("Mein Titel", text);
        Assert.Contains(tr.Tr("media_table.detail.confirmed_yes"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithTechnical_ListsPresentFieldsOnly()
    {
        var tr = new Translator("de");
        var technical = new TechnicalMetadata(
            ContainerFormat: "flac", AudioCodec: "flac", VideoCodec: null, BitrateKbps: 900,
            SampleRateHz: 44100, Channels: 2, DurationSeconds: 210.5, ResolutionWidth: null,
            ResolutionHeight: null, Fps: null, Hdr: null, ChaptersCount: null);
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(technical: technical), tr);

        Assert.Contains("audio_codec: flac", text);
        Assert.Contains("sample_rate_hz: 44100", text);
        Assert.DoesNotContain("video_codec:", text);
        Assert.DoesNotContain("resolution:", text);
    }

    [Fact]
    public void BuildMediaDetailText_EmbeddedArtworkReflectsFlag()
    {
        var tr = new Translator("de");
        var withArtwork = MediaTableSupport.BuildMediaDetailText(MinimalDetail(hasEmbeddedArtwork: true), tr);
        var withoutArtwork = MediaTableSupport.BuildMediaDetailText(MinimalDetail(hasEmbeddedArtwork: false), tr);

        Assert.Contains(tr.Tr("media_table.detail.embedded_artwork", ("value", tr.Tr("common.value_yes"))), withArtwork);
        Assert.Contains(tr.Tr("media_table.detail.embedded_artwork", ("value", tr.Tr("common.value_no"))), withoutArtwork);
    }

    // --- Gap K Schritt 4: Qualitaet/Loudness/KI/Quelle im Detailpanel -------

    [Fact]
    public void BuildMediaDetailText_WithoutQuality_OmitsQualitySectionEntirely()
    {
        var tr = new Translator("de");
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr);

        Assert.DoesNotContain(tr.Tr("media_table.detail.quality_header"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithQuality_ShowsFlagsAndNotes()
    {
        var tr = new Translator("de");
        var quality = new QualityInfo(
            MediaFileId: 1, SuspectedUpscale: true, SuspectedTranscode: false,
            SuspectedCorruption: false, SuspectedTruncation: false,
            Notes: new List<string> { "Verdaechtiges Spektrum oberhalb 16 kHz" });
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr, quality: quality);

        Assert.Contains(tr.Tr("media_table.detail.quality_header"), text);
        Assert.Contains("Verdaechtiges Spektrum oberhalb 16 kHz", text);
    }

    [Fact]
    public void BuildMediaDetailText_WithoutLoudnessHistory_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr);

        Assert.Contains(tr.Tr("media_table.detail.loudness_none"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithLoudnessHistory_ShowsLatestEntryFirst()
    {
        var tr = new Translator("de");
        var history = new List<LoudnessEntry>
        {
            new(1, 1, -13.5, -1.2, 7.0, -14.0, -1.0, true, "/out.flac", "2026-01-02T00:00:00"),
            new(2, 1, -16.0, -2.0, 8.0, -14.0, -1.0, false, null, "2026-01-01T00:00:00"),
        };
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr, loudnessHistory: history);

        Assert.Contains("-13.5", text);
        Assert.DoesNotContain("-16", text);
        Assert.Contains(tr.Tr("common.value_yes"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithoutAiEntries_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr);

        Assert.Contains(tr.Tr("media_table.detail.ai_none"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithAiEntries_ShowsModelAndConfidence()
    {
        var tr = new Translator("de");
        var entries = new List<AiMetadataEntry>
        {
            new(1, 1, "genre", "Ambient", true, "qwen2.5:0.5b", "1.0", 0.72, null, "2026-01-01T00:00:00", false),
        };
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr, aiEntries: entries);

        Assert.Contains("qwen2.5:0.5b", text);
        Assert.Contains("Ambient", text);
        Assert.Contains(tr.Tr("common.value_no"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithoutSources_ShowsNoneFallback()
    {
        var tr = new Translator("de");
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr);

        Assert.Contains(tr.Tr("media_table.detail.source_none"), text);
    }

    [Fact]
    public void BuildMediaDetailText_WithSources_ShowsProviderAndImportTimestamp()
    {
        var tr = new Translator("de");
        var sources = new List<MediaSourceEntry>
        {
            new(1, 1, "YouTube-Download", "youtube", "https://example.invalid/x", "abc", "2026-01-01T00:00:00", "download"),
        };
        var text = MediaTableSupport.BuildMediaDetailText(MinimalDetail(), tr, sources: sources);

        Assert.Contains("YouTube-Download", text);
        Assert.Contains("youtube", text);
    }
}
