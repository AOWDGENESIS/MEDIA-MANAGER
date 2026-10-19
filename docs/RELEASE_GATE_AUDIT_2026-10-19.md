# Offline-Windows-Paket: Release-Gate-Bestandsaufnahme (19.10.2026)

**Aktueller Status des strengen Release-Gates: NOT_READY – keine vollständige
Freigabe.** Der ursprünglich unten auditierte Commit `8aa1f26` hatte wegen
fehlender Pfadwahl und irreführender Anleitung noch `FAIL`. Die beiden
konkreten Mängel sind im neueren Paket `ddee09d` mit Windows-CI-Nachweis
behoben (Nachprüfung am Ende dieser Datei). Weitere verpflichtende Prüfungen
sind weiterhin offen. Diese Bestandsaufnahme ist kein Audit aller
Quellcodefunktionen.

## Ursprünglicher Befund: Paketstand `8aa1f26` (historisch)

Die folgende Matrix bewertet den **damals** verfügbaren Download. Für das
aktuell getestete Paket und die Neubewertung siehe die Nachprüfung unten.

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

**Historische Release-Entscheidung für `8aa1f26`:** `FAIL`, weil mindestens
eine verpflichtende Anforderung verletzt war (frei wählbarer Pfad; außerdem
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
- **Damals nächster Schritt:** Anpassung des Inno-Installationspfads **zusammen
  mit** Konflikterkennung, Start, Update und Deinstallation planen und
  anschließend auf Windows mit einem gewählten Pfad samt Leerzeichen testen.

## Nachprüfung am 19.10.2026: Pfadwahl und Anleitung korrigiert

[Windows-CI-Lauf 39244040685](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39244040685)
zu Commit `ddee09da4104e40d728faa66e80a363e5eaaf7f1` ist **vollständig
success**: .NET-Tests, Build, Offline-Runtime, funktionaler Medientest,
stilles Inno/41 WPF-Navigations-IDs, sichtbarer Inno-Wizard, ZIP und MSI,
Deinstallationen, Bundle-Bau und Upload. Das damalige
[Komplettpaket-Artefakt 12183176959](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39244040685/artifacts/12183176959)
hatte beim Metadatenabruf 1.010.032.906 Bytes und war nicht abgelaufen.
Es wurde **nicht** in diesen 100-MiB-Workspace heruntergeladen.

- **PASS – Pfadwahl im Inno-Wizard:** `DisableDirPage=no` und `UsePreviousAppDir=yes`.
  Der UI-Test startete mit per `/DIR` vorgegebenem Pfad *mit Leerzeichen*,
  sah ihn tatsächlich im sichtbaren Verzeichnisfeld und aktivierte danach
  nativ die Buttons Weiter, Weiter, Installieren und Fertigstellen. Er prüfte
  die Programmdateien und Offline-Runtime **am alternativen Pfad**. Die
  Texteingabe selbst erfolgte hier nicht per Tastatur/Maus, sondern per
  Inno-Kommandozeile; das ist ausdrücklich kein Beweis für jeden Klick auf
  dem Nutzer-PC.
- **PASS – Umzug/Update, Start, Deinstallation:** Ein Installationsversuch
  an einem anderen Ort wurde nur dann als blockiert gewertet, wenn der
  Inno-Log die konkrete Umzugssperre bestätigte. Update am bisherigen Pfad,
  Launcher und Core `/health` sowie Deinstallation bei laufendem Core
  bestanden; synthetische Benutzerdaten blieben erhalten.
- **PASS – Anleitung dieses Paketstands:** Die irreführende Aussage über
  Python/Internet im *historischen* Audit wurde als auf frühere Artefakte
  begrenzt klargestellt; die aktuelle `deploy/README-INSTALL.md` erläutert
  Pfadwahl, Update und Offline-Paket. Bundle-Bau kopiert diese Texte.
- **NOT_RUN – weitere Gate-Punkte:** Dedizierter echter Nichtadmin-Account,
  unabhängiger Download mit Integritätsprüfung der äußeren ZIP, finale
  Lizenz-/CVE-/Supply-Chain-Abnahme und visuelle Kontrolle auf dem Rechner
  des Nutzers. Alte Testberichte ersetzen keinen Nachweis für diesen
  Paketstand.

## Nachprüfung am 19.10.2026: Bundle vor Upload validiert

[Windows-CI-Lauf 39246989167](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39246989167)
zu Commit `8245d765d994dd06a65da660013a9d51e5cf9bf8` war vollständig
`success`, einschließlich des neuen Schritts `Komplettpaketstruktur,
SHA-256 und ZIP-Inhalte vor Upload pruefen`. Das
[Komplettpaket-Artefakt 12184357604](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39246989167/artifacts/12184357604)
hatte laut GitHub-Metadaten 1.010.008.665 Bytes und war beim Abruf
nicht abgelaufen. Das Paket wurde NICHT in den lokalen 100-MiB-Workspace
heruntergeladen. Installer-/Core-/Medien-/UI-Smokes aus dem vorigen Lauf
bestanden auch hier erneut.

`deploy/Test-DownloadBundle.ps1` kontrolliert auf dem Windows-Runner vor
dem Upload: genau neun Nutzdateien plus SHA256SUMS, nichtleere Dateien,
korrekten Commit in BUILDINFO, erneuten SHA-256-Abgleich jeder Nutzdatei
mit allen neun Manifest-Einträgen. Beide **inneren ZIP-Dateien**
(`GenesisMediaManager-Setup.zip` und `GenesisMediaManager-Quellcode.zip`)
wurden vollständig gestreamt und gegen Größe/CRC32 jedes Eintrags geprüft;
Pflichtdateien wie `runtime/python/python.exe`, `ffmpeg.exe`, `ffprobe.exe`,
`fpcalc.exe`, Client, Startskript und `.iss` wurden nachgewiesen. Die
CI-Notice und der erfolgreiche Schritt belegen diesen spezifischen Test.

**Grenze:** GitHub erzeugt die **äußere Artefakt-ZIP erst nach** dem
Pre-Upload-Schritt. Ein unabhängiger Download/CRC-Check genau dieses
transportierten Archivs wurde nicht durchgeführt (`NOT_RUN`). Ebenso sind
Nichtadmin-Test, finale Lizenz-/CVE-Prüfung und visuelle Abnahme auf dem
Ziel-PC offen. Der strenge Gesamtstatus bleibt **`NOT_READY`**. Das neue
Artefakt ersetzt den oben genannten Download als zuletzt vollständig
CI-getestete Paketversion, nicht als abschließend freigegebenes Release.

**Aktuelle Release-Entscheidung: `NOT_READY` für eine *vollständige*
Freigabe nach GENESIS OMEGA v10.1.** Die früheren konkreten `FAIL`-Befunde
sind für das neue Paket behoben. Der Download ist in den oben genannten
Fällen CI-getestet und installierbar; nicht geprüfte Pflichtkriterien
bleiben offen. Weder SmartScreen/Antivirus-Verhalten auf fremden PCs noch
absolute Fehlerfreiheit wird behauptet.
