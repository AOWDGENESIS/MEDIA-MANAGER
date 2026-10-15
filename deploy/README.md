# Windows-Paketierung und Installation

`Build-Package.ps1` veröffentlicht unter Windows x64 den WPF/.NET-Client,
Python-Core, Python 3.11 samt installierten Kernpaketen, FFmpeg/FFprobe und
Chromaprint/fpcalc in einem **offline installierbaren** Paket. Der Build-
Runner lädt die externen Binaries mit festen SHA-256-Prüfsummen und
installiert Python-Pakete nur **beim Bau**. Für den Ziel-PC sind weder
Python noch pip noch Internet nötig. Die Quelltexte und Lizenzen der
externen Komponenten sind unter `runtime/licenses/SOURCES.txt`
referenziert; die Python-Lizenzdateien bleiben im `runtime/python`-Baum.
Optionale KI-/TTS-Modelle sind nicht Bestandteil des Pakets.

## Windows-Build

Voraussetzungen **nur auf dem Build-Rechner**: Windows x64, .NET SDK 8,
PowerShell 7, Git; für MSI WiX v5 und für EXE Inno Setup 6.

```powershell
./deploy/Build-Package.ps1 -BuildMsi -BuildInno
```

Ergebnis: `build/GenesisMediaManager-Inno-Setup.exe`,
`build/package/GenesisMediaManager-Setup.msi` und
`build/GenesisMediaManager-Setup.zip`. Der GitHub-Actions-Workflow
`.github/workflows/build-windows-installer.yml` erstellt alle drei,
prüft Installation/Core/Deinstallation unter Windows und lädt unter
**Artifacts** genau ein `GenesisMediaManager-Komplettpaket-zip` hoch. Der
Workflow liegt bislang nur auf dem Arbeitsbranch; „Run workflow“ steht
auf `main` noch nicht zur Verfügung.

`-SkipOfflineRuntime` ist **nur** für lokale Entwickler-Builds ohne
portable Runtime vorgesehen; so erzeugte Pakete dürfen nicht an
Endnutzer verteilt werden. Eine bloße `.iss` ohne zuvor gebautes
`build/package` ist keine installierbare Datei. Linux kann WiX/MSI und
den Windows-x64-Runtime-Build nicht vollständig ausführen.

## Installieren

Die Anleitung für Nutzer steht in `README-INSTALL.md`. Inno-EXE, MSI und
ZIP/PowerShell sind **Alternativen** mit demselben Zielordner; nicht
übereinander installieren. Im Zweifel die Inno-EXE verwenden. Die
Benutzerdaten unter `%APPDATA%\GenesisMediaManager` werden beim
Deinstallieren nicht entfernt. Das Setup ist nicht digital signiert.

`deploy/Build-DownloadBundle.ps1` sammelt die gebauten Dateien, Bauskript,
Quellcode und SHA-256-Liste erst auf dem Windows-CI-Runner. Große Binär-
und temporäre Dateien gehören nicht in das Git-Repository oder den
Entwicklungs-Workspace (100-MB-Grenze).
