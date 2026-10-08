// i18n-Mechanismus der WPF-UI (§53 - keine hartcodierten UI-Texte).
//
// Siehe ADR-0009 (DECISIONS.md) fuer die volle Begruendung: dieselben
// rohen `i18n/<sprache>.json`-Dateien aus dem Repository-Wurzelverzeichnis
// werden von DREI unabhaengigen, bewusst kleinen Loader-Implementierungen
// gelesen (hier, `core/genesis_core/i18n/__init__.py`,
// `ui-reference-pyside/genesis_ui/i18n.py`) - geteilt wird nur das
// JSON-DATENFORMAT, nicht der Code. Diese Klasse importiert bzw.
// referenziert nichts aus den anderen beiden Implementierungen (kann sie
// als .NET-Projekt ohnehin nicht importieren) und verletzt daher keine
// ADR-0001-Grenze.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace GenesisMediaManager.Client.I18n;

public sealed class Translator
{
    public static readonly string[] SupportedLanguages = { "de", "en", "ja", "ru" };
    private const string DefaultLanguage = "de";
    private const string FallbackLanguage = "en";

    private readonly string _catalogDir;
    private readonly Dictionary<string, Dictionary<string, string>> _catalogs = new();
    private readonly HashSet<string> _warnedMissingKeys = new();

    public string Language { get; private set; } = DefaultLanguage;

    public Translator(string language = DefaultLanguage, string? catalogDir = null)
    {
        _catalogDir = catalogDir ?? DefaultCatalogDir();
        SetLanguage(language);
    }

    /// <summary>
    /// Repository-Wurzel ausgehend vom Ausfuehrungsverzeichnis der App
    /// gesucht (../../../i18n relativ zum Build-Output in Entwicklung,
    /// mit Override via Umgebungsvariable GENESIS_I18N_DIR fuer ein
    /// spaeteres gepacktes Installer-Layout, bei dem die Kataloge z.B.
    /// direkt neben der .exe liegen).
    /// </summary>
    public static string DefaultCatalogDir()
    {
        var envOverride = Environment.GetEnvironmentVariable("GENESIS_I18N_DIR");
        if (!string.IsNullOrWhiteSpace(envOverride))
        {
            return envOverride;
        }

        var baseDir = AppContext.BaseDirectory;
        // Entwicklungsszenario: bin/Debug/net8.0-windows/ -> Repo-Wurzel ist
        // vier Ebenen hoeher (GenesisMediaManager.Client/bin/Debug/netX ->
        // ui-windows-dotnet -> Repo-Wurzel).
        var candidate = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "..", "i18n"));
        if (Directory.Exists(candidate))
        {
            return candidate;
        }
        // Fallback: direkt neben der ausfuehrbaren Datei (gepacktes Deployment).
        return Path.Combine(baseDir, "i18n");
    }

    public void SetLanguage(string language)
    {
        if (Array.IndexOf(SupportedLanguages, language) < 0)
        {
            language = DefaultLanguage;
        }
        LoadCatalog(DefaultLanguage);
        LoadCatalog(FallbackLanguage);
        LoadCatalog(language);
        Language = language;
    }

    private Dictionary<string, string> LoadCatalog(string language)
    {
        if (_catalogs.TryGetValue(language, out var cached))
        {
            return cached;
        }

        var path = Path.Combine(_catalogDir, $"{language}.json");
        if (!File.Exists(path))
        {
            _catalogs[language] = new Dictionary<string, string>();
            return _catalogs[language];
        }

        using var stream = File.OpenRead(path);
        var document = JsonDocument.Parse(stream);
        var flat = new Dictionary<string, string>();
        Flatten(document.RootElement, "", flat);
        _catalogs[language] = flat;
        return flat;
    }

    private static void Flatten(JsonElement element, string prefix, Dictionary<string, string> target)
    {
        foreach (var property in element.EnumerateObject())
        {
            var key = prefix.Length == 0 ? property.Name : $"{prefix}.{property.Name}";
            if (property.Value.ValueKind == JsonValueKind.Object)
            {
                Flatten(property.Value, key, target);
            }
            else
            {
                target[key] = property.Value.GetString() ?? string.Empty;
            }
        }
    }

    /// <summary>
    /// Loest <paramref name="key"/> (z.B. "nav.dashboard") zu lokalisiertem
    /// Text auf. Reihenfolge: aktuelle Sprache -> Englisch -> roher
    /// Schluessel (NIE eine Exception/leere UI-Stelle, Prinzip "kein
    /// stiller Fehlschlag"). Die JSON-Kataloge verwenden BENANNTE
    /// Platzhalter im Python-`.format(**kwargs)`-Stil (z.B. "{version}"),
    /// NICHT .NETs positionsbasierte "{0}"-Syntax - deshalb hier eine
    /// kleine eigene Ersetzung statt <c>string.Format</c>, die exakt
    /// dasselbe Platzhalterformat versteht wie die beiden Python-
    /// Implementierungen (inkl. "{{literal}}" fuer Textstellen, die
    /// tatsaechlich geschweifte Klammern zeigen sollen, z.B. die
    /// Vorlagen-Hinweise im Rename-Dialog).
    /// </summary>
    public string Tr(string key, params (string Name, object Value)[] args)
    {
        foreach (var candidate in new[] { Language, FallbackLanguage, DefaultLanguage })
        {
            if (_catalogs.TryGetValue(candidate, out var catalog) && catalog.TryGetValue(key, out var template))
            {
                return FormatNamed(template, args);
            }
        }
        if (_warnedMissingKeys.Add(key))
        {
            Console.Error.WriteLine($"i18n: Schluessel '{key}' fehlt fuer Sprache '{Language}'.");
        }
        return key;
    }

    /// <summary>
    /// Ersetzt benannte Platzhalter "{name}" durch die zugehoerigen Werte
    /// aus <paramref name="args"/>, laesst "{{"/"}}" als literale einzelne
    /// Klammern durch und laesst unbekannte "{irgendwas}"-Platzhalter
    /// UNVERAENDERT stehen (kein KeyError/Exception wie bei Pythons
    /// str.format mit fehlendem kwarg - lieber ein sichtbarer Platzhalter
    /// in der UI als ein Absturz).
    /// </summary>
    private static string FormatNamed(string template, (string Name, object Value)[] args)
    {
        var values = new Dictionary<string, string>();
        foreach (var (name, value) in args)
        {
            values[name] = value?.ToString() ?? string.Empty;
        }

        var result = new System.Text.StringBuilder(template.Length);
        var i = 0;
        while (i < template.Length)
        {
            var c = template[i];
            if (c == '{' && i + 1 < template.Length && template[i + 1] == '{')
            {
                result.Append('{');
                i += 2;
                continue;
            }
            if (c == '}' && i + 1 < template.Length && template[i + 1] == '}')
            {
                result.Append('}');
                i += 2;
                continue;
            }
            if (c == '{')
            {
                var closeIndex = template.IndexOf('}', i + 1);
                if (closeIndex > i)
                {
                    var name = template.Substring(i + 1, closeIndex - i - 1);
                    if (values.TryGetValue(name, out var substituted))
                    {
                        result.Append(substituted);
                        i = closeIndex + 1;
                        continue;
                    }
                    // Unbekannter Platzhalter: unveraendert stehen lassen
                    // statt eine Exception zu werfen (kein stiller Absturz).
                    result.Append(template, i, closeIndex - i + 1);
                    i = closeIndex + 1;
                    continue;
                }
            }
            result.Append(c);
            i += 1;
        }
        return result.ToString();
    }


    private static Translator? _default;

    public static Translator Default => _default ??= new Translator();

    public static void ConfigureDefaultLanguage(string language) => Default.SetLanguage(language);
}
