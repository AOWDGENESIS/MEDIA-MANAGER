# G4S-Legacy — Herkunftsnachweis & technisches Erbe von Gregor Segner (g4s)

**Zweck dieses Dokuments:** Auf ausdrücklichen Wunsch wird hier sichtbar und
ehrlich dokumentiert, ob und wo technische Arbeiten aus dem öffentlichen
GitHub-Bestand von **Gregor Segner** (GitHub-Handle [`g4s`](https://github.com/g4s),
`g4s3.de`) das GENESIS-Projekt beeinflusst haben — als dauerhafte,
nachvollziehbare Referenz, nicht als einmalige Fußnote.

Dieses Dokument ersetzt KEINE Lizenzprüfung (siehe
`licenses/THIRD-PARTY-LICENSES.md` für tatsächlich übernommenen
Drittanbieter-Code) — es ist eine **Transparenz- und Würdigungs-Akte**.

## G4S Legacy Attribution Standard (verbindlich für GENESIS-Projekte)

1. Gregors Arbeit wird sichtbar als technische Inspiration/Referenz genannt
   — nicht in einer versteckten Fußnote.
2. Es wird **nicht behauptet**, Gregor habe an GENESIS mitgearbeitet, wenn
   das nicht der Fall ist.
3. Direkter Code wird nur nach Lizenz- und Herkunftsprüfung übernommen
   (Datei, Lizenz, Copyright, Änderungen werden dokumentiert).
4. Ideen werden bei eigener Neuimplementierung ehrlich eingeordnet als
   „inspiriert durch", „technische Referenz" oder — wo die GENESIS-Lösung
   bereits unabhängig existierte, bevor dieser Bestand geprüft wurde — als
   „historische Parallele/Bestätigung eines bereits gewählten Prinzips".
5. Interessante Fehler/Schwachstellen aus Gregors Projekten können als
   reale Regressionstestfälle für GENESIS' künftigen „Project Doctor"
   dienen (siehe Abschnitt 4).
6. Gregors ursprüngliche Repositories bleiben dabei **unverändert** — es
   wird nichts in seinen Bestand zurückgeschrieben.
7. Diese Auswertung wird als dauerhafte Referenz geführt und bei Bedarf
   um neue Funde ergänzt (keine einmalige Momentaufnahme).
8. Kategorisierung erfolgt ehrlich nach tatsächlichem Nutzen — ein Fund,
   der nur geprüft, aber nicht verwendet wurde, wird auch so gekennzeichnet
   (nicht künstlich als Beitrag aufgewertet).

## 1. Audit-Stand

**Geprüft am:** 2026-10-02. **Quelle:** öffentliches GitHub-Profil
[`github.com/g4s`](https://github.com/g4s) (Gregor Segner, Bundesdruckerei,
Ludwigshafen am Rhein). Alle unten gelisteten Repositories sind primär
Infrastruktur-/DevOps-Tooling (Ansible-Rollen, Packer-/Buildah-Rezepte,
Shell-Skripte) — ein **anderer technischer Bereich** als GENESIS (Python/
FastAPI-Backend, PySide6-Desktop-UI, SQLAlchemy/SQLite, geplanter
.NET/WPF-Client). Direkte Code-Übernahme war daher in keinem Fall
sachlich sinnvoll oder lizenzrechtlich geprüft notwendig; die Auswertung
konzentriert sich entsprechend auf **Architekturideen/Prinzipien**, nicht
auf Quelltext-Zeilen.

## 2. Repository-für-Repository-Auswertung

| Repository | Tatsächlicher Inhalt (aus README) | Kategorie | Bezug zu GENESIS |
|---|---|---|---|
| [`ansible-cve-scan`](https://github.com/g4s/ansible-cve-scan) | Ansible-Playbooks, die gezielt gegen bekannte CVEs **nur prüfen** — Zitat README: *"will not patch them"* (kein automatisches Patchen). | Idee/Architektur | **Stärkste Parallele im gesamten Bestand.** Exakt dasselbe Prinzip wie GENESIS' eigenes Grundprinzip #4–#6 (keine stillen Änderungen) und die bereits implementierten Module `genesis_core/diagnostics` (rein lesend) und `genesis_core/repair` (Scan → Plan → Vorschau → erst nach Bestätigung ausführen). **Historische Parallele**, keine Inspirationsquelle im zeitlichen Sinn — GENESIS' Scan&Repair-Architektur stand bereits vor dieser Durchsicht. Ehrlich dokumentiert als Bestätigung, dass dieses Prinzip sich auch bei Gregor unabhängig bewährt hat. |
| [`de.seafi.minimalinstall`](https://github.com/g4s/de.seafi.minimalinstall) | Schlanke Ansible-Rolle, die eine definierte **Baseline** auf frisch installierten Maschinen herstellt (Zeitzone, Zeitserver, Management-User, SELinux-Kontext für Cockpit). | Idee/Architektur | Konzeptionelle Parallele zum Soll-/Ist-Zustand-Gedanken, den GENESIS in `genesis_core/diagnostics` (Ist-Zustand prüfen) und `genesis_core/config` (deklarative Default-Baseline der Einstellungen, §56 datenschutzfreundliche Defaults) bereits unabhängig verfolgt. Nur untersucht, kein direkter Beitrag zur aktuellen Implementierung. |
| [`machine-templates`](https://github.com/g4s/machine-templates) | Packer-Vorlagen für reproduzierbare VM-Images, bewusst in einem **immutable Build-Container** ausführbar (eigenes `Containerfile`), damit der Build nicht vom lokalen Host-Zustand abhängt. | Idee/Architektur | Reproduzierbarkeits-Gedanke deckt sich mit GENESIS' eigenem Testprinzip (isolierte, reproduzierbare Testläufe über `scripts/run_tests.sh`). Nur untersucht, kein konkreter Code- oder Architekturbeitrag — unterschiedliche Zielsetzung (VM-Images vs. Desktop-Anwendung). |
| [`paperless-install`](https://github.com/g4s/paperless-install) | Ansible/Podman-Quadlet-Sammlung zum Deployment von paperless-ngx (+ KI-Erweiterung, StirlingPDF, DocuSeal), inkl. `trivyignore.yaml` (dokumentierte, bewusst akzeptierte Scan-Ausnahmen) und GitHub-Issue-Templates. | Idee/Architektur | Der Gedanke "akzeptierte Risiken werden explizit und nachvollziehbar dokumentiert, nicht stillschweigend ignoriert" (`trivyignore.yaml`) deckt sich mit GENESIS' eigener Offenlegungspflicht für bekannte Restrisiken (z.B. die dokumentierte Plugin-Sandbox-Einschränkung in `docs/GAP_ANALYSIS.md` Abschnitt 3). Nur untersucht, kein direkter Beitrag. |
| [`boxes`](https://github.com/g4s/boxes) | Sammlung von Buildah-/Packer-"Rezepten" zum Bau von OCI-Containern bzw. VMs für einzelne Dienste (AdGuard Home, InfluxDB, Mosquitto, NextCloud, ein Smarthome-Logikknoten). | Idee/Architektur | Klares "Rezept → Build → Artefakt"-Muster, strukturell vergleichbar mit GENESIS' Pipeline-Gedanken an anderer Stelle (z.B. Export-Formate in `genesis_core/exporter`: ein Eingabezustand, mehrere deterministische Ausgabeformate). Nur untersucht, kein direkter Beitrag — anderes Zieldomäne (Infrastruktur-Artefakte vs. Mediendateien). |
| [`dotfiles`](https://github.com/g4s/dotfiles) | Persönliches Dotfile-Framework auf Basis von `ellipsis` (Modularisierung) + `envsubst` (Templating), gestartet über ein `bootstrap.sh` mit einer `dis()`-Funktion. | Idee/Architektur | Der Modularisierungsgedanke ("jedes Konfigurationsmodul unabhängig aktivierbar") ist konzeptionell verwandt mit GENESIS' Plugin-System (`genesis_core/plugins`, §34) und der Sektions-Struktur der `config.yaml`/Settings-UI. Nur untersucht, kein direkter Beitrag. |
| [`collecction`](https://github.com/g4s/collecction) | "Collection of various scripts" — plattformspezifische Diagnose-/Aufräum-Skripte (u.a. `nix/`, `win/`, `cleanup_system.py`). | Nur untersucht, ohne Verwendung | Thematisch am ehesten mit GENESIS' `genesis_core/diagnostics` (Systemzustand prüfen) verwandt, aber zu allgemein/plattformspezifisch (OS-Cleanup) für eine konkrete Übernahme. Ehrlich als "nur untersucht" eingeordnet, nicht künstlich aufgewertet. |
| [`de.seafi.firewalling`](https://github.com/g4s/de.seafi.firewalling) | Ansible-Rolle für Firewalling — zum Prüfzeitpunkt noch sehr früher Stand (2 Commits, zuletzt "adding stub for using firewalld", d.h. ein Platzhalter/Stub, keine ausgereifte Policy→Regel→Apply-Pipeline). | Nur untersucht, ohne Verwendung | Das ursprünglich vermutete "Policy → Regel → Apply"-Muster lässt sich im aktuellen Repo-Zustand (Stub) noch nicht konkret belegen. Ehrlich als "nur untersucht, kein verwertbarer Befund zum Prüfzeitpunkt" dokumentiert statt eines nicht beleg­baren Musters. |

## 3. Direkt übernommener Code

**Keiner.** Es wurde zum Stand dieses Audits keine einzige Zeile Code aus
einem `g4s`-Repository in GENESIS übernommen. Sollte sich das künftig
ändern, wird hier verpflichtend ergänzt: Datei, Quelle (Repo + Commit),
Lizenz zum Übernahmezeitpunkt, und welche Änderungen GENESIS daran
vorgenommen hat (Prinzip 3 des Standards oben).

## 4. Historische Testfälle / Regressionstest-Kandidaten

Die Commit-Historien von `boxes` ("fixing typo in README") und `dotfiles`
("fixing typos") zeigen, dass auch in einem gepflegten, funktionierenden
Infrastruktur-Bestand Tippfehler vorkommen und behoben werden — das ist in
diesem Audit nur als allgemeiner Beleg sichtbar (die konkreten,
inzwischen bereits behobenen Tippfehler selbst sind kein eigenständiger
Befund mehr). Es wurde **keine zum Audit-Zeitpunkt noch aktive** konkrete
Fehlstelle (z.B. ein tatsächlich noch vorhandenes `testinfa`/`testinfra`-
artiges Problem) in den geprüften Repos gefunden, die sich 1:1 als
GENESIS-Regressionstest übernehmen ließe.

Der dahinterliegende Gedanke bleibt dennoch als **Standing-Praxis**
festgehalten: Sollte ein künftiger Blick in Gregors (oder einen anderen)
Bestand einen konkreten, noch unbehobenen Fehler zutage fördern, der für
GENESIS lehrreich ist (z.B. eine Tippfehler-Klasse, eine Race Condition,
eine übersehene Edge-Case), wird dieser hier mit Fundstelle dokumentiert
und als historischer Referenz-/Regressionstest in die GENESIS-Testsuite
aufgenommen — nicht um die ursprüngliche Arbeit schlechtzureden, sondern
weil reale Fehlerbeispiele wertvolle Testfälle für den künftig geplanten
„Project Doctor" liefern.

## 5. Fazit dieses Audits

Der `g4s`-Bestand ist technisch einem anderen Bereich (Infrastruktur-
Automatisierung) zuzuordnen als GENESIS (Desktop-Medienverwaltung) — eine
direkte Code- oder Architektur-Übernahme war entsprechend in keinem Fall
sachlich naheliegend. Die wertvollste Erkenntnis ist die **bestätigte
Parallele** zwischen `ansible-cve-scan`s "Scan, aber nicht automatisch
patchen"-Philosophie und GENESIS' eigenem, bereits vorher unabhängig
etabliertem Grundprinzip #4–#6. Diese Parallele wird hier bewusst
transparent als das benannt, was sie ist — eine nachträglich erkannte
Bestätigung eines gemeinsamen guten Prinzips, keine rückwirkend erfundene
Inspirationsgeschichte.

Dieses Dokument bleibt offen für Ergänzungen, falls künftige GENESIS-
Arbeit tatsächlich konkrete Ideen, Muster oder Code aus Gregors Bestand
übernimmt — dann wird der jeweilige Eintrag oben um einen Verweis auf die
konkrete Umsetzungsstelle in GENESIS ergänzt.
