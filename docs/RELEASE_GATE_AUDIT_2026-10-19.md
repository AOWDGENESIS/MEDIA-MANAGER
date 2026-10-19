# Offline-Windows-Paket: Release-Gate-Bestandsaufnahme (19.10.2026)

**Status des strengen Release-Gates: FAIL – keine vollständige Freigabe.**
Der bereits veröffentlichte Download bleibt ein *CI-getestetes Installationspaket*,
aber der erfolgreiche CI-Lauf allein erfüllt nicht alle Kriterien des vom Nutzer
bereitgestellten GENESIS-OMEGA-v10.1-Kontrollsystems. Diese Bestandsaufnahme
ist weder ein neuer Installer-Test noch ein Audit aller Quellcodefunktionen.

## Preflight und Nachweisgrenzen

- Ziel: Belege zum aktuellen Offline-Windows-Paket dem Release-Gate gegenüberstellen,
  offene Prüfungen ausdrücklich kennzeichnen und den Projektstatus aktualisieren.
- Quelle des Paketbefunds: GitHub-Actions-Lauf
  [38836570355](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/38836570355),
  Commit `8aa1f265e4e4e979be670847f1787fca12aea6a1`, `success` am
  16.10.2026. Paket-Artefakt
  [12019991863](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/38836570355/artifacts/12019991863),
  Name `GenesisMediaManager-Komplettpaket-zip`, 1.009.985.271 Bytes,
  beim Abruf nicht abgelaufen.
- Methode: CI-Job-/Schrittresultate und Notices via `gh`, statische Sichtung
  von Workflow, Installern, Smokes und Dokumentation. Das >1-GB-Artefakt
  wurde wegen des 100-MiB-Workspace-Limits **nicht heruntergeladen**.
  Keine Windows-Installation, ZIP-Integritätsprüfung, Sicherheitsanalyse
  oder visuellen Tests in dieser Bestandsaufnahme ausgeführt.
- Workspace `/home/user`: ca. 13 MiB bei Beginn. Das vollständige, vom
  Nutzer bereitgestellte Kontrollsystem liegt privat außerhalb des Git-Repos
  unter `/home/user/GENESIS-OMEGA-v10.1-Kontrollsystem.txt`; die im Text
  erwähnte separate v9.2-Masterprompt-Referenz wurde nicht gelesen.
- `PROGRESS.md` ist der bereits festgelegte autoritative Status-Tracker
  (siehe `PROJECT_BRIEF.md`); kein konkurrierendes `FORTSCHRITT.md` anlegen.

## Abgleich (PASS = nachgewiesen; FAIL = belegter Widerspruch; NOT_RUN = offen)

| Kriterium | Status | Konkreter Beleg / Grenze |
|---|---|---|
| Windows-Build und .NET-Client-Tests | PASS | Alle entsprechenden Schritte des genannten Windows-CI-Laufs erfolgreich; vollständige Compilerwarnungs-/Python-Test-Auswertung für **diesen** Commit nicht separat belegt. |
| Portable Offline-Runtime und Medienwerkzeuge | PASS | Workflow-Prüfung ohne globales Python/externe Proxys und funktionaler Test `Smoke-Test-MediaTools.ps1` grün; optionale KI-/TTS-Modelle sind laut `deploy/README-INSTALL.md` nicht enthalten. |
| Inno-Installation/Start/Core/Update/Deinstallation | PASS | `Smoke-Test-Inno.ps1` im Lauf grün: `/health`, WPF-Fenster, Zweitstart, erneutes Setup, Entfernen der Programmdateien und Erhalt eines Test-Benutzerdatensatzes. Gilt für den getesteten Standardpfad und CI-Runner. |
| Installationsassistent und WPF-Navigation | PASS (begrenzt) | CI-Notices belegen native Betätigung von `&Weiter`, `&Installieren`, `&Fertigstellen`; `Smoke-Test-UI.ps1` wählt 41 Navigations-IDs. Kein visueller Screenshot-Abgleich und kein Test jedes Bedienelements. |
| ZIP- und MSI-Installationsvarianten/Deinstallation | PASS (begrenzt) | Beide Workflow-Smokes grün mit Start/Core/Entfernung und Erhalt von Test-Benutzerdaten; keine Aussage zu allen Installationspfaden oder Rechnerkonfigurationen. |
| Frei wählbarer Installationspfad | **FAIL** | `deploy/inno/GenesisMediaManager.iss` setzt `DisableDirPage=yes`; `InitializeSetup()` und Startskripte setzen den Standardordner voraus. Im GUI-Wizard ist der Installationsort daher nicht frei wählbar. Das ist eine ausdrückliche Pflicht in Abschnitt 4.2 des neuen Kontrollsystems. Nicht durch bloßes Umschalten von `DisableDirPage` beheben: Konfliktprüfungen, Launcher, Deinstaller und Tests müssen den gewählten Pfad ebenfalls korrekt behandeln. |
| Nichtadministrative Installation, Pfad mit Leerzeichen, MSI-/ZIP-Upgrade | NOT_RUN | Die Inno-Konfiguration fordert `PrivilegesRequired=lowest`, aber ein dedizierter Test mit entzogenem Adminrecht und frei gewähltem Pfad ist nicht nachgewiesen; der Lauf enthält Inno-Update, nicht alle Varianten. |
| Externer Sicherheits-/Abhängigkeits-/Lizenzcheck | NOT_RUN | Im untersuchten aktuellen Windows-Workflow kein vollständiger CVE-/Lizenz- oder NuGet/Python-Supply-Chain-Gate-Schritt. `licenses/THIRD-PARTY-LICENSES.md` trägt ausdrücklich `ENTWURF / IN ARBEIT — NICHT RELEASE-FINAL` und beschreibt noch offene Redistribution-/Copyleft-Fragen. Das ist **keine** abschließende Lizenzfreigabe. |
| Release-Dokumentation aktuell und widerspruchsfrei | **FAIL** | Das mitgelieferte `docs/INSTALLER_AUDIT_2026-10-13.md` kennzeichnet sich zwar eingangs als historisch, behauptet aber im Installationsabschnitt weiterhin, Python auf PATH und Internet seien erforderlich. Das widerspricht dem neuen Offline-Paket und kann Nutzer irreführen. Aktuelle Anleitung in `deploy/README-INSTALL.md` nennt die richtigen Offline-Voraussetzungen. |
| Ein Downloadpaket samt `.iss`, Anleitung, Quellcode und SHA-256-Liste | PASS (Erstellung) | `deploy/Build-DownloadBundle.ps1` prüft die Quelldateien, erzeugt `BUILDINFO.txt`, Quellcode-ZIP und `SHA256SUMS.txt`; Artefakt-Upload erfolgreich. Die historische Installer-Audit-Datei wird ebenfalls beigelegt. |
| Unabhängige Prüfung der **fertigen äußeren ZIP** | NOT_RUN | Kein nachgewiesener erneuter Download mit Dateiliste, vollständiger Archiv-Integritätsprüfung und unabhängigem Vergleich der Nutzdateien gegen `SHA256SUMS.txt`. Die GitHub-Artefaktgröße allein ist kein Integritätsbeweis. |
| Visuelle Abnahme und SmartScreen/Antivirus auf Nutzer-PC | NOT_RUN | CI kann Layout, alle Klickfolgen und Sicherheitsrichtlinien auf dem individuellen Rechner nicht ersetzen; Setup-EXE ist laut Anleitung nicht signiert. |

**Release-Entscheidung:** `FAIL`, weil mindestens eine verpflichtende
Anforderung nachweislich verletzt ist (frei wählbarer Pfad; außerdem
widersprüchliche beiliegende Anleitung). Weitere Prüfpunkte stehen auf
`NOT_RUN`. Der frühere erfolgreiche Windows-CI-Test wird dadurch nicht
rückwirkend falsch: Er belegt nur die dort tatsächlich getesteten Fälle.
Vor einer *vollständigen* Freigabe sind die Fehler zu beheben und die
betroffenen Windows-Tests sowie die noch offenen Pflichtprüfungen erneut
nachweislich durchzuführen. Die nach diesem Audit vorbereiteten Aenderungen
am Inno-Assistenten, am Pfad-Smoke-Test und am historischen Anleitungstext
sind **bis zu einem neuen gruenen Windows-Lauf keine bestandenen Tests**;
das oben bewertete Artefakt aus Commit `8aa1f26` bleibt unveraendert.
Keine neue Veröffentlichung allein aus diesem Audit.

## Arbeitszyklus und nächste sichere Maßnahme

- **Schritt:** Release-Kriterien gegen tatsächlichen CI-Lauf und Quellstand geprüft.
- **Erwartung:** PASS/FAIL/NOT_RUN trennen, fehlende Freigabe nicht verschweigen.
- **Prüfung:** GitHub-Run-/Artefaktmetadaten und CI-Notices; statische Sichtung
  von Installer-/Bundle-Skripten und Dokumentation; anschließend `git diff --check`.
- **Ergebnis:** Nachgewiesener Standard-Installationspfad und CI-Abdeckung,
  aber keine frei wählbare Inno-Zieladresse und keine vollständige Release-Abnahme.
- **Status:** PASS für die Bestandsaufnahme; Release-Gate FAIL.
- **Nächster Schritt:** Anpassung des Inno-Installationspfads **zusammen mit**
  Konflikterkennung, Start, Update und Deinstallation planen und anschließend
  auf Windows mit einem benutzergewählten Pfad samt Leerzeichen testen.
