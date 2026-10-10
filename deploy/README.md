# Deployment — Windows-Installationspaket

Dieser Ordner enthaelt alles, was zum Bauen eines testbaren
Windows-Installationspakets fuer GENESIS Media Manager noetig ist (Client
+ Core-Service zusammen, Originalauftrag/Nutzerwunsch: "Client + Backend
zusammen" + "echtes MSI").

## Bestandteile

- **`Build-Package.ps1`** — die einzige Quelle der Wahrheit fuer den
  Paketierungsvorgang. Baut den .NET/WPF-Client self-contained fuer
  `win-x64` (`dotnet publish`), stellt den Python-Core-Service-Quellcode
  samt Laufzeit-`requirements.txt` zusammen, kopiert die gemeinsamen
  `i18n/`-Sprachkataloge und die Installer-Skripte, packt alles in ein
  ZIP und kann optional (`-BuildMsi`) zusaetzlich das echte MSI mit dem
  WiX-Toolset bauen.
- **`installer/`** — die drei PowerShell-Skripte des *einfachen*
  Installationswegs (funktioniert SOFORT auf jedem Windows-Rechner, auch
  ohne WiX/MSI):
  - `Install-GenesisMediaManager.ps1` — kopiert die Programmdateien nach
    `%LOCALAPPDATA%\Programs\GenesisMediaManager`, richtet eine virtuelle
    Python-Umgebung fuer den Core-Service ein, legt Startmenue-/
    Desktop-Verknuepfungen an und traegt das Programm unter
    "Apps & Features" ein. Kein Admin noetig.
  - `Setup-PythonRuntime.ps1` — die Python-venv-/pip-Logik, ausgelagert
    aus `Install-GenesisMediaManager.ps1`, damit sie UNVERAENDERT auch
    vom MSI (als CustomAction nach der Dateiinstallation) wiederverwendet
    werden kann, statt zwei leicht unterschiedliche Kopien zu pflegen.
  - `Uninstall-GenesisMediaManager.ps1` — entfernt Programmdateien,
    Verknuepfungen und den Registry-Eintrag; laesst Mediathek-Daten/
    Einstellungen unter `%APPDATA%\GenesisMediaManager` bewusst
    unangetastet (kein stiller Datenverlust).
- **`wix/Product.wxs`** — das WiX-v5-Installationsprojekt fuer ein MSI.
- **`inno/GenesisMediaManager.iss`** — Inno-Setup-6-Skript fuer eine
  Setup-EXE (x64, ohne Administratorrechte). Erwartet den von
  `Build-Package.ps1` erzeugten Ordner `build/package` mit dem gebauten
  Client und Backend; die `.iss` allein enthaelt keine Programmdateien.
  Sie verwendet dasselbe `Setup-PythonRuntime.ps1` wie ZIP/MSI und zeigt
  den Programmstart erst nach erfolgreicher Python-Einrichtung an.

## Wichtige Einschraenkung: MSI kann NICHT in der Linux-Sandbox gebaut werden

Das WiX-Toolset erzeugt MSI-Dateien ueber die Windows-Installer-COM-APIs
und funktioniert deshalb grundsaetzlich nur unter echtem Windows - unter
Linux bricht `wix build` schon beim ersten `<Directory>`-Element mit
`WIX0389: The Directory/@Name attribute's value ... is not a relative
path` ab (bekannter, von den WiX-Maintainern bestaetigter Linux-Bug, siehe
https://github.com/wixtoolset/issues/issues/7154 und
https://github.com/orgs/wixtoolset/discussions/7972). `deploy/wix/Product.wxs`
wurde in dieser Sandbox daher nur bis zur Compiler-/Schema-Ebene geprueft
(alle *eigenen* Fehler - falsch sitzende `Return="asyncNoWait"`-Attribute,
eine ungueltige `Property`-Selbstreferenz, eine veraltete
Inline-Text-Condition - wurden dabei tatsaechlich gefunden und behoben;
siehe PROGRESS.md). Ein echtes MSI entsteht automatisch und verifiziert
ueber den GitHub-Actions-Workflow
`.github/workflows/build-windows-installer.yml` (laeuft auf
`windows-latest`) - einfach unter GitHub → Actions → "Windows-Installer
bauen" → "Run workflow" anstossen, danach liegt das MSI als Artefakt zum
Download bereit.

## Lokal von Hand bauen (auf echtem Windows mit WiX)

```powershell
dotnet tool install --global wix --version 5.0.2
wix extension add -g WixToolset.Util.wixext/5.0.2
./deploy/Build-Package.ps1 -BuildMsi
```

## Inno-Setup-EXE bauen (Windows)

Inno Setup 6 und .NET SDK 8 unter Windows installieren. Im Repo-Root:

```powershell
./deploy/Build-Package.ps1 -BuildInno
```

Ergebnis: `build/GenesisMediaManager-Inno-Setup.exe`. Fuer einen manuellen
Kompilierungslauf mit Inno Setup zuerst
`./deploy/Build-Package.ps1 -SkipZip` ausfuehren; danach
`ISCC.exe deploy\inno\GenesisMediaManager.iss`. Der Windows-CI-Workflow
baut und veroeffentlicht die Setup-EXE ebenfalls als Artefakt.
**Python 3.11+ und Internet** sind auf dem Ziel-PC fuer die einmalige
Einrichtung des lokalen Core-Service noetig. Eine bestehende MSI- oder
PowerShell-Installation bitte vorher deinstallieren (gleicher Zielordner,
unterschiedliche Deinstallationsmechanismen); Nutzerdaten bleiben erhalten.
Setup ist derzeit nicht digital signiert.

## Lokal bauen OHNE MSI (funktioniert auch in der Linux-Sandbox)

```bash
export PATH=/opt/dotnet:$PATH:/home/user/.dotnet/tools DOTNET_ROOT=/opt/dotnet NUGET_PACKAGES=/opt/nuget-packages HOME=/home/user
pwsh -NoProfile -File deploy/Build-Package.ps1
```

Ergebnis: `build/GenesisMediaManager-Setup.zip` (entpackt: `client/` +
`backend/` + `i18n/` + `installer/`) - direkt per
`installer/Install-GenesisMediaManager.ps1` auf einem echten
Windows-Rechner installierbar.
