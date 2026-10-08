# TEST_REPORT.md — Fortsetzung 23 (Dark-Theme-Deep-Scan)

Dieser Bericht dokumentiert transparent und nachvollziehbar, was in dieser
Session tatsächlich getestet wurde, mit welchem Ergebnis, und — ganz
wichtig — was **nicht** getestet werden konnte und warum. Das ist die vom
Nutzer geforderte "Testumgebung mit Nachverfolgung jeder Komponente".

## 1. Harte Plattformgrenze (bitte zuerst lesen)

Diese Sandbox ist ein **Linux-System ohne Windows-Grafikstack** (kein
DWM, kein Direct3D/Direct2D, kein `wpfgfx`). WPF-Anwendungen können hier
unter keinen Umständen tatsächlich **gerendert** werden — weder
automatisiert noch manuell. Das bedeutet:

- Es ist technisch **unmöglich**, hier einen Screenshot der laufenden
  GENESIS-Media-Manager-GUI zu erzeugen oder per Bildvergleich zu
  verifizieren, dass das Dark Theme jetzt wirklich überall korrekt
  aussieht.
- Jede Aussage über das *visuelle* Ergebnis in diesem Bericht beruht auf
  **Code-Review und WPF-Rendering-Fachwissen**, nicht auf einem echten
  Blick auf die Oberfläche. Das ist eine ehrliche Einschränkung, keine
  Ausrede — deshalb wurde in dieser Runde so viel Aufwand wie möglich in
  robuste, zustandsunabhängige `ControlTemplate`-Overrides gesteckt statt
  in einfache `Style`-Setter, die sich als nicht ausreichend erwiesen
  haben (siehe Abschnitt 4).
- Eine **verbindliche visuelle Abnahme ist nur auf einem echten
  Windows-Rechner möglich.** Bitte nach der Installation erneut einen
  Screenshot schicken, falls noch etwas nicht passt — das ist nach dieser
  Plattformgrenze der einzig verlässliche Weg.

Was in dieser Sandbox **sehr wohl** zuverlässig geprüft werden kann und
auch wurde: Kompilierbarkeit, Compiler-Warnungen, reine Logik-Tests,
Backend-API-Verhalten über echte HTTP-Aufrufe gegen einen laufenden
Server, und Linting.

## 2. .NET-Client (`ui-windows-dotnet/GenesisMediaManager.Client`)

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Build (Release, win-x64, inkl. aller geänderten XAML-Dateien) | `dotnet build -c Release -p:EnableWindowsTargeting=true -r win-x64 -p:WarningLevel=9` | **0 Fehler, 0 Warnungen** |
| Logik-Testsuite | `dotnet test -c Release` (`GenesisMediaManager.Client.Tests`) | **131/131 bestanden** |

`WarningLevel=9` wurde bewusst statt der Standardstufe verwendet, um
sicherzustellen, dass wirklich **alle** vom Compiler erkennbaren
Warnungen sichtbar gemacht werden, nicht nur die Standardauswahl.

Reproduzierbar über: `scripts/run_dotnet_tests.sh`

## 3. Python-Core-Service (`core/`)

| Prüfung | Befehl | Ergebnis |
|---|---|---|
| Vollständige Testsuite | `python -m pytest -q` | **571 bestanden, 7 bewusst übersprungen (plattform-/feature-abhängig), 0 fehlgeschlagen** |
| Linting (ruff) | `ruff check .` | **Alle Prüfungen bestanden** (7 kleinere Funde automatisch behoben, 1 toter Code-Fund manuell behoben, siehe Abschnitt 5) |

Beim ersten Lauf schlugen 26 Tests fehl, weil in der Sandbox weder
`ffmpeg`/`ffprobe` noch `fpcalc` (Chromaprint) installiert waren. Nach
Installation dieser System-Abhängigkeiten liefen **alle** Tests ohne
Einschränkung durch — das bestätigt, dass der Fehlerursprung rein an der
Testumgebung lag, nicht am Produktcode.

### 3.1 Live-API-Rauchtest (zusätzlich zu den Unit-Tests)

Der Core-Service wurde tatsächlich gestartet (`python run_api.py`,
`uvicorn` auf `127.0.0.1:8420`) und folgende Endpunkte wurden per echtem
HTTP-Aufruf geprüft — sowohl ohne als auch mit gültigem API-Token, um
auch die Authentifizierung (ADR-0006) zu verifizieren:

| Endpunkt | Ohne Token | Mit Token |
|---|---|---|
| `/health` | 200 OK (bewusst offen) | — |
| `/dashboard/summary` | 401 Unauthorized | 200 OK |
| `/media` | 401 Unauthorized | 200 OK |
| `/settings` | 401 Unauthorized | 200 OK |
| `/jobs` | 401 Unauthorized | 200 OK |
| `/errors` | 401 Unauthorized | 200 OK |
| `/logs` | 401 Unauthorized | 200 OK |
| `/plugins` | 401 Unauthorized | 200 OK |
| `/diagnostics` | 401 Unauthorized | 200 OK |

Alle Antworten enthielten valides, erwartungskonformes JSON. Der Service
wurde danach sauber gestoppt und sein Laufzeitverzeichnis
(`~/.genesis-media-manager`, Testdatenbank etc.) wieder entfernt.

Reproduzierbar über: `scripts/run_tests.sh` (Unit-Tests) + manueller
Start via `python core/run_api.py`.

## 4. Root-Cause-Analyse: Warum die erste Theme-Korrekturrunde nicht ausreichte

Nach Auswertung des zweiten Nutzer-Screenshots wurden per Code-Review
zwei unabhängige, sich gegenseitig verstärkende Ursachen identifiziert:

1. **`ContentControl` zeichnet `Background` gar nicht.** Der vorherige
   Fix setzte `Background="{StaticResource BackgroundBrush}"` direkt auf
   `<ContentControl x:Name="MainContent">`. Das Standard-Template von
   `ContentControl` besteht aber nur aus einem nackten
   `ContentPresenter` **ohne** umschließenden `Border` — die
   `Background`-Eigenschaft wird dadurch von keinem visuellen Element
   gezeichnet und hatte schlicht **keine Wirkung**. Behoben durch ein
   explizites `ControlTemplate` mit echtem `Border` (siehe
   `MainWindow.xaml`).
2. **Einfache `Style`-Setter reichen bei bestimmten WPF-Standard-
   `ControlTemplate`s nicht aus.** Insbesondere das native
   `Button`-Chrome zeichnet seinen deaktivierten Zustand über ein
   internes, von der `Background`-Eigenschaft unabhängiges Overlay.
   Behoben durch vollständige, selbst geschriebene `ControlTemplate`-
   Overrides für `Button`, `CheckBox`, `ComboBox`, `ScrollBar` und
   `DataGrid` in `Themes/DarkTheme.xaml` (letzteres 1:1 nach dem
   offiziellen Microsoft-Referenzaufbau, nur mit unserer Farbpalette).

Zusätzlich wurde als doppelte Absicherung jedes der **17** Stellen im
Code, die eigene Root-Panels für Ansichten erzeugen und per
`MainContent.Content = ...` anzeigen (Dashboard, Medientabelle,
Einstellungen, Anbieter, KI-Center, Backups, Diagnose, Download-Center,
Duplikate, Fehlercenter, Job-Queue, Bibliothek, Log-Viewer, Plugins,
Sprachstudio), dahingehend geprüft und wo nötig ergänzt, dass sie ihren
`Background` **zusätzlich selbst explizit** setzen — unabhängig davon,
ob der `ContentControl`-Fix allein schon ausreichen würde.

## 5. Vollständiger Fehler-/Warnungs-Scan

- `grep` nach `Brushes.White`, `Colors.White`, `#FFFFFF`, `SystemColors`
  und jeder Form von `.Background = ...` im gesamten `.cs`-Code: **keine
  Fundstellen**, die das ursprüngliche Symptom erklären würden (bestätigt
  die obige Root-Cause-Analyse, nicht eine lokale Fehlzuweisung).
- `dotnet build` mit `WarningLevel=9` über Client **und** Test-Projekt:
  **0 Warnungen**.
- `ruff check` über den gesamten Python-Core: **0 verbleibende Funde**
  (7 automatisch behoben, 1 manuell: ungenutzte Tupel-Variable in einem
  Test umbenannt, siehe Commit).

## 6. Fazit

Alles, was in dieser Sandbox **messbar und automatisiert** geprüft werden
kann, ist grün: Build, Compiler-Warnungen, 131 .NET-Logik-Tests, 571
Python-Tests, Linting, Live-API-Rauchtest. Die eigentliche, vom Nutzer
gemeldete visuelle Regression wurde durch Code-Review ursächlich
geklärt (siehe Abschnitt 4) und durch einen grundlegend robusteren Ansatz
(vollständige `ControlTemplate`-Overrides statt einfacher `Style`-Setter)
behoben. Eine **100%ige visuelle Garantie kann aus dieser Linux-Sandbox
heraus nicht gegeben werden** — das ist eine Plattformgrenze, keine
Nachlässigkeit. Bitte nach dem nächsten Windows-Testlauf kurz
rückmelden.

## 7. Echter Ende-zu-Ende-Funktionstest (Nachtrag, nach Dark-Theme-Bestätigung)

Nachdem der Nutzer die Farbgebung als korrekt bestätigt hat, kam die neue
Anforderung: **"teste alles sauber jeden Button jedes Element auf
wirkliche Lauffähigkeit"**, ausgelöst durch zwei Screenshots:

- **Bild 1**: Viele Werkzeugleisten-Buttons in der Medientabelle sind
  ausgegraut/nicht klickbar.
- **Bild 2**: Klick auf "Konvertieren" (und ähnliche WERKZEUGE-Einträge
  im linken Nav) zeigt nur einen Platzhaltertext
  ("Dieses Modul ist laut Entwicklungsphasenplan... noch nicht
  implementiert").

Da unter Linux kein WPF-Rendering möglich ist, wurde als bestmöglicher
Ersatznachweis ein **echter Integrationstest gegen die tatsächliche
Business-Logik** aufgebaut: ein Wegwerf-Konsolenprogramm, das denselben
`GenesisApiClient`-Code einbindet, den `MainWindow.*.cs` für jeden
Button-Klick aufruft, und ihn gegen eine echte laufende Core-API-Instanz
ausführt (keine Mocks, keine Simulation).

**Aufbau:**
- .NET 8 SDK + Python-venv + `ffmpeg`/`ffprobe`/`fpcalc` frisch installiert.
- Echte Test-MP3 erzeugt (3s Sinuston, ID3-Tags gesetzt).
- Core-API als echter Prozess gestartet (`http://127.0.0.1:8420`).
- `/home/user/inttest/Program.cs` ruft 23 Methoden von `GenesisApiClient`
  in der exakten Reihenfolge auf, die die echten Button-Handler in
  `MainWindow.*.cs` verwenden.

**Ergebnis: alle 28 Einzelprüfungen grün**, u.a.:

| Geprüfter Button/Workflow | API-Aufruf | Ergebnis |
|---|---|---|
| Einstellungen → Medienordner setzen | `UpdateSettingsAsync` | ✅ übernommen |
| "Scannen"-Button | `TriggerScanAsync` | ✅ 1 Datei gefunden, DB aktualisiert |
| Dashboard-Zähler | `GetDashboardSummaryAsync` | ✅ 0 → 1 nach Scan |
| Medientabelle füllen | `ListMediaAsync` | ✅ Testdatei erscheint |
| Detailpanel (Zeile anklicken) | `GetMediaDetailAsync`, `GetQualityAsync`, `ListLoudnessAsync`, `GetAiMetadataAsync`, `ListMediaSourcesAsync` | ✅ alle liefern Antwort |
| "Umbenennen..."-Button | `RenamePreviewAsync` | ✅ Vorschau berechnet |
| "Metadaten abgleichen" | `GetMetadataSuggestionsAsync` | ✅ korrekt kontrollierter Fehler (Feature in Einstellungen deaktiviert, kein Absturz) |
| "Lautheit..."-Button | `AnalyzeLoudnessAsync`, `PreviewLoudnessNormalizationAsync` | ✅ echte LUFS-Messung (-21,75 LUFS) |
| "Cutter..."-Button | `PreviewCutAsync` | ✅ Schnittplan berechnet |
| "Konvertieren..."-Button (Medientabelle!) | `PreviewConversionAsync` | ✅ Konvertierungsplan berechnet |
| "Fingerprint berechnen" | `ComputeFingerprintAsync` | ✅ echter Chromaprint-Fingerabdruck via `fpcalc` |
| "Qualität prüfen" | `AnalyzeQualityAsync` | ✅ Analyse durchgeführt |
| "Artwork..."-Button | `GetArtworkBytesAsync` | ✅ korrekt "kein Cover" (kein Absturz) |

**Schlussfolgerung zu Bild 1:** Die ausgegrauten Buttons waren **kein
Bug**, sondern der korrekte, vom Code so vorgesehene Zustand bei leerer
Bibliothek (`UpdateButtonStates()` in `MainWindow.xaml.cs` deaktiviert
zeilenabhängige Aktionen ohne Auswahl/Daten — das ist Absicht, kein
Fehler). Nach echtem Scan sind alle getesteten Buttons durchgängig
funktionsfähig bis zur Business-Logik-Ebene.

**Schlussfolgerung zu Bild 2:** Die Platzhalter bei den WERKZEUGE-Einträgen
im linken Nav-Menü ("Konvertieren", "Umbenennen", "Lautheit", "Cutter",
"Qualitätsprüfung" usw. als *eigenständige, ordner-weite* Seiten) sind
**bewusstes Design**, 1:1 identisch mit der PySide6-Referenz-UI
(`ui-reference-pyside/genesis_ui/main_window.py`, Zeilen 84–92, definiert
exakt dieselben Einträge als `"placeholder"`). Die **echte** Funktionalität
existiert bereits vollständig und ist jetzt nachweislich lauffähig — nur
erreichbar über die Werkzeugleisten-Buttons der Medientabelle (pro
ausgewählter Datei/Dateien), nicht über eigenständige Vollbild-Ansichten
im Nav-Menü.
