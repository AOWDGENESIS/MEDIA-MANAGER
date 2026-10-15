# GENESIS Media Manager – Installer-Audit (13.10.2026, aktualisiert 15.10.2026)

## Ergebnis

Der hier geprüfte Windows-Build ist erfolgreich: [GitHub-Actions-Lauf 38702688565](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/38702688565). Der Lauf hat **0 GitHub-Annotationen** und erzeugte drei nicht abgelaufene Einzelartefakte. Neuere Läufe bündeln diese Dateien in **einem** Download-Artefakt:

| Artefakt | Größe des GitHub-Artefakts |
|---|---:|
| `GenesisMediaManager-Inno-Setup-exe` | 50.990.496 Bytes |
| `GenesisMediaManager-Setup-msi` | 59.597.684 Bytes |
| `GenesisMediaManager-Setup-zip` | 132.512.752 Bytes |

**Für die Installation auf dem PC (neue Läufe):** Unter „Artifacts“ nur `GenesisMediaManager-Komplettpaket-zip` herunterladen, die von GitHub gelieferte ZIP entpacken und die enthaltene `GenesisMediaManager-Inno-Setup.exe` ausführen. Die ebenfalls enthaltenen MSI- und ZIP-Pakete sind **Alternativen**, nicht zusätzlich zu installieren. Die `.iss` ist nur das Bauskript. Python 3.11+ auf PATH und Internet für die erstmalige Python-Einrichtung sind erforderlich. `BUILDINFO.txt` nennt den zugehörigen Lauf und Commit.

## Gefunden und behoben

1. **Veraltete GitHub-Action-Laufzeit:** `checkout@v4`, `setup-dotnet@v4` und `upload-artifact@v4/v5` lösten Node-20-Deprecation-Annotationen aus. Auf `checkout@v5`, `setup-dotnet@v5` und `upload-artifact@v6` (Node 24) umgestellt. Der letzte Lauf hat keine Annotationen.
2. **Deinstallation mit laufendem Core:** Die Inno-EXE beendete zuvor `pythonw.exe` nicht ausdrücklich, obwohl `.venv` von pip erzeugte, nicht durch Inno getrackte Dateien enthält. `Stop-GenesisProcesses.ps1` beendet vor dem Löschen nur die Prozesse der betreffenden Installation (Client-Pfad bzw. `run_api.py`-Pfad). Im Windows-Smoke-Test waren App und Core beim Start der Deinstallation aktiv; danach waren Client, venv und Core-Prozess weg, die Nutzerdaten unter `%APPDATA%\GenesisMediaManager` blieben erhalten.
3. **Kollisionen verschiedener Installer:** Alle Wege verwenden denselben Programmordner. Inno blockierte schon bisher fremde Installationen. Jetzt weist auch der ZIP/PowerShell-Weg vorhandene Inno-/MSI-Installationen ab; das MSI prüft per WiX-Launch-Bedingung auf die Uninstall-Registry-Einträge von Inno/PowerShell. Ein negativer Windows-CI-Test hat bestätigt, dass das MSI eine vorhandene Inno-Installation **vor der Dateiinstallation** ablehnt.
4. **Unvollständiger ZIP-Erstlauf:** `start.bat` übersprang bislang die Installation, sobald nur die Client-EXE vorhanden war – selbst ohne `.venv`. Jetzt werden Backend, venv und Startskript mitgeprüft; eine unvollständige ZIP-Installation wird erneut eingerichtet. Eine unvollständige Inno-Installation wird nicht versehentlich per ZIP überschrieben, sondern verweist auf erneutes Ausführen der Inno-EXE.
5. **MSI meldete Erfolg ohne Python-Core:** Die ursprünglich asynchrone Custom-Action endete, obwohl keine `.venv` entstand. Ein positiver MSI-Test deckte den Fehler auf. Die Einrichtung läuft nun synchron mit geprüftem Exit-Code; im Windows-CI wird der Interpreterpfad explizit über `GENESIS_PYTHON` übergeben, weil der MSI-Dienst den nur für den CI-Prozess gesetzten PATH nicht erbt. Ohne diese Property sucht das Skript nach Python auf PATH und in den Python-Registry-Einträgen.
6. **MSI-Deinstallation und Installerkollision:** Ein weiterer positiver Test zeigte, dass `util:RemoveFolderEx` das von pip erzeugte `.venv` nicht entfernte. Die MSI-Deinstallation stoppt nun gezielt die Prozesse der Installation und löscht `.venv` vor `RemoveFiles`. Eine MSI-eigene Markierungsdatei sichert die ZIP-/PowerShell-Konfliktsperre zusätzlich ab, wenn der Uninstall-Registry-Eintrag im anderen Kontext liegt.
7. **Veraltete Anleitung:** Der Workflow existiert derzeit nicht auf dem Default-Branch `main`; der dokumentierte „Run workflow“-Knopf ist deshalb momentan nicht verfügbar. Die Anleitung verweist nun korrekt auf Push-Builds des Arbeitsbranches und auf „Artifacts“.

## Durchgeführte Prüfungen

- Windows-CI: `.NET`-Client-Tests erfolgreich; self-contained WPF-Client, ZIP, WiX-MSI und Inno-Setup-EXE erfolgreich gebaut.
- Inno auf Windows: Installation, Python-Abhängigkeiten, `/health` der laufenden Core-API, Client-Fenster-Handle mit und ohne Core, zweiter Start ohne neue Core-PIDs, Update, Deinstallation **bei laufender App/Core**, Erhalt von Nutzerdaten.
- ZIP auf Windows: echtes ZIP entpackt, via beigelegtem PowerShell-Installer installiert, Abhängigkeiten und `/health` nach `start.bat` geprüft, deinstalliert und Erhalt der Benutzerdaten bestätigt.
- MSI auf Windows: installiert (mit explizitem Interpreterpfad aus `setup-python`), Core-Abhängigkeiten und `/health` geprüft; deinstalliert **bei laufendem Core**. Client, MSI-Markierung und `.venv` danach entfernt, Nutzerdaten erhalten.
- Konflikttests: `msiexec` lehnt vorhandene Inno-Installation mit der erwarteten Launch-Meldung ab; ZIP-/PowerShell-Installer lehnt vorhandene MSI-Installation ab.
- Statische Prüfung: 199 Python-Dateien mit `ast.parse`, vier i18n-JSON-Kataloge und WiX-XML erfolgreich geparst; `git diff --check` ohne Befund. Arbeitsbereich: 11 MB (<100 MB).

## Offene Grenzen / Restrisiken

- **Kein visueller Abnahmetest** von Farben, Layout und Bedienung auf dem PC des Nutzers. Das erzeugte WPF-Fenster-Handle beweist nicht, dass jede Ansicht richtig aussieht.
- Die MSI-Installation wurde im CI mit **explizit übergebenem** Python-Pfad (`GENESIS_PYTHON`) getestet. Die automatische Python-Erkennung des MSI-Dienstes auf einem fremden Ziel-PC ohne diese Property ist damit nicht nachgewiesen. Der ZIP-Test nutzte die beigelegte Installationsdatei und danach `start.bat`; der erste Doppelklick auf `start.bat` als *Installationsauslöser* wurde nicht separat getestet. Für den Nutzer bleibt die Inno-EXE der empfohlene Weg.
- Die Inno-EXE ist **nicht digital signiert**; SmartScreen kann warnen. Python 3.11+ und eine einmalige pip-Verbindung sind weiterhin externe Voraussetzungen; eine vollständige Offline-/Sicherheits-/CVEs-Prüfung aller künftig aufgelösten Python-Versionen ist damit nicht erbracht.
- „0 GitHub-Annotationen“ ist keine Garantie für absolute Fehlerfreiheit oder für null Warnungen in jeder Abhängigkeit. Der visuelle Test auf dem Ziel-PC und dortige Sicherheitsrichtlinien/Antivirus-Verhalten bleiben offen.
