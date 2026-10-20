# GENESIS Media Manager 0.2.0 – Windows-x64-Offlinepaket (Vorabversion)

**Vorabversion – NICHT als vollständig freigegebenes Release nach GENESIS OMEGA v10.1 kennzeichnen.** Das Paket ist für einen Installationstest auf einem Windows-PC bestimmt. Es ist keine Garantie für Fehlerfreiheit oder Verträglichkeit mit der Sicherheitssoftware des Zielrechners.

## Download und Installation

Die Release-Datei `GenesisMediaManager-Komplettpaket.zip` vollständig entpacken und darin `GenesisMediaManager-Inno-Setup.exe` doppelklicken. Der Installationsordner ist im Assistenten wählbar. Die enthaltenen MSI- und ZIP-Installationsformen sind **Alternativen**, nicht zusätzlich zu installieren. Die `.iss` ist das Inno-Setup-Bauskript.

Python samt Core-Abhängigkeiten sowie `ffmpeg`, `ffprobe` und `fpcalc` sind enthalten. Für die Grundfunktionen ist auf dem Ziel-PC kein vorheriges Python, pip oder Internet erforderlich. Optionale lokale KI-Dienste/Modelle und TTS-Stimmmodelle sind nicht enthalten. Die Setup-EXE ist **nicht digital signiert**; Windows SmartScreen kann warnen.

## Tatsächlich geprüfter Stand

- Quellstand/Installer-Build: Commit `536c06924e34c2619ef3184aa9ed0b1784d589e6` auf `arena/b54df116-media-manager`.
- Windows-CI-Lauf [39251709035](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39251709035), zuletzt erfolgreich in Versuch 2: .NET-Tests, Paketbau, Offline-Runtime und Medienwerkzeuge, Inno-/ZIP-/MSI-Installation und Deinstallation. Inno-Wizard-Buttons und ein alternativer Pfad mit Leerzeichen wurden getestet; 41 Navigations-IDs der WPF-UI gewählt.
- Das CI-Artefakt wurde vor Upload und nach erneutem Download auf einem separaten Windows-Runner gegen Inhaltsliste, SHA-256 und CRC32 der ZIPs geprüft. Diese Vorabversion lädt dasselbe ZIP als Release-Asset hoch und prüft den anonym erreichbaren Release-Link erneut.
- Erwarteter SHA-256-Wert der **gesamten** Release-ZIP: `22f00e8cbde23fe428dc0800b9944bf1819be316214deb248b03ade4f772aeef` (1.009.996.594 Bytes). Nach dem Download kann dieser Hash mit `Get-FileHash .\GenesisMediaManager-Komplettpaket.zip -Algorithm SHA256` geprüft werden. Der Hash beweist Integrität gegenüber dem bekannten Wert, nicht die Unbedenklichkeit des Programms.

## Noch offen

Die vollständige visuelle Abnahme auf dem individuellen PC, ein dedizierter Test unter einem nichtadministrativen Windows-Konto sowie die abschließende Lizenz-/CVE-/Supply-Chain-Bewertung stehen aus. Nicht buchstäblich jedes Bedienelement wurde angeklickt. Projektstand und detaillierte Nachweise: `PROGRESS.md` und `docs/RELEASE_GATE_AUDIT_2026-10-19.md` im Quellcode.
