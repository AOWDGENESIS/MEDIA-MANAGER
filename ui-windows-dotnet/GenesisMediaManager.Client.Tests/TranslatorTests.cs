// Laufzeittests fuer den .NET-Translator (ADR-0009). Spiegelt die
// Kernfaelle von core/tests/test_i18n.py und
// ui-reference-pyside/tests/test_i18n.py: Default-Sprache, Fallback auf
// Englisch bei fehlendem Schluessel in Zielsprache, roher Schluessel als
// letzter Rueckfallwert, benannte Platzhalter und alle vier
// Pflichtsprachen DE/EN/JA/RU (§53).
using GenesisMediaManager.Client.I18n;

namespace GenesisMediaManager.Client.Tests;

public class TranslatorTests
{
    [Fact]
    public void DefaultLanguageIsGerman()
    {
        var translator = new Translator();
        Assert.Equal("de", translator.Language);
        Assert.Equal("Dashboard", translator.Tr("nav.dashboard"));
    }

    [Theory]
    [InlineData("de", "MEDIEN")]
    [InlineData("en", "MEDIA")]
    [InlineData("ja", "メディア")]
    [InlineData("ru", "МЕДИА")]
    public void AllFourRequiredLanguagesResolveNavSection(string language, string expected)
    {
        var translator = new Translator(language);
        Assert.Equal(language, translator.Language);
        Assert.Equal(expected, translator.Tr("nav.section_media"));
    }

    [Fact]
    public void UnknownLanguageFallsBackToDefaultInsteadOfThrowing()
    {
        var translator = new Translator("fr");
        Assert.Equal("de", translator.Language);
    }

    [Fact]
    public void UnknownKeyReturnsRawKeyInsteadOfThrowing()
    {
        var translator = new Translator("de");
        Assert.Equal("this.key.does.not.exist", translator.Tr("this.key.does.not.exist"));
    }

    [Fact]
    public void NamedPlaceholdersAreSubstituted()
    {
        var translator = new Translator("de");
        var result = translator.Tr("dashboard.status",
            ("version", "0.2.0"), ("ai_provider", "ollama"), ("ai_status", "erreichbar"), ("mode", "AUS"));
        Assert.Contains("0.2.0", result);
        Assert.Contains("ollama", result);
        Assert.Contains("erreichbar", result);
        Assert.Contains("AUS", result);
    }

    [Fact]
    public void PythonFormatSpecIsAppliedLocaleIndependent()
    {
        // voice_studio.synthesize_done enthaelt in allen vier Katalogen
        // "{duration:.1f}s". Pythons str.format ist locale-unabhaengig
        // ("3.5"), also muss der .NET-Translator unter deutscher Kultur
        // ebenfalls "3.5" (NICHT "3,5") einsetzen und darf den
        // Formatspec nicht als Teil des Platzhalternamens stehen lassen.
        var translator = new Translator("de");
        var previous = System.Globalization.CultureInfo.CurrentCulture;
        System.Globalization.CultureInfo.CurrentCulture = new System.Globalization.CultureInfo("de-DE");
        try
        {
            var result = translator.Tr("voice_studio.synthesize_done",
                ("duration", 3.5), ("path", "C:\\tmp\\sample.wav"));
            Assert.Equal("Fertig (3.5s) - gespeichert unter: C:\\tmp\\sample.wav", result);
        }
        finally
        {
            System.Globalization.CultureInfo.CurrentCulture = previous;
        }
    }

    [Fact]
    public void NumericPlaceholdersWithoutSpecStayInvariant()
    {
        var translator = new Translator("de");
        var previous = System.Globalization.CultureInfo.CurrentCulture;
        System.Globalization.CultureInfo.CurrentCulture = new System.Globalization.CultureInfo("de-DE");
        try
        {
            var result = translator.Tr("settings_view.scan_done", ("count", 1234));
            Assert.Contains("1234", result);
        }
        finally
        {
            System.Globalization.CultureInfo.CurrentCulture = previous;
        }
    }

    [Fact]
    public void SetLanguageSwitchesLiveWithoutRecreatingInstance()
    {
        var translator = new Translator("de");
        Assert.Equal("MEDIEN", translator.Tr("nav.section_media"));
        translator.SetLanguage("en");
        Assert.Equal("MEDIA", translator.Tr("nav.section_media"));
    }

    [Fact]
    public void DefaultSingletonCanBeReconfigured()
    {
        Translator.ConfigureDefaultLanguage("ja");
        Assert.Equal("ja", Translator.Default.Language);
        Translator.ConfigureDefaultLanguage("de");
        Assert.Equal("de", Translator.Default.Language);
    }

    [Fact]
    public void CatalogDirectoryIsFoundRelativeToRepositoryRoot()
    {
        // Architektur-Wächter (analog zu den Python-Testsuiten): stellt
        // sicher, dass der Loader tatsaechlich die echten, geteilten
        // i18n/<sprache>.json-Dateien im Repository findet und nicht
        // stillschweigend auf leere Kataloge zurueckfaellt.
        var dir = Translator.DefaultCatalogDir();
        Assert.True(Directory.Exists(dir), $"Katalogverzeichnis nicht gefunden: {dir}");
        foreach (var language in Translator.SupportedLanguages)
        {
            Assert.True(File.Exists(Path.Combine(dir, $"{language}.json")), $"{language}.json fehlt in {dir}");
        }
    }
}
