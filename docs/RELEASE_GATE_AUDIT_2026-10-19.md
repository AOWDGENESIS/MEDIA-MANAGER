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

## Nachprüfung am 19.10.2026: Äußere GitHub-ZIP unabhängig heruntergeladen

[Windows-CI-Lauf 39251709035](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39251709035)
zu Commit `536c06924e34c2619ef3184aa9ed0b1784d589e6` ist vollständig
**success**, einschließlich des zweiten Jobs `Veroeffentlichtes Download-ZIP
unabhaengig pruefen` auf einem **anderen** Windows-Runner (2m1s).
[Artefakt 12187150814](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39251709035/artifacts/12187150814)
war beim Abruf nicht abgelaufen, Größe **1.010.000.271 Bytes**; GitHub-API-
Digest `sha256:a03456f262ab3b1e6091a7e023d96fc0a2d2c08f14165242dc408957b346446b`.

Der zweite Job prüfte zunächst ID, Run und Commit über die Actions-API,
lud danach die **tatsächliche äußere Artefakt-ZIP** auf seinen Runner in
`RUNNER_TEMP`, verglich Byte-Länge und neu berechneten SHA-256 mit den
API-Metadaten, dekomprimierte alle äußeren ZIP-Einträge mit eigenem
CRC32-/Längenvergleich und kontrollierte die exakte Dateiliste. Nach
Extraktion folgten der erneute Abgleich aller neun Nutzdateien gegen
`SHA256SUMS.txt` und die vollständige CRC32-Prüfung beider inneren ZIPs.
CI-Notices und grüne Jobs belegen diesen konkreten Ablauf. Die GB-Datei
wurde **nie** in den limitierten lokalen Entwicklungs-Workspace geladen;
die eigens erzeugten temporären Daten wurden auf dem zweiten Runner
anschließend entfernt.

**ZIP-Gate für diesen Artefakt-Download: PASS** für Struktur, Übertragung,
Hash-Konsistenz und Dekomprimierbarkeit. Der GitHub-Digest/Manifestabgleich
ist ein Integritätsnachweis gegenüber GitHub-Metadaten, **keine**
Software-Signatur und kein Nachweis der Unbedenklichkeit des Codes.
Weiter `NOT_RUN`: echte Installation als Nichtadmin, abschließende
Lizenz-/CVE-/Supply-Chain-Abnahme und visuelle Nutzer-PC-Abnahme.

## Lieferweg am 20.10.2026: öffentliches VORAB-Release statt veralteter Actions-URL

Die alte Actions-Artefakt-ID `12187150814` verschwand nach einem Rerun
(`run_attempt=2`) des ansonsten grünen Laufs `39251709035`; ihr Link
lieferte 404. Die frühere Erklärung „nur fehlende Anmeldung“ war nicht
ausreichend. Nach **ausdrücklicher Nutzerfreigabe für ein öffentliches
Vorab-Release** wurde das aktuelle Artefakt `12189527827` per separatem
[CI-Lauf 39380054666](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39380054666)
an den festen Tag `v0.2.0-offline-preview-20261020` auf dem getesteten
Quellstand `536c06924e34c2619ef3184aa9ed0b1784d589e6` gebunden.

Stabiler öffentlicher Download:
[GenesisMediaManager-Komplettpaket.zip](https://github.com/AOWDGENESIS/MEDIA-MANAGER/releases/download/v0.2.0-offline-preview-20261020/GenesisMediaManager-Komplettpaket.zip).
Release-Metadaten: `prerelease=true`, `draft=false`, eine Assetdatei
1.009.996.594 Bytes mit Digest
`sha256:22f00e8cbde23fe428dc0800b9944bf1819be316214deb248b03ade4f772aeef`.
Der Veröffentlichungslauf prüfte vorher nochmals Artefakt-ID, Herkunft,
SHA-256 und ZIP-CRC; danach lud ein Windows-Runner den Release-Link
**ohne Authentifizierung** vollständig neu und bestätigte erneut Dateigröße
und SHA-256. Das ist ein Nachweis für diesen öffentlich nutzbaren Link,
nicht für spätere Verfügbarkeit oder den PC des Nutzers. Das >1-GB-ZIP
wurde nie im auf 100 MiB begrenzten lokalen Workspace abgelegt.

## Nutzer-PC am 20.10.2026: echter Installationsversuch gestoppt

Der Nutzer hat den äußeren ZIP-Hash auf seinem Windows-PC berechnet:
`22F00E8CBDE23FE428DC0800B9944BF1819BE316214DEB248B03ADE4F772AEEF`
(identisch mit dem veröffentlichten Digest, Groß-/Kleinschreibung
unerheblich). Screenshot-Beleg: Paket entpackt, Setup-EXE gestartet;
SmartScreen meldete mangels Signatur einen unbekannten Herausgeber.
Im Inno-Wizard erschien anschließend die Meldung „bereits per MSI oder
ZIP installiert“. Der Nutzer widerspricht: Es sei nichts installiert.
Die Meldung allein beweist **KEINE Altinstallation**: Derselbe Codepfad
prüft auch Dateireste im Ziel- oder Standardordner, einen MSI-Marker oder
einen möglicherweise verwaisten HKCU-Uninstall-Schlüssel. Nachträgliche
lesende Diagnose des Standardordners: Client-EXE vorhanden, Inno-Uninstaller
fehlt, MSI-Marker fehlt, HKCU-ZIP-Uninstall-Schlüssel vorhanden. Zwei
unabhängige Konfliktbedingungen schlagen an; ob eine nutzbare bzw. in
Windows-Apps sichtbare ZIP-Installation existiert, ist **nicht geklärt**.
**Keine erfolgreiche Installation oder visuelle Komplettabnahme auf dem
Nutzer-PC** (`BLOCKED`). Bevor Dateien oder Registry verändert werden,
lesend prüfen, ob das zum Schlüssel gehörende Uninstall-Skript existiert
und welche InstallLocation/UninstallString eingetragen sind. Keine
pauschale Löschung oder Schutzumgehung empfehlen.

## Nachtrag: „Installierte Apps“ ist Pflicht, Registry-Test bestanden – UI noch offen

Der Nutzer erklärte die Anzeige unter Windows „Installierte Apps“ samt
Deinstallationsmöglichkeit ausdrücklich zur Pflicht. Die frühere ZIP-
Registrierung besaß zwar DisplayName und Uninstaller, war aber laut Nutzer
in den Windows-Einstellungen nicht sichtbar. Ursache auf seinem PC noch
ungeklärt; die blockierte Inno-Installation konnte dort noch keinen neuen
Uninstall-Eintrag anlegen.

Commit `7398a44bc62db444dd180fdcd504cf78ba214fe3` ergänzt explizite
Inno-Uninstall-Registrierung, macht die Konfliktmeldung wahrheitsgemäß
(auch Dateireste statt zwingend vorhandener Installation), setzt
ZIP-Versteck-Flags beim Wiederverwenden eines alten Eintrags zurück und
prüft die vollständigen HKCU-Uninstall-Werte, den realen Deinstaller sowie
die Entfernung nach Deinstallation automatisiert. Der ZIP-Test beginnt
mit einem absichtlich versteckten Alteintrag. [Windows-CI-Lauf 39385648302](https://github.com/AOWDGENESIS/MEDIA-MANAGER/actions/runs/39385648302)
hat Build, Inno-Wizard und Inno-Standardinstallation, ZIP-Installation,
Deinstallation sowie unabhängigen Paket-Download **bestanden**.
Aktuelles CI-Artefakt `12247397846`, Digest
`sha256:fb57fcce171bd2ebaaebaffa9630fafcc9d9910ea00208ed6352736371ecdd3b`.

**Wichtige Abgrenzung:** Der vorhandene *öffentliche* Release-Link liefert
weiterhin das ältere, bereits heruntergeladene Paket; die neue CI-Version
wurde nicht stillschweigend unter demselben Tag ausgetauscht. Die grüne
Registry-Prüfung belegt nur Registrierungsdaten, nicht die sichtbare
Windows-Settings-Liste auf dem individuellen PC. Nach regulärem
ZIP-Uninstaller bestätigte der Nutzer am PC `False` sowohl für den
Programmordner als auch für den ZIP-Registry-Eintrag; die alte Sperre ist
damit beseitigt. **Visuelles Apps-Gate: noch `NOT_RUN`**, bis die Inno-
Installation anschließend abgeschlossen und „Installierte Apps“ samt
Deinstallationsfunktion auf dem Ziel-PC tatsächlich gezeigt wird.

## Kritischer Nutzer-PC-Scan am 20.10.2026 – Auslieferung gestoppt

Beim ersten echten Scan meldete der Nutzer massenhaft aufblinkende
PowerShell-Fenster, einen blockierten Rechner und einen erforderlichen
harten Neustart. Ein durch CI zuvor bestandenes Installations- oder
Registry-Gate belegt **keinen sicheren Vollscan auf fremder Hardware**.
Die konkrete auslösende Prozesskette ist ohne Nutzerlogs noch nicht
belegt. Der alte öffentliche Vorab-Download wurde **sofort als Draft
zurückgezogen** (`draft=true`; anonymer Download nun HTTP 404), um
weitere Installationen des betroffenen Scans zu verhindern. Bereits
heruntergeladene Dateien lassen sich dadurch nicht zurückrufen. Nutzer
angewiesen, App/Scan nicht erneut zu öffnen und keine Mediendaten zu
löschen. Hypothesen und Gegenmaßnahmen stehen in `PROGRESS.md`;
für einen neuen Build gelten Tests, unabhängige Windows-Prüfung und
visuelle Nutzer-PC-Abnahme weiterhin als offen.

**Aktuelle Release-Entscheidung: `FAIL / DO_NOT_USE_SCAN`,
`NOT_READY` für jegliche Produktfreigabe nach GENESIS OMEGA v10.1.** Die früheren konkreten `FAIL`-Befunde
sind für das neue Paket behoben. Der Download ist in den oben genannten
Fällen CI-getestet und installierbar; nicht geprüfte Pflichtkriterien
bleiben offen. Weder SmartScreen/Antivirus-Verhalten auf fremden PCs noch
absolute Fehlerfreiheit wird behauptet.
