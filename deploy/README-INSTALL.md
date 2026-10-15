# GENESIS Media Manager – Offline-Installation unter Windows x64

Das Windows-CI-Paket enthält den self-contained .NET/WPF-Client, den
Python-Core samt installierter Python-Pakete, `ffmpeg`, `ffprobe` und
`fpcalc` (Chromaprint). **Auf dem Ziel-PC braucht die Installation weder
Python noch pip noch Internet.** Die Medienbibliothek arbeitet lokal;
Online-Dienste/Downloads benötigen nur dann Internet, wenn du sie nutzt.

## Empfohlen: Setup-EXE

1. Auf GitHub unter **Artifacts** `GenesisMediaManager-Komplettpaket-zip`
   herunterladen und vollständig entpacken (gegebenenfalls anmelden).
2. `GenesisMediaManager-Inno-Setup.exe` doppelklicken. Den Schritten des
   Installationsassistenten folgen. Keine Administratorrechte erforderlich.
3. Über „GENESIS Media Manager“ im Startmenü starten. Das Startskript
   startet den mitgelieferten Core auf `127.0.0.1:8420` und dann die UI.

Das Setup ist derzeit **nicht digital signiert**; Windows SmartScreen kann
einen Hinweis zeigen. Herkunft und SHA-256-Prüfsummen der Dateien stehen
im Download-ZIP (`BUILDINFO.txt`, `SHA256SUMS.txt`). Installer-Skripte
stehen im Quellcode und in `GenesisMediaManager.iss`.

## Alternative Installationsarten (NICHT zusätzlich ausführen)

- `GenesisMediaManager-Setup.msi`: Windows Installer. Dieselben Dateien,
  ebenfalls offline. Nur verwenden, wenn du MSI bevorzugst.
- `GenesisMediaManager-Setup.zip`: vollständig entpacken und `start.bat`
  doppelklicken. Das installiert pro Benutzer, erzeugt Startmenü- und
  Desktop-Verknüpfungen und startet den Client. Alternativ zuerst
  `installer\Install-GenesisMediaManager.ps1` ausführen.
- `GenesisMediaManager.iss` ist das **Bauskript**, nicht eine zweite
  Installationsdatei. `GenesisMediaManager-Quellcode.zip` ist Projektcode.

Alle drei Installer nutzen denselben Zielordner unter
`%LOCALAPPDATA%\Programs\GenesisMediaManager`. Vor dem Wechsel zwischen
EXE, MSI und ZIP die vorhandene Installation unter **Windows-Einstellungen
→ Apps → Installierte Apps** deinstallieren, sonst kollidieren die
Deinstallierer. Updates innerhalb desselben Installers sind möglich.
Die Benutzerdaten unter `%APPDATA%\GenesisMediaManager` bleiben bei der
Deinstallation erhalten.

## Was ist nicht enthalten?

Persönliche Mediendateien und Zugangsdaten werden nie mitgeliefert.
Lokale KI-Dienste (z. B. Ollama/LM Studio) und deren Modelle sind
**optionale, separate Komponenten**. Auch TTS-Stimmmodelle gehören nicht
zum Paket; `piper-tts` ist optional und kann beim Build fehlen. Diese
Funktionen sind ohne Modelle/Dienste nicht offline nutzbar. Die
Grundfunktionen (Core, Scan, technische Analyse, Fingerprinting, Lautheit,
Schnitt und Umwandlung) benötigen keine nachträglichen Installationen.

## Fehlersuche

- Bei einer fehlenden oder beschädigten Offline-Runtime die ZIP/Setup-EXE
  erneut herunterladen. **Nicht** `Setup-PythonRuntime.ps1` manuell
  ausführen; dieses Altskript ist für ältere Pakete gedacht.
- Wenn die UI „Core-API nicht erreichbar“ anzeigt, die Anwendung über
  ihre Startmenü-Verknüpfung erneut öffnen und
  `%APPDATA%\GenesisMediaManager\core-service.log` prüfen. Der erste
  Core-Start wartet bis zu 60 Sekunden auf `/health`.
- Ein unerwarteter Client-Fehler steht zusätzlich unter
  `%APPDATA%\GenesisMediaManager\client-crash.log`.
- Die Diagnoseansicht prüft unter anderem, ob `ffmpeg`, `ffprobe` und
  `fpcalc` erreichbar sind. Bei Start über die mitgelieferte Verknüpfung
  zeigt PATH auf die lokalen Kopien, nicht auf globale Programme.
- Bei einer Skript-Blockierung durch Windows („nicht digital signiert“)
  für die alternative ZIP-Installation `start.bat` verwenden oder das
  heruntergeladene ZIP unter Eigenschaften → „Zulassen“ freigeben und
  danach erneut vollständig entpacken. Der PowerShell-Installer entsperrt
  die mitgelieferten Skripte vor dem Ausführen.

Farben/Layout und sämtliche Interaktionen auf einem individuellen PC
können durch automatische Windows-CI-Tests nicht vollständig ersetzt
werden. Für eine visuelle Abnahme bitte einen Screenshot/Rückmeldung
vom Ziel-PC senden.
