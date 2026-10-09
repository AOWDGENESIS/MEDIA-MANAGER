# GENESIS Media Manager — Windows-Client (.NET/WPF)

> **Hinweis (aktualisiert, Sitzung 4):** Dieser Client kann in der
> Linux-Entwicklungssandbox weiterhin **nicht ausgeführt werden** (WPF
> rendert kein Fenster ohne Windows). Er kann hier aber sehr wohl
> **kompiliert und (soweit WPF-frei) getestet** werden - siehe
> "Bauen/Testen in der Linux-Sandbox" unten. Das war in einer frueheren
> Sitzung faelschlich als generell unmoeglich dokumentiert; tatsaechlich
> schlug nur die (unnoetige) Installation des vollen .NET SDK direkt nach
> `/tmp` mangels Speicherplatz fehl. Siehe `ARCHITECTURE.md` (ADR-0001) im
> Projekt-Root fuer die Begruendung der Hybrid-Architektur.

## Bauen/Testen in der Linux-Sandbox (verifiziertes Rezept, Sitzung 4)

Das .NET SDK ist in der Sandbox standardmaessig NICHT vorinstalliert und
wird auch nicht dauerhaft im Workspace gespeichert (ca. 400-600 MB inkl.
NuGet-Cache - das wuerde das Workspace-Snapshot-Limit sprengen). Es muss
daher am Anfang jeder Sitzung, in der am .NET-Code gearbeitet wird, neu
installiert werden (dauert ca. 15-20 Sekunden Download + Extraktion):

```bash
# WICHTIG: /tmp ist in der Sandbox ein kleines tmpfs (~1 GB) - das SDK
# (ca. 580 MB entpackt) UND dessen temporaere Entpack-Dateien duerfen NICHT
# beide in /tmp landen, sonst "No space left on device". Deshalb: Installationsziel
# ausserhalb von /tmp waehlen, TMPDIR aber ebenfalls ausserhalb von /tmp,
# und NACH der Session wieder entfernen (z.B. nach /tmp verschieben, s.u.),
# damit es nicht im persistierten Workspace landet.
curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
chmod +x /tmp/dotnet-install.sh
mkdir -p /home/user/.dotnet-tmp
TMPDIR=/home/user/.dotnet-tmp /tmp/dotnet-install.sh --channel 8.0 --install-dir /home/user/.dotnet

export PATH=/home/user/.dotnet:$PATH
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export HOME=/home/user

# WPF zielt auf net8.0-windows; auf Linux fehlt das Windows-Targeting-Pack
# standardmaessig. Mit EnableWindowsTargeting=true laedt dotnet die reinen
# Referenz-Assemblies (Microsoft.WindowsDesktop.App.Ref) per NuGet nach und
# kompiliert/typprueft den Code vollstaendig - nur AUSFUEHREN (dotnet run)
# geht weiterhin nicht, da WPF zur Laufzeit echtes Windows braucht.
cd ui-windows-dotnet/GenesisMediaManager.Client
dotnet build -p:EnableWindowsTargeting=true

# Das separate, reine net8.0-Testprojekt (keine WPF-Abhaengigkeit, siehe
# GenesisMediaManager.Client.Tests.csproj-Kommentar) laeuft ohne Sondertricks:
cd ../GenesisMediaManager.Client.Tests
dotnet test

# Danach UNBEDINGT aufraeumen, damit der naechste Workspace-Snapshot nicht
# durch SDK/NuGet-Cache ueberfuellt wird (siehe Nutzervorgabe "Workspace darf
# nie vollaufen"):
rm -rf /home/user/.dotnet /home/user/.dotnet-tmp /home/user/.nuget /home/user/.templateengine
rm -rf ui-windows-dotnet/*/bin ui-windows-dotnet/*/obj   # bin/obj sind ohnehin .gitignore-t
```

Verifiziert zuletzt in Sitzung 14 (Fortsetzung 12): `dotnet build
-p:EnableWindowsTargeting=true` im Client-Projekt → **0 Warnings, 0
Errors**; `dotnet test` im Testprojekt → **52/52 Tests grün**
(`TranslatorTests.cs` [11, deckt u.a. alle vier Pflichtsprachen DE/EN/JA/RU
ab, siehe `I18n/Translator.cs`] + `MediaTableSupportTests.cs` [22:
Nav-Key→Medienart-Zuordnung und VOLLER Detailtext-Aufbau der
Medientabellen-Ansicht inkl. Qualität/Loudness/KI/Quelle, siehe
`MediaTableSupport.cs`] + `MediaCoverSupportTests.cs` [9: Signatur-/
Magic-Bytes-Erkennung der Cover-Vorschau (PNG/JPEG/GIF/BMP/WEBP vs.
ungültige Daten), siehe `MediaCoverSupport.cs`] +
`SettingsViewSupportTests.cs` [7: Lese-/Schreib-Hilfslogik aller sieben
Einstellungen-Abschnitte inkl. Medienordner-Listenverwaltung, siehe
`SettingsViewSupport.cs`] + `ProvidersViewSupportTests.cs` [3: Lese-/
Schreib-Hilfslogik des `metadata`-Abschnitts der Metadaten-Provider-Seite,
siehe `ProvidersViewSupport.cs`]).

**Seither deutlich ausgebaut (Stand 2026-10-09):** Die Suite umfasst
inzwischen 15 Testdateien mit 134 Testmethoden (~208 Testfälle inkl.
Theory-Aufzählung): zusätzlich `MediaSearchFiltersTests` (Filter-Dialog-
Suchlogik), `MediaFileActionsSupportTests` (Kontextmenü-/Toolbar-Aktionen),
`MediaPlayerSupportTests` (Player-Parität), `LibraryBrowserSupportTests`
(Bibliotheks-Drill-down), `DuplicatesSupportTests`,
`DownloadCenterSupportTests`, `AiCenterSupportTests`,
`VoiceStudioSupportTests`, `JobQueueSupportTests` und
`ApiErrorSupportTests` (§37-Fehlerdialog-Textaufbau und -Parsing). Die
seit Sitzung 14 hinzugekommenen Tests konnten in der Sandbox noch NICHT
ausgeführt werden (dot.net/NuGet sind hier netzwerkseitig blockiert,
deshalb ist seitdem kein SDK-Download/Build/Test möglich) - ihr Lauf ist
Teil der nachzuholenden Windows-Verifikation (siehe PROGRESS.md).

## Voraussetzungen (unter Windows)

- .NET 8 SDK oder neuer (https://dotnet.microsoft.com, MIT-lizenziert)
- Der GENESIS Core Service muss laufen (`core/run_api.py`, Standard:
  `http://127.0.0.1:8420`)

## Bauen

```powershell
cd ui-windows-dotnet\GenesisMediaManager.Client
dotnet restore
dotnet build
dotnet run
```

## OpenAPI-Client generieren (empfohlen statt Handschrift)

Der Core Service liefert unter `/openapi.json` ein vollständiges
OpenAPI-3-Schema. Damit lässt sich ein typisierter C#-Client automatisch
generieren (z.B. mit NSwag oder Kiota), statt die DTOs manuell zu pflegen:

```powershell
dotnet tool install -g NSwag.ConsoleCore
nswag openapi2csclient /input:http://127.0.0.1:8420/openapi.json /classname:GenesisApiClient /namespace:GenesisMediaManager.Client.Api /output:Api/GenesisApiClient.Generated.cs
```

Die Datei `Api/GenesisApiClient.cs` in diesem Projekt enthält bereits eine
schlanke, handgeschriebene Minimalversion für den Start (Health-Check,
Dashboard, Media-Liste) — sie kann durch den generierten Client ersetzt oder
ergänzt werden, sobald mehr Endpunkte feststehen.

## Architekturregel

Dieses Projekt enthält **keine Fachlogik** (kein Scannen, kein Tag-Schreiben,
keine Fingerprint-/Loudness-/KI-Berechnung). Es ist eine reine
Präsentationsschicht über die lokale REST-API des Python Core Service
(siehe ADR-0001). Jede neue View ruft ausschließlich `GenesisApiClient` auf.

## Status

Grundgerüst (Phase 1): Projektstruktur, API-Client (`GenesisApiClient.cs`,
deckt inzwischen Dashboard/Settings/Media/Metadaten-Vorschläge/Umbenennen/
Artwork ab), Hauptfenster mit vollständiger Navigationsstruktur analog zu
`ui-reference-pyside` (Originalauftrag §4).

**Umgesetzte Seiten (echte Funktionalität, kein Platzhalter):**
- `nav.dashboard` — Zusammenfassung (Status, Anzahl Medien, fehlende
  Dateien, laufende Jobs).
- `nav.music`/`nav.audiobook`/`nav.movie`/`nav.episode`/`nav.podcast`/
  `nav.ai_music`/`nav.unknown`/`nav.search` — Medientabellen-Ansicht
  (`MainWindow.xaml.cs::ShowMediaTableAsync` + WPF-freie Hilfslogik in
  `MediaTableSupport.cs`/`MediaCoverSupport.cs`/`MediaFilters.cs`): Frei-
  textsuche, Filter-Dialog (Pendant `SearchFiltersDialog`), Tabelle mit
  Mehrfachauswahl, eingebetteter Medienplayer (seit 2026-10-08 mit voller
  Parität zu `player_bar.py`: Seek, Lautstärke, Zeit-/Daueranzeige,
  Fehleranzeige, Videobild für Filme/Episoden, Stop-and-Clear beim
  Neuladen), Kontextmenü UND
  Werkzeugleiste mit allen neun Werkzeug-Dialogen (Metadaten-Vorschläge/
  Umbenennen/Artwork/Lautheit/Cutter/Konvertieren/Hörbuch+Kapitel/
  Film+Serie/KI) sowie den zwei One-Shot-Analysen (Fingerprint/
  Qualität), Detailpanel mit VOLLEM Funktionsumfang der Python-Referenz-UI
  (Cover-Vorschau, Pfad/Technik/Qualitätsprüfung/Track-Metadaten/Artwork-
  Status/Loudness/KI-Analyse/Quelle, identische Reihenfolge und
  Sonderverhalten) — volle Parität zu `media_table.py` erreicht, siehe
  `docs/GAP_ANALYSIS.md` Gap K Siebter/Achter Schritt.
- `nav.artists`/`nav.albums`/`nav.titles`/`nav.genres`/`nav.persons`/
  `nav.sources` — Bibliotheks-Drill-down (`MainWindow.Library.cs` +
  `LibraryBrowserSupport.cs`, Pendant zu `library_view.py`, Gap B).
- `nav.duplicates` (`MainWindow.Duplicates.cs`, §21), `nav.download_center`/
  `nav.import` (`MainWindow.DownloadCenter.cs`, §30-§32), `nav.ai_metadata`
  (`MainWindow.AiCenter.cs`, §25/§26), `nav.voice_studio`/`nav.tts`
  (`MainWindow.VoiceStudio.cs`, §28/§29), `nav.plugins`
  (`MainWindow.Plugins.cs`, §34), `nav.logs` (`MainWindow.LogViewer.cs`,
  §54), `nav.backups` (`MainWindow.Backups.cs`, §40), `nav.diagnostics`
  (`MainWindow.Diagnostics.cs`, §38), `nav.job_queue`
  (`MainWindow.JobQueue.cs`, §35/§36), `nav.error_center`
  (`MainWindow.ErrorCenter.cs`, §37) — je eigenständige Seite, Pendant zur
  gleichnamigen Python-Ansicht.
- `nav.settings` — Einstellungen-Ansicht (`MainWindow.xaml.cs::
  ShowSettingsAsync` + WPF-freie Hilfslogik in `SettingsViewSupport.cs`):
  Lesen (`GET /settings`) UND Schreiben (`PATCH /settings`, immer erst
  nach Ja/Nein-Bestätigungsdialog) für ALLE SIEBEN Abschnitte der
  Python-Referenz-UI (Allgemein/Medienordner/KI/Sprachausgabe/Lautheit/
  Download-Center/Datenschutz) — volle funktionale Parität innerhalb
  dieser Ansicht. Ordnerauswahl (Medienordner hinzufügen, Download-
  Zielordner) nutzt `Microsoft.Win32.OpenFolderDialog` (seit .NET 8 Teil
  von WPF). "Jetzt scannen" ruft `POST /scan` mit der aktuellen
  Ordnerliste auf.
- `nav.providers` — Metadaten-Provider-Seite (`MainWindow.xaml.cs::
  ShowProvidersAsync` + WPF-freie Hilfslogik in `ProvidersViewSupport.cs`):
  Lesen UND Schreiben (nach Ja/Nein-Bestätigungsdialog) des `metadata`-
  Abschnitts von `GET`/`PATCH /settings` — betrifft AUSSCHLIESSLICH die
  ONLINE-Metadatenabgleich-Provider (MusicBrainz/AcoustID/Cover Art
  Archive), nicht die bereits über die Einstellungen-Ansicht verwalteten
  Download-/Import-Provider. Volle Parität zu
  `ui-reference-pyside/genesis_ui/views/providers_view.py`.

Alle ~20 Python-Ansichten/-Dialoge haben damit ein .NET-Pendant. **Status
(2026-10-09): Parity-Arbeit ABGESCHLOSSEN.** Die stichprobenartige
Tiefenprüfung jeder einzelnen .NET-Ansicht gegen ihre Python-Referenz
(Gap K) ist beendet - ALLE §1-§54-Ansichten sind Zeile-für-Zeile geprüft,
inklusive API-Ebene (Endpunkte/Payloads/DTO-Felder gegen
`core/genesis_core/api/app.py`), und Gap L (§37-Fehlerdialoge mit
Fehler-ID/Lösungshinweis an allen 35 `show_api_error`-Stellen) ist
geschlossen; damit sind die dokumentierten Gaps A-L sämtlich bearbeitet.
Befundliste und Fixes: `PROGRESS.md` 2026-10-08/2026-10-09 und
`docs/GAP_ANALYSIS.md` Abschnitt 5. Wiederkehrendes Muster der Prüfung:
.NET-Standardformate sind kulturabhängig, Python-f-Strings nicht - sieben
Locale-Bugs wurden behoben und per InvariantCulture-Tests unter
erzwungener de-DE-Kultur abgesichert. **Weiterhin nachzuholen (Windows-
Seite):** `dotnet build -p:EnableWindowsTargeting=true`, `dotnet test`
(inkl. der seit Sitzung 14 neu hinzugekommenen Tests) und eine visuelle
Abnahme. UI-Ausbau folgt weiter synchron zu den Entwicklungsphasen in
`PROGRESS.md`.
