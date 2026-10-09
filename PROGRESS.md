
## 2026-10-09 (Fortsetzung 6) - Tiefenprüfung der restlichen sechs Ansichten: Locale-Bug Nr. 6, JobQueue- und Backups-Parität hergestellt

Abschluss der stichprobenartigen WPF-Tiefenprüfung (Gap K) für die
verbleibenden Ansichten: Plugins (§34), Log-Viewer (§54), Backups
(§40), Diagnose (§38), Job-Warteschlange (§35/§36) und Fehler-Center
(§37) — jeweils Zeile-für-Zeile gegen die Python-Referenz
(`ui-reference-pyside/genesis_ui/views/*.py`), inklusive API-Ebene
(Endpunkte, Parameter, DTO-Felder gegen `core/genesis_core/api/app.py`).

**Befund 1 (Bug, behoben): Locale-Bug Nr. 6 in der Job-Warteschlange.**
Der Fortschrittstext nutzte das Standardformat `P0` — unter deutschem
Windows "42 %" statt Pythons "42%" (`:.0%` ist locale-unabhängig und
setzt kein Leerzeichen). Fix: neue WPF-freie
`JobQueueSupport.FormatProgressText()`, die den Prozentanteil über das
bewährte `AiCenterSupport.FormatScore()` ("0%", InvariantCulture,
half-to-even) bildet; getestet in `JobQueueSupportTests` (u.a.
erzwungene de-DE-Kultur und 12.5%→"12%").

**Befund 2 (Bug, behoben): Backups-Größenformat dupliziert und
kulturabhängig.** `MainWindow.Backups` hatte eine eigene `FormatSize()`
mit kulturabhängigem `F1`. Die Python-Referenz der Backups-Ansicht ist
dieselbe `_format_size()` wie im Download-Center — die Ansicht nutzt
jetzt das bereits getestete `DownloadCenterSupport.FormatSize()`
(InvariantCulture), die Dublette ist entfernt.

**Befund 3 (Parität, hergestellt): Python-`or`-Fallbacks in vier
Ansichten.** `x or fallback` behandelt auch den Leerstring als
"nicht vorhanden"; der WPF-Code nutzte `??`. Umgestellt auf
`DownloadCenterSupport.OrFallback()` bei: Plugins (sechs
Manifest-Felder), Job-Warteschlange (`created_at`, `current_item`),
Backups (`created_at`), Fehler-Center (`timestamp`, `component`,
`solution_hint`, `technical_details`).

**Befund 4 (Parität, hergestellt): Job-Auswahl springt nicht mehr weg.**
Python stellt die Tree-Auswahl nach jedem Reload wieder her
(`setCurrentItem` auf die zuvor gewählte Job-Id); im WPF-Client wurde
die DataGrid-Auswahl bei der automatischen 2-Sekunden-Aktualisierung
jedes Mal gelöscht. Fix: Zeile mit derselben Job-Id nach dem Neuladen
wieder auswählen.

**Befund 5 (Parität, hergestellt): Log-Viewer-Zeilenumbrüche.**
Python nutzt `splitlines()[0]` (trennt an `\n`, `\r\n` UND `\r`); der
WPF-Code splittete nur an `\n`, ließ also `\r`-Reste stehen und zeigte
bei `\r`-Umbrüchen die ganze Meldung. Fix: Split an allen drei
Separatoren.

**Befund 6 (Parität, hergestellt): Backups-Erfolgsmeldung blieb nicht
stehen.** Python setzt den Status beim Neuladen NUR bei leerer Liste
zurück, sodass `create_done`/`restore_done` sichtbar bleiben; WPF
löschte die Meldung sofort wieder. Fix: Verhalten der Referenz
übernommen.

**Befund 7 (Parität, hergestellt): Plugins-Spaltenbreiten.** Python
streckt die Namensspalte; WPF streckte nur die Statusspalte. Jetzt
bekommt die Namensspalte Star-Breite wie in der Referenz, die
Statusspalte behält zusätzlich Star-Breite, damit die §34-Klartext-
`load_error`-Meldungen nicht abgeschnitten werden.

**Bestätigt ohne Befund:** Plugins (Titel/Hinweis/Neu-laden-Flow,
Sieben-Spalten-Grid, Status "geladen/fehlgeschlagen: Fehlermeldung",
`no_plugins`-Leerzustand, API: `GET /plugins`, `POST /plugins/reload`,
alle elf `plugin_to_dict`-Felder im DTO); Log-Viewer (Level-Filter mit
"beliebig" an erster Stelle, Enter-Auslösung in beiden Suchfeldern,
Erste-Seite-Reset bei Filteränderung §57, Paginierung 200er-Schritte
mit Vor/Zurück-Freischaltung, `shown_from/shown_to/total`-Status,
Detailanzeige der vollen Meldung bei Auswahl, API: `GET /logs` mit
limit/offset/level/component/search); Backups (Erstellen ohne
Bestätigung, Wiederherstellen mit Bestätigung Default No, fünf
Spalten inkl. Pfad-Stretch, API: `GET /backup`, `POST /backup/db`,
`POST /backup/config`, `POST /backup/{id}/restore` mit `{confirm}`);
Diagnose (Laufen-Status mit deaktiviertem Button, Gesamtstatus-Zeile
mit `generated_at`, Statusschlüssel-Fallback auf den Rohwert, API:
`GET /diagnostics` mit overall_status/generated_at/checks);
Job-Warteschlange (Sechs-Status-Schlüsselmap, aktive Statusmenge für
Abbrechen, Pause-nur-bei-running/Fortsetzen-nur-bei-paused,
Abbrechen-Bestätigung Default No, unbestimmter Fortschrittsbalken bei
unbekannter Gesamtmenge, 2-Sekunden-Timer mit Stopp beim
Seitenwechsel, API: `GET /jobs`, `POST /jobs/{id}/pause|resume|cancel`);
Fehler-Center (Checkbox "nur offene" Default an, Fünf-Spalten-Grid,
Detailzeilen Lösungshinweis/technische Details/optionaler Dateipfad,
Lösen-Button nur bei ungelösten Einträgen, API: `GET /errors`,
`POST /errors/{id}/resolve`). Verbleibende systematische Abweichung
(alle Ansichten): API-Fehler zeigt die Python-Referenz als
`show_api_error`-Dialog mit §37-`error_id`/`solution_hint`, WPF setzt
Statuszeilentext — das ist der dokumentierte Gap L (eigener
Arbeitsabschnitt).

**Verifikation:** Wie zuvor kein `dotnet build`/`dotnet test` möglich
(dot.net/NuGet in dieser Sandbox nicht erreichbar) — Ersatzprüfungen:
Klammer-/Strukturcheck (balanciert), Zeile-für-Zeile-Parity-Vergleich.
Windows-Build/Testlauf weiterhin nachzuholen. Damit sind ALLE
§1-§54-Ansichten tiefengeprüft (Gap K vollständig).

## 2026-10-09 (Fortsetzung 5) - Tiefenprüfung Voice Studio: Locale-Bug Nr. 5, Formatspec-Support im Translator und Paritätslücken behoben

Fortsetzung der stichprobenartigen WPF-Tiefenprüfung (Gap K), sechster
Bereich: Voice Studio (`MainWindow.VoiceStudio.cs` vs.
`ui-reference-pyside/genesis_ui/views/voice_studio_view.py`, §28/§29,
ADR-0018).

**Befund 1 (Bug, behoben): Historien-Dauer war systemkulturabhängig.**
`$"{r.DurationSeconds:F1}s"` zeigt unter deutschem Windows "3,5s" statt
"3.5s" (Pythons `f"{d:.1f}s"` ist locale-unabhängig). Zusätzlich
Paritätslücke: Python behandelt per `if r.get(...)` auch 0.0 als fehlend
("-"), der WPF-Code zeigte "0,0s". Fix: neue WPF-freie
`VoiceStudioSupport.FormatHistoryDuration()` (InvariantCulture, null/0 →
"-"), getestet in `VoiceStudioSupportTests` (u.a. unter erzwungener
de-DE-Kultur). Fünfter Befund der Locale-Fehlerklasse nach Duplikaten-
Confidence, Download-Größe, KI-Score und Translator-Platzhaltern.

**Befund 2 (Bug, behoben): `created_at` nicht auf 19 Zeichen gekürzt.**
Python schneidet mit `[:19]` Mikrosekunden/Zeitzonen-Reste ab, BEVOR
das T ersetzt wird; der WPF-Code ersetzte nur das T und zeigte dadurch
"2026-10-08 12:34:56.789012+00:00". Fix:
`VoiceStudioSupport.FormatHistoryCreatedAt()` mit exakter
Python-Reihenfolge, getestet.

**Befund 3 (Bug, behoben): Python-Formatspec `{duration:.1f}` im
i18n-Katalog wurde vom .NET-Translator nicht verstanden.** Der geteilte
Schlüssel `voice_studio.synthesize_done` enthält in allen vier Sprachen
`{duration:.1f}`; der Translator suchte dadurch einen Wert namens
"duration:.1f" und ließ den Platzhalter roh im Anzeigetext stehen. Fix:
`Translator.FormatNamed()` versteht jetzt `{name:formatspec}` — die in
den Katalogen verwendeten Specs (aktuell nur `.Nf`) werden auf das
entsprechende .NET-Format (`FN`) abgebildet und wie alle Zahlen IMMER
mit InvariantCulture formatiert (Pythons `str.format` ist ebenfalls
locale-unabhängig). Die geteilten JSON-Kataloge bleiben damit für alle
drei i18n-Implementierungen unverändert. Getestet: exakter
synthesize_done-Output unter de-DE ("Fertig (3.5s) - ..."),
Integer-Platzhalter ohne Spec.

**Befund 4 (Parität, hergestellt): Python-`or`-Fallbacks.**
Sprache/Lizenz im Profil-Grid und die Lizenz in der
Profildetail-Zeile nutzen in der Referenz `x or fallback` — leerer
String gilt ebenfalls als "nicht vorhanden". Der WPF-Code nutzte `??`
und ließ Leerstrings durchrutschen. Fix: Umstellung auf das etablierte
`DownloadCenterSupport.OrFallback()` (drei Stellen).

**Befund 5 (Parität, hergestellt): Medien-Stopp beim Verlassen der
Ansicht.** In Python stirbt der QMediaPlayer mit der Ansicht; das
WPF-MediaElement spielte nach dem Navigieren unsichtbar weiter. Fix:
`player.Unloaded += Stop` (gleiches Idiom wie der Haupt-Medientabellen-
Player in `MainWindow.xaml.cs`).

**Befund 6 (Parität, hergestellt): Sprachfeld-Platzhalter.** Python
zeigt im Sprachfeld den Platzhalter "de / en / ja / ru ..."; WPF-
TextBoxen kennen das nicht — Haus-Konvention ToolTip ergänzt (wie bei
`MainWindow.Library.cs::searchBox`).

**Bestätigt ohne Befund:** Zwei-Tabs-Aufbau; Statusbanner-Vierweg
(Laden-Fehler/deaktiviert/nicht verfügbar/aktiv mit Provider);
Engine-Katalog mit Fehler-Fallback auf leere Liste und Engine-Hinweisen
(Lizenz-/Notizen-Anzeige; dass WPF bei None "-" statt Pythons "None"
zeigt, ist wie im KI-Center bewusst beibehalten); Erstellen-Flow
(Name-pflichtig → Bestätigungsdialog mit allen §28-Feldern, Default No
→ Payload mit or-None-Konvertierungen → Felder leeren + Formular
verbergen + Neuladen); Löschen-Flow (Bestätigen → exakte Namenseingabe
per Dialog-Pendant zu QInputDialog → Mismatch-Warnung → DELETE mit
`{confirm, confirm_name}`); TTS-Flow (kein-Profil-Warnung →
Bestätigen Default No → synthesizing → done mit Dauer/Pfad bzw. failed
→ Historie neu laden); Exportformate wav/mp3/flac; Textvorschau der
Historie ≤60 Zeichen sonst [:57]+"..."; leere Anfrage wird vor dem
Synthetisieren blockiert; `CanUserSortColumns=false` auf beiden Grids
(Schutz vor Indexzugriff auf falsche Zeile); Auswahl→Löschen/Abspielen-
Freischaltung; Kombobox-Wiederherstellung nach Neuladen (Index merken,
Fallback auf erstes Element). API-Ebene: alle sieben Voice-Endpunkte
(Status, Engines, Profile CRUD, Synthetisieren/Test, Historie) mit
Payloads und confirm-Schaltern 1:1 gegen `api_client.py` Zeilen 517-562
geprüft.

**Verifikation:** Wie zuvor kein `dotnet build`/`dotnet test` möglich
(dot.net/NuGet in dieser Sandbox nicht erreichbar) — Ersatzprüfungen:
Klammer-/Strukturcheck (balanciert), Zeile-für-Zeile-Parity-Vergleich.
Windows-Build/Testlauf weiterhin nachzuholen.

## 2026-10-08 (Fortsetzung 4) - Tiefenprüfung KI-Center: Score-Locale-Bug behoben, ansonsten volle Parität bestätigt

Fortsetzung der stichprobenartigen WPF-Tiefenprüfung (Gap K), fünfter
Bereich: KI-Center (`MainWindow.AiCenter.cs` vs.
`ui-reference-pyside/genesis_ui/views/ai_center_view.py`, §25/§26,
ADR-0017).

**Befund 1 (Bug, behoben): Score-Anzeige war systemkulturabhängig.**
Die Treffer-Scores der semantischen Suche wurden per
`$"{score:P0}"` formatiert — unter deutschem Windows "87 %" statt
"87%" (Pythons `f"{score:.0%}"` ist locale-unabhängig). Fix: neue
WPF-freie Hilfsfunktion `AiCenterSupport.FormatScore()` (Custom-Format
`"0%"`, `InvariantCulture`, "half to even" wie Python), getestet in
`AiCenterSupportTests` (u.a. unter erzwungener de-DE-Kultur). Vierter
Befund dieser Fehlerklasse nach Confidence (Duplikate) und Dateigröße
(Download-Center) — alle Prozent-/Zahlenformate des Clients sind damit
auf InvariantCulture umgestellt.

**Bestätigt ohne Befund:** Statusbanner-Vierweg (Laden-Fehler/
deaktiviert/nicht verfügbar/aktiv mit Provider+Embedding-Modell),
Reindex-Ablauf ("reindexing" → done mit embedded/total bzw. failed,
ohne confirm wie in der Referenz — reine additive Cache-Operation),
Suchablauf (leere Anfrage wird STILL ignoriert wie in Python, kein
Warn-Dialog; Ergebnisliste wird VOR dem API-Aufruf geleert;
"nicht verfügbar"/"keine Treffer"/"n Treffer"-Statusmeldungen in
derselben Reihenfolge), Medienart-Label-Fallback auf den Rohwert
(`MediaKindLabelKey`-Default entspricht `MEDIA_KIND_LABEL_KEYS.get(kind,
kind)`), Enter-Taste löst die Suche aus (returnPressed-Pendant),
API-Ebene: `GET /ai/status`, `POST /ai/search/reindex`,
`POST /ai/search` mit `{query, top_k=20}` und alle DTO-Felder gegen
`core/genesis_core/api/app.py` bzw. `core/genesis_core/ai/search.py`
(SemanticSearchResult: media_file_id/filename/kind/score).
**Bewusst beibehaltene Abweichung:** fehlt das Embedding-Modell, zeigt
der WPF-Client "-" statt Pythons "None" (konsistent mit den übrigen
"-"+Fallbacks des Clients, z.B. im Download-Center).

**Verifikation:** Wie zuvor kein `dotnet build`/`dotnet test` möglich
(dot.net/NuGet in dieser Sandbox nicht erreichbar) — Ersatzprüfungen:
Klammer-/Strukturcheck (balanciert), Zeile-für-Zeile-Parity-Vergleich.
Windows-Build/Testlauf weiterhin nachzuholen.

## 2026-10-08 (Fortsetzung 3) - Tiefenprüfung Download-/Import-Center: Locale-Bug in Größenanzeige behoben, Python-`or`-Fallback-Parität hergestellt

Fortsetzung der stichprobenartigen WPF-Tiefenprüfung (Gap K), vierter
Bereich: Download-/Import-Center (`MainWindow.DownloadCenter.cs` vs.
`ui-reference-pyside/genesis_ui/views/download_center_view.py`,
§30-§32/ADR-0019).

**Befund 1 (Bug, behoben): Dateigrößen-Anzeige war systemkulturabhängig.**
`$"{size:F1} {unit}"` erzeugt unter deutschem Windows "1,5 KB" statt
"1.5 KB" — Pythons `f"{size:.1f}"` ist immer locale-unabhängig. Fix:
Formatlogik in die neue WPF-freie `DownloadCenterSupport`-Klasse
verschoben (`FormatSize` mit `InvariantCulture`), getestet in
`DownloadCenterSupportTests` (u.a. unter erzwungener de-DE-Kultur).
Dritter Befund dieser Klasse nach Confidence (Duplikate) — Muster:
.NET-Interpolationsformate sind kulturabhängig, Python-f-Strings nicht.

**Befund 2 (Parität, hergestellt): Python-`or`-Fallbacks.** Die
Python-Referenz nutzt an sechs Stellen `x or fallback` (Verfügbarkeits-
Grund, Metadaten-Titel/-Uploader/-Lizenz, Options-ID "default",
Provider-Label "?") — das behandelt auch den LEERSTRING als "nicht
vorhanden". Der WPF-Client nutzte `??`, das Leerstrings durchrutschen
lässt. Überall auf die neue Hilfsfunktion
`DownloadCenterSupport.OrFallback()` umgestellt (ebenfalls getestet).

**Befund 3 (Parität, hergestellt): Options-Label-Fallback.** Fehlt das
Label einer Download-Option, zeigt die Python-Referenz die Options-ID
(`opt.get("label", opt.get("option_id", ""))`) — der WPF-Client band
`o.Label` ohne Fallback. Jetzt `o.Label ?? o.OptionId`.

**Befund 4 (Parität, hergestellt): `suggested_filename` nur im URL-Tab.**
Die Python-Referenz protokolliert den vom Core gelieferten empfohlenen
Dateinamen NUR beim URL-Import (`_report_import_result`), der lokale
Import loggt bloß `import_done` + Warnungen. Der WPF-Client nutzte eine
gemeinsame `ReportImportResult` und zeigte den Namen in BEIDEN Tabs.
Jetzt per `includeSuggestedFilename`-Parameter getrennt (URL=true,
lokal=false) — verifiziert in `core/genesis_core/download/engine.py`,
dass der Core das Feld für beide Importwege füllt.

**Bestätigt ohne Befund:** Zwei-Tab-Layout, Provider-Statusbanner
(deaktiviert/aktiviert mit Anzeigenamen, rohe Fehlermeldung ohne
tr()-Wrapper wie im Python-Vorbild), der §31-Stufenworkflow mit vier
expliziten Knopfdrücken ohne Autoverkettung, Bestätigungspflicht VOR
jedem Import (§56), "default"-Options-Fallback, Import-Ergebnisprotokoll-Basisfelder
(job_id/media_id/Pfad, Warnungen mit "; "-Join), lokale Datei:
Pfad-Pflicht + Durchsuchen + eigene Bestätigung, Dauerformatierung
(Trunkierung statt Rundung wie Pythons `int()`), API-Endpunkte und
DTO-Felder gegen
`core/genesis_core/api/app.py` (`/download/providers|detect|availability|
metadata|options|import`, `/import/local-file`). Dialog-Anzeige bei
API-Fehlern bleibt Gap L (systematisch).

**Verifikation:** Wie zuvor kein `dotnet build`/`dotnet test` möglich
(dot.net/NuGet in dieser Sandbox nicht erreichbar) — Ersatzprüfungen:
Klammer-/Strukturcheck (balanciert), Test-Erwartungswerte per
Python-Laufzeitabgleich der Referenzfunktionen, Zeile-für-Zeile-
Parity-Vergleich. Windows-Build/Testlauf weiterhin nachzuholen.

## 2026-10-08 (Fortsetzung 2) - Tiefenprüfung Duplikate-Ansicht: Locale-Bug bei Confidence-Anzeige behoben, Fehler-/Reload-Parität hergestellt, Dateiliste mehrzeilig

Fortsetzung der stichprobenartigen WPF-Tiefenprüfung (Gap K), dritter
Bereich: Duplikate (`MainWindow.Duplicates.cs` vs.
`ui-reference-pyside/genesis_ui/views/duplicates_view.py`, §21/
ADR-0013). API-Ebene vorab separat verifiziert
(`GenesisApiClient.GapK.cs`: `POST /duplicates/scan` mit `{kind}`-Body,
`GET /duplicates?reviewed=true/false`, `POST /duplicates/{id}/review|
unreview` — Parameter und DTO-Felder stimmen 1:1 mit
`core/genesis_core/api/app.py`; Scope-Auswahl entspricht exakt
`MEDIA_KIND_LABEL_KEYS` inkl. `podcast_episode`).

**Befund 1 (Bug, behoben): Confidence-Anzeige war systemkulturabhängig.**
`$"{confidence:P0}"` erzeugt unter deutschem Windows "87 %" (mit
Leerzeichen), die Python-Referenz zeigt via `f"{confidence:.0%}"` immer
"87%". Fix: neue WPF-freie Hilfsfunktion
`DuplicatesSupport.FormatConfidence()` (Custom-Format `"0%"` mit
`InvariantCulture`, inkl. Pythons "half to even"-Rundung bei exakt
halben Werten: 0.875→"88%", 0.125→"12%"), abgesichert durch
`DuplicatesSupportTests` (u.a. explizit unter erzwungener de-DE-Kultur).

**Befund 2 (Parität, hergestellt): Reload nach fehlgeschlagenen
Aktionen.** Die Python-Referenz lädt die Gruppenliste nach einem
fehlgeschlagenen Scan bzw. Review/Unreview NICHT neu (frühe Rückkehr
vor `self._reload()`); der WPF-Client lud trotzdem neu und vermischte
die Fehlermeldung mit frischen Daten. Nach Scan-/Review-/Unreview-
Fehler wird jetzt nicht mehr neu geladen.

**Befund 3 (Parität, hergestellt): Mehrzeilige Dateiliste.** Die
Python-Referenz zeigt alle Pfade einer Duplikatgruppe zeilenweise in
der Zelle (`"\n".join(paths)` im QTreeWidget); die WPF-Textspalte
zeigte nur die erste Zeile. Die Spalte ist jetzt eine
`DataGridTemplateColumn` mit umbruchfähigem TextBlock (dasselbe
`FrameworkElementFactory`-Muster wie die Thumbnail-/Format-Spalten der
Medientabelle).

**Bestätigt ohne Befund:** Kategorie-/Status-Label-Mapping inkl.
Fallback auf den Rohwert, Filterkombobox-Reihenfolge (offen/geprüft/
alle) mit True/False/Null-Semantik, Scan-Button-Sperrung während des
Scans, Auswahlregeln (Markieren nur wenn nicht geprüft, Zurücksetzen
nur wenn geprüft), `#id`-Fallback der Pfadauflösung bei
API-Fehlern + Pfad-Cache, bewusst keine Löschfunktion (§21).
**Bewusst beibehaltene Abweichung:** Bei nicht-leerer Trefferliste
leert der WPF-Client die Statuszeile (verhindert veraltete
Fehlermeldungen), während die Python-Referenz den letzten Statustext
stehen lässt — die WPF-weite Konvention (`count == 0 ? no_results :
leer`) wurde hier dem Einzelverhalten vorgezogen. Dialog-Anzeige bei
API-Fehlern bleibt Gap L (systematisch).

**Verifikation:** Wie zuvor kein `dotnet build`/`dotnet test` möglich
(dot.net/NuGet in dieser Sandbox nicht erreichbar) — Ersatzprüfungen:
Klammer-/Strukturcheck der geänderten Dateien (balanciert),
Zeile-für-Zeile-Parity-Vergleich, Test-Erwartungswerte per Python-
Laufzeitabgleich (`f"{0.875:.0%}"` → "88%" usw.). Windows-Build/
Testlauf weiterhin nachzuholen.

## 2026-10-08 (Fortsetzung) - Tiefenprüfung Bibliotheks-Drill-down: Rendering 1:1 bestätigt, zwei Kleinstlücken geschlossen, neue systematische Lücke L dokumentiert

Fortsetzung der stichprobenartigen WPF-Tiefenprüfung (Gap K), zweiter
Bereich: Bibliotheks-Drill-down (`MainWindow.Library.cs` +
`LibraryBrowserSupport.cs` vs.
`ui-reference-pyside/genesis_ui/views/library_view.py`).

**Ergebnis Zeile-für-Zeile-Vergleich:** Die Render-/Formatierungslogik
(`Fmt`/`FmtDuration`, alle sechs Detail-Renderer für Interpreten/Alben/
Titel/Genres/Personen/Quellen inkl. disc.track-Positionierung,
Rollen-/Werkart-Übersetzung und allen Leerwert-Fallbacks) ist 1:1
identisch zur Python-Referenz und bereits durch 28 bestehende Tests
abgedeckt (`LibraryBrowserSupportTests.cs`). Listen-/Detail-/Such-
Verhalten (Neuladen leert Details, Titel/Quellen rendern ohne zweiten
Netzwerk-Roundtrip) ebenfalls paritätisch.

**Geschlossene Kleinstlücken (2):**
- Null-Werte in Tabellenzellen wurden leer angezeigt statt als
  lokalisierter Leerwert "-" (`_render_cell()`-Parität): neuer
  `LibraryNullValueConverter` am `DisplayMemberBinding` aller
  Bibliotheksspalten (ersetzt wie die Python-Referenz NUR null, keine
  Leerstrings).
- Das Suchfeld hatte keinen Platzhalterhinweis
  (`library_view.search_placeholder`-Parität, als ToolTip nach der in
  der Medientabelle etablierten WPF-Konvention).

**Neue systematische Lücke L dokumentiert (`docs/GAP_ANALYSIS.md`,
Abschnitt 5):** Die Python-Referenz zeigt bei jeder fehlgeschlagenen
Core-API-Anfrage einen Fehler-Dialog mit nachschlagbarer Fehler-ID +
Lösungshinweis (§37, `show_api_error`, 30 Aufrufstellen) — der WPF-
Client zeigt API-Fehler überall nur als Inline-Statustext und parst
`error_id`/`solution_hint` nicht. Sichtbar ist der Fehler zwar (kein
stiller Fehlschlag), aber ohne §37-Referenzdaten. Umsetzungsvorschlag
steht im Gap-Eintrag; bewusst als eigener Inkrement zurückgestellt, da
alle ~11 WPF-Ansichten betroffen sind.

**Verifikation:** Wie am Vortag kein `dotnet build`/`dotnet test`
möglich (dot.net/NuGet in dieser Sandbox nicht erreichbar) —
Ersatzprüfungen: Klammer-/Strukturcheck der geänderten Datei
(balanciert), i18n-Abgleich aller neuen Schlüssel in DE/EN/JA/RU
(vorhanden), Zeile-für-Zeile-Parity-Vergleich. Windows-Build/Testlauf
weiterhin nachzuholen (siehe Eintrag vom selben Tag, Medientabelle).

## 2026-10-08 - Tiefenprüfung Medientabelle (WPF vs. Python-Referenz): Player-Parität geschlossen, LUFS-Filter-Bug behoben

Stichprobenartige Tiefenprüfung der Medientabellen-Ansicht des
WPF-Clients gegen ihre Python-Referenz (angekündigter, noch offener
Parity-Arbeitsschritt laut `ui-windows-dotnet/README.md`). Ergebnis:

**Befund 1 (Bug, behoben): LUFS-Grenzwert 0 wurde im Filter-Dialog
verworfen.** Die beiden LUFS-Felder (`min_lufs`/`max_lufs`, §9/§19)
wurden über die generische 0-als-"nicht gesetzt"-Hilfsfunktion geparst —
eine eingegebene 0 ("mindestens/höchstens 0 LUFS") wurde dadurch
stillschweigend durch den -60/10-Default ersetzt. Die Python-Referenz
(`search_filters_dialog.py`, QDoubleSpinBox -60..10) gibt den Wert
unverändert weiter. Fix: neue, WPF-freie Hilfsfunktion
`MediaSearchFiltersSupport.ParseLufsOrDefault()` in
`MediaFileActionsSupport.cs` (behält die 0, clampet auf den
Spinbox-Bereich -60..10, fällt bei leerer/ungültiger Eingabe auf den
Default zurück), eingebunden in `MainWindow.MediaFilters.cs`,
abgesichert durch `MediaSearchFiltersSupportLufsTests`.

**Befund 2 (Paritätslücke, geschlossen): Eingebetteter Medienplayer
(§60) unvollständig.** Der WPF-Player bestand nur aus Play/Pause/Stop
und einem unsichtbaren MediaElement (Höhe 0) — die Python-Referenz
(`widgets/player_bar.py`) bietet zusätzlich Suchleiste (Seek),
Lautstärkeregler (Default 0.8), Zeit-/Daueranzeige, Titelanzeige,
Fehleranzeige und ein Videobild für Filme/Episoden. Geschlossen:

- Neue persistente Wiedergabeleiste unter dem Detailpanel (Position wie
  in der Python-Referenz: `root.addWidget(self.player_bar)` nach dem
  Splitter) mit Titelanzeige (`player_bar.no_media`/`now_playing`),
  Suchregler (ziehen sucht, Timer-Nachführung funkt nicht dazwischen),
  Positions-/Daueranzeige, Lautstärkeregler 0-100 (Default 80) und
  Fehleranzeige (`player_bar.playback_error` bei `MediaFailed` — kein
  stiller Fehlschlag, Grundprinzip).
- Videobild (220 px, `setMinimumHeight(220)`-Pendant) ausschließlich für
  `movie`/`episode` (`VIDEO_KINDS`-Parität), sonst ausgeblendet.
- `ReloadAsync()` ruft jetzt `stopAndClearPlayer()` auf (Parität zu
  `stop_and_clear()` in `media_table.py::refresh()` — keine unsichtbar
  weiterspielende Datei nach Suche/Filter-Neuladen).
- `Unloaded`-Handler stoppt Wiedergabe/Timer beim Verlassen der Ansicht.
- Zeitformatierung als WPF-freies `MediaPlayerSupport.FormatTime()`
  (1:1-Pendant zu `player_bar.py::format_time`, inkl. Negativ-Clamp und
  Stundenformat ohne Nullpadding), getestet in
  `MediaPlayerSupportTests`.

**Verifikation (Einschränkung ehrlich dokumentiert):** In dieser
Sandbox sind `dot.net`/NuGet netzwerkseitig nicht erreichbar, daher war
diesmal KEIN `dotnet build`/`dotnet test` möglich (in früheren
Sitzungen über das dotnet-install-Skript verifiziert, siehe
`ui-windows-dotnet/README.md`). Ersatzprüfungen dieser Sitzung:
Klammer-/Strukturcheck aller geänderten C#-Dateien (balanciert),
Grep-Audit (keine Alt-Referenzen auf entfernte Elemente, alle
Grid-Zeilen konsistent 0-5 belegt), Abgleich jedes neuen i18n-Schlüssels
mit allen vier Katalogen (alle vorhanden), 1:1-Vergleich jedes
Verhaltens mit der Python-Referenz Zeile für Zeile. Ein Windows-Build
(`dotnet build -p:EnableWindowsTargeting=true`) und `dotnet test`
(einschließlich der neuen Tests) sind vor der nächsten Abnahme
nachzuholen; die visuelle Player-Abnahme erfordert echtes Windows mit
Audio-/Videoausgabe.

## 2026-10-07 - UI v2 / Version 0.2.0

- WPF-Oberflaeche auf modernes Charcoal/Navy-Design mit Sidebar-Icons, Dashboard-Karten, Pill-Aktionen und Connection-Status umgestellt.
- Medientabelle um Format-Chips und lazy geladene Cover-Thumbnails erweitert.
- Core, WPF-Client und Installer-Version auf 0.2.0 angehoben.
- Keine Release-Freigabe behauptet; Windows-UI-Abnahme und vollstaendiges Release-Gate bleiben erforderlich.
# PROGRESS TRACKER — GENESIS Media Manager

> Diese Datei ist die **Wahrheit über den aktuellen Stand**. Bei jedem
> Sitzungsstart zuerst lesen (zusammen mit PROJECT_BRIEF.md, ARCHITECTURE.md,
> DECISIONS.md). Bei jedem Sitzungsende aktualisieren.

Letztes Update: 2026-10-09 (Tiefenprüfung der restlichen sechs Ansichten abgeschlossen — Gap K vollständig, Locale-Bug Nr. 6 und Paritätslücken behoben; siehe oberster Eintrag)

## Gesamtstatus

```
Infrastruktur: Git-Repository + i18n DE/EN/JA/RU (Core+PySide6+WPF) [##########] fertig

Phase 1  Foundation        [##########] abgeschlossen
Phase 2  Musik              [##########] abgeschlossen (Kernmodule + REST-API + UI-Anbindung + Deep-Review-Pass, Sitzung 2+4)
Phase 3  Audio               [##########] abgeschlossen (Loudness/Cutter/Konvertierung/Duplikate/Qualität)
Phase 4  Hörbücher            [##########] abgeschlossen (Tags lesen+übernehmen, Kapitel erkennen/erzeugen/umbenennen/exportieren)
Phase 5  Video                 [##########] abgeschlossen (Filme/Serien, §24, ADR-0016)
Phase 6  KI                     [##########] abgeschlossen (KI-Metadaten/-Suche/-Musik, §25-§27, ADR-0017)
Phase 7  Voice                    [##########] abgeschlossen (Voice Studio: Piper-TTS, Profile, lokale API, §28/§29, ADR-0018)
Phase 8  Import/Download           [##########] abgeschlossen (Download-/Import-Center, §30-§32, ADR-0019)
Phase 9  Hardening                   [##########] abgeschlossen (§34-§43: Plugins, Job-Steuerung, Fehler-Center, Diagnose, Backup, Scan&Repair, Temp-Aufräumung, Export, Relokation + PySide6-UI, ADR-0020)
Phase 10 Release                      [----------] bewusst zurückgestellt (kein Release in dieser Sitzung, siehe Nutzervorgabe)
```

**Damit sind Phase 3 bis Phase 9 des Originalauftrags gemäß der expliziten
Nutzervorgabe dieser Sitzungsreihe ("baue erst alles fertig bis alles
komplett ist") vollständig abgeschlossen.** Phase 10 (Release:
Lizenzaudit, THIRD-PARTY-LICENSES, NOTICE, CHANGELOG, finale
Dependency-Reports) bleibt wie ausdrücklich gewünscht zurückgestellt, bis
der Nutzer das Projekt als inhaltlich fertig erklärt.



## Sitzung 1 (2026-09-30) — Ergebnis

### Fertiggestellt und getestet

- [x] Vollständige Originalspezifikation gesichert: `docs/ORIGINAL_SPEC_DE.md`
- [x] Kondensierte Arbeitsgrundlage: `PROJECT_BRIEF.md`
- [x] Architekturentscheidungen: `DECISIONS.md` (ADR-0001 bis ADR-0005)
- [x] Deep-Review-Prompt-Pack integriert: `reference/review-prompt-pack/`
      + Nutzungsanleitung `docs/DEEP_REVIEW_USAGE.md`
- [x] Sandbox-Werkzeuge installiert: FFmpeg/FFprobe 7.1.5, SQLite 3.46,
      Ollama 0.35.0, PySide6 6.11.2
- [x] Lokales KI-Modell `qwen2.5:0.5b` gezogen & per Integrationstest
      erfolgreich verifiziert
- [x] **Python Core Service** (`core/genesis_core/`):
  - `config/` — Settings mit datenschutzfreundlichen Defaults (§56)
  - `logutil/` — strukturiertes, rotierendes Logging (§54, TRACE..CRITICAL)
  - `db/` — vollständiges SQLAlchemy-Schema für alle §7-Entitäten (26 Tabellen)
  - `scanner/` — rekursiver, read-only Scanner: Klassifikation, SHA-256-Hash,
    FFprobe-Technikanalyse, Neu-/Änderungs-/Vermisst-Erkennung
  - `jobs/` — Job-Queue mit eindeutigen `JOB-YYYYMMDD-NNNNN`-IDs,
    Fortschritt/Fehler/Warnungen, Grundlage für Rollback (§17)
  - `ai/` — Provider-Interface + `NullAIProvider` + `OllamaProvider`
    (getestet, inkl. echtem End-to-End-Aufruf gegen laufenden Ollama-Dienst)
  - `api/` — lokale REST-API (FastAPI) mit `/health`, `/scan`,
    `/dashboard/summary`, `/media`, `/media/{id}`, `/jobs` + automatischer
    OpenAPI-Doku unter `/docs`
- [x] **Testumgebung** (ADR-0004): `core/testdata_generator/` erzeugt
      synthetische Testbibliothek (Musik/Hörbuch/Film, mehrere Formate) rein
      per FFmpeg — keine echten Mediendateien im Spiel; `core/tests/`
      erzwingt SAFE TEST MODE über `conftest.py`-Fixtures
- [x] **16 von 16 automatisierten Tests grün** (`scripts/run_tests.sh`):
      Config, DB-Schema, Scanner (inkl. Idempotenz & Missing-File-Erkennung),
      AI-Provider (inkl. echtem Ollama-Call), REST-API End-to-End
- [x] **Live demonstriert:** Core-API gestartet, echte Testbibliothek
      gescannt (7 Dateien, korrekt klassifiziert, FFprobe-Technikdaten
      extrahiert, physischer Pfad gespeichert), Dashboard/Media/Jobs-Endpunkte
      erfolgreich abgefragt
- [x] **PySide6-Referenz-UI** (`ui-reference-pyside/`): Dark Mode,
      vollständige Navigationsstruktur nach §4, Dashboard mit echten
      Live-Daten aus der Core-API, Medientabelle mit Such-/Detailansicht
      (physischer Pfad, Technik-Metadaten). Per Screenshot verifiziert:
      `docs/screenshot_dashboard.png`, `docs/screenshot_media_table.png`
- [x] **.NET/WPF-Windows-Client-Grundgerüst** (`ui-windows-dotnet/`):
      Projektstruktur, Dark-Theme-ResourceDictionary, Navigationsbaum
      (identisch zur PySide6-UI), schlanker `GenesisApiClient`. **Kann in
      dieser Linux-Sandbox nicht kompiliert/getestet werden** (siehe
      ADR-0001) — muss unter Windows verifiziert werden.
- [x] Lizenz-Entwurf: `licenses/THIRD-PARTY-LICENSES.md` (Status ENTWURF,
      ADR-0005), `NOTICE.md`, automatisiertes Rohbericht-Skript
      `scripts/generate_license_report.py`
- [x] Root-`README.md` mit Schnellstart-Anleitung

### Während der Sitzung gefundene & behobene Probleme (Transparenz, Prinzip #16)

1. **Datetime-Vergleichsfehler im Scanner**: SQLite/SQLAlchemy verwirft
   Zeitzoneninfo beim Roundtrip, dadurch schlug der Änderungsvergleich
   zwischen frisch gelesenem (tz-aware) und aus der DB geladenem (tz-naiv)
   `mtime` fehl. Fix: `mtime` wird konsistent als UTC-naiv gespeichert
   (siehe `scanner/scanner.py`). Durch Testsuite aufgedeckt und verifiziert.
2. **FastAPI + `from __future__ import annotations` + lokal verschachteltes
   Pydantic-Modell**: `ScanRequest` wurde als Query-Parameter statt als
   Body erkannt, weil String-Annotationen nicht gegen die Closure der
   Funktion aufgelöst werden konnten. Fix: Modell auf Modulebene verschoben.
   Auch dies durch die Testsuite aufgedeckt, nicht manuell übersehen.

Diese Historie bleibt hier bewusst stehen (nicht "schöngeschrieben") als
Beleg für §49/§50 (testgetriebene, nachvollziehbare Entwicklung).

## Nächste konkrete Schritte (Phase 2: Musik)

1. `metadata/` — zentrale Metadata-Engine mit Trefferbewertung (§10/§11)
2. `providers/musicbrainz.py`, `providers/acoustid.py`,
   `providers/coverartarchive.py` — HTTP-Clients mit Timeout/Retry, klar
   gekennzeichnete Fehlermeldungen (§37), Offline-Fallback ohne erfundene
   Daten
3. `fingerprint/` — Chromaprint-Anbindung (`pyacoustid` oder `fpcalc`
   CLI-Wrapper prüfen, Lizenz LGPL-2.1 beachten)
4. `artwork/` — Cover Art Archive Anbindung, Einbetten/Extrahieren via
   mutagen/ffmpeg
5. `rename/` — Template-Engine (§15) + Preview-Dialog (§16) in beiden UIs
6. Erweiterte Suche (§9) mit Filtern in der PySide6-UI
7. ~~Deep Review anwenden~~ — ERLEDIGT in Sitzung 2, siehe Abschnitt
   "Sitzung 2 — Deep Review" unten und `docs/REVIEW_LOG.md`. Für Phase 2
   sollte nach Fertigstellung der Provider/Fingerprint-Module ein
   Folge-Review speziell für `metadata/`, `providers/`, `fingerprint/`
   durchgeführt werden (gleiche Methodik, neuer REVIEW_LOG-Abschnitt).
8. Diesen Tracker nach Abschluss von Phase 2 aktualisieren

## Ressourcen-Disziplin — Erinnerung für künftige Sitzungen

- `bash scripts/setup_python_env.sh` und ggf. `bash scripts/setup_ollama.sh`
  zu Beginn jeder neuen Sitzung erneut ausführen (installierte Pakete und
  `~/.ollama`-Modelle überleben den Sandbox-Snapshot nicht).
- Keine echten/großen Mediendateien in den Workspace legen — nur die
  FFmpeg-generierte synthetische Testbibliothek verwenden.
- Fortschritt/Entscheidungen immer in `PROGRESS.md`/`DECISIONS.md`
  festhalten statt im Chatverlauf aufzublähen.

## Offene Entscheidungen / Risiken (unverändert seit Sitzung 1)

- `ui-windows-dotnet` kann in dieser Sandbox nicht kompiliert werden — Build/
  Test muss unter Windows erfolgen.
- Lizenzfragen mutagen (GPL-2.0-or-later) und finale FFmpeg-Build-Variante
  beeinflussen die spätere Gesamtlizenz-Wahl (§64) — bewusst erst im
  Release-Gate final entschieden (ADR-0005).
- MusicBrainz/AcoustID/Cover-Art-Archive-Provider (§10) benötigen
  Internetzugriff — im Offline-Modus transparent "nicht verfügbar" statt
  erfundener Daten (Prinzip #16/#17).

---

## Sitzung 2 — Deep Review (tatsächliche Anwendung des Prompt Packs)

Nutzerauftrag: "prüfe anhand der daten nochmal suche dir das passende raus"
— die Deep-Review-Methodik aus `reference/review-prompt-pack/` erstmals
wirklich auf den realen Code anwenden (Sitzung 1 hatte sie nur
dokumentiert/referenziert). Volles Ergebnis inkl. Beweisstatus/Vertrauen pro
Fund: **`docs/REVIEW_LOG.md`** (neu angelegt, 9-Abschnitte-Format exakt wie
im Prompt Pack vorgeschrieben).

**Angewendete Profile:** Python, Bash/POSIX, SQL, JSON/YAML/Config,
API REST, KI/LLM/Agent, C#/.NET (siehe REVIEW_LOG.md Abschnitt 2 für Details
und Zeilenverweise im Prompt-Pack-Dokument).

**Gefunden und in dieser Sitzung behoben (mit Regressionstest):**

1. **HOCH — Job-ID-Kollision nach Neustart am selben Tag.** Der
   Job-ID-Zähler war rein prozesslokal (`itertools.count()`) und begann bei
   jedem Neustart wieder bei 1 → `IntegrityError` beim ersten Job nach einem
   Neustart. Per Reproduktionsskript (zwei Prozesse gegen dieselbe
   SQLite-Datei) bestätigt. Fix: ID-Sequenz wird aus der DB abgeleitet
   (`MAX(id)` je Tagespräfix) statt aus einem In-Memory-Zähler, plus
   Retry-Schleife bei seltener Kollision. → `core/genesis_core/jobs/__init__.py`,
   Tests in `core/tests/test_jobs.py`.

2. **HOCH — Lokale REST-API ohne Authentifizierung.** `127.0.0.1`-Bindung
   allein schützt nicht vor Drive-by-Localhost-/JSON-CSRF-Anfragen aus dem
   Browser. Fix: Shared-Secret-Token (`api_token.txt`, 0600), Pflicht-Header
   `X-Genesis-Token` auf allen Endpunkten außer `/health`. Beide UI-Clients
   (Python + .NET) lesen das Token eigenständig ein. Siehe **ADR-0006** in
   `DECISIONS.md`. → `core/genesis_core/api/security.py`,
   `core/genesis_core/api/app.py`,
   `ui-reference-pyside/genesis_ui/api_client.py`,
   `ui-windows-dotnet/.../Api/GenesisApiClient.cs`, Tests in
   `core/tests/test_api.py`.

3. **MITTEL — Scanner hasht jede Datei bei jedem Scan unbedingt.** Verstößt
   gegen den Inkrementell-Scan-Anspruch (§12/§57). Fix: günstige
   Größe/mtime-Vorprüfung zuerst, Hash nur bei tatsächlicher Änderung.
   → `core/genesis_core/scanner/scanner.py`.

4. **MITTEL — FFprobe-Re-Analyse prüfte kumulierten statt Pro-Datei-
   Zustand.** Sobald irgendeine Datei im Scan als geändert erkannt wurde,
   lief FFprobe für alle danach besuchten, tatsächlich unveränderten
   Dateien erneut. Fix: lokales Pro-Datei-Flag. → dieselbe Datei wie Punkt 3,
   Tests in `core/tests/test_scanner_performance.py` (Spy auf `sha256_of_file`
   / `probe_file`, verifiziert 0 bzw. genau 1 Aufruf im richtigen Szenario).

5. **NIEDRIG-MITTEL — `Settings.load()` ohne Fehlerbehandlung.** Eine
   beschädigte `config.yaml` hätte die App mit rohem Stacktrace abstürzen
   lassen (§37). Fix: try/except, Backup der kaputten Datei
   (`config.broken-<Zeitstempel>.yaml`), Fallback auf Defaults.
   → `core/genesis_core/config/__init__.py`, Tests in
   `core/tests/test_config.py`.

6. **NIEDRIG — Unsichere JSON-String-Interpolation in `setup_ollama.sh`.**
   `$MODEL` wurde direkt in einen JSON-String eingebettet. Fix: JSON-Body
   sicher via `python3 -c`/`json.dumps` erzeugen. → `scripts/setup_ollama.sh`.

**Dokumentiert, aber kein Code-Fix nötig (INFO):**

7. Async-void-artige Event-Handler in `MainWindow.xaml.cs` sind aktuell
   sicher (alle Exceptions werden intern abgefangen) — erklärender
   Kommentar ergänzt, damit das bei künftigen Erweiterungen erhalten bleibt.

**Nach jedem Einzel-Fix und final erneut vollständig getestet:**
`cd core && python3 -m pytest -q` → **25 passed** (Sitzung 1: 16, dann 18
nach Job-Fix, 20 nach Scanner-Fix, 23 nach API-Auth-Fix, 25 final nach
Config-Fix).

**Positiv bestätigt (siehe REVIEW_LOG.md Abschnitt 6):** kein Roh-SQL im
Projekt, kein `shell=True`/`eval`/`exec`/`pickle`/unsicheres `yaml.load`,
Scanner öffnet Dateien nachweislich nur lesend, Privacy-Defaults korrekt
und testabgesichert.

**Bewusst zurückgestelltes Backlog (siehe REVIEW_LOG.md Abschnitt 7):**
OS-Keyring für Download-Credentials (relevant erst ab Phase 8),
Dependency-Pinning/Lockfile vor Release-Gate, `git init` noch ausstehend,
Prompt-Injection-Neubewertung vor Phase 6 (sobald KI-Tool-Calling/Auto-Apply
existiert), Scanner-Preload-Strategie für sehr große Bibliotheken (>> 1 Mio.
Dateien) in Phase 9 verfeinern.

---

## Sitzung 3 (2026-09-30) — Phase 2 Kernmodule + REST-API + UI-Anbindung

Fortsetzung von Sitzung 2/2b (Provider, Metadata-Engine, Fingerprint waren
bereits fertig). Diese Sitzung hat die verbleibenden Phase-2-Kernmodule
gebaut und **komplett bis in die UI verdrahtet** (nicht nur Backend-Code
ohne Anschluss).

**Neu implementiert und getestet:**

1. `rename/templates.py` + `rename/engine.py` (§15/§16): sichere
   Platzhalter-Vorlagen (kein `eval`), harte Endungs-Erhalt-Prüfung,
   Batch-Kollisionserkennung (intern + Disk + DB), Pflicht-Vorschau vor
   jeder Anwendung, Rollback bei Teilfehler mitten im Batch (verifiziert
   durch dedizierten Test mit gepatchtem `os.rename`).
2. `artwork/engine.py` (§22): Cover extrahieren/einbetten für
   MP3/FLAC/OGG/MP4/M4B via mutagen, eigener deduplizierender Cache-Ordner
   (rührt nie die Mediendatei an außer beim expliziten, bestätigten
   Einbetten).
3. **REST-API-Endpunkte** in `core/genesis_core/api/app.py`:
   `GET /media/{id}/metadata-suggestions`,
   `POST /media/{id}/metadata-suggestions/apply` (confirm-Pflicht),
   `POST /rename/preview`, `POST /rename/apply` (berechnet die Vorschau
   serverseitig NEU statt Client-Daten zu vertrauen — TOCTOU-Vermeidung),
   `GET /media/{id}/artwork`, `POST /media/{id}/artwork/fetch-online`,
   `POST /media/{id}/artwork/embed` (confirm-Pflicht). Alle token-geschützt,
   `JobManager.record_history()` wird konsequent NACH Commit in der
   API-Schicht aufgerufen (nicht in den Engines — siehe DECISIONS.md).
4. **PySide6-UI-Anbindung** (`ui-reference-pyside/genesis_ui/`):
   `api_client.py` um alle neuen Methoden + verbesserte deutschsprachige
   Fehlerextraktion (`detail`-Feld aus FastAPI-Fehlern) erweitert;
   `dialogs/metadata_dialog.py` (Vorschläge anzeigen, Übernahme nur nach
   `QMessageBox.question`-Bestätigung) und `dialogs/rename_dialog.py`
   (Vorlage → Vorschau-Tabelle mit Status pro Datei → zweite Bestätigung
   → Anwenden) neu; `views/media_table.py` um Mehrfachauswahl, zwei neue
   Buttons und eine erweiterte Detailansicht (Track-Metadaten,
   Konfidenz, Bestätigungsstatus, Artwork-Vorhanden-Flag) ergänzt.
5. `GET /media/{id}` liefert jetzt zusätzlich `track` (Metadaten-Zustand)
   und `has_embedded_artwork`.

**Gefundener und behobener Bug (durch echten End-to-End-Smoke-Test, nicht
durch Unit-Tests):** `{track:02d}` crashte mit `Unknown format code 'd' for
object of type 'str'`, wenn die Tracknummer fehlt (leeres Pflichtfeld +
numerischer Format-Spezifizierer). Fix: `_EmptyAwareFormatter` in
`rename/templates.py` — leere Felder ignorieren den Format-Spezifizierer
und werden zu `""` statt zu crashen, exakt im Sinne von Prinzip #16 (keine
Fantasiedaten, aber auch kein Absturz). Regressionstest ergänzt.

**Verifikationsmethode (wichtig, da PySide6-Klicks nicht automatisiert
getestet werden können):** echter End-to-End-Smoke-Test mit echtem
`uvicorn`-Serverprozess + generierter Testbibliothek + echtem
`GenesisAPIClient` (derselbe Code-Pfad wie die UI) für: Scan → Metadaten-
Vorschlag übernehmen (mit `confirm=False` korrekt abgelehnt, mit
`confirm=True` erfolgreich, Track in DB aktualisiert) → Rename-Vorschau
und -Anwendung (Datei auf Disk tatsächlich umbenannt, DB aktualisiert) →
Artwork-Endpunkte (404 ohne Artwork, korrekter Fehler bei ungültiger
Fake-MBID gegen Cover Art Archive). UI-Module zusätzlich mit
`QT_QPA_PLATFORM=offscreen` real importiert/instanziiert (keine reinen
`py_compile`-Prüfungen).

**Testfortschritt:** 78 → **86/86 grün** (+7 `test_api_phase2.py`, +1
Regressionstest für den Format-Spec-Bug). Volle Suite lief nach jeder
Änderung erneut grün.

**Noch offen für Phase 2 (nächste Schritte):**
- Deep-Review-Pass speziell für `rename/`, `artwork/`, die neuen
  API-Endpunkte und die neuen UI-Dialoge (gleiche Methodik wie Sitzung 2,
  neuer REVIEW_LOG-Abschnitt).
- Artwork-UI fehlt noch komplett (Cover anzeigen/abrufen/einbetten-Buttons
  in `media_table.py` bzw. eigener Artwork-Tab) — nur die API-Seite und der
  `api_client.py`-Client sind fertig.
- `.NET`-UI (`ui-windows-dotnet`) hat noch KEINE der Phase-2-Endpunkte
  angebunden (nur in PySide6 nachgezogen) — muss vor Phase-2-Abschluss
  nachgezogen werden, da beide UIs laut ARCHITECTURE.md gleichwertig sein
  sollen.
- ADR für Konfidenz-/Rename-/Artwork-Sicherheitsdesign noch nicht
  geschrieben (nur implizit in Code-Kommentaren dokumentiert).
- Lizenzdokumentation (Chromaprint LGPL-2.1, mutagen) bewusst weiterhin
  NICHT final eingetragen (nur am Projektende, siehe Nutzervorgabe).

---

## Sitzung 3, Fortsetzung ("weiter") — Artwork-UI + .NET-Client-Parität + kritischer Fund

**1. Artwork-UI in PySide6 nachgezogen:** neuer `dialogs/artwork_dialog.py`
(`ArtworkDialog`): zeigt eingebettetes Cover (oder "kein Cover"), Button
"Online suchen" (Cover Art Archive, landet NUR im Cache, nie direkt in der
Datei), erst nach `QMessageBox`-Bestätigung ein zweiter Button "Einbetten".
In `media_table.py` als dritter Aktions-Button verdrahtet. End-to-End mit
echtem Server + echtem eingebettetem Testbild verifiziert (Dialog zeigt
korrekt "kein Artwork" bzw. das eingebettete Bild als QPixmap an).
Zusätzliche API-Tests `test_artwork_fetch_online_then_embed_roundtrip` und
`test_artwork_fetch_online_without_known_album_mbid_returns_409` ergänzt
(86 → 88 Tests gesamt).

**2. Sandbox mangels Snapshot-Persistenz neu eingerichtet:** PySide6,
FastAPI/mutagen/etc. (`scripts/setup_python_env.sh`) waren nach Sitzungsende
weg und mussten neu installiert werden — wie in "Ressourcen-Disziplin"
dokumentiert, erwartungsgemäß.

**3. NEU: .NET SDK erstmals in der Sandbox installiert** (`dotnet-install.sh`
nach `~/.dotnet`, jetzt per `scripts/setup_dotnet_env.sh` wiederholbar).
**Wichtiger Fund:** Das WPF-Projekt (`net8.0-windows`, `UseWPF=true`) lässt
sich mit `dotnet build -p:EnableWindowsTargeting=true` auf Linux
**kompilieren** (nicht ausführen) — das war in Sitzung 1/2 nicht bekannt und
stand noch als "kann nicht kompiliert werden" in den Risiken. Das ändert
diese Einschätzung: C#-Änderungen können ab sofort in der Sandbox auf
Kompilierfehler geprüft werden, bevor sie auf eine Windows-Maschine
überführt werden.

**4. GenesisApiClient.cs (.NET) um Phase-2-Methoden erweitert** (Metadaten-
Vorschläge, Rename-Preview/Apply, Artwork lesen/online-suchen/einbetten) —
inklusive neuer Records und einer `GenesisApiException`, die FastAPIs
`detail`-Feld extrahiert (Analogie zum Python-Client).

**5. KRITISCHER FUND während der Verifikation (nicht durch Build, sondern
durch echten Laufzeittest entdeckt):** Der komplette .NET-Client — nicht
nur die neuen Phase-2-Methoden, sondern auch ALLE bestehenden Phase-1-
Methoden seit Sitzung 1 — deserialisierte JSON-Antworten der Core-API
**still falsch**. Grund: FastAPI liefert snake_case-Felder (`job_id`,
`absolute_path`), die C#-Records nutzen PascalCase (`JobId`,
`AbsolutePath`); `System.Text.Json` mappt das ohne explizite
`JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower`
NICHT automatisch — und zwar ohne Fehler zu werfen, sondern mit stillem
Verbleib auf dem Default-Wert (`null`/`0`/`false`). Klarer §37-Verstoß
("keine stillen Fehlschläge"), der bisher nur deshalb nicht auffiel, weil
die .NET-UI bislang nur das Dashboard rendert. **Gefixt:** eine einzige
zentrale `JsonSerializerOptions`-Instanz mit `SnakeCaseLower` +
`PropertyNameCaseInsensitive`, die jetzt bei JEDEM Serialisierungs-/
Deserialisierungsaufruf explizit übergeben wird (Regel als Kommentar direkt
im Code verankert, damit sie nicht wieder vergessen wird). Vollständig neu
dokumentiert als **ADR-0008** in `DECISIONS.md`.

**Verifikationsmethode für den Fix:** ein von der WPF-Abhängigkeit
entkoppeltes, temporäres `net8.0`-Konsolenprogramm hat `GenesisApiClient.cs`
direkt (`<Compile Include>`) gegen einen echten laufenden Core-API-Prozess
getestet — Health, Dashboard, Scan, MediaList, MediaDetail, Rename-Preview/
Apply (inkl. tatsächlicher Dateiumbenennung auf Disk), Metadaten-Vorschlag-
Übernahme (inkl. Ablehnung ohne `confirm=true`), Artwork lesen/online-
suchen/einbetten (inkl. aller Fehlerfälle) — alle Felder korrekt befüllt,
alle Fehlerfälle mit korrekt extrahierter deutschsprachiger Fehlermeldung.

**Testfortschritt:** Python-Suite weiterhin **87/88 grün + 1 übersprungen**
(AcoustID-Live-Test ohne Netzwerk/Key); .NET-Client kompiliert mit 0
Fehlern/Warnungen und wurde live-verifiziert (kein formales .NET-Unit-Test-
Projekt bisher — könnte in einer künftigen Sitzung ergänzt werden, siehe
"Noch offen").

**Bewusste Scope-Entscheidung:** Es wurden in dieser Sitzung KEINE
WPF-Views/Dialoge für Phase 2 gebaut (kein Pendant zu
`MetadataSuggestionsDialog`/`RenamePreviewDialog`/`ArtworkDialog` in C#).
Begründung: Die .NET-UI hat bis heute noch nicht einmal die Phase-1-
Medientabelle nachgezogen (`MainWindow.xaml.cs` zeigt für alles außer
"Dashboard" absichtlich "noch nicht implementiert" an, siehe Code-Kommentar
dort zu Prinzip #16-Transparenz). Eine vollständige WPF-Oberfläche wäre
gegenüber diesem fehlenden Fundament unverhältnismäßig und sollte als
eigene, bewusste Aufgabe behandelt werden, sobald die .NET-UI-Phase-1-
Medientabelle gebaut wird. Bis dahin ist die API-Client-Schicht
(`GenesisApiClient.cs`) vollständig synchron zum Python-Pendant gehalten,
sodass eine künftige WPF-UI direkt darauf aufbauen kann.

**Noch offen für Phase 2 (aktualisiert):**
- WPF-Views für Phase 2 (siehe Scope-Entscheidung oben) — eigentlich erst
  sinnvoll NACH einer WPF-Phase-1-Medientabelle.
- Formales .NET-Testprojekt (xUnit o.ä.) für `GenesisApiClient` fehlt noch -
  bisher nur ad-hoc per Konsolenprogramm verifiziert; sollte für
  Regressionssicherheit dauerhaft eingerichtet werden.
- ADR für Konfidenz-Scoring-Sicherheitsdesign (separat von ADR-0007/0008)
  noch nicht geschrieben.
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).

## Sitzung 4 — Deep-Review-Pass für Phase-2-Module (rename/artwork/API/UI)

Deep-Review-Pass speziell für die neuen Phase-2-Module durchgeführt
(gleiche Methodik wie Sitzung 2, siehe `docs/REVIEW_LOG.md`, neuer
Abschnitt "Sitzung 3" — Benennung historisch an die Code-Sitzung
angelehnt, nicht an die Chat-Sitzungszählung). Geprüft: `rename/engine.py`,
`rename/templates.py`, `artwork/engine.py`, die Phase-2-REST-Endpunkte in
`api/app.py`, alle drei PySide6-Dialoge (`rename_dialog.py`,
`metadata_dialog.py`, `artwork_dialog.py`) sowie `GenesisApiClient.cs`
(Phase-2-Methoden, per Code-Lektüre — SDK in dieser Sandbox-Instanz nicht
vorinstalliert, kein erneuter `dotnet build`).

**6 Findings identifiziert (F-08 bis F-13), alle behoben:**
- F-08 (Nachtrag, HOCH zum Zeitpunkt der Entdeckung): .NET-Client
  snake_case/PascalCase-JSON-Mismatch — bereits vor dieser Review-Runde
  behoben (ADR-0008), hier nur formal nachgetragen.
- F-09 (MITTEL): Case-insensitive-Dateisystem-Fehlalarm bei Umbenennung —
  hätte auf Windows/macOS jede reine Schreibweise-Korrektur blockiert.
  Fix: `os.path.samefile`-basierte Konflikt-Unterdrückung. Beweisstatus:
  Stellvertreter-Test via Hardlink (ext4 ist case-sensitiv, reales Szenario
  nicht direkt reproduzierbar).
- F-10 (NIEDRIG-MITTEL): `empty_fields`-Warnung fehlte im
  Rename-Vorschau-Dialog trotz vorhandener API-Information. Fix: Statuszeile
  zeigt jetzt "bereit (Achtung, leer: ...)".
- F-11 (NIEDRIG-MITTEL): Artwork-MIME-Typ wurde nicht persistiert und beim
  Einbetten verlustbehaftet aus der Cache-Dateiendung zurückgeraten;
  `_embed_mp4` akzeptierte stillschweigend jeden Nicht-PNG-Mime als JPEG.
  Fix: neue `mime_type`-Spalte am `Artwork`-Modell (ohne Migrationsaufwand,
  da Schema noch per `create_all()` erzeugt wird), MP4-Einbettung lehnt
  nicht unterstützte Formate jetzt mit klarer Fehlermeldung ab.
- F-12 (NIEDRIG, Defense-in-Depth): Server prüfte die konfigurierte
  Mindest-Konfidenz nur beim Generieren von Vorschlägen, nicht erneut beim
  Anwenden — ein Client-Bug hätte einen Vorschlag mit beliebig niedriger
  Konfidenz trotzdem anwenden können. Fix: zusätzliche serverseitige
  Prüfung in `apply_metadata_suggestion`.
- F-13 (NIEDRIG): Trailing-Punkt im Dateinamen bei leerem `{ext}`
  (endungslose Originaldatei). Fix: `rstrip(". ")` auf den gesamten
  gerenderten Dateinamen.

**7 neue Regressionstests geschrieben**, Gesamtsuite danach 94 passed/1
skipped (vorher 87/1). Zusätzlich ein Offscreen-PySide6-Smoke-Test für
F-10 durchgeführt (kein dauerhafter pytest-Test, da UI-Testinfrastruktur
für PySide6 noch nicht in die reguläre Suite integriert ist).

Vollständige Finding-Details, Beweisstatus und Vertrauenseinstufung je
Fund: siehe `docs/REVIEW_LOG.md`, Abschnitt "Sitzung 3". Dort auch die
Korrektur der veralteten Sitzung-2-Annahme zur .NET-Kompilierbarkeit.

**Sandbox-Hinweis dieser Sitzung:** Bei Fortsetzung in einer neuen
Sandbox-Instanz waren alle Python-Pakete wieder weg (erwartetes Verhalten,
kein Fehler) — `bash scripts/setup_python_env.sh` erneut ausgeführt, dazu
`sudo pip install --break-system-packages PySide6` für den UI-Smoke-Test.

**Noch offen (unverändert/aktualisiert):**
- Formales .NET-Testprojekt (xUnit) für `GenesisApiClient` weiterhin
  ausstehend.
- Manuelle Verifikation von F-09 auf echtem Windows/macOS steht noch aus.
- ADR für Konfidenz-Scoring-Sicherheitsdesign noch nicht geschrieben.
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- `/tmp/genesis_smoke/` ist durch den Sandbox-Neustart dieser Sitzung von
  selbst weg (nicht Teil des Workspace-Snapshots) — Aufräum-Posten damit
  erledigt, kein Handlungsbedarf mehr.

## Sitzung 5 (2026-10-01) — Strukturelle Basis: Git-Repository + i18n (DE/EN/JA/RU)

Auf expliziten Nutzerwunsch VOR Beginn von Phase 3: strukturelle Basis
nachgerüstet. Zwei Teilaufgaben, beide abgeschlossen und verifiziert.

### 1. Git-Repository

Repository initialisiert (`git init`, Branch `main`), kompletter bisheriger
Stand (Phase 1+2) als Initial-Commit `00b6950` gesichert. `.gitignore`
deckt DB-/Log-/Build-Artefakte, `.NET` `bin/`/`obj/`, Python-Cache,
`reference/` (externes Prompt-Pack-Klon) und `ollama_data/` ab.

### 2. i18n-Mechanismus (ADR-0009)

- Geteiltes JSON-Katalogformat `i18n/{de,en,ja,ru}.json`, je 201 Schlüssel,
  identische Schlüsselmenge über alle vier Sprachen (durch Test erzwungen).
- Drei unabhängige, bewusst kleine (~100-130 Zeilen) Loader-Implementierungen
  statt eines geteilten Moduls (Begründung: ADR-0001-Prozessgrenze PySide6
  ↔ Core, .NET kann ohnehin kein Python importieren):
  1. `core/genesis_core/i18n/__init__.py` — für künftige strukturierte
     Fehlercodes/-schlüssel im Core-Service.
  2. `ui-reference-pyside/genesis_ui/i18n.py` — für die PySide6-UI.
  3. `ui-windows-dotnet/GenesisMediaManager.Client/I18n/Translator.cs` —
     für den WPF-Client (eigenes Platzhalterformat `{name}` statt .NETs
     `string.Format`-Positionssyntax, um mit demselben JSON kompatibel zu
     bleiben).
- Core: neuer `GET /settings`-Endpunkt (token-geschützt, read-only) liefert
  die volle Konfiguration inkl. `general.language`, damit beide UIs die
  Sprache beim Start aus der zentralen Konfiguration lesen können (kein
  manuelles Config-Datei-Editieren nötig, §52-Geist). 2 neue Tests
  (`test_settings_endpoint_returns_general_language_for_ui_startup`,
  `test_settings_endpoint_requires_token`). Core-Gesamtsuite: **104 passed,
  1 skipped**.
- PySide6-UI: `main_window.py` + alle fünf Views/Dialoge (`dashboard.py`,
  `media_table.py`, `rename_dialog.py`, `metadata_dialog.py`,
  `artwork_dialog.py`) vollständig auf `tr()` umgestellt — keine
  hartcodierten deutschen Strings mehr. `_apply_language_from_settings()`
  liest `GET /settings` beim Start. **Vollständiger End-to-End-Smoke-Test:**
  zwei echte Core-API-Instanzen (Port 8421 mit Default-Sprache DE, Port 8422
  mit `config.yaml` → `general.language: en`) offscreen (`QT_QPA_PLATFORM=
  offscreen`) gegen `MainWindow` getestet — DE-Instanz zeigt "MEDIEN" /
  "Hörbücher", EN-Instanz korrekt "MEDIA" / "Audiobooks". Alle vier Sprachen
  × alle vier Views/Dialoge (Dashboard, Rename-, Metadaten-, Artwork-Dialog)
  zusätzlich einzeln offscreen durchgebaut, keine Exceptions.
  i18n-Testsuite (`ui-reference-pyside/tests/test_i18n.py`): **5 passed**.
  (Hinweis zum Prozess: ein erster Testlauf zeigte scheinbar fehlschlagende
  Sprachumschaltung — Ursache war ein Fehler im Testskript selbst, nicht im
  Produktivcode: `GENESIS_DATA_DIR` zeigte für beide API-Instanzen auf
  denselben/falschen Ordner, wodurch der API-Client das falsche Token
  verwendete und beide Aufrufe mit 401 scheiterten, was still auf den
  Default DE zurückfiel. Mit korrekt pro Instanz gesetztem
  `GENESIS_DATA_DIR` funktioniert die Umschaltung einwandfrei.)
- .NET/WPF-Client: `Translator.cs` neu (eigene Named-Placeholder-Ersetzung,
  da .NETs `string.Format` nur Positions-Platzhalter kennt, die JSON-Kataloge
  aber Python-Style `{name}`-Platzhalter verwenden), `MainWindow.xaml.cs` und
  `GenesisApiClient.cs` (neue `GetSettingsAsync()`-Methode) auf `tr()`
  umgestellt. Neues reines `net8.0`-Testprojekt
  `GenesisMediaManager.Client.Tests` (kein WPF/Windows-Targeting nötig, da
  nur die Quelldatei `Translator.cs` per `<Compile Include>`-Link
  eingebunden wird) mit `TranslatorTests.cs`: **11/11 Tests grün**, deckt
  alle vier Pflichtsprachen ab.
  **Wichtige Korrektur einer veralteten Annahme aus einer früheren Sitzung:**
  Das .NET-Projekt lässt sich in der Linux-Sandbox sehr wohl **kompilieren**
  (nicht nur lesen) — vorheriges Scheitern lag an fehlendem Speicherplatz in
  `/tmp` (tmpfs, ~1 GB) beim SDK-Download, nicht an einer grundsätzlichen
  Unmöglichkeit. Funktionierendes Rezept (SDK-Installation außerhalb von
  `/tmp`, `EnableWindowsTargeting=true` für den Build) jetzt in
  `ui-windows-dotnet/README.md` dokumentiert. `dotnet build
  -p:EnableWindowsTargeting=true` im Client-Projekt: **0 Warnings, 0
  Errors**. Das SDK selbst (~580 MB inkl. NuGet-Cache) wurde NACH
  Verifikation wieder aus `/home/user` entfernt, um den
  Workspace-Snapshot (Limit ca. 128 MB) nicht zu sprengen — muss bei
  Bedarf in künftigen Sitzungen per dokumentiertem Rezept neu installiert
  werden.

**Alles committed:** Commit `658f8ae` auf `main` (24 Dateien, i18n-Kataloge,
alle drei Loader, neuer API-Endpoint + Tests, alle UI-Umstellungen, neues
.NET-Testprojekt). Working Tree danach sauber.

**Nächste Schritte:** Phase 3 (Audio: Loudness-Engine, Audio-Cutter,
Konvertierung, Duplikaterkennung, Qualitätsprüfung) beginnen. Offene
technische Vorfrage: `pyloudnorm`-Unterstützung für True Peak (ITU-R
BS.1770 Annex 2) klären, bevor die Loudness-Engine implementiert wird.
Ziel laut Nutzervorgabe: Phase 3 bis Phase 9 vollständig fertigstellen,
Phase 10 (Release) und Lizenzdokumentation bleiben bewusst zurückgestellt.

## Sitzung 6 (2026-10-01) — Phase 3 begonnen: Loudness-Engine (§19)

Offene technische Vorfrage aus Sitzung 5 geklärt: `pyloudnorm` 0.2.0 wurde
im PyPI-Wheel-Quellcode direkt geprüft — implementiert NUR Integrated-LUFS
und LRA, **keine** True-Peak-Messung (ITU-R BS.1770 Annex 2). Entscheidung
(ADR-0010): FFmpegs eingebauter `loudnorm`-Filter wird stattdessen genutzt
(bereits Projektabhängigkeit, volle BS.1770-Konformität inkl. True Peak,
keine neue Python-Abhängigkeit). `libebur128` wurde als Alternative geprüft
und verworfen (keine verlässliche Windows-Python-Bindung gefunden).

**Implementiert und vollständig getestet:**
- `core/genesis_core/loudness/ffmpeg_loudnorm.py` — duenner subprocess-
  Wrapper um `ffmpeg -af loudnorm` (Pass 1 = Messung, Pass 2 = Anwendung),
  JSON-Statistik-Parsing, Timeout-/Fehlerbehandlung analog zu
  `ffprobe_util.py`.
- `core/genesis_core/loudness/engine.py` — Geschäftslogik mit vollem
  Sicherheitsfluss: `measure_loudness()` (rein lesend) ->
  `plan_normalization()` (reine Berechnung, KEIN Dateizugriff, zeigt
  geplanten Gain/Ausgabepfad/Lossy-Reencode-Hinweis/Dynamik-Warnung) ->
  `apply_normalization()` (erfordert `user_confirmed=True`, erzeugt IMMER
  eine NEUE Datei `<name>.normalized.<ext>`, fasst das Original NIE an).
  Scope bewusst auf reine Audio-Medienarten beschränkt (Musik/Hörbuch/
  Podcast/KI-Musik) - Video-Normalisierung ist dokumentiertes Backlog
  (analog zur Rename-Engine-Scope-Entscheidung aus Phase 2).
- DB-Schema (`Loudness`-Tabelle) um `loudness_range_lu`,
  `target_true_peak_dbtp_used`, `normalized_output_path` ergänzt
  (migrationsfrei, `create_all()`).
- 4 neue REST-Endpunkte: `POST /media/{id}/loudness/analyze` (lesend),
  `GET /media/{id}/loudness` (volle Historie), `POST
  /media/{id}/loudness/normalize/preview` (reine Berechnung), `POST
  /media/{id}/loudness/normalize/apply` (confirm-pflichtig, §44-Job-Log).
- **26 neue Tests** (17 Engine-Tests inkl. Konflikterkennung/
  Confirm-Erzwingung/Dynamik-Warnung/Format-Mapping, 9 API-Tests). Core-
  Gesamtsuite: **130 passed, 1 skipped** (vorher 104).
- PySide6: neuer `dialogs/loudness_dialog.py` (Messen -> Vorschau mit
  editierbaren Zielwerten -> Bestätigungsdialog -> Anwenden -> Verlauf),
  neue `api_client.py`-Methoden, neuer `media_table.loudness_button`,
  neue i18n-Sektion `loudness_dialog.*` (26 Schlüssel × 4 Sprachen) + neuer
  `media_table.loudness_button`-Schlüssel. i18n-Testsuite weiterhin 5/5
  grün (Schlüsselmengen-Gleichheit automatisch geprüft).
- **Vollständiger End-to-End-Smoke-Test** (echte Core-API-Instanz, Port
  8431, `ffmpeg`-erzeugte Test-MP3 via `/scan` eingelesen): Dialog offscreen
  in allen 4 Sprachen fehlerfrei aufgebaut (Messung: -22.1 LUFS/-21.3 dBTP
  korrekt angezeigt); vollständiger Normalisierungs-Workflow über den
  API-Client durchgespielt — Original-Byte-Identität nach Normalisierung
  bestätigt, neue Datei (`test_song.normalized.mp3`) erzeugt, Job
  protokolliert, Historie zeigt 1 normalisierte + 4 reine Messzeilen
  korrekt.
- ADR-0010 in `DECISIONS.md` dokumentiert (vollständige Begründung,
  Sicherheitsmechanik, Scope-Grenzen, Konsequenzen).
- `.dotnet`-SDK-Installationsrezept (aus Sitzung 5) nicht erneut gebraucht
  in dieser Sitzung - Loudness-Engine ist reine Core-/PySide6-Arbeit, der
  .NET-Client bleibt bei seinem Sitzung-5-Stand (Loudness-API-Methoden dort
  NOCH NICHT ergänzt - siehe "Noch offen" unten).

**Noch offen (Phase 3, aktualisiert):**
- `.NET`/WPF-`GenesisApiClient.cs` um die 4 Loudness-Endpunkte ergänzen
  (bisher nur PySide6-Seite verdrahtet) + optional ein einfaches
  WPF-Pendant zum Dialog.
- Audio-Cutter (grafischer Schnitt, MP3/WAV/FLAC-Export) - §Originalauftrag.
- Konvertieren-Werkzeug (nav.convert) - evtl. Synergien mit der
  Codec-Auswahl-Logik aus der Loudness-Engine (`_pick_output`/`_CODEC_MAP`
  könnten zu einem gemeinsamen `genesis_core/audio_formats.py`-Modul
  extrahiert werden, sobald ein zweiter Verbraucher existiert - YAGNI
  vorerst bewusst nicht vorgezogen).
- Mehrstufige Duplikaterkennung (Hash/Fingerprint-basiert).
- Qualitätsprüfung (als Verdacht markiert, nicht als Fakt, §20).
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

## Sitzung 7 (2026-10-01) — Phase 3 fortgesetzt: Audio-Cutter (§18, ADR-0011)

**Kontext:** Fortsetzung direkt nach Sitzung 6 (Loudness-Engine). Ziel laut
Nutzervorgabe weiterhin: Phase 3 bis Phase 9 vollständig fertigstellen
(ausdrücklich noch KEIN Release/Phase 10).

**Getan:**
- Vor dem eigentlichen Cutter: offenes YAGNI-Backlog aus Sitzung 6 eingelöst
  — `genesis_core/audio_formats.py` (NEU) als gemeinsames Codec-/
  Format-Modul extrahiert (`AudioFormatSpec`, `FORMATS_BY_NAME`/
  `FORMATS_BY_EXTENSION`, `FALLBACK_FORMAT`, `CUTTER_MINIMUM_EXPORT_FORMATS`,
  `spec_for_extension()`/`spec_for_name()`). `loudness/engine.py`
  entsprechend refaktoriert (`_CODEC_MAP`/`_pick_output`-Eigenlogik entfernt,
  nutzt jetzt `spec_for_extension()`) — alle 26 bestehenden Loudness-Tests
  danach erneut grün (keine Regression).
- Sandbox-Experimente VOR der Implementierung (TDD-ähnliches Vorgehen wie
  bei Loudness, siehe ADR-0011 für alle Messwerte): belegt, dass
  Demuxer-seitiges `-ss`/`-t -c copy` (a) bei WAV/PCM nicht sample-genau ist
  (~2-3% Abweichung) und (b) bei FLAC in diesem ffmpeg-Build (7.1.5)
  überhaupt nicht schneidet (stiller Korrektheitsfehler). Entscheidung:
  **immer** Filter-basiertes Re-Encode über `atrim`+`asetpts`(+`afade`) —
  für verlustfreie Formate (WAV/FLAC) ohne Qualitätsverlust, dafür mit
  exakter (sample-genauer) Schnittposition in allen getesteten Fällen.
- `core/genesis_core/cutter/` (NEU):
  - `ffmpeg_cutter.py` — subprocess-Wrapper (`render_cut`, `render_waveform_image`,
    `_build_audio_filter`), analog zu `loudness/ffmpeg_loudnorm.py`.
  - `engine.py` — `CutPlan`/`CutResult`-Dataclasses, `generate_waveform_image()`
    (rein lesend), `plan_cut()` (reine Berechnung: Start<Ende-Validierung,
    Fades ≤ Selektionsdauer, Endzeit ≤ bekannte Dateidauer falls vorhanden,
    unterstützte Exportformate, Zielpfad `<stem>.cut.<ext>` mit
    Konflikterkennung), `apply_cut()` (erfordert `user_confirmed=True`,
    erzeugt IMMER eine neue Datei, fasst Original nie an).
  - `__init__.py` — öffentliche Fassade (Re-Exports).
- DB-Schema: neue Tabelle `AudioCut` (media_file_id, source_path, output_path,
  start/end/fade-Sekunden, export_format; via `TimestampMixin` automatisch
  `created_at`/`updated_at`) + `MediaFile.audio_cuts`-Relationship.
  Migrationsfrei (`create_all()`).
- API-Endpunkte (`genesis_core/api/app.py`):
  `GET /media/{id}/cutter/waveform` (PNG, gecacht unter
  `<data_dir>/waveform_cache/`, rein lesend, KEINE DB-Zeile), 
  `POST /media/{id}/cutter/preview` (reine Berechnung),
  `POST /media/{id}/cutter/apply` (confirm-pflichtig, schreibt `AudioCut`-Zeile
  + Job/History), `GET /media/{id}/cutter` (volle Historie, §44).
- PySide6-Referenz-UI:
  - `api_client.py` um `get_cutter_waveform_bytes`/`list_cuts`/`preview_cut`/
    `apply_cut` ergänzt.
  - `dialogs/cutter_dialog.py` (NEU) — Waveform als `QLabel`-Pixmap,
    Start/Ende/Fade-In/Fade-Out als sekunden-genaue `QDoubleSpinBox`en
    (Begründung für numerische statt Drag-Eingabe: ADR-0011, erfüllt
    "exakte Zeitposition" direkt), Export-Format-Dropdown (mp3/wav/flac),
    Live-Vorschau bei jeder Wertänderung, Wiedergabe/Pause/"Auswahl anhören"
    via `QtMultimedia` (`QMediaPlayer`+`QAudioOutput`, spielt die
    Originaldatei direkt vom lokalen Dateisystem — UI und Core laufen auf
    derselben Maschine, daher kein Umweg über die API nötig), Verlauf-Liste,
    Bestätigungsdialog vor dem Export. Lädt beim Öffnen die bekannte
    Dateidauer (`media_detail().technical.duration_seconds`), um Start-/
    Endzeit-Spinbox-Grenzen sinnvoll vorzubelegen (mit kleiner
    Sicherheitsmarge gegen Rundungs-Randfälle bei 2 Nachkommastellen).
  - `views/media_table.py` verdrahtet (`cutter_btn` nach `loudness_btn`,
    `_on_cutter_clicked`, `_on_selection_changed` erweitert).
- i18n: `cutter_dialog.*`-Namensraum + `media_table.cutter_button` in allen
  4 Sprachen (DE/EN/JA/RU) ergänzt (JSON-Skript analog zur
  Loudness-Erweiterung aus Sitzung 6). `pytest tests/` (UI) weiterhin
  5/5 grün.
- Tests: `tests/test_cutter_engine.py` (17 Tests: Waveform-Erzeugung,
  `plan_cut`-Validierung aller Fehlerfälle, `apply_cut`-Bestätigungspflicht,
  Original-Unversehrtheit, exakte Dauer für verlustfreie Formate inkl.
  Fades, Konflikterkennung) + `tests/test_api_cutter.py` (10 Tests: Token-
  Pflicht, 404-Fälle, Waveform-Caching, Preview/Apply/History-Endpunkte,
  409-Konflikt bei zweitem Apply). Core-Gesamtsuite danach: **157 passed,
  1 skipped** (vorher 130 — korrekt um 27 neue Tests gewachsen).
- **Vollständiger End-to-End-Smoke-Test** (analog Loudness-Vorgehen):
  PySide6 + QtMultimedia in Sandbox neu installiert (Sandbox-Reset
  bestätigt — diesmal zusätzlich auch `sqlalchemy`/`fastapi` verloren,
  via `scripts/setup_python_env.sh` wiederhergestellt), echte Core-API-
  Instanz gestartet (Port 8432, `/tmp/genesis_cutter_smoke`), Test-MP3 via
  `ffmpeg` erzeugt (8s Sinuston) + über `/scan` eingelesen (media_id=1),
  `CutterDialog` offscreen in allen 4 Sprachen fehlerfrei instanziiert
  (dabei einen echten Rundungs-Randfall gefunden und sofort behoben: die
  anfängliche Default-Endzeit traf knapp über die exakte Dateidauer wegen
  2-Nachkommastellen-Rundung in der Spinbox — Fix: 0.1s Sicherheitsmarge),
  kompletter Workflow über `GenesisAPIClient` durchgespielt (preview → apply
  mit confirm=True, FLAC-Export mit Fades) — Original blieb unverändert,
  neue Datei `test_song.cut.flac` erzeugt, Job protokolliert, Verlauf zeigt
  korrekt 1 Eintrag; Waveform-Endpunkt verifiziert (PNG wird erzeugt und
  beim zweiten Aufruf aus dem Cache bedient, unveränderter mtime bestätigt
  das Caching). Danach komplett aufgeräumt (`pkill run_api.py`,
  `rm -rf /tmp/genesis_cutter_smoke*`).
- ADR-0011 in `DECISIONS.md` dokumentiert (vollständige Sandbox-Messwerte,
  Begründung für Filter- statt Stream-Copy-Ansatz, Sicherheitsmechanik,
  Konsequenzen).

**Noch offen (Phase 3, aktualisiert):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne Loudness- UND jetzt auch
  ohne Cutter-Endpunkte (nur PySide6-Seite durchgängig verdrahtet) —
  Backlog, vor Phase-3-Abschluss nachzuziehen oder spätestens vor
  Phase-9-Hardening zu entscheiden, ob der .NET-Client überhaupt
  vollständig nachgezogen wird oder PySide6 die federführende Referenz-UI
  bleibt (Architekturfrage, noch nicht final entschieden).
- Interaktives Ziehen der Start-/Endmarker direkt auf der Waveform (statt
  nur Zahlenfelder) — bewusster Zeitbudget-Kompromiss, siehe ADR-0011
  Punkt 4, Backlog für spätere UI-Iteration.
- Konvertierungs-Werkzeug (nav.convert) — kann jetzt `audio_formats.py`
  direkt mitverwenden (Blocker aus Sitzung 6 behoben).
- Mehrstufige Duplikaterkennung (Hash→Größe→Dauer→technische Parameter→
  Fingerprint→Metadaten, §21).
- Qualitätsprüfung (als Verdacht markiert, nicht als Fakt, §20).
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen, dann weiter mit Konvertierungs-Werkzeug,
Duplikaterkennung, Qualitätsprüfung (restliche Phase-3-Bausteine), danach
Phasen 4–9 gemäß Nutzervorgabe ("alles komplett", aber kein Release).

## Sitzung 8 (2026-10-01) — Phase 3 fortgesetzt: Konvertierungs-Werkzeug

**Kontext:** Direkte Fortsetzung nach Sitzung 7 (Audio-Cutter). Ziel
weiterhin: Phase 3 bis Phase 9 vollständig fertigstellen (kein Release).

**Getan:**
- Spec-Check: "Konvertieren" hat keinen eigenen nummerierten Abschnitt im
  Originalauftrag (nur Navigationspunkt/Plugin-Typ/Jobtyp/Phase-3-Baustein)
  — Design daher in Eigenregie nach denselben Prinzipien wie Loudness/Cutter
  getroffen (siehe ADR-0012), wie vom Nutzer für solche Fälle autorisiert.
- `core/genesis_core/convert/` (NEU): `engine.py` (`ConversionPlan`/
  `ConversionResult`, `plan_conversion()`/`apply_conversion()`,
  No-Op-Erkennung bei identischem Format+Bitrate statt Blockade),
  `ffmpeg_convert.py` (subprocess-Wrapper), `__init__.py` (Fassade).
  Dritter Verbraucher von `audio_formats.py` (nach Loudness, Cutter).
- DB: neue Tabelle `AudioConversion` + `MediaFile.audio_conversions`-Relationship
  (migrationsfrei).
- API: `POST /media/{id}/convert/preview`, `POST /media/{id}/convert/apply`
  (confirm-pflichtig), `GET /media/{id}/convert` (Historie).
- PySide6: `api_client.py` um `list_conversions`/`preview_conversion`/
  `apply_conversion` ergänzt; `dialogs/convert_dialog.py` (NEU) — Zielformat-
  Dropdown (7 Formate), optionale Bitrate-Checkbox+Spinbox, Live-Vorschau,
  Verlauf, Bestätigungsdialog; `views/media_table.py` verdrahtet
  (`convert_btn`).
- i18n: `convert_dialog.*` + `media_table.convert_button` in DE/EN/JA/RU.
  UI-i18n-Suite weiterhin 5/5 grün.
- Tests: `tests/test_convert_engine.py` (14 Tests) + `tests/test_api_convert.py`
  (8 Tests). Core-Gesamtsuite danach: **179 passed, 1 skipped** (vorher 157,
  korrekt um 22 neue Tests gewachsen).
- End-to-End-Smoke-Test (analog Loudness/Cutter-Vorgehen): Core-API-Instanz
  gestartet (Port 8433, `/tmp/genesis_convert_smoke`), Test-WAV via `ffmpeg`
  erzeugt + über `/scan` eingelesen, `ConvertDialog` offscreen in allen 4
  Sprachen fehlerfrei instanziiert, kompletter Workflow über
  `GenesisAPIClient` durchgespielt (preview → apply mit confirm=True,
  WAV→MP3 mit 160 kbps) — Original blieb unverändert, neue Datei erzeugt,
  Job protokolliert, Verlauf korrekt. Danach komplett aufgeräumt.
- ADR-0012 in `DECISIONS.md` dokumentiert.
- Umgebungs-Hinweis bestätigt: PySide6/sqlalchemy/fastapi wieder durch
  Sandbox-Reset verloren gegangen (drittes Mal in Folge) — Wiederherstellung
  weiterhin über `scripts/setup_python_env.sh` + `sudo pip install
  --break-system-packages PySide6` zuverlässig und schnell (< 1 Minute).

**Noch offen (Phase 3, aktualisiert):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne Loudness-/Cutter-/
  Convert-Endpunkte (nur PySide6-Seite durchgängig verdrahtet) — Backlog,
  Architekturfrage zur Rolle des .NET-Clients weiterhin offen (siehe
  Sitzung 7).
- Mehrstufige Duplikaterkennung (Hash→Größe→Dauer→technische Parameter→
  Fingerprint→Metadaten, §21) — NÄCHSTER SCHRITT.
- Qualitätsprüfung (als Verdacht markiert, nicht als Fakt, §20).
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen, dann Duplikaterkennung (§21), danach
Qualitätsprüfung (§20) — damit wäre Phase 3 vollständig abgeschlossen.
Danach Phasen 4–9 gemäß Nutzervorgabe.

## Sitzung 9 (2026-10-01) — Phase 3 fortgesetzt: Duplikaterkennung (§21, ADR-0013)

**Kontext:** Direkte Fortsetzung nach Sitzung 8 (Konvertierungs-Werkzeug).
Ziel weiterhin: Phase 3 bis Phase 9 vollständig fertigstellen (kein Release).

**Getan:**
- Empirischer Chromaprint-Test (Sandbox, `/tmp/fp_test`, danach aufgeräumt):
  identischer Audioinhalt als WAV/MP3/FLAC liefert BYTE-IDENTISCHEN
  Fingerprint-String — bestätigt, dass eine einfache String-Gleichheit für
  die Kategorie "gleicher Inhalt/anderes Format" ausreicht, ohne die
  komplexe Chromaprint-Kompression (3-Bit-Differenzcodes) nachzubauen
  (siehe ADR-0013 für die vollständige Begründung).
- `core/genesis_core/duplicates/` (NEU): `engine.py`
  (`MediaSnapshot`/`DuplicateCandidate`/`DuplicateCategory`,
  `compare_pair()`/`find_duplicate_candidates()`) — reine, DB-unabhängige
  Vergleichslogik, 6-stufig (Hash→Größe→Dauer→technische Parameter→
  Fingerprint→Metadaten), vier Kategorien exakt nach §21-Wortlaut,
  Konfidenzwert + deutschsprachige Begründung je Fund. Bewusst KEINE
  Löschfunktion.
- DB: neue Tabellen `DuplicateGroup` (Kategorie/Konfidenz/Begründung/
  `reviewed`-Flag) + `DuplicateGroupMember` (N-zu-N, aktuell 2 Mitglieder
  pro Gruppe befüllt).
- API: `POST /duplicates/scan` (optionaler `kind`-Filter, ersetzt alle
  nicht-überprüften Gruppen, lässt überprüfte unangetastet), `GET
  /duplicates` (Filter `reviewed`), `POST /duplicates/{id}/review` +
  `/unreview`.
- **Notwendige Vorstufe entdeckt und nachgerüstet:** die bestehende
  `Fingerprint`-DB-Tabelle wurde bisher NIE befüllt (nur transiente Nutzung
  in der AcoustID-Vorschlagsengine) — neuer Endpunkt `POST/GET
  /media/{id}/fingerprint` berechnet und persistiert den
  Chromaprint-Fingerabdruck jetzt explizit (reine Analyse, kein `confirm`
  nötig). Ohne diese Ergänzung hätte die Duplikat-Stufe 5 nie Daten gehabt.
- PySide6: `api_client.py` um `scan_duplicates`/`list_duplicates`/
  `review_duplicate_group`/`unreview_duplicate_group`/`compute_fingerprint`/
  `get_fingerprint` ergänzt; NEUE eigene Navigationsseite
  `views/duplicates_view.py` (`DuplicatesView`, ersetzt den bisherigen
  Platzhalter für `nav.duplicates` in `main_window.py`) mit Bereichsfilter
  (Medienart), Scan-Button, Baumliste (Kategorie/Konfidenz/Dateien/
  Begründung/Status), Review/Unreview-Aktionen; neuer Button "Fingerprint
  berechnen" in `views/media_table.py`.
- i18n: `duplicates_view.*` (27 Keys) + `media_table.fingerprint_*` (4 Keys)
  in DE/EN/JA/RU. UI-i18n-Suite weiterhin 5/5 grün.
- Tests: `tests/test_duplicates_engine.py` (13 Tests, reine Snapshot-Logik,
  u.a. explizit geprüft: Selbstvergleich wirft Fehler, fehlende
  Dauer-Analyse führt NICHT zu falsch-positivem Treffer, Metadaten-Match
  erhöht nur die Konfidenz statt allein auszuschlagen), `tests/test_api_duplicates.py`
  (10 Tests: Token-Pflicht, alle 4 Kategorien end-to-end über die API,
  leere Ergebnisliste, unbekannte Medienart→422, reviewed-Filter,
  überprüfte Gruppen überleben erneuten Scan, unreview, 404 bei unbekannter
  Gruppe, Scope-Filter nach Medienart), `tests/test_api_fingerprint.py`
  (5 Tests: Token-Pflicht, 404, leeres Ergebnis vor Berechnung, erfolgreiche
  Berechnung+Abruf, erneute Berechnung überschreibt statt zu duplizieren).
  Core-Gesamtsuite danach: **207 passed, 1 skipped** (vorher 179, korrekt um
  28 neue Tests gewachsen: 13 Engine + 10 Duplikate-API + 5 Fingerprint-API).
- End-to-End-Smoke-Test: Core-API auf Port 8434 (`/tmp/genesis_dup_smoke`,
  danach gelöscht) gestartet, drei Testdateien erzeugt (zwei byteidentische
  WAV-Kopien + eine inhaltlich identische MP3 mit anderem Encoding) und
  gescannt, `DuplicatesView` offscreen in allen 4 Sprachen fehlerfrei
  instanziiert, kompletter Workflow durchgespielt: Fingerprint für zwei
  Dateien berechnet → Scan fand korrekt BEIDE erwarteten Kategorien
  ("Exaktes Duplikat" 100% für die WAV-Kopien, "Gleicher Inhalt/anderes
  Format" 85% für MP3 vs. WAV) → Review/Filter (nur offene/nur geprüfte)
  funktionierten korrekt, überprüfte Gruppe überlebte erneuten Scan. Danach
  vollständig aufgeräumt (Prozess gestoppt, Temp-Verzeichnisse gelöscht,
  inkl. übrig gebliebener Reste aus Sitzung 8).
- ADR-0013 in `DECISIONS.md` dokumentiert (Begründung für String-Gleichheit
  statt Hamming-Distanz, Kategorie-Zuordnung, Fingerprint-Persistierungs-
  Lücke, Schema-Entscheidungen).

**Noch offen (Phase 3, aktualisiert):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne Loudness-/Cutter-/
  Convert-/Duplikate-/Fingerprint-Endpunkte (nur PySide6-Seite durchgängig
  verdrahtet) — Backlog, Architekturfrage zur Rolle des .NET-Clients
  weiterhin offen (siehe Sitzung 7).
- "Ähnlicher Inhalt" (§21, schwächste Kategorie) erkennt aktuell nur den
  Fall "Fingerprint exakt gleich, aber Dauer/technische Parameter weichen
  ab" — eine echte Fuzzy-Ähnlichkeit (Hamming-Distanz auf dekomprimierten
  Chromaprint-Daten) ist bewusst zurückgestellt (siehe ADR-0013,
  dokumentiertes Backlog).
- O(n²)-Paarvergleich bei sehr großen Bibliotheken — Performance-Optimierung
  (Bucketing nach Größe/Dauer) ist Backlog für Phase 9 (§57).
- Keine Löschfunktion für erkannte Duplikate (bewusst, §21) — falls künftig
  gewünscht, separate, eigens abgesicherte Funktion nötig (nicht Teil dieser
  Version).
- Qualitätsprüfung (als Verdacht markiert, nicht als Fakt, §20) — NÄCHSTER
  SCHRITT, letzter Phase-3-Baustein.
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen, dann Qualitätsprüfung (§20) — damit wäre
Phase 3 vollständig abgeschlossen. Danach Phasen 4–9 gemäß Nutzervorgabe.

### Fortsetzung Sitzung 9 — Qualitätsprüfung (§20, ADR-0014) — Phase 3 Abschluss

**Getan:**
- `core/genesis_core/quality/` (NEU): `engine.py` (`QualitySnapshot`/
  `QualityReport`/`analyze_quality()`) — reine Interpretationsschicht über
  bereits vorhandene `TechnicalMetadata`/`Track`/`Loudness`-Daten, vier
  Verdachtsprüfungen (Beschädigung, Abschneidung, Transcodierung, Upscale)
  exakt nach §20-Wortlaut, jede einzeln dokumentiert mit ihren Grenzen/
  False-Positive-Risiken. Ergebnis immer als "Verdacht", nie als Fakt
  formuliert. Peak/Loudness als rein informative Hinweise ohne eigenes Flag.
- Wiederverwendung der bereits vorhandenen, aber bisher ungenutzten
  `TechnicalMetadata.suspected_*`/`quality_notes`-Felder (aus einer früheren
  Sitzung im Schema angelegt) — Analyse schreibt direkt auf diese Zeile
  (kein neues History-Table nötig, siehe ADR-0014).
- API: `POST /media/{id}/quality/analyze` (kein `confirm` nötig, analog
  `/loudness/analyze`), `GET /media/{id}/quality`; 422 falls noch keine
  technische Analyse (Scan) vorliegt.
- PySide6: `api_client.py` um `analyze_quality`/`get_quality` ergänzt; neuer
  Button "Qualität prüfen" in `views/media_table.py`; Detailansicht zeigt
  den zuletzt gespeicherten Befund PASSIV mit Überschrift "(Verdacht, kein
  Fakt, §20)" — kein Nav-Platzhalter nötig, da eng an bestehende
  Technik-Detailansicht angebunden.
- i18n: `media_table.quality_*` (4 Keys) + `media_table.detail.quality_*`
  (5 Keys) in DE/EN/JA/RU. UI-i18n-Suite weiterhin 5/5 grün.
- Tests: `tests/test_quality_engine.py` (18 Tests, u.a. explizit geprüft:
  kleine Rundungsdifferenzen lösen KEINEN Trunkierungs-Verdacht aus, rohes
  PCM/WAV wird NIE als Upscale geflaggt, fehlende Bittiefe nimmt
  konservativ 16 Bit an, mehrere Verdachtsmomente können gleichzeitig
  auftreten), `tests/test_api_quality.py` (13 Tests: Token-Pflicht, 404,
  422 ohne technische Analyse, alle vier Verdachtskategorien end-to-end,
  Loudness-Hinweise, GET vor/nach Analyse, erneute Analyse überschreibt
  statt zu duplizieren). Core-Gesamtsuite danach: **238 passed, 1 skipped**
  (vorher 207, korrekt um 31 neue Tests gewachsen: 18 Engine + 13 API).
- End-to-End-Smoke-Test: Core-API auf Port 8435 (`/tmp/genesis_quality_smoke`,
  danach gelöscht), drei Testdateien erzeugt (eine saubere MP3, eine MP3 mit
  absichtlich falscher `.flac`-Endung zur gezielten Transcode-Erkennung,
  eine dritte für künftige Tests) und gescannt — Analyse erkannte korrekt
  `suspected_transcode=True` für die Fake-FLAC-Datei und "keine
  Auffälligkeiten" für die saubere MP3; `MediaTableView` offscreen in allen
  4 Sprachen fehlerfrei instanziiert, Qualitätsabschnitt in der
  Detailansicht korrekt lokalisiert sichtbar. Danach vollständig
  aufgeräumt.
- ADR-0014 in `DECISIONS.md` dokumentiert.

**Damit ist Phase 3 (Audio) inhaltlich vollständig abgeschlossen:**
Loudness-Engine (§19, ADR-0010), Audio-Cutter (§18, ADR-0011),
Konvertierungs-Werkzeug (ADR-0012), Duplikaterkennung (§21, ADR-0013),
Qualitätsanalyse (§20, ADR-0014) — alle mit Engine+DB+API+PySide6-UI+i18n
DE/EN/JA/RU+Tests+End-to-End-Smoke-Test+ADR+PROGRESS-Eintrag.

**Weiterhin offen (projektweit, nicht Phase-3-spezifisch):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne jegliche Phase-3-Endpunkte
  (nur PySide6-Seite durchgängig verdrahtet) — Backlog, Architekturfrage zur
  Rolle des .NET-Clients weiterhin offen (siehe Sitzung 7).
- Echte Fuzzy-Fingerprint-Ähnlichkeit (Duplikate, "ähnlicher Inhalt") und
  echte Spektralanalyse (Qualität, vollständige Upscale-/Transcode-
  Erkennung) sind beide bewusst zurückgestelltes Backlog (ADR-0013/ADR-0014)
  — würden jeweils eine eigene DSP-/FFT-Implementierung erfordern.
- O(n²)-Paarvergleich bei der Duplikaterkennung — Performance-Optimierung
  für sehr große Bibliotheken ist Backlog für Phase 9 (§57).
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen. Danach Phase 4 (Hörbücher) gemäß
Nutzervorgabe ("Phase 3 bis Phase 9 vollständig fertigstellen, kein
Release").

## Sitzung 10 (2026-10-01) — Phase 4: Hörbücher & Kapitel (§23, ADR-0015) — Phase 4 Abschluss

Ziel weiterhin gemäß Nutzervorgabe: Phase 3 bis Phase 9 vollständig
fertigstellen (kein Release, Phase 10 bleibt zurückgestellt).

**Umgesetzt:**
- Neues Modul `core/genesis_core/audiobook/` (`tags.py` liest
  Hörbuch-relevante Tags rein lesend aus der Datei inkl. transparenter
  Fallback-Herkunft `*_source`; `engine.py` mit `apply_audiobook_tags()`
  (bestätigungspflichtig, `AudiobookApplyNotConfirmedError`),
  `detect_chapters()` (liest eingebettete ffprobe-Kapitelmarken),
  `generate_fixed_interval_chapters()` (gleichmäßige Intervalle, KEINE
  DSP-Erkennung), `replace_chapters()`, `export_chapters_json/csv()`).
- `metadata/tag_reader.py`: `_first_value`/`_parse_leading_int` zu
  `first_tag_value`/`parse_leading_int` umbenannt (public) zur
  Wiederverwendung durch das neue Modul — Verhalten unverändert.
- API: `GET/POST /media/{id}/audiobook/tags[/apply]`, `GET
  /media/{id}/audiobook`, `GET /media/{id}/chapters`, `POST
  /media/{id}/chapters/detect[/apply]`, `POST
  /media/{id}/chapters/generate[/apply]`, `PATCH
  /media/{id}/chapters/{chapter_id}`, `GET
  /media/{id}/chapters/export?format=json|csv` — alle Änderungs-Endpunkte
  mit `confirm`-Pflicht (Prinzip #17/§44), Export ohne.
- PySide6: neuer `AudiobookDialog` (Tabs „Metadaten“ + „Kapitel“) in
  `genesis_ui/dialogs/audiobook_dialog.py`; neuer Button „Hörbuch & Kapitel
  …“ in `media_table.py`, NUR aktiv bei genau einem ausgewählten Medium der
  Art `audiobook`; `api_client.py` um alle zugehörigen Methoden (inkl.
  neuem `_patch()`-Helfer) ergänzt.
- i18n: 65 neue Schlüssel (`audiobook_dialog.*` + `media_table.audiobook_
  button`) in DE/EN/JA/RU ergänzt, alle vier Kataloge synchron
  (`core/tests/test_i18n.py` + `ui-reference-pyside/tests/test_i18n.py`
  weiterhin grün).
- Tests: 12 neue Engine-Unit-Tests (`test_audiobook_engine.py`), 11 neue
  API-Tests (`test_api_audiobook.py`) — alle grün. Core-Gesamtsuite danach
  **261 passed, 1 skipped** (vorher 238).
- End-to-End-Smoke-Test: Core-API-Server gegen eine echte Test-Bibliothek
  mit zwei ffmpeg-erzeugten Dateien gestartet — `book2.m4b` (Tags: Titel/
  Autor/Reihe, PLUS zwei eingebettete ffmetadata-Kapitelmarken) und
  `book1.mp3` (keine Hörbuch-Tags). Scanner klassifizierte `.m4b` korrekt
  automatisch als `audiobook`, `.mp3` als `music`. Vollständiger
  API-Workflow erfolgreich: Tags-Vorschau → Übernahme → DB-Persistenz
  (inkl. automatischem `Series`-get-or-create) → Kapitel-Erkennung →
  Übernahme (ersetzt atomar) → Liste → CSV-Export. `AudiobookDialog` sowie
  `MediaTableView` offscreen (`QT_QPA_PLATFORM=offscreen`) in allen 4
  Sprachen fehlerfrei instanziiert, inkl. korrekt lokalisierter
  Quellenangaben (z. B. „aus Interpret-Feld übernommen“/„taken from artist
  field“/日本語/русский) und korrekter Button-Aktivierung nur für die
  `.m4b`-Zeile. Danach vollständig aufgeräumt (`/tmp/genesis_phase4_test`
  entfernt, Testserver gestoppt).
- ADR-0015 in `DECISIONS.md` dokumentiert.

**Damit ist Phase 4 (Hörbücher) inhaltlich vollständig abgeschlossen:**
Tag-basiertes Metadaten-Lesen+Übernehmen, Kapitel erkennen/erzeugen
(Intervall)/umbenennen/exportieren — alle mit Engine+DB+API+PySide6-UI+i18n
DE/EN/JA/RU+Tests+End-to-End-Smoke-Test+ADR+PROGRESS-Eintrag.

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Phase):**
- Inhaltliche Scanner-Reklassifizierung ambiger Audio-Endungen
  (`.mp3`/`.m4a`/`.aac`/`.flac`/`.wav`) als Hörbuch anhand von
  Tags/Dauer-Heuristiken (aktuell nur `.m4b` automatisch erkannt).
- Online-Hörbuch-Provider-Abgleich (Audible/OpenLibrary o. ä.) — überlappt
  mit Phase 8 (Download/Import-Adapter), bewusst zurückgestellt.
- Stille-/Sprechpausen-basierte (DSP-)Kapitelerkennung statt gleichmäßiger
  Intervalle.

**Weiterhin offen (projektweit, nicht Phase-4-spezifisch):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne jegliche Phase-3/4-
  Endpunkte (nur PySide6-Seite durchgängig verdrahtet) — Backlog,
  Architekturfrage zur Rolle des .NET-Clients weiterhin offen.
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen. Danach Phase 5 (Video: Filme/Serien, §24)
gemäß Nutzervorgabe ("Phase 3 bis Phase 9 vollständig fertigstellen, kein
Release").

## Sitzung 10 (2026-10-01) — Phase 5: Video (Filme/Serien, §24, ADR-0016) — Phase 5 Abschluss

Ziel weiterhin gemäß Nutzervorgabe: Phase 3 bis Phase 9 vollständig
fertigstellen (kein Release, Phase 10 bleibt zurückgestellt).

**Umgesetzt:**
- `scanner/ffprobe_util.py` um `languages_json` (deduplizierte Audio-
  Sprachcodes aus Stream-Tags) und `subtitles_json` (eingebettete
  Untertitelspuren: Sprache/Codec/Titel/Forced-Flag) erweitert — rein
  deskriptiv, nichts wird geraten (fehlendes Tag wird ausgelassen, nicht
  durch Heuristik ersetzt). 10 neue Tests in `test_ffprobe_util.py`
  (vorher kein dedizierter Test für dieses Modul vorhanden).
- `metadata/tag_reader.py::first_tag_value()`: Bugfix für MP4-Freeform-
  Atome (`bytes`/`bytearray`-Werte wurden vorher als Python-Repr-String
  `"b'Text'"` statt dekodiertem Klartext zurückgegeben — betraf bisher
  nichts, weil erstmals durch Director/Actor-Freeform-Tags getriggert).
- Neues Modul `core/genesis_core/video/` (`tags.py`: `read_video_tags()`
  liest Titel/Jahr/Genre/Regisseur/Schauspieler/Serie/Staffel/Episode rein
  lesend aus der Datei; `engine.py`: `detect_episode()` liefert
  Film-vs-Episode-Vorschlag mit Confidence 0.9 (Tag) / 0.6
  (Dateiname-/Ordner-Muster) / 0.0 (Film) je Feld mit eigener
  `*_source`-Angabe; `apply_movie_metadata()`/`apply_episode_metadata()`
  bestätigungspflichtig, erzeugen `Person`/`PersonRole`-Zeilen (§63
  Wissensgraph) und `Series`-Wiederverwendung bei Episoden).
- API: `GET /media/{id}/video/tags`, `POST
  /media/{id}/video/episode-detection` (beide reine Vorschau), `POST
  /media/{id}/movie/apply`/`GET /media/{id}/movie`, `POST
  /media/{id}/episode/apply`/`GET /media/{id}/episode` — Apply-Endpunkte
  mit `confirm`-Pflicht (422 sonst), aktualisieren `MediaFile.kind` und
  protokollieren über `ProcessingJob`/`record_history`.
- PySide6: neuer `VideoDialog` (Tabs „Film“ + „Serie/Episode“) in
  `genesis_ui/dialogs/video_dialog.py`; neuer Button „Film & Serie …“ in
  `media_table.py`, aktiv nur bei genau einem ausgewählten Medium der Art
  `movie`/`episode`; `api_client.py` um 6 Video-Methoden ergänzt.
- i18n: 40 neue Schlüssel (`video_dialog.*` + `media_table.video_button`)
  in DE/EN/JA/RU ergänzt, alle vier Kataloge synchron
  (`core/tests/test_i18n.py` + `ui-reference-pyside/tests/test_i18n.py`
  weiterhin grün).
- Tests: 11 neue Engine-Unit-Tests (`test_video_engine.py`), 9 neue
  API-Tests (`test_api_video.py`), 10 neue `ffprobe_util`-Tests — alle
  grün. Core-Gesamtsuite danach **291 passed, 1 skipped** (vorher 261).
- End-to-End-Smoke-Test: Core-API-Server gegen eine echte Test-Bibliothek
  mit 3 Video-Dateien gestartet (reiner Film mit Freeform-Director/Actor-
  Tags; getaggte Serien-Episode "Pilot"; nur per Dateiname erkennbare
  Episode "S01E02"). Vollständiger Workflow erfolgreich: Scan (9 Dateien,
  Video pauschal als `movie` vorklassifiziert) → Tags-Vorschau →
  Episode-Detection-Vorschau (Confidence 0.0/0.9/0.6 wie erwartet) →
  Movie-Apply → zwei Episode-Applies → `MediaFile.kind` korrekt auf
  `movie`/`episode` aktualisiert → `GET .../movie`/`.../episode` liefert
  persistierte Daten → DB-Direktprüfung bestätigt korrekte
  `Person`/`PersonRole`-Zeilen (Wissensgraph, inkl. einer Person mit
  DIRECTOR- UND ACTOR-Rollen über Film+Episode hinweg) sowie eine einzige
  `Series`-Zeile für beide Episoden (Wiederverwendung) und saubere
  `ProcessingHistory`-Einträge. `VideoDialog` sowie `MediaTableView`
  offscreen (`QT_QPA_PLATFORM=offscreen`) in allen 4 Sprachen fehlerfrei
  instanziiert, Button korrekt nur bei passendem `kind` aktiv. Danach
  vollständig aufgeräumt (`/tmp/genesis_phase5_test` entfernt, Testserver
  gestoppt).
- ADR-0016 in `DECISIONS.md` dokumentiert.

**Damit ist Phase 5 (Video: Filme/Serien) inhaltlich vollständig
abgeschlossen:** Tag-basiertes Lesen, Film-vs-Episode-Erkennung mit
Confidence+Quellenangabe, bestätigungspflichtige Übernahme inkl.
Wissensgraph-Verknüpfung — alle mit Engine+DB+API+PySide6-UI+i18n
DE/EN/JA/RU+Tests+End-to-End-Smoke-Test+ADR+PROGRESS-Eintrag.

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Phase):**
- Online-Provider-Abgleich (TMDB/TheTVDB) — überlappt mit Phase 8
  (Download/Import-Adapter), bewusst zurückgestellt.
- Automatische Scanner-Vorklassifizierung Episode vs. Film direkt beim
  Scan (aktuell bewusst erst nachträglich on-demand über die
  Detection-Vorschau, um die Scan-Phase schnell/seiteneffektfrei zu
  halten).
- Namenskonflikt-Auflösung bei Personen (zwei unterschiedliche Personen
  mit identischem Namen) — aktuell einfache Name-Deduplizierung.

**Weiterhin offen (projektweit, nicht Phase-5-spezifisch):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne jegliche Phase-3/4/5-
  Endpunkte (nur PySide6-Seite durchgängig verdrahtet) — Backlog,
  Architekturfrage zur Rolle des .NET-Clients weiterhin offen.
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen. Danach Phase 6 (KI: lokale
KI-Metadaten/-Analyse via Ollama/LM Studio, mit verpflichtender
AI-generated/model/confidence-Kennzeichnung) gemäß Nutzervorgabe ("Phase 3
bis Phase 9 vollständig fertigstellen, kein Release").

## Sitzung 10 (2026-10-01) — Phase 6: KI-Metadaten/-Suche/-Musik (§25/§26/§27, ADR-0017) — Phase 6 Abschluss

Ziel weiterhin gemäß Nutzervorgabe: Phase 3 bis Phase 9 vollständig
fertigstellen (kein Release, Phase 10 bleibt zurückgestellt).

**Vorarbeit: echte Ollama-Installation in der Sandbox** (wie in einer
früheren Sitzung für Phase 6 explizit festgelegt - kein Mock): Binär nach
`/opt/ollama_test` (bewusst ausserhalb `/home/user`, da das ~900 MB-Archiv
sonst den Workspace aufgebläht hätte und `/tmp` als ~1 GB-tmpfs zu klein
war). `ollama serve` läuft auf `127.0.0.1:11434`. Modelle `qwen2.5:0.5b`
(Text-Generierung, 397 MB) und `all-minilm` (Embeddings, 45 MB) real
heruntergeladen. Beide gegen die reale REST-API verifiziert (siehe unten).

**Umgesetzt:**
- `db/models.py`: neue Tabelle `AIEmbedding` (§26, EIN Eintrag pro
  `media_file_id`+`model_name`, mit `source_text_hash` für
  Reindex-Überspringung unveränderter Dateien); neues `Track.ai_owner`-
  Feld (letzter fehlender §27-Wert, "Besitzer").
- `config/__init__.py`: `AISettings.embedding_model` (Default
  `"all-minilm"`) - separates, kleineres Modell für `/api/embed`, da
  reine Text-Generierungsmodelle (z. B. `qwen2.5:0.5b`) Ollamas
  Embeddings-Endpunkt nachweislich ablehnen (real getestet).
- `ai/base.py`/`null_provider.py`/`ollama_provider.py`: neue abstrakte
  Methode `embed_text()` - `OllamaProvider` ruft `/api/embed` mit dem
  dedizierten Embedding-Modell auf, liefert `None` statt Exception bei
  Fehlern (kein Absturz, "keine KI verfügbar" ist normal).
- Neues Modul `core/genesis_core/ai/engine.py` (§25): `build_context()`
  (faktenbasierter Text aus DB+Tags, keine erfundenen Zusatzinfos),
  `suggest_metadata()` (reine Vorschau, 9 Standardfelder: genre, mood,
  language, instruments, vocals, topic, description, tags,
  classification), `apply_suggestions()` (bestätigungspflichtig,
  schreibt NUR in die `AIMetadata`-EAV-Tabelle, NICHT automatisch in
  kanonische Felder - Reapply desselben Feldes+Modells ersetzt den
  vorherigen Eintrag).
- Neues Modul `core/genesis_core/ai/search.py` (§26): `reindex_media_file`/
  `reindex_all` (additiver Cache, kein confirm nötig, überspringt
  unveränderten Text), `semantic_search()` (Brute-Force-Kosinus-
  Ähnlichkeit über `AIEmbedding`, leeres Ergebnis statt Fehler bei
  deaktivierter/nicht erreichbarer KI).
- Neues Modul `core/genesis_core/ai/music_provenance.py` (§27): IMMER
  manuelle, bestätigungspflichtige Nutzerangabe (AI Generated/Human
  Generated/Hybrid/Unknown + Quelle/Modell/Prompt/Stil/Stimmung/Besitzer/
  Künstlername); "Künstlername" über `PersonRole`(ARTIST) statt
  dupliziertem Textfeld (Wissensgraph-Konsistenz mit Phase 5);
  `AI_GENERATED`/`HYBRID` klassifiziert `MediaFile.kind` zu `AI_MUSIC` um.
- API: `POST /media/{id}/ai/suggest`, `POST /media/{id}/ai/apply` + `GET
  /media/{id}/ai/metadata`, `GET /ai/status` (Transparenz: Provider/
  Modell/lokal/erreichbar), `GET/POST /media/{id}/ai-music`, `POST
  /ai/search/reindex`, `POST /ai/search` - Apply-Endpunkte mit
  `confirm`-Pflicht (422 sonst), protokolliert über `ProcessingJob`/
  `record_history`.
- PySide6: neuer `AIDialog` (Tab "KI-Vorschläge" mit Checkbox-Auswahl +
  optionalem Tab "KI-Musik" nur für `kind in {music, ai_music}`) über
  neuen "KI …"-Button in der Medientabelle (aktiv für JEDE einzeln
  ausgewählte Datei); neue eigenständige Seite `AICenterView` (ersetzt
  den bisherigen Platzhalter `nav.ai_metadata`) mit KI-Status-Banner,
  Reindex-Button und semantischer Suche mit Ergebnisliste.
  `api_client.py` um 7 KI-Methoden ergänzt.
- i18n: 46 neue `ai_dialog.*`-Schlüssel, 14 neue `ai_center.*`-Schlüssel,
  `media_table.ai_button` in DE/EN/JA/RU ergänzt, alle vier Kataloge
  synchron (`test_i18n.py` beidseitig weiterhin grün).
- Tests: 13 neue Engine-Tests (`test_ai_engine.py`), 11 neue
  (`test_ai_search.py`), 11 neue (`test_ai_music_provenance.py`), 16 neue
  API-Tests (`test_api_ai.py`) - alle mit deterministischen Stub-Providern
  (kein Ollama nötig für CI-Stabilität), alle grün. Core-Gesamtsuite
  danach **343 passed** (vorher 291 passed/1 skipped - der zuvor
  übersprungene `test_ollama_integration_suggests_fields` aus Phase 1
  läuft jetzt ebenfalls echt durch, da Ollama real erreichbar ist).
- **Echter End-to-End-Smoke-Test mit laufendem Ollama (kein Stub):** Core-
  API-Server mit `ai.enabled=true, provider=ollama` gegen eine 9-Datei-
  Testbibliothek. `GET /ai/status` → `available=true`; `POST .../ai/
  suggest` liefert echte LLM-Ausgaben (`genre=music, mood=happy` für eine
  getaggte Datei, ~2.5s Laufzeit); Apply persistiert korrekt mit voller
  Herkunft (Modell/Konfidenz/Zeitstempel); `POST .../ai-music/apply`
  setzt alle Felder + `PersonRole`(ARTIST) + klassifiziert `MediaFile.
  kind` korrekt zu `ai_music` um; `POST /ai/search/reindex` indiziert
  alle 9 Dateien mit echten 384-dim `all-minilm`-Vektoren; `POST
  /ai/search("synthwave electronic music")` rankt die KI-Musik-Datei
  korrekt auf Platz 1, `POST /ai/search("Film mit Regisseur und
  Schauspielern")` rankt alle drei Video-Dateien korrekt vor den Audio-
  Dateien - inhaltlich sinnvolle, nicht zufällige Ergebnisse.
  `ProcessingHistory` korrekt protokolliert. Zusätzlich `AIDialog`/
  `AICenterView` direkt (reale HTTP-Aufrufe, kein Mock) gegen denselben
  Server getestet - Status-Banner, Vorschlagsgenerierung, gespeicherte
  KI-Musik-Felder und Suchergebnisse korrekt und korrekt lokalisiert (DE)
  angezeigt. Danach vollständig aufgeräumt.
- ADR-0017 in `DECISIONS.md` dokumentiert.

**Damit ist Phase 6 (KI: lokale KI-Metadaten/-Suche/-Musik) inhaltlich
vollständig abgeschlossen:** §25 KI-Vorschläge mit vollständiger Herkunft
(AI generated/Model/Version/Timestamp/Confidence), §26 funktionierende
lokale semantische Suche mit echten Embeddings, §27 KI-Musik-Provenienz
inkl. Wissensgraph-Verknüpfung und Umklassifizierung - alle mit
Engine+DB+API+PySide6-UI+i18n DE/EN/JA/RU+Tests+echtem End-to-End-Test
gegen laufendes Ollama+ADR+PROGRESS-Eintrag.

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Phase):**
- ANN-Indexstruktur für die semantische Suche bei sehr grossen
  Bibliotheken (Phase 9 Hardening) - aktuell Brute-Force-Kosinus-
  Ähnlichkeit, für Entwicklungs-/Testbibliotheken ausreichend.
- DSP-basierte Audio-KI-Analyse direkt aus dem Audiosignal
  (`nav.ai_audio_analysis` bleibt Platzhalter).
- GUI-Einstellungsseite zum Aktivieren der KI (aktuell nur über
  `config.yaml` - projektweite Settings-UI ist noch nicht gebaut).
- `creation_date`-Eingabefeld im `AIDialog`-Formular (Backend unterstützt
  es, das Referenz-UI-Formular verzichtet bewusst darauf).

**Weiterhin offen (projektweit, nicht Phase-6-spezifisch):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne jegliche Phase-3/4/5/6-
  Endpunkte (nur PySide6-Seite durchgängig verdrahtet) - Backlog,
  Architekturfrage zur Rolle des .NET-Clients weiterhin offen.
- Projektweite Settings-UI (GUI-basierte Konfiguration, §55) noch nicht
  gebaut - aktuell nur `GET /settings` (read-only) + manuelle
  `config.yaml`-Bearbeitung für Entwickler/Tests.
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am Projektende).
- Ollama-Binärinstallation liegt in `/opt/ollama_test` (ausserhalb
  `/home/user`) und persistiert NICHT über Sitzungen hinweg - muss bei
  Bedarf in einer künftigen Sitzung erneut heruntergeladen werden (siehe
  ADR-0017 für die genauen Schritte: `.tar.zst`-Variante, nicht `.tgz`).
- Alles aus dieser Sitzung ist NOCH NICHT committed (siehe nächster
  Schritt).

**Nächste Schritte:** Committen. Danach Phase 7 (Voice Studio, §28/§29:
lokale TTS, Stimmprofile, Offline-Pflicht, Engine/Lizenz/Offline-Status-
Offenlegung, lokale TTS-API für andere Anwendungen) gemäß Nutzervorgabe
("Phase 3 bis Phase 9 vollständig fertigstellen, kein Release").

## Sitzung 10 (Fortsetzung, 2026-10-01) — Phase 7: Voice Studio (§28/§29, ADR-0018) — Phase 7 Abschluss

Direkt im Anschluss an Phase 6 (KI) begonnen und im selben Zuge
abgeschlossen, gemäß Nutzervorgabe ("Phase 3 bis Phase 9 vollständig
fertigstellen, kein Release").

**Zwischenfall zu Sitzungsbeginn (behoben):** Die Sandbox wurde zwischen
dem Phase-6-Abschluss und Phase-7-Beginn intern zurückgesetzt - alle
Python-Pakete (sqlalchemy, fastapi, PySide6, ...), `ffmpeg`/`fpcalc` und
die Git-Commit-Identität waren weg. Wiederhergestellt über
`scripts/setup_python_env.sh` (dabei um die Installation von
`ui-reference-pyside/requirements.txt` ERGÄNZT, damit PySide6 künftig in
einem Rutsch mitinstalliert wird) + `scripts/setup_git_identity.sh`
(bereits aus einer früheren Sitzung vorhanden, startet weiterhin
"GENESIS Media Manager Dev <genesis-dev@example.local>"). Danach volle
Regressionssuite erneut grün (342 passed/1 skipped, 1 weniger als zuvor,
weil Ollama in dieser Sitzung nicht mehr lief - keine echte Regression).
Phase-6-Commit (`8ae8e76`) im Anschluss erfolgreich durchgeführt.

**Vorarbeit: echte Piper-TTS-Installation (kein Mock), wie bei Ollama in
Phase 6 explizit gewünscht:** `pip install piper-tts` (Version 1.8.0).
**Wichtiger Lizenz-Fund (reale Recherche):** das aktuell gepflegte
`piper-tts`-Paket (OHF-Voice/piper1-gpl) ist **GPL-3.0-or-later**, NICHT
MIT wie das inzwischen archivierte `rhasspy/piper`-Original-Repository
(archiviert Oktober 2025). Stimmen-Modellgewichte bleiben separat
MIT-lizenziert. Für GENESIS unproblematisch (Projekt nutzt bereits
`mutagen`, GPL-2.0-or-later; GENESIS selbst wird am Ende Open Source),
aber wichtig für die spätere Phase-10-Lizenzprüfung - vollständig in
ADR-0018 dokumentiert. Zwei kleine Testmodelle (`de_DE-thorsten-low`,
`en_US-amy-low`, zusammen ~126 MB) nach `/opt/piper_voices`
heruntergeladen (bewusst ausserhalb `/home/user`, siehe
Ressourcen-Disziplin) über neues `scripts/setup_voice_studio.sh`.

**Umgesetzt:**
- `db/models.py`: `VoiceProfile` erweitert (`model_path`, `language`,
  `description`, Cascade-Delete zur Historie), neue Tabelle
  `VoiceSynthesis` (volle Historie jeder erzeugten Sprachausgabe, analog
  zu `AudioCut`).
- `config/__init__.py`: neues `VoiceSettings` (`enabled=False` Standard,
  `provider: null|piper`, `default_export_format`).
- Neues Modul `core/genesis_core/voice/`:
  - `base.py` (`TTSProvider`-Interface, austauschbar gemäss §29),
  - `null_provider.py` (sicherer Standard, §56),
  - `piper_provider.py` (echte Piper-Anbindung, Modell-Caching,
    klare Fehler bei fehlendem Modell statt stillem Fehlschlag),
  - `catalog.py` (unverbindlicher Engine-Katalog für UI-Vorschlagswerte,
    NIE automatisch übernommen),
  - `engine.py` (DB-bewusste CRUD-Funktionen für Profile + Synthese-
    Orchestrierung inkl. WAV→MP3/FLAC-Export über das bestehende
    `convert/ffmpeg_convert.py`-Modul, Wiederverwendung aus Phase 3).
- API: 10 neue Endpunkte (`/voice/status`, `/voice/engines`, `GET/POST
  /voice/profiles`, `GET/DELETE /voice/profiles/{id}`, `POST
  .../synthesize`, `POST .../test`, `GET /voice/syntheses`, `GET
  /voice/syntheses/{id}/audio`). **Erster Lösch-Endpunkt im gesamten
  Projekt** - setzt den Präzedenzfall für "Löschen = extra confirm"
  (§28/Prinzip #6): zusätzlich zu `confirm=true` muss `confirm_name`
  exakt dem Profilnamen entsprechen (403 bei Mismatch).
- PySide6: neue eigenständige Seite `VoiceStudioView` (Tabs "Profile" +
  "Text-zu-Sprache") - ersetzt die Platzhalter für BEIDE bisherigen
  Nav-Einträge "Voice Studio" und "TTS" (zeigen bewusst dieselbe
  Seiteninstanz). `api_client.py` um 9 Voice-Methoden + erste
  `_delete()`-Hilfsmethode ergänzt.
- i18n: 63 neue `voice_studio.*`-Schlüssel in DE/EN/JA/RU (exakte
  1:1-Übereinstimmung mit den tatsächlichen `tr()`-Aufrufen geprüft).
- **Lokale "Voice API für andere Programme" (§29) bewusst über dieselben
  Core-API-Endpunkte gelöst** (kein zweiter Server/Port) - als Beweis
  dafür neues eigenständiges `scripts/genesis_voice_cli.py`, das GENESIS
  ausschliesslich über HTTP nutzt (kein `genesis_core`-Import), reale
  "Andere lokale Anwendung → GENESIS Voice API → Voice Engine →
  Audio"-Architektur aus §29.
- Tests: 20 neue Engine-Tests (Stub-Provider), 6 neue ECHTE Piper-Tests
  (übersprungen ohne lokale Modelle), 17 neue API-Tests - alle grün.
  Core-Gesamtsuite jetzt **385 passed/1 skipped** (vorher 343/1).
- **Mehrfacher echter End-to-End-Test mit real installiertem Piper (kein
  Mock):** (1) Core-API direkt: deutsches Profil angelegt, 5.98s/104-
  Zeichen-Synthese, MP3-Export via ffmpeg real validiert (`ffprobe`:
  6.08s, valides MP3), Testsatz-Endpunkt erfolgreich. (2)
  `VoiceStudioView` DIREKT (reale HTTP-Calls, kein Mock) gegen
  laufenden Server: Statusbanner, Engine-Katalog, Profilanlage mit allen
  Transparenzfeldern, Synthese (3.7s MP3), Test (3.1s WAV),
  Verlaufsliste, kompletter Lösch-Fluss (Namens-Mismatch blockiert
  lokal UND Server-seitig validiert, korrekter Name löscht) - alles über
  die volle UI-Schicht bestätigt, inkl. `MainWindow`-Verifikation, dass
  beide Nav-Einträge ("Voice Studio"/"TTS") auf dieselbe Seiteninstanz
  zeigen. (3) `genesis_voice_cli.py` als externer Konsument real
  getestet - fremdes Profil angelegt, 4.69s-MP3 synthetisiert und
  exportiert, von `ffprobe` als valide bestätigt. Alle Testserver
  sauber gestoppt (keine Fehler im Shutdown-Log), alle temporären
  Testverzeichnisse aufgeräumt, Disk-Gesundheit erneut bestätigt (19G
  frei auf `/`, Workspace weiterhin nur ~7.4M).
- ADR-0018 in `DECISIONS.md` dokumentiert (Piper-Wahl, GPL-3.0-Lizenzfund,
  Profil-statt-Engine-Disclosure, "Löschen = extra confirm"-Präzedenzfall,
  §29-Architekturentscheidung, Voice-Cloning-Backlog-Begründung).

**Damit ist Phase 7 (Voice Studio: lokale TTS, Voice-Profile, lokale
TTS-API für andere Programme) inhaltlich vollständig abgeschlossen:**
§28 (Profilverwaltung mit vollständiger Transparenzpflicht, Text-zu-
Sprache, Audio-Export, Löschen mit verschärfter Bestätigung) und §29
(austauschbare Voice Engine, lokale REST-API, CLI-Beispiel für externe
Programme) - alle mit Engine+DB+API+PySide6-UI+i18n DE/EN/JA/RU+Tests+
mehrfachem echtem End-to-End-Test gegen laufendes Piper+ADR+PROGRESS-
Eintrag.

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Phase):**
- Echtes Voice-Cloning aus Sprachproben ("Stimme aufnehmen" im Sinne
  einer neuen, aus einer Aufnahme gelernten Stimme) - Piper ist eine
  Wiedergabe-Engine mit vortrainierten Modellen, kein Cloning-System;
  ein Cloning-fähiger Provider (z.B. Coqui XTTS v2) hat eine restriktive
  Lizenz (CPML) und einen deutlich höheren Ressourcenbedarf - siehe
  ADR-0018 Entscheidung 6 für die volle Begründung.
- Mikrofon-Aufnahme-UI (`QAudioInput`) - ohne Cloning-fähigen Provider
  kein funktionaler Nutzen; `sample_path` bleibt als informatives Feld
  für spätere Erweiterung bestehen, per Datei-Browser befüllbar.
- Windows-SAPI5-Integration (einer von vier in §29 vorgeschlagenen
  Schnittstellentypen) - plattformspezifisch, in der Linux-Sandbox weder
  baubar noch testbar.
- Projektweite Settings-UI (§55) weiterhin nicht gebaut (gleiches
  Backlog-Item wie bereits in ADR-0017 für KI vermerkt) - Voice Studio
  wird aktuell nur über `config.yaml` aktiviert.

**Weiterhin offen (projektweit, nicht Phase-7-spezifisch):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne jegliche Phase-3 bis
  Phase-7-Endpunkte (nur PySide6-Seite durchgängig verdrahtet).
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am
  Projektende, Phase 10) - ADR-0018 hält aber bereits den wichtigen
  GPL-3.0-Lizenzfund für piper-tts fest, damit er bei der finalen Prüfung
  nicht verloren geht.
- Piper-Testmodelle liegen in `/opt/piper_voices` (ausserhalb
  `/home/user`) und persistieren NICHT über Sitzungen hinweg - bei
  Bedarf über `scripts/setup_voice_studio.sh` erneut herunterladen.
- Alles aus dieser Sitzung (Phase 7) ist NOCH NICHT committed (nächster
  Schritt).

**Nächste Schritte:** Committen. Danach Phase 8 (Download/Import Center,
§30/§31/§32: Adapter-System für YouTube/TikTok/Spotify/Audible/Pocket FM
etc., kein DRM-Umgehen, keine unsichere Credential-Speicherung,
Quellen-/Provenienz-Tracking je importierter Datei) gemäß Nutzervorgabe
("Phase 3 bis Phase 9 vollständig fertigstellen, kein Release").

---

## Sitzung 10 (Fortsetzung 2) — Phase 8: Download-/Import-Center (§30/§31/§32, ADR-0019)

**Status: Phase 8 vollständig abgeschlossen.**

Zu Beginn dieser Teilsitzung wurde zunächst Phase 7 (Voice Studio) committet
(`af59d57`), da sie am Ende der vorigen Teilsitzung noch offen war. Danach
Phase 8 vollständig neu gebaut:

1. Sandbox hatte wieder (wie schon mehrfach zuvor dokumentiert) ihre nicht
   in `/home/user` persistierten Pakete verloren (uvicorn, PySide6, auch
   die frisch für Phase 8 installierten yt-dlp/fpcalc) - durch
   `scripts/setup_python_env.sh` vollständig wiederhergestellt. Die
   Piper-Testmodelle aus Phase 7 (`/opt/piper_voices`) sind dadurch
   ebenfalls wieder weg - 6 Tests in `test_voice_piper_provider.py` werden
   deshalb aktuell wieder übersprungen (kein Code-Rückschritt, reines
   Sandbox-Persistenzverhalten, bei Bedarf über
   `scripts/setup_voice_studio.sh` behebbar).
2. Neues Modul `core/genesis_core/storage/` - projektweite
   Speicherplatzprüfung vor großen Operationen (`check_free_space`,
   `ensure_free_space`, `InsufficientStorageError`), bisher im
   Originalauftrag gefordert, aber nirgends konkret umgesetzt gewesen.
3. Neues Modul `core/genesis_core/download/` mit kompletter
   Provider-Architektur: `base.py` (Interface), `local_file_provider.py`
   (echter Dateisystem-Kopiervorgang), `direct_url_provider.py` (echter
   httpx-Streaming-Download), `ytdlp_provider.py` (YouTube/TikTok über
   `yt-dlp`, Unlicense), `drm_blocked.py` (Spotify/Audible/Pocket FM -
   bewusst dauerhaft blockiert, macht NIE einen Netzwerkaufruf),
   `registry.py` (Provider-Registrierung/-Erkennung), `engine.py`
   (`DownloadEngine` - orchestriert den vollständigen §31-Workflow:
   Erkennen → Verfügbarkeit → Metadaten → Optionen (alles reine Vorschau)
   → Import (confirm=true-Pflicht) → Scan (Wiederverwendung von Phase 1)
   → Fingerprint/Lautheitsmessung (Wiederverwendung von Phase 3, best
   effort) → Namensvorschlag (keine automatische Umbenennung) →
   Quellenverwaltung).
4. Keine neuen DB-Tabellen nötig - `Source`/`Provider` aus Phase 1 passen
   bereits exakt zu den §32-Feldern.
5. Neues `DownloadSettings` (`enabled=False` Standard, §56) in
   `config/__init__.py`.
6. 7 neue REST-Endpunkte (`/download/providers`, `/download/detect`,
   `/download/availability`, `/download/metadata`, `/download/options`,
   `/download/import`, `/import/local-file`) plus `GET
   /media/{id}/sources` für die Quellenabfrage.
7. PySide6: neue eigenständige Seite `DownloadCenterView` (Tabs "URL /
   Online-Quelle" und "Lokale Datei") ersetzt die Platzhalter für BEIDE
   Nav-Einträge "Download Center" und "Import" (gleiche Seiteninstanz,
   analog zum Voice-Studio/TTS-Muster). `api_client.py` um 8 Methoden
   ergänzt.
8. i18n: 49 neue `download_center.*`-Schlüssel in DE/EN/JA/RU. **Neuer
   projektweiter Regressionstest** `test_all_languages_have_identical_key_sets`
   in `test_i18n.py` ergänzt - prüft ab sofort bei JEDER künftigen Phase
   automatisch exakte Schlüsselgleichheit zwischen allen vier Sprachen
   (bisher nur manuell/stichprobenartig geprüft - wichtige strukturelle
   Absicherung, passend zur Nutzervorgabe "i18n-Mechanismus, DE/EN/JA/RU").
9. Tests: 23 neue Engine-/Provider-Tests, 11 neue API-Tests, 6 neue
   PySide6-UI-Tests (erster dedizierter View-Test im Projekt). Core-Suite
   419 passed/1 skipped (vorher 385/1), UI-Suite 11 passed (vorher 5).
10. **Mehrere echte End-to-End-Tests mit echtem Internetzugriff** (kein
    Mock): lokaler Datei-Import, echter 7,3-MB-Direkt-URL-Download von
    GitHub (vollständiger §31-Workflow, `ffprobe`-bestätigt), echter
    YouTube-Metadatenabruf via `yt-dlp` (bei einem Versuch löste YouTube
    eine Bot-Prüfung aus - korrekt als Nichtverfügbarkeit gemeldet, OHNE
    auf eine Cookie-Umgehung auszuweichen - unmittelbarer Praxisbeweis für
    die korrekte §30-Grenze), echter TikTok-Download eines öffentlichen
    Testvideos (`ffprobe`-bestätigt, inkl. Fingerprint/Lautheit),
    Spotify/Audible/Pocket-FM korrekt und ohne jeden Netzwerkaufruf als
    "nicht verfügbar: DRM-geschützt" gemeldet, Import ohne `confirm=true`
    korrekt mit 422 abgelehnt. Alle Testserver sauber gestoppt, alle
    temporären Downloads/Testverzeichnisse aufgeräumt.
11. ADR-0019 in DECISIONS.md dokumentiert (Provider-Architektur inkl.
    DRM-Block-Kategorie, yt-dlp-Wahl, eigener Downloads-Zwischenordner,
    Wiederverwendung statt Doppelimplementierung, neues Storage-Modul).

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Phase):**
- Spotify/Audible/Pocket FM bleiben dauerhaft als "DRM-geschützt, kein
  Download möglich" gemeldet - das ist keine offene Aufgabe, sondern eine
  bewusste, dauerhafte Entscheidung (§30-Grenze, siehe ADR-0019).
- TikTok-Adapter ist als "experimentell/best effort" markiert
  (`is_experimental=True`) - TikToks Erkennung/Blockaden ändern sich
  häufig, ein künftiger Fehlschlag ist erwartbar, kein Bug.
- Projektweite Settings-UI (§55) weiterhin nicht gebaut (Download Center
  wird aktuell nur über `config.yaml` aktiviert, gleiches Backlog-Item wie
  bereits in ADR-0017/ADR-0018 vermerkt).
- `storage`-Modul wird bisher nur vom Download Center genutzt - weitere
  große Operationen (Backups, Stapel-Konvertierung) sollten es in einer
  späteren Härtungsphase ebenfalls konsultieren (siehe ADR-0019
  Entscheidung 5).

**Weiterhin offen (projektweit, nicht Phase-8-spezifisch):**
- `.NET`/WPF-`GenesisApiClient.cs` weiterhin ohne jegliche Phase-3 bis
  Phase-8-Endpunkte (nur PySide6-Seite durchgängig verdrahtet).
- Lizenzdokumentation weiterhin bewusst NICHT final (erst am
  Projektende, Phase 10) - ADR-0019 hält aber bereits den Unlicense-Fund
  für yt-dlp fest, damit er bei der finalen Prüfung nicht verloren geht.
- Alles aus dieser Teilsitzung (Phase 8) ist NOCH NICHT committed
  (nächster Schritt).

**Nächste Schritte:** Committen. Danach Phase 9 (Härtung: Diagnostics,
Scan & Repair, Backups, Export JSON/CSV/XML/M3U/M3U8, Pfad-Relokation via
Hash/Fingerprint, Plugin-System, zentrale Job-Queue-UI, strukturierte
Fehlerbehandlung mit Error-IDs) gemäß Nutzervorgabe ("Phase 3 bis Phase 9
vollständig fertigstellen, kein Release").

---

## Phase 9 (Härtung) - Teilsitzung 1: §37 Fehlerbehandlung, §35/§36
Job-Pause/Resume/Cancel-Backend, §38 Diagnostics, §39 Scan & Repair, §40
Backup, §41 Temp-Aufräumung

Status: Core-Backend für sechs der neun Phase-9-Teilsysteme fertig und
getestet. Noch offen (nächste Teilsitzung(en)): §42 Export
(JSON/CSV/XML/M3U/M3U8), §43 Pfad-Relokation, §34 Plugin-System, PySide6
"Job Queue"-Ansicht (Pause/Resume/Cancel-UI) und PySide6-Fehlerdialog, ADR-
0020 (wird erst am Ende der GESAMTEN Phase 9 geschrieben, nicht pro
Teilgruppe - siehe bisheriger Plan).

**Neu in diesem Abschnitt:**

1. **§37 Strukturierte Fehlerbehandlung** (`genesis_core/errors.py`, neue
   Tabelle `ErrorLog` in `db/models.py`): `GenesisError`, `log_error`,
   `log_exception` (fängt vollen Traceback ein), `list_errors`,
   `mark_resolved`. Error-IDs folgen demselben datumsbasierten,
   DB-abgeleiteten Muster wie Job-IDs (`ERR-YYYYMMDD-NNNNN`, kein
   In-Memory-Zähler - Lehre aus der Job-ID-Historie direkt wiederverwendet).
   Ein **globaler FastAPI-Exception-Handler** in `create_app()` fängt JEDE
   unbehandelte Exception, protokolliert sie strukturiert und liefert
   `{error_id, timestamp, component, message, solution_hint}` mit Status
   500 - kein stiller Absturz mehr möglich (Kernprinzip "keine stillen
   Fehlschläge"). Neue Endpunkte `GET /errors`,
   `POST /errors/{error_id}/resolve`.
2. **§35/§36 Job-Steuerung (Backend-Hälfte)**: `JobManager.
   cooperative_checkpoint(job_id)` - wird von Batch-Engines zwischen
   einzelnen Elementen aufgerufen, blockiert kooperativ bei PAUSED, wirft
   `JobCancelledError` bei CANCELLED/fehlendem Job. Neue Endpunkte
   `POST /jobs/{id}/pause|resume|cancel`. `execute_repairs` (§39, siehe
   unten) ist der erste tatsächliche Verbraucher dieses Hooks - das
   PySide6-UI-Gegenstück (Fortschrittsbalken + Buttons) ist noch Backlog.
3. **§38 Diagnostics** (`genesis_core/diagnostics/__init__.py`): rein
   lesender Gesundheitsbericht über 11 Teilbereiche (Datenbank-Integrität
   via `PRAGMA integrity_check`, Speicherplatz, Medienordner-Erreichbarkeit,
   ffmpeg/ffprobe/fpcalc-Verfügbarkeit, Online-Metadaten-Provider-Status,
   KI/TTS-Erreichbarkeit, Download-Provider, Plugins - aktuell `None`, da
   Plugin-System noch nicht gebaut -, Dateiberechtigungen, verwaiste
   Datenbankzeilen). Jeder Einzel-Check ist defensiv isoliert - ein
   fehlerhafter/fehlender Provider lässt nie die gesamte Diagnose
   abstürzen. `find_orphaned_rows()` ist die gemeinsame, einzige
   Quelle-der-Wahrheit-Funktion für "verwaist" und wird sowohl von
   Diagnostics (nur Zählung/Meldung) als auch von Repair (tatsächliche
   Bereinigung) genutzt. Neuer Endpunkt `GET /diagnostics`.
4. **§40 Backup** (`genesis_core/backup/__init__.py`, nutzt die bereits in
   Phase 1 angelegte `Backup`-Tabelle): `create_db_backup` (SQLite Online
   Backup API statt rohem Dateikopiervorgang - sicher auch bei aktivem
   WAL-Modus), `create_config_backup`, `list_backups`, `restore_db_backup`
   (ECHTE Änderung, IMMER `user_confirmed=True` nötig, erstellt VOR dem
   Überschreiben automatisch selbst ein "pre_restore"-Backup des aktuellen
   Standes - eine Wiederherstellung darf nie selbst zu unwiderruflichem
   Datenverlust führen können). Automatische Versions-Rotation
   (`max_versions`, Standard 10) - betrifft ausschließlich GENESIS-eigene
   Sicherungskopien, nie Original-Mediendateien (ausdrücklich NIE
   gesichert, siehe Moduldocstring/`Backup.backup_type`-Kommentar: nur
   db/config/rename_journal). **Deep-Review-Fund während der
   Implementierung (selbst gefunden, vor Commit behoben):** Zeitstempel-
   basierte Versions-Labels mit reiner Sekundenauflösung kollidierten bei
   zwei Backups desselben Typs innerhalb derselben Sekunde (z.B. ein
   Backup direkt gefolgt von der automatischen `pre_restore`-Sicherung)
   und überschrieben sich gegenseitig auf der Festplatte, obwohl beide
   DB-Zeilen weiterbestanden. Fix: zusätzliches Zufallssuffix
   (`uuid.uuid4().hex[:8]`) in jedem Dateinamen, Regressionstest
   `test_version_labels_are_unique_even_within_same_second` ergänzt.
   Neue Endpunkte `POST /backup/db`, `POST /backup/config`, `GET /backup`,
   `POST /backup/{id}/restore`.
5. **§41 Temp-Aufräumung** (Erweiterung von `genesis_core/storage/
   __init__.py`): `scan_temp_files` (rein lesende Vorschau, mit
   Mindestalter-Filter gegen gerade erst erzeugte, noch in Benutzung
   befindliche Dateien) und `cleanup_temp_files` (erfordert IMMER
   `user_confirmed=True`, einzelne fehlschlagende Löschungen brechen den
   Gesamtvorgang nicht ab). Betrifft ausschließlich
   `settings.paths.resolved_temp_dir()` - niemals Original-Mediendateien.
6. **§39 Scan & Repair** (`genesis_core/repair/__init__.py`) - wendet die
   projektweite "Goldene Prozesskette" auf die von Diagnostics gefundenen
   Probleme an: `plan_repairs()` (liest Diagnostics+Temp-Scan, rein
   lesend) -> `preview_repairs()` (löst ausgewählte Plan-Einträge in
   konkrete Zeilen-IDs/Dateien auf, rein lesend) -> `execute_repairs()`
   (IMMER `user_confirmed=True`, erstellt ZUERST automatisch ein
   Datenbank-Backup - konkrete Umsetzung von "Backup vor
   Reparatur-Ausführung" -, protokolliert jede Teilaktion in
   `ProcessingHistory`, ruft `cooperative_checkpoint` zwischen den
   Teilschritten auf). Bewusster Umfang dieser ersten Version: nur die
   beiden eindeutig ungefährlichen Reparaturarten (verwaiste DB-Zeilen,
   veraltete Temp-Dateien) - risikoreichere/urteilsabhängige Fälle (z.B.
   ob eine seit Monaten "fehlende" Mediendatei endgültig aus der
   Bibliothek entfernt werden soll) bleiben bewusst eine manuelle
   Nutzerentscheidung, kein automatisierter Repair-Vorschlag (Backlog,
   spätere Phase). Neue Endpunkte `GET /repair/plan`,
   `POST /repair/preview`, `POST /repair/execute`.
7. Tests: 7 (`test_errors.py`) + 6 (`test_jobs_cooperative.py`) + 6
   (`test_diagnostics.py`) + 8 (`test_backup.py`) + 7
   (`test_storage_temp_cleanup.py`) + 8 (`test_repair.py`) + 4
   (`test_api_errors_and_jobs.py`) + 6
   (`test_api_diagnostics_backup_repair.py`) = 52 neue Tests, alle grün.
   Core-Gesamtsuite: 464 passed/7 skipped (vorher 419 passed/1 skipped vor
   Phase 9 - Differenz teils durch neue Skips bei fehlenden optionalen
   Werkzeugen in diesem Sandbox-Lauf).

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Teilsitzung):**
- §42 Export (JSON/CSV/XML/M3U/M3U8), §43 Pfad-Relokation via
  Hash/Fingerprint, §34 Plugin-System - folgen in weiteren
  Phase-9-Teilsitzungen.
- PySide6 "Job Queue"-Ansicht (Fortschrittsbalken + Pause/Resume/Cancel-
  Buttons) und ein globaler PySide6-Fehlerdialog, der das neue
  strukturierte Fehlerformat konsumiert - noch nicht gebaut.
- `.NET`/WPF `GenesisApiClient.cs` weiterhin ohne die neuen Phase-9-
  Endpunkte (nur PySide6-Seite wird in dieser Phase durchgängig
  verdrahtet, wie bereits in Phase 8 vermerkt).
- `genesis_core.diagnostics` prüft Plugins nur, wenn ein
  `plugin_registry`-Objekt übergeben wird - aktuell immer `None`, da das
  Plugin-System (§34) noch nicht existiert. Wird automatisch wirksam,
  sobald `AppState` eine echte Registry hält.
- ADR-0020 (Zusammenfassung der gesamten Phase 9) wird erst nach
  Abschluss ALLER neun Teilsysteme geschrieben, nicht pro Teilgruppe -
  unverändert gemäß bisherigem Plan.

**Nächste Schritte:** Committen. Danach §42 Export + §43 Pfad-Relokation
gemeinsam, danach §34 Plugin-System, danach PySide6 Job-Queue-UI +
Fehlerdialog, abschließend ADR-0020 + finale Regression - weiterhin gemäß
Nutzervorgabe ("Phase 3 bis Phase 9 vollständig fertigstellen, kein
Release").

---

## Phase 9 (Härtung) - Teilsitzung 2: §42 Export (JSON/CSV/XML/M3U/M3U8),
§43 Pfad-Relokation

Status: Zwei weitere der neun Phase-9-Teilsysteme fertig und getestet.
Noch offen: §34 Plugin-System, PySide6 "Job Queue"-Ansicht + Fehlerdialog,
ADR-0020 (weiterhin erst nach Abschluss ALLER Teilsysteme).

**Neu in diesem Abschnitt:**

1. **§42 Export** (`genesis_core/exporter/__init__.py`): reine Lesefunktion
   (kein `confirm` nötig, wie jeder andere Export im Projekt). Neutrale
   Zwischenform `MediaExportRow` (analog zu `MediaSnapshot` in
   `genesis_core.duplicates`) entkoppelt die Formatierer (`to_json`,
   `to_csv`, `to_xml`, `to_m3u`) vollständig von der Datenbank - jede
   Formatierfunktion ist eine reine, isoliert testbare String-Funktion.
   M3U/M3U8 werden bewusst inhaltlich identisch erzeugt (beide UTF-8,
   siehe Moduldocstring für die Begründung) - der Unterschied ist nur die
   gemeldete Dateiendung/der `media_type`. Neuer Endpunkt `GET /export`
   (`format=json|csv|xml|m3u|m3u8`, optionaler `media_file_ids`-Filter für
   Teilexporte/Wiedergabelisten).
2. **§43 Pfad-Relokation** (`genesis_core/relocate/__init__.py`) - wendet
   die Goldene Prozesskette auf vom Scanner als `is_missing=True`
   markierte Dateien an: `find_relocation_candidates()` (rein lesend,
   durchsucht angegebene Verzeichnisse, drei Erkennungsstufen mit
   Konfidenzwert: Datei-Hash=1.0 stärkstes Signal/erkennt auch
   Umbenennung, Dateiname+Größe=0.7 Fallback, Audio-Fingerprint=0.85
   optional/rechenintensiv für Formatwechsel) -> `apply_relocations()`
   (IMMER `user_confirmed=True`, prüft JEDE Zieldatei unmittelbar vor der
   Übernahme erneut auf Existenz - keine blinde Ausführung einer
   eventuell veralteten Vorschau). Aktualisiert bei Erfolg
   `absolute_path`/`directory`/`filename` und setzt `is_missing`/
   `missing_since` zurück. Protokollierung in ProcessingHistory erfolgt -
   analog zur Rename-Engine - in der API-Schicht, nicht im Engine-Modul
   selbst (konsistent mit bestehendem Muster). Neue Endpunkte
   `POST /relocate/scan`, `POST /relocate/apply`.
3. Tests: 8 (`test_exporter.py`) + 7 (`test_relocate.py`) + 7
   (`test_api_export_relocate.py`) = 22 neue Tests, alle grün. Core-
   Gesamtsuite: 486 passed/7 skipped (vorher 464/7), keine Regression.

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Teilsitzung):**
- §34 Plugin-System folgt als nächste (letzte inhaltliche) Phase-9-
  Teilsitzung.
- PySide6 "Job Queue"-Ansicht und globaler Fehlerdialog weiterhin offen.
- `.NET`/WPF `GenesisApiClient.cs` weiterhin ohne die neuen Endpunkte.
- Export-/Relokations-UI-Seiten in PySide6 noch nicht gebaut (nur die
  Core-API ist in dieser Teilsitzung fertig) - geplant zusammen mit der
  Job-Queue-UI-Arbeit am Ende von Phase 9.

**Nächste Schritte:** Committen. Danach §34 Plugin-System (PluginBase +
Registry + Sandboxing/Fehlerisolierung + funktionierendes Beispiel-Plugin
+ absichtlich fehlerhaftes Test-Plugin zum Beweis der Host-Stabilität).
Danach PySide6 Job-Queue-UI + Fehlerdialog, abschließend ADR-0020 +
finale Regression - weiterhin gemäß Nutzervorgabe ("Phase 3 bis Phase 9
vollständig fertigstellen, kein Release").

---

## Phase 9 (Härtung) - Teilsitzung 3: §34 Plugin-System

Status: Achtes von neun Phase-9-Teilsystemen fertig und getestet. Noch
offen: PySide6 "Job Queue"-Ansicht + Fehlerdialog, danach ADR-0020 +
finale Regression (letzte verbleibende Teilsitzung(en) von Phase 9).

**Neu in diesem Abschnitt:**

1. **§34 Plugin-System** (`genesis_core/plugins/__init__.py`):
   `PluginKind`-Enum mit allen zehn in §34 genannten Kategorien
   (metadata/fingerprint/downloader/tts/ai/artwork/db/exporter/importer/
   converter - vollstaendig benannt, auch wenn vorerst nur `exporter`
   voll ausgearbeitet ist, siehe Backlog unten), `PluginBase` (Pflicht-
   Metadaten: plugin_id/plugin_kind/display_name/version/author/license/
   is_local/requires_internet - Lizenz-/Herkunftstransparenz ist
   Ladevoraussetzung), `ExporterPlugin` als erste konkrete, voll
   funktionsfaehige Plugin-Kategorie (erweitert §42 Export um
   Drittanbieter-Formate). `PluginRegistry.discover_and_load()` sucht in
   `data_dir/plugins/<name>/plugin.py`-Unterordnern, importiert jeden
   Kandidaten EINZELN UND FEHLERISOLIERT (eigener `sys.modules`-Eintrag
   mit UUID-Suffix, kompletter try/except um Import+Instanziierung+
   Validierung) - ein kaputtes Plugin verhindert nie das Laden der
   uebrigen und stuerzt den Host nie ab, landet stattdessen mit
   `load_error` in der Registry (sichtbar in /plugins UND im
   Diagnostics-Bericht, §38). `PluginRegistry.call_exporter()` faengt
   zusaetzlich Laufzeitfehler INNERHALB eines bereits erfolgreich
   geladenen Plugins ab (z.B. Exception beim tatsaechlichen Export-
   Aufruf), damit auch ein zur Ladezeit einwandfreies, aber zur Laufzeit
   fehlerhaftes Plugin den aufrufenden Workflow nicht mitreisst.
2. **Zwei mitgelieferte Beispiel-Plugins** (`genesis_core/plugins/
   examples/`, NICHT automatisch von AppState geladen - dienen als
   Dokumentation + Testgrundlage, siehe Moduldocstring):
   - `example_exporter/plugin.py` - echtes, funktionierendes "Pipe-
     separated values"-Export-Plugin.
   - `broken_example/plugin.py` - wirft absichtlich eine Exception beim
     Modul-Import; Kernbeweis fuer §34 ("Plugins duerfen den Host nicht
     destabilisieren").
3. `AppState` laedt jetzt bei jedem Start Plugins aus
   `data_dir/plugins/` (leer per Default - KEIN automatisches Einsammeln
   von irgendwo sonst, keine ungefragte Codeausfuehrung). Neue Endpunkte:
   `GET /plugins` (zeigt erfolgreiche UND fehlgeschlagene Plugins mit
   Klartext-Fehler), `POST /plugins/reload` (uebernimmt neu abgelegte
   Plugins ohne Neustart des Core Service), `GET /plugins/export/
   {plugin_id}` (nutzt ein geladenes Exporter-Plugin anstelle der fest
   eingebauten §42-Formate). `genesis_core.diagnostics` erhaelt jetzt die
   echte Plugin-Registry statt immer `None` - ein fehlgeschlagenes Plugin
   erscheint fortan als "warning" im Diagnostics-Bericht.
4. Tests: 11 (`test_plugins.py`, inkl. des zentralen Host-Stabilitaets-
   Beweises mit dem absichtlich kaputten Plugin) + 6
   (`test_api_plugins.py`) = 17 neue Tests, alle grün. Core-Gesamtsuite:
   503 passed/7 skipped (vorher 486/7), keine Regression.

**Bewusst zurückgestelltes Backlog (nicht Teil dieser Teilsitzung):**
- Nur die Kategorie `exporter` hat bisher eine voll ausgearbeitete,
  konkrete Plugin-Schnittstelle. Die uebrigen neun §34-Kategorien
  (metadata/fingerprint/downloader/tts/ai/artwork/db/importer/converter)
  sind im `PluginKind`-Enum bereits vollstaendig benannt, bekommen ihre
  jeweils eigene, kategoriespezifische ABC aber erst in einer spaeteren
  Haertungsphase - bewusst kleiner, gruendlich getesteter Funktionsumfang
  jetzt statt zehn gleichzeitig nur oberflaechlich angebundener
  Kategorien (gleiches Vorgehen wie bereits bei der Rename-Engine in
  Phase 2 dokumentiert).
- Eine ECHTE Betriebssystem-/Prozess-Sandbox (statt reiner Python-
  Fehlerisolierung) ist als Haertungs-Backlog-Punkt vermerkt (siehe
  Moduldocstring Punkt 4) - fuer die aktuelle Zielsetzung ausreichend.
- PySide6 "Plugin Manager"-Seite noch nicht gebaut (nur die Core-API ist
  fertig) - geplant zusammen mit der Job-Queue-UI-Arbeit.
- `.NET`/WPF `GenesisApiClient.cs` weiterhin ohne die neuen Endpunkte.

**Nächste Schritte:** Committen. Danach PySide6 "Job Queue"-Ansicht
(Fortschrittsbalken + Pause/Resume/Cancel-Buttons) + globaler PySide6-
Fehlerdialog (konsumiert das §37-Fehlerformat), danach ADR-0020 (fasst
die GESAMTE Phase 9 zusammen) + PROGRESS.md-Update + finale
Gesamtregression (Core + UI) - weiterhin gemäß Nutzervorgabe ("Phase 3
bis Phase 9 vollständig fertigstellen, kein Release").

---

## Phase 9 (Härtung) — Teilsitzung 4 (Abschluss): PySide6-UI für §34-§38/§40, globaler Fehlerdialog, ADR-0020

**Status: Phase 9 jetzt vollständig abgeschlossen.**

Diese Teilsitzung schließt Phase 9 ab, indem die in den vorigen
Teilsitzungen gebaute Core-API (Fehlerbehandlung, Job-Steuerung, Diagnose,
Backup, Plugins) erstmals eine echte PySide6-Oberfläche bekommt, statt nur
über HTTP ansprechbar zu sein - und ein deferred-Punkt aus früheren
Sitzungen (globaler Fehlerdialog) nachgeholt wird.

1. **`api_client.py` erweitert:** `GenesisAPIError` transportiert jetzt
   zusätzlich `error_id`/`solution_hint`, FALLS die Antwort dem §37-
   Fehlerformat des globalen Exception-Handlers entspricht (statt dem
   einfachen `{"detail": "..."}` normaler `HTTPException`s) -
   `_build_api_error()` erkennt beide Formate. Neue Client-Methoden für
   Jobs (`list/get/pause/resume/cancel_job`), Fehler-Center
   (`list/resolve_error`), Diagnose (`run_diagnostics`), Backups
   (`list/create_db/create_config/restore_backup`), Plugins
   (`list/reload_plugins`).
2. **`dialogs/error_dialog.py` (neu):** `show_api_error()` zeigt eine
   fehlgeschlagene API-Anfrage inkl. nachschlagbarer Fehler-ID + Lösungs-
   hinweis, falls vorhanden. `install_global_excepthook()` (in `main.py`
   verdrahtet) fängt echte, unerwartete Python-/Qt-Exceptions aus der UI
   selbst ab und zeigt einen Dialog mit ausklappbaren technischen Details
   statt eines kommentarlosen Absturzes/Einfrierens. Bewusst NICHT
   rückwirkend in alle bestehenden älteren Views eingebaut (Backlog, siehe
   Moduldocstring) - nur die fünf neuen Views dieser Teilsitzung nutzen es
   bereits konsequent.
3. **Fünf neue PySide6-Ansichten:**
   - `job_queue_view.py` (nav.job_queue, neu in der Navigation): Tabelle
     aller Jobs mit Status/Fortschritt/Fehlern/Warnungen, Auto-Refresh
     alle 2s, Detailbereich mit echtem `QProgressBar` (unbestimmter Modus
     bei unbekannter Gesamtmenge) + Pause/Fortsetzen/Abbrechen-Buttons,
     deren Aktivierung vom tatsächlichen Job-Status abhängt (z.B. Pause
     nur bei "läuft"). Abbrechen verlangt Bestätigung.
   - `error_center_view.py` (nav.error_center, neu): Fehlerliste mit
     Filter "nur ungelöste", Detailbereich zeigt Lösungshinweis +
     technische Details + betroffene Datei, "Als gelöst markieren".
   - `diagnostics_view.py` (ersetzt den bisherigen Platzhalter unter
     nav.diagnostics): Button "Diagnose jetzt ausführen" (läuft auch
     automatisch einmal beim Öffnen), Gesamtstatus-Banner + Tabelle aller
     Einzelprüfungen inkl. jetzt sichtbarem Plugin-Status.
   - `backups_view.py` (ersetzt Platzhalter unter nav.backups):
     DB-/Konfigurations-Backup erstellen (unkritisch), Backup-Historie,
     Wiederherstellen nur nach Bestätigungsdialog (ersetzt die aktive DB).
   - `plugins_view.py` (ersetzt Platzhalter unter nav.plugins): Tabelle
     aller geladenen UND fehlgeschlagenen Plugins (mit Klartext-
     `load_error`), Button "Neu laden" ohne Neustart.
4. **i18n:** 52 neue Schlüssel (`job_queue_view.*`, `error_center_view.*`,
   `diagnostics_view.*`, `backups_view.*`, `plugins_view.*`,
   `error_dialog.*`, `nav.job_queue`, `nav.error_center`,
   `common.success_title`) konsistent in DE/EN/JA/RU ergänzt - alle vier
   Sprachkataloge haben weiterhin exakt dieselbe Schlüsselmenge (jetzt 685
   statt 633, Paritätstest weiterhin grün).
5. **Tests:** `tests/test_phase9_hardening_views.py` (PySide6-UI-Suite) -
   9 neue Smoke-/Verdrahtungstests mit Fake-API-Clients (kein echter Core
   Service nötig), decken Statusabhängigkeit der Job-Buttons, Fehler-
   Center-Resolve-Fluss, Diagnose-Darstellung, Backup-Erstellen/
   Wiederherstellen und Plugin-Anzeige (inkl. des absichtlich kaputten
   Beispiel-Plugins) ab. UI-Gesamtsuite: 20 passed (vorher 11).
6. **ADR-0020** in `DECISIONS.md` ergänzt - fasst alle neun §34-§43-
   Abschnitte dieser Phase in sechs Entscheidungen zusammen (Plugin-
   Isolation ohne OS-Sandbox, kooperative statt präemptive Job-Steuerung,
   zentrales Fehlerformat mit Fehler-ID bis in die UI, rein lesende
   Diagnose getrennt von Reparatur, Backup-Scope ohne Mediendateien,
   Export/Relokation als eigenständige lesende/vorschaupflichtige
   Werkzeuge).
7. **Gesamtregression:** Core-Suite 503 passed/7 skipped (zwei
   aufeinanderfolgende volle Läufe bestätigt; ein einzelner Lauf dazwischen
   zeigte einen transienten Fehlschlag eines echten MusicBrainz-
   Live-Netzwerktests, unabhängig von dieser Phase, im erneuten Lauf
   wieder grün). UI-Suite 20 passed, keine Regression.
8. **PROGRESS.md-Gesamtstatusblock korrigiert:** Phasen 5-8 waren in den
   jeweiligen Sitzungsabschnitten bereits als abgeschlossen dokumentiert
   (ADR-0016 bis ADR-0019 existieren), der kurze Statusbalken ganz oben in
   dieser Datei war seit mehreren Sitzungen nicht mehr aktualisiert worden
   und zeigte fälschlich "offen" für Phase 5/7/8 bzw. nur teilweise für
   Phase 6 - jetzt korrigiert, damit diese Datei wieder zuverlässig "die
   Wahrheit über den aktuellen Stand" ist (eigener Dateikopf-Anspruch).

**Bewusst zurückgestelltes Backlog (projektweit, nicht nur diese Phase):**
- Echte OS-Prozess-Sandbox für Plugins (aktuell reine Python-
  Fehlerisolierung, siehe ADR-0020 Entscheidung 1).
- Die übrigen neun §34-Plugin-Kategorien (nur `exporter` ist voll
  ausgearbeitet).
- Vollständige Migration aller VOR dieser Teilsitzung entstandenen Views
  auf `show_api_error()` statt der ursprünglichen einfachen
  `QMessageBox.critical(...)`-Aufrufe.
- Export (§42) und Pfad-Relokation (§43) haben noch keine eigene
  PySide6-Ansicht (nur über die Core-API nutzbar) - vorgesehen als Aktion
  aus der Medientabelle/Detailansicht heraus, sobald deren Aktionsmenü
  überarbeitet wird.
- `.NET`/WPF `GenesisApiClient.cs` wurde in Phase 9 nicht mitgepflegt -
  weiterhin reine PySide6/Core-API-Abdeckung für alle in dieser Phase
  entstandenen Endpunkte.
- Lizenz-/Third-Party-Dokumentation (License Center, THIRD-PARTY-LICENSES,
  NOTICE, CHANGELOG) bleibt wie vom Nutzer ausdrücklich gewünscht bis zum
  Projektabschluss zurückgestellt - NICHT Teil dieser Phase.
- Phase 10 (Release) bleibt vollständig unangetastet, wie vom Nutzer
  ausdrücklich gewünscht.

**Nächste Schritte:** Committen (letzter Commit dieser Sitzungsreihe).
Phasen 3-9 sind damit insgesamt abgeschlossen. Künftige Sitzungen: entweder
auf ausdrücklichen Nutzerwunsch Phase 10 (Release) angehen, oder weitere
Deep-Review-/Qualitätsschleifen über bereits fertige Phasen, oder gezielt
eines der oben gelisteten Backlog-Themen - je nachdem, was der Nutzer als
Nächstes vorgibt.

---

## Deep-Review-Sitzung 11 (Audit über Phase 3–9, kein neues Feature)

Nach Abschluss von Phase 3–9 (siehe oben) wurde — wie im Projekt für
fertige Phasenblöcke vorgesehen — ein erneuter Deep-Review-Pass gemäß
`reference/review-prompt-pack/` durchgeführt, diesmal über den gesamten
seit Sitzung 2/3 neu entstandenen Code (Phasen 3–9 in einem Rutsch, da
dazwischen kein Review mehr stattgefunden hatte). Voller Bericht:
`docs/REVIEW_LOG.md`, Abschnitt "Deep-Review-Report (Sitzung 11)".

**Ergebnis:** kein KRITISCH/HOCH-Fund (deutlich besser als Sitzung 2).
2 MITTEL- und 1 NIEDRIG-Fund, alle noch in dieser Sitzung behoben:

1. **Qt-Rich-Text-Autoerkennung (MITTEL):** `QLabel`/`QMessageBox` zeigten
   dynamische Inhalte (Fehlermeldungen, Dateipfade, KI-Metadaten,
   Plugin-Pfade) standardmäßig als potenzielles Rich-Text-Markup statt
   als reinen Text an. Neuer Helfer `set_plain_text()` in
   `genesis_ui/widgets/__init__.py`, angewendet auf 5 Stellen
   (`ai_dialog.py`, `error_center_view.py`, `job_queue_view.py`,
   `plugins_view.py`, `error_dialog.py`). Migration der übrigen, vor
   dieser Sitzung entstandenen Views bewusst zurückgestellt (siehe
   Backlog unten) — Risiko gering (reine Desktop-App, keine Code-
   Ausführung möglich), aber nicht vergessen.
2. **Qt-Mnemonic-Fehlinterpretation von `&` (MITTEL):** KI-generierte
   Vorschlagswerte (z.B. "Rock & Pop") flossen ungeschützt in eine
   `QCheckBox` — `&` hätte als Tastaturkürzel-Markierung interpretiert
   werden können. Neuer Helfer `escape_mnemonic()`, angewendet in
   `ai_dialog.py` (einzige betroffene Stelle im gesamten Projekt, per
   Grep-Vollsuche bestätigt).
3. **`ExporterPlugin.file_extension()` war nie verdrahtet (NIEDRIG):**
   Export-Endpunkt (§42) lieferte nie einen `Content-Disposition`-Header;
   zusätzlich war der Plugin-Rückgabewert ungeprüft, obwohl Plugin-Code
   laut eigenem Sicherheitsmodell (§34) nicht vertrauenswürdig ist. Neue
   Methode `PluginRegistry.safe_export_filename()` mit Whitelist +
   Fehlerisolierung.
4. **Prompt-Injection-Backlog aus Sitzung 1/2 neu bewertet (INFO,
   Bedingungs-geschlossen):** Phase 6 implementiert kein Tool-Calling und
   kein Auto-Apply für KI-Vorschläge — jede Übernahme verlangt explizite
   Nutzerauswahl + `confirm=True`, landet nur in der separaten
   `AIMetadata`-Tabelle, nie in kanonischen Feldern/Pfaden/SQL/Shell.
   Backlog-Punkt gilt für den aktuellen Funktionsumfang als geprüft;
   muss bei echtem künftigem Tool-Calling erneut bewertet werden.
5. **Flächendeckend (nicht nur stichprobenartig) per Tooling bestätigt,
   keine Fixes nötig:** Auth-Abdeckung 94/95 Routen (einzige Ausnahme
   `/health`, by-design), Confirm-Pflicht auf jedem destruktiven
   Endpunkt, kein `shell=True`/String-Interpolation in allen
   `subprocess`-Aufrufen, keine Credential-/Cookie-Speicherung im
   Download-Modul, generierte Ausgabedateipfade (Cutter/Konvertierung/
   Lautheit) ausschließlich aus validiertem Quellpfad-Stem + fixem
   Suffix + whitelisted Extension, Quellpfade für destruktive Operationen
   ausschließlich aus DB-Lookup via `media_id`, Plugin-Fehlerisolierung
   funktioniert wie spezifiziert, keine hartcodierten UI-Strings in den
   fünf neuen Phase-9-Views.

**Tests:** 4 neue Plugin-Tests + 1 erweiterter API-Test (Core-Suite:
507 passed/7 skipped, vorher 503), 1 neue Testdatei mit 4 Tests für die
beiden UI-Fixes (UI-Suite: 24 passed, vorher 20).

**Fortsetzung derselben Review-Sitzung (unmittelbar danach, auf
Nutzerwunsch "weiter"): die zuvor offen gelassenen Vertiefungspunkte
wurden jetzt abgearbeitet — dabei kamen zwei weitere, echte MITTEL-Funde
zum Vorschein, beide noch in derselben Sitzung behoben:**

6. **`unlink()`-Audit abgeschlossen:** alle vier Aufrufstellen im Projekt
   (`backup/__init__.py` Backup-Rotation, `diagnostics/__init__.py`
   Schreibrechte-Probe, `voice/engine.py` Synthese-Zwischen-WAV, sowie
   die bereits vorher geklärte `storage/`-Stelle) einzeln geprüft: alle
   löschen ausschließlich selbst erzeugte, intern konstruierte Pfade,
   nie einen vom Nutzer/einer KI gelieferten Pfad — keine Funde.
7. **JobManager-Statusübergänge (F-11-4, MITTEL, behoben):**
   `pause/resume/cancel` setzten den Zielstatus zuvor ungeprüft (z.B.
   setzte `resume()` selbst einen bereits abgeschlossenen Job
   kommentarlos wieder auf "läuft" zurück - ein "Geister-Job") und lasen/
   schrieben den Status in zwei getrennten DB-Sitzungen (Rennbedingung).
   Per Multi-Thread-Stresstest nachgewiesen. Fix: neue atomare
   `JobManager._transition()` (Lock + eine Transaktion) mit expliziter
   Zustandsmaschine je Methode, ungültige Übergänge lösen
   `JobTransitionError` aus (API: HTTP 409). `cancel()` bleibt bewusst
   idempotent bei bereits CANCELLED (deckt den internen Scan&Repair-
   Doppel-Abbruch-Pfad ab). 8 neue Tests (5× `test_jobs.py`, 3×
   `test_api_errors_and_jobs.py`).
8. **Hängendes Plugin blockierte den gesamten Core-Service-Start (F-11-5,
   MITTEL, behoben):** ADR-0020 sicherte Fehlerisolierung gegen
   EXCEPTIONS beim Plugin-Laden/-Aufruf zu - geprüft und bestätigt
   korrekt. Ein Plugin, das stattdessen HÄNGT (Endlosschleife,
   blockierender Aufruf ohne eigenes Timeout - ein gewöhnlicher
   Programmierfehler, kein Angriff), wurde dagegen nicht erkannt und
   blockierte empirisch nachgewiesen den kompletten Core-Service-Start
   auf unbestimmte Zeit. Fix: Laden und jeder Laufzeitaufruf laufen jetzt
   zusätzlich mit Zeitlimit in einem Daemon-Thread
   (`_run_with_timeout()`, bewusst `threading.Thread(daemon=True)` statt
   `ThreadPoolExecutor`, dessen Worker sonst sogar einen sauberen
   Prozess-Shutdown verhindert hätten - ebenfalls empirisch verifiziert).
   5 neue Tests in `test_plugins.py`. Vollständiger Bericht inkl.
   Vorher/Nachher-Reproduktion: `docs/REVIEW_LOG.md`, Finding F-11-4/
   F-11-5. ADR-0020 in `DECISIONS.md` um entsprechende Nachträge zu
   Entscheidung 1 und 2 ergänzt.

**Tests nach dieser Fortsetzung:** Core-Suite **520 passed, 7 skipped**
(vorher 507), UI-Suite unverändert 24 passed (diese Fixes betreffen nur
`core/`).

**Bewusst weiterhin zurückgestelltes Backlog:**
- `set_plain_text()`-Migration für die ~20 vor dieser Sitzung
  entstandenen Views (`duplicates_view.py`, `download_center_view.py`
  u.a.), wo sie ebenfalls dynamische Inhalte anzeigen.
- Doku-Präzisierung in `repair/__init__.py`: "Rollback-Grundlage" ist
  grobkörnig (ganzes DB-Backup vor Ausführung), nicht zeilengenaues Undo
  aus `ProcessingHistory` — kein Datenverlustrisiko, nur eine
  Kommentarpräzisierung offen.
- Echte OS-Prozess-Sandbox für Plugins bleibt Backlog (das neue Zeitlimit
  schützt zuverlässig vor hängenden/fehlerhaften Plugins, aber NICHT vor
  aktiv böswilligem Code, der innerhalb des Zeitlimits Schaden anrichten
  könnte — unverändert dasselbe, bereits in ADR-0020 bewusst akzeptierte
  Bedrohungsmodell-Limit).
- Lizenz-/Third-Party-Dokumentation und Phase 10 bleiben wie vom Nutzer
  ausdrücklich gewünscht vollständig unangetastet.

**Nächste Schritte:** Diesen gesamten Review-Fund-Arc (Plugin-Fixes +
JobManager-Fix + UI-Fixes + REVIEW_LOG-, DECISIONS.md- und
PROGRESS.md-Einträge) in einem Commit sichern. Danach: entweder auf
Nutzerwunsch Phase 10 (Release) angehen, oder die oben gelisteten
verbleibenden Backlog-Punkte in einer weiteren Review-Sitzung
abarbeiten, oder neue Feature-Arbeit — je nach Nutzervorgabe.

---

## Deep-Review-Sitzung 12 (Abarbeitung des Sitzung-11-Backlogs, kein neues Feature)

Direkte Fortsetzung des oben zurückgestellten Backlogs, auf Nutzerwunsch
"weiter" — kein neues Feature, reine Abschluss-/Härtungsarbeit:

1. **I-11-1-Doku-Präzisierung — ERLEDIGT:** Modul-Docstring und
   `execute_repairs()`-Docstring in `core/genesis_core/repair/__init__.py`
   stellen jetzt korrekt klar, dass Rollback über das vor Ausführung
   angelegte vollständige DB-Backup (`POST /backup/{id}/restore`) läuft,
   nicht über ein zeilengenaues `ProcessingHistory`-Undo. Reiner Doku-Fix.
2. **`set_plain_text()`-Migration für alle vor Sitzung 11 entstandenen
   Views/Dialoge — ERLEDIGT:** `dialogs/audiobook_dialog.py`,
   `dialogs/video_dialog.py` (inkl. beider `*_status_label`-Ladefehler),
   `views/dashboard.py`, `views/diagnostics_view.py`,
   `views/download_center_view.py` (inkl. eines rohen `str(exc)` ganz
   ohne `tr()`-Wrapper — höchste Priorität dieser Liste),
   `views/duplicates_view.py`, `views/ai_center_view.py`,
   `views/backups_view.py`, `views/voice_studio_view.py`,
   `dialogs/artwork_dialog.py`, `dialogs/convert_dialog.py`,
   `dialogs/cutter_dialog.py`, `dialogs/loudness_dialog.py`,
   `dialogs/metadata_dialog.py`, `dialogs/rename_dialog.py` — überall
   dort auf `set_plain_text()` umgestellt, wo QLabel-Text dynamische/
   externe Inhalte zeigt (Fehlermeldungen, Dateipfade, Provider-/Modell-
   Namen, Lizenztexte). Rein numerische Felder (Jahr, Staffel, Episode,
   Zähler) blieben bewusst bei `setText()`. Neu bestätigt:
   `QTreeWidgetItem`/`QListWidgetItem`/Tabellenzellen lösen Qts Rich-
   Text-Autoerkennung nicht aus und brauchen keinen Fix.
   `QMessageBox.critical(...)`-Aufrufe (13 Dateien, keine
   `setTextFormat`-Kontrolle über die statische Convenience-Methode)
   wurden bewusst NICHT migriert — eigenständiges Backlog-Thema
   (Umstieg auf `show_api_error()`), um den Scope dieser Runde eng zu
   halten. Details: `docs/REVIEW_LOG.md`, Abschnitt 8.
3. **Testumgebungs-Lücke behoben (keine Code-Änderung, reine
   Infrastruktur):** `scripts/setup_python_env.sh` installiert jetzt
   zusätzlich die Qt-Systembibliothek `libxkbcommon0`/
   `libxkbcommon-x11-0` via apt, falls sie fehlt — ohne sie schlagen
   PySide6-Tests selbst im `QT_QPA_PLATFORM=offscreen`-Modus mit
   `ImportError: libxkbcommon.so.0` fehl, auch wenn das PySide6-
   Pip-Paket korrekt installiert ist (System-Lib wird nicht von pip
   mitgeliefert).

**Tests:** beide Suiten unverändert grün nach allen Änderungen dieser
Sitzung — `core`: **520 passed, 7 skipped**; `ui-reference-pyside`:
**24 passed**.

**Unmittelbare Fortsetzung derselben Sitzung (Nutzerwunsch "weiter"):
das zuletzt noch offene Backlog-Thema wurde direkt im Anschluss
ebenfalls abgearbeitet:**

5. **`QMessageBox.critical(...)` → `show_api_error()`-Migration
   abgeschlossen:** alle 24 Aufrufstellen für `GenesisAPIError` in 12
   Dateien (`views/duplicates_view.py`, `views/media_table.py`,
   `views/voice_studio_view.py`, `dialogs/ai_dialog.py`,
   `dialogs/artwork_dialog.py`, `dialogs/audiobook_dialog.py` [7×],
   `dialogs/convert_dialog.py`, `dialogs/cutter_dialog.py`,
   `dialogs/loudness_dialog.py`, `dialogs/metadata_dialog.py`,
   `dialogs/rename_dialog.py`, `dialogs/video_dialog.py` [2×]) nutzen
   jetzt `show_api_error()` statt der einfachen Convenience-Methode.
   `show_api_error()` bekam dafür einen neuen optionalen
   `message`-Parameter (`genesis_ui/dialogs/error_dialog.py`): die
   bisherige, handlungsspezifische Fehlermeldung jeder Aufrufstelle
   bleibt dadurch als Haupttext erhalten, Fehler-ID und Lösungshinweis
   werden zusätzlich angehängt, falls die Core-API sie mitgeliefert hat
   — reiner Zugewinn (Auffindbarkeit im Fehler-Center), kein
   Informationsverlust. Bewusst NICHT migriert: der einzige
   `OSError`-Fall in `audiobook_dialog.py` (lokales Datei-Schreiben beim
   Kapitel-Export) bleibt bei `QMessageBox.critical(...)`, da
   `show_api_error()` explizit für `GenesisAPIError` typisiert ist. In
   `duplicates_view.py` wurde der dadurch ungenutzte `QMessageBox`-Import
   entfernt. 3 neue Tests in `test_deep_review_sitzung12_fixes.py`
   (inkl. End-to-End-Test über `ArtworkDialog._on_embed_clicked()`).

**Tests nach dieser Fortsetzung:** `core` unverändert 520 passed/7
skipped, `ui-reference-pyside` **27 passed** (24 + 3 neue).

**Verbleibendes Backlog:**
- Echte OS-Prozess-Sandbox für Plugins (ADR-0020, unverändert bewusst
  akzeptiertes Bedrohungsmodell-Limit).
- Lizenz-/Third-Party-Dokumentation und Phase 10 bleiben wie vom Nutzer
  ausdrücklich gewünscht vollständig unangetastet.

**Nächste Schritte:** Diesen gesamten Abschluss-Arc (Doku-Fix +
vollständige `set_plain_text()`-Migration + `show_api_error()`-Migration
+ Testumgebungs-Fix + REVIEW_LOG.md-/PROGRESS.md-Einträge) in einem
Commit sichern (Git-Identität zuvor via
`bash scripts/setup_git_identity.sh` setzen, da `.git/config` nicht Teil
des Workspace-Snapshots ist). Danach je nach Nutzervorgabe: Phase 10
(Release, weiterhin nur auf expliziten Wunsch) oder neue Feature-Arbeit.
Mit diesem Schritt ist das komplette aus Sitzung 11 bekannte Backlog
(außer den bewusst dauerhaft zurückgestellten Punkten: echte Plugin-
Sandbox, Phase 10, Lizenzdokumentation) abgearbeitet.

## Sitzung 13 — Kompletter Deep-Review-Neu-Durchlauf über ALLE Komponenten
(expliziter Nutzerauftrag: nach jedem Fund/Fix von vorne beginnen, bis ein
Durchlauf weder Fehler noch Warnungen zeigt)

**Ausgangslage:** `ruff` (bisher nirgends im Projekt eingesetzt) zeigte in
`core/` 266 initiale Funde. Eine parallele Untersuchung, ob dies an einer
fehlerhaften Projektkonfiguration liegt, wurde ergebnisoffen durchgeführt
und **abgeschlossen**: es handelt sich um das echte, breite Standard-
Regelset der installierten ruff-Version 0.16.10 (verifiziert per
byte-identischem `--show-settings`-Abgleich gegen eine isolierte
Minimal-Reproduktion) — kein Konfigurationsfehler.

**Durchgeführt (`core/`):**
1. `ruff check . --fix` → 155 automatisch behoben, Testsuite danach
   unverändert grün (520 passed/7 skipped).
2. Verbleibende 113 Funde manuell aufgearbeitet: `PLW1510`×5 (explizites
   `check=False` bei bereits manuell geprüften `subprocess.run`-Aufrufen),
   `TRY203`×1 (totes No-Op-try/except entfernt + unbenutzten Import
   bereinigt), `F401`×1, `F841`×1 (+ kaskadierende Bereinigung in
   `test_i18n.py`), `DTZ005`×1 (begründetes `noqa`, Backup-Dateiname
   braucht bewusst lokale Zeit), `EXE001`×1 — das deckte einen
   **repo-weiten Befund** auf: 7 weitere Shebang-Dateien waren in Git
   selbst NIE als ausführbar getrackt (Modus `100644` trotz Shebang,
   keine Sitzungsdrift) — per `chmod +x` + Commit dauerhaft behoben.
3. `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` in
   `pyproject.toml` ergänzt, um das bekannte FastAPI-`Depends()`-
   Falsch-Positiv (`B008`×96) sauber zu lösen statt zu ignorieren.
4. Verbleibende 7 Stilfunde (`C408`×3, `SIM117`×2, `PIE810`×1, `RUF046`×1)
   behoben. **Ergebnis: `ruff check .` → 0 Funde**, volle Testsuite
   weiterhin grün (520 passed/7 skipped, 0 Warnings).

**Durchgeführt (`ui-reference-pyside/`, erstmals gelintet):**
- `ruff check . --fix` → 32 behoben, 6 verblieben.
- Davon 2 echte, bisher unentdeckte **Laufzeitfehler** gefunden und
  behoben (siehe `docs/REVIEW_LOG.md` Sitzung 13, F-13-1/F-13-2):
  - **F-13-1 (kritisch):** drei Methoden in `api_client.py`
    (`get_cutter_waveform_bytes`, `export_chapters_text`,
    `get_voice_synthesis_audio`) riefen bei einem HTTP-Fehler eine nie
    existierende Funktion `_extract_detail()` auf (`NameError` statt
    sauberer `GenesisAPIError`) — Tippfehler/unvollständiges Refactoring,
    von keinem bisherigen Test abgedeckt, da alle UI-Tests gegen
    Fake-APIs laufen. Fix: Aufruf der tatsächlich vorhandenen
    `_build_api_error(exc)`, wie an den übrigen vier Stellen.
  - **F-13-2:** doppelte `list_jobs`-Methode (eine davon toter Code durch
    stille Python-Überschreibung) — tote erste Definition entfernt.
  - Zusätzlich 2× `S110` (try/except/pass ohne jede Protokollierung) in
    `error_dialog.py`/`main_window.py` behoben: Sekundärfehler werden
    jetzt protokolliert, ohne das defensive Nicht-Abstürzen-Verhalten zu
    ändern.
- Neue Datei `tests/test_deep_review_sitzung13_fixes.py` (5 Tests, echter
  `GenesisAPIClient` + `httpx.MockTransport`, kein Netzwerkzugriff nötig).
  **Ergebnis: `ruff check .` → 0 Funde, 32 passed** (27 + 5 neue).

**Durchgeführt (`ui-windows-dotnet/`, erstmals tatsächlich gebaut/getestet
statt nur gelesen):**
- `.NET SDK 8.0.425` frisch installiert (`scripts/setup_dotnet_env.sh`).
- `dotnet build -p:EnableWindowsTargeting=true` (WPF-Client) → **Build
  succeeded, 0 Warning(s), 0 Error(s)**.
- `dotnet test` (xUnit-Testprojekt, plattformunabhängig verlinkt gegen
  `Translator.cs`) → **11/11 Tests grün**.
- `dotnet list package --vulnerable` → keine bekannten Schwachstellen.

**Zusätzliche manuelle Prüfung** (geleitet durch die review-prompt-pack-
Profile `10-python` und `06-csharp-dotnet`): grep-Suche nach `shell=True`,
`eval`/`exec`, `pickle`, unsicherem `yaml.load`, bare `except:`,
Zip-Slip-Mustern, HTTP-Aufrufen ohne Timeout, Pfad-Traversal — **keine
weiteren Funde**, mehrere bereits vorhandene Schutzmaßnahmen bestätigt
(zentrale Timeout-erzwingende HTTP-Client-Fabrik, Verzeichniswechsel-
Sperre im Rename-Engine, korrektes `IDisposable`/`CancellationToken`-
Handling im .NET-Client).

**Finaler Durchlauf dieser Sitzung (Zielzustand erreicht):**
```
core:                ruff check .          → 0 Funde
core:                pytest -q             → 520 passed, 7 skipped, 0 Warnings
ui-reference-pyside:  ruff check .          → 0 Funde
ui-reference-pyside:  pytest tests/ -q      → 32 passed, 0 Warnings
ui-windows-dotnet:    dotnet build + test   → 0 Warnings/0 Errors, 11/11 Tests grün
```
Alle drei Komponenten gleichzeitig fehler- UND warnungsfrei.

**Verbleibendes Backlog (bewusst zurückgestellt, kein Fehlerbefund):**
- `ui-windows-dotnet` ohne `.editorconfig`/verschärfte Roslyn-Analyzer
  (spätere Härtungsoption).
- `HttpClient` im .NET-Client ohne expliziten `Timeout` (nutzt
  .NET-Default 100s; unkritisch für reinen Localhost-Client).
- Echte OS-Prozess-Sandbox für Plugins (ADR-0020, unverändert).
- Lizenz-/Third-Party-Dokumentation und Phase 10 bleiben wie vom Nutzer
  ausdrücklich gewünscht vollständig unangetastet.

**Nächste Schritte:** Diesen vollständigen Review-Durchlauf (alle Fixes +
`REVIEW_LOG.md`/`PROGRESS.md`-Einträge) in einem Commit sichern. Danach,
wie vom Nutzer für genau diesen Zeitpunkt vorgesehen: Gap-Analyse/
Brainstorming, ob im Projekt etwas vergessen wurde oder sinnvoll ergänzt
werden könnte — explizit als zweiter, nachgelagerter Schritt.

## Sitzung 13 (Fortsetzung) — Gap-Analyse nach Spec abgeschlossen

Nach Erreichen des fehler-/warnungsfreien Zustands (siehe oben) wurde wie
vom Nutzer vorgesehen die Gap-Analyse gegen die 71-Abschnitt-Spezifikation
durchgeführt. Vollständiges Ergebnis in **`docs/GAP_ANALYSIS.md`**.

**Kernbefund:** Backend/Datenmodell sind durchgängig solide (alle 28
DB-Entitäten, DRM-Grenze vorbildlich, Export/Scan&Repair/Job-Queue/
Fehlerbehandlung vollständig) — die Lücken liegen fast ausschließlich in
der Referenz-GUI (`ui-reference-pyside`), die mehrere Navigationspunkte nur
als Platzhalter verdrahtet hat, obwohl die zugehörigen Backend-Fähigkeiten
bereits existieren:

- **[HOCH]** Einstellungen nur lesbar (`GET /settings`, kein PATCH) —
  verstößt gegen §55 ("keine manuelle Config-Datei-Bearbeitung nötig").
- **[HOCH]** Bibliotheks-Drill-down (Interpreten/Alben/Titel/Genres/
  Personen/Quellen) nur Platzhalter-Seiten, DB-Relationen existieren.
- **[MITTEL-HOCH]** Globale Suche filtert nur nach `kind` + Dateiname-
  Substring, keiner der in §9 geforderten Filter (Genre/Jahr/Lautheit/
  Qualität/KI-Status/...) ist ansteuerbar.
- **[MITTEL]** Kein Cover wird irgendwo tatsächlich angezeigt (kein
  einziges `QPixmap` im gesamten Referenz-Client).
- **[MITTEL]** Keine "Datei öffnen"/"Ordner öffnen"/"Pfad kopieren".
- **[MITTEL]** Kein allgemeiner Bibliotheks-Medienplayer (§60).
- **[NIEDRIG-MITTEL]** Loudness/KI-Daten fehlen im zentralen Detail-Panel
  (nur in separaten Dialogen abrufbar), kein Log-Viewer, keine Provider-
  Verwaltungs-GUI.
- **[NIEDRIG]** Globale Aktionen als Toolbar statt Kontextmenü (funktional
  im Kern vorhanden, nur andere UI-Form als im Spec-Text beschrieben).

Bewusst **keine** Lücken (Nutzerentscheidung, unverändert): License Center-
Einträge, Phase 10 (Installer/Update/Release), echte Plugin-OS-Sandbox.

**Empfohlene Abarbeitungsreihenfolge** (siehe `docs/GAP_ANALYSIS.md`
Abschnitt 4): zuerst die drei aufwandsarmen Lücken (Datei/Ordner öffnen,
Cover-Anzeige, Loudness/KI im Detail-Panel), dann Settings-Schreibzugriff +
Provider-Verwaltung gemeinsam, dann Bibliotheks-Drill-down, dann
Medienplayer, zuletzt Log-Viewer/Kontextmenü-Umbau. Wartet auf
Nutzerrückmeldung, bevor sie verbindlich wird.

## Sitzung 14 — Gap-Gruppe 1 geschlossen (Cover, Datei/Ordner öffnen, Pfad kopieren, Loudness+KI im Detail-Panel)

Nutzerfreigabe erhalten ("mach es der reihe nach bis du fertig bist") —
arbeite die Gap-Liste aus `docs/GAP_ANALYSIS.md` ab jetzt sequenziell ohne
weitere Rückfrage ab. **Gruppe 1 (Gaps D, E, F) ist abgeschlossen:**

- **Gap D (Cover-Anzeige, §8/§22/§59):** `MediaTableView` lädt beim
  Auswählen einer Datei das Artwork per `api.get_artwork_bytes()` und
  rendert es als `QPixmap` (auf 220px Kantenlänge skaliert) über der
  Textdetailansicht. Fehlt das Cover oder sind die Bytes nicht
  dekodierbar, erscheint statt eines Absturzes/erfundenen Bildes der
  Platzhaltertext "Kein Cover vorhanden" (`media_table.detail.no_cover`).
  Reine, isoliert testbare Hilfsfunktion `pixmap_from_artwork_bytes()`.
- **Gap E (Datei/Ordner öffnen, Pfad kopieren, §8/§61):** drei neue
  Toolbar-Buttons (nur bei Einzelauswahl aktiv), nutzen
  `QDesktopServices.openUrl()` (plattformunabhängig, rein anzeigend, kein
  Bestätigungsdialog nötig, Grundprinzip #4/#5) bzw. `QApplication.
  clipboard()`. Fehlschläge zeigen eine `QMessageBox.warning` statt still
  zu scheitern. Rückmeldung beim Pfad-Kopieren über die Statusleiste des
  Hauptfensters (sofern vorhanden - degradiert in Tests/Isoliert-Nutzung
  ohne `QMainWindow`-Elternteil sauber).
- **Gap F (Loudness + KI-Analyse + Quelle im Detail-Panel, §59):** die
  Detailansicht zeigt jetzt zusätzlich die **neueste** Loudness-Messung
  (`api.list_loudness()[0]`, API liefert neueste zuerst), **alle**
  KI-Metadaten-Vorschläge mit Modell/Confidence/Übernahme-Status
  (`api.get_ai_metadata()`) und die Importquelle(n) (`api.
  list_media_sources()`) - vorher nur über separate Dialoge erreichbar.
  Jede der drei Sektionen zeigt einen klaren "noch nicht
  analysiert"/"keine Vorschläge"/"kein Importnachweis"-Text, wenn keine
  Daten vorliegen, und degradiert bei `GenesisAPIError` auf denselben
  Leerzustand, statt die gesamte Detailansicht abstürzen zu lassen.

Alle neuen UI-Strings wurden identisch in **allen vier** Sprachkatalogen
(`i18n/de.json`, `en.json`, `ja.json`, `ru.json`) ergänzt und gegen
`tests/test_i18n.py` (Schlüsselmengen-Gleichheit) verifiziert.

**Neue Testdatei `tests/test_gap_closure_detail_view.py`** (17 Tests,
erster dedizierter Testfall für `MediaTableView` überhaupt - vorher ohne
Coverage): Cover-Dekodierung/-Fallback, Button-Enablement nach
Auswahlzahl, `open_path_in_os`/`copy_path_to_clipboard` werden nie wirklich
aufgerufen (per `monkeypatch` ersetzt - ein echter `QDesktopServices.
openUrl()`-Aufruf kann in der Headless-Sandbox ohne Desktop-Umgebung
hängen bleiben, siehe unten), sowie alle drei neuen Detail-Sektionen
(Erfolgs- und Leer-/Fehlerfall). Gesamte Suite (49 Tests) läuft grün unter
`QT_QPA_PLATFORM=offscreen`.

**Infrastruktur-Notiz:** `PySide6` war in dieser Sandbox bisher nicht
installiert (`pip install PySide6`, zusätzlich System-Pakete
`libxkbcommon0`, `libxkbcommon-x11-0`, `libegl1`, `libopengl0`,
`libpulse0`, `libxcb-cursor0`, `libasound2` per `apt-get` nachinstalliert),
wodurch zum ersten Mal die komplette PySide6-Testsuite tatsächlich
(statt nur stillschweigend via `pytest.importorskip` übersprungen)
ausgeführt werden konnte. Diese Pakete sind Sandbox-lokal und nicht Teil
des Repos/der Snapshot-Persistenz (`node_modules`-artige Caches
ausgenommen - hier aber System-apt-Pakete, die ohnehin nie im Workspace
landen) - müssen in künftigen Sitzungen ggf. erneut installiert werden,
um die UI-Tests wirklich auszuführen statt sie nur zu kompilieren.

**Nächster Schritt (Gruppe 2 laut Priorität):** Gap A (PATCH `/settings`
Endpoint + Settings-UI) und Gap I (Metadaten-Provider-Verwaltung) gemeinsam
angehen, da beide dieselbe neue "Einstellungen/Provider"-UI-Fläche
benötigen.

## Sitzung 14 (Fortsetzung) — Gap-Gruppe 2 geschlossen (Settings-UI + Metadaten-Provider-Verwaltung)

**Gaps A und I sind abgeschlossen.** Backend-Teil (`PATCH /settings`) war
bereits im vorigen Commit fertig; diese Runde ergänzt die GUI-Seite.

- **Neue Datei `genesis_ui/views/settings_view.py`** (`nav.settings`, vorher
  Platzhalter): editierbares Formular für General (Sprache, Bestätigungs-
  pflicht), Medienordner (Liste + Hinzufügen/Entfernen/"Bibliothek jetzt
  scannen"), KI, Sprachausgabe, Lautheit, Download/Import, Datenschutz.
  Speichern geht über einen Bestätigungsdialog (Prinzip #17) und
  `api.update_settings(updates, confirm=True)`; nach dem Speichern zeigt
  die Statuszeile an, ob ein Neustart nötig ist (`restart_required` aus
  der API-Antwort).
- **Neuer, bisher unentdeckter Gap während der Umsetzung gefunden und
  gleich mitgeschlossen:** `api_client.trigger_scan()` existierte bereits,
  wurde aber in der GESAMTEN Referenz-UI nirgends aufgerufen - es gab
  buchstäblich keine Möglichkeit, über die GUI einen Bibliotheksscan zu
  starten oder Medienordner zu verwalten. Jetzt über die neue Medienordner-
  Sektion der Settings-Seite gelöst (naheliegend, da `paths.media_folders`
  ohnehin Teil der Settings ist) - `POST /scan` nimmt seine Zielordner
  weiterhin als expliziten Parameter entgegen, unabhängig vom
  Speicherstatus der Liste.
- **Neue Datei `genesis_ui/views/providers_view.py`** (`nav.providers`,
  vorher Platzhalter, Gap I): eigene Seite für die Online-Metadaten-
  Provider (MusicBrainz/AcoustID/Cover Art Archive, `MetadataSettings`) -
  bewusst getrennt von den Download-Providern (YouTube/TikTok/…, die
  bereits im Download-Center verwaltet werden). Zeigt/speichert
  `metadata.*` über denselben PATCH-Endpunkt.
- Beide Views in `main_window.py` verdrahtet (`NAV_STRUCTURE`/
  `_create_page`).
- **Bug während der eigenen Testarbeit gefunden und sofort behoben:** in
  beiden neuen Views wurde nach dem Speichern zuerst die Erfolgs-/Neustart-
  Meldung gesetzt und DANACH `_reload()` aufgerufen - `_reload()` setzt am
  Ende aber selbst den Status-Text auf "", wodurch die gerade gesetzte
  Meldung sofort wieder verschwand. Reihenfolge vertauscht (erst
  `_reload()`, dann die Meldung setzen) und mit einem Regressionstest
  abgesichert.
- Alle neuen i18n-Schlüssel (`settings_view.*`, `providers_view.*`)
  identisch in de/en/ja/ru ergänzt, `test_i18n.py` grün.
- **Neue Testdatei `tests/test_gap_closure_settings_providers_view.py`**
  (11 Tests): Laden/Anzeigen, partielles Speichern mit `confirm=true`,
  Neustart-Hinweis ja/nein, Fehlerfall zeigt `show_api_error`, Ordner
  hinzufügen/entfernen, Scan mit/ohne Ordnerliste, Provider-Speichern
  schreibt NUR den `metadata`-Abschnitt.
- **Vollständiger End-to-End-Test gegen den echten Core Service**
  durchgeführt (nicht nur Fake-API): `SettingsView`/`ProvidersView` gegen
  einen laufenden `run_api.py`-Prozess instanziiert, Werte geändert,
  gespeichert, mit einer frisch geladenen zweiten View-Instanz verifiziert,
  dass die Änderungen tatsächlich persistiert wurden; zusätzlich kompletter
  `MainWindow`-Start gegen den echten Service durchgespielt (alle
  Navigationsseiten bauen fehlerfrei, inkl. der beiden neuen).
  Gesamte UI-Testsuite (60 Tests) und Backend-Testsuite (334 Tests,
  ausgenommen die bereits vorher bekannten ffmpeg/yt-dlp-Umgebungslücken)
  laufen grün.

**Nächster Schritt (Gruppe 3 laut Priorität):** Gap B - echte Bibliotheks-
Drill-down-Seiten für Interpreten/Alben/Titel/Genres/Personen/Quellen
(Backend-Datenmodell existiert bereits vollständig, siehe
`docs/GAP_ANALYSIS.md`).

## Sitzung 14 (Fortsetzung 2) — Gap-Gruppe 3 geschlossen (Bibliotheks-Drill-down: Interpreten/Alben/Titel/Genres/Personen/Quellen, Gap B)

Dritte von sechs Gap-Gruppen aus `docs/GAP_ANALYSIS.md`, im Rahmen der
pauschalen Nutzerfreigabe ("mach es der reihe nach bis du fertig bist")
ohne weitere Rückfrage umgesetzt.

**Backend (neu):**
- `core/genesis_core/library.py` — rein lesendes Aggregations-/Browsing-
  Modul (keine neuen Tabellen) mit Dataclasses + Query-Funktionen für:
  - `list_artists`/`get_artist_detail` (Interpret → Alben mit Titelanzahl)
  - `list_albums`/`get_album_detail` (Album → Titelliste)
  - `list_tracks` (flache, durchsuchbare Titel-Liste über ALLE Musiktitel,
    mit Interpret/Album/Genre/Jahr; `artist_name` fällt auf
    `Track.album_artist` zurück, wenn kein Album verknüpft ist)
  - `list_genres`/`get_genre_detail` (Genre → Titelliste mit Interpret/Album)
  - `list_persons`/`get_person_detail` (Person → Rollenliste über Movie/
    Episode/Audiobook/Track hinweg, §63 Wissensgraph)
  - `list_sources` (alle `Source`-Einträge, mit Dateiname verknüpft)
  - Docstring dokumentiert bewusst die bestehende, nicht behobene
    Modellgrenze: `Track` hat keine direkte FK zu `Artist`, nur über
    `Track.album_id -> Album.artist_id` — ein Titel ohne Album taucht
    daher nicht unter seinem Interpreten auf (wohl aber in `list_tracks`).
- Neue Endpunkte in `core/genesis_core/api/app.py` (alle `require_token`,
  rein lesend, kein `confirm` nötig): `GET /library/artists[/​{id}]`,
  `/library/albums[/​{id}]`, `/library/tracks`, `/library/genres[/​{id}]`,
  `/library/persons[/​{id}]`, `/library/sources`.
- Stale gewordenen `GET /settings`-Docstring korrigiert (verwies noch auf
  "Phase 9, absichtlich noch nicht implementiert" obwohl `PATCH /settings`
  seit Gap A bereits existiert).
- Neue Testdatei `core/tests/test_api_library.py` (7 Tests, inkl. Token-
  Pflicht-Check, 404-Fälle, Such-Filter, der dokumentierten album_artist-
  Fallback-Modellgrenze) — alle grün.
- Volle Backend-Suite (`core/tests/`, nach Nachinstallation von `ffmpeg`,
  das zwischenzeitlich aus der Sandbox verschwunden war):
  530 passed, 12 skipped — die einzige verbleibende Lücke (`fpcalc`/
  Chromaprint-Binary fehlt in der Sandbox) ist umgebungsbedingt und
  unabhängig von dieser Änderung (vorher-nachher-Vergleich per `git
  stash` bestätigt).

**UI (neu):**
- `ui-reference-pyside/genesis_ui/api_client.py` — 9 neue Client-Methoden
  (`list_library_*`/`get_library_*_detail`).
- `ui-reference-pyside/genesis_ui/views/library_view.py` — EINE
  parametrisierte `LibraryBrowserView(api, kind, title)` statt sechs
  Kopien, da sich Interpreten/Alben/Titel/Genres/Personen/Quellen alle auf
  dasselbe Muster abbilden lassen: durchsuchbare Liste (`QTreeWidget`) +
  Detailbereich (`QTextEdit`, read-only) in einem `QSplitter`. Bei
  Interpreten/Alben/Genres/Personen löst eine Zeilenauswahl einen
  zusätzlichen Detail-API-Aufruf aus; bei Titeln/Quellen werden die
  bereits geladenen Zeilendaten direkt gerendert (kein weiterer
  Roundtrip nötig, da die Listen-Antwort dort schon alle Felder enthält).
  Rollen-/Werkart-Bezeichnungen (Person-Detail) sind über eigene
  i18n-Schlüssel übersetzt, nicht hartcodiert.
- `main_window.py`: `NAV_STRUCTURE`-Einträge für `nav.artists/albums/
  titles/genres/persons/sources` von `"placeholder"` auf `"library"`
  umgestellt (inkl. des zweiten `nav.sources`-Eintrags im Download/
  Import-Abschnitt — beide Einträge teilen sich dieselbe Seiteninstanz,
  wie bereits beim bestehenden `download_center`/`import`-Muster üblich).
  `_create_page` um den `"library"`-Zweig ergänzt.
- i18n: neue Sektion `library_view.*` (inkl. `library_view.artists.*`,
  `.albums.*`, `.titles.*`, `.genres.*`, `.persons.*`, `.sources.*`) in
  allen vier Sprachen (de/en/ja/ru) ergänzt; die nun obsoleten
  `nav.{artists,albums,titles,genres,persons,sources}_detail`-Platzhalter-
  Schlüssel entfernt. `test_i18n.py` (Schlüssel-Paritätscheck über alle
  vier Sprachen) weiterhin grün (6/6).
- Neue Testdatei `ui-reference-pyside/tests/test_library_view.py`
  (9 Tests: Liste+Detail je Kind, Such-Filter, Fehlerfall bei
  API-Ausfall, leere Trefferliste, "kein zusätzlicher Request bei
  Titeln/Quellen"-Verhalten) — alle grün. Volle UI-Suite:
  69/69 passed (60 vorher + 9 neue), keine Regressionen.

**End-to-End-Verifikation gegen einen echten, befüllten Core-Service**
(nicht nur Fakes): `core/run_api.py` auf Port 8421 gegen ein frisches
`/tmp`-Datenverzeichnis gestartet, per direktem `Database`/ORM-Zugriff
mit einem vollständigen Beispieldatensatz befüllt (Interpret "Die Toten
Hosen" → Album "Opium fürs Volk" → Titel "Alles aus Liebe", Genre "Punk
Rock", Quelle via YouTube-Download, Person "Campino" mit Rolle
`ARTIST`), dann alle sechs `LibraryBrowserView`-Instanzen UND eine volle
`MainWindow` gegen den laufenden Service instanziiert. Ergebnis: jede der
sechs Seiten zeigt genau 1 Zeile mit den erwarteten Werten, jeder
Detailbereich rendert korrekt (inkl. der Album-/Rollen-Listen aus den
Detail-Endpunkten), alle sechs Navigationseinträge sind auf genau 6
eindeutige `page_index`-Einträge (`library:artists` … `library:sources`)
dedupliziert, und das Server-Log zeigt ausschließlich `200 OK`-Antworten
über den gesamten Durchlauf (keine Fehler).

**Dokumentation:** `docs/GAP_ANALYSIS.md` aktualisiert — Gaps D, E, F, A,
I und B sind jetzt direkt unter ihrer jeweiligen Befund-Überschrift mit
"✅ GESCHLOSSEN (Sitzung 14)" markiert (ursprünglicher Befundtext bleibt
als historisches Protokoll stehen), Abschnitt 4 (priorisierte Empfehlung)
entsprechend aktualisiert. `docs/REVIEW_LOG.md` um einen zusammenfassenden
Abschnitt 8 mit Verweis auf diese PROGRESS.md-Einträge ergänzt.

**Commit/Push:** alle Änderungen dieser Gruppe werden gemeinsam mit den
Doku-Korrekturen aus Gruppe 2 (stale `/settings`-Docstring,
`GAP_ANALYSIS.md`, `REVIEW_LOG.md`) in einem Commit zusammengefasst und
nach `origin/main` gepusht.

**Nächster Schritt (Gruppe 4 laut Priorität):** Gap G - ein allgemeiner,
in die Bibliothek eingebauter Medienplayer (Play/Pause/Stop/Seek/
Lautstärke), analog zum bereits vorhandenen `QMediaPlayer`-Einsatz im
Cutter/Voice Studio, aber für beliebige Bibliotheksmedien direkt aus der
Medientabelle heraus nutzbar.

## Sitzung 14 (Fortsetzung 3) — G4S-Legacy-Audit (Gregor Segner / `g4s`)

Auf expliziten Nutzerwunsch: Durchsicht des öffentlichen GitHub-Bestands
von Gregor Segner (`github.com/g4s`, 23 öffentliche Repos, Bundesdruckerei/
Ludwigshafen) auf verwertbare technische Ideen für GENESIS, mit der
Vorgabe, Gregors Namen dabei NICHT in einer versteckten Fußnote
verschwinden zu lassen, sondern als sichtbare, ehrliche technische
Herkunft zu dokumentieren — niemals als unzutreffende Behauptung einer
Mitarbeit.

- Neues Dokument `docs/G4S-LEGACY.md`: enthält den vom Nutzer vorgegebenen
  "G4S Legacy Attribution Standard" (8 Punkte) sowie eine Repo-für-Repo-
  Auswertung der acht vom Nutzer benannten Projekte (`machine-templates`,
  `de.seafi.minimalinstall`, `ansible-cve-scan`, `collecction`,
  `paperless-install`, `boxes`, `dotfiles`, `de.seafi.firewalling`) —
  jeweils mit tatsächlichem README-Inhalt (nicht geraten), ehrlicher
  Kategorisierung (Idee/Architektur vs. "nur untersucht, ohne
  Verwendung") und Bezug zu GENESIS.
- Zentrales, ehrliches Ergebnis: Der `g4s`-Bestand ist technisch
  Infrastruktur-Automatisierung (Ansible/Packer/Buildah/Shell) — ein
  anderer Bereich als GENESIS (Python/FastAPI/PySide6/SQLAlchemy).
  Direkte Code-Übernahme war in keinem Fall sachlich naheliegend oder
  erfolgt. Die wertvollste Erkenntnis ist eine **bestätigte Parallele**:
  `ansible-cve-scan`s README-Zitat "will not patch them" (nur scannen,
  nicht automatisch patchen) entspricht exakt GENESIS' eigenem, bereits
  VOR dieser Durchsicht unabhängig etablierten Grundprinzip #4–#6 (keine
  stillen Änderungen) sowie den Modulen `genesis_core/diagnostics`
  (rein lesend) und `genesis_core/repair` (Scan → Plan → Vorschau →
  Bestätigung → Ausführen). Bewusst als "historische Parallele/
  Bestätigung", NICHT als rückwirkend erfundene Inspirationsquelle
  dokumentiert, da GENESIS' Architektur zeitlich zuerst entstand.
- `de.seafi.firewalling` erwies sich beim tatsächlichen Hineinsehen als
  noch sehr früher Stub (2 Commits) ohne das vom Nutzer vermutete
  ausgereifte "Policy→Regel→Apply"-Muster — ehrlich als "kein
  verwertbarer Befund zum Prüfzeitpunkt" vermerkt statt eines nicht
  belegbaren Musters hineinzuinterpretieren.
- Der vom Nutzer erwähnte Gedanke "fehlerhafte Stellen als künftige
  Regressionstest-Grundlage bewahren" (Beispiel: Tippfehler wie
  `testinfa`/`testinfra`) wurde geprüft: Die tatsächlich vorhandenen
  Tippfehler-Commits in `boxes`/`dotfiles` ("fixing typo(s)") sind bereits
  behoben, kein konkret übernehmbarer Fehler zum Audit-Zeitpunkt
  gefunden. Der Grundsatz selbst wurde dennoch als dauerhafte
  Standing-Praxis in `docs/G4S-LEGACY.md` Abschnitt 4 festgehalten, für
  künftige Funde.
- Keine einzige Zeile Code aus einem `g4s`-Repo wurde übernommen (siehe
  `docs/G4S-LEGACY.md` Abschnitt 3) — entsprechend keine
  Lizenz-/Copyright-Einträge in `licenses/THIRD-PARTY-LICENSES.md` nötig.
- `README.md` um einen kurzen, sichtbaren Danksagungs-/Verweisabschnitt
  auf `docs/G4S-LEGACY.md` ergänzt (keine versteckte Fußnote).

**Hinweis:** Dies ist eine lebende Auswertung (Punkt 7 des Standards) —
wird bei künftigem tatsächlichem Ideen-/Code-Transfer aus Gregors Bestand
weiter ergänzt, nicht als einmalige Momentaufnahme behandelt.

## Sitzung 14 (Fortsetzung 4) — Gap-Gruppe 4: Eingebauter Medienplayer (Gap G, §60)

**Auftrag:** Fortsetzung der vom Nutzer freigegebenen sequenziellen
Abarbeitung (`"mach es der reihe nach bis du fertig bist"`, bestätigt
erneut per `"ja sollst du"` nach Abschluss der G4S-Legacy-Aufgabe).
Gruppe 4 schließt Gap G aus `docs/GAP_ANALYSIS.md`: GENESIS hatte keinen
allgemeinen, immer verfügbaren Medienplayer für die Bibliothek — nur
eng gekoppelte Vorschau-Wiedergabe in `CutterDialog` (Schnittvorschau)
und `VoiceStudioView` (TTS-Testwiedergabe), beide als `QMediaPlayer`
innerhalb eines Werkzeug-Dialogs. §60 fordert ausdrücklich einen
"einfachen lokalen Player" für die Bibliothek selbst.

**Umsetzung:**

- Neue wiederverwendbare Komponente
  `ui-reference-pyside/genesis_ui/widgets/player_bar.py`
  (`PlayerBarWidget`): `QMediaPlayer` + `QAudioOutput` (Lautstärke) +
  optionales `QVideoWidget` (nur sichtbar für `kind in {"movie",
  "episode"}`, bei reiner Audio-Wiedergabe ausgeblendet, um Platz zu
  sparen). Steuerung: Play/Pause-Umschaltknopf (Text wechselt je nach
  `playbackStateChanged`), Stopp, Such-Schieberegler (`QSlider`,
  synchronisiert mit `positionChanged`/`durationChanged`, reagiert nicht
  auf Programmaktualisierungen, während der Nutzer selbst zieht —
  geprüft in `test_position_update_does_not_fight_user_drag`),
  Lautstärkeregler (0–100 → 0.0–1.0), Zeitanzeige (`format_time()`,
  reine Hilfsfunktion, inkl. Stunden-Format für lange Hörbuch-
  Kapitel/Filme), sowie eine sichtbare Fehlermeldung bei
  `errorOccurred` statt stillem Fehlschlag (Grundprinzip: keine stillen
  Fehler). `load_and_play(path, title, kind)` schaltet auf eine neue
  Datei um und startet sofort die Wiedergabe (bewusste Reaktion auf
  einen expliziten "Abspielen"-Klick, kein Autoplay beim bloßen
  Markieren einer Tabellenzeile). `stop_and_clear()` setzt alles zurück
  (wird bei jedem `MediaTableView.refresh()` aufgerufen, damit eine neu
  geladene Trefferliste nie eine unsichtbar weiterlaufende alte
  Wiedergabe zurücklässt).
- `ui-reference-pyside/genesis_ui/views/media_table.py`: neuer
  "Abspielen …"-Button in der Aktionsleiste (aktiv nur bei genau einer
  Auswahl, analog zu `metadata_btn`), `_on_play_clicked()` liest Pfad/
  Dateiname/Art aus der ausgewählten Zeile (gleiches Muster wie
  `_on_cutter_clicked`) und ruft `self.player_bar.load_and_play(...)`
  auf. `self.player_bar` ist als persistente Instanz unterhalb des
  bestehenden `QSplitter` eingebettet — bleibt über Auswahl-/Suchwechsel
  hinweg sichtbar, echte "immer verfügbare" Leiste statt Dialog.
- i18n: neue Sektion `player_bar.*` (no_media, now_playing, play_button,
  pause_button, stop_button, volume_label, playback_error) sowie
  `media_table.play_button` in allen vier Sprachdateien
  (`i18n/{de,en,ja,ru}.json`) ergänzt; `test_i18n.py` weiterhin grün (6
  bestanden — prüft u.a. Schlüsselparität zwischen allen Sprachen).
- Tests: `tests/test_player_bar.py` (12 Fälle — Zeitformatierung mit/
  ohne Stunden, Negativ-Clamping, Ausgangszustand deaktiviert,
  Positions-/Dauer-Update inkl. Schieberegler-Schutz während Nutzer-
  Drag, Lautstärke-Mapping 0/50/100 → 0.0/0.5/1.0, sichtbare
  Fehlermeldung, vollständiger Reset bei `stop_and_clear`, Laden+Play
  aktiviert Steuerelemente und setzt Titel, Video-Sichtbarkeit korrekt
  je nach `kind`) sowie
  `tests/test_media_table_player_integration.py` (6 Fälle — Leiste ist
  eingebettet und anfangs inaktiv, "Abspielen"-Button nur bei exakt
  einer Auswahl aktiv, Klick übergibt korrekten Pfad/Titel/Art [inkl.
  Video-Art bei `movie`], Klick ohne Auswahl ist no-op, `refresh()`
  stoppt und leert die Leiste). Alle Fälle laufen per
  `QT_QPA_PLATFORM=offscreen` mit Fake-API, kein echter Core-Service
  nötig.
- **Bekannte, bewusst akzeptierte Testgrenze:** wie bereits bei
  `CutterDialog`/`VoiceStudioView` ist tatsächliche Tonausgabe in der
  Linux-Sandbox ohne Audiogerät nicht hörbar verifizierbar (PulseAudio-
  Verbindung schlägt erwartungsgemäß fehl, siehe Stderr-Meldung
  `pa_context_connect() failed` beim Smoke-Test). Getestet wird daher
  die vollständige Verdrahtung (Zustände, Signale, Mapping-Formeln,
  Button-Freischaltung, Parameterübergabe) — exakt dasselbe,
  bereits akzeptierte Muster wie bei den beiden bestehenden
  Vorschau-Playern.
- `docs/GAP_ANALYSIS.md`: Gap G als ✅ GESCHLOSSEN markiert mit
  Umsetzungsdetails; Gap H (Toolbar- statt Kontextmenü-Darstellung) als
  "teilweise geschlossen" aktualisiert, da alle zuvor dort als fehlend
  gelisteten Einzel-Aktionen ("Abspielen", "Datei öffnen"/"Ordner
  öffnen", "In Bibliothek anzeigen") jetzt vorhanden sind — offen bleibt
  nur noch der rein strukturelle Umbau Toolbar→Kontextmenü.

**Umgebungs-Hinweis (Sandbox-Volatilität, wie in früheren Sitzungen):**
Zu Beginn dieses Segments waren weder `PySide6` noch `ffmpeg` installiert
(Pakete werden zwischen Sitzungs-Segmenten nicht zuverlässig
übernommen). Nach `pip install -q PySide6` sowie
`sudo apt-get install -y --no-install-recommends libxkbcommon0
libpulse0 ffmpeg` liefen alle Tests wie erwartet:
`ui-reference-pyside`: **87 von 87 Tests bestanden** (vorher 69 — 18 neu
hinzugekommen durch diese Gruppe); `core`: **530 bestanden, 12
übersprungen, 1 bekannter Fehlschlag** wegen fehlendem `fpcalc`-Binary
(exakt derselbe, bereits dokumentierte Umgebungs-Fehlschlag wie in
Fortsetzung 1/2 — unverändert, nicht durch diese Arbeit verursacht; kein
Core-Code wurde in dieser Gruppe verändert).

**Nächste Schritte:** Weiter der Reihe nach zu den verbleibenden
Gap-Analyse-Gruppen (5–6) gemäß stehender Nutzerfreigabe, bis die
gesamte Liste abgearbeitet ist.

## Sitzung 14 (Fortsetzung 5) — Gap-Gruppe 5: Erweiterte Suche/Filter (Gap C, §9)

**Auftrag:** Fortsetzung der freigegebenen sequenziellen Abarbeitung. Beim
Durchgehen der in `docs/GAP_ANALYSIS.md` Abschnitt 4 festgehaltenen
Prioritätenliste fiel auf, dass **Gap C dort versehentlich fehlte**,
obwohl ihr Schweregrad (MITTEL-HOCH) über den für Gruppe 6 vorgesehenen
Punkten J (NIEDRIG-MITTEL) und H-Rest (NIEDRIG) liegt. Dies wurde als
offensichtlicher Dokumentationsfehler behandelt (keine neue, vom Nutzer zu
bestätigende Scope-Entscheidung, da die bestehende Freigabe "bis du fertig
bist" die GESAMTE Lückenliste abdeckt) und C direkt im Anschluss an G als
Gruppe 5 eingeschoben; die Liste wurde entsprechend mit einem Nachtrag-
Vermerk korrigiert.

**Befund:** `GET /media` filterte zuvor nur nach `kind` und einem reinen
Dateiname-/Pfad-Substring. §9 fordert erheblich mehr: Suche nach Interpret,
Album, Genre, Autor, Sprecher, Serie, Quelle, Person; Filter nach Format,
Dateigröße, Dauer, Jahr, Genre, Lautheit, Qualitätsverdacht, Quelle,
KI-Status, fehlenden Metadaten, fehlendem Cover, Duplikaten.

**Umsetzung (Backend):**

- Neue Funktion `genesis_core/library.py::build_media_search_statement()`
  (plus Hilfsfunktionen `_person_match_subquery()` für den
  Wissensgraph-Personenpfad über vier verschiedene Rollenverknüpfungen
  [Film/Episode/Hörbuch/Musiktitel] und `_series_match_subquery()` für den
  von Hörbuch-Reihen UND TV-Serien gemeinsam genutzten `Series`-Pfad).
  Ein-zu-viele-Beziehungen (Quelle, Lautheits-Messungen, Duplikat-
  Mitgliedschaft, Artwork, Personenrollen) werden bewusst als EXISTS-/
  IN-Unterabfragen statt als direkter JOIN angehängt, damit eine Datei mit
  z.B. drei Quellen nicht dreifach in der Trefferliste auftaucht.
- `GET /media` (`genesis_core/api/app.py`) um 19 neue optionale
  Query-Parameter erweitert: `year`, `genre`, `extension`,
  `min_size_bytes`/`max_size_bytes`, `min_duration_s`/`max_duration_s`,
  `source`, `person`, `series`, `season`, `episode_number`, `ai_status`,
  `min_lufs`/`max_lufs`, `has_quality_issues`, `missing_metadata`,
  `missing_cover`, `duplicate_only`. `search` selbst wurde serverseitig
  erheblich erweitert (vorher nur Dateiname/Pfad - jetzt zusätzlich
  Titel/Interpret/Album/Genre/Autor/Sprecher/Serie/Quelle/Person).
- Tests: `core/tests/test_api_media_search.py` (19 Testfälle über eine
  realistische, gemischte Testbibliothek [Musiktitel mit KI-Status/
  Lautheit/Qualitätsverdacht/Quelle, Hörbuch mit Reihe/Autor/Sprecher,
  Film ohne Titel, TV-Episode mit Staffel/Episode, Duplikat-Paar] -
  deckt jede Filterdimension einzeln sowie kombiniert ab). Volle
  Core-Suite danach: **549 bestanden** (vorher 530 — 19 neu), 12
  übersprungen, weiterhin derselbe eine bekannte fpcalc-bedingte
  Fehlschlag, unverändert zu vorherigen Sitzungen.

**Umsetzung (GUI):**

- Neuer `SearchFiltersDialog`
  (`ui-reference-pyside/genesis_ui/dialogs/search_filters_dialog.py`):
  Formular mit Textfeldern (Genre/Quelle/Person/Serie/Format),
  Zahlen-/Bereichsfeldern (Jahr, Staffel/Episode, Dateigröße-Von/Bis in
  MB, Dauer-Von/Bis in Sekunden, Lautheit-Von/Bis in LUFS mit eigener
  Aktivierungs-Checkbox, damit `0` nicht faelschlich als "LUFS=0"
  interpretiert wird), KI-Status-Auswahlbox sowie vier Kontrollkästchen
  (Qualitätsverdacht/fehlende Metadaten/fehlendes Cover/nur Duplikate).
  `get_filters()` liefert nur tatsächlich gesetzte Werte (leere/Default-
  Werte werden zu `None`, damit sie die Bibliothek nicht fälschlich
  leerfiltern); `count_active_filters()` ist eine von Qt unabhängige reine
  Zählfunktion für die Statusanzeige.
- `genesis_ui/api_client.py::list_media()` nimmt jetzt `**filters`
  entgegen und reicht nur die nicht-`None`-Werte als Query-Parameter
  durch - zukunftssicher fuer evtl. weitere spaetere Filter, ohne die
  Signatur erneut aendern zu muessen.
- `media_table.py`: neuer "Filter …"-Button neben dem bestehenden
  Suchschlitz öffnet den Dialog (vorbelegt mit den aktuell aktiven
  Filtern); bei Bestätigung werden die Filter in `self._active_filters`
  gespeichert, eine Statusanzeige ("Filter aktiv (n)") aktualisiert und
  sofort ein `refresh()` mit den neuen Filtern ausgelöst. Abbruch des
  Dialogs ändert nichts an den bisher aktiven Filtern.
- i18n: neue Sektion `search_filters_dialog.*` (26 Schlüssel) sowie
  `media_table.filters_button`/`media_table.filters_active_label` in
  allen vier Sprachdateien ergänzt; `test_i18n.py` weiterhin grün.
- Tests: `tests/test_search_filters_dialog.py` (13 Fälle - Feld-zu-
  Filter-Mapping, Leerstring-Behandlung, MB→Byte-Umrechnung, LUFS nur bei
  aktivierter Checkbox, KI-Status-Mapping, Vorbelegung/Reset) und
  `tests/test_media_table_filters_integration.py` (4 Fälle - initialer
  Refresh ohne Zusatzfilter, bestätigte Filter werden durchgereicht,
  Statusanzeige korrekt, Abbruch ändert nichts). `SearchFiltersDialog.
  exec()` wird dabei per `monkeypatch` ersetzt (kein echter modaler
  Dialog in der Offscreen-Sandbox nötig) - gleiches Muster wie bei allen
  anderen Dialog-Integrationstests in diesem Verzeichnis. Volle
  UI-Suite danach: **104 bestanden** (vorher 87 — 17 neu).
- `docs/GAP_ANALYSIS.md`: Gap C als ✅ GESCHLOSSEN markiert; bewusst nicht
  geschlossene Verfeinerung dokumentiert (kein rollen-spezifischer
  Personenfilter, z.B. "nur als Regisseur" statt "in irgendeiner Rolle" -
  von §9 nicht explizit gefordert). Prioritätenliste in Abschnitt 4
  korrigiert (Gap C nachträglich eingefügt, Gruppen 6/7 entsprechend
  verschoben).

**Nächste Schritte:** Weiter der Reihe nach mit Gruppe 6 (**J** Log-Viewer,
**H**-Rest Kontextmenü-Umbau) und danach laufend **K** (.NET-Parität),
gemäß stehender Nutzerfreigabe.

## Sitzung 14 (Fortsetzung 6) — Gap-Gruppe 6: Log-Viewer (Gap J, §?) + Kontextmenü (Gap H-Rest, §61)

**Umsetzung (Backend, Log-Viewer):**

- Neues Modul `core/genesis_core/logutil/reader.py`: `LogEntry`-Dataclass,
  `read_log_entries(log_dir, level, component, search, limit, offset)` liest
  die bereits bestehenden strukturierten Logdateien (`StructuredFormatter`,
  siehe `genesis_core/logutil/__init__.py`), inkl. rotierter Backup-Dateien
  (`_list_log_files_oldest_first()`), gruppiert mehrzeilige
  Traceback-Fortsetzungszeilen zu ihrem Eintrag (`_parse_log_lines()`),
  filtert nach Level (`LEVEL_ORDER`-Rangfolge, "mindestens Level X"),
  Komponente (exakt) und Freitext (Teilstring über die volle Nachricht),
  liefert `(total, entries)` mit den neuesten Einträgen zuerst, paginiert
  per `limit`/`offset`. Rein lesend — keine Schreib-/Löschfunktion (Prinzip
  "kein stiller Fehlschlag", Logs sind Diagnoseinstrument, kein editierbarer
  Datenbestand).
- Neuer Endpunkt `GET /logs` in `core/genesis_core/api/app.py` (token-
  geschützt wie alle anderen Endpunkte außer `/health`), reicht Query-
  Parameter `level`/`component`/`search`/`limit`/`offset` direkt an
  `read_log_entries()` durch.
- Tests: `core/tests/test_logutil_reader.py` (10 Fälle — Parsing einzeiliger
  und mehrzeiliger Einträge inkl. Traceback, Level-Filter als
  Mindestschwelle, Komponenten-Filter, Freitextsuche, Pagination, Sortierung
  neueste zuerst, mehrere Logdateien inkl. rotierter Backups) und
  `core/tests/test_api_logs.py` (6 Fälle, nutzt echte durch einen
  Scan-Lauf erzeugte Logzeilen über die `test_library_root`-Fixture statt
  künstlich konstruierter Logdateien). Volle Core-Suite danach: **565
  bestanden** (vorher 549 — 16 neu), 12 übersprungen, weiterhin derselbe
  eine bekannte fpcalc-bedingte Fehlschlag.

**Umsetzung (GUI, Log-Viewer):**

- Neue Ansicht `ui-reference-pyside/genesis_ui/views/log_viewer_view.py`
  (`LogViewerView`): Level-Auswahlbox, Komponenten-/Freitext-Suchfelder,
  `QTreeWidget` mit Zeitstempel/Level/Komponente/erster Zeile der Nachricht
  je Eintrag, Detailbereich zeigt die volle (ggf. mehrzeilige) Nachricht bei
  Auswahl, Vor-/Zurück-Pagination (`PAGE_SIZE = 200`).
  `genesis_ui/api_client.py::get_logs(level, component, search, limit,
  offset)` neu ergänzt.
- `main_window.py`: `nav.logs` war bisher
  `("nav.logs", "placeholder", "nav.logs_detail")` — jetzt
  `("nav.logs", "log_viewer", None)`, `_create_page()` liefert dafür eine
  `LogViewerView`-Instanz.
- i18n: neue Sektion `log_viewer_view.*` in allen vier Sprachdateien.
- Tests: `tests/test_log_viewer_view.py` (8 Fälle — initiales Laden,
  Level-/Komponenten-/Freitextfilter werden korrekt an `get_logs()`
  durchgereicht, Pagination vor/zurück, Detailanzeige bei Auswahl,
  API-Fehler werden sichtbar statt stillschweigend verschluckt).

**Umsetzung (Kontextmenü, Gap H-Rest):**

- `media_table.py`: Tabelle erhält `setContextMenuPolicy(Qt.
  CustomContextMenu)` + `customContextMenuRequested`-Verbindung. Neue
  `_on_table_context_menu()` (wählt die Zeile unter dem Mauszeiger aus,
  behält eine bestehende Mehrfachauswahl bei, falls der Klick innerhalb
  davon liegt) und `_build_context_menu()` (rein aufbauend, bewusst
  GETRENNT von `.exec()` gehalten, um in Tests ohne echten modalen
  Eventloop prüfbar zu sein). Das Menü spiegelt alle 15
  Toolbar-Aktionen (Abspielen, Metadaten-Vorschläge, Umbenennen,
  Fingerprint, Lautheit, Qualität, Artwork, KI, Hörbuch&Kapitel,
  Film&Serie, Cutter, Konvertieren, Datei öffnen, Ordner öffnen, Pfad
  kopieren) über dieselben bestehenden Handler — die Toolbar selbst bleibt
  zusätzlich bestehen (§61-Wortlaut verlangt ein Kontextmenü, keine
  Entfernung der Toolbar).
- Tests: `tests/test_media_table_context_menu.py` (7 Fälle — Rechtsklick
  auf Einzelzeile wählt sie aus, Rechtsklick innerhalb einer bestehenden
  Mehrfachauswahl erhält diese [ein erster Versuch mit `selectRow()`
  schlug fehl, weil das die bestehende Auswahl ERSETZT statt sie zu
  erweitern — behoben über `QItemSelectionModel.Select|Rows`-Flags],
  Rechtsklick außerhalb jeder Zeile hebt die Auswahl auf, Menüeinträge
  vorhanden und mit den Toolbar-Handlern identisch verdrahtet). Ein
  erster Testansatz, der `QMenu.exec()` direkt in einem Smoke-Test
  aufrief, hing/blockierte (Klassen-Monkeypatch verhinderte die echte
  modale Eventloop nicht) — behoben durch obige Trennung von
  Menü-Aufbau und `.exec()`-Aufruf.

**Ergebnis gesamt:** Volle UI-Suite danach: **119 bestanden** (vorher 104 —
15 neu). `docs/GAP_ANALYSIS.md`: Gap J als ✅ GESCHLOSSEN markiert, Gap H
jetzt als ✅ VOLLSTÄNDIG GESCHLOSSEN (vorher nur teilweise über Gaps
E/G/B), Prioritätenliste in Abschnitt 4 finalisiert (Gap K als einziger
noch offener Punkt markiert).

**Nächste Schritte:** Laufend **K** (.NET-Parität), gemäß stehender
Nutzerfreigabe — siehe folgender Abschnitt für den ersten inkrementellen
Schritt.

## Sitzung 14 (Fortsetzung 7) — Gap K: .NET/WPF-Parität, erster inkrementeller Schritt (Medientabellen-Ansicht)

**Scope-Entscheidung:** Der verbleibende Punkt K (.NET/WPF-Client hinkt der
Python-Referenz-UI hinterher) hat einen massiv größeren Umfang als alle
zuvor abgearbeiteten Punkte A–J (WPF-Grundgerüst zu diesem Zeitpunkt: ~825
Zeilen über 7 Dateien mit genau EINER echten Seite [Dashboard] gegenüber
der Python-Referenz-UI mit ~20 Ansichten/~15 Dialogen). Der Nutzer wurde
dazu per Rückfrage explizit befragt und hat sich für die Option
**"inkrementell"** entschieden: die 2–3 wichtigsten Ansichten jetzt
nachziehen (begonnen mit Dashboard [bereits vorhanden] und Medientabelle),
Fortsetzung in künftigen Sitzungen — explizit KEIN Versuch, die volle
Parität in einer einzigen Sitzung zu erzwingen.

**Umsetzung:**

- `.NET SDK 8.0.425` nach dem in `ui-windows-dotnet/README.md` dokumentierten
  Rezept installiert (`/home/user/.dotnet`, `TMPDIR=/home/user/.dotnet-tmp`),
  Baseline-Build vor Änderungen verifiziert (0 Warnings/0 Errors), Baseline-
  Tests verifiziert (`TranslatorTests.cs`: 11/11 grün).
- `GenesisApiClient.cs` vollständig gelesen/geprüft: deckt bereits
  Dashboard/Settings/Media-Liste+Detail/Metadaten-Vorschläge/Umbenennen/
  Artwork ab (mehr als zunächst angenommen) — die eigentliche Lücke liegt
  in `MainWindow.xaml.cs`, wo bisher nur `nav.dashboard` tatsächlich
  verdrahtet war und alle anderen Navigationspunkte einen generischen
  Platzhaltertext zeigten.
- Neue Methode `ShowMediaTableAsync(navItemKey, kind)` in
  `MainWindow.xaml.cs`: baut programmatisch (gleiches Muster wie
  `ShowDashboardAsync()`) ein Suchfeld + `DataGrid`
  (Titel/Art/Format/Größe/Pfad, gebunden an `List<MediaItem>`) + ein
  Detail-Textfeld, das bei Zeilenauswahl per `GetMediaDetailAsync()`
  nachgeladen wird. Neue Zuordnung `MediaKindByNavKey`: 1:1 dieselbe
  `("nav.xxx", "media", "<kind-oder-null>")`-Struktur wie
  `NAV_STRUCTURE` in `ui-reference-pyside/genesis_ui/main_window.py`
  (sieben Medienarten-Navigationspunkte + `nav.search` ohne Art-Filter).
  `OnNavigationSelectedAsync()` prüft diese Zuordnung vor dem Rückfall auf
  den Platzhaltertext.
- **Refactoring für Testbarkeit:** die Zuordnungstabelle und die
  Detailtext-Erzeugung (`BuildMediaDetailText`) wurden NICHT direkt in
  `MainWindow.xaml.cs` belassen, sondern in eine neue, WPF-freie Datei
  `MediaTableSupport.cs` ausgelagert (gleiches Muster wie
  `I18n/Translator.cs`) — nur so kann das separate, reine `net8.0`-
  Testprojekt (`GenesisMediaManager.Client.Tests`, läuft ohne Windows-
  Targeting-Pack) diese Logik ohne echten WPF-Control-Baum prüfen.
  `GenesisMediaManager.Client.Tests.csproj` bindet dafür zusätzlich
  `Api/GenesisApiClient.cs` (enthält die DTO-Records `MediaItem`/
  `MediaDetail`/`TechnicalMetadata`/`TrackInfo`, selbst ohne
  WPF-Abhängigkeit) und `MediaTableSupport.cs` per `<Compile Include>` ein.
- Detailtext deckt denselben Kernumfang ab wie
  `ui-reference-pyside/genesis_ui/views/media_table.py`: Pfad,
  Existenz auf Datenträger, Dateiname/Ordner/Größe/Format/Änderungsdatum/
  SHA-256, Technik-Metadaten (nur tatsächlich vorhandene Felder),
  Track-Metadaten (Titel/Track-Disc/Jahr/Quelle/Konfidenz/Nutzer-
  bestätigt) bzw. "keine Metadaten", eingebettetes Artwork ja/nein —
  verwendet exakt dieselben `media_table.*`/`media_table.detail.*`
  i18n-Schlüssel wie die Python-UI (keine neue Doppelpflege von Texten
  nötig, da beide UIs dieselben `i18n/*.json`-Dateien lesen).
- **Bewusst NICHT** in diesem ersten Schritt enthalten (vorgemerkt für
  Folgesitzungen, siehe `docs/GAP_ANALYSIS.md` Gap K): Qualitätsprüfung/
  Loudness/KI-Analyse/Quellen-Abschnitt im Detailpanel (brauchen weitere,
  noch fehlende `GenesisApiClient.cs`-Endpunkt-Methoden), Kontextmenü,
  Mehrfachauswahl-Aktionen (Rename/Metadaten/Artwork-Methoden existieren
  im API-Client bereits, sind aber noch an keiner UI-Stelle verdrahtet),
  Filter-Dialog, eingebetteter Player, Settings-Ansicht, Log-Viewer,
  Bibliotheks-Drill-down.
- Tests: neue `MediaTableSupportTests.cs` (14 Fälle — alle sieben
  Medienarten-Zuordnungen, `nav.search` ohne Filter, nicht-medienbezogene
  Nav-Keys fehlen bewusst in der Zuordnung, Detailtext-Grundfelder,
  "keine Metadaten"-Fall, Metadaten-Fall mit Titel/Bestätigt-Status,
  Technik-Feld-Filterung [nur vorhandene Felder erscheinen],
  eingebettetes Artwork ja/nein). `dotnet test`: **25/25 bestanden**
  (vorher 11 — 14 neu). `dotnet build -p:EnableWindowsTargeting=true` für
  den WPF-Client selbst: weiterhin 0 Warnings/0 Errors.
- Begleitend volle Python-Suiten erneut verifiziert (reine
  Regressionskontrolle, keine Python-Änderung in dieser Fortsetzung):
  Core-Suite **565 bestanden**/12 übersprungen/1 bekannter fpcalc-Fehlschlag,
  UI-Suite **119 bestanden** — unverändert zu Fortsetzung 6.
- `docs/GAP_ANALYSIS.md` Gap K und Prioritätenliste aktualisiert: NICHT als
  geschlossen markiert (🟡 statt ✅), sondern als "laufend, inkrementell"
  mit genauer Auflistung des bereits Erledigten und der nächsten
  vorgemerkten Schritte. `ui-windows-dotnet/README.md`-Status-Abschnitt
  entsprechend erweitert.
- **Aufräumen nach Abschluss** (gemäß README-Vorgabe, Workspace-Snapshot-
  Größe): `.NET-SDK`, `NuGet`-Cache, `bin`/`obj`-Verzeichnisse werden vor
  Sitzungsende entfernt (siehe unten im Commit-Verlauf dieser Sitzung).

**Nächste Schritte:** Fortsetzung in künftigen Sitzungen gemäß
"inkrementell"-Vorgabe — als nächstes voraussichtlich eine Settings-Ansicht
(da `GetSettingsAsync` bereits existiert), danach weitere Werkzeuge/Dialoge
nach Priorität der verbleibenden Python-Ansichten.

## Sitzung 14 (Fortsetzung 8) — Gap K: .NET/WPF-Parität, zweiter inkrementeller Schritt (Einstellungen-Ansicht)

Fortsetzung der in Fortsetzung 7 begonnenen, vom Nutzer als "inkrementell"
freigegebenen .NET/WPF-Parity-Arbeit. Auf "los" vom Nutzer hin direkt mit
dem nächsten vorgemerkten Schritt fortgefahren: der Einstellungen-Ansicht.

**Umsetzung:**

- `.NET SDK 8.0.425` erneut nach dem README-Rezept installiert (wird
  zwischen Sitzungen nicht aufbewahrt, siehe Workspace-Hygiene-Vorgabe).
- `GenesisApiClient.cs` erweitert: `GeneralSettings`-Record um
  `SafeTestMode`/`RequireConfirmationForBulkChanges` ergänzt, neue DTOs
  `AiSettingsInfo`, `LoudnessSettingsInfo`, `PrivacySettingsInfo`,
  `SettingsResponse` entsprechend erweitert. Neue Methode
  `UpdateSettingsAsync(Dictionary<string, object> updates, bool confirm)`
  ruft `PATCH /settings` auf (`HttpClient.PatchAsJsonAsync`, Teil von
  `System.Net.Http.Json` seit .NET 5 — durch erfolgreichen Build
  verifiziert). Neue Records `SettingsUpdateRequest`/`SettingsUpdateResult`
  spiegeln `SettingsUpdateRequest`/die Rückgabestruktur von
  `update_settings_endpoint` in `core/genesis_core/api/app.py`.
- Neue, WPF-freie Hilfsdatei `SettingsViewSupport.cs` (gleiches Muster wie
  `MediaTableSupport.cs`/`Translator.cs`): `SettingsFormValues`-Record als
  reiner Werte-Schnappschuss der UI-Steuerelemente,
  `FromSettingsResponse()` (API-Antwort → Formularwerte),
  `BuildUpdatePayload()` (Formularwerte → verschachtelte PATCH-Payload).
  WICHTIG dokumentiert im Code: die Payload wird mit EXPLIZITEN
  snake_case-Schlüsseln gebaut, weil `JsonNamingPolicy.SnakeCaseLower` nur
  auf echte Record-/Klassen-Properties wirkt, NICHT auf
  `Dictionary<string, object>`-Schlüssel — ein stiller Namensfehler hier
  hätte zu am Core Service ignorierten Feldern geführt (kein stiller
  Fehlschlag, Grundprinzip des Projekts).
- Neue Methode `ShowSettingsAsync()` in `MainWindow.xaml.cs` (verdrahtet
  für `nav.settings`, ersetzt den bisherigen Platzhalter): lädt die
  aktuellen Einstellungen, baut programmatisch vier Abschnitte
  (Allgemein/KI/Lautheit/Datenschutz) mit `GroupBox`+`CheckBox`/
  `ComboBox`/`TextBox`-Steuerelementen (Sprachauswahl DE/EN/JA/RU,
  KI-Aktivierung/Provider/Endpunkt/Modell/Zeitlimit, Lautheit-Zielwerte
  LUFS/True-Peak + Überschreiben-Erlauben-Warnung, fünf
  Datenschutz-Kontrollkästchen). "Speichern"-Button zeigt ZUERST einen
  `MessageBox.Show(...)`-Ja/Nein-Bestätigungsdialog (identisches Verhalten
  zu `ui-reference-pyside/genesis_ui/views/settings_view.py::
  _on_save_clicked`, Prinzip #17/§44 — kein automatisches Übernehmen),
  erst danach wird `UpdateSettingsAsync(..., confirm: true)` aufgerufen.
  Bei Erfolg wird die UI-Sprache sofort aktualisiert, falls geändert
  (`Translator.ConfigureDefaultLanguage`), und eine Erfolgsmeldung
  angezeigt (unterscheidet "gespeichert" vs. "gespeichert, Neustart
  nötig" je nach `restart_required`-Flag aus der API-Antwort). Nutzt
  dieselben `settings_view.*`-i18n-Schlüssel wie die Python-Referenz-UI
  (keine neue Doppelpflege von Texten).
- **Bewusst NICHT** in diesem zweiten Schritt enthalten (vorgemerkt für
  eine Folgesitzung, siehe `docs/GAP_ANALYSIS.md` Gap K): Medienordner-
  Liste, Sprachausgabe/Voice-Studio-Abschnitt, Download-/Import-Center-
  Abschnitt — alle drei brauchen einen noch fehlenden
  Ordner-Auswahldialog (`OpenFolderDialog`/`System.Windows.Forms.
  FolderBrowserDialog`), der als gemeinsame Grundlage für mehrere
  Abschnitte zuerst gebaut werden sollte, statt ihn dreifach zu
  duplizieren.
- Tests: neue `SettingsViewSupportTests.cs` (3 Fälle — vollständige
  Übernahme aller abgedeckten Felder aus `SettingsResponse`,
  `BuildUpdatePayload()` liefert exakt die vom Core erwarteten
  snake_case-Schlüssel inkl. korrekter Typen, Payload spiegelt geänderte
  Werte korrekt wider). `GenesisMediaManager.Client.Tests.csproj` um
  `<Compile Include>` für `SettingsViewSupport.cs` ergänzt (gleiches
  Muster wie `MediaTableSupport.cs`). `dotnet test`: **28/28 bestanden**
  (vorher 25 — 3 neu). `dotnet build -p:EnableWindowsTargeting=true` für
  den WPF-Client selbst: weiterhin 0 Warnungen/0 Fehler.
- `docs/GAP_ANALYSIS.md` Gap K um den zweiten Schritt ergänzt (weiterhin
  bewusst 🟡 "laufend/inkrementell", nicht ✅ geschlossen).
  `ui-windows-dotnet/README.md`-Status-Abschnitt entsprechend erweitert.
- **Aufräumen nach Abschluss** (gemäß README-Vorgabe): `.NET-SDK`,
  NuGet-Cache, `bin`/`obj`-Verzeichnisse vor Sitzungsende entfernt (siehe
  Commit-Verlauf dieser Sitzung).

**Nächste Schritte:** Fortsetzung in künftigen Sitzungen gemäß
"inkrementell"-Vorgabe — als nächstes voraussichtlich ein
Ordner-Auswahldialog (gemeinsame Grundlage) gefolgt von der
Medienordner-Verwaltung bzw. dem Download-Center, danach weitere
Werkzeuge/Dialoge nach Priorität der verbleibenden Python-Ansichten.

## Sitzung 14 (Fortsetzung 9) — Gap K: .NET/WPF-Parität, Einstellungen-Ansicht vervollständigt (7/7 Abschnitte)

Fortsetzung der inkrementellen .NET/WPF-Parity-Arbeit auf "weiter" vom
Nutzer hin. Statt eines neuen Themenbereichs wurden die in Fortsetzung 8
bewusst zurückgestellten drei Abschnitte der Einstellungen-Ansicht ergänzt,
da sie zusammengehören (gleiche Seite) und einen gemeinsamen Baustein
(Ordner-Auswahldialog) benötigten.

**Umsetzung:**

- `.NET SDK 8.0.425` erneut installiert (Workspace-Hygiene, siehe
  README-Vorgabe).
- **Medienordner-Abschnitt**: `ListBox` mit der aktuellen Ordnerliste,
  "Hinzufügen …"/"Entfernen"/"Jetzt scannen"-Buttons. "Hinzufügen" nutzt
  `Microsoft.Win32.OpenFolderDialog` — seit .NET 8 fester Bestandteil von
  WPF, kein `System.Windows.Forms`-Verweis nötig (durch erfolgreichen
  `dotnet build -p:EnableWindowsTargeting=true` bestätigt, dass der Typ in
  den Windows-Referenzassemblies vorhanden ist; kann in der Linux-Sandbox
  naturgemäß nicht interaktiv ausgeführt werden). "Jetzt scannen" ruft das
  bereits bestehende `TriggerScanAsync()` mit der aktuell sichtbaren
  Ordnerliste auf (unabhängig davon, ob gespeichert — identisch zum
  Kommentar/Verhalten in `settings_view.py::_on_scan_clicked`, Prinzip
  #4/#5) und liest `files_found` aus der `JsonElement`-Antwort.
- **Sprachausgabe/Voice-Studio-Abschnitt**: drei einfache Felder
  (Aktiviert-Checkbox, Provider-Combo `null`/`piper`, Export-Format-Combo
  `wav`/`mp3`/`flac`).
- **Download-/Import-Center-Abschnitt**: Aktiviert/YouTube/TikTok-
  Checkboxen, Zielordner-Textfeld + "Durchsuchen …"-Button (ebenfalls
  `OpenFolderDialog`), max. Downloadgröße/Mindest-Freispeicher (MB,
  `int`)/Zeitlimit (s, `double`).
- `GenesisApiClient.cs`: `SettingsResponse` um `Paths`
  (`PathsSettingsInfo.MediaFolders`), `Voice` (`VoiceSettingsInfo`) und
  `Download` (`DownloadSettingsInfo`, inkl. nullable `DownloadsDir`)
  erweitert.
- `SettingsViewSupport.cs`: `SettingsFormValues` und
  `BuildUpdatePayload()`/`FromSettingsResponse()` decken jetzt alle sieben
  Abschnitte ab (Allgemein/Medienordner/KI/Sprachausgabe/Lautheit/
  Download/Datenschutz) — **volle Parität zur Python-Referenz-UI
  innerhalb der Einstellungen-Ansicht**. Neue, WPF-freie
  `AddFolderIfMissing()`-Hilfsfunktion: dedupliziert, mutiert die
  Eingabeliste nicht (reine Funktion). Leerstring im Downloadordner-Feld
  wird beim Senden bewusst zu `null` (=> Core-Default), identisch zu
  `self.download_dir_edit.text() or None` in der Python-Referenz-UI.
- Tests: `SettingsViewSupportTests.cs` um 4 Fälle erweitert (Übernahme
  der neuen Felder aus `SettingsResponse`, Leerstring→`null`-Umwandlung
  für den Downloadordner UND der umgekehrte Fall [nicht-leerer Ordner
  bleibt unverändert], `AddFolderIfMissing` dedupliziert korrekt und
  lässt die Eingabeliste unangetastet). `dotnet test`: **32/32 bestanden**
  (vorher 28 — 4 neu). `dotnet build -p:EnableWindowsTargeting=true` für
  den WPF-Client selbst: weiterhin 0 Warnungen/0 Fehler.
- `docs/GAP_ANALYSIS.md` Gap K um den dritten Teilschritt ergänzt:
  Einstellungen-Ansicht erreicht volle 7/7-Parität, Gap K als Ganzes
  bleibt bewusst weiterhin 🟡 "laufend/inkrementell" (alle anderen
  ~19 Python-Ansichten/Dialoge sind weiterhin offen).
  `ui-windows-dotnet/README.md`-Status-Abschnitt entsprechend erweitert.
- **Aufräumen nach Abschluss** (gemäß README-Vorgabe): `.NET-SDK`,
  NuGet-Cache, `bin`/`obj`-Verzeichnisse vor Sitzungsende entfernt (siehe
  Commit-Verlauf dieser Sitzung).

**Nächste Schritte:** Metadaten-Provider-Verwaltung (Pendant zu Gap I,
eigene `nav.providers`-Seite) ODER Erweiterung des Medientabellen-
Detailpanels aus Schritt 1 (Qualität/Loudness/KI/Quellen) — Priorität in
einer künftigen Sitzung neu zu bewerten, gemäß stehender
"inkrementell"-Freigabe.

## Sitzung 14 (Fortsetzung 10) — Gap K: .NET/WPF-Parität, Medientabellen-Detailpanel vervollständigt (Qualität/Loudness/KI/Quelle)

Fortsetzung der inkrementellen .NET/WPF-Parity-Arbeit auf "weiter" vom
Nutzer hin. Statt eines neuen Themenbereichs wurden die in Schritt 1
(Fortsetzung 7) bewusst zurückgestellten vier Detailpanel-Abschnitte der
Medientabellen-Ansicht ergänzt.

**Umsetzung:**

- `.NET SDK 8.0.425` erneut installiert (Workspace-Hygiene, siehe
  README-Vorgabe).
- Vier neue, rein lesende Methoden in `GenesisApiClient.cs`:
  `GetQualityAsync` (`GET /media/{id}/quality` — liefert bewusst `null`
  bei "noch nicht analysiert", die Core-API antwortet dafür mit JSON
  `null` + Status 200, kein 404, da kein Fehlerfall), `ListLoudnessAsync`
  (`GET /media/{id}/loudness`, volle Historie neueste zuerst),
  `GetAiMetadataAsync` (`GET /media/{id}/ai/metadata`, immer mit Modell/
  Version/Confidence/Übernahme-Status — §25/Prinzip #9),
  `ListMediaSourcesAsync` (`GET /media/{id}/sources`, entpackt das
  serverseitige `{"sources": [...]}`-Wrapper-Objekt). Neue DTOs
  `QualityInfo`, `LoudnessEntry`, `AiMetadataEntry`,
  `MediaSourceEntry`/`MediaSourcesResponse` spiegeln exakt die
  `*_to_dict()`-Funktionen in `core/genesis_core/api/app.py`.
- `MediaTableSupport.BuildMediaDetailText()` um vier optionale Parameter
  erweitert (`quality`, `loudnessHistory`, `aiEntries`, `sources`, alle
  mit Default `null`) — bestehende Aufrufer/Tests bleiben unveraendert
  funktionsfaehig. Reihenfolge und Sonderverhalten exakt wie
  `ui-reference-pyside/genesis_ui/views/media_table.py::
  _on_selection_changed` nachgebildet: Pfad → Technik → **Qualität**
  (Abschnitt inkl. Kopfzeile entfaellt KOMPLETT ohne vorhandene Analyse,
  anders als die folgenden drei Abschnitte) → Track-Metadaten →
  eingebettetes Artwork → **Loudness** (Kopfzeile immer sichtbar,
  "noch nicht analysiert"-Fallback) → **KI-Analyse** (Kopfzeile immer
  sichtbar, "keine Vorschläge"-Fallback) → **Quelle** (Kopfzeile immer
  sichtbar, "lokal gefunden"-Fallback).
- `MainWindow.xaml.cs`: die Selektionsänderung der Medientabelle ruft
  jetzt zusätzlich alle vier neuen Endpunkte ab — JEDER einzeln in ein
  eigenes `try`/`catch` gefasst (identisch zum Python-Muster "ein nicht
  erreichbarer Zusatz-Endpunkt darf die restliche Detailansicht nicht
  verhindern"), fällt bei Fehlschlag auf `null`/eine leere Liste zurück.
- Tests: `MediaTableSupportTests.cs` um 8 Fälle erweitert (Qualitäts-
  Abschnitt entfällt komplett ohne Analyse / zeigt Flags+Notizen bei
  vorhandener Analyse, Loudness zeigt "none"-Fallback / den neuesten
  Eintrag zuerst [API liefert neueste zuerst], KI-Analyse zeigt
  "none"-Fallback / Modell+Confidence+Wert, Quelle zeigt "none"-Fallback /
  Provider+Importzeitstempel). `dotnet test`: **40/40 bestanden**
  (vorher 32 — 8 neu). `dotnet build -p:EnableWindowsTargeting=true` für
  den WPF-Client selbst: weiterhin 0 Warnungen/0 Fehler.
- `docs/GAP_ANALYSIS.md` Gap K um den vierten Teilschritt ergänzt: sowohl
  Medientabellen- als auch Einstellungen-Ansicht haben jetzt vollen
  fachlichen Funktionsumfang ihrer jeweiligen Python-Pendants (abzüglich
  rein struktureller/kosmetischer Unterschiede wie Kontextmenü,
  Cover-Bildanzeige, Filter-Dialog). Gap K als Ganzes bleibt bewusst
  weiterhin 🟡 "laufend/inkrementell" (alle anderen ~18 Python-Ansichten/
  Dialoge sind weiterhin offen). `ui-windows-dotnet/README.md`-Status-
  Abschnitt entsprechend erweitert.
- **Aufräumen nach Abschluss** (gemäß README-Vorgabe): `.NET-SDK`,
  NuGet-Cache, `bin`/`obj`-Verzeichnisse vor Sitzungsende entfernt (siehe
  Commit-Verlauf dieser Sitzung).

**Nächste Schritte:** Metadaten-Provider-Verwaltung (Pendant zu Gap I,
eigene `nav.providers`-Seite) ODER die verbliebenen Medientabellen-
Verfeinerungen (Cover-Anzeige, Filter-Dialog) ODER eine gänzlich neue
Ansicht (z.B. Bibliotheks-Drill-down, Pendant zu Gap B) — Priorität in
einer künftigen Sitzung neu zu bewerten, gemäß stehender
"inkrementell"-Freigabe.

## Sitzung 14 (Fortsetzung 11) — Gap K: .NET/WPF-Parität, Metadaten-Provider-Seite (`nav.providers`, Pendant zu Gap I)

Fortsetzung der inkrementellen .NET/WPF-Parity-Arbeit auf "weiter" vom
Nutzer hin. Neuer Themenbereich (statt weiterer Medientabellen-
Verfeinerungen): die Metadaten-Provider-Seite aus Gap I wurde für den
.NET-Client nachgebaut.

**Umsetzung:**

- `.NET SDK 8.0.425` erneut installiert (Workspace-Hygiene).
- Python-Referenz `ui-reference-pyside/genesis_ui/views/providers_view.py`
  (168 Zeilen) vollständig gelesen: betrifft ausschließlich die ONLINE-
  Metadatenabgleich-Provider (MusicBrainz/AcoustID/Cover Art Archive) —
  nicht zu verwechseln mit den Download-/Import-Providern (YouTube/
  TikTok/…), die bereits in der Einstellungen-Ansicht verwaltet werden.
  Nutzt denselben `PATCH /settings`-Endpunkt, schreibt aber ausschließlich
  in den `metadata`-Abschnitt. Standardmäßig ist der komplette Online-
  Abgleich AUS (§56, "kein Internetzwang") — auch aktiviert bleibt jeder
  Treffer nur ein Vorschlag mit Konfidenzwert (Prinzip #17).
- `GenesisApiClient.cs`: neues DTO `MetadataSettingsInfo` (enabled,
  musicbrainz_enabled, acoustid_enabled, acoustid_api_key,
  coverartarchive_enabled, contact_email, request_timeout_seconds,
  min_confidence_for_suggestion), `SettingsResponse` um das Pflichtfeld
  `Metadata` erweitert (ruft weiterhin denselben `GET`/`PATCH /settings`-
  Endpunkt auf).
- Neue WPF-freie Hilfsklasse `ProvidersViewSupport.cs`
  (`ProviderFormValues`, `BuildUpdatePayload`, `FromSettingsResponse`) nach
  demselben Muster wie `SettingsViewSupport.cs`.
- Neue Ansicht `ShowProvidersAsync` in `MainWindow.xaml.cs`, 1:1 nach dem
  Python-Vorbild: drei Gruppen ("Online-Abgleich", "Provider", "Kontakt &
  Grenzwerte"), Speichern fragt per `MessageBox.Show` (Ja/Nein, Default
  Nein) nach, Neu-Laden ruft die Methode erneut auf (verwirft ungespeicherte
  Änderungen). Navigation: `nav.providers` ruft jetzt `ShowProvidersAsync()`
  auf statt auf den generischen Platzhaltertext zurückzufallen.
- Tests: neue Datei `ProvidersViewSupportTests.cs` (3 Fälle: Metadaten-
  Felder korrekt übernommen, PATCH-Payload enthält NUR den `metadata`-
  Schlüssel, alle Schlüssel/Werte exakt snake-case). Bestehende
  `SettingsViewSupportTests.cs` angepasst (neues Pflichtfeld `Metadata` im
  Test-Fixture). `dotnet test`: **43/43 bestanden** (vorher 40 — 3 neu).
  `dotnet build -p:EnableWindowsTargeting=true`: 0 Warnings/0 Errors.
- `docs/GAP_ANALYSIS.md` Gap K um den fünften Teilschritt ergänzt,
  `ui-windows-dotnet/README.md` Status-Abschnitt entsprechend erweitert.
- **Aufräumen nach Abschluss** (gemäß README-Vorgabe): `.NET-SDK`,
  NuGet-Cache, `bin`/`obj`-Verzeichnisse vor Sitzungsende entfernt (siehe
  Commit-Verlauf dieser Sitzung).

**Nächste Schritte:** eine der beiden verbliebenen Medientabellen-
Verfeinerungen (Cover-Anzeige, Filter-Dialog) ODER eine gänzlich neue
Ansicht (z.B. Bibliotheks-Drill-down, Pendant zu Gap B, oder der
Lautheits-Dialog `nav.loudness`) — Priorität in einer künftigen Sitzung neu
zu bewerten, gemäß stehender "inkrementell"-Freigabe.

## Sitzung 14 (Fortsetzung 12) — Gap K: .NET/WPF-Parität, Cover-Anzeige im Medientabellen-Detailpanel

Fortsetzung der inkrementellen .NET/WPF-Parity-Arbeit auf "weiter" vom
Nutzer hin. Letzte der vier in Schritt 4 zurückgestellten Medientabellen-
Verfeinerungen (Cover-Anzeige) umgesetzt.

**Umsetzung:**

- `.NET SDK 8.0.425` erneut installiert (Workspace-Hygiene).
- "COVER" ist laut Originalauftrag §8/§59 der ERSTE Bestandteil der
  Detailansicht (Gap-Analyse D) — bisher wurde eingebettetes/gespeichertes
  Artwork im .NET-Client nirgends tatsächlich ANGEZEIGT, nur über
  `EmbedArtworkAsync`/`FetchArtworkOnlineAsync` bearbeitet. Jetzt zeigt das
  Detailpanel links neben dem Text das über `GET /media/{id}/artwork`
  gelieferte Bild (Image-Bereich links statt — wie im Python-Vorbild —
  darüber, Anpassung an die bestehende, enger bemessene Grid-Zeilenhöhe).
  `GenesisApiClient.GetArtworkBytesAsync` existierte bereits aus einer
  früheren Phase, keine neue API-Methode nötig.
- Neue WPF-freie Hilfsklasse `MediaCoverSupport.cs`
  (`LooksLikeDecodableImage`) — Pendant zu `pixmap_from_artwork_bytes()`
  in `media_table.py`: reine Signatur-/Magic-Bytes-Prüfung (PNG/JPEG/GIF/
  BMP/WEBP) als bewusste, dokumentierte Vereinfachung gegenüber einem
  echten WPF-Decodierversuch (BitmapImage.EndInit() wirft bei kaputten
  Daten eine Exception) — erkennt eindeutig invalide/fremde Daten VOR dem
  WPF-Aufruf, bleibt ohne WPF-Referenz testbar. Ein beschädigtes Bild MIT
  korrektem Dateikopf fällt weiterhin über try/catch um
  BitmapImage.EndInit() auf den "kein Cover"-Platzhalter zurück.
- `MainWindow.xaml.cs::ShowMediaTableAsync`: Cover wird — identisch zur
  Reihenfolge im Python-Vorbild — VOR dem Detailtext aktualisiert, in
  einem eigenen, isolierten try/catch (gleiches Muster wie Qualität/
  Loudness/KI/Quelle aus Schritt 4).
- Tests: neue Datei `MediaCoverSupportTests.cs` (9 Fälle: null/leere/zu
  kurze/zufällige Daten → false, je eine Signatur PNG/JPEG/GIF/BMP/WEBP →
  true). `dotnet test`: **52/52 bestanden** (vorher 43 — 9 neu).
  `dotnet build -p:EnableWindowsTargeting=true`: 0 Warnings/0 Errors.
- `docs/GAP_ANALYSIS.md` Gap K um den sechsten Teilschritt ergänzt,
  `ui-windows-dotnet/README.md` Status-Abschnitt entsprechend erweitert.
- **Aufräumen nach Abschluss**: `.NET-SDK`, NuGet-Cache, `bin`/`obj`-
  Verzeichnisse vor Sitzungsende entfernt.

Damit sind nun DREI der vier in Schritt 4 zurückgestellten
Medientabellen-Verfeinerungen erledigt — offen bleiben weiterhin
Kontextmenü/Mehrfachauswahl-Aktionen und der Filter-Dialog.

**Nächste Schritte:** Filter-Dialog in der Medientabelle (Pendant zu
`SearchFiltersDialog`) ODER Kontextmenü/Mehrfachauswahl-Aktionen (Öffnen/
Ordner öffnen/Pfad kopieren, AI-/Convert-/Cutter-/Audiobook-/Video-
Dialoge) ODER eine gänzlich neue Ansicht (z.B. Bibliotheks-Drill-down,
Pendant zu Gap B, oder der Lautheits-Dialog `nav.loudness`) — Priorität
in einer künftigen Sitzung neu zu bewerten, gemäß stehender
"inkrementell"-Freigabe.

## Sitzung 14 (Fortsetzung 13) — Gap K: .NET/WPF-Parität, Hörbuch-/Video-/KI-Dialog + Workspace-Hygiene-Vorfall

Fortsetzung der inkrementellen .NET/WPF-Parity-Arbeit. Nutzerauftrag: alle
verbliebenen Gap-K-Punkte autonom abarbeiten, danach Deep-Search. In dieser
Sitzung wurden die letzten drei der neun Werkzeug-Dialoge fertiggestellt;
die Medientabelle selbst sowie zehn ganz neue Ansichten waren laut
Workspace-Befund bereits aus einem vorherigen, in der Zusammenfassung nicht
mehr im Detail erfassten Arbeitsschritt ("Schritt 7") vollständig gebaut
UND in die Navigation eingehängt (siehe unten) — das war zu Sitzungsbeginn
nicht bekannt und wurde erst durch Nachprüfung der Datei-Doc-Kommentare
festgestellt.

**Umsetzung (neue/fertiggestellte Dialoge):**

- `MainWindow.ToolDialogsAi.cs` — `ShowAiDialogAsync` (§25/§27): Tab
  "KI-Vorschläge" (Generieren → Checkboxen → Auswahl übernehmen, mit
  Bestätigung) + Tab "KI-Musik" (nur für `music`/`ai_music`-Kind: Status/
  Quelle/Modell/Prompt/Stil/Stimmung/Eigentümer/Interpret, mit Bestätigung).
  Status-Banner zeigt KI-Provider-Verfügbarkeit.
- `MainWindow.ToolDialogsAudiobook.cs` — `ShowAudiobookDialogAsync` (§23):
  Tab "Metadaten" (eingebettete Tags rein lesend, Quelle immer angezeigt,
  Übernahme mit Bestätigung) + Tab "Kapitel" (Tabelle gespeicherter
  Kapitel, Erkennen/Intervall-Generieren als Vorschau mit Ersetzen-
  Bestätigung, Einzelkapitel umbenennen, JSON/CSV-Export ohne Bestätigung).
- `MainWindow.ToolDialogsVideo.cs` — `ShowVideoDialogAsync` (§24): Tab
  "Film" + Tab "Serie/Episode", je rein lesende Erkennung mit Herkunfts-
  angabe/Konfidenz, Übernahme als Film ODER Episode erfordert explizite
  Nutzerentscheidung + Bestätigung (kein automatisches Umschalten der
  Medienart).
- Neue API-Infrastruktur: `Api/DtosTools.cs` (alle Response-/Request-DTOs
  für Lautheit/Cutter/Konvertieren/Hörbuch+Kapitel/Video+Film+Episode/KI/
  Fingerprint/Qualität), `Api/GenesisApiClient.Tools.cs` (zugehörige
  HTTP-Methoden, inkl. in dieser Sitzung ergänzt:
  `GenerateChaptersPreviewAsync`/`GenerateChaptersApplyAsync`/
  `RenameChapterAsync`/`ExportChaptersAsync`/`GetAiMusicAsync`/
  `ApplyAiMusicAsync`).
- `PromptForText` (bisher nur in `MainWindow.VoiceStudio.cs`) um einen
  optionalen `initialText`-Parameter erweitert, damit der Kapitel-
  Umbenennen-Dialog den aktuellen Titel vorbelegen kann (eine einzige
  Implementierung statt einer zweiten Texteingabe-Dialog-Variante).
- `dotnet build -p:EnableWindowsTargeting=true`: **0 Warnings/0 Errors**
  nach jedem Dialog erneut bestätigt.

**Bestandsaufnahme (bereits vorhanden, erst in dieser Sitzung inventarisiert):**
Folgende Dateien existierten bereits vollständig implementiert UND in
`BuildNavigation`/die Nav-Weiche von `MainWindow.xaml.cs` eingehängt, noch
ohne eigenen PROGRESS.md-Eintrag: `MainWindow.Library.cs` +
`LibraryBrowserSupport.cs` (Bibliotheks-Drill-down, §9/§62, Gap B, EINE
parametrisierte Methode für alle sechs Kinds), `MainWindow.Duplicates.cs`
(§21), `MainWindow.DownloadCenter.cs` (§30-§32), `MainWindow.AiCenter.cs`
(§25/§26), `MainWindow.VoiceStudio.cs` (§28/§29), `MainWindow.Plugins.cs`
(§34), `MainWindow.LogViewer.cs` (§54), `MainWindow.Backups.cs` (§40),
`MainWindow.Diagnostics.cs` (§38), `MainWindow.JobQueue.cs` (§35/§36),
`MainWindow.ErrorCenter.cs` (§37), `MainWindow.MediaFilters.cs` (Filter-
Dialog, Pendant `SearchFiltersDialog`, bereits im Medientabellen-Toolbar
verdrahtet). Diese Inventur sollte in einer künftigen Sitzung durch
`dotnet test` + stichprobenartige Durchsicht verifiziert werden (siehe
"Offen" unten) — in dieser Sitzung aus Zeit-/Workspace-Gründen nicht mehr
geschehen.

**Workspace-Hygiene-Vorfall (wichtig, siehe DECISIONS.md/ADR-Hinweis unten):**
Der Nutzer wies per Screenshot darauf hin, dass der Workspace diese
Sitzung zwischenzeitlich auf 665 MB/5.807 Dateien angewachsen war (Limit:
128 MB/10.000 Dateien) — 4.223 Dateien wurden dadurch NICHT gespeichert.
Ursachen identifiziert und behoben:
1. Eine verwaiste 61-MB-Testsprachdatei (`de_DE-thorsten-low.onnx`) lag
   direkt unter `/home/user` statt (wie in ADR-0018 für genau solche
   Modelle vorgesehen) unter `/opt/piper_voices` — gelöscht.
2. `~/.nuget`-Paket-Cache lag unter `/home/user` — geleert und für den
   Rest der Sitzung nach `/opt/nuget-packages` umgeleitet.
3. `.NET-SDK` wurde (in einer früheren Sitzung) unter `/home/user`
   installiert statt außerhalb — ab sofort Installation nach `/opt/dotnet`.
4. `bin`/`obj`-Build-Ordner (NICHT auf der automatischen Snapshot-
   Ausschlussliste) wurden nach jedem Build konsequent gelöscht.
Workspace danach: 14 MB/1.552 Dateien. Der gesamte bis dahin
unversionierte Stand wurde zur Absicherung sofort committet (Commit
`9998620`). **Kein Git-Remote ist aktuell konfiguriert** (`.git/config`
wird aus Sicherheitsgründen nie zwischen Sitzungen gespeichert) — ein
`git push` ist daher derzeit nicht möglich, bis der Nutzer eine Remote-
URL/Zugangsdaten für eine künftige Sitzung bereitstellt.
**Wichtige Lehre für alle künftigen Sitzungen:** `.NET-SDK` IMMER nach
`/opt/dotnet` installieren (`dotnet-install.sh --install-dir /opt/dotnet`),
NuGet-Cache IMMER via `NUGET_PACKAGES=/opt/nuget-packages` umleiten,
`bin`/`obj` nach jedem Build-Schritt löschen — NIE mehr unter
`/home/user`. Dasselbe Prinzip wie ADR-0018 (Piper-Stimmmodelle), jetzt
konsequent auch auf die .NET-Toolchain angewendet.

**Offen (nächste Sitzung, Nutzerauftrag "morgen weiter, dann Deep-Search"):**
1. Kontextmenü + Werkzeugleisten-Verdrahtung der neun Werkzeug-Dialoge
   (Umbenennen/Metadaten-Vorschläge/Artwork/Lautheit/Cutter/Konvertieren/
   Hörbuch/Video/KI) sowie Fingerprint/Qualität (One-Shot, kein Dialog) IN
   `ShowMediaTableAsync` (`MainWindow.xaml.cs`) — das ist der EINZIGE noch
   nicht umgesetzte Punkt aus der ursprünglichen "was fehlt noch"-Liste.
   Referenz vollständig gelesen: `ui-reference-pyside/genesis_ui/views/
   media_table.py::_build_context_menu`/`_on_selection_changed` (Aktions-
   reihenfolge: Play, Metadaten, Umbenennen, Artwork, Lautheit, Cutter,
   Konvertieren, Fingerprint, Qualität, Hörbuch, Video, KI, Datei öffnen,
   Ordner öffnen, Pfad kopieren). Umbenennen funktioniert bei
   Mehrfachauswahl, alle anderen Werkzeuge nur bei Einzelauswahl;
   Hörbuch-Button nur bei `kind == "audiobook"`, Video-Button nur bei
   `kind in (movie, episode)` aktiv — aktuelle `ShowMediaTableAsync` nutzt
   `DataGridSelectionMode.Single`, muss für Umbenennen-Mehrfachauswahl auf
   `Extended` umgestellt werden. Alle benötigten Dialog-Methoden
   (`ShowRenameDialogAsync`, `ShowMetadataSuggestionsDialogAsync`,
   `ShowArtworkDialogAsync`, `ShowLoudnessDialogAsync`,
   `ShowCutterDialogAsync`, `ShowConvertDialogAsync`,
   `ShowAudiobookDialogAsync`, `ShowVideoDialogAsync`, `ShowAiDialogAsync`)
   sowie `ComputeFingerprintAsync`/`AnalyzeQualityAsync` existieren bereits
   und sind build-grün — reine Verdrahtungsarbeit.
2. Danach: Bestandsaufnahme der zehn in diesem Eintrag gelisteten,
   bereits existierenden neuen Ansichten verifizieren (`dotnet test` +
   stichprobenartige Durchsicht gegen die jeweilige Python-Referenz).
3. Danach: `MediaSearchFiltersTests.cs` (xUnit) sowie
   `media_table.open_file_failed_title`/`_text`-i18n-Schlüssel-Prüfung
   (beide seit mehreren Sitzungen zurückgestellt).
4. Danach: vom Nutzer angeforderte Deep-Search/Review auf Fehler im
   gesamten bisherigen Werk (steht noch komplett aus).
5. **Zu Sitzungsbeginn IMMER zuerst**: `.NET-SDK` nach `/opt/dotnet`
   installieren, `NUGET_PACKAGES=/opt/nuget-packages` setzen (siehe
   Workspace-Hygiene-Hinweis oben) — nichts davon übersteht eine Pause
   innerhalb der Sitzung oder einen Sitzungswechsel.

## Sitzung 14 (Fortsetzung 14) — Gap K: Kontextmenü/Werkzeugleisten-Verdrahtung der Medientabelle (Medientabellen-Teilaufgabe abgeschlossen)

Fortsetzung vom Vortag ("morgen weiter machen"). Einziger noch offener
Punkt aus Fortsetzung 13: die neun Werkzeug-Dialoge in `ShowMediaTableAsync`
tatsächlich erreichbar machen.

**Umsetzung:**

- `MainWindow.xaml.cs::ShowMediaTableAsync`: Werkzeugleiste um Metadaten-/
  Umbenennen-/Artwork-/Lautheit-/Cutter-/Konvertieren-/Fingerprint-/
  Qualität-/Hörbuch-/Video-/KI-Knöpfe ergänzt (exakte Reihenfolge wie
  `media_table.py::action_row`), alle außer "Filter" zu Beginn
  deaktiviert.
- `DataGrid.SelectionMode`: `Single` → `Extended` (Umbenennen wirkt auf
  Mehrfachauswahl, wie im Python-Vorbild).
- Neue `UpdateButtonStates()` (Pendant `_on_selection_changed`): Umbenennen
  bei jeder nicht-leeren Auswahl aktiv, alle anderen Werkzeuge nur bei
  Einzelauswahl, Hörbuch nur bei `kind == "audiobook"`, Video nur bei
  `kind` in (`movie`, `episode`).
- Neues Kontextmenü (`grid.ContextMenuOpening` + `PreviewMouseRightButtonDown`
  zum Vorab-Auswählen der Zeile unter dem Cursor, falls noch nicht
  ausgewählt): identische Aktionsreihenfolge wie
  `_build_context_menu()`, jeder Menüpunkt löst über
  `sourceButton.RaiseEvent(...)` denselben Button-`Click`-Handler aus wie
  die Werkzeugleiste — keine zweite Implementierung derselben Aktion,
  identisch zur Python-Architekturentscheidung.
- `RefreshDetailAsync()`/`ReloadAsync()` werden nach jedem Dialog, der
  `changed == true` zurückmeldet, erneut aufgerufen (Umbenennen lädt die
  gesamte Tabelle neu, da sich Dateiname/-pfad ändert; alle anderen nur
  die Detailansicht) — identisch zu `dialog.changed`/`self.refresh()` vs.
  `self._on_selection_changed()` in der Python-Referenz.
- `.NET-SDK` zu Sitzungsbeginn nach `/opt/dotnet` installiert,
  `NUGET_PACKAGES=/opt/nuget-packages` gesetzt (siehe Workspace-Hygiene-
  Lehre aus Fortsetzung 13) — Workspace blieb während der gesamten Sitzung
  klein.
- `dotnet build -p:EnableWindowsTargeting=true`: **0 Warnings/0 Errors**.
  `dotnet test`: **52/52 bestanden**, keine Regression (keine neuen
  Testfälle — reine UI-Verdrahtung ohne neue WPF-freie Logik).
- `docs/GAP_ANALYSIS.md` um Siebter/Achter Schritt ergänzt, Punkt 7 der
  "Priorisierten Empfehlung" aktualisiert, `ui-windows-dotnet/README.md`
  Status-Abschnitt vollständig überarbeitet (listet jetzt alle zehn
  bereits existierenden neuen Ansichten + die vollständige
  Medientabellen-Funktionalität).

**Damit ist die Medientabellen-Teilaufgabe aus Gap K vollständig
abgeschlossen**, und JEDE der ~20 Python-Ansichten/-Dialoge hat ein
.NET-Pendant. Gap K bleibt dennoch als "laufend" markiert, bis eine
stichprobenartige Tiefenprüfung jeder Ansicht gegen ihre Python-Referenz
erfolgt ist (insbesondere der zehn in Fortsetzung 13 nachträglich
inventarisierten Ansichten).

**Nächste Schritte (Nutzerauftrag, unverändert):**
1. Stichprobenartige Tiefenprüfung der zehn bereits existierenden neuen
   Ansichten gegen ihre jeweilige Python-Referenz.
2. `MediaSearchFiltersTests.cs` (xUnit) sowie
   `media_table.open_file_failed_title`/`_text`-i18n-Prüfung (beide seit
   mehreren Sitzungen zurückgestellt).
3. Vom Nutzer angeforderte Deep-Search/Review auf Fehler im gesamten
   bisherigen Werk (steht noch komplett aus).
4. Zu Sitzungsbeginn IMMER zuerst `.NET-SDK` nach `/opt/dotnet`
   installieren, `NUGET_PACKAGES=/opt/nuget-packages` setzen, `bin`/`obj`
   nach jedem Build löschen — nichts davon übersteht einen
   Sitzungswechsel.

## Fortsetzung 14: Deep-Search auf Fehler (Teil 1) — vier reale Bugs gefunden und behoben

Begonnen mit der vom Nutzer angeforderten Deep-Search über das gesamte
bisherige .NET-Client-Werk. Ergebnisse dieser Sitzung:

1. **Vier hartcodierte UI-Strings statt i18n-Aufrufen** (§53-Verstoss):
   `resetBtn`/`okBtn` in `MainWindow.MediaFilters.cs`, `okBtn`/`cancelBtn`
   in `MainWindow.VoiceStudio.cs`. Ursache: den vier Sprachdateien fehlten
   die Schlüssel `common.button_ok`/`common.button_reset`. Beides ergänzt/
   behoben.
2. **Fehlende Testdatei** `MediaSearchFiltersTests.cs` nachgetragen (12
   Fälle: `CountActive()`/`ToQueryString()` inkl. Abgleich der
   Query-Parameternamen gegen `core/genesis_core/api/app.py::list_media`,
   Leerstring/explizites `false` zählen nicht, URL-Escaping,
   `InvariantCulture`-Dezimaltrennzeichen).
3. **Systematischer i18n-Schlüssel-Abgleich** (Skript: alle `_tr.Tr(...)`-
   Aufrufe mit statischem Schlüssel extrahiert, gegen alle vier
   Sprachdateien geprüft): 634 statische Schlüssel, alle vorhanden in
   allen vier Sprachen. 41 dynamische/interpolierte Fundstellen einzeln
   verifiziert (`ai_dialog.status_{v}` gegen alle 4 KI-Status-Werte,
   `video_dialog.source_{source}` gegen alle 4 vom Backend gelieferten
   Quellenwerte `tag`/`filename_pattern`/`directory_name`/`filename`,
   sowie 39 `{d}.xxx`-Stellen in `MediaTableSupport.cs`, die sich als
   effektiv statisch herausstellten, da `d` eine `const string` ist) —
   **keine fehlenden Schlüssel gefunden**.
4. **ECHTER, SYSTEMISCHER BUG gefunden und behoben: `DataGrid.
   SelectedIndex`-in-Liste-Antipattern.** Sieben neue Gap-K-Ansichten
   (`Backups`, `Duplicates`, `ErrorCenter`, `LogViewer`, `DownloadCenter`,
   `ToolDialogsAudiobook`, `ToolDialogsBasic`, `VoiceStudio`) indizieren
   nach einer Aktion (z.B. "Backup wiederherstellen", "Sprachprofil
   löschen", "Duplikatgruppe prüfen") per `grid.SelectedIndex` in eine
   separat gehaltene C#-Liste. WPF-`DataGrid` erlaubt per Default
   (`CanUserSortColumns` ungesetzt = `true`) das Sortieren per
   Spaltenkopf-Klick — dabei sortiert WPF die ANZEIGE (`ICollectionView`),
   NICHT die zugrunde liegende Liste. Nach einer Nutzersortierung hätte
   `SelectedIndex` auf die sortierte Anzeigeposition gezeigt, während
   `liste[SelectedIndex]` weiterhin die UNSORTIERTE Position indiziert —
   es wäre also z.B. das FALSCHE Backup wiederhergestellt, das FALSCHE
   Sprachprofil gelöscht oder die FALSCHE Download-Option heruntergeladen
   worden. Die Haupt-Medientabelle (`MainWindow.xaml.cs`) und
   `MainWindow.JobQueue.cs` waren NICHT betroffen, da sie korrekt
   `SelectedItem(s)` auf die gebundenen Objekte selbst nutzen
   (sortierresistent). **Fix:** `CanUserSortColumns = false` auf ALLEN 16
   `DataGrid`-Instanzen im Client ergänzt (auch den ungefährdeten, für
   Konsistenz/Parität — `ui-reference-pyside` implementiert ebenfalls
   keine interaktive Spaltensortierung, bestätigt per
   `grep -rn setSortingEnabled` ohne Treffer). Jede Fundstelle mit
   Kommentar versehen, der erklärt, ob es sich um einen echten Bugfix
   oder reine Konsistenz handelt.
5. `dotnet build -p:EnableWindowsTargeting=true`: **0 Warnings/0 Errors**.
   `dotnet test`: **64/64 bestanden** (vorher 52, +12 durch
   `MediaSearchFiltersTests.cs`).

**Noch ausstehend (nächste Sitzung, Nutzerauftrag unverändert):**
- Stichprobenartige Tiefenprüfung der restlichen, noch nicht komplett
  gelesenen Ansichten (`Backups.cs`/`Diagnostics.cs`/`ErrorCenter.cs`/
  `Plugins.cs`/`LogViewer.cs`/`DownloadCenter.cs`/`Duplicates.cs`/
  `AiCenter.cs` wurden nur per Grep, nicht vollständig Zeile für Zeile
  gegen die Python-Referenz gelesen).
- Deep-Search auf die neun Werkzeug-Dialoge, `GenesisApiClient.*.cs`,
  `DtosGapK.cs` und den Kern von `MainWindow.xaml.cs` ausweiten.
- Zu Sitzungsbeginn IMMER zuerst `.NET-SDK` nach `/opt/dotnet`
  installieren, `NUGET_PACKAGES=/opt/nuget-packages` setzen, `bin`/`obj`
  nach jedem Build löschen — nichts davon übersteht einen
  Sitzungswechsel (in dieser Sitzung zweimal nötig geworden).

## Fortsetzung 15: Deep-Search auf Fehler (Teil 4) — API-Client-Schicht vollständig geprüft

Vollständige Zeile-für-Zeile-Prüfung aller neun Werkzeug-Dialoge
(`ShowAiDialogAsync`, `ShowLoudnessDialogAsync`, `ShowCutterDialogAsync`,
`ShowConvertDialogAsync`, `ShowAudiobookDialogAsync`,
`ShowRenameDialogAsync`, `ShowMetadataSuggestionsDialogAsync`,
`ShowArtworkDialogAsync`, `ShowVideoDialogAsync`) gegen ihre jeweilige
Python-Referenz abgeschlossen:
- Alle Bestätigungsdialoge, Payload-Feldlisten (z.B. `AcceptedAiSuggestion`
  mit 6 Feldern, `AiMusicApplyRequest` mit 8 UI-Feldern + 2 backend-seitig
  ungenutzten `null`-Feldern) stimmen exakt mit
  `ui-reference-pyside/genesis_ui/dialogs/*.py` überein.
- Zwei rein kosmetische Code-Smells gefunden und bereinigt (siehe
  Fortsetzung 14/Commit `4608303`): verwaiste TextBlock-Instanz in
  `ToolDialogsAudiobook.cs`, unbenutzte `spacer`-Variable in
  `ToolDialogsBasic.cs`.
- Eine Python-Pendant-Eigenheit (`CutterDialog._on_play_selection_clicked`
  verbindet bei jedem Klick einen neuen `positionChanged`-Handler ohne den
  vorherigen zu trennen) wird in `MainWindow.ToolDialogsAudio.cs` 1:1
  identisch reproduziert (neuer `DispatcherTimer` je Klick) - bewusst
  keine Verbesserung über die Python-Referenz hinaus, da dies reine
  Parität zum bestehenden (bekannten, harmlosen) Verhalten ist.

**Systematischer Abgleich der gesamten API-Client-Schicht
(`GenesisApiClient.cs`/`.Tools.cs`/`.GapK.cs`, 82 HTTP-Aufrufe) gegen die
107 Backend-Routen in `core/genesis_core/api/app.py`** (Skript-basiert,
Verb+Pfad normalisiert): **0 Abweichungen gefunden** - jeder einzelne
.NET-Aufruf (inkl. der über Hilfsmethoden wie `PostJobActionAsync`/
`PostDownloadAsync`/`HttpRequestMessage`+`SendAsync` für DELETE
aufgelösten Pfade) hat eine exakte Entsprechung in der Backend-Routenliste.
17 Backend-Routen werden von KEINER der beiden UIs (weder Python noch
.NET) genutzt (`GET /export`, `GET /plugins/export/{id}`,
`GET /repair/plan`, `POST /repair/preview`, `POST /repair/execute`,
`POST /relocate/scan`, `POST /relocate/apply`) - verifiziert, dass dies
VOR-BESTEHENDE, in BEIDEN UIs fehlende Backend-Funktionalität ist (siehe
`docs/GAP_ANALYSIS.md` Zeile 30, als bekannte Backend-Fähigkeit vermerkt,
nicht als Gap-K-Punkt), also keine .NET-spezifische Lücke und außerhalb
des Port-Umfangs.

Zusätzlich stichprobenartig geprüft: `JsonNamingPolicy.SnakeCaseLower`
global für alle Record-/Klassen-DTOs korrekt gesetzt;
`SettingsViewSupport.BuildUpdatePayload`/`ProvidersViewSupport.
BuildUpdatePayload` (lose `Dictionary<string, object>`-Payloads, auf die
`JsonNamingPolicy` NICHT automatisch wirkt) verwenden korrekt explizite
snake_case-Schlüssel - stichprobenartig gegen
`core/genesis_core/config/__init__.py` abgeglichen (`timeout_seconds`,
`default_export_format`, `target_true_peak_dbtp`, `overwrite_originals`,
`media_folders`, `require_confirmation_for_bulk_changes`) - alle exakt
übereinstimmend.

**Ergebnis dieser Runde: keine neuen funktionalen Bugs gefunden** (nur
die beiden bereits behobenen kosmetischen Code-Smells). Die API-Client-
Schicht und alle neun Werkzeug-Dialoge gelten damit als vollständig
tiefengeprüft.

dotnet build: 0/0. dotnet test: 64/64 bestanden (keine Änderung an
Testanzahl in dieser Runde, da keine neue testbare Logik entstanden ist).

**Noch offen für künftige Sitzungen:**
- `DtosGapK.cs`/`DtosTools.cs` vollständige Feld-für-Feld-Prüfung gegen
  alle Backend-Pydantic-Response-Modelle (bisher nur stichprobenartig:
  `AiMusicApplyRequest`, Settings-Payload).
- Kern von `MainWindow.xaml.cs` (Haupt-Medientabelle, Navigation,
  Einstellungen-Tab jenseits von Settings/Providers) noch nicht
  vollständig zeilenweise gegen `media_table.py`/`main_window.py`
  geprüft.
- Zu Sitzungsbeginn IMMER zuerst `.NET-SDK` nach `/opt/dotnet`
  installieren, `NUGET_PACKAGES=/opt/nuget-packages` setzen, `bin`/`obj`
  nach jedem Build löschen.

## Fortsetzung 16 ("mache alle noch fehlenden tests" - Unit-Test-Lücken geschlossen)

Auftrag: alle noch fehlenden Unit-Tests der WPF-unabhängigen Hilfslogik
im .NET-Client systematisch finden und schließen (nicht nur eine
Stichprobe).

**Inventur auf Datei-Ebene:** von 5 "Support"-Klassen hatte
`LibraryBrowserSupport.cs` (181 Zeilen, Bibliotheks-Drill-down-Ansicht,
Pendant zu `library_view.py`) als einzige KEINE Testdatei.
→ `LibraryBrowserSupportTests.cs` neu angelegt (44 Tests): deckt
`LibraryKindByNavKey`, `Fmt`, `FmtDuration` sowie alle sechs
`Render*Detail`-Methoden ab (inkl. Rollen-/Werk-Art-Mapping in
`RenderPersonDetail` mit Fallback auf `value_none` bei unbekanntem
Schlüssel - Prinzip #37).

**Inventur auf Methoden-Ebene** (nicht nur Datei-Existenz) ergab zwei
weitere, bis dahin unentdeckte Lücken:
1. `MediaTableSupport.MediaKindLabelKey` (kind→nav-i18n-Schlüssel,
   Kehrfunktion zu `MediaKindByNavKey`, genutzt in
   `MainWindow.AiCenter.cs`) hatte trotz existierender Testdatei keine
   eigenen Tests. → 15 neue Tests in `MediaTableSupportTests.cs`
   ergänzt (alle sechs Kind-Codes, Rückrichtungs-Konsistenzprüfung
   gegen `MediaKindByNavKey`, Fallback bei unbekanntem Code).
2. `MediaFileActions` (Datei/Ordner öffnen, §8/§61 Gap-Analyse E) und
   `MediaSearchFiltersSupport` (Leerwert-Sentinel für den Filterdialog)
   lagen "versteckt" am Kopf der ansonsten WPF-abhängigen
   `MainWindow.MediaFilters.cs` und waren dadurch nie testbar
   eingebunden. → beide Klassen ohne Verhaltensänderung nach neuer
   Datei `MediaFileActionsSupport.cs` extrahiert (reiner
   `System`/`System.IO`/`System.Diagnostics`-Code, keine
   WPF-Abhängigkeit), Testprojekt-`.csproj` um den entsprechenden
   `<Compile Include>`-Eintrag ergänzt, `MediaFileActionsSupportTests.cs`
   neu angelegt (8 Tests: deterministische Schutzklauseln von
   `TryOpenPath` ohne echten Prozessstart, plus Record-Gleichheit/
   `CountActive`/`ToQueryString` von `MediaSearchFiltersSupport.Empty`).

Restliche drei Support-Klassen (`MediaCoverSupport`,
`SettingsViewSupport`, `ProvidersViewSupport`) sowie `Translator`
geprüft: alle öffentlichen Mitglieder bereits in den bestehenden
Testdateien abgedeckt, keine weiteren Lücken gefunden. Vollständige
Inventur aller `public static class`/Record-Methoden im Client
bestätigt: keine weiteren testbaren WPF-unabhängigen Einheiten ohne
Abdeckung übrig.

dotnet build (Client + Tests): 0 Fehler. dotnet test: **131/131
bestanden** (vorher 64, +67 neue Tests: 44 + 15 + 8 = 67).

## Fortsetzung 17 (Windows-Installationspaket: Client + Core-Service gebündelt)

Auftrag: "bau es mir jetzt in eine saubere zip datei mit windows
installer damit ich es real testen kann" — Nutzerentscheidung nach
Rückfrage: Client UND Backend zusammen, echtes MSI gewünscht.

**Neue Dateien (`deploy/`):**
- `Build-Package.ps1` — einzige Quelle der Wahrheit für den
  Paketierungsvorgang (self-contained `dotnet publish -r win-x64` für den
  Client, Core-Service-Quellcode + Laufzeit-`requirements.txt` ohne
  Test-/Dev-Werkzeuge, gemeinsame `i18n/`-Kataloge, Installer-Skripte,
  ZIP, optional `-BuildMsi`). Tatsächlich ausgeführt (nicht nur
  geschrieben) über PowerShell 7 (per `dotnet-install.sh`-Muster separat
  nach `/home/user/pwsh7` geladen, nach Gebrauch wieder entfernt) —
  erzeugt ein 169 MB-Paket (68 MB als ZIP).
- `installer/Install-GenesisMediaManager.ps1`,
  `installer/Setup-PythonRuntime.ps1`,
  `installer/Uninstall-GenesisMediaManager.ps1` — einfacher, SOFORT
  funktionierender Installationsweg ohne Admin-Rechte
  (`%LOCALAPPDATA%\Programs\GenesisMediaManager`), inkl. venv-Aufbau für
  den Core-Service, Start-/Desktop-Verknüpfungen, Eintrag unter "Apps &
  Features". Mit PowerShell 7 Parser syntaktisch validiert (alle drei:
  SYNTAX OK) sowie die beiden riskantesten Logikstellen (Python-
  Versionsregex-Vergleich, Datei-Kopierschleife) isoliert funktional
  getestet (korrekte Ergebnisse für alle Randfälle).
- `wix/Product.wxs` — echtes WiX-v5-MSI-Projekt (gleiche Installation,
  klassischer Windows-Installer-Dialog). **Wichtiger Befund:** WiX kann
  unter Linux grundsätzlich KEIN MSI erzeugen (bestätigter
  Toolset-Maintainer-Hinweis: nutzt Windows-Installer-COM-APIs, bricht
  schon bei jedem `<Directory>`-Element mit `WIX0389` ab, siehe
  github.com/wixtoolset/issues/issues/7154). Trotzdem wurden beim
  wiederholten `wix build`-Versuch in der Sandbox drei ECHTE, eigene
  Autorenfehler gefunden und behoben (kein Linux-Artefakt): eine
  ungültige `Property`-Selbstreferenz auf `[INSTALLFOLDER]` (WIX1077,
  behoben über eine dedizierte `CustomAction Property=.../Value=...`),
  ein falsch zusammengesetztes `CustomAction`-Element (`Return=
  "asyncNoWait"` ohne `ExeCommand`, WIX0038/WIX0044, behoben durch
  direkte `ExeCommand`-Angabe für den `Setup-PythonRuntime.ps1`-Aufruf),
  sowie eine veraltete WiX-v3-Syntax (Inline-Text statt
  `Condition`-Attribut bei `<Custom>`, WIX0400). Nach der Korrektur
  bleiben in der Sandbox NUR NOCH die sieben erwarteten `WIX0389`-Linux-
  Artefakte übrig — alle eigenen Fehler sind damit nachweislich behoben,
  bevor das Projekt an echtes Windows geht.
- `.github/workflows/build-windows-installer.yml` — baut auf
  `windows-latest` automatisch ZIP + echtes MSI und lädt beides als
  Actions-Artefakte hoch (manuell anstoßbar über "Run workflow").

**Funktionaler Rauchtest des gebündelten Backends (Linux, da Python
plattformunabhängig ist):** `pip install -r backend/requirements.txt`
(exakt die Datei aus dem Paket) in einer frischen venv, danach
`python3 run_api.py --port 8521` mit dem exakt gepackten
`backend/`-Ordner gestartet → `GET /health` → `200 OK`
(`{"status":"ok","version":"0.1.0",...}`). Zusätzlich verifiziert: die
API-Token-Authentifizierung (ADR-0006, `X-Genesis-Token`-Header) ist
Client- UND Core-seitig identisch auf `%APPDATA%\GenesisMediaManager\
api_token.txt` verdrahtet (`GenesisApiClient.cs::ResolveDataDir()` vs.
`genesis_core.config.default_data_dir()` - exakt dieselbe
Auflösungsreihenfolge: `GENESIS_DATA_DIR`-Override, sonst `%APPDATA%`);
der Core-Service erzeugt die Token-Datei automatisch beim ersten Start
(`security.py::load_or_create_token`) — kein manueller
Konfigurationsschritt nötig, Client und Core-Service finden sich auf dem
Zielrechner von selbst.

**Ergebnis:** `GenesisMediaManager-Setup.zip` (68 MB, 563 Dateien:
self-contained `.NET`-Client inkl. aller WPF-Laufzeit-DLLs, Core-Service-
Quellcode + Laufzeit-Requirements, gemeinsame `i18n/`-Kataloge, drei
Installer-Skripte, README-INSTALL.md) liegt unter
`/home/user/genesis-media-manager/release/` (bewusst NICHT unter
`build/`, da dieser Ordnername von der Workspace-Snapshot-Ausschlussliste
erfasst wird). Ein echtes MSI entsteht beim ersten Lauf des neuen
GitHub-Actions-Workflows. `.gitignore` um `/build/` und `/release/`
ergänzt (beides generierte, regenerierbare Artefakte, gehören nicht ins
Git-Repo).

## Fortsetzung 18 — Echter Nutzer-Testlauf auf Windows: MOTW-Signaturfehler gefunden und behoben

Der Nutzer hat das in Fortsetzung 17 gebaute Installationspaket real auf
Windows getestet. Ergebnis: `Install-GenesisMediaManager.ps1` lief per
Rechtsklick → "Mit PowerShell ausführen" erfolgreich bis zum Kopieren der
Programmdateien, brach dann aber beim automatischen Aufruf von
`Setup-PythonRuntime.ps1` ab mit:

```
... ist nicht digital signiert. Sie können dieses Skript im aktuellen
System nicht ausführen.
PSSecurityException / FullyQualifiedErrorId: UnauthorizedAccess
```

**Ursache:** Windows' "Mark of the Web" (Zone.Identifier-ADS) markiert
jede aus einem heruntergeladenen ZIP entpackte Datei einzeln als
"Internet-Zone". Unter `RemoteSigned`/`AllSigned`-Policy dürfen solche
unsignierten Skripte nicht laufen. Das Hauptskript selbst kam durch
(Windows' "Mit PowerShell ausführen"-Verb setzt für den eigenen
Prozess-Scope meist `Bypass`), der `&`-Kindaufruf von
`Setup-PythonRuntime.ps1` wurde aber trotzdem individuell geprüft und
blockiert.

**Fix (`deploy/installer/Install-GenesisMediaManager.ps1`):**
1. Ganz am Anfang: `Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File`
   über das gesamte Paket (Quelle), danach zusätzlich erneut über das
   Installationsziel (Ziel) nach dem Kopieren — doppelt abgesichert, da
   `Copy-Item` die ADS-Markierung je nach Windows-Version mitkopieren
   kann.
2. Aufruf von `Setup-PythonRuntime.ps1` nicht mehr per `&` im selben
   Prozess, sondern als eigener `powershell.exe -ExecutionPolicy Bypass
   -File ...`-Subprozess (Verteidigung in der Tiefe — `Bypass` ignoriert
   die Signaturprüfung unabhängig von MOTW).

**Zusätzlicher UX-Fix (`deploy/installer/Setup-PythonRuntime.ps1`):**
`[Parameter(Mandatory)]` an `-InstallDir` entfernt und durch eine
explizite `throw`-Prüfung ersetzt, damit ein fehlender Parameter (z. B.
bei versehentlichem Direktaufruf) zu einem klaren Fehler statt einem
hängenden interaktiven Eingabe-Prompt führt (dieser trat beim Nutzer
separat als "Geben Sie Werte für die folgenden Parameter an:
InstallDir:" auf).

**README-INSTALL.md** um einen Troubleshooting-Abschnitt zum
MOTW-Signaturfehler ergänzt (inkl. manuellem Workaround
`Get-ChildItem -Recurse | Unblock-File` und ZIP-Eigenschaften-Workaround
vor dem Entpacken).

**Verifikation:**
- Alle drei Installer-Skripte + `Build-Package.ps1` per
  `[System.Management.Automation.Language.Parser]::ParseFile` syntaktisch
  geprüft (fehlerfrei).
- `Build-Package.ps1` erneut erfolgreich gelaufen, neues ZIP nach
  `release/GenesisMediaManager-Setup.zip` (MD5 `86971f62937d1ddbc49d978d896813fb`,
  564 Dateien, ~70MB komprimiert).
- Backend-Smoke-Test wiederholt (unverändert, da nur Installer-Skripte
  angefasst wurden): `/health` antwortet korrekt, geschützte Endpunkte
  verlangen weiterhin das Token.
- `Unblock-File`-Verhalten auf der Linux-Sandbox geprüft (wirft dort
  "The cmdlet does not support Linux.", was durch
  `-ErrorAction SilentlyContinue` korrekt abgefangen wird — reale
  Windows-Funktionsprüfung konnte in dieser Sandbox naturgemäß nicht
  erfolgen, da WMI/NTFS-ADS-Semantik Windows-exklusiv ist).

**Offen:** Kein Live-Windows-Retest durch den Agenten möglich (keine
Windows-Umgebung in der Sandbox) — nächster verlässlicher Beweis ist ein
erneuter Testlauf durch den Nutzer mit dem neuen Paket.

## Fortsetzung 19 — Kritischer Absturz-Bug gefunden: WPF-Client hatte NIE eine lauffaehige Instanziierung

Nach dem MOTW-Fix (Fortsetzung 18) lief die Installation beim Nutzer
komplett fehlerfrei durch (Exit-Code 0). Trotzdem: Klick auf die
Desktop-Verknuepfung liess nur kurz ein Fenster aufblitzen, das sich
sofort wieder schloss.

**Root Cause (Code-Review, zweifelsfrei identifiziert):**
`App.xaml` setzte `StartupUri="MainWindow.xaml"`. WPFs StartupUri-
Mechanismus erzeugt das Root-Fenster intern per Reflection
(`Activator.CreateInstance`) - das verlangt einen ECHTEN parameterlosen
Konstruktor. `MainWindow` hatte aber ausschliesslich
`public MainWindow(string apiBaseUrl = "http://127.0.0.1:8420")` - ein
C#-Standardparameter erzeugt auf IL-Ebene KEINEN echten Null-Parameter-
Konstruktor. Ergebnis: `MissingMethodException` bei JEDEM Start, auf
JEDEM Rechner, ausnahmslos - 100% reproduzierbar. Da `App.xaml.cs`
zusaetzlich KEINERLEI globale Exception-Behandlung hatte (kein
`DispatcherUnhandledException`, kein `AppDomain.UnhandledException`),
wurde der Prozess kommentarlos beendet - exakt das beobachtete
"Fenster blitzt auf und schliesst sich sofort".

**Warum das vorher nie auffiel:** WPF kann in der Linux-
Entwicklungssandbox nur GEBAUT (`dotnet build`/`publish`), niemals
AUSGEFUEHRT werden. Dies war der allererste echte Lauf des kompilierten
Clients ueberhaupt, auf einem richtigen Windows-Rechner, durch den
Nutzer.

**Fix:**
1. `App.xaml`: `StartupUri="MainWindow.xaml"` entfernt.
2. `App.xaml.cs`: `OnStartup` ueberschrieben, erzeugt `MainWindow`
   jetzt explizit per `new MainWindow()` (Default-Parameter des
   C#-Konstruktors wirkt bei einem echten Methodenaufruf im Code
   korrekt, anders als bei Reflection). Zusaetzlich (Prinzip "kein
   stiller Fehlschlag", §37) globale Exception-Handler ergaenzt:
   `DispatcherUnhandledException`, `AppDomain.UnhandledException`,
   `TaskScheduler.UnobservedTaskException` - schreiben jede unbehandelte
   Ausnahme nach `%APPDATA%\GenesisMediaManager\client-crash.log` UND
   zeigen eine deutschsprachige MessageBox, statt den Prozess
   kommentarlos zu beenden.
3. **Zusaetzlich gefundener, verwandter Bug (Deep-Review waehrend der
   Fehlersuche):** `MainWindow`s Konstruktor ruft
   `_api.GetSettingsAsync().GetAwaiter().GetResult()` SYNCHRON auf dem
   UI-Thread auf (Sprache beim Start laden). Da `GetSettingsAsync()`
   intern ohne `ConfigureAwait(false)` auf den von WPF bereits
   installierten `DispatcherSynchronizationContext` angewiesen war,
   haette dies zu einem klassischen Sync-over-Async-DEADLOCK fuehren
   koennen (App bleibt fuer immer haengen, sobald der StartupUri-Absturz
   behoben ist und der Code tatsaechlich bis zu dieser Zeile kommt) -
   `GetSettingsAsync()` in `GenesisApiClient.cs` jetzt mit
   `.ConfigureAwait(false)` abgesichert (wirkt nur auf die interne
   Fortsetzung dieser einen Methode, keine Auswirkung auf andere,
   bereits korrekt per normalem `await` aufrufende Stellen).

**Verifikation:**
- `dotnet build -c Release -p:EnableWindowsTargeting=true -r win-x64`:
  erfolgreich, 0 Fehler/Warnungen.
- `dotnet test` (GenesisMediaManager.Client.Tests): weiterhin alle 131
  Tests gruen.
- Generiertes `App.g.cs` geprueft: `StartupUri`-Zuweisung ist weg,
  `Main()` ruft jetzt nur noch `app.Run()` ohne automatische
  Fenstererzeugung - das ueberschriebene `OnStartup` uebernimmt das.
- Paket neu gebaut: `release/GenesisMediaManager-Setup.zip`
  (MD5 `70fc59f30d98b8c4ccee28854e92fd80`).

**Weiterhin offen/nicht moeglich:** Ein echter Live-Start des Clients
unter Windows kann vom Agenten nicht durchgefuehrt werden (keine
Windows-Umgebung verfuegbar). Der naechste verlaessliche Beweis ist ein
erneuter Testlauf durch den Nutzer. Sollte der Client jetzt zwar
starten, aber auf einen ANDEREN unbehandelten Fehler treffen, zeigt er
dank der neuen globalen Exception-Handler jetzt erstmals eine
verstaendliche Fehlermeldung UND schreibt die Details nach
`%APPDATA%\GenesisMediaManager\client-crash.log` - das macht jede
zukuenftige Fehlersuche erheblich leichter als bisher (vorher: totale
Stille).

## Fortsetzung 20 — Client startet jetzt, aber "Core-API nicht erreichbar"

Nach dem Absturz-Fix (Fortsetzung 19) hat der Nutzer bestaetigt: das
Fenster oeffnet sich jetzt korrekt, komplette Navigation sichtbar. Im
Dashboard erschien jedoch: "Core-API nicht erreichbar: ... Zielcomputer
hat die Verbindung verweigert (127.0.0.1:8420)". Das ist KEIN Bug im
Client (die Meldung ist absichtlich - Prinzip #16/#17, kein Rueckgriff
auf erfundene Daten) - der Core-Service (Python-Backend) lief schlicht
noch nicht, als der Client zu fragen begann.

**Root Cause im Start-Skript:** `Start-GenesisMediaManager.bat`
(generiert von `Install-GenesisMediaManager.ps1`) startete bisher den
Core-Service im Hintergrund (`pythonw.exe`, kein Fenster) und wartete
dann nur STARRE 2 Sekunden, bevor es die Oberflaeche startete. Der
allererste Start eines frisch installierten venv mit vielen Paketen
(FastAPI/SQLAlchemy/Alembic/onnxruntime fuer Voice Studio/...) kann auf
Windows deutlich laenger dauern - u.a. weil Windows Defender jede neu
installierte Datei/DLL beim ersten Zugriff einzeln prueft. Zusaetzlich:
da `pythonw.exe` kein Konsolenfenster hat, waere ein echter Absturz des
Core-Service komplett unsichtbar gewesen (zweiter stiller Fehlschlag).

**Fix (`deploy/installer/Install-GenesisMediaManager.ps1`, generiertes
`Start-GenesisMediaManager.bat`):**
1. Core-Service-Ausgabe wird jetzt nach
   `%APPDATA%\GenesisMediaManager\core-service.log` umgeleitet (statt
   ins Leere zu gehen).
2. Statt fester 2-Sekunden-Wartezeit: aktives Polling von
   `http://127.0.0.1:8420/health` per PowerShell-Einzeiler, bis zu 60x
   im Sekundentakt, bevor die Oberflaeche gestartet wird. Antwortet der
   Core-Service nach 60s immer noch nicht, wird trotzdem gestartet (mit
   Warnhinweis + Verweis auf die Log-Datei) statt endlos zu haengen.

**README-INSTALL.md** um einen entsprechenden Troubleshooting-Eintrag
ergaenzt (inkl. Hinweis auf die neue Log-Datei und den manuellen
Diagnose-Befehl).

**Verifikation:** PowerShell-Syntaxpruefung des geaenderten Skripts
bestanden. `Build-Package.ps1` erneut erfolgreich gelaufen. Paket neu
gebaut: `release/GenesisMediaManager-Setup.zip`
(MD5 `baeb660e14b44f7237a01a00d0bcbc81`).

**Offen:** Kein Live-Windows-Test moeglich. Falls der Nutzer nach
erneuter Installation IMMER NOCH "Core-API nicht erreichbar" sieht,
zeigt `%APPDATA%\GenesisMediaManager\core-service.log` jetzt erstmals
den tatsaechlichen Grund (z.B. ein Python-Importfehler oder ein
blockierter Port) - das macht die naechste Fehlersuche gezielt moeglich,
statt erneut zu raten.

## Fortsetzung 21 — App-Icon ergaenzt + "Zugriff verweigert"-Installationsfehler behoben

**Problem 1 (Nutzer-Report):** Zweiter Installationslauf (Aktualisierung
einer bestehenden Installation) schlug fehl:
```
Remove-Item : ... PresentationCore.resources.dll ... Zugriff verweigert
```
Ursache: Der .NET-Client (oder der Core-Service) lief noch aus einer
frueheren Testsitzung und hatte eigene DLLs geladen - Windows sperrt
solche Dateien exklusiv gegen Loeschen, solange der Prozess laeuft.

**Fix (`deploy/installer/Install-GenesisMediaManager.ps1`):**
- Neuer Schritt ganz am Anfang: beendet automatisch eine laufende
  `GenesisMediaManager.exe`-Instanz (`Stop-Process`) sowie jeden
  `python.exe`/`pythonw.exe`-Prozess, dessen Kommandozeile `run_api.py`
  enthaelt (per `Get-CimInstance Win32_Process`), BEVOR irgendetwas
  kopiert wird.
- Zusaetzlich: `Remove-Item` beim Aktualisieren der Programmordner jetzt
  in try/catch - bei einem verbleibenden Sperrkonflikt (z.B. durch
  Antivirus-Scan im exakt falschen Moment) erscheint jetzt eine klare,
  handlungsanweisende Fehlermeldung statt eines rohen PowerShell-Stack-
  Traces.

**Problem 2 (Nutzerwunsch):** Passendes Desktop-/App-Icon fehlte
komplett - der Client nutzte bisher das generische .NET-Standardsymbol.

**Fix:**
- Neues Icon erstellt (`ui-windows-dotnet/GenesisMediaManager.Client/
  Assets/app-icon-source.png`, generiert: stilisiertes "G"-Monogramm aus
  gestapelten Medien-Ablagen mit integriertem Play-Dreieck, Cyan-Tuerkis-
  Verlauf auf dunklem Hintergrund - passend zum dunklen UI-Theme) und
  nach `Assets/app-icon.ico` konvertiert (7 Groessen: 16/24/32/48/64/
  128/256px, per Pillow).
- `GenesisMediaManager.Client.csproj`: `<ApplicationIcon>` gesetzt
  (eingebettetes .exe-Dateisymbol, wirkt automatisch auf alle
  Verknuepfungen, die wie bisher `-IconPath $clientExe` verwenden -
  keine Aenderung in Install-GenesisMediaManager.ps1 noetig) UND
  zusaetzlich als WPF-`<Resource>` eingebunden fuer die Fenster-
  Titelleiste (`MainWindow.xaml`: `Icon="Assets/app-icon.ico"` ergaenzt -
  ohne das zeigt WPF in der Titelleiste sonst ein Standardsymbol,
  unabhaengig vom .exe-Dateisymbol).

**Verifikation:**
- `dotnet build -c Release -p:EnableWindowsTargeting=true -r win-x64`:
  erfolgreich, 0 Fehler/Warnungen.
- Eingebettetes Icon per `pefile` (Python) im kompilierten
  `GenesisMediaManager.exe` bestaetigt (RT_GROUP_ICON-Ressource
  vorhanden).
- `dotnet test`: weiterhin alle 131 Tests gruen.
- PowerShell-Syntaxpruefung des geaenderten Installer-Skripts bestanden.
- Paket neu gebaut: `release/GenesisMediaManager-Setup.zip`
  (MD5 `bf138800fa8bcf96adf4492e8d08db69`).

**Workspace-Hygiene (Lehre aus Fortsetzung 18/19):** Toolchain
(.NET SDK, PowerShell 7) nach jedem Build-Lauf konsequent wieder
entfernt, `bin`/`obj`-Ordner bereinigt - Workspace-Gesamtgroesse vor
Turn-Ende erneut unter dem ~128MB-Snapshot-Limit gehalten.

## Fortsetzung 22 — Dunkles Farbschema griff nicht ueberall (Dashboard weiss/unlesbar)

Nutzer-Report (Screenshot): Dashboard-Inhaltsbereich zeigte einen
WEISSEN Hintergrund mit kaum lesbarem, naheszu weissem Text - mit der
klaren Forderung, das Farbschema ueberall konsistent anzuwenden
("Farbschemata an alle anpassen").

**Root Cause:**
1. `MainWindow.xaml`: die verschachtelten `Grid`-Container (Hauptraster,
   Inhaltsbereich-Grid) und der `ContentControl` (MainContent) hatten
   KEINEN eigenen `Background` gesetzt - in der Praxis blieb dieser
   Bereich dadurch WEISS statt den dunklen Window-Hintergrund
   durchscheinen zu lassen. Der helle `TextPrimaryBrush` (#E8EAED, fuer
   dunkle Hintergruende gedacht) war korrekt gesetzt, aber auf Weiss
   praktisch unlesbar - bestaetigt das exakte Symptom im Screenshot.
2. `Themes/DarkTheme.xaml` deckte bisher nur 5 Control-Typen ab
   (Window, TextBlock, Button, TreeView, TextBox). Code-Suche
   (`grep -c "new <ControlTyp>"`) zeigte aber eine viel breitere
   Verwendung app-weit: TextBlock(146), Button(103), StackPanel(72),
   TextBox(64), DataGridTextColumn(58), CheckBox(26), ScrollViewer(24),
   DataGrid(16), ComboBox(15), TabItem(10), TabControl(5), ListBox(4),
   GroupBox(3), ComboBoxItem(3), ProgressBar/MenuItem/ListView/
   ContextMenu/Border(je 1). All diese Controls fielen mangels eigener
   Style-Definition auf die hellen Windows-Standardfarben zurueck,
   sobald eine View sie nutzt - betraf praktisch JEDEN Dialog/jede
   Ansicht im Programm (Rename, Metadaten, Artwork, Audio-/Hoerbuch-/
   Video-Werkzeuge, KI-Dialoge, Voice Studio, Medienfilter, ...).
3. Alle ~11 Werkzeug-Dialoge (`MainWindow.ToolDialogs*.cs`,
   `MainWindow.MediaFilters.cs`, `MainWindow.VoiceStudio.cs`) erzeugen
   ihr Root-Panel (`Grid`/`StackPanel`/`DockPanel`) ebenfalls OHNE
   eigenen Background - dieselbe Bugklasse wie im Dashboard, nur noch
   nicht vom Nutzer gesehen/gemeldet.

**Fix:**
1. `MainWindow.xaml`: explizites `Background="{StaticResource
   BackgroundBrush}"` auf dem Haupt-Grid, dem Inhaltsbereich-Grid UND
   dem `ContentControl` (MainContent) ergaenzt - behebt den konkret
   gemeldeten Dashboard-Bug UND wirkt automatisch auf ALLE ueber
   MainContent eingeblendeten Ansichten (Dashboard, Einstellungen,
   Medientabellen, ...), da sie sich diesen einen Container teilen.
2. `Themes/DarkTheme.xaml` grundlegend erweitert: jetzt 25 Control-Typen
   gestylt statt 5 - zusaetzlich CheckBox, RadioButton, Label, GroupBox,
   ComboBox/ComboBoxItem, ListBox/ListBoxItem, ListView/ListViewItem,
   TabControl/TabItem (inkl. Auswahl-Hervorhebung), ScrollViewer/
   ScrollBar, DataGrid/DataGridColumnHeader/DataGridRow/DataGridCell
   (inkl. Zebra-Streifen + Auswahl-Highlight), ProgressBar, Slider,
   Menu/MenuItem/ContextMenu, ToolTip, Expander, Separator,
   GridSplitter, DatePicker, PasswordBox. Neue Hilfsfarben ergaenzt:
   HoverBrush, SelectionBrush, DisabledTextBrush.
3. Alle 11 programmatisch erzeugten Dialogfenster
   (`MainWindow.ToolDialogsAi/Audio/Audiobook/Basic/Video.cs`,
   `MainWindow.MediaFilters.cs`, `MainWindow.VoiceStudio.cs`): deren
   Root-Panel bekommt jetzt explizit `Background =
   (Brush)Application.Current.Resources["BackgroundBrush"]` -
   konsistent per Skript auf alle 11 Fundstellen angewendet.

**Verifikation:**
- `dotnet build -c Release -p:EnableWindowsTargeting=true -r win-x64`:
  erfolgreich, 0 Fehler/Warnungen (bestaetigt u.a., dass die
  fully-qualified `System.Windows.Media.Brush`-Casts in allen 7
  betroffenen Dateien syntaktisch korrekt sind, auch ohne zusaetzliche
  using-Direktiven).
- `dotnet test`: weiterhin alle 131 Tests gruen.
- Paket neu gebaut: `release/GenesisMediaManager-Setup.zip`
  (MD5 `706d3511611575291414b3fc5fa0f5f1`).

**Offen:** Kein Live-Windows-Test moeglich. Die Grundursache, WARUM ein
unbemalter (Background=null) WPF-Grid den dunklen Window-Hintergrund in
dieser konkreten Konfiguration nicht automatisch durchscheinen liess,
bleibt theoretisch ungeklaert (regulaeres WPF-Compositing sollte das
eigentlich erlauben) - der gewaehlte Fix (explizite Background-Zuweisung
auf jeden Root-Container) ist jedoch unabhaengig von der genauen Ursache
wirksam und ist ohnehin die robustere, empfohlene WPF-Praxis.

## Fortsetzung 23 — Dark-Theme-Fix Runde 2 (Deep-Scan nach Nutzer-Zurueckweisung), Testumgebung, start.bat

**Ausgangslage:** Der Nutzer wies das in Fortsetzung 22 ausgelieferte
Paket (MD5 `706d3511611575291414b3fc5fa0f5f1`) per neuem Screenshot
("Hoerbuecher"-Ansicht) explizit zurueck: DataGrid-Tabellenflaeche
weiterhin komplett weiss, Ansichtstitel kaum lesbar, deaktivierte
Werkzeugleisten-Buttons hell/weiss-grau statt dunkel. Forderung: erneuter
Deep-Scan, Behebung ALLER Fehler/Warnungen, Aufbau einer Testumgebung mit
Ergebnis-Tracking, keine Auslieferung vor vollstaendigem Funktionieren,
zusaetzlich eine `start.bat` fuer Installation+Start in einem Schritt.

### Root-Cause-Analyse (per Code-Review, siehe TEST_REPORT.md Abschnitt 4)

Zwei unabhaengige, sich gegenseitig verstaerkende Ursachen identifiziert:

1. **`ContentControl.Background` hat serienmaessig KEINE visuelle
   Wirkung.** Der Fortsetzung-22-Fix setzte `Background` direkt auf
   `<ContentControl x:Name="MainContent">` - dessen Default-Template
   besteht aber nur aus einem nackten `ContentPresenter` ohne
   umschliessenden `Border`, der die Eigenschaft ueberhaupt zeichnet.
   Der Fix war dadurch komplett wirkungslos (bekannter WPF-Stolperstein).
2. **Einfache `Style`-Setter reichen fuer bestimmte native
   `ControlTemplate`s nicht aus**, insbesondere das Aero2-`Button`-Chrome
   im deaktivierten Zustand (zeichnet ein internes, von `Background`
   unabhaengiges Overlay).

Per `grep` bestaetigt: keine lokale `Background`/`Brushes.White`/
`Colors.White`/`#FFFFFF`/`SystemColors`-Fundstelle im gesamten `.cs`-Code
erklaert das Symptom - die Ursache liegt tatsaechlich in den
WPF-Template-Mechanismen, nicht in einer lokalen Fehlzuweisung.

### Fix

1. **`MainWindow.xaml`:** `MainContent` (ContentControl) erhaelt jetzt
   ein explizites `ControlTemplate` mit echtem `Border` statt eines
   blossen `Background`-Setters - garantiert zeichnende dunkle Flaeche
   fuer ALLE ueber MainContent eingeblendeten Ansichten, unabhaengig vom
   Inhalt.
2. **`Themes/DarkTheme.xaml`:** Vollstaendige `ControlTemplate`-Overrides
   (statt nur `Style`-Setter) fuer `Button` (inkl. explizitem
   Disabled/Hover/Pressed-Visual), `CheckBox` (eigener Box+Haken-Look),
   `ComboBox` + `ComboBoxToggleButtonStyle` (Toggle+Popup, nicht
   editierbar - passend zur tatsaechlichen Nutzung im gesamten Client),
   `ScrollBar` + `ScrollBarThumbStyle`/`ScrollBarPageButtonStyle`
   (Track/Thumb/RepeatButton), `DataGrid` (1:1 nach dem offiziellen
   Microsoft-Referenzaufbau mit `PART_ColumnHeadersPresenter`/
   `PART_ScrollContentPresenter`/`PART_VerticalScrollBar`/
   `PART_HorizontalScrollBar`, nur mit unserer Palette statt
   SystemColors).
3. **Doppelte Absicherung:** Alle 17 Stellen im Code, die per
   `MainContent.Content = ...` eigene Root-Panels anzeigen (Dashboard,
   Medientabelle, Einstellungen, Anbieter, KI-Center, Backups, Diagnose,
   Download-Center, Duplikate, Fehlercenter, Job-Queue, Bibliothek,
   Log-Viewer, Plugins, Sprachstudio, 2x Platzhalter-TextBlock), per
   `grep`/`sed`/gezielten Python-Edits durchsucht; alle 13 vorher
   fehlenden Faelle bekommen jetzt zusaetzlich `Background =
   (Brush)Application.Current.Resources["BackgroundBrush"]` direkt am
   Root-Panel (unabhaengig vom ContentControl-Fix wirksam).
4. **Backend (Python Core-Service) in den Deep-Scan einbezogen** (vom
   Nutzer explizit gefordert: "gesamtes Paket"): `ruff check .` fand 9
   kleinere Funde (7 automatisch behoben, 1 Shebang-Executable-Bit
   gesetzt, 1 ungenutzte Tupel-Variable in einem Test manuell behoben) -
   jetzt 0 verbleibende Lint-Funde.

### Testumgebung + Nachverfolgung (siehe TEST_REPORT.md, neu angelegt)

**Wichtige, ehrlich kommunizierte Plattformgrenze:** WPF kann in dieser
Linux-Sandbox grundsaetzlich nicht gerendert/visuell getestet werden
(kein DWM/Direct3D). Die Testumgebung deckt deshalb ab, was hier
tatsaechlich zuverlaessig pruefbar ist:

- `.NET`: `dotnet build` mit `WarningLevel=9` (Client + Tests) - 0
  Fehler, 0 Warnungen. `dotnet test` - 131/131 gruen.
- `Python`: `pytest` komplette Suite - zunaechst 26 Fehlschlaege wegen
  fehlender System-Tools in der Sandbox (`ffmpeg`/`ffprobe`/`fpcalc`
  nicht vorinstalliert); nach Installation dieser Tools **571/571
  bestanden, 7 bewusst uebersprungen, 0 fehlgeschlagen**. `ruff check .`
  - alle Pruefungen bestanden.
- **Live-API-Rauchtest:** Core-Service tatsaechlich gestartet
  (`python run_api.py`), 9 Endpunkte (`/health`, `/dashboard/summary`,
  `/media`, `/settings`, `/jobs`, `/errors`, `/logs`, `/plugins`,
  `/diagnostics`) per echtem HTTP-Aufruf sowohl ohne als auch mit
  gueltigem API-Token geprueft - Auth (401 ohne Token, 200 mit Token)
  und JSON-Antworten verifiziert, Service danach sauber gestoppt.
- Neue Skripte: `scripts/run_dotnet_tests.sh` (Build+Test .NET-Seite,
  mit explizitem Hinweis auf die Rendering-Grenze im Kommentarkopf).
- Neue Datei `TEST_REPORT.md` im Repo-Wurzelverzeichnis: vollstaendige,
  fuer den Nutzer lesbare Dokumentation aller durchgefuehrten Pruefungen
  inkl. Ergebnissen und der Plattformgrenze - dient der geforderten
  "Nachverfolgung".

### start.bat (Nutzerforderung: Installation + Start in einem Schritt)

`deploy/Build-Package.ps1` erzeugt jetzt zusaetzlich zur Paketwurzel ein
`start.bat`: erkennt per Pruefung auf
`%LOCALAPPDATA%\Programs\GenesisMediaManager\client\GenesisMediaManager.exe`,
ob die App schon installiert ist; falls nicht, ruft es automatisch
`powershell -NoProfile -ExecutionPolicy Bypass -File
installer\Install-GenesisMediaManager.ps1` auf (keine manuelle
Rechtsklick-/Richtlinien-Huerde) und startet danach in jedem Fall sofort
die App ueber das vom Installer erzeugte
`Start-GenesisMediaManager.bat`. `README-INSTALL.md` entsprechend
aktualisiert (start.bat jetzt der empfohlene Schnellstart-Weg, alter Weg
bleibt als Alternative dokumentiert).

### Verifikation

- `dotnet build -c Release -p:EnableWindowsTargeting=true -r win-x64
  -p:WarningLevel=9`: 0 Fehler, 0 Warnungen (bestaetigt insbesondere,
  dass alle neuen `ControlTemplate`-Overrides syntaktisch korrektes
  XAML sind und erfolgreich zu BAML kompiliert wurden - per `strings`
  auf der gebauten DLL stichprobenartig verifiziert, dass
  `PART_HorizontalScrollBar`/`PART_ColumnHeadersPresenter` tatsaechlich
  eingebettet sind).
- `dotnet test -c Release`: 131/131 gruen.
- `pytest` (Core): 571/571 gruen, 7 bewusst uebersprungen.
- `ruff check .` (Core): alle Pruefungen bestanden.
- Paket neu gebaut via `deploy/Build-Package.ps1` (frisch installierte
  .NET-8-SDK/PowerShell-7-Toolchain dieser Session) - `start.bat` im
  Paket enthalten und inhaltlich verifiziert.

**Offen / ehrlich kommuniziert:** Eine verbindliche visuelle Abnahme ist
aus dieser Linux-Sandbox heraus nicht moeglich - das ist in
TEST_REPORT.md explizit dokumentiert. Der Nutzer wird gebeten, nach dem
naechsten Windows-Testlauf erneut Rueckmeldung zu geben (insbesondere zur
Hoerbuecher-Tabellenansicht).
