# Deep-Review-Report — GENESIS Media Manager (Sitzung 2)

Erstellt gemäß der Methodik aus `reference/review-prompt-pack/DEEP_REVIEW_PROMPT_DE.md`
(AI Deep Review Prompt Pack v1.2.2). Dies ist die erste tatsächlich
**ausgeführte** Tiefenprüfung gegen den realen Code (Sitzung 1 hat das
Prompt-Pack nur referenziert/dokumentiert, aber nicht angewendet).

Datum: 2026-09-30

---

## 1. Prüfkontext und Grenzen

- **Geprüfter Stand:** `core/genesis_core/` (Python-Kernlogik + REST-API),
  `ui-reference-pyside/` (PySide6-Referenz-UI), `ui-windows-dotnet/`
  (WPF-Client-Skelett), `scripts/*.sh` (Setup-Skripte), Konfigurationssystem.
- **Nicht geprüft / außerhalb des Rahmens:** GitHub-Actions/CI-Pipelines
  (noch nicht angelegt), SQL-Rohabfragen (es gibt keine — ausschließlich
  SQLAlchemy-ORM/Query-Builder, siehe Abschnitt 6), Android (nicht Teil des
  Projekts), produktiver Netzwerkbetrieb (App ist Single-User/localhost-only
  per Architekturentscheidung).
- **Testumgebung:** SAFE TEST MODE (§50/§51) — alle Tests laufen gegen
  temporäre SQLite-Datenbanken und synthetische Testdateien
  (`core/testdata_generator/`), niemals gegen echte Nutzerbibliotheken.
- **Reproduktionsumgebung:** Linux-Sandbox, Python 3.13, pytest, kein
  Windows verfügbar → der .NET/WPF-Client konnte nicht kompiliert/ausgeführt
  werden, nur durch Code-Lektüre geprüft.

## 2. Aktivierte Profile

| Profil (Prompt-Pack-Zeile) | Angewendet auf |
|---|---|
| Python (315) | `core/genesis_core/**/*.py` |
| Bash/POSIX (467) | `scripts/*.sh` |
| SQL (494) | SQLAlchemy-Modelle/-Queries (kein Roh-SQL im Projekt) |
| JSON/YAML/XML/Config (520) | `config.yaml`-Schema, `pyproject`/`csproj` |
| API REST/GraphQL/gRPC/WebSocket (597) | `core/genesis_core/api/app.py` |
| KI/LLM/Agent/RAG (655) | `core/genesis_core/ai/` (Ollama-Anbindung) |
| C#/.NET (262) | `ui-windows-dotnet/GenesisMediaManager.Client/` |

GitHub-Actions/CI-CD-Profil (~615) wurde überflogen, aber nicht als
Primärziel behandelt, da noch keine CI-Konfiguration existiert (Backlog für
spätere Phase, siehe Abschnitt 9).

## 3. Architektur, Datenflüsse, Vertrauensgrenzen

```
[Browser/Fremdseite]  --(unauthentifiziert möglich, siehe F-02)-->
                                    |
[PySide6-UI] --HTTP+Token--> [FastAPI Core-API, 127.0.0.1:8420] --SQLAlchemy--> [SQLite]
[.NET-WPF-UI] --HTTP+Token-->        |                                   \
                                      +--> [Scanner] --liest nur--> [Dateisystem]
                                      +--> [JobManager] --schreibt--> [ProcessingJobs-Tabelle]
                                      +--> [AIProvider] --HTTP--> [Ollama, 127.0.0.1:11434]
```

Vertrauensgrenzen:
- **UI ↔ Core-API:** vormals unauthentifiziert (F-02, jetzt behoben durch
  Shared-Secret-Token, ADR-0006). Größte Vertrauensgrenze im System, da
  jeder lokale Prozess (inkl. Browser-JavaScript) potenziell Zugriff hat.
- **Core ↔ Dateisystem:** Scanner öffnet Dateien ausschließlich lesend
  (verifiziert per Code-Lektüre und Grep, kein `os.remove`/`shutil.move`
  irgendwo im Scan-Pfad).
- **Core ↔ Ollama:** lokal, `NullAIProvider` als sicherer Default, KI ist
  standardmäßig deaktiviert (§56).
- **Core ↔ DB:** ausschließlich über SQLAlchemy-ORM, keine
  String-Konkatenation für SQL (Grep auf `f"SELECT`, `.format(`, `%` in
  Verbindung mit SQL-Strings ergab keine Treffer).

## 4. Executive Summary

**Risikostufe gesamt: MITTEL** (vor dieser Sitzung: HOCH, wegen F-01/F-02).

Alle in dieser Sitzung gefundenen HOCH-Findings wurden noch in derselben
Sitzung behoben und durch Regressionstests abgesichert. Es verbleiben
MITTEL/NIEDRIG-Findings, die bewusst als Backlog für spätere Phasen
zurückgestellt wurden (siehe Abschnitt 7), sowie planmäßig ausstehende
Punkte (Lizenz-Finalisierung, Dependency-Pinning), die laut expliziter
Nutzervorgabe erst am Projektende erledigt werden.

**Findings nach Schweregrad:** KRITISCH: 0 · HOCH: 2 (beide behoben) ·
MITTEL: 2 (1 behoben, 1 zurückgestellt) · NIEDRIG: 2 (beide behoben) ·
INFO: 3

**Top-3-Risiken (Stand vor Fixes):**
1. Job-ID-Kollision nach Neustart am selben Tag → harter Absturz bei jedem
   ersten Scan/Job nach einem Neustart (F-01).
2. Fehlende API-Authentifizierung → Drive-by-Localhost-/JSON-CSRF-Angriffe
   könnten Seiteneffekte auf der lokalen API auslösen (F-02).
3. Unbedingtes Voll-Rehashing + fehlerhafte Re-Analyse-Bedingung im Scanner
   → widerspricht dem Inkrementell-Scan-Anspruch bei großen Bibliotheken
   (F-03/F-04).

## 5. Findings

### F-01 — Job-ID-Kollision nach Prozess-Neustart am selben Tag

- **Kategorie:** Funktionaler Defekt / Nebenläufigkeit (B1/B5)
- **Schweregrad:** HOCH
- **Ort:** `core/genesis_core/jobs/__init__.py` (vor Fix: modulweiter
  `itertools.count()`-Zähler)
- **Beleg:** Reproduziert durch zwei unabhängige `JobManager`-Instanzen
  gegen dieselbe SQLite-Datei (simuliert zwei Prozessstarts am selben Tag):
  zweite Instanz erzeugte dieselbe Job-ID wie die letzte der ersten Instanz
  → `sqlite3.IntegrityError: UNIQUE constraint failed: processing_jobs.id`.
- **Ursache:** Der In-Memory-Zähler kannte nur den eigenen Prozesslauf, nicht
  die bereits in der DB vorhandenen IDs desselben Tages.
- **Auswirkung:** Jeder erste Job (z.B. Scan) nach einem Neustart der
  Core-Anwendung am selben Kalendertag schlägt hart fehl — kritisch für die
  Kernfunktion der App.
- **Reproduktion:** Standalone-Skript, zwei Subprozesse gegen dieselbe
  DB-Datei; siehe `core/tests/test_jobs.py::test_job_id_survives_simulated_restart`.
- **Minimaler Fix:** Job-ID-Sequenz wird aus der DB abgeleitet
  (`SELECT MAX(id) WHERE id LIKE 'JOB-{today}-%'`), mit Retry-Schleife
  (max. 5 Versuche) bei seltener gleichzeitiger ID-Kollision.
- **Regressionstest:** `test_job_ids_are_sequential_and_unique`,
  `test_job_id_survives_simulated_restart` (beide grün).
- **Referenzen:** Prompt-Pack Python-Profil, Kategorie "Nebenläufigkeit/
  Zustandsverwaltung".
- **Beweisstatus:** BELEGT (per Reproduktionsskript). **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-02 — Lokale REST-API ohne Authentifizierung

- **Kategorie:** Sicherheit — fehlende Zugriffskontrolle (API-Profil)
- **Schweregrad:** HOCH
- **Ort:** `core/genesis_core/api/app.py`
- **Beleg:** Code-Lektüre — kein `Depends(...)`-Auth-Mechanismus auf
  mutierenden Endpunkten (`/scan`) oder datenliefernden Endpunkten
  (`/media`, `/dashboard/summary`, `/jobs`). Bindung an `127.0.0.1` allein
  verhindert keine JSON-CSRF-/Drive-by-Localhost-Anfragen von im Browser
  geöffneten Fremdseiten.
- **Ursache:** Architektonisches Versäumnis in Phase 1 — Authentifizierung
  war für die Referenzimplementierung noch nicht vorgesehen.
- **Auswirkung:** Eine im Browser des Nutzers geöffnete bösartige Webseite
  könnte per JavaScript `POST http://127.0.0.1:8420/scan` auslösen (blinde
  CSRF reicht, da keine Rückgabewert-Lesbarkeit nötig ist) — widerspricht
  Prinzip #44 ("Änderung = Benutzerbestätigung"). Mit zukünftigen
  Lösch-/Umbenennen-Endpunkten würde der Schaden gravierender.
- **Minimaler Fix:** Shared-Secret-Token (`secrets.token_urlsafe(32)`),
  persistiert in `<data_dir>/api_token.txt` (0600), Pflicht-Header
  `X-Genesis-Token` auf allen Endpunkten außer `/health`, geprüft via
  `hmac.compare_digest`. Beide UI-Clients lesen das Token eigenständig ein.
  Siehe `core/genesis_core/api/security.py`, ADR-0006.
- **Regressionstest:**
  `test_protected_endpoints_reject_missing_or_wrong_token`,
  `test_health_endpoint_requires_no_token`,
  `test_api_token_file_is_written_with_restrictive_permissions`.
- **Referenzen:** Prompt-Pack API-Profil, Kategorie "AuthN/AuthZ";
  OWASP-analoge CSRF-Klasse (kein CSRF-Token bei State-Changing-Requests).
- **Beweisstatus:** PLAUSIBEL (kein realer Browser-Exploit im Sandbox
  reproduziert, aber Mechanismus ist Standard-Angriffsmuster gegen
  unauthentifizierte localhost-APIs). **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-03 — Scanner hasht jede Datei bei jedem Scan unbedingt

- **Kategorie:** Performance / Skalierbarkeit (B6)
- **Schweregrad:** MITTEL
- **Ort:** `core/genesis_core/scanner/scanner.py`
- **Beleg:** Code-Lektüre — `content_hash = sha256_of_file(...) if
  compute_hash else None` wurde unabhängig davon berechnet, ob sich Größe
  oder Änderungsdatum der Datei seit dem letzten Scan geändert hatten.
- **Ursache:** Fehlende Vorprüfung günstiger Signale (Größe/mtime) vor dem
  teuren Hash.
- **Auswirkung:** Bei großen Bibliotheken (§12/§57 verlangen ausdrücklich
  Vermeidung unnötiger Neuanalyse) würde jeder Scan die komplette
  Bibliothek erneut vollständig einlesen — potenziell stunden-/tagelange
  Laufzeiten und hoher Energie-/Festplattenverschleiß.
- **Minimaler Fix:** Günstige Vorprüfung (Größe/mtime) zuerst; Hash nur bei
  Abweichung oder erstmaligem Scan.
- **Regressionstest:**
  `test_unchanged_files_are_not_rehashed_on_second_scan` (Spy auf
  `sha256_of_file`, erwartet 0 Aufrufe bei zweitem Scan derselben,
  unveränderten Bibliothek).
- **Referenzen:** Prompt-Pack Python-Profil, Kategorie "Performance/
  Ressourcennutzung".
- **Beweisstatus:** BELEGT (Code-Lektüre + Test, der den alten Zustand
  reproduzierbar rot gemacht hätte). **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-04 — FFprobe-Re-Analyse prüft kumulierten statt Pro-Datei-Zustand

- **Kategorie:** Funktionaler Defekt (B1)
- **Schweregrad:** MITTEL
- **Ort:** `core/genesis_core/scanner/scanner.py`, `_upsert_media_file`
- **Beleg:** `if run_ffprobe and (existing is None or result.files_changed):`
  — `result.files_changed` ist der über den GESAMTEN Scan-Lauf kumulierte
  Zähler, kein Pro-Datei-Flag. Sobald irgendeine Datei im laufenden Scan als
  geändert erkannt wurde, wurde FFprobe für **alle** danach besuchten,
  tatsächlich unveränderten Dateien im selben Lauf erneut ausgeführt.
- **Ursache:** Verwechslung von Aggregat-Zustand (`ScanResult`) und
  lokalem Pro-Datei-Zustand.
- **Auswirkung:** Unnötige, potenziell zahlreiche Subprozess-Aufrufe
  (`ffprobe`) pro Scan, proportional zur Position der ersten Änderung im
  Scan-Durchlauf — bei großen Bibliotheken erheblicher Laufzeit-Overhead.
- **Minimaler Fix:** Lokales `file_changed`-Flag pro Datei statt des
  kumulierten Zählers.
- **Regressionstest:** `test_only_actually_changed_file_triggers_rehash`
  (genau 1 `ffprobe`-Aufruf erwartet, wenn genau 1 von mehreren Dateien
  geändert wurde).
- **Beweisstatus:** BELEGT (Code-Lektüre, eindeutiger Logikfehler; durch
  Test verifiziert). **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-05 — `Settings.load()` ohne Fehlerbehandlung um YAML/Validierung

- **Kategorie:** Robustheit / Fehlerbehandlung (§37)
- **Schweregrad:** NIEDRIG-MITTEL
- **Ort:** `core/genesis_core/config/__init__.py`
- **Beleg:** Vor Fix kein try/except um `yaml.safe_load`/
  `cls.model_validate(raw)`.
- **Ursache:** Fehlende Defensivprogrammierung für externe/benutzerseitig
  editierbare Eingabedatei.
- **Auswirkung:** Eine beschädigte oder von Hand fehlerhaft bearbeitete
  `config.yaml` hätte die gesamte App beim Start mit einem rohen
  Python-Stacktrace zum Absturz gebracht — verstößt gegen §37
  (nutzerfreundliche Fehlerbehandlung, keine stillen/unverständlichen
  Abstürze).
- **Minimaler Fix:** try/except um Laden+Validierung; bei Fehler: Warnung
  loggen, kaputte Datei als `config.broken-<Zeitstempel>.yaml` sichern
  (Prinzip #4 — nichts wird stillschweigend gelöscht), Defaults verwenden
  und neu speichern.
- **Regressionstest:** `test_load_recovers_from_corrupted_yaml`,
  `test_load_recovers_from_unknown_fields_type_error`.
- **Beweisstatus:** BELEGT. **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-06 — Unsichere JSON-String-Interpolation in `setup_ollama.sh`

- **Kategorie:** Robustheit / Injection-Hygiene (Bash-Profil)
- **Schweregrad:** NIEDRIG
- **Ort:** `scripts/setup_ollama.sh`
- **Beleg:** `curl -d "{\"model\":\"$MODEL\",...}"` — `$MODEL` wird direkt in
  einen JSON-String eingebettet.
- **Ursache:** Fehlendes JSON-Escaping bei String-Interpolation.
- **Auswirkung:** Ein `$MODEL`-Wert mit Anführungszeichen oder Backslash
  hätte ungültiges JSON erzeugt (Skript-Fehler, kein Sicherheitsrisiko, da
  lokales Dev-Skript mit selbstgewähltem Argument). Real-Risiko gering,
  aber konkrete Code-Hygiene-Verbesserung.
- **Minimaler Fix:** JSON-Body sicher via `python3 -c`/`json.dumps` statt
  Shell-String-Interpolation erzeugen.
- **Regressionstest:** manuell verifiziert mit `$MODEL` enthaltend
  Anführungszeichen und Backslash → korrekt geparstes JSON (siehe
  Aktionsprotokoll dieser Sitzung); kein automatisierter Test, da das
  Skript `sudo`/Netzwerk/Ollama-Installation voraussetzt und nicht in der
  regulären `pytest`-Suite läuft.
- **Beweisstatus:** BELEGT. **Vertrauen:** MITTEL (manuell statt
  automatisiert verifiziert).
- **Status:** BEHOBEN.

### F-07 — Async-void-artige Event-Handler in `MainWindow.xaml.cs` (INFO)

- **Kategorie:** Wartbarkeit / potenzielles Zukunftsrisiko (C#/.NET-Profil)
- **Schweregrad:** INFO
- **Ort:** `ui-windows-dotnet/GenesisMediaManager.Client/MainWindow.xaml.cs`
- **Beleg:** `Loaded += async (_, _) => await ShowDashboardAsync();` und
  `child.Selected += async (_, _) => await OnNavigationSelectedAsync(label);`
  sind "async void"-artige Event-Handler (Delegat ist `async`, Rückgabetyp
  technisch `void`).
- **Ursache:** Übliches, aber riskantes WPF-Muster — eine unbehandelte
  Exception in einem async-void-Kontext kann den Prozess direkt zum
  Absturz bringen, da sie von keinem umgebenden try/catch mehr gefangen
  werden kann.
- **Auswirkung aktuell:** KEINE — `ShowDashboardAsync()` fängt bereits alle
  Exceptions intern per try/catch ab (verifiziert durch Code-Lektüre),
  `OnNavigationSelectedAsync()` wirft selbst nichts zusätzlich.
- **Entscheidung:** Kein Code-Umbau nötig, aber erklärender Kommentar an
  beiden Stellen ergänzt, der zukünftige Beitragende warnt, diese
  Eigenschaft bei Erweiterungen zu erhalten oder auf ein explizites
  async-Command-Pattern umzusteigen.
- **Beweisstatus:** BELEGT (Code-Lektüre). **Vertrauen:** HOCH.
- **Status:** Dokumentiert (kein Fix nötig, INFO-Einstufung).

## 6. Positiv bestätigte Schutzmaßnahmen

- Kein Roh-SQL im gesamten Projekt — ausschließlich SQLAlchemy-ORM/Query-
  Builder (`select(...)`), daher strukturell keine SQL-Injection-Fläche.
- Kein `shell=True`, `eval`/`exec` auf Nutzereingaben, `pickle`, unsicheres
  `yaml.load` (immer `safe_load`) im gesamten Python-Code (per Grep über
  `core/` und `ui-reference-pyside/` verifiziert).
- Scanner öffnet Dateien nachweislich nur lesend — keine
  `os.remove`/`shutil.move`/`Path.unlink`-Aufrufe im Scan-Pfad.
- Privacy-Defaults korrekt umgesetzt und per Test abgesichert
  (`test_default_settings_are_privacy_friendly`): Telemetrie/Cloud-KI/
  automatisches Löschen/Überschreiben/Herunterladen sind alle standardmäßig
  deaktiviert.
- KI-Provider-Architektur trennt sauber `NullAIProvider` (sicherer Default)
  von `OllamaProvider` — kein Zwang zu einer laufenden KI-Instanz.
- Job-System protokolliert Fehler strukturiert (`error_count`,
  `warning_count`) statt sie zu verschlucken.

## 7. Priorisierter Maßnahmenplan

**Sofort (in dieser Sitzung erledigt):**
- F-01, F-02, F-03, F-04, F-05, F-06 behoben und regressionsgetestet.
- F-07 dokumentiert.

**Kurzfristig (vor Phase 2/3):**
- Provider-/Download-Credentials perspektivisch über OS-Keyring statt
  Klartext-YAML speichern (relevant sobald Phase 8 Download/Import
  Zugangsdaten einführt, betrifft §30).
- Dependency-Pinning/Lockfile vor dem Release-Gate einführen
  (`requirements.txt` nutzt aktuell Bereiche statt exakter Versionen —
  Reproduzierbarkeitsrisiko, Prompt-Pack-Check B8).
- `git init` durchführen (noch kein Git-Repository im Workspace) —
  spätestens vor Phase 10 nötig, idealerweise deutlich früher für
  nachvollziehbare Historie.

**Mittelfristig:**
- AI-Prompt-Injection-Exposition ist aktuell INFO/niedrig, da es noch kein
  Tool-Calling oder automatisches Anwenden von KI-Vorschlägen gibt. Muss
  spätestens vor Phase 6 (KI-Erweiterungen) mit verbindlichen
  Freigabe-Gates/Action-Budgets neu bewertet werden.
- Preload-Strategie des Scanners (`known_by_path`, siehe F-03-Fix) sollte
  für sehr große Bibliotheken (>> 1 Mio. Dateien) in Phase 9
  (Performance-Hardening) durch einen gezielteren, verzeichnisweise
  inkrementellen Ansatz ersetzt werden, um den RAM-Bedarf des vollständigen
  Vorladens zu vermeiden (§12/§57).

## 8. Empfohlene Prüfkommandos (nur zur Information, nicht automatisch ausgeführt)

```bash
# Vollständige Testsuite
bash scripts/run_tests.sh

# Gezielte Regressionstests dieser Sitzung
cd core && python3 -m pytest -q tests/test_jobs.py tests/test_scanner_performance.py \
    tests/test_api.py tests/test_config.py -v

# Erneuter Grep-Sicherheitsscan (sollte weiterhin leer sein)
grep -rn "shell=True\|pickle\.load\|yaml\.load(" core/ ui-reference-pyside/
```

## 9. Offene Fragen / Annahmen

- Angenommen: `.NET`/WPF-Client-Code ist syntaktisch korrekt, da er in
  dieser Linux-Sandbox nicht kompiliert werden kann (kein Windows/`dotnet`
  mit WPF-Workload verfügbar) — Verifikation nur durch Code-Lektüre. Muss
  vor Phase-Abschluss auf echtem Windows/`dotnet build` verifiziert werden.
- Angenommen: `setup_ollama.sh`-Fix ist syntaktisch/funktional korrekt
  (manuell mit Beispielwerten verifiziert), aber nicht End-to-End gegen
  eine echte laufende Ollama-Instanz in dieser Sitzung erneut durchgetestet
  (Ollama/Modell sind laut Ressourcen-Disziplin nicht dauerhaft im
  Sandbox-Snapshot vorhanden).
- Die API-Token-Lösung (ADR-0006) schützt spezifisch vor dem Browser-/
  Remote-Angriffsvektor, nicht vor einem bereits kompromittierten
  Benutzerkonto mit Dateisystemzugriff — das ist eine bewusst akzeptierte
  Grenze, siehe ADR-0006 "Konsequenzen".

---

# Deep-Review-Report — GENESIS Media Manager (Sitzung 3)

Erstellt gemäß derselben Methodik wie Sitzung 2
(`reference/review-prompt-pack/DEEP_REVIEW_PROMPT_DE.md`, AI Deep Review
Prompt Pack v1.2.2). Gegenstand dieser Runde sind die seit Sitzung 2 neu
hinzugekommenen **Phase-2-Module**: Rename-Engine samt Vorlagen, Artwork-
Engine, die zugehörigen REST-API-Endpunkte sowie die PySide6-Referenz-
Dialoge und der .NET-API-Client, die diese Endpunkte konsumieren.

Datum: 2026-10-01

---

## 1. Prüfkontext und Grenzen

- **Geprüfter Stand:** `core/genesis_core/rename/` (Engine + Templates),
  `core/genesis_core/artwork/` (Engine), die Phase-2-Endpunkte in
  `core/genesis_core/api/app.py` (`/rename/preview`, `/rename/apply`,
  `/media/{id}/metadata-suggestions`, `/media/{id}/metadata-suggestions/apply`,
  `/media/{id}/artwork*`), `core/genesis_core/db/models.py` (`Artwork`-Modell),
  `ui-reference-pyside/genesis_ui/dialogs/` (alle drei Dialoge:
  Rename/Metadata/Artwork), `ui-windows-dotnet/.../Api/GenesisApiClient.cs`
  (Phase-2-Methoden).
- **Nicht erneut geprüft:** Foundation-Module aus Sitzung 2 (Scanner,
  Job-System, Settings) — dort wurden in dieser Runde keine Änderungen
  vorgenommen, Sitzung-2-Findings bleiben unverändert gültig.
- **Testumgebung:** weiterhin SAFE TEST MODE (§50/§51), ausschließlich
  temporäre SQLite-DBs und synthetische Testdateien.
- **Reproduktionsumgebung:** Linux-Sandbox, Python 3.13, pytest, PySide6
  (offscreen-Plattform, `QT_QPA_PLATFORM=offscreen`) für UI-Smoke-Tests.
  **Korrektur gegenüber Sitzung 2** (siehe dortigen Abschnitt 9): Die
  damalige Annahme "der .NET/WPF-Client kann in dieser Sandbox nicht
  kompiliert werden" ist **überholt** — seit der Einführung von
  `scripts/setup_dotnet_env.sh` mit `-p:EnableWindowsTargeting=true` lässt
  sich der WPF-Client-Code auch unter Linux mit dem .NET-8-SDK vollständig
  kompilieren (0 Errors/0 Warnings, siehe PROGRESS.md "Sitzung 3"). In
  dieser konkreten Sitzung wurde der .NET-Build nicht erneut ausgeführt, da
  keine .NET-Dateien verändert wurden und das SDK im aktuellen
  Sandbox-Neustart nicht vorinstalliert war (Neuinstallation wäre reiner
  Zeitaufwand ohne erwarteten neuen Befund) — `GenesisApiClient.cs` wurde
  stattdessen durch Code-Lektüre geprüft.

## 2. Aktivierte Profile

| Profil (Prompt-Pack-Zeile) | Angewendet auf |
|---|---|
| Python (315) | `core/genesis_core/rename/`, `core/genesis_core/artwork/`, `core/genesis_core/api/app.py` |
| API REST (597) | Phase-2-Endpunkte (Rename/Artwork/Metadaten-Apply) — Vertrauensgrenzen-Fokus |
| C#/.NET (262) | `GenesisApiClient.cs` Phase-2-Record-Typen/-Methoden |

## 3. Executive Summary

**Risikostufe gesamt: NIEDRIG** (keine HOCH/KRITISCH-Funde in dieser Runde).

Alle in dieser Sitzung identifizierten Findings wurden noch in derselben
Sitzung behoben und durch Regressionstests abgesichert (7 neue Tests,
94 passed/1 skipped insgesamt). Besonders hervorzuheben: zwei der Funde
(F-09, F-11) betreffen konkret die **primäre Zielplattform Windows**
(case-insensitives Dateisystem bzw. MP4/M4A-Cover-Format), wurden aber in
der Linux-Sandbox nur indirekt über Stellvertreter-Tests nachgewiesen —
siehe Beweisstatus-Hinweise in den jeweiligen Findings.

**Findings nach Schweregrad:** KRITISCH: 0 · HOCH: 0 · MITTEL: 1 (behoben)
· NIEDRIG-MITTEL: 3 (alle behoben) · NIEDRIG: 1 (behoben) · INFO: 1
(dokumentiert, kein Code-Fix nötig)

**Top-Risiken (Stand vor Fixes):**
1. Case-insensitive-Dateisystem-Fehlalarm bei Umbenennung (F-09) — hätte
   auf der eigentlichen Zielplattform (Windows/NTFS) jede reine
   Groß-/Kleinschreibungskorrektur über die App blockiert.
2. Nicht angezeigte `empty_fields`-Warnung im Rename-Dialog (F-10) — eine
   von der Engine extra berechnete Sicherheitsinformation (Prinzip #16)
   erreichte den Nutzer nie.
3. Verlustbehaftete MIME-Typ-Rückableitung beim Artwork-Einbetten (F-11).

## 4. Findings

### F-08 — (Nachtrag) .NET-API-Client: snake_case/PascalCase-JSON-Mismatch

- **Kategorie:** Funktionaler Defekt — API-Vertragsverletzung (API-Profil/C#-Profil)
- **Schweregrad:** HOCH (zum Zeitpunkt der Entdeckung in Sitzung 3,
  vor dieser formalen Review-Runde)
- **Ort:** `ui-windows-dotnet/GenesisMediaManager.Client/Api/GenesisApiClient.cs`
- **Beleg/Ursache/Fix:** Bereits vollständig dokumentiert in `DECISIONS.md`
  (ADR-0008) und `PROGRESS.md` ("Sitzung 3, Fortsetzung"). Kurzfassung: Die
  FastAPI-Antworten liefern `snake_case`-Felder, die .NET-`record`-Typen
  waren aber ohne `JsonSerializerOptions` mit `PascalCase`-Konvention
  deserialisiert worden → alle Phase-2-Antwortobjekte enthielten
  ausschließlich `null`/Default-Werte, ohne dass ein Fehler geworfen wurde
  (stiller Datenverlust). Fix: zentrale `JsonSerializerOptions` mit
  `PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower` (bzw.
  äquivalenter Konverter) für alle `ReadFromJsonAsync`-Aufrufe.
- **Regressionstest:** siehe PROGRESS.md-Eintrag für die konkrete
  `<Compile Include>`-basierte Sandbox-Testtechnik (kein volles
  xUnit-Projekt vorhanden — siehe Abschnitt 7, weiterhin Backlog-Punkt).
- **Beweisstatus:** BELEGT. **Vertrauen:** HOCH.
- **Status:** BEHOBEN (wird hier nur zur lückenlosen Nachvollziehbarkeit im
  Review-Protokoll nachgetragen, da der Fix vor dieser formalen
  Review-Runde, aber innerhalb derselben Session entstand).

### F-09 — Case-insensitive-Dateisystem-Fehlalarm bei Umbenennung

- **Kategorie:** Funktionaler Defekt / Plattform-Kompatibilität (Python-Profil)
- **Schweregrad:** MITTEL
- **Ort:** `core/genesis_core/rename/engine.py`, Funktion `preview_renames`
- **Beleg:** Code-Lektüre — `exists_on_disk = Path(target).exists()` ohne
  Sonderbehandlung des Falls, dass `target` auf einem case-insensitiven,
  aber case-preservierenden Dateisystem (Windows/NTFS, macOS/APFS-Standard
  — **beides reale Zielplattformen dieser App**, siehe ARCHITECTURE.md)
  auf dieselbe physische Datei zeigt wie `old_path`, nur mit anderer
  Groß-/Kleinschreibung.
- **Ursache:** `is_identical`/der Konfliktcheck vergleichen Pfade als
  reine Strings (case-sensitiv), während das zugrundeliegende
  Betriebssystem die Pfade als identisch behandelt.
- **Auswirkung:** Eine reine Schreibweise-Korrektur eines Dateinamens
  (z.B. "song.mp3" → "Song.mp3") wird fälschlich als "Zieldatei existiert
  bereits"-Konflikt mit einer FREMDEN Datei gemeldet und blockiert — auf
  den eigentlichen Zielplattformen der App (Windows/macOS) wäre diese ganz
  gewöhnliche Aktion über die Rename-Funktion **nie** möglich gewesen.
- **Minimaler Fix:** Zusätzliche Prüfung via `os.path.samefile(target,
  old_path)`, wenn beide Pfade existieren und sich als String
  unterscheiden — bei Dateiidentität (gleicher Inode/gleiche File-ID) wird
  KEIN Konflikt gemeldet. Auf case-sensitiven Dateisystemen (Linux/ext4)
  ändert sich das Verhalten nicht (dort sind alter und neuer Pfad bei
  reinem Case-Unterschied ohnehin nie gleichzeitig vorhanden).
- **Regressionstest:**
  `test_preview_does_not_flag_case_only_self_rename_as_conflict` (NEU),
  `test_preview_still_flags_conflict_with_genuinely_different_file` (NEU,
  Gegenprobe) in `core/tests/test_rename_engine.py`.
- **Beweisstatus:** **PLAUSIBEL, Stellvertreter-Test.** ext4 (Sandbox) ist
  case-sensitiv, daher kann das reale Windows/macOS-Fehlalarm-Szenario
  hier nicht direkt reproduziert werden. Der Regressionstest verifiziert
  stattdessen die neue `samefile`-Unterdrückungslogik über einen
  Hardlink (zwei Pfade, ein Inode) als technisches Äquivalent zu "zwei
  Schreibweisen derselben Datei". Eine manuelle Verifikation auf echtem
  Windows/macOS steht noch aus (siehe Abschnitt 6, Offene Fragen).
  **Vertrauen:** MITTEL-HOCH (Logik ist korrekt und eng umrissen, aber
  nicht end-to-end auf der Zielplattform verifiziert).
- **Status:** BEHOBEN.

### F-10 — `empty_fields`-Warnung wird im Rename-Vorschau-Dialog nicht angezeigt

- **Kategorie:** Funktionaler Defekt / UX-Sicherheitslücke (Python-Profil,
  Prinzip #16 "keine Fantasiedaten ohne Warnung")
- **Schweregrad:** NIEDRIG-MITTEL
- **Ort:** `ui-reference-pyside/genesis_ui/dialogs/rename_dialog.py`,
  `RenamePreviewDialog._on_preview_clicked`
- **Beleg:** Die API/Engine liefert pro Vorschau-Zeile explizit eine
  Liste `empty_fields` (leere Platzhalter wie Titel oder Tracknummer) —
  extra zu diesem Zweck von der Engine berechnet. Der Dialog wertete dieses
  Feld jedoch nie aus; die Statusspalte zeigte in diesem Fall
  fälschlich schlicht "bereit" an, identisch zu einer Datei mit
  vollständigen Metadaten.
- **Auswirkung:** Nutzer sieht keinen Hinweis, dass eine umzubenennende
  Datei mit einem leeren Platzhalter (z.B. leerer Titel) tatsächlich einen
  Dateinamen mit einer Lücke erzeugen würde (z.B. "05 - .mp3"), bevor er
  die Massenumbenennung bestätigt.
- **Minimaler Fix:** Statuszeile um einen zusätzlichen `elif`-Zweig
  ergänzt: ist `empty_fields` nicht leer, wird
  `"bereit (Achtung, leer: <felder>)"` statt eines nackten "bereit"
  angezeigt.
- **Regressionstest:** Offscreen-PySide6-Smoke-Test mit gemocktem
  API-Client (`QT_QPA_PLATFORM=offscreen`), verifiziert direkt den
  gerenderten Zelleninhalt der Statusspalte für eine Zeile mit und eine
  Zeile ohne leere Felder (siehe Abschnitt 6 für das Testprotokoll — kein
  dauerhafter pytest-Test, da die UI-Testinfrastruktur für PySide6 noch
  nicht in die reguläre Suite integriert ist, siehe Abschnitt 7).
- **Beweisstatus:** BELEGT (durch tatsächliche Dialog-Instanziierung +
  Zellinhalt-Assertion, nicht nur Code-Lektüre). **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-11 — Artwork-MIME-Typ nicht persistiert; stille MP4-Format-Fehlkennzeichnung

- **Kategorie:** Funktionaler Defekt / Datenintegrität (Python-Profil)
- **Schweregrad:** NIEDRIG-MITTEL
- **Ort:** `core/genesis_core/db/models.py` (`Artwork`-Modell, fehlendes
  Feld), `core/genesis_core/api/app.py` (`embed_artwork_endpoint`),
  `core/genesis_core/artwork/engine.py` (`_embed_mp4`)
- **Beleg:** Das `Artwork`-Modell hatte kein `mime_type`-Feld (verifiziert
  per `grep "class Artwork" -A 20`). `embed_artwork_endpoint` musste den
  MIME-Typ deshalb aus der Cache-Datei-**Endung** zurückraten
  (`.endswith(".png")` sonst `"image/jpeg"`), obwohl `cache_artwork`
  unbekannte MIME-Typen ohnehin still auf die Endung `.jpg` abbildet
  (`_MIME_TO_EXT.get(mime_type, ".jpg")`) — eine doppelte verlustbehaftete
  Kette. Zusätzlich behandelte `_embed_mp4` jeden MIME-Typ außer exakt
  `"image/png"` stillschweigend als JPEG, ohne Validierung.
- **Ursache:** Schema wurde beim ursprünglichen Artwork-Feature-Entwurf
  ohne MIME-Typ-Spalte angelegt; die Rückableitung aus der Dateiendung war
  als "funktioniert meistens" (Cover Art Archive liefert praktisch immer
  JPEG/PNG) akzeptiert worden, ohne die Kombination mit dem
  Endungs-Fallback in `cache_artwork` zu Ende zu denken.
- **Auswirkung (aktuell gering, da Cover Art Archive fast nur JPEG/PNG
  liefert):** Ein zukünftiger Provider oder eine lokale
  Datei-Upload-Funktion mit einem anderen Bildformat (z.B. WebP) würde
  beim Einbetten in MP4/M4A/M4B stillschweigend mit einem falschen
  Format-Tag versehen — kaputtes/unlesbares Cover in manchen Playern, ohne
  jede Fehlermeldung.
- **Minimaler Fix:**
  1. `mime_type`-Spalte zum `Artwork`-Modell hinzugefügt (keine
     Alembic-Migration nötig — Schema wird aktuell noch per
     `Base.metadata.create_all()` erzeugt, siehe Beleg in Abschnitt 6;
     Migrations-Tooling ist laut ADR-0002 erst vor der Schema-Stabilisierung
     für echte Nutzerdaten geplant).
  2. `fetch_artwork_online` speichert den vom Provider tatsächlich
     gelieferten MIME-Typ direkt in der neuen Spalte.
  3. `embed_artwork_endpoint` liest `artwork.mime_type` statt die Endung
     zu raten (Fallback auf die alte Rate-Logik nur für evtl. ältere
     Artwork-Zeilen ohne gespeicherten Wert, Abwärtskompatibilität).
  4. `_embed_mp4` wirft jetzt `ArtworkError` für jeden MIME-Typ außer
     `image/jpeg`/`image/png`, statt stillschweigend JPEG anzunehmen.
- **Regressionstest:**
  `test_embed_mp4_rejects_unsupported_mime_type_instead_of_silently_using_jpeg`
  (`core/tests/test_artwork.py`),
  `test_artwork_embed_uses_persisted_mime_type_not_cache_file_extension_guess`
  (`core/tests/test_api_phase2.py`, deckt konkret den Fall ab, dass die
  `.jpg`-Fallback-Endung den korrekt gespeicherten `mime_type` nicht mehr
  überschreibt).
- **Beweisstatus:** BELEGT (per echtem MP4-Embed-Versuch mit
  `image/gif`-Mime, wirft den erwarteten Fehler; per echtem API-Roundtrip
  mit `image/webp`-Mock-Antwort, DB-Zeile enthält korrekt `"image/webp"`
  trotz `.jpg`-Cache-Dateiendung). **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

### F-12 — Fehlende serverseitige Konfidenz-Nachprüfung bei Metadaten-Übernahme

- **Kategorie:** Sicherheit/Robustheit — fehlende Defense-in-Depth
  (API-Profil, Vertrauensgrenzen)
- **Schweregrad:** NIEDRIG (lokales Single-User-Token-Modell begrenzt die
  reale Ausnutzbarkeit deutlich, siehe "Auswirkung")
- **Ort:** `core/genesis_core/api/app.py`, `apply_metadata_suggestion`
- **Beleg:** `req.match` (das vom Client eingereichte `RecordingMatch`)
  wird 1:1 in ein `RecordingMatch`-Objekt übernommen und angewendet,
  sobald `confirm=true` gesetzt ist. Der konfigurierte Mindest-Konfidenzwert
  (`settings.metadata.min_confidence_for_suggestion`) wird nur beim
  **Generieren** der Vorschlagsliste (`suggest_for_media_file`) gefiltert,
  nicht erneut beim **Anwenden**. Der Server verifiziert nicht, dass
  `req.match` tatsächlich aus einer kürzlich für genau dieses `media_id`
  generierten, serverseitigen Vorschlagsliste stammt.
- **Ursache:** Architektur überträgt den vollständigen Vorschlag
  zustandslos zwischen GET (Vorschläge abrufen) und POST (übernehmen)
  über den Client, statt eine serverseitige Vorschlags-Session/einen
  opaken Verweis zu halten — eine bewusste, einfachere Design-Entscheidung,
  die aber die Konfidenz-Prüfung nur auf Client-Vertrauen stützt.
- **Auswirkung:** Bei einem Client-Bug (z.B. stale UI-Zustand nach
  schnellem Doppelklick, oder ein künftiges drittes UI mit eigenem Bug)
  könnte ein `match` mit sehr niedriger oder manipulierter Konfidenz ohne
  jede serverseitige Gegenkontrolle als `is_user_confirmed=True`
  gespeichert werden. **Keine Fremdangriffsfläche**, da der Endpunkt
  bereits durch das lokale Shared-Secret-Token (ADR-0006) geschützt ist —
  wer das Token hat, könnte ohnehin direkt in der DB editieren. Es handelt
  sich also um eine Härtung gegen **eigene Client-Fehler**, nicht gegen
  externe Angreifer.
- **Minimaler Fix:** Zusätzliche serverseitige Prüfung
  `req.match.confidence < settings.metadata.min_confidence_for_suggestion`
  → `422`, unabhängig vom `confirm`-Flag. Kein größeres Redesign
  (Vorschlags-Session-Cache) vorgenommen, da der Zusatznutzen den aktuellen
  Architekturumbau nicht rechtfertigt — als Backlog-Punkt vermerkt
  (Abschnitt 7).
- **Regressionstest:**
  `test_metadata_apply_rejects_match_below_configured_min_confidence`
  (`core/tests/test_api_phase2.py`) — verifiziert sowohl den
  HTTP-422-Response als auch, dass die DB tatsächlich unverändert bleibt.
- **Beweisstatus:** BELEGT (Code-Lektüre + Test, der zeigt, dass die
  Übernahme ohne den Fix durchgelaufen wäre — bestehender
  Happy-Path-Test `test_metadata_suggestions_and_apply_roundtrip` nutzt
  bewusst hohe Konfidenz und bleibt unverändert grün). **Vertrauen:** HOCH
  bzgl. der Korrektheit des Fixes, MITTEL bzgl. der realen
  Ausnutzbarkeit (siehe "Auswirkung" — bewusst niedrig eingestuft).
- **Status:** BEHOBEN.

### F-13 — Trailing-Punkt im Dateinamen bei leerem `{ext}`-Platzhalter (NIEDRIG)

- **Kategorie:** Funktionaler Defekt / Plattform-Kompatibilität (Python-Profil)
- **Schweregrad:** NIEDRIG
- **Ort:** `core/genesis_core/rename/templates.py`, `render_template`
- **Beleg:** `sanitize_filename_component` entfernt trailende Punkte/
  Leerzeichen nur PRO Platzhalterwert, nicht auf dem gesamten gerenderten
  Dateinamen. Ist die Original-Datei endungslos (`{ext}` rendert zu `""`)
  und die Vorlage endet mit `.{ext}`, entsteht ein Dateiname mit
  trailendem Punkt (z.B. "Titel."), was unter Windows beim Erstellen zu
  stillschweigender Normalisierung/Überraschungen führen kann.
- **Auswirkung:** Sehr seltener Randfall (nahezu alle Mediendateien haben
  eine Endung), aber ein reiner Ein-Zeilen-Fix ohne Risiko für bestehende
  Fälle.
- **Minimaler Fix:** `rendered = rendered.rstrip(". ")` am Ende von
  `render_template`, nach dem eigentlichen Formatieren.
- **Regressionstest:**
  `test_render_template_strips_trailing_dot_for_extensionless_file`,
  `test_render_template_does_not_strip_legitimate_trailing_extension`
  (Gegenprobe) in `core/tests/test_rename_templates.py`.
- **Beweisstatus:** BELEGT. **Vertrauen:** HOCH.
- **Status:** BEHOBEN.

## 5. Positiv bestätigte Schutzmaßnahmen (Phase-2-Module)

- `apply_renames`, `embed_artwork` und `apply_suggestion` erzwingen
  durchgehend `user_confirmed=True` als Pflichtparameter ohne Default —
  verifiziert per Code-Lektüre für alle drei Funktionen.
- Alle drei zugehörigen API-Endpunkte (`/rename/apply`,
  `/media/{id}/artwork/embed`, `/media/{id}/metadata-suggestions/apply`)
  lehnen fehlendes `confirm=true` mit `422` ab, BEVOR irgendein
  Datenbankzugriff oder Dateisystemzugriff erfolgt.
- `preview_renames`, `extract_embedded_artwork` und `fetch_artwork_online`
  sind nachweislich rein lesend bzw. schreiben ausschließlich in den
  GENESIS-eigenen Cache-Ordner — keine `os.rename`/Tag-Schreib-Aufrufe in
  diesen Funktionen (verifiziert per Code-Lektüre).
- `apply_renames` rollt bei einem Fehler mitten im Batch bereits
  durchgeführte Umbenennungen nachweislich zurück (bestehender Test
  `test_apply_rolls_back_completed_renames_on_mid_batch_failure`, in
  dieser Runde erneut gegengelesen und bestätigt).
- `fetch_artwork_online` liest das MusicBrainz-Release-MBID ausschließlich
  aus bereits in der DB vorhandenen, zuvor vom Nutzer bestätigten
  Album-Daten — es wird keine MBID geraten (konsistent mit dem in
  Sitzung 2 bestätigten MusicBrainz-MBID-Rateverbot).
- DB-Schema wird aktuell per `Base.metadata.create_all()` erzeugt (kein
  Alembic im Einsatz) — Hinzufügen der `mime_type`-Spalte in F-11 war
  daher ohne Migrationsaufwand möglich; verifiziert per
  `grep -n "create_all" genesis_core/db/__init__.py`.
- `.NET`-Client-Modell `RenamePreviewItem` enthält bereits das
  `EmptyFields`-Feld korrekt (parallel zu F-10 wäre dort also kein
  Analogiefehler vorhanden, falls künftig eine WPF-Umsetzung des
  Rename-Dialogs folgt).

## 6. Priorisierter Maßnahmenplan

**Sofort (in dieser Sitzung erledigt):**
- F-09, F-10, F-11, F-12, F-13 behoben und regressionsgetestet (7 neue
  Tests, Gesamtsuite 94 passed/1 skipped).
- F-08 nachträglich formal dokumentiert (war bereits vor dieser
  Review-Runde behoben, siehe ADR-0008).

**Kurzfristig:**
- Manuelle Verifikation von F-09 auf echtem Windows oder macOS (die
  Hardlink-basierte Stellvertreter-Testlogik in `ext4` kann die reale
  Case-insensitive-Situation nicht 1:1 nachstellen).
- `.NET`-Build erneut ausführen (SDK-Neuinstallation via
  `scripts/setup_dotnet_env.sh`), sobald an `GenesisApiClient.cs` oder der
  WPF-Oberfläche weitergearbeitet wird, um sicherzustellen, dass die
  Phase-2-Record-Typen weiterhin kompilieren.

**Mittelfristig:**
- F-12s zugrunde liegendes Architekturmuster (zustandslose
  Vorschlags-Übertragung über den Client) bei Bedarf durch eine
  serverseitige Vorschlags-Session mit opakem Verweis ersetzen, falls in
  späteren Phasen zusätzliche Angriffs-/Fehlklassen relevant werden
  (z.B. sobald das Plugin-System aus §48/§49 Drittanbieter-Metadaten-
  Provider erlaubt, die weniger vertrauenswürdig sind als die
  eingebauten).
- `Artwork.mime_type` ist nullable für Alt-Zeilen vor diesem Fix — bei
  einer künftigen Migration könnte ein Backfill-Skript (MIME-Typ aus
  eingebettetem Artwork der zugehörigen Datei neu auslesen) ergänzt
  werden, ist aber nicht zeitkritisch (Fallback-Logik deckt diesen Fall
  bereits sicher ab).

## 7. Offene Fragen / Annahmen (Korrektur zu Sitzung 2)

- **Korrigiert:** Die in Sitzung 2 getroffene Annahme "der .NET/WPF-Client
  kann in dieser Sandbox nicht kompiliert werden" ist überholt — siehe
  Abschnitt 1 dieser Sitzung. `dotnet build` mit
  `-p:EnableWindowsTargeting=true` funktioniert in der Linux-Sandbox und
  wurde in Sitzung 3 bereits erfolgreich mit 0 Errors/0 Warnings
  durchgeführt (siehe PROGRESS.md). Künftige Sitzungen sollten den
  tatsächlichen `dotnet build` nutzen, statt sich auf reine Code-Lektüre
  zu beschränken, sobald das SDK installiert ist.
- Weiterhin offen: F-09 wurde nur per Stellvertreter-Test (Hardlink)
  verifiziert, nicht auf einem echten case-insensitiven Dateisystem.
- Weiterhin offen (aus Sitzung 2 unverändert): formales .NET-xUnit-
  Testprojekt für `GenesisApiClient` fehlt noch; aktuelle
  .NET-Testtechnik nutzt `<Compile Include>` in Ad-hoc-Testprogrammen statt
  eines regulären Testprojekts.

---

# Deep-Review-Report — GENESIS Media Manager (Sitzung 11)

Erstellt gemäß derselben Methodik wie Sitzung 2/3
(`reference/review-prompt-pack/DEEP_REVIEW_PROMPT_DE.md`, AI Deep Review
Prompt Pack v1.2.2). Sitzung 2/3 deckten Foundation + die ersten
Phase-2-Module ab; seitdem (Sitzungen 4–10) wurden Phase 2 (Rest),
Phase 3 (Audio), Phase 4 (Hörbücher), Phase 5 (Video), Phase 6 (KI),
Phase 7 (Voice Studio), Phase 8 (Download/Import) und Phase 9
(Härtung: Plugins, Job-Steuerung, Fehler-Center, Diagnose, Backup,
Scan & Repair, Temp-Aufräumung, Export, Relokation) vollständig neu
gebaut, OHNE dass seitdem ein weiterer Deep-Review-Pass durchgeführt
wurde. Diese Sitzung schließt genau diese Lücke.

## 1. Prüfkontext und Grenzen

- **Geprüfter Stand:** der gesamte seit Sitzung 3 hinzugekommene Code in
  `core/genesis_core/` (Cutter, Konvertierung, Lautheit, Duplikate,
  Qualität, Hörbuch/Kapitel, Video, KI-Metadaten/-Suche/-Musik, Voice
  Studio, Download/Import, Plugins, Job-Steuerung, Fehlerbehandlung,
  Diagnose, Backup, Scan & Repair, Temp-Aufräumung, Export, Relokation)
  sowie die zugehörigen PySide6-Ansichten/-Dialoge.
- **Nicht erneut geprüft:** Foundation- und frühe Phase-2-Module
  (Scanner, Metadaten-Engine, Konfiguration, API-Grundgerüst, Rename-
  Engine, Artwork-Engine) — bereits in Sitzung 2/3 tiefengeprüft, in
  dieser Sitzung nur stichprobenartig auf Konsistenz der dort etablierten
  Muster (Auth-Abdeckung, Confirm-Pflicht, Pfadsicherheit) hin erneut
  gegengeprüft, nicht vollständig neu durchleuchtet.
- **Schwerpunkt dieser Runde:** gezielte, belegbasierte Prüfung
  gegen die projekteigenen Leitprinzipien (keine stillen Fehler, kein
  Shell-/SQL-Injection-Vektor, Confirm-Pflicht bei jeder Änderung,
  Auth auf jedem Endpunkt, korrekte Ausgabe-Kontext-Kodierung in der UI)
  statt eines erschöpfenden Line-by-Line-Audits jeder einzelnen der
  mittlerweile ~30 Backend-Module — bei diesem Umfang wäre Letzteres in
  einer Sitzung nicht seriös leistbar; stattdessen wurden die laut
  Prompt-Pack höchsten Risikoklassen (B2 Injection, B3 Auth/Secrets, B4
  Fehlerbehandlung) gezielt mit Tooling (grep/AST über alle Routen)
  flächendeckend geprüft.
- **Reproduktionsumgebung:** Linux-Sandbox, Python 3.13, pytest,
  PySide6 unter `QT_QPA_PLATFORM=offscreen`. .NET/WPF weiterhin nur
  durch Code-Lektüre geprüft (kein Windows verfügbar).
- **Angenommen/nicht verifizierbar:** keine Windows-spezifischen
  Pfadlängen-/Zeichensatz-Grenzfälle in dieser Linux-Sandbox real
  getestet (ANNAHME, siehe bereits in Sitzung 2/3 dokumentierte gleiche
  Einschränkung).

## 2. Aktivierte Profile

| Profil | Angewendet auf |
|---|---|
| Python (315) | alle seit Sitzung 3 neuen `core/genesis_core/**/*.py`-Module |
| API REST (597) | alle 95 Routen in `core/genesis_core/api/app.py` |
| KI/LLM/Agent (655) | `core/genesis_core/ai/` — insbesondere Prompt-Injection-Neubewertung |
| Bash/POSIX (467) | `scripts/setup_python_env.sh`, `scripts/setup_voice_studio.sh` (Stichprobe) |

## 3. Architektur-Ergänzung seit Sitzung 2/3

```
[PySide6-UI] --HTTP+Token--> [FastAPI Core-API] --SQLAlchemy--> [SQLite]
                                    |
                                    +--> [PluginRegistry] --exec in-process--> [data_dir/plugins/*/plugin.py] (NEU, §34)
                                    +--> [JobManager] --kooperative Checkpoints--> [ProcessingJobs] (NEU, §35/§36)
                                    +--> [globaler Exception-Handler] --> [ErrorLog] (NEU, §37)
                                    +--> [AIEngine] --Text-Kontext--> [Ollama/LM Studio, lokal] (Phase 6)
                                    +--> [DownloadEngine] --yt-dlp/HTTP--> [YouTube/TikTok/Direkt-URL] (Phase 8)
                                    +--> [VoiceEngine] --subprocess--> [Piper, lokal] (Phase 7)
```

Neue Vertrauensgrenze seit Sitzung 2/3: **Plugin-Code** (§34) läuft
in-process im selben Python-Interpreter wie der Core Service - siehe
Finding F-11-3 unten für die konkrete Konsequenz daraus.

## 4. Executive Summary

**Risikostufe gesamt: NIEDRIG-MITTEL** (unverändert zur nach Sitzung 2/3
erreichten Einstufung — keine neuen HOCH/KRITISCH-Funde in den seitdem
hinzugekommenen sieben Phasen).

**Findings nach Schweregrad:** KRITISCH: 0 · HOCH: 0 · MITTEL: 4 (alle
in dieser Sitzung behoben — zwei davon, F-11-4/F-11-5, erst in einer
Fortsetzung derselben Sitzung gefunden, nachdem die in Abschnitt 8
("Offene Fragen") zunächst nur als Backlog vermerkten Vertiefungspunkte
tatsächlich durchgeführt wurden) · NIEDRIG: 1 (behoben) · INFO: 2
(dokumentiert, kein Code-Fix nötig/sinnvoll).

Das ist ein deutlich besseres Bild als nach Sitzung 2 (damals 2 HOCH-
Funde) — plausibel, weil die seit Sitzung 3 etablierten Muster (DB als
alleinige Quelle für Dateipfade, Confirm-Pflicht, require_token auf jeder
Route) über alle sieben neuen Phasen hinweg konsequent wiederverwendet
statt pro Phase neu erfunden wurden.

## 5. Findings

### F-11-1 — MITTEL: Qt-Rich-Text-Autoerkennung zeigt externe/dynamische Inhalte potenziell als fehlerhaft formatiertes Markup statt als reinen Text

- **Kategorie:** Ausgabe-Kontext-Kodierung (B2)
- **Ort:** `QLabel.setText()` nutzt standardmäßig `Qt.AutoText` und
  interpretiert einen String als Rich-Text, sobald er wie HTML-Markup
  aussieht (`Qt.mightBeRichText()`-Heuristik). Betroffen: jeder Text, der
  nicht vom Entwickler selbst stammt, sondern aus Core-API-Antworten
  (Fehlermeldungen/technische Details, §37), Dateipfaden (Job-
  `current_item`, §35/§36), Plugin-Metadaten (§34) oder KI-generierten
  Metadatenvorschlägen (§25) gelesen wird.
- **Beleg:** `ai_dialog.py` zeigte KI-Vorschlagswerte (`field_value`) und
  gespeicherte KI-Metadaten ungefiltert per `QLabel.setText()` an;
  ebenso neu in dieser Sitzung geschriebene Ansichten
  (`error_center_view.py`, `job_queue_view.py`, `plugins_view.py`) sowie
  `error_dialog.show_api_error()` (`QMessageBox.setText()` hat dieselbe
  Heuristik).
- **Einordnung:** KEINE Remote-Code-Execution (Qt-Rich-Text ist ein stark
  eingeschränktes HTML-Subset ohne JavaScript) — aber ein entsprechend
  benannter Dateiname oder eine KI-Ausgabe könnte Teile der Anzeige
  verschwinden lassen oder Formatierung vortäuschen, was in einem
  Werkzeug, das u.a. Vertrauensentscheidungen über Metadatenübernahmen
  anzeigt, ein reales Robustheitsproblem ist.
- **Fix (in dieser Sitzung umgesetzt):** `genesis_ui/widgets.set_plain_text()`
  (erzwingt `Qt.PlainText`) neu eingeführt und angewendet auf
  `ai_dialog.py` (`stored_metadata_label`), `error_center_view.py`
  (`detail_label`), `job_queue_view.py` (`current_item_label`),
  `plugins_view.py` (`plugins_dir_label`), `error_dialog.show_api_error()`
  (`QMessageBox.setTextFormat`). Tests:
  `test_deep_review_sitzung11_fixes.py::test_set_plain_text_forces_plain_text_format`,
  `::test_show_api_error_forces_plain_text_on_message_box`.
- **Bewusst NICHT vollständig migriert:** die übrigen, vor dieser Sitzung
  entstandenen Views (`duplicates_view.py`, `download_center_view.py`
  u.a.) zeigen ebenfalls teils dynamische Inhalte (z.B. Dateipfade,
  Scan-Begründungen) und wurden NICHT rückwirkend umgestellt — als
  Backlog in PROGRESS.md vermerkt, da eine vollständige Migration aller
  ~20 View-Dateien den Rahmen dieser Review-Sitzung gesprengt hätte und
  das Risiko (lokale Desktop-App, kein Mehrbenutzerbetrieb, keine
  Code-Ausführung möglich) als vertretbar eingestuft wird.

### F-11-2 — MITTEL: Qt-Mnemonic-Fehlinterpretation von `&` in KI-generiertem Checkbox-Text

- **Kategorie:** Fachliche Korrektheit / Ausgabe-Kontext (B1/B2)
- **Ort:** `ai_dialog.py`, KI-Vorschlag-Checkboxen (§25).
- **Beleg:** `QCheckBox`/`QPushButton`/`QRadioButton`/`QGroupBox`
  interpretieren ein einzelnes `&` im Text standardmäßig als Mnemonic-
  Markierung für das nächste Zeichen (z.B. unterstrichenes Zeichen +
  Alt-Tastenkürzel). Der KI-Vorschlag-Text wurde aus `field_value`
  (KI-generierter Wert, z.B. ein vorgeschlagenes Genre) OHNE Escaping in
  eine `QCheckBox` eingesetzt. Echte Musik-/Film-/Hörbuchmetadaten
  enthalten sehr häufig `&` ("Simon & Garfunkel", "Earth, Wind & Fire",
  "Dungeons & Dragons"-Hörbücher) — ein KI-Vorschlag wie "Rock & Pop"
  hätte "Rock Pop" mit unterstrichenem "P" angezeigt und Alt+P als
  ungewolltes Tastenkürzel für genau diese Checkbox registriert.
- **Fix:** `genesis_ui/widgets.escape_mnemonic()` (verdoppelt `&`) neu
  eingeführt, in `ai_dialog.py` vor dem `QCheckBox`-Konstruktor
  angewendet. Grep-Audit aller `QCheckBox(`/`QPushButton(`/
  `QRadioButton(`/`QGroupBox(`-Konstruktoraufrufe im gesamten
  `ui-reference-pyside/`-Baum ergab, dass dies die EINZIGE Stelle im
  Projekt ist, an der dynamischer statt rein übersetzter, fest im
  Quellcode stehender Text in ein Mnemonic-fähiges Widget fließt — kein
  weiterer Fund nötig.
  Test: `test_ai_dialog_suggestion_checkbox_escapes_ampersand_in_ai_value`.

### F-11-3 — NIEDRIG: `ExporterPlugin.file_extension()` war definiert, aber nie aufgerufen; Rückgabewert war außerdem ungeprüft

- **Kategorie:** API-Vollständigkeit / Eingabevalidierung (B2/B7)
- **Ort:** `GET /plugins/export/{plugin_id}` (§34+§42).
- **Beleg:** Die Plugin-Schnittstelle verlangt `file_extension()`, der
  Endpunkt rief sie aber nie auf — der Client bekam immer `text/plain`
  ohne Dateinamen-Vorschlag (`Content-Disposition` fehlte komplett).
  Zusätzlich: Plugin-Code gilt laut Moduldocstring explizit als nicht
  vertrauenswürdig (siehe §34-Sandboxing-Strategie) — ein Rückgabewert
  wie `"../../etc/passwd"` oder eine im Aufruf werfende Methode wäre VOR
  dem Fix ungeprüft in den `Content-Disposition`-Header geflossen.
- **Fix:** `PluginRegistry.safe_export_filename()` ruft `file_extension()`
  jetzt in einem eigenen try/except auf (dieselbe Fehlerisolierungs-
  Philosophie wie beim Laden/`export()`-Aufruf) und lässt nur rein
  alphanumerische Werte bis 10 Zeichen durch, sonst Fallback `.txt`. Der
  Endpunkt setzt jetzt einen korrekten `Content-Disposition`-Header;
  `media_type` bleibt bewusst IMMER `text/plain` (nie z.B. `text/html`),
  damit ein Plugin niemals aktiven Inhalt im Browser-Kontext auslösen
  kann. 4 neue Tests in `test_plugins.py`
  (`test_safe_export_filename_*`), 1 erweiterter Test in
  `test_api_plugins.py` prüft den tatsächlichen HTTP-Header.

### F-11-4 — MITTEL: Job-Statusübergänge (pause/resume/cancel) waren weder gegen ungültige Übergänge noch gegen Rennbedingungen abgesichert

- **Kategorie:** Fachliche Korrektheit / Nebenläufigkeit (B5)
- **Ort:** `JobManager.pause/resume/cancel/start/complete` (§35/§36),
  `/jobs/{id}/pause|resume|cancel` (`core/genesis_core/api/app.py`).
- **Beleg:** Jede der vier Methoden setzte den Zielstatus UNCONDITIONAL
  (kein Blick auf den tatsächlichen aktuellen Status) UND las/schrieb
  ihn in zwei getrennten DB-Sitzungen (`get_job()` dann `_update()`) -
  eine klassische Lost-Update-Rennbedingung. Konkret reproduzierbar: ein
  `resume()`-Aufruf auf einen bereits `COMPLETED`/`FAILED`/`CANCELLED`-Job
  setzte ihn kommentarlos auf `RUNNING` zurück, obwohl keine Engine mehr
  tatsächlich daran arbeitet - ein "Geister-Job", der im Job-Queue-UI für
  immer als "läuft" angezeigt wird, ohne je wieder Fortschritt zu machen.
  Per direktem Multi-Thread-Stresstest gegen `JobManager` nachgestellt
  (siehe `test_concurrent_cancel_and_resume_never_leaves_job_running`).
  Verbindungsebene selbst war unkritisch: SQLAlchemy setzt
  `check_same_thread=False` automatisch, sobald `QueuePool` (Standard für
  dateibasiertes SQLite) genutzt wird - per Experiment verifiziert, dass
  eine in Thread A geöffnete Verbindung sicher in Thread B weiterverwendet
  werden kann. Das eigentliche Problem lag ausschließlich auf
  Anwendungsebene (fehlende Zustandsmaschine + fehlende Atomarität), nicht
  in der DB-Schicht.
- **Fix:** `JobManager._transition()` (neu) führt Lesen des aktuellen
  Status und Schreiben des neuen Status ATOMAR aus (ein Prozess-weiter
  `threading.Lock` + eine einzige DB-Transaktion) und akzeptiert nur
  explizit erlaubte Herkunftsstatus je Methode (`start`: nur PENDING;
  `pause`: nur RUNNING; `resume`: nur PAUSED; `complete`: RUNNING/PAUSED;
  `cancel`: PENDING/RUNNING/PAUSED, dabei bewusst idempotent bei bereits
  CANCELLED, da `execute_repairs_endpoint` `cancel()` nach einem
  `JobCancelledError` ein zweites Mal aufruft). Ungültige Übergänge lösen
  `JobTransitionError` aus, von der API-Schicht auf HTTP 409 gemappt
  (`fail()` bleibt bewusst OHNE Zustandsprüfung - "als fehlgeschlagen
  markieren" muss laut Prinzip #19/§37 immer möglich sein). Siehe
  Nachtrag zu ADR-0020/Entscheidung 2 in `DECISIONS.md`.
- **Tests:** 5 neue Tests in `core/tests/test_jobs.py`
  (u.a. `test_resume_rejects_already_completed_job`,
  `test_cancel_is_idempotent_when_already_cancelled`,
  `test_concurrent_cancel_and_resume_never_leaves_job_running`), 3 neue
  Tests in `core/tests/test_api_errors_and_jobs.py` für die HTTP-409-
  Antwort auf API-Ebene. Volle Regression bestätigt grün (siehe
  Abschnitt 7).

### F-11-5 — MITTEL: Ein hängendes (nicht nur fehlerhaftes) Plugin blockierte nachweislich den gesamten Core-Service-Start

- **Kategorie:** Verfügbarkeit / Ressourcenerschöpfung (B2/B9)
- **Ort:** `PluginRegistry._load_single_plugin`/`call_exporter`/
  `safe_export_filename` (§34).
- **Beleg:** ADR-0020/Entscheidung 1 beschreibt ausdrücklich
  Fehlerisolierung gegen EXCEPTIONS beim Laden und beim Aufruf - geprüft
  und bestätigt korrekt (siehe Abschnitt 6). Ein Plugin, das stattdessen
  HÄNGT (Endlosschleife, ein blockierender Aufruf ohne eigenes Timeout -
  ein gewöhnlicher, nicht böswilliger Programmierfehler, also exakt
  innerhalb des von der ADR selbst beschriebenen Bedrohungsmodells "eigene/
  Community-Plugins mit Programmierfehlern"), wurde von keinem
  try/except abgefangen. Empirisch reproduziert: ein Plugin mit
  `time.sleep(9999)` auf Modulebene ließ `discover_and_load()` - und
  damit beim echten Core-Service-Start `AppState.__init__` - unbegrenzt
  hängen (`timeout 8 python3 -c "..."` lief reproduzierbar in den
  Timeout, kein Rückkehrwert). Das ist die schwerste Form eines §34-
  Verstoßes: nicht nur dieses eine Plugin, sondern die GESAMTE Anwendung
  startet nie.
- **Fix:** Laden (Import+Instanziierung+Validierung) UND jeder
  Laufzeitaufruf (`export()`, `file_extension()`) laufen jetzt zusätzlich
  mit einem Zeitlimit in einem eigenen Daemon-Thread
  (`_run_with_timeout()`, neu in `genesis_core/plugins/__init__.py`;
  bewusst `threading.Thread(daemon=True)` statt `concurrent.futures.
  ThreadPoolExecutor`, dessen Worker-Threads NICHT daemonisch sind und
  bei einem für immer hängenden Plugin sogar einen sauberen Shutdown des
  gesamten Core-Service-Prozesses verhindert hätten - ebenfalls
  empirisch verifiziert und korrigiert). Zeitlimits:
  `PLUGIN_LOAD_TIMEOUT_SECONDS=10s`, `PLUGIN_CALL_TIMEOUT_SECONDS=60s`,
  `PLUGIN_METADATA_CALL_TIMEOUT_SECONDS=5s`. Nach Ablauf kehrt die
  Funktion sofort mit einem klaren `load_error`/Aufruf-Fehler zurück, die
  Anwendung bleibt bedienbar. Ausdrücklich dokumentierte Restlücke: der
  gehängte Hintergrund-Thread selbst kann in Python nicht hart terminiert
  werden und läuft im schlimmsten Fall bis zum Prozessende weiter - die
  vollständige Lösung (Prozess- statt Thread-Isolation mit hartem
  `terminate()`) bleibt Teil des bereits dokumentierten "echte
  OS-Sandbox"-Backlogs und wurde hier bewusst NICHT nebenbei mitgezogen.
- **Tests:** 5 neue Tests in `core/tests/test_plugins.py` (u.a.
  `test_hanging_plugin_at_load_time_times_out_instead_of_blocking_forever`,
  `test_hanging_exporter_call_times_out_instead_of_blocking_forever`),
  per `monkeypatch` auf 0.2s verkürzte Zeitlimits für schnelle Testläufe.

### I-11-1 — INFO: "Rollback-Grundlage" bei Scan & Repair (§39) ist grobkörnig (ganze DB), nicht zeilengenau

- **Kategorie:** Dokumentationsklarheit (B7)
- **Beleg:** `execute_repairs()` protokolliert bei
  `ACTION_CLEANUP_ORPHANED_ROWS` nur die entfernten IDs in
  `ProcessingHistory.before`, nicht die vollständigen Zeileninhalte - ein
  gezieltes "nur diese eine Reparaturaktion rückgängig machen" ist damit
  NICHT direkt aus der History-Tabelle möglich. Tatsächliche
  Wiederherstellbarkeit ist trotzdem gegeben: `execute_repairs()` legt
  NACHWEISLICH (Code-Lektüre + `test_repair.py`) vor jeder Ausführung
  automatisch ein vollständiges DB-Backup an (§40) - ein Rollback ist
  also jederzeit über `POST /backup/{id}/restore` möglich, nur eben als
  Wiederherstellung des GESAMTEN Standes vor der Reparatur, nicht als
  gezieltes Undo einer einzelnen Teilaktion.
- **Bewertung:** Kein Fehler, aber die Doc-Kommentare ("ProcessingHistory,
  Rollback-Grundlage") könnten eine feinere Granularität suggerieren, als
  tatsächlich gegeben ist. Empfehlung für eine künftige Sitzung: Kommentar
  in `repair/__init__.py` präzisieren ("Rollback erfolgt über das vor
  Ausführung angelegte DB-Backup, nicht zeilengenau aus der History").
  Kein Code-Fix in dieser Sitzung, da das zugrundeliegende Verhalten
  bereits sicher ist (kein Datenverlustrisiko) und eine Änderung der
  History-Struktur app-weite Rückwirkungen hätte, die eine eigene
  Review-Runde verdienen.
- **Nachtrag (Sitzung 12) — RESOLVED:** Modul-Docstring und
  `execute_repairs()`-Docstring in `core/genesis_core/repair/__init__.py`
  präzisiert wie oben empfohlen: Rollback erfolgt nachweislich über das
  vor Ausführung angelegte vollständige DB-Backup
  (`POST /backup/{id}/restore`), nicht über eine zeilengenaue
  ProcessingHistory-Undo-Funktion. Reiner Doku-Fix, kein
  Verhaltensunterschied; `core`-Tests laufen unverändert grün (520
  passed, 7 skipped).

### I-11-2 — INFO (Backlog geschlossen bewertet): Prompt-Injection-Neubewertung vor Phase 6 — jetzt durchgeführt

- **Hintergrund:** Sitzung 1/2 hatte explizit vermerkt: "Prompt-
  Injection-Neubewertung vor Phase 6 (sobald KI-Tool-Calling/Auto-Apply
  existiert)".
- **Ergebnis dieser Neubewertung:** Das in Phase 6 tatsächlich gebaute
  `genesis_core/ai/engine.py` implementiert WEDER Tool-Calling NOCH
  Auto-Apply. Der Kontext für das lokale Modell besteht ausschließlich
  aus bereits bekannten Textfeldern (Dateiname, vorhandene Tags/DB-Werte)
  — der Dateiname ist zwar theoretisch vom Nutzer beeinflussbar, aber das
  Modell kann daraus bestenfalls eine manipulierte TEXT-Antwort erzeugen.
  Diese Antwort (a) wird NIE automatisch übernommen
  (`apply_suggestions()` verlangt `confirm=True` UND eine vom Aufrufer
  explizit übergebene, vom Nutzer ausgewählte Teilmenge `accepted`), (b)
  landet ausschließlich in der separaten `AIMetadata`-EAV-Tabelle, NIE in
  kanonischen Track-/Movie-/Episode-Feldern, (c) wird nirgends als Datei-
  pfad, SQL-Fragment oder Shell-Kommando weiterverwendet (durchgängig
  parametrisierte ORM-Statements, siehe `apply_suggestions()`). Die
  einzige reale Auswirkung einer "erfolgreichen" Prompt-Injection über den
  Dateinamen wäre eine ungewöhnliche, aber harmlose Text-Anzeige, die
  ohnehin Gegenstand von Finding F-11-1/F-11-2 ist (jetzt behoben).
- **Einordnung:** Für den AKTUELLEN Funktionsumfang als geprüft und
  unkritisch bewertet — NICHT dauerhaft abgeschlossen: Sollte eine
  künftige Phase echtes Tool-Calling/Funktionsaufrufe/Auto-Apply für KI-
  Vorschläge einführen, muss diese Bewertung zwingend wiederholt werden
  (gleicher Hinweis bleibt als Backlog-Eintrag in PROGRESS.md bestehen,
  nur mit präzisierter Bedingung).

## 6. Positiv bestätigt (flächendeckend per Tooling geprüft, nicht nur stichprobenartig)

- **Auth-Abdeckung:** automatisierte Prüfung aller 95 `@app.get/post/
  patch/delete`-Routen in `app.py` ergab genau EINE Route ohne
  `dependencies=[require_token]` — `GET /health`, by-design (siehe ADR-
  0006, muss vor Tokenbesitz erreichbar sein, liefert keine sensiblen
  Daten).
- **Confirm-Pflicht:** jeder destruktive/ändernde Endpunkt
  (`*/apply`, `*/restore`, `/repair/execute`, `/relocate/apply`) prüft
  `confirm`/`user_confirmed` und lehnt ohne diesen Wert mit 403/422 ab —
  konsistent über alle sieben neuen Phasen hinweg.
- **Keine Shell-/SQL-Injection-Vektoren:** kein `shell=True` im gesamten
  Projekt (`grep`-Vollsuche), alle `subprocess.run`-Aufrufe (ffmpeg,
  ffprobe, fpcalc, yt-dlp, Piper) nutzen Listen-Argumente statt
  String-Interpolation, keine rohen SQL-Strings (weiterhin
  ausschließlich SQLAlchemy-ORM).
- **Keine Credential-/Cookie-Speicherung:** `genesis_core/download/`
  enthält an keiner Stelle Code zum Speichern von Zugangsdaten/Cookies
  (grep-Vollsuche über alle Download-Provider-Module).
- **Pfadsicherheit bei generierten Ausgabedateien:** Cutter/Konvertierung/
  Lautheits-Normalisierung leiten `output_path` ausschließlich aus dem
  bereits validierten Quelldateinamen (Stem) + festem, hartcodiertem
  Suffix + whitelisted Extension ab — kein Client-/KI-/Plugin-
  kontrollierter String fließt in einen neuen Dateipfad ein.
  `source_path` für JEDE destruktive Medienoperation kommt ausschließlich
  aus einem DB-Lookup via `media_id` (Pfad niemals aus dem Client-Body
  übernommen).
- **Plugin-Fehlerisolierung gegen Exceptions** (§34) funktioniert
  nachweislich wie spezifiziert: das mitgelieferte `examples/
  broken_example/plugin.py` (wirft beim Import) destabilisiert weder das
  Laden der übrigen Plugins noch den Host-Prozess (`test_plugins.py`,
  `test_api_plugins.py`) — die zusätzlich notwendige Absicherung gegen
  HÄNGENDE (nicht nur werfende) Plugins war dagegen lückenhaft, siehe
  F-11-5.
- i18n-Vollständigkeit (§53) weiterhin automatisiert abgesichert
  (`test_all_languages_have_identical_key_sets`, jetzt 685 Schlüssel je
  Sprache) — Stichproben-Grep über alle fünf in dieser Sitzung neuen
  PySide6-Views ergab keine hartcodierten UI-Strings.
- **Alle vier im Projekt vorkommenden `unlink()`-Aufrufstellen** einzeln
  per Code-Lektüre geprüft (`backup/__init__.py` Backup-Rotation,
  `diagnostics/__init__.py` Schreibrechte-Probe-Datei,
  `voice/engine.py` Synthese-Zwischen-WAV, sowie die bereits in einer
  früheren Teilsitzung geklärte Stelle in `storage/`): alle vier löschen
  AUSSCHLIESSLICH selbst erzeugte, intern konstruierte Pfade (niemals
  einen vom Nutzer/Client/einer KI gelieferten Pfad), jeweils mit
  `exists()`-Prüfung davor und sauberer Fehlerbehandlung danach — keine
  Verstöße gegen Prinzip #4 ("Originaldateien nie ungefragt löschen")
  gefunden.
- **JobManager-Nebenläufigkeit** vertieft geprüft (siehe F-11-4) —
  DB-Verbindungsebene war bereits sicher (SQLAlchemy/`QueuePool` erlaubt
  Cross-Thread-Nutzung derselben SQLite-Verbindung nachweislich
  gefahrlos), die gefundene und behobene Lücke lag ausschließlich auf
  Anwendungsebene (fehlende Zustandsmaschine/Atomarität).
- **Plugin-Exception-Isolation vs. ADR-0020-Zusagen** Punkt für Punkt
  nachgeprüft: Laden in UUID-eindeutigem Modulnamen ✓, Entfernen aus
  `sys.modules` in jedem Fall (`finally`) ✓, ein kaputtes Plugin blockiert
  die übrigen nicht ✓, Laufzeitfehler in `export()` werden abgefangen ✓ —
  alle Zusagen bezüglich EXCEPTIONS halten. Die fehlende Zusage
  bezüglich HÄNGENDER Plugins wurde als F-11-5 gefunden und behoben.

## 7. Nach Fixes erneut vollständig getestet

- `cd core && python3 -m pytest -q` → **520 passed, 7 skipped**
  (507 nach F-11-1/F-11-2/F-11-3, dann +13 weitere Tests für F-11-4/
  F-11-5: 5 in `test_jobs.py`, 3 in `test_api_errors_and_jobs.py`,
  5 in `test_plugins.py`). Ein einzelner Zwischenlauf zeigte einen
  transienten HTTP-503-Fehlschlag des echten MusicBrainz-Live-Tests
  (externer Dienst, Rate-Limiting) — im direkten Folgelauf wieder grün,
  unabhängig von allen Aenderungen dieser Sitzung.
- `cd ui-reference-pyside && QT_QPA_PLATFORM=offscreen python3 -m pytest
  tests/ -q` → **24 passed** (unverändert seit F-11-1/F-11-2, F-11-4/
  F-11-5 betreffen nur `core/`).
- Empirische Vorher/Nachher-Reproduktion von F-11-5 (siehe Finding):
  vorher `timeout 8 ...` → Prozess durch Timeout beendet (kein
  Rückkehrwert); nachher derselbe Testfall → `discover_and_load()`
  kehrt nach 10s mit `load_error` zurück, Prozess beendet sich danach
  sauber (`exit code 0`) statt durch den Hintergrund-Thread blockiert zu
  bleiben.

## 8. Offene Fragen / verbleibendes Backlog

- ERLEDIGT (Sitzung 12): F-11-1-Migration für die vor Sitzung 11
  entstandenen View-/Dialog-Dateien auf `set_plain_text()` umgestellt,
  überall dort, wo QLabel-Text dynamische/externe Inhalte anzeigt
  (Fehlermeldungen, Dateipfade, Provider-/Modell-Namen, Lizenztexte):
  `dialogs/audiobook_dialog.py`, `dialogs/video_dialog.py` (inkl. der
  beiden `*_status_label`-Ladefehler), `views/dashboard.py`,
  `views/diagnostics_view.py` (`overall_label`),
  `views/download_center_view.py` (inkl. eines rohen `str(exc)` ganz
  ohne `tr()`-Wrapper), `views/duplicates_view.py`,
  `views/ai_center_view.py`, `views/backups_view.py`,
  `views/voice_studio_view.py`, `dialogs/artwork_dialog.py`,
  `dialogs/convert_dialog.py`, `dialogs/cutter_dialog.py`,
  `dialogs/loudness_dialog.py`, `dialogs/metadata_dialog.py`,
  `dialogs/rename_dialog.py`. Dabei neu bestätigt und dokumentiert:
  `QTreeWidgetItem`/`QListWidgetItem`/Tabellenzellen-Text lösen Qts
  Rich-Text-Auto-Erkennung NICHT aus (anders als `QLabel`/
  `QMessageBox`) und benötigen daher keinen Fix; rein numerische
  Felder (Jahr, Staffel, Episodennummer, Zähler) blieben bewusst bei
  `setText()`. `QMessageBox.critical(...)`-Aufrufe (statische
  Convenience-Methode ohne `setTextFormat`-Kontrolle) wurden NICHT in
  dieser Runde migriert — das ist ein separates, bereits zuvor
  erkanntes Backlog-Thema (Umstellung auf `show_api_error()`), hier
  bewusst nicht mitgezogen, um den Scope eng zu halten. Beide
  Testsuiten laufen danach unverändert grün (`core`: 520 passed/7
  skipped; `ui-reference-pyside`: 24 passed).
- ERLEDIGT (Sitzung 12, unmittelbare Fortsetzung auf Nutzerwunsch
  "weiter"): das oben als "separates Backlog-Thema" benannte
  `QMessageBox.critical(...)` → `show_api_error()`-Umstellung jetzt
  vollständig durchgeführt — alle 24 Aufrufstellen für `GenesisAPIError`
  in 12 Dateien (`views/duplicates_view.py`, `views/media_table.py`,
  `views/voice_studio_view.py`, `dialogs/ai_dialog.py`,
  `dialogs/artwork_dialog.py`, `dialogs/audiobook_dialog.py` [7×],
  `dialogs/convert_dialog.py`, `dialogs/cutter_dialog.py`,
  `dialogs/loudness_dialog.py`, `dialogs/metadata_dialog.py`,
  `dialogs/rename_dialog.py`, `dialogs/video_dialog.py` [2×]) nutzen
  jetzt `show_api_error()`. Um dabei die bisherige, handlungsspezifische
  Fehlermeldung (z.B. "Kapitel konnten nicht geladen werden: {error}")
  NICHT durch einen generischen `str(exc)`-Text zu ersetzen, wurde
  `show_api_error()` um einen optionalen `message`-Parameter erweitert
  (`genesis_ui/dialogs/error_dialog.py`): die aufrufende Stelle übergibt
  weiterhin ihren bisherigen, bereits übersetzten Text als `message`,
  `show_api_error()` ergänzt in jedem Fall zusätzlich die Fehler-ID/den
  Lösungshinweis darunter, falls vorhanden — reiner Zugewinn ohne
  Textverlust. Bewusst NICHT migriert: der einzige `OSError`-Fall in
  `audiobook_dialog.py` (`export_write_failed`, lokales Datei-Schreiben
  beim Kapitel-Export) bleibt bei einfachem `QMessageBox.critical(...)`,
  da `show_api_error()` explizit für `GenesisAPIError` typisiert ist
  (kein `error_id`/`solution_hint` bei einem `OSError`). In
  `duplicates_view.py` wurde der dadurch ungenutzt gewordene
  `QMessageBox`-Import entfernt. 3 neue Regressionstests in
  `test_deep_review_sitzung12_fixes.py` (u.a. End-to-End über
  `ArtworkDialog._on_embed_clicked()` mit einem fehlschlagenden Fake,
  der beweist, dass sowohl die bisherige Meldung als auch Fehler-ID/
  Lösungshinweis gemeinsam angezeigt werden). Beide Testsuiten grün:
  `core` 520 passed/7 skipped (unverändert), `ui-reference-pyside`
  **27 passed** (24 + 3 neue).
- I-11-1-Doku-Präzisierung in `repair/__init__.py` — ERLEDIGT (Sitzung
  12), siehe Nachtrag im jeweiligen Finding-Abschnitt oben.
- Neu gefunden und behoben (Sitzung 12, kein eigenes Finding, da reine
  Testumgebungs-Infrastruktur): `scripts/setup_python_env.sh` prüfte
  bislang nicht die System-Bibliothek `libxkbcommon.so.0`, die Qt/
  PySide6 selbst im `QT_QPA_PLATFORM=offscreen`-Testmodus zur Laufzeit
  benötigt (pip-Paket allein reicht nicht). Das Skript installiert nun
  bei Bedarf automatisch `libxkbcommon0`/`libxkbcommon-x11-0` via apt.
- I-11-2 bleibt als bedingter Backlog-Punkt bestehen (erneut bewerten,
  sobald Tool-Calling/Auto-Apply für KI-Vorschläge eingeführt wird).
- ERLEDIGT in dieser Sitzung (zuvor hier als offen gelistet): alle
  verbleibenden `unlink()`-Aufrufstellen geprüft (siehe Abschnitt 6),
  JobManager-Nebenläufigkeit geprüft und behoben (F-11-4), Plugin-
  Fehlerisolierung vs. ADR-0020-Zusagen geprüft und die gefundene Lücke
  (hängende statt werfende Plugins) behoben (F-11-5).
- Weiterhin unverändert aus Sitzung 2/3: echte OS-Prozess-Sandbox für
  Plugins (§34, bewusste Folgeentscheidung, siehe ADR-0020 inkl.
  Nachtrag — ein Zeitlimit schützt vor Hängern, aber NICHT vor aktiv
  böswilligem Code, der innerhalb des Zeitlimits Schaden anrichtet),
  vollständige .NET/WPF-Parität mit allen seit Phase 5 hinzugekommenen
  Endpunkten, Dependency-Pinning/Lockfile und Lizenzaudit vor
  Release-Gate (Phase 10, explizit zurückgestellt).

---

# Deep-Review-Report — GENESIS Media Manager (Sitzung 13)

## 1. Prüfkontext und Grenzen

Auf expliziten Nutzerwunsch: ein komplett **neuer** Deep-Review-Durchlauf
über ALLE Komponenten (`core`, `ui-reference-pyside`, `ui-windows-dotnet`),
mit der Vorgabe, nach jedem Fund/Fix wieder komplett von vorne zu beginnen,
bis ein Durchlauf **weder Fehler noch Warnungen** zeigt (ausdrücklich auch
bereits bekannte Deprecation-Warnings, nicht nur Testfehler). review-prompt-
pack-Profile `10-python_DE_EN.md` (core + ui-reference-pyside) und
`06-csharp-dotnet_DE_EN.md` (ui-windows-dotnet) wurden als Prüfraster
herangezogen (siehe `docs/DEEP_REVIEW_USAGE.md`).

## 2. Aktivierte Profile / Werkzeuge

- `ruff check .` (vollständiger Regellauf, kein manuell eingeschränktes
  `select`) in `core/` und `ui-reference-pyside/`.
- Vollständige `pytest`-Suiten in beiden Python-Komponenten, zusätzlich
  mit `-rw` (zeigt alle aufgetretenen Warnings explizit) gegengeprüft.
- `.NET SDK 8.0.425` frisch installiert (`scripts/setup_dotnet_env.sh`);
  `dotnet build -p:EnableWindowsTargeting=true` + `dotnet test` für
  `ui-windows-dotnet/GenesisMediaManager.Client` (WPF) und
  `GenesisMediaManager.Client.Tests` (xUnit) — **zum ersten Mal in diesem
  Projekt tatsächlich kompiliert und getestet**, nicht nur gelesen.
- `dotnet list package --vulnerable` gegen die Testprojekt-Abhängigkeiten.
- Manuelle, checklisten-geleitete Zusatzprüfung (Python-Profil): grep-
  basierte Suche nach `shell=True`, `eval`/`exec`, `pickle`, unsicherem
  `yaml.load`, bare `except:`, `zipfile`/`tarfile`-Extraktion (Zip Slip),
  HTTP-Aufrufen ohne Timeout, Pfad-Traversal in Rename-/Download-Code.

## 3. Executive Summary

Dieser Durchlauf hat zwei **echte Laufzeitfehler** im Python-Referenz-
Client gefunden, die durch keinen der bisherigen Tests abgedeckt waren
(F-13-1, F-13-2) — beide sind jetzt behoben und mit Regressionstests
abgesichert. Zusätzlich wurde `core/` von 266 auf **0** ruff-Funde
reduziert (siehe Abschnitt 4) und `ui-reference-pyside/` erstmals
überhaupt einem Linter unterzogen (38 → 0 Funde). `ui-windows-dotnet/`
wurde zum ersten Mal in diesem Projekt tatsächlich gebaut und getestet
(vorher nur gelesen) — baut sauber mit 0 Warnings/0 Errors, 11/11 Tests
grün, keine bekannten Schwachstellen in den Abhängigkeiten. Am Ende dieser
Sitzung zeigt ein vollständiger Durchlauf über alle drei Komponenten
**weder Fehler noch Warnungen**.

## 4. Findings

### F-13-1 (KRITISCH, core-nah/UI) — `_extract_detail` existiert nicht:
NameError statt sauberer Fehlermeldung bei drei API-Client-Methoden

- **Ort:** `ui-reference-pyside/genesis_ui/api_client.py`,
  `get_cutter_waveform_bytes()`, `export_chapters_text()`,
  `get_voice_synthesis_audio()`.
- **Beleg:** `ruff` (`F821 Undefined name '_extract_detail'`) an allen drei
  Stellen; die tatsächlich existierende, vollständig funktionsfähige
  Helper-Funktion `_build_api_error(exc) -> GenesisAPIError` (mit
  korrekter Behandlung BEIDER Core-Fehlerformate inkl. `error_id`/
  `solution_hint`, §37) wird an den übrigen vier `HTTPStatusError`-
  Stellen in derselben Datei bereits korrekt verwendet — nur diese drei
  riefen stattdessen eine nie definierte Funktion auf.
- **Ursache/Ablauf:** Vermutlich ein unvollständiges Refactoring (von
  einer früheren, einfacheren `_extract_detail(exc) -> str`-Hilfsfunktion
  auf die heutige, vollständige `_build_api_error(exc) -> GenesisAPIError`)
  — drei Aufrufstellen wurden dabei übersehen.
- **Auswirkung:** Jeder HTTP-Fehlerstatus (4xx/5xx) von diesen drei
  Endpunkten (Cutter-Waveform laden, Kapitel-Export, Voice-Synthese-Audio
  laden) führte NICHT zu der erwarteten, lesbaren `GenesisAPIError` mit
  ggf. nachschlagbarer Fehler-ID, sondern zu einem unbehandelten
  `NameError` — ein klassischer stiller/verschleierter Fehlschlag
  (Verstoß gegen das Projektprinzip "keine stillen Fehlschläge", §37) UND
  ein direkter Widerspruch zur gesamten Fehlerdialog-Arbeit aus Sitzung
  11/12. Kein bestehender Test deckte dies ab, da alle bisherigen UI-Tests
  gegen Fake-/Stub-API-Objekte laufen, nicht gegen einen echten
  `GenesisAPIClient` mit simuliertem HTTP-Fehler.
- **Fix:** Alle drei Stellen rufen jetzt `raise _build_api_error(exc) from
  exc` auf (identisch zu den übrigen vier Stellen).
- **Regressionstest:** `tests/test_deep_review_sitzung13_fixes.py` — neue
  Tests mit echtem `GenesisAPIClient` + `httpx.MockTransport` (kein echter
  Netzwerkzugriff), die für alle drei Methoden sowohl das einfache
  `{"detail": ...}`-Format als auch das vollständige
  `{"error_id", "message", "solution_hint"}`-Format prüfen.
- **Beweisstatus:** BELEGT, Vertrauen HOCH (reproduzierbar, Fix verifiziert
  per neuem Test + vollem Testlauf).

### F-13-2 (MITTEL, Code-Qualität/Robustheit) — Doppelte `list_jobs`-
Methode in `GenesisAPIClient` (toter Code durch stille Überschreibung)

- **Ort:** `ui-reference-pyside/genesis_ui/api_client.py`, Zeile 97 (alt)
  und Zeile 559.
- **Beleg:** `ruff` (`F811 Redefinition of unused 'list_jobs'`).
- **Ursache/Ablauf:** Zwei Methoden desselben Namens in derselben Klasse —
  Python behält bei Klassenattributen immer nur die zuletzt definierte;
  die erste (`list_jobs(self) -> list[dict]`, ohne `limit`-Parameter) war
  dadurch bereits seit ihrer Einführung toter, nie erreichbarer Code.
- **Auswirkung:** Kein Laufzeitfehler (der einzige Aufrufer,
  `job_queue_view.py`, nutzt ohnehin `list_jobs(limit=100)` und hätte
  daher auch mit der toten ersten Definition weiterhin funktioniert, da
  Python stets die zweite Definition bindet) — aber verwirrender,
  irreführender Code, der bei zukünftiger Wartung leicht zu falschen
  Annahmen führen könnte.
- **Fix:** Tote erste Definition entfernt; die verbleibende Methode (mit
  `limit`-Parameter, Default 50) bleibt unverändert am angestammten Ort
  im §35/§36-Abschnitt.
- **Regressionstest:** `test_list_jobs_has_exactly_one_definition_with_limit_parameter`
  in derselben neuen Testdatei (prüft `limit`-Parameter-Weitergabe an die
  Core-API).
- **Beweisstatus:** BELEGT, Vertrauen HOCH.

### I-13-3 (NIEDRIG, Robustheit) — Zwei `except Exception: pass`-Stellen
ohne jede Protokollierung

- **Ort:** `ui-reference-pyside/genesis_ui/dialogs/error_dialog.py`
  (Fallback, falls die Anzeige des globalen Fehlerdialogs selbst
  fehlschlägt) und `genesis_ui/main_window.py`
  (`_apply_language_from_settings`, falls die Core-API beim Start nicht
  erreichbar ist).
- **Beleg:** `ruff` (`S110 try-except-pass`).
- **Einordnung:** Kein Fehlverhalten — die erste Stelle ist in ihrem
  primären Zweck bereits korrekt (die eigentliche Ursprungs-Exception
  steht VOR dem Try-Block bereits auf stderr), die zweite ist ein
  bewusster, dokumentierter Fallback auf die Default-Sprache. Dennoch ein
  Verstoß gegen das Projektprinzip "kein stiller Fehlschlag", da der
  SEKUNDÄRE Fehler (Dialoganzeige schlägt fehl bzw. Sprach-Ladevorgang
  schlägt fehl) komplett ohne jede Spur verschwand.
- **Fix:** Beide Stellen protokollieren jetzt den Sekundärfehler (stderr
  bzw. `logging.getLogger("genesis_ui.main_window").warning(...,
  exc_info=True)`), ohne das defensive Nicht-Abstürzen-Verhalten zu
  verändern. `# noqa: BLE001`-Begründungskommentare an beiden (weiterhin
  bewusst breiten) `except Exception`-Stellen ergänzt/erhalten.
- **Beweisstatus:** BELEGT (Ruff-Fund), Fix ist rein additiv (Logging),
  kein Verhaltensunterschied im Erfolgsfall.

### I-13-4 (NIEDRIG, Reproduzierbarkeit) — `core/`: 103 verbleibende
Ruff-Funde nach Auto-Fix, davon 96 reines FastAPI-Falsch-Positiv

- **Ort:** `core/pyproject.toml`.
- **Beleg:** `ruff check . --statistics` zeigte `B008` ("function-call-in-
  default-argument") 96×, ausschließlich an FastAPI-Endpunkt-Signaturen
  mit `= Depends(...)`/`= Query(...)`/`= Header(...)` — ein von ruff
  selbst dokumentiertes bekanntes Falsch-Positiv für FastAPIs offiziell
  empfohlenes Dependency-Injection-Muster.
- **Fix:** `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` in
  `core/pyproject.toml` um alle FastAPI-Parameter-Marker-Funktionen
  ergänzt (`Depends`, `Query`, `Body`, `Header`, `Path`, `Cookie`, `File`,
  `Form`, `Security`). Verbleibende 7 Funde (`C408`×3, `SIM117`×2,
  `PIE810`×1, `RUF046`×1) manuell/per `--unsafe-fixes` behoben (reine
  Stilverbesserungen ohne Verhaltensänderung, durch vollen Testlauf
  verifiziert).
- **Beweisstatus:** BELEGT.

### I-13-5 (INFO, Repo-Hygiene) — 7 Shebang-Dateien waren in Git selbst
nie als ausführbar getrackt (keine Sitzungsdrift, sondern von Anfang an
falsch)

- Bereits in der Session-Historie dieser Sitzung aufgearbeitet (siehe
  `PROGRESS.md`): `git ls-files -s` zeigte Modus `100644` für
  `scripts/generate_license_report.py`, `scripts/run_tests.sh`,
  `scripts/setup_dotnet_env.sh`, `scripts/setup_git_identity.sh`,
  `scripts/setup_ollama.sh`, `scripts/setup_python_env.sh`,
  `ui-reference-pyside/main.py` sowie `core/run_api.py` (neu, nie 755)
  trotz vorhandenem Shebang. Per `chmod +x` + Commit dauerhaft behoben.

## 5. Positiv bestätigte Schutzmaßnahmen (checklisten-geleitete
Zusatzprüfung, Abschnitt "Manuelle Zusatzprüfung")

- Kein einziges Vorkommen von `shell=True`, `eval(`, `exec(`, `pickle`,
  unsicherem `yaml.load` oder bare `except:` in `core/genesis_core` oder
  `ui-reference-pyside/genesis_ui`.
- Jeder HTTP-Client/-Aufruf im gesamten Projekt (Python UND .NET) setzt
  explizit einen Timeout bzw. nutzt eine zentrale Fabrik, die das
  erzwingt (`genesis_core/providers/base.py::make_http_client`,
  Docstring: *"garantiert, dass JEDER Provider einen Timeout ... setzt"*).
  Keine einzige "nackte" `httpx.Client()`/`.get()`/`.post()`-Stelle ohne
  Timeout gefunden.
- `genesis_core/rename/engine.py` verweigert aktiv jede Vorlage mit `/`
  oder `\` (Fehlermeldung "Verzeichniswechsel ... wird ... nicht
  unterstützt") — verhindert Pfad-Traversal über Umbenennungsvorlagen.
- `ui-windows-dotnet`: `GenesisApiClient` ist `sealed` und implementiert
  `IDisposable` korrekt (`_http.Dispose()`); alle API-Aufrufe sind
  `async`/`await` mit durchgereichtem `CancellationToken`; explizite
  `JsonSerializerOptions` mit Snake-Case-Mapping an JEDER (De-)
  Serialisierungsstelle (verhindert den dokumentierten stillen
  Feldnamen-Mismatch zwischen FastAPI-snake_case und C#-PascalCase).
- `dotnet list package --vulnerable`: keine bekannten Schwachstellen in
  den Test-Projekt-Abhängigkeiten.

## 6. Nach Fixes erneut vollständig getestet (finaler sauberer
Durchlauf dieser Sitzung)

```
core:                ruff check .          → 0 Funde
core:                pytest -q             → 520 passed, 7 skipped, 0 Warnings
ui-reference-pyside:  ruff check .          → 0 Funde
ui-reference-pyside:  pytest tests/ -q      → 32 passed (27 + 5 neue), 0 Warnings
ui-windows-dotnet:    dotnet build (Client) → Build succeeded, 0 Warning(s), 0 Error(s)
ui-windows-dotnet:    dotnet test (Tests)   → Passed: 11, Failed: 0, Skipped: 0
```

Alle drei Komponenten gleichzeitig fehler- UND warnungsfrei — Zielzustand
dieser Sitzung erreicht.

## 7. Offene Fragen / verbleibendes Backlog

- `ui-windows-dotnet` hat noch keine automatisierten Linter-/Analyzer-
  Regeln (`.editorconfig`/Roslyn-Analyzer) konfiguriert — `dotnet build`
  zeigt 0 Warnings nur, weil keine zusätzlichen Analyzer aktiv sind. Für
  eine noch tiefere Prüfung käme z.B. `Microsoft.CodeAnalysis.NetAnalyzers`
  mit verschärftem `AnalysisLevel` in Frage — als spätere Härtungsoption
  vorgemerkt, kein akuter Fehlerbefund.
- `HttpClient` in `GenesisApiClient.cs` setzt keinen expliziten `Timeout`
  (nutzt den .NET-Default von 100s) — unkritisch für einen reinen
  Localhost-Client, aber zur Konsistenz mit dem Python-Pendant (30s)
  als mögliche spätere Kleinigkeit vermerkt, kein Fehlerbefund.
- Gap-Analyse/Brainstorming (nächster Schritt laut explizitem
  Nutzerauftrag) steht nun an, da dieser Durchlauf den geforderten
  komplett fehler- und warnungsfreien Zustand erreicht hat.

## 8. Sitzung 14 — Gap-Analyse-Backlog (docs/GAP_ANALYSIS.md) abgearbeitet

Kein weiterer Deep-Review-Durchlauf im engeren Sinn (kein neues
`ruff`/Vollsuite-Fehlerbild gesucht), sondern planmäßige, vom Nutzer
sequenziell freigegebene ("mach es der reihe nach bis du fertig bist")
Schließung der in `docs/GAP_ANALYSIS.md` Abschnitt 2 dokumentierten
Lücken. Vollständige Belege/Tests/Commits siehe `PROGRESS.md` ("Sitzung
14" / "Sitzung 14 (Fortsetzung)"): Gap-Gruppe 1 (D/E/F: Cover-Anzeige,
Datei/Ordner öffnen + Pfad kopieren, Loudness/KI im Detail-Panel),
Gap-Gruppe 2 (A/I: Settings-Schreibzugriff per `PATCH /settings` +
GUI-Seite, Metadaten-Provider-Verwaltung; dabei zusätzlich entdeckte und
behobene Lücke: `trigger_scan()` war zuvor über die gesamte GUI nicht
erreichbar), Gap-Gruppe 3 (B: Bibliotheks-Drill-down für Interpreten/
Alben/Titel/Genres/Personen/Quellen, neues Backend-Modul
`genesis_core/library.py`). Jede Gruppe wurde vor dem Commit sowohl per
vollständiger automatisierter Testsuite (Backend + UI) ALS AUCH end-to-end
gegen einen echten, befüllten `core/run_api.py`-Prozess verifiziert
(keine reine Mock-Verifikation). `docs/GAP_ANALYSIS.md` wurde je
geschlossener Lücke mit einem "✅ GESCHLOSSEN"-Vermerk direkt unter der
jeweiligen Befund-Überschrift aktualisiert; der ursprüngliche Befundtext
bleibt als historisches Protokoll erhalten.

## 2026-10-07 - UI v2 / Version 0.2.0

- Deep-Review-basierte UI-Modernisierung des WPF-Clients umgesetzt.
- Keine Core-/API-Logik ersetzt; Aenderung bleibt auf Presentation Layer und Packaging-Metadaten begrenzt.
- Geprueft: XAML parsebar, C# Strukturcheck PASS, Python compileall PASS, i18n JSON PASS, gezielte Regressionstests 19 PASS / 1 SKIP.
- Echter Windows-WPF-Build und visuelle Endabnahme bleiben Release-Gate-Aufgaben.
