# GENESIS Media Manager — Installation unter Windows

Dieses Paket enthält den kompletten GENESIS Media Manager: die
WPF-Benutzeroberfläche (`client/`, bereits mit allem Nötigen gebündelt —
**keine .NET-Installation auf deinem Rechner nötig**) und den lokalen
Python-Core-Service (`backend/`, der deine Mediathek scannt, verwaltet
und die REST-API bereitstellt, auf die die Oberfläche zugreift).

Alles läuft **ausschließlich lokal auf 127.0.0.1** — kein Cloud-Zugriff,
keine Telemetrie (siehe `ARCHITECTURE.md` im Haupt-Repository, ADR-0001).

## Schnellstart — ein Doppelklick für alles (empfohlen)

1. Dieses ZIP vollständig entpacken (Rechtsklick → "Alle extrahieren").
2. **Voraussetzung:** Python 3.11 oder neuer. Falls noch nicht
   installiert: https://www.python.org/downloads/ — beim Installieren
   unbedingt den Haken **"Add python.exe to PATH"** setzen!
3. Im entpackten Ordner einfach **`start.bat`** doppelklicken.
   - Beim allerersten Mal erkennt `start.bat` automatisch, dass die App
     noch nicht installiert ist, und führt die Installation selbst
     unbeaufsichtigt aus (kein manuelles Rechtsklick-"Mit PowerShell
     ausführen", keine Ausführungsrichtlinien-Hürde) — kopiert alles nach
     `%LOCALAPPDATA%\Programs\GenesisMediaManager`, richtet die
     Python-Umgebung für den Core-Service ein und legt Verknüpfungen im
     Startmenü/auf dem Desktop an.
   - Direkt im Anschluss startet `start.bat` die App automatisch.
   - Bei jedem weiteren Doppelklick auf `start.bat` (oder einfach über
     die angelegte Verknüpfung) wird die Installation übersprungen und
     die App sofort gestartet.

Keine Administratorrechte nötig (Installation nur für den aktuellen
Benutzer). Deinstallation über **Einstellungen → Apps → Installierte
Apps → GENESIS Media Manager → Deinstallieren**, oder über die
Verknüpfung "Deinstallieren" im Startmenü-Ordner.

### Alternative: Installation und Start einzeln steuern

Falls lieber Schritt für Schritt vorgegangen werden soll (z. B. um Logs
der Installation separat einzusehen), funktioniert weiterhin der
klassische Weg: Rechtsklick auf
`installer\Install-GenesisMediaManager.ps1` → **"Mit PowerShell
ausführen"** (bzw. bei einer Ausführungsrichtlinien-Warnung:
`powershell -ExecutionPolicy Bypass -File installer\Install-GenesisMediaManager.ps1`),
danach die angelegte Verknüpfung **"GENESIS Media Manager"** im
Startmenü/auf dem Desktop starten.

## Alternative: echtes MSI

Für ein klassisches MSI-Installationspaket (gleiche Funktion, aber über
den normalen Windows-Installer-Dialog statt PowerShell) liegt im
Haupt-Repository unter `deploy/wix/Product.wxs` das fertige
WiX-Installationsprojekt. Ein MSI lässt sich automatisch und fertig
gebaut über den GitHub-Actions-Workflow
`.github/workflows/build-windows-installer.yml` beziehen (Actions → "Run
workflow", danach als Artefakt herunterladen) — oder manuell auf einem
Windows-Rechner mit installiertem WiX-Toolset über
`deploy/Build-Package.ps1 -BuildMsi`.

## Alternative: Setup-EXE mit Inno Setup

Das Projekt enthaelt auch `deploy/inno/GenesisMediaManager.iss` fuer eine
klassische Windows-Setup-EXE. Ein fertiger Windows-CI-Build liegt im
Actions-Lauf als Artefakt `GenesisMediaManager-Inno-Setup-exe` (die
Artefakt-ZIP entpacken und die enthaltene `.exe` ausfuehren). Die `.iss`
allein ist **keine** installierbare Datei: sie braucht das mit
`deploy/Build-Package.ps1` erstellte Paket mit dem gebauten Client.
Python 3.11+ (auf PATH) und einmalig Internet fuer pip sind weiterhin
noetig. Die Setup-EXE ist nicht signiert; Windows kann eine
SmartScreen-Warnung anzeigen. Bestehende MSI- oder PowerShell-Installationen
vorher ueber Windows-Einstellungen > Apps deinstallieren, weil sie denselben
Programmordner mit unterschiedlichen Deinstallationsmechanismen benutzen.
Die Benutzerdaten unter `%APPDATA%\GenesisMediaManager` bleiben erhalten.

## Falls etwas nicht funktioniert

- **"... ist nicht digital signiert. Sie können dieses Skript im aktuellen
  System nicht ausführen." / `PSSecurityException: UnauthorizedAccess`**
  beim Ausführen von `Install-GenesisMediaManager.ps1` (ggf. erst beim
  automatischen Aufruf von `Setup-PythonRuntime.ps1` mittendrin, nachdem
  die Programmdateien schon kopiert wurden): Das ist der klassische
  Windows-**"Mark of the Web"**-Schutz — jede aus dem Internet
  heruntergeladene Datei wird einzeln als "aus dem Internet" markiert,
  und je nach Sicherheitsrichtlinie (`RemoteSigned`/`AllSigned`) dürfen
  unsignierte, so markierte Skripte nicht laufen. Das aktuelle Paket
  entsperrt alle mitgelieferten Skripte bereits automatisch zu Beginn der
  Installation — falls die Meldung trotzdem auftritt (z. B. bei einer
  älteren Paketversion oder einer besonders strikten Konzern-Richtlinie),
  manuell beheben:
  1. PowerShell im entpackten Ordner öffnen (Rechtsklick auf den Ordner
     im Explorer → "In Terminal öffnen" oder "PowerShell-Fenster hier
     öffnen").
  2. Folgenden Befehl ausführen, um **alle** Dateien im Ordner zu
     entsperren:
     ```
     Get-ChildItem -Recurse | Unblock-File
     ```
  3. `Install-GenesisMediaManager.ps1` erneut per Rechtsklick → "Mit
     PowerShell ausführen" starten.

  Alternative, bevor überhaupt entpackt wird: Rechtsklick auf die
  heruntergeladene ZIP-Datei → Eigenschaften → unten den Haken bei
  "Zulassen" setzen → OK → danach erst entpacken.

- **Interaktive Eingabeaufforderung "Geben Sie Werte für die folgenden
  Parameter an: InstallDir:"** erscheint in einem eigenen Konsolenfenster:
  Das passiert nur, wenn `Setup-PythonRuntime.ps1` direkt (statt über
  `Install-GenesisMediaManager.ps1`) ohne `-InstallDir`-Parameter
  gestartet wurde. Fenster schließen und stattdessen immer
  `Install-GenesisMediaManager.ps1` ausführen — dieses reicht den Pfad
  automatisch weiter.

- **"Python wurde nicht gefunden"**: Python nachinstallieren (siehe
  oben), danach `Install-GenesisMediaManager.ps1` einfach erneut
  ausführen — vorhandene Programmdateien werden aktualisiert, nichts geht
  verloren.
- **Oberfläche startet, zeigt aber "Core-API nicht erreichbar" (Verbindung
  verweigert, Port 8420)**: Das ist keine kaputte Oberfläche, sondern
  eine bewusste, ehrliche Fehlermeldung (kein automatischer Rückgriff auf
  erfundene Daten) — der lokale Core-Service läuft (noch) nicht. Das
  mitgelieferte `Start-GenesisMediaManager.bat` wartet seit der letzten
  Paketversion bereits aktiv bis zu 60 Sekunden auf den Core-Service,
  bevor es die Oberfläche startet (gerade beim allerersten Start kann der
  Core-Service deutlich länger als früher brauchen, u. a. weil Windows
  Defender jede frisch installierte `.venv`-Datei einzeln prüft). Hilft
  das nicht:
  1. Einfach die Oberfläche schließen und über die Verknüpfung erneut
     starten — der Core-Service läuft evtl. inzwischen schon im
     Hintergrund (im Task-Manager nach einem `pythonw.exe`-Prozess
     schauen).
  2. Log-Datei prüfen: `%APPDATA%\GenesisMediaManager\core-service.log`
     — enthält die vollständige Startausgabe/Fehlermeldung des
     Core-Service (neu seit dieser Paketversion; vorher ging das ins
     Leere, weil `pythonw.exe` kein Fenster hat).
  3. Core-Service zur Fehlersuche manuell im sichtbaren Fenster starten:
     ```
     "%LOCALAPPDATA%\Programs\GenesisMediaManager\.venv\Scripts\python.exe" "%LOCALAPPDATA%\Programs\GenesisMediaManager\backend\run_api.py"
     ```
     (zeigt eventuelle Fehlermeldungen direkt im Fenster an; bei Erfolg
     steht dort "Uvicorn running on http://127.0.0.1:8420" — dieses
     Fenster offen lassen und die GENESIS-Oberfläche separat starten).
- **Client-Fenster meldet einen unerwarteten Fehler**: Seit dieser
  Paketversion zeigt der Client bei unbehandelten Fehlern eine
  MessageBox UND schreibt Details nach
  `%APPDATA%\GenesisMediaManager\client-crash.log` — diese Datei bei
  einer Fehlermeldung bitte mit angeben.
- **Voice Studio/Sprachausgabe fehlt**: Die optionale `piper-tts`-
  Abhängigkeit konnte evtl. nicht automatisch installiert werden — alle
  anderen Funktionen (Bibliothek, Scan, Tags, Duplikate, Download-Center,
  Lautheit, Cutter, KI-Metadaten, ...) sind davon nicht betroffen.
  Nachinstallieren mit:
  ```
  "%LOCALAPPDATA%\Programs\GenesisMediaManager\.venv\Scripts\python.exe" -m pip install -r "%LOCALAPPDATA%\Programs\GenesisMediaManager\backend\requirements-voice.txt"
  ```

## Entwicklungsstand

Dies ist eine laufende, mehrsitzungsübergreifende Portierung der
Python/PySide6-Referenz-UI nach .NET/WPF — siehe `docs/GAP_ANALYSIS.md`
und `PROGRESS.md` im Haupt-Repository für den aktuellen Stand. Fast alle
Ansichten/Dialoge haben ein vollständiges .NET-Pendant; einzelne
Detailprüfungen laufen noch weiter.
