# Architecture Decision Records (ADR) — GENESIS Media Manager

Kurzformat: Kontext → Entscheidung → Konsequenzen. Neue ADRs immer anhängen,
alte niemals rückwirkend "schönschreiben" (Nachvollziehbarkeit, Prinzip #16).

---

## ADR-0001: Hybrid-Architektur Python-Core + zwei UI-Clients

**Kontext:** Nutzer wünschte explizit "eine Kombination aus .NET/C#
(WPF/WinUI3) UND Python+PySide6". Das Entwicklungs-Sandbox-System ist Linux
ohne Windows-Desktop-Runtime; WPF/WinUI3 können dort nicht gebaut oder
getestet werden (sie benötigen Windows-spezifische Presentation-Frameworks).
Der Auftrag selbst schlägt an mehreren Stellen (§29 Voice API, §46 lokale
KI-Anbindung) bereits ein lokales HTTP/REST-Muster vor.

**Entscheidung:**
- Die gesamte Fachlogik (Scanner, DB, Metadaten-Engine, Fingerprint,
  Loudness, Duplicate-, Quality-, Rename-, Backup-, Rollback-, Job-Queue-,
  Plugin-, AI-, Voice-, Download-Engine) wird **einmal** in Python
  implementiert als `genesis-media-manager/core` (Paket `genesis_core`),
  exponiert über eine lokale REST-API (FastAPI, nur `127.0.0.1`, kein
  Cloud-Zwang) sowie eine importierbare Python-Bibliothek für Tests.
- Zwei UI-Clients konsumieren dieselbe API:
  1. `ui-reference-pyside` (PySide6/Qt) — läuft & wird in dieser
     Linux-Sandbox tatsächlich gebaut, gestartet und getestet. Dient während
     der gesamten Entwicklung als Referenz-/Test-Oberfläche.
  2. `ui-windows-dotnet` (C#/.NET, WPF für Windows 10/11) — das native
     Windows-Zielprodukt für den Endnutzer. Wird als vollständiger
     Quellcode/Projektstruktur geliefert, muss aber unter Windows mit dem
     .NET SDK gebaut werden (hier nicht kompilierbar/testbar).
- Kommunikation ausschließlich über die dokumentierte REST-API (`docs/API.md`,
  OpenAPI-Schema wird von FastAPI automatisch generiert) — keine
  Sprachvermischung im selben Prozess.

**Konsequenzen:**
- (+) Keine doppelte Implementierung von Fachlogik in zwei Sprachen.
- (+) Fachlogik ist vollständig automatisiert testbar in der Sandbox (pytest).
- (+) Erfüllt Prinzip #13 (Modularität) und #8 (austauschbare Provider) sehr
  natürlich, da Provider/Engines ohnehin hinter der API liegen.
- (+) Der PySide6-Client kann später sogar als voll unterstützter
  Linux/macOS-Client weiterleben (Bonus, nicht Kernziel).
- (–) Zwei UI-Codebasen zu pflegen (Aufwand), aber UI enthält bewusst KEINE
  Fachlogik (nur Darstellung + API-Aufrufe) → Pflegeaufwand bleibt klein.
- (–) .NET-Client kann in dieser Umgebung nicht kompiliert/getestet werden;
  Qualitätssicherung dafür verlagert sich auf Windows-Sitzungen bzw. auf den
  Nutzer selbst oder eine künftige Windows-CI.

**Status:** Angenommen, 2026-09-30.

---

## ADR-0002: Lokale Datenbank = SQLite + SQLAlchemy 2.x + Alembic

**Kontext:** Nutzer bevorzugt SQLite (Antwort auf Rückfrage). Offline-first,
keine Serverinstallation nötig, dateibasiert, gut sicherbar/kopierbar für
Backups (Prinzip #20), ausreichend performant für "sehr große Bibliotheken"
im Zehn- bis Hunderttausender-Bereich an Mediendateien bei sauberem
Indexdesign (WAL-Modus, Indizes auf Pfad/Hash/Fingerprint/Fremdschlüssel).

**Entscheidung:** SQLite als Standard-Datenbank-Engine, Zugriff ausschließlich
über SQLAlchemy-ORM-Schicht mit `DatabaseProvider`-Interface, damit ein
Wechsel auf PostgreSQL (für Nutzer mit sehr großen Bibliotheken oder
Mehrbenutzerbetrieb) später als austauschbarer Plugin/Provider möglich bleibt,
ohne die Kernarchitektur umzuschreiben (Prinzip #13). Migrationen über
Alembic, damit Schema-Änderungen nie destruktiv sind (Prinzip #7/#20).

**Konsequenzen:** DB-Layer ist von Anfang an hinter einem Interface
(`IDatabaseProvider`) versteckt — Grundlage für §34 Plugin-System
"Database Provider".

**Status:** Angenommen, 2026-09-30.

---

## ADR-0003: Lokale KI = Ollama (Standard), OpenAI-kompatible API austauschbar

**Kontext:** Nutzer wählte "Ollama im Sandbox installieren & testen". Ollama
wurde erfolgreich installiert (Version 0.35.0) und das kleine Modell
`qwen2.5:0.5b` (~397 MB, Apache-2.0-Lizenz von Alibaba/Qwen-Team, siehe
`licenses/THIRD-PARTY-LICENSES.md` Entwurf) erfolgreich gezogen und getestet
(`/api/generate` lieferte in ~1.7s eine sinnvolle Antwort bei <1GB RAM-Bedarf).

**Entscheidung:** `AIProvider`-Interface mit Ollama als Referenzimplementierung
(`OllamaProvider`, HTTP zu `http://127.0.0.1:11434`, Modellname
konfigurierbar). Zusätzlich ein `NullAIProvider` (Mock/Stub) für Tests ohne
laufenden Ollama-Dienst und Umgebungen ganz ohne KI. Jede
OpenAI-kompatible lokale API (LM Studio etc.) ist über denselben
Interface-Vertrag später als weiterer Provider anbindbar (§46).

**Konsequenzen:** Tests laufen standardmäßig gegen `NullAIProvider` (schnell,
deterministisch, keine Abhängigkeit von installiertem Ollama). Ein optionaler
Integrationstest prüft *wenn* Ollama erreichbar ist zusätzlich die echte
Anbindung, wird aber übersprungen (nicht fehlgeschlagen), wenn nicht
erreichbar — wichtig, weil das große Sprachmodell/-Verzeichnis
(`~/.ollama`) laut Ressourcen-Disziplin NICHT im Workspace-Snapshot
persistiert wird und nach einem Sandbox-Neustart erneut gezogen werden müsste
(`scripts/setup_ollama.sh` automatisiert das).

**Status:** Angenommen, 2026-09-30.

---

## ADR-0004: Test-Mediendateien = winzige synthetische FFmpeg-Erzeugnisse

**Kontext:** Prinzip #50/#51: niemals auf echten persönlichen Mediendateien
testen; SAFE TEST MODE. Zusätzlich Ressourcen-Disziplin: Workspace darf nicht
volllaufen.

**Entscheidung:** `core/testdata_generator/` erzeugt bei Bedarf (nicht
dauerhaft eingecheckt, sondern reproduzierbar per Skript) eine synthetische
Testbibliothek: Sinuston-/Stille-Audiodateien (1–3 Sekunden, verschiedene
Formate: MP3/FLAC/WAV/OGG/M4A) mit klar erfundenen, als solche
kenntlich gemachten Test-Tags ("Test Artist", "Test Album" …), sowie ein
winziges Testvideo (Farbbalken, 2 Sekunden, niedrige Auflösung) für die
Video-Pipeline. Alle erzeugten Dateien landen unter einem `.gitignore`d bzw.
nicht-persistiertem Temp-Verzeichnis während der Testläufe (`pytest`-Fixture
mit `tempfile.TemporaryDirectory`), NICHT dauerhaft im Workspace, außer einem
kleinen, bewusst eingecheckten Minimal-Set (< 200 KB gesamt) für schnelle
manuelle Demos.

**Status:** Angenommen, 2026-09-30.

---

## ADR-0005: Lizenzbericht bleibt bis Release-Reife als ENTWURF markiert

**Kontext:** Nutzer: "hier muss am ende alles sauber eingetragen werden aber
erst wenn es fertig ist" — bezogen auf das Lizenz-/Review-System.

**Entscheidung:** `licenses/THIRD-PARTY-LICENSES.md` und `NOTICE.md` werden
von Anfang an geführt und bei jeder neuen Abhängigkeit aktualisiert, tragen
aber bis zum offiziellen Release-Gate (Phase 10) einen sichtbaren
Kopf-Hinweis `STATUS: ENTWURF / IN ARBEIT — NICHT RELEASE-FINAL`. Der
`reference/review-prompt-pack` (Deep-Review-Prompts, siehe
`docs/DEEP_REVIEW_USAGE.md`) wird als wiederkehrendes Werkzeug für
Code-Qualitäts- und Lizenz-Tiefenprüfungen genutzt; sein `RELEASE_CHECKLIST.md`
dient als Vorlage für unser eigenes `docs/RELEASE_CHECKLIST_GENESIS.md`,
das erst am Ende von Phase 9/10 vollständig abgehakt wird.

**Status:** Angenommen, 2026-09-30.

---

## ADR-0006: Lokale REST-API erfordert ein Shared-Secret-Token (`X-Genesis-Token`)

**Kontext:** Deep-Review-Sitzung 2 (Anwendung des AI Deep Review Prompt Packs,
Profile Python/API REST). Die Core-API bindet ausschließlich an `127.0.0.1`
(ADR-0001), aber das allein schützt NICHT vor sogenannten
"Drive-by-Localhost"-/JSON-CSRF-Angriffen: jede im Browser des Nutzers
gleichzeitig geöffnete Webseite kann per JavaScript eine Anfrage an
`http://127.0.0.1:<port>` senden. Der Browser verhindert zwar per CORS, dass
die fremde Seite die Antwort lesen kann — nicht aber, dass die Anfrage beim
Server ankommt und dort eine Seitenwirkung auslöst ("blinde" CSRF reicht für
POST-Endpunkte ohne Rückgabewert-Bedarf völlig aus). Da `/scan` bereits
Festplatten-I/O, Hashing und `ffprobe`-Aufrufe auslöst und spätere Phasen
Umbenennen/Löschen-Endpunkte hinzufügen werden, würde ein unauthentifizierter
Endpunkt das zentrale Sicherheitsprinzip #44 ("Änderung = Benutzerbestätigung")
untergraben — eine fremde Webseite hat nie eine Bestätigung des Nutzers
eingeholt.

**Entscheidung:** Der Core Service erzeugt beim ersten Start ein
zufälliges Token (`secrets.token_urlsafe(32)`) und speichert es in
`<data_dir>/api_token.txt` mit restriktiven Dateirechten (POSIX: `0600`,
unter Windows greift zusätzlich der ACL-Schutz von `%APPDATA%`). Jeder
Endpunkt außer `/health` (reiner Liveness-Check ohne Seitenwirkung und ohne
sensible Daten) verlangt den Header `X-Genesis-Token` mit exakt diesem Wert
(konstante Vergleichszeit via `hmac.compare_digest`, siehe
`genesis_core/api/security.py`). Beide UI-Clients (PySide6-Referenz,
.NET-WPF-Ziel) lesen die Token-Datei eigenständig ein (bewusst OHNE
Abhängigkeit auf `genesis_core`-Interna, siehe ADR-0001) und senden sie bei
jeder Anfrage mit.

**Konsequenzen:** Ein lokaler, nicht privilegierter Angreifer mit
Dateisystemzugriff auf das Benutzerprofil könnte das Token trotzdem lesen —
das ist eine bewusst akzeptierte Grenze (ein Angreifer mit lokalem
Dateisystemzugriff auf das Benutzerkonto kann ohnehin direkt auf die
Mediendateien/DB zugreifen; das Token schützt spezifisch vor dem
Browser-/Remote-Angriffsvektor, nicht vor einem bereits kompromittierten
Benutzerkonto). Für Phase 8 (Download/Import, mögliche Multi-User- oder
Netzwerk-Szenarien) muss dieses Modell erneut bewertet werden. Alle
bestehenden API-Tests wurden entsprechend angepasst; ein neuer Regressionstest
(`test_protected_endpoints_reject_missing_or_wrong_token`) verifiziert
401-Antworten ohne/mit falschem Token.

**Status:** Angenommen, 2026-09-30.

## ADR-0007: Job-Protokollierung erfolgt IMMER in der API-Schicht nach Commit, nie in Engines

**Kontext:** `metadata/engine.py`, `rename/engine.py` und `artwork/engine.py`
führen jeweils eine vollständige, in sich geschlossene DB-Transaktion pro
Aufruf aus (Prinzip #6: eine Änderung = eine Transaktion, klar rückrollbar).
`JobManager.record_history()` selbst schreibt ebenfalls in die Datenbank
(SQLite). Würde eine Engine `record_history()` MITTEN in ihrer eigenen
Transaktion aufrufen (z. B. vor dem eigenen `commit()`), entstünde eine
verschachtelte Schreiboperation auf derselben SQLite-Datei — bei
gleichzeitigen Zugriffen (z. B. Job-Queue + UI-Polling) ein unnötig hohes
Risiko für `database is locked`-Fehler, und im Fehlerfall wäre unklar, ob
der Rollback der Engine-Transaktion auch den Log-Eintrag zurückrollt oder
nicht (inkonsistenter Zustand: Log sagt "passiert", DB sagt "nie passiert").

**Entscheidung:** Engines (`metadata`, `rename`, `artwork`, künftig auch
`loudness`, `duplicates`, `backup` usw.) rufen `JobManager.record_history()`
NIEMALS selbst auf. Stattdessen: eine Engine-Funktion beendet ihre eigene
Transaktion vollständig (Commit oder Exception), und die aufrufende
API-Schicht (`core/genesis_core/api/app.py`) legt DANACH — in einer eigenen,
zweiten Transaktion — den Job- und Protokolleintrag an. Das bedeutet: bei
einem Absturz zwischen Engine-Commit und `record_history()`-Aufruf fehlt im
schlimmsten Fall NUR der Log-Eintrag (die eigentliche Datenänderung ist
bereits sauber committed und korrekt), nie umgekehrt ein Log-Eintrag ohne
zugehörige tatsächliche Änderung.

**Konsequenzen:** Jeder neue Engine-Typ muss sich an dieses Muster halten;
Code-Review-Checkliste ergänzt (siehe `docs/REVIEW_LOG.md`). Aufrufer
(API-Endpunkte) sind dadurch etwas länger, weil sie `before`/`after`-Zustand
selbst einsammeln müssen — das ist ein bewusst akzeptierter Trade-off für
Transaktionssicherheit.

**Status:** Angenommen, 2026-09-30 (Sitzung 3, Phase 2 REST-API-Verdrahtung
für `rename/` und `artwork/`; das Muster existierte implizit bereits für
`metadata/engine.py`, wurde hier erstmals explizit als ADR festgehalten).

## ADR-0008: .NET-Client MUSS `JsonSerializerOptions` mit `SnakeCaseLower` explizit verwenden

**Kontext (kritischer Deep-Review-Fund, Sitzung 3):** Die Core-API liefert
und erwartet ausschliesslich snake_case-JSON (FastAPI-Standard, z.B.
`job_id`, `absolute_path`, `is_user_confirmed`). Der .NET-Client
(`GenesisApiClient.cs`) verwendet aus C#-Sprachkonvention PascalCase-Record-
Properties (`JobId`, `AbsolutePath`, `IsUserConfirmed`). Alle bisherigen
Aufrufe (`GetFromJsonAsync`, `PostAsJsonAsync`, `ReadFromJsonAsync`) wurden
OHNE eigene `JsonSerializerOptions` aufgerufen. Per Default matcht
`System.Text.Json` Property-Namen weder case-insensitive noch per
Namenskonvention - `"job_id"` wird NIE auf `JobId` gemappt. Entscheidend:
Das wirft dabei **keinen Fehler**, sondern laesst die betroffene Property
einfach auf ihrem Default-Wert (`null`/`0`/`false`) stehen. Verifiziert mit
einem isolierten Probe-Programm (`JsonSerializer.Deserialize` mit und ohne
`PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower`).

**Tragweite:** Das betraf nicht nur die in dieser Sitzung neu hinzugefuegten
Phase-2-Methoden, sondern JEDE bisherige Methode des .NET-Clients
(`GetHealthAsync`, `GetDashboardSummaryAsync`, `ListMediaAsync`,
`GetMediaDetailAsync`, `TriggerScanAsync`) seit deren Erstellung in
Sitzung 1 - ein klassischer stiller Fehler (Verstoss gegen §37). Da die
.NET-UI bisher nur das Dashboard tatsaechlich rendert (siehe
`MainWindow.xaml.cs`) und dort nur wenige Felder anzeigt, ist der sichtbare
Schaden gering geblieben, haette sich aber bei jeder UI-Erweiterung
verschlimmert.

**Entscheidung:** `GenesisApiClient` haelt eine einzige
`private static readonly JsonSerializerOptions JsonOptions` mit
`PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower` und
`PropertyNameCaseInsensitive = true` vor. **Jeder** Serialisierungs-/
Deserialisierungsaufruf in dieser Klasse muss sie explizit uebergeben;
die parameterlosen Default-Ueberladungen duerfen dort nie mehr verwendet
werden (Code-Review-Regel ergaenzt). Zusaetzlich wurde eine
`GenesisApiException` eingefuehrt, die FastAPIs `{"detail": "..."}`-Feld
aus Fehlerantworten extrahiert - Analogie zu `_extract_detail()` im
Python-Client.

**Verifikation:** Ein temporaeres, von der WPF-Abhaengigkeit entkoppeltes
Konsolen-Testprogramm (referenziert `GenesisApiClient.cs` direkt per
`<Compile Include>`, `net8.0` statt `net8.0-windows`) wurde gegen einen
echten laufenden Core-API-Prozess ausgefuehrt und hat den kompletten
Phase-1+2-Methodenumfang end-to-end verifiziert (Health, Dashboard,
Scan, MediaList, MediaDetail, Rename-Preview/Apply, Metadaten-Vorschlag
uebernehmen, Artwork lesen/online-suchen/einbetten inkl. aller
Fehlerfaelle). Alle Felder wurden korrekt befuellt (kein `null`/`0` mehr
an Stellen, wo die API echte Werte liefert).

**Zusatzfund (Werkzeug fuer kuenftige Sitzungen):** Das `.NET`-WPF-Projekt
(`net8.0-windows`, `UseWPF=true`) kann in dieser Linux-Sandbox NICHT mit
`dotnet build` kompiliert werden (`NETSDK1100`), *ausser* man setzt das
MSBuild-Property `-p:EnableWindowsTargeting=true`
(`dotnet build -p:EnableWindowsTargeting=true`). Damit lassen sich
Kompilierfehler/Typfehler bereits in der Sandbox finden, OHNE auf eine
Windows-Maschine warten zu muessen (Ausfuehren/Starten der WPF-App selbst
bleibt weiterhin nur unter Windows moeglich). Das .NET SDK wurde dafuer via
`dotnet-install.sh` nach `~/.dotnet` installiert (nicht Teil des
Workspace-Snapshots - muss ggf. in kuenftigen Sitzungen erneut installiert
werden, siehe PROGRESS.md "Ressourcen-Disziplin").

**Status:** Angenommen, 2026-09-30 (Sitzung 3).

## ADR-0009: i18n-Mechanismus — geteilte JSON-Kataloge, pro Stack ein eigener (dupliziertes) Loader

**Kontext:** §53 verlangt, dass alle UI-Texte aus Sprachressourcen kommen
(nie hartcodiert), mit Pflichtunterstützung für DE/EN/JA/RU, umschaltbar
zur Laufzeit über die GUI (kein manuelles Config-Datei-Editieren, §52-Geist
auf Sprache übertragen). Das Projekt hat laut ADR-0001 **zwei unabhängige
UI-Prozesse** (PySide6-Referenz, WPF-Ziel) plus den Core-Service selbst,
die potenziell alle UI-/nutzerseitigen Texte anzeigen müssen (Core: künftige
strukturierte Fehlercodes/-schlüssel in API-Antworten, siehe Backlog in
`docs/REVIEW_LOG.md`).

**Problem:** Ein einzelner Übersetzungsmechanismus kann nicht einfach
"importiert" werden, weil ADR-0001 explizit verbietet, dass die UI-Schicht
Python-Code aus `genesis_core` importiert (reiner REST-API-Präsentations-
Client, siehe Kommentar in `api_client.py` zu `TOKEN_FILENAME`) - und die
.NET-UI kann ohnehin kein Python importieren.

**Entscheidung:**
- Die eigentlichen Übersetzungstexte liegen als reine JSON-Dateien im
  Repository-Wurzelverzeichnis unter `i18n/de.json`, `i18n/en.json`,
  `i18n/ja.json`, `i18n/ru.json` ab. `de.json` ist die Quelle der Wahrheit
  (muss jeden Schlüssel enthalten); die anderen drei müssen exakt dieselbe
  Schlüsselmenge haben (durch Test erzwungen, siehe
  `core/tests/test_i18n.py::test_all_catalogs_have_identical_key_sets`).
- Es gibt bewusst **drei unabhängige, kleine Loader-Implementierungen**
  (dupliziertes Verhalten, geteiltes Datenformat statt geteilter Code):
  1. `core/genesis_core/i18n/__init__.py` - für den Core-Service selbst
     (künftige Error-Keys in API-Antworten).
  2. `ui-reference-pyside/genesis_ui/i18n.py` - für die PySide6-UI, OHNE
     Import von `genesis_core` (Architekturregel ADR-0001 bleibt gewahrt).
  3. `ui-windows-dotnet/GenesisMediaManager.Client/I18n/Translator.cs` -
     für die WPF-UI (kann ohnehin kein Python importieren).
  Jede Implementierung ist absichtlich klein (~100-130 Zeilen) und
  funktional identisch: Katalog laden, flach machen (`"a.b.c"`-Schlüssel
  aus verschachteltem JSON), `tr(key, **kwargs)` mit Platzhalter-Ersetzung
  und dreistufigem Fallback (aktuelle Sprache -> Englisch -> roher
  Schlüssel - NIE eine Exception oder eine leere UI-Stelle).
- Bewusst KEIN gettext (`.po`/`.mo`-Kompilierschritt) und KEIN Qt Linguist
  (`.ts`/`.qm`-Build) verwendet, obwohl beides für Qt-Apps "idiomatischer"
  wäre: beide würden eine zusätzliche Build-Toolchain UND unterschiedliche
  Werkzeuge für die Python- und die .NET-Seite erfordern. Reines JSON ist
  in beiden Stacks ohne zusätzliche Abhängigkeit lesbar
  (`json`-Stdlib bzw. `System.Text.Json`) und zur Laufzeit ohne
  Neukompilierung austauschbar - die für dieses Projekt wichtigere
  Eigenschaft (Konsistenz/Einfachheit über zwei Stacks) wiegt schwerer als
  Tooling-Idiomatik innerhalb eines einzelnen Stacks.

**Konsequenzen:**
- Übersetzer/innen bearbeiten ausschließlich die vier JSON-Dateien, egal
  welcher UI-Client den Text später zeigt.
- Jede neue UI-Zeichenkette erfordert einen Schlüssel in ALLEN VIER
  Katalogen (durchgesetzt durch `test_all_catalogs_have_identical_key_sets`)
  - verhindert, dass eine Sprache schleichend hinter den anderen
    zurückbleibt.
- Drei-Implementierungen-ein-Format bedeutet etwas Code-Duplikation
  (identische ~100-Zeilen-Logik dreimal), die bewusst in Kauf genommen
  wird, um die in ADR-0001 festgelegte Prozess-/Importgrenze nicht zu
  verletzen.
- Laufzeit-Sprachumschaltung ist vorbereitet (`Translator.set_language()`/
  `configure_default_language()`), aber eine tatsächliche
  Einstellungs-UI zum Umschalten fehlt noch (Phase 9 "System ->
  Einstellungen" ist weiterhin ein Platzhalter) - aktuell wird die Sprache
  beim Start aus `Settings.general.language` gelesen (neuer minimaler
  `GET /settings`-Endpunkt).

**Status:** Angenommen, 2026-10-01 (Sitzung 4).

## ADR-0010: Loudness-Engine — FFmpegs `loudnorm`-Filter statt `pyloudnorm`

**Kontext:** §19 verlangt eine Loudness-Engine mit LUFS- UND True-Peak-Messung
(ITU-R BS.1770, inkl. Annex 2 für True Peak), konfigurierbarem Zielwert, und
dem Prinzip "Original nie ungefragt überschreiben" (§6, Prinzip #5). Die
PROGRESS.md-Notiz aus Sitzung 4 hatte als offene technische Vorfrage
markiert, ob `pyloudnorm` dafür ausreicht.

**Untersuchung:** `pyloudnorm` 0.2.0 (aktuellste PyPI-Version, MIT-Lizenz)
wurde direkt im Quellcode geprüft (`pyloudnorm/meter.py` aus dem
PyPI-Wheel): Es implementiert ausschließlich `integrated_loudness()` und
`loudness_range()` (ITU-R BS.1770-4 bzw. EBU Tech 3342) — **keine
True-Peak-Messung nach Annex 2** (4×-Oversampling). Eine eigene
Nachimplementierung (z.B. via `scipy.signal.resample_poly`) wäre machbar,
bedeutet aber eigene DSP-Mathematik, eigene Tests gegen die Referenzwerte
des Standards, und eine zusätzliche `scipy`-Abhängigkeit nur für diesen einen
Zweck.

**Entscheidung:** Stattdessen wird FFmpegs eingebauter `loudnorm`-Audiofilter
verwendet (Teil von FFmpeg, bereits seit Phase 1 Projektabhängigkeit für
`ffprobe`-Technikanalyse, siehe `licenses/THIRD-PARTY-LICENSES.md`):
- **Messung (Pass 1):** `ffmpeg -i <datei> -af
  loudnorm=I=...:TP=...:LRA=...:print_format=json -f null -` liefert
  `input_i` (Integrated LUFS), `input_tp` (True Peak, dBTP, vollständig
  Annex-2-konform mit internem Oversampling), `input_lra` (Loudness Range)
  als sauber parsbares JSON — unabhängig von den übergebenen Zielwerten
  (diese sind nur fürs Pflichtargument des Filters nötig, siehe
  `genesis_core/loudness/ffmpeg_loudnorm.py::_MEASURE_PASS_DEFAULTS`).
- **Normalisierung (Pass 2):** derselbe Filter, diesmal mit den in Pass 1
  gemessenen Werten gefüttert (`measured_I=...` etc.) und `linear=true`
  (reine, dynamikerhaltende Pegelverschiebung; nur wenn der True-Peak-Zielwert
  sonst verletzt würde, weicht ffmpeg intern auf eine leichte dynamische
  Begrenzung aus — dies wird VOR der Ausführung in der Vorschau als
  `will_likely_alter_dynamics`-Warnung angezeigt, Prinzip #16).
- Verworfene Alternative: `libebur128` (C-Bibliothek, sehr verbreitet,
  implementiert ebenfalls vollständig True Peak + LRA) wurde geprüft, aber
  verworfen, weil es eine zusätzliche native Abhängigkeit mit eigenem
  Build-/Packaging-Aufwand für die finale Windows-Distribution bedeutet
  hätte (keine verlässlich gepflegte Python-Bindung mit Windows-Wheels
  gefunden) — FFmpeg ist ohnehin schon vorhanden und bereits für Windows
  vertriebsfertig eingeplant.

**Sicherheitsmechanik (genesis_core/loudness/engine.py):**
1. `measure_loudness()` ist rein lesend.
2. `plan_normalization()` ist reine Berechnung (kein ffmpeg-Aufruf, keine
   Datei wird angelegt) — zeigt Zielgewinn, geplanten Ausgabepfad,
   Lossy-Reencode-Hinweis und Dynamik-Warnung.
3. `apply_normalization()` erzeugt **immer eine neue Datei**
   (`<name>.normalized.<ext>` im selben Ordner) und fasst das Original
   NIEMALS an — anders als beim Umbenennen gibt es hier bewusst KEINEN
   "in-place mit Bestätigung"-Modus, weil eine Pegeländerung an komprimiertem
   Audio ohnehin eine Neukodierung (Generationsverlust bei verlustbehafteten
   Formaten) erfordert; das Original unverändert zu lassen ist daher nicht
   nur die sicherste, sondern auch die einzige verlustfreie Option für die
   Originaldatei. Rollback ist dadurch trivial: die neue Datei löschen.
4. Scope-Einschränkung (analog zur Rename-Engine, ADR siehe dort): nur reine
   Audio-Medienarten (Musik/Hörbuch/Podcast/KI-Musik) — Video-Normalisierung
   (Film/Serie) ist Backlog für eine spätere, eigens getestete Erweiterung.

**Konsequenzen:**
- Keine neue Python-Abhängigkeit (kein `pyloudnorm`, kein `scipy`) —
  `pyloudnorm` wird im Projekt nicht verwendet.
- Volle ITU-R-BS.1770-Konformität inkl. True Peak, da FFmpegs `loudnorm` eine
  seit Jahren production-erprobte Referenzimplementierung ist.
- Jede Normalisierung bedeutet zwangsläufig eine Neukodierung; bei
  verlustbehafteten Quellformaten (MP3/OGG/AAC/Opus) ein dokumentierter,
  dem Nutzer in der Vorschau offengelegter Generationsverlust (Prinzip #16).
- DB-Schema (`Loudness`-Tabelle) um `loudness_range_lu`,
  `target_true_peak_dbtp_used` und `normalized_output_path` ergänzt
  (migrationsfrei, Schema wird weiterhin per `create_all()` erzeugt).

**Status:** Angenommen, 2026-10-01 (Sitzung 5/Phase 3).

## ADR-0011: Audio-Cutter — immer Filter-basiertes Re-Encode statt Demuxer-Stream-Copy; gemeinsames `audio_formats.py`-Modul

**Kontext:** §18 verlangt einen grafischen Audio-Cutter (Wiedergabe, Start/Ende
setzen, Zoom, Waveform, exakte Zeitposition, Vorschau, Fade In/Out, Auswahl
speichern) mit Export mindestens als MP3/WAV/FLAC, und der Vorgabe "bei
verlustfreien bzw. geeigneten Formaten möglichst ohne unnötige Neukodierung".
Gleichzeitig verlangt dieselbe Sektion eine "exakte Zeitposition" — beide
Anforderungen wurden vor der Implementierung gegeneinander in der Sandbox
getestet (`ffmpeg` 7.1.5), da sie sich potenziell widersprechen können.

**Untersuchung (Sandbox-Messungen, 10s-Sinus-Testdatei, 44.1kHz Stereo):**
- `ffmpeg -ss 2 -i src.wav -t 3 -c copy out.wav` (reiner Stream-Copy-Schnitt
  bei PCM/WAV): Ergebnis-Dauer 3.065s bzw. 2.972s (je nach `-ss`-Platzierung
  vor/nach `-i`) statt der angeforderten exakten 3.000s — eine Abweichung von
  2-3%, die der geforderten "exakten Zeitposition" widerspricht.
- `ffmpeg -ss 2 -i src.flac -t 3 -c copy out.flac`: schneidet in diesem
  ffmpeg-Build **überhaupt nicht** — die Ausgabedatei behält die volle
  Original-Dauer (10s statt 3s). Ein stiller Korrektheitsfehler, der
  unbemerkt eine falsche Datei erzeugen würde, wenn man sich auf Stream-Copy
  verlassen hätte.
- `ffmpeg -i src.wav -af "atrim=start=2:end=5,asetpts=PTS-STARTPTS[,afade=...]" -c:a pcm_s16le/flac out.*`
  (Filter-basiertes Re-Encode): liefert in allen getesteten Fällen (WAV, FLAC,
  mit und ohne Fades) eine exakte, auf die Mikrosekunde genaue Dauer
  (3.000000s). MP3-Export zeigt eine geringfügige Abweichung (~49ms), die
  jedoch dem bekannten LAME-Encoder-Padding/Priming-Verhalten entspricht und
  unabhängig vom hier gewählten Ansatz bei jedem MP3-Encoder auftritt.

**Entscheidung:**
1. Der Cutter schneidet **immer** über die Audiofilter-Kette
   `atrim`+`asetpts`(+`afade`), niemals über Demuxer-/Muxer-seitiges
   `-ss`/`-t -c copy`. Da WAV (PCM) und FLAC verlustfreie Formate sind,
   bedeutet dieses Re-Encode dort **keinen Qualitätsverlust** (bit-exaktes
   PCM bzw. verlustfreie Kompression) — nur einen vernachlässigbaren
   zusätzlichen CPU-Durchlauf. Die Vorgabe "möglichst ohne unnötige
   Neukodierung" aus §18 wird daher als "ohne unnötigen **Qualitätsverlust**"
   ausgelegt, nicht als "ohne jeglichen CPU-Aufwand" — ein Lese-/Schreibpass
   ohne Qualitätseinbuße ist dem beobachteten Korrektheits-/Präzisionsrisiko
   des Stream-Copy-Pfads klar vorzuziehen (Prinzip #16: lieber transparent
   korrekt als im Zweifel kaputt-aber-schnell).
2. Gemeinsames Modul `genesis_core/audio_formats.py` (`AudioFormatSpec`,
   `FORMATS_BY_NAME`/`FORMATS_BY_EXTENSION`, `CUTTER_MINIMUM_EXPORT_FORMATS =
   ("mp3", "wav", "flac")`) wird jetzt sowohl vom Cutter als auch von der
   Loudness-Engine genutzt (`loudness/engine.py` entsprechend refaktoriert) —
   vermeidet eine zweite, leicht abweichende Codec-Tabelle (DRY), war in
   PROGRESS.md Sitzung 6 bereits als "YAGNI vorerst bewusst nicht vorgezogen,
   sobald ein zweiter Verbraucher existiert" vorgemerkt.
3. Waveform-Visualisierung über ffmpegs `showwavespic`-Filter (rein lesend,
   erzeugt nur ein Cache-PNG unter `<data_dir>/waveform_cache/`, schreibt
   NICHTS in die Datenbank — es ist keine Analyseaussage, sondern nur eine
   Visualisierungshilfe) statt eigener DSP-/Rendering-Code.
4. Start/Ende/Fade-Längen werden in der PySide6-Referenz-UI als
   `QDoubleSpinBox`-Sekundenwerte eingegeben statt per interaktivem
   Maus-Drag auf der Waveform — erfüllt die §18-Anforderung "exakte
   Zeitposition" direkt (numerische Eingabe ist exakter als Pixel-Drag) bei
   deutlich geringerem Implementierungsaufwand; interaktives Draggen bleibt
   Backlog für eine spätere UI-Iteration.
5. Sicherheitsmechanik (analog ADR-0010): `generate_waveform_image()` rein
   lesend; `plan_cut()` reine Berechnung (Validierung Start<Ende, Fades ≤
   Selektionsdauer, Zielpfad-Konflikterkennung, kein ffmpeg-Aufruf);
   `apply_cut()` erfordert `user_confirmed=True`, erzeugt immer eine NEUE
   Datei (`<stem>.cut.<ext>`), fasst das Original nie an. Rollback: neue
   Datei löschen.

**Konsequenzen:**
- Keine "Stream Copy ohne Re-Encode"-Fast-Path-Logik im Code — vereinfacht
  die Engine erheblich (kein `will_use_stream_copy`-Flag, kein zweiter
  Ausführungspfad, der separat getestet werden müsste).
- DB-Schema um neue Tabelle `AudioCut` ergänzt (media_file_id, source_path,
  output_path, start/end/fade-Sekunden, export_format;
  migrationsfrei, `create_all()`).
- API: `GET /media/{id}/cutter/waveform` (PNG, gecacht),
  `POST /media/{id}/cutter/preview` (reine Berechnung),
  `POST /media/{id}/cutter/apply` (confirm-pflichtig),
  `GET /media/{id}/cutter` (volle Historie, §44).
- 17 Engine-Tests + 10 API-Tests, alle grün; bestehende Loudness-Testsuite
  nach dem `audio_formats.py`-Refactoring erneut grün (keine Regression).

**Status:** Angenommen, 2026-10-01 (Sitzung 7/Phase 3).

## ADR-0012: Konvertierungs-Werkzeug — dritter Verbraucher von `audio_formats.py`, kein separater Fachabschnitt im Originalauftrag

**Kontext:** "Konvertieren" ist im Originalauftrag kein eigener nummerierter
Abschnitt (anders als §18 Audio Cutter oder §19 Lautheitsanalyse) — es taucht
nur als Navigationspunkt (§4 UI-Baum: Werkzeuge → Konvertieren), als
Plugin-Typ (§34: "Converter"), als Jobtyp (§35: "Konvertierung"), als
FFmpeg-Einsatzzweck (§47) und als Phase-3-Baustein (§69) auf, ohne
detaillierte Fachanforderungen. Da der Nutzer für solche Fälle explizit
"die bestmögliche Variante wählen, ohne nachzufragen" angewiesen hat, wurde
das Werkzeug nach denselben Prinzipien wie Loudness-Engine (ADR-0010) und
Audio-Cutter (ADR-0011) entworfen, um projektweite Konsistenz zu wahren.

**Entscheidung:**
1. Reine Formatkonvertierung (Zielformat aus `genesis_core.audio_formats`,
   alle 7 dort katalogisierten Formate: mp3/flac/wav/ogg/opus/m4a/aac) mit
   optionaler, vom Nutzer überschreibbarer Bitrate für verlustbehaftete
   Zielformate (wirkungslos bei verlustfreien Zielen — wird nicht als Fehler
   behandelt, aber auch nicht beworben).
2. Gleiche Sicherheitsmechanik wie Loudness/Cutter: `plan_conversion()`
   (reine Berechnung, kein ffmpeg-Aufruf, Konflikterkennung) →
   `apply_conversion()` (erfordert `user_confirmed=True`, erzeugt IMMER eine
   neue Datei `<stem>.converted.<ext>`, Original bleibt unangetastet).
3. **No-Op-Erkennung statt Blockade:** wird dieselbe Formatendung ohne
   abweichende Bitrate angefordert, wird dies als `is_no_op_same_format=True`
   im Plan markiert und dem Nutzer in der Vorschau transparent als Hinweis
   angezeigt (Prinzip #16) — die Aktion wird NICHT verboten (ein Nutzer
   könnte bewusst denselben Codec mit anderen Einstellungen neu erzeugen
   wollen, oder schlicht ausprobieren), sondern nur kommentiert.
4. Kein eigenes DSP/Encoding — reine FFmpeg-Subprocess-Anbindung
   (`convert/ffmpeg_convert.py`), analog zu Loudness/Cutter.
5. DB: neue Tabelle `AudioConversion` (media_file_id, source_path,
   output_path, source_format, target_format, bitrate_kbps), API-Endpunkte
   `POST /media/{id}/convert/preview`, `POST /media/{id}/convert/apply`
   (confirm-pflichtig), `GET /media/{id}/convert` (Historie, §44).

**Konsequenzen:**
- Dritter Verbraucher von `audio_formats.py` bestätigt den Nutzen der in
  ADR-0011 vorgezogenen Extraktion — keine weitere Codec-Tabellen-Duplizierung
  nötig.
- 14 Engine-Tests + 8 API-Tests, alle grün; Core-Gesamtsuite danach 179
  passed/1 skipped (vorher 157).
- End-to-End-Smoke-Test (PySide6-Dialog offscreen in 4 Sprachen + kompletter
  API-Workflow gegen echte Core-Instanz) erfolgreich, keine Befunde.

**Status:** Angenommen, 2026-10-01 (Sitzung 8/Phase 3).

## ADR-0013: Duplikaterkennung (§21) — mehrstufige Heuristik mit String-Gleichheit statt Chromaprint-Dekompression

**Kontext:** §21 verlangt eine mehrstufige Duplikaterkennung (Dateihash →
Größe → Dauer → technische Parameter → Audio-Fingerprint → Metadaten) mit
vier zu unterscheidenden Kategorien ("Exaktes Duplikat", "wahrscheinliches
Duplikat", "gleicher Inhalt/anderes Format", "ähnlicher Inhalt") und dem
zwingenden Grundsatz "Niemals automatisch löschen". Ein empirischer Test in
der Sandbox (identische 440-Hz-Testdatei als WAV/MP3/FLAC codiert) zeigte:
Chromaprint liefert für DENSELBEN Audioinhalt in unterschiedlichen
Formaten/Bitrates einen BYTE-IDENTISCHEN Fingerprint-String. Eine echte
Fuzzy-Ähnlichkeit (Hamming-Distanz) würde eine Nachimplementierung von
Chromaprints properitärem 3-Bit-Differenz-Kompressionsformat erfordern —
keine gepflegte, offline verfügbare Python-Bibliothek dafür im Workspace
bestätigt.

**Entscheidung:**
1. Reine, DB-lesende Analysefunktion (`genesis_core/duplicates/engine.py`,
   `MediaSnapshot`/`find_duplicate_candidates()`) — vergleicht NUR bereits
   vorhandene DB-Felder (Hash, Größe, Dauer, Codec/Samplerate/Kanäle,
   Fingerprint-STRING, Track/Album-Metadaten), fasst keine Datei selbst an.
2. Fingerprint-Vergleich per exakter String-Gleichheit statt
   Hamming-Distanz-Dekodierung — deckt "gleicher Inhalt/anderes Format"
   empirisch zuverlässig ab; "ähnlicher Inhalt" (leicht abweichendes
   Mastering) wird bewusst NICHT per Fuzzy-Fingerprint erkannt (Risiko
   einer unbemerkt fehlerhaften Nachimplementierung wiegt schwerer als der
   Nutzen) — stattdessen deckt diese Kategorie den Fall ab, dass der
   Fingerprint exakt übereinstimmt, aber Dauer/technische Parameter
   abweichen (z.B. getrimmte Version). Dokumentiertes Backlog für eine
   spätere, eigens getestete echte Ähnlichkeitsmetrik.
3. Vier Kategorien exakt nach §21-Wortlaut, mit Konfidenzwert (0.55–1.0) und
   menschenlesbarer deutscher Begründung je Fund.
4. Metadaten (Stufe 6) wirken NUR als Konfidenz-Bonus (+0.05), nie als
   alleiniges/blockierendes Kriterium.
5. **Keine Löschfunktion, auch nicht manuell** — das Werkzeug ist reine
   Erkennung + Protokoll; Löschen bleibt expliziter Backlog für eine
   spätere Phase (z.B. über eine generische Datei-Explorer-Integration).
6. DB: neue Tabellen `DuplicateGroup` (Kategorie, Konfidenz, Begründung,
   `reviewed`-Flag) und `DuplicateGroupMember` (N-zu-N, aktuell mit genau 2
   Mitgliedern pro Gruppe befüllt — Schema ist für spätere
   Mehr-Weg-Cluster-Erweiterung vorbereitet). Jeder Scan ersetzt alle NICHT
   überprüften Gruppen; überprüfte/verworfene Gruppen (`reviewed=True`)
   bleiben unangetastet bestehen.
7. API: `POST /duplicates/scan` (optionaler `kind`-Filter), `GET
   /duplicates` (Filter `reviewed`), `POST /duplicates/{id}/review` +
   `/unreview` (keine `confirm`-Pflicht, da rein organisatorisch, keine
   Dateiänderung, jederzeit umkehrbar).
8. **Zusätzlich (notwendige Vorstufe):** Die bestehende `Fingerprint`-DB-
   Tabelle wurde bisher NIE befüllt (`compute_fingerprint()` wurde nur
   transient in der AcoustID-Metadaten-Vorschlagsengine aufgerufen, ohne
   Persistierung). Neuer Endpunkt `POST/GET /media/{id}/fingerprint`
   berechnet und speichert den Chromaprint-Fingerabdruck explizit (Analyse,
   kein `confirm` nötig) — ohne diese Ergänzung hätte die
   Duplikaterkennungs-Stufe 5 nie Daten zum Vergleichen gehabt. Neuer Button
   "Fingerprint berechnen" in der Medientabelle.
9. Eigene Navigationsseite `nav.duplicates` (anders als Cutter/Loudness/
   Convert, die Pro-Datei-Dialoge aus der Medientabelle sind) — ein
   Duplikat-Scan betrifft immer die gesamte/gefilterte Bibliothek, nicht
   eine einzelne Datei.

**Konsequenzen:**
- O(n²)-Paarvergleich in `find_duplicate_candidates()` — bewusster, für
  Phase 3 akzeptierter Performance-Kompromiss (Korrektheit vor
  Optimierung); Bucketing nach Größe/Dauer für sehr große Bibliotheken ist
  dokumentiertes Backlog (§57, Phase 9).
- 13 Engine-Tests + 10 Duplikate-API-Tests + 5 Fingerprint-API-Tests, alle
  grün; Core-Gesamtsuite danach 207 passed/1 skipped (vorher 179).
- End-to-End-Smoke-Test (reale ffmpeg-Testdateien, echter API-Workflow:
  Fingerprint berechnen → Scan → korrekte Erkennung von "Exaktes Duplikat"
  UND "Gleicher Inhalt/anderes Format" → Review/Filter) erfolgreich; UI in
  allen 4 Sprachen offscreen fehlerfrei instanziiert.

**Status:** Angenommen, 2026-10-01 (Sitzung 9/Phase 3).

## ADR-0014: Qualitätsanalyse (§20) — metadatenbasierte Heuristiken statt Spektralanalyse

**Kontext:** §20 verlangt eine Qualitätsanalyse (Codec, Bitrate, Samplerate,
Bittiefe, Kanäle, Dauer, Peak, Loudness, mögliche Beschädigung) mit
Verdachtserkennung für vier Fälle (verdächtige Upscales, ungewöhnliche
Transcodierungen, beschädigte Dateien, abgeschnittene Dateien) — zwingend
als "Verdacht", nie als Fakt gekennzeichnet. Das DB-Schema
(`TechnicalMetadata.suspected_*`/`quality_notes`) existierte bereits aus
einer früheren Sitzung, aber ungenutzt (keine Logik füllte diese Felder).

**Entscheidung:**
1. Reine, DB-lesende Interpretationsschicht
   (`genesis_core/quality/engine.py`, `QualitySnapshot`/`analyze_quality()`)
   — berechnet SELBST keine neuen ffprobe-/ffmpeg-Werte, sondern interpretiert
   ausschließlich bereits vorhandene `TechnicalMetadata`-, `Track`- und
   `Loudness`-Daten.
2. Vier Verdachtsprüfungen, jede einzeln begründbar und mit dokumentierten
   Grenzen (false-positive-Risiko wird explizit benannt statt verschwiegen):
   - **Beschädigung:** Scanner-Fehler (`MediaFile.last_scan_error`) ODER
     Datei mit Inhalt (`size_bytes > 0`) ohne ermittelbare Dauer.
   - **Abgeschnitten:** vom Tag deklarierte Dauer (`Track.duration_seconds`)
     liegt > 10 % UND > 2 s über der technisch gemessenen Dauer.
   - **Ungewöhnliche Transcodierung:** tatsächlich enthaltener Codec passt
     nicht zur erwarteten Codec-Familie der Dateiendung (z. B. MP3-Daten in
     einer `.flac`-Datei) — robust, da direkt aus bereits bekannten Feldern
     ableitbar, ohne neue Analyse.
   - **Verdächtiges Upscale:** NUR für echte komprimierende verlustfreie
     Codecs (FLAC/ALAC) — tatsächliche Bitrate liegt unter 35 % der
     theoretischen Roh-PCM-Bitrate (unüblich niedrig für echtes
     verlustfreies Material, Hinweis auf eine ursprünglich verlustbehaftete
     Quelle). Rohes PCM (WAV/AIFF) wird bewusst NIE geprüft, da seine
     Bitrate durch das Format exakt vorgegeben ist und kein
     Kompressions-Indiz liefern kann.
3. **Bewusst NICHT implementiert:** eine vollständige Transcode-/
   Upscale-Erkennung müsste das Frequenzspektrum der Audiodaten selbst
   analysieren (z. B. eine für 128-kbps-MP3 typische Tiefpassgrenze bei ca.
   16 kHz, die nach Upscale auf FLAC/320 kbps weiterhin sichtbar bleibt).
   Das erfordert eine eigene FFT-/DSP-Implementierung — analog zur in
   ADR-0013 zurückgestellten Hamming-Distanz-Fingerprint-Ähnlichkeit wird
   dies als dokumentiertes Backlog zurückgestellt, um keine unbemerkt
   fehlerhafte Nachimplementierung als verlässliches Ergebnis auszugeben.
4. Peak/Loudness (von §20 explizit gefordert) werden als rein informative
   Hinweise ausgegeben (Clipping bei True Peak > 0 dBTP, auffällig niedrige
   Lautheit < −40 LUFS) — OHNE eigenes `suspected_*`-Flag, da Lautheit
   allein kein Qualitätsmangel, sondern eine bewusste Entscheidung sein
   kann.
5. Persistenz DIREKT auf der bestehenden `TechnicalMetadata`-Zeile (anders
   als Loudness/Cutter/Convert/Duplikate, die History-Tabellen sind) — das
   Schema sah die `suspected_*`-Felder von Anfang an als Teil dieser
   1:1-"aktueller Zustand"-Tabelle vor; ein erneuter Scan überschreibt diese
   Felder NICHT (nur `extract_technical_summary()`-Felder), eine erneute
   Analyse ersetzt den vorherigen Befund vollständig (keine Historie nötig,
   da es sich um eine wiederholbare Neubewertung desselben aktuellen
   Zustands handelt, nicht um eine Abfolge von Aktionen wie bei Loudness).
6. API: `POST /media/{id}/quality/analyze` (keine `confirm`-Pflicht, analog
   zu `/loudness/analyze` — reine Analyse, keine Dateiänderung), `GET
   /media/{id}/quality`. Voraussetzung: `TechnicalMetadata` muss bereits
   existieren (422, falls noch kein Scan durchgeführt wurde).
7. PySide6: Neuer Button "Qualität prüfen" in der Medientabelle; die
   Detailansicht zeigt den zuletzt gespeicherten Befund PASSIV (ohne Klick)
   mit deutlich sichtbarer Überschrift "(Verdacht, kein Fakt, §20)".

**Konsequenzen:**
- 18 Engine-Tests + 13 API-Tests, alle grün; Core-Gesamtsuite danach 238
  passed/1 skipped (vorher 207).
- End-to-End-Smoke-Test (reale ffmpeg-Testdateien inkl. einer MP3-Datei mit
  `.flac`-Endung zur gezielten Transcode-Erkennung) erfolgreich: korrekte
  Erkennung von `suspected_transcode=True` für die Fake-FLAC-Datei und
  `keine Auffälligkeiten` für eine saubere MP3-Datei; UI in allen 4
  Sprachen offscreen fehlerfrei instanziiert, Detailansicht zeigt den
  Qualitätsabschnitt korrekt lokalisiert an.
- Damit ist **Phase 3 (Audio) inhaltlich vollständig abgeschlossen**
  (Loudness, Cutter, Konvertierung, Duplikaterkennung, Qualitätsanalyse) —
  nächster Schritt laut Nutzervorgabe: Phase 4 (Hörbücher).

**Status:** Angenommen, 2026-10-01 (Sitzung 9/Phase 3, Abschluss).

## ADR-0015: Hörbücher & Kapitel (§23) — rein tag-basiert, kein Online-Provider, Intervall- statt DSP-Kapitelerzeugung

**Kontext:** §23 verlangt eine Hörbuchverwaltung (Titel, Autor, Sprecher,
Reihe, Band, Verlag, Jahr, Sprache, Beschreibung) sowie eine optionale
Kapitelverwaltung (erkennen, erzeugen, umbenennen, exportieren). Die
Datenmodelle (`Audiobook`, `Series`, `Chapter`, `Person`/`PersonRole`)
existierten bereits vollständig im Schema (Phase 1), waren aber bislang
ungenutzt. Der Scanner klassifiziert `.m4b`-Dateien bereits automatisch als
`MediaKind.AUDIOBOOK` (siehe `scanner/classify.py`); ambige Endungen
(`.mp3`, `.m4a`, `.aac`, `.flac`, `.wav`) bleiben bewusst defensiv
`MUSIC`-klassifiziert — eine inhaltliche Scanner-Reklassifizierung ist NICHT
Teil dieses Scopes (siehe Konsequenzen).

**Entscheidung:**
1. **Kein Online-Hörbuch-Provider** (z. B. Audible/OpenLibrary-Abgleich) in
   dieser Phase — das würde inhaltlich mit dem Phase-8-Konzept
   (austauschbare Download/Import-Adapter) überlappen und wird bewusst
   zurückgestellt, um die Download/Import-Architektur nicht vorab zu
   fragmentieren. Stattdessen werden ausschließlich bereits in der Datei
   eingebettete Tags gelesen (`audiobook/tags.py`), analog zur bestehenden
   `metadata/tag_reader.py`-Grundlage (deren private Helfer `_first_value`/
   `_parse_leading_int` dafür zu `first_tag_value`/`parse_leading_int`
   public gemacht wurden).
2. **Transparente Fallback-Herkunft statt Erfindung (Prinzip #16):** Für
   Autor/Sprecher/Reihe existiert branchenweit KEIN einheitliches
   Tag-Schema. Existiert kein dediziertes Tag (`author`, `narrator`,
   `series` bzw. deren ID3/Vorbis/MP4-Varianten), wird ersatzweise das
   generische `artist`- (Autor), `composer`- (Sprecher) bzw. `album`-Feld
   (Reihe) herangezogen — die tatsächliche Quelle wird dabei IMMER über ein
   eigenes `*_source`-Feld (`"tag"` vs. `"artist_field"`/`"composer_field"`/
   `"album_field"`) offengelegt, nie stillschweigend vermischt.
3. **Übernahme in die DB ausschließlich über einen bestätigungspflichtigen
   `apply_audiobook_tags()`-Fluss** (`AudiobookApplyNotConfirmedError` bei
   `user_confirmed=False`), 1:1 nach dem Muster von
   `MetadataEngine.apply_suggestion` — auch wenn die Quelle „nur“ die Datei
   selbst ist, bleibt die Bestätigungspflicht bestehen (Konsistenz mit dem
   projektweiten Sicherheitsmodell, Prinzip #17/§44). Server-seitig wird
   defensiv ERNEUT aus der Datei gelesen statt dem Client-Payload zu
   vertrauen (Lehre aus Deep-Review-Fund F-12, siehe ADR zu Phase 2/3).
4. **Kapitel erkennen:** liest ausschließlich bereits eingebettete
   Kapitelmarken (`ffprobe -show_chapters`, bereits vorhandene
   `scanner/ffprobe_util.probe_file()`-Grundlage) — reine Vorschau ohne
   Seiteneffekt; eine Übernahme ERSETZT alle bestehenden Kapitel atomar
   (`replace_chapters()`), nicht additiv, um inkonsistente Teilzustände zu
   vermeiden.
5. **Kapitel erzeugen (§23, optional) bewusst einfach gehalten:**
   GLEICHMÄSSIGE Intervall-Kapitel („Kapitel 1“, „Kapitel 2“, …) aus einer
   nutzerdefinierten Minutenangabe — ausdrücklich NICHT als inhaltlich
   sinnvolle Kapitelgrenzen ausgegeben. Eine echte Kapitelerkennung über
   Stille-/Sprechpausenerkennung wäre eine eigene DSP-Analyse — analog zur
   in ADR-0013/ADR-0014 zurückgestellten Fingerprint-Ähnlichkeits- bzw.
   Spektralanalyse wird dies als dokumentiertes Backlog zurückgestellt.
6. **Kapitel umbenennen:** einfacher Edit auf `Chapter.title`, geht
   TROTZDEM durch das Bestätigungsmuster (Textfeld + Ja/Nein), um
   Konsistenz mit dem projektweiten Sicherheitsmodell zu wahren, auch wenn
   das Risiko eines reinen Textfelds gering ist.
7. **Export (JSON/CSV) ohne `confirm`-Pflicht** — reine Lesefunktion wie
   andere Exporte im Projekt (§45).
8. API: `GET/POST /media/{id}/audiobook/tags[/apply]`, `GET
   /media/{id}/audiobook`, `GET /media/{id}/chapters`, `POST
   /media/{id}/chapters/detect[/apply]`, `POST
   /media/{id}/chapters/generate[/apply]`, `PATCH
   /media/{id}/chapters/{chapter_id}`, `GET
   /media/{id}/chapters/export?format=json|csv`.
9. PySide6: neuer dedizierter `AudiobookDialog` (zwei Tabs: Metadaten,
   Kapitel) statt Wiederverwendung von `MetadataSuggestionsDialog` (andere
   Felder, kein Online-Provider, zusätzliche Kapitelverwaltung). Der
   zugehörige Aktionsbutton in der Medientabelle ist NUR aktiv, wenn genau
   EIN Medium der Art `audiobook` ausgewählt ist.

**Konsequenzen:**
- Neues Modul `core/genesis_core/audiobook/` (`tags.py`, `engine.py`,
  Facade `__init__.py`); 12 Engine-Unit-Tests + 11 API-Tests, alle grün;
  Core-Gesamtsuite danach 261 passed/1 skipped (vorher 238).
- End-to-End-Smoke-Test mit zwei echten ffmpeg-erzeugten Testdateien (eine
  `.m4b` mit Tags UND zwei eingebetteten Kapitelmarken, eine `.mp3` ohne
  Hörbuch-Tags) über einen laufenden Core-Server: Scanner klassifiziert
  `.m4b` korrekt als `audiobook` und `.mp3` als `music`; vollständiger
  API-Workflow (Tags lesen → übernehmen → Kapitel erkennen → übernehmen →
  exportieren) erfolgreich; `AudiobookDialog` in allen 4 Sprachen offscreen
  fehlerfrei instanziiert, inkl. korrekt lokalisierter Quellenangaben
  (`artist_field`/`album_field`); Aktionsbutton in der Medientabelle
  korrekt nur für die `.m4b`-Zeile aktiv, für die `.mp3`-Zeile deaktiviert.
- **Bewusst zurückgestelltes Backlog** (nicht Teil dieser Phase): (a)
  inhaltliche Scanner-Reklassifizierung ambiger Audio-Endungen als
  Hörbuch anhand von Tags/Dauer-Heuristiken, (b) Online-Hörbuch-Provider-
  Abgleich (Phase 8), (c) Stille-/Sprechpausen-basierte Kapitelerkennung.
- Damit ist **Phase 4 (Hörbücher) inhaltlich vollständig abgeschlossen** —
  nächster Schritt laut Nutzervorgabe: Phase 5 (Video: Filme/Serien, §24).

**Status:** Angenommen, 2026-10-01 (Sitzung 10/Phase 4, Abschluss).

## ADR-0016: Video (Filme/Serien, §24) — kein Online-Provider, Film/Episode-Erkennung ausschließlich aus Tags/Dateiname/Ordnerstruktur, bestätigungspflichtige Klassifizierung

**Kontext:** §24 verlangt eine Film-/Serienverwaltung (Titel, Originaltitel,
Jahr, Genre, Laufzeit, Sprache, Beschreibung, Regisseur, Schauspieler;
Serien zusätzlich Staffel/Episode). Die Datenmodelle (`Movie`, `Episode`,
`Series`, `Person`/`PersonRole`) existierten bereits vollständig im Schema
(Phase 1). Der Scanner klassifiziert alle Video-Endungen bislang pauschal
als `MOVIE` (`scanner/classify.py`, `VIDEO_EXTENSIONS`) — eine
automatische Unterscheidung Film vs. Serien-Episode existierte noch nicht.
Technische Metadaten (Auflösung, Codec, HDR, Sprachen, Untertitel) werden
bereits automatisch per ffprobe beim Scan erfasst (`ffprobe_util.py`,
diese Sitzung um `languages_json`/`subtitles_json` erweitert) — das ist
rein deskriptiv und fällt NICHT unter die Bestätigungspflicht.

**Entscheidung:**
1. **Kein Online-Provider** (z. B. TMDB/TheTVDB) in dieser Phase — analog
   zu ADR-0015 (Hörbücher) bewusst zurückgestellt, um nicht vorzeitig in
   die Phase-8-Download/Import-Adapter-Architektur einzugreifen.
   Stattdessen werden ausschließlich bereits in der Datei eingebettete
   Tags (`video/tags.py::read_video_tags()`) sowie, falls keine
   Serien-Tags vorhanden sind, Dateiname-/Ordnerstruktur-Muster
   (`video/engine.py::detect_episode()`) ausgewertet.
2. **Film-vs-Episode-Erkennung ist IMMER nur ein Vorschlag mit
   Confidence-Wert, nie eine automatische Umklassifizierung:**
   `detect_episode()` liefert `is_likely_episode`, `confidence` (0.9 bei
   eingebetteten TV-Show-Tags = `source="tag"`; 0.6 bei
   Dateiname-/Ordner-Mustererkennung wie `S01E02` = `source=
   "filename_pattern"`/`"directory_name"`/`"filename"`; 0.0 für reine
   Filme) sowie pro Feld eine eigene `*_source`-Angabe. Die eigentliche
   Übernahme (Umklassifizierung `MediaFile.kind` zu `"movie"`/`"episode"`
   plus Anlage der `Movie`- bzw. `Episode`-/`Series`-Zeilen) geschieht
   ausschließlich über `apply_movie_metadata()`/`apply_episode_metadata()`
   mit Pflicht-Bestätigung (`VideoApplyNotConfirmedError` bei
   `confirm=False`), 1:1 nach dem Muster von Phase 4
   (`apply_audiobook_tags`). Server-seitig wird defensiv erneut aus der
   Datei gelesen statt dem Client-Payload zu vertrauen (Konsistenz mit
   ADR-0015 Punkt 3).
3. **Regisseur/Schauspieler erzeugen `Person`/`PersonRole`-Zeilen (§63
   Wissensgraph):** Beim Apply werden Personen per Name get-or-created und
   mit `PersonRoleType.DIRECTOR`/`ACTOR` sowie der jeweiligen
   `movie_id`/`episode_id`-Fremdschlüsselspalte verknüpft. Erneutes Apply
   auf dasselbe Medium dedupliziert (keine doppelten `PersonRole`-Zeilen).
   Dieselbe Person kann unabhängig in mehreren Rollen/Werken auftreten
   (verifiziert: "Test Actor One" trägt sowohl DIRECTOR- als auch
   ACTOR-Rollen über Film und Episode hinweg, siehe Smoke-Test).
4. **Serien-Wiederverwendung:** `apply_episode_metadata()` sucht eine
   bestehende `Series` per Name, bevor eine neue angelegt wird (analog zum
   `Series`-get-or-create-Muster aus Phase 4 für Hörbuch-Reihen).
5. API: `GET /media/{id}/video/tags` (Vorschau, kein Seiteneffekt), `POST
   /media/{id}/video/episode-detection` (Vorschau), `POST
   /media/{id}/movie/apply`/`GET /media/{id}/movie`, `POST
   /media/{id}/episode/apply`/`GET /media/{id}/episode` — Apply-Endpunkte
   mit `confirm`-Pflicht (422 sonst), alle protokolliert über
   `ProcessingJob`/`record_history` (Prinzip #17/§44).
6. PySide6: neuer dedizierter `VideoDialog` mit zwei Tabs ("Film" und
   "Serie/Episode"), analog zu `AudiobookDialog` — getrennte Tabs statt
   eines gemeinsamen Formulars, weil sich die Zielschemata (Movie vs.
   Episode/Series) strukturell unterscheiden und der Nutzer explizit
   entscheiden soll, als welcher Typ übernommen wird. Aktionsbutton in der
   Medientabelle ist nur aktiv, wenn genau EIN Medium der Art `"movie"`
   oder `"episode"` ausgewählt ist.

**Konsequenzen:**
- Neues Modul `core/genesis_core/video/` (`tags.py`, `engine.py`, Facade
  `__init__.py`); 11 Engine-Unit-Tests + 9 API-Tests + 10 neue
  `ffprobe_util`-Tests (Sprachen/Untertitel/Frame-Rate-Parsing), alle
  grün; Core-Gesamtsuite danach **291 passed, 1 skipped** (vorher 261).
- End-to-End-Smoke-Test über einen laufenden Core-Server gegen eine echte
  Test-Bibliothek mit 3 Video-Dateien (reiner Film mit Freeform-Tags für
  Regisseur/Schauspieler; getaggte Serien-Episode; nur per Dateiname
  erkennbare Serien-Episode `S01E02`): Scan klassifiziert alle zunächst
  als `movie` (Scanner-Grobklassifizierung unverändert); Tags-Vorschau,
  Episode-Detection-Vorschau (0.9/0.6/0.0 Confidence je nach Quelle wie
  erwartet), Movie-Apply und zwei Episode-Applies erfolgreich; `MediaFile.
  kind` korrekt auf `movie`/`episode` aktualisiert; `Person`/`PersonRole`-
  Zeilen korrekt angelegt (Wissensgraph); `Series`-Wiederverwendung über
  beide Episoden bestätigt (eine `Series`-Zeile, zwei `Episode`-Zeilen);
  `ProcessingHistory` korrekt protokolliert. `VideoDialog` sowie
  `MediaTableView` offscreen in allen 4 Sprachen fehlerfrei instanziiert,
  Aktionsbutton korrekt nur bei `kind in {"movie","episode"}` aktiv.
- **Bewusst zurückgestelltes Backlog** (nicht Teil dieser Phase): (a)
  Online-Provider-Abgleich (TMDB/TheTVDB) — Phase 8, (b) automatische
  Scanner-Vorklassifizierung von Episode vs. Film direkt beim Scan (aktuell
  bewusst erst nachträglich on-demand über die Detection-Vorschau, um die
  Scan-Phase schnell und seiteneffektfrei zu halten), (c) Mehrfach-
  Regisseur/Schauspieler-Rollenauflösung bei Namenskonflikten (z. B. zwei
  unterschiedliche Personen mit identischem Namen) — aktuell einfache
  Name-basierte Deduplizierung wie in Phase 4.
- Damit ist **Phase 5 (Video: Filme/Serien) inhaltlich vollständig
  abgeschlossen** — nächster Schritt laut Nutzervorgabe: Phase 6 (KI:
  lokale KI-Metadaten/-Analyse, Ollama/LM Studio).

**Status:** Angenommen, 2026-10-01 (Sitzung 10/Phase 5, Abschluss).

## ADR-0017: KI-Metadaten, KI-Suche, KI-Musik (§25/§26/§27) — EAV-Speicherung statt kanonischer Felder, dediziertes Embedding-Modell, manuelle KI-Musik-Provenienz

**Kontext:** Phase 6 verlangt drei thematisch verwandte, aber funktional
unterschiedliche KI-Fähigkeiten: §25 KI-Metadaten-VORSCHLÄGE (Genre,
Stimmung, Sprache, Instrumente, Gesang, Thema, Beschreibung, Tags,
Klassifikation) über eine austauschbare Provider-Abstraktion, §26 lokale
semantische Suche ("ruhige Musik zum Einschlafen" etc.) und §27 KI-Musik-
Provenienz (AI Generated/Human Generated/Hybrid/Unknown + Quelle/Modell/
Prompt/Erstellungsdatum/Besitzer/Künstlername/Stil/Stimmung). Die
Provider-Abstraktion (`AIProvider`, `OllamaProvider`, `NullAIProvider`,
`build_ai_provider`) sowie das `AIMetadata`-EAV-Schema und die §27-Felder
auf `Track` existierten bereits vollständig aus Phase 1 (ADR-0003) -
ungenutzt. Es gab noch KEINE Engine, API oder UI dafür.

**Umgebungsvalidierung (wichtig fuer diese Entscheidung):** Ollama wurde in
dieser Sitzung TATSÄCHLICH in der Sandbox installiert (nicht gemockt, wie
in einer früheren Sitzung für Phase 6 bereits festgelegt) - Binärinstallation
nach `/opt/ollama_test` (ausserhalb `/home/user`, da das ~900MB-Archiv den
Workspace aufgebläht hätte; `/tmp` ist als tmpfs mit nur ~1 GB zu klein).
Modelle `qwen2.5:0.5b` (Text, 397 MB) und `all-minilm` (Embeddings, 45 MB)
real heruntergeladen und über `ollama serve` auf `127.0.0.1:11434`
betrieben. Beide Modelle wurden gegen die echte REST-API getestet (siehe
Konsequenzen) - die Architekturentscheidungen unten basieren auf diesem
echten Verhalten, nicht auf Annahmen.

**Entscheidung:**
1. **KI-Metadaten-Vorschläge werden NUR in der generischen `AIMetadata`-
   EAV-Tabelle gespeichert, NICHT automatisch in die kanonischen Felder
   (`Track.genre_id`, `Movie.genre`, ...) übernommen.** §25 verlangt
   lediglich, dass jedes KI-Ergebnis mit "AI generated/Model/Model
   version/Timestamp/Confidence" gespeichert wird - nicht, dass es die
   bestehenden, ggf. vom Nutzer gepflegten Metadatenfelder überschreibt.
   Eine Vermischung mit der bestehenden `metadata/engine.py` (Online-
   Provider, kanonische Felder) würde zwei strukturell unterschiedliche
   Flüsse (feste MusicBrainz-Matches vs. offene, freitextige KI-Vorschläge)
   künstlich zusammenzwingen. Eine manuelle Übernahme in echte Felder
   bleibt dem bestehenden Tag-Editor vorbehalten.
2. **Ein Reapply desselben Feldes+Modells ERSETZT den vorherigen
   `AIMetadata`-Eintrag** (kein unbegrenztes Anwachsen bei wiederholtem
   Retry/Reindex) - dieselbe Dedup-Logik wie `PersonRole` in Phase 4/5.
   Unterschiedliche Modelle für dasselbe Feld werden dagegen beide
   behalten (Vergleichbarkeit verschiedener KI-Ergebnisse).
3. **Separates, dediziertes Embedding-Modell (`all-minilm`) statt des
   Text-Generierungsmodells für §26.** Realer Test ergab: Ollamas
   `/api/embed`-Endpunkt lehnt reine Chat-/Instruct-Modelle wie
   `qwen2.5:0.5b` explizit ab ("this server does not support
   embeddings"/Modell liefert keine Pooling-Repräsentation), während ein
   dediziertes Embedding-Modell (nur 45 MB) echte 384-dimensionale Vektoren
   liefert. `AISettings.embedding_model` (Default `"all-minilm"`) ist
   daher ein eigenes Konfigurationsfeld, `AIProvider.embed_text()` eine
   neue abstrakte Methode (liefert `None` statt Exception bei fehlendem
   Modell/nicht erreichbarem Dienst - "keine KI verfügbar" ist ein
   normaler Zustand, kein Absturz).
4. **Semantische Suche: Brute-Force-Kosinus-Ähnlichkeit über eine
   zwischengespeicherte `AIEmbedding`-Tabelle** (ein Eintrag pro
   `(media_file_id, model_name)`, per `UniqueConstraint` erzwungen).
   Reindex überspringt unveränderte Dateien (`source_text_hash`-Vergleich)
   für Performance bei grossen Bibliotheken (§57). Eine echte ANN-
   Indexstruktur (z. B. FAISS) wäre ein Hardening-Thema (Phase 9) und wird
   bewusst zurückgestellt - für Entwicklungs-/Testbibliotheken ist die
   einfache Variante ausreichend und wurde gegen eine reale 9-Datei-
   Testbibliothek mit sinnvollen Ergebnissen verifiziert (siehe
   Konsequenzen). Der Such-/Embedding-Text ist bewusst identisch mit dem
   KI-Metadaten-Kontext (`ai/engine.py::build_context`) - eine einzige
   Quelle der Wahrheit für "was weiss GENESIS bereits über diese Datei",
   keine zweite, abweichende Textzusammenstellung nur für die Suche.
5. **Reindex ist bestätigungsfrei** (reine additive Cache-Operation ohne
   Risiko für Originaldateien/bestehende Metadaten) - anders als
   Metadaten-ÄNDERUNGEN (Prinzip #17 gilt dort, nicht für einen
   Suchindex-Cache).
6. **KI-Musik-Provenienz (§27) ist AUSSCHLIESSLICH eine manuelle
   Nutzerangabe, niemals ein KI-Vorschlag.** GENESIS kann KI-Urheberschaft
   einer Audiodatei nicht selbst zuverlässig feststellen (unbelegte
   Tatsachenbehauptung, Prinzip #16) - der gesamte `ai/music_provenance.py`-
   Fluss ist daher bestätigungspflichtig wie jede andere Änderung, auch
   wenn der Nutzer selbst der "Provider" der Information ist (Konsistenz
   mit allen anderen Apply-Flüssen). "Künstlername" wird NICHT als
   weiteres Textfeld auf `Track` dupliziert, sondern über eine
   `PersonRole` (`role=ARTIST`, `track_id=...`) abgebildet - konsistent
   mit dem Wissensgraph-Muster aus §63/Phase 5 (Regisseur/Schauspieler).
   Status `AI_GENERATED`/`HYBRID` klassifiziert `MediaFile.kind` zu
   `AI_MUSIC` um (eigene Navigationskategorie); `HUMAN_GENERATED`/
   `UNKNOWN` lassen die Klassifikation unverändert. Neues `Track.ai_owner`-
   Feld ergänzt (einziger im bestehenden Schema fehlender §27-Wert).
7. **API:** `POST /media/{id}/ai/suggest` (Vorschau), `POST
   /media/{id}/ai/apply` + `GET /media/{id}/ai/metadata` (Übernahme/
   Anzeige, `confirm`-Pflicht), `GET /ai/status` (Transparenz: Provider/
   Modell/lokal/erreichbar, Prinzip #9), `GET/POST /media/{id}/ai-music`
   (`confirm`-Pflicht), `POST /ai/search/reindex` (ohne confirm), `POST
   /ai/search` (Vorschau).
8. **PySide6:** neuer `AIDialog` (Tabs "KI-Vorschläge" mit Checkbox-Liste
   + optional "KI-Musik", letzterer nur sichtbar für `kind in
   {music, ai_music}`) aus der Medientabelle heraus (KI-Button für JEDE
   einzeln ausgewählte Datei aktiv, da §25 medienartunabhängig ist) sowie
   eine neue eigenständige Seite `AICenterView` (ersetzt den bisherigen
   Platzhalter `nav.ai_metadata`) für §26 - analog zur bestehenden
   Trennung "Pro-Datei-Dialog" (Cutter/Loudness/Convert/Hörbuch/Video) vs.
   "bibliotheksweite Seite" (Duplikaterkennung).

**Konsequenzen:**
- Neue Module `core/genesis_core/ai/engine.py` (§25), `ai/search.py`
  (§26), `ai/music_provenance.py` (§27); `AIProvider`/`NullAIProvider`/
  `OllamaProvider` um `embed_text()` erweitert; neue DB-Tabelle
  `AIEmbedding`; neues `Track.ai_owner`-Feld.
- 35 neue Engine-Unit-Tests (`test_ai_engine.py`, `test_ai_search.py`,
  `test_ai_music_provenance.py`, deterministische Stub-Provider, kein
  Ollama nötig) + 16 neue API-Tests (`test_api_ai.py`) - alle grün.
  Core-Gesamtsuite danach **343 passed** (vorher 291 passed/1 skipped -
  der zuvor übersprungene `test_ollama_integration_suggests_fields` aus
  Phase 1 läuft jetzt ebenfalls echt durch, da Ollama real erreichbar
  ist).
- **Echter End-to-End-Smoke-Test mit laufendem Ollama (kein Stub) über
  einen echten Core-API-Server gegen eine 9-Datei-Testbibliothek:** `GET
  /ai/status` zeigt `provider=ollama, available=true`; `POST .../ai/
  suggest` liefert echte LLM-Ausgaben (z. B. `genre=music, mood=happy`
  für eine getaggte Testdatei, Laufzeit ~2.5s); Apply persistiert korrekt
  mit voller Herkunft; `POST .../ai-music/apply` setzt Status/Quelle/
  Modell/Stil + `PersonRole`(ARTIST) und klassifiziert `MediaFile.kind`
  korrekt zu `ai_music` um; `POST /ai/search/reindex` indiziert alle 9
  Dateien mit echten 384-dim `all-minilm`-Vektoren; `POST /ai/search` mit
  der Anfrage "synthwave electronic music" rankt die KI-Musik-Datei
  korrekt auf Platz 1, die Anfrage "Film mit Regisseur und Schauspielern"
  rankt alle drei Video-Dateien korrekt vor den Audio-Dateien - die
  semantische Suche liefert also inhaltlich sinnvolle, nicht zufällige
  Ergebnisse. `ProcessingHistory` korrekt für alle drei Apply-/Reindex-
  Aktionen protokolliert. `AIDialog`/`AICenterView` zusätzlich direkt
  gegen denselben laufenden Server (reale HTTP-Aufrufe, kein Mock)
  durchgetestet - Status-Banner, Vorschlagsgenerierung, gespeicherte KI-
  Musik-Felder und Suchergebnisse werden korrekt und korrekt lokalisiert
  (DE) angezeigt.
- Ollama-Binärinstallation liegt bewusst ausserhalb des Workspace
  (`/opt/ollama_test`, ~1.4 GB inkl. beider Modelle) - persistiert NICHT
  über Sitzungen hinweg (ausserhalb `/home/user`) und muss bei Bedarf in
  einer künftigen Sitzung erneut heruntergeladen werden (Download-Schritte
  in dieser ADR dokumentiert: `curl .../ollama-linux-amd64.tar.zst` +
  `tar --zstd -xf`, da `ollama-linux-amd64.tgz` nicht mehr existiert).
- **Bewusst zurückgestelltes Backlog** (nicht Teil dieser Phase): (a)
  ANN-Indexstruktur für die semantische Suche bei sehr grossen
  Bibliotheken (Phase 9 Hardening), (b) DSP-basierte Audio-KI-Analyse
  direkt aus dem Audiosignal (`nav.ai_audio_analysis` bleibt Platzhalter -
  eigenständiges, deutlich aufwändigeres Feature, nicht Teil von §25/26/27
  im engeren Sinne), (c) GUI-Einstellungsseite zum Aktivieren von KI
  (aktuell nur über `config.yaml` - Settings-UI ist projektweit noch nicht
  gebaut, siehe "weiterhin offen"), (d) `creation_date`-Eingabefeld im
  `AIDialog`-UI-Formular (API/Engine unterstützen es, das PySide6-
  Referenzformular verzichtet bewusst auf ein Datumsfeld, um die
  UI-Komplexität zu begrenzen).
- Damit ist **Phase 6 (KI: lokale KI-Metadaten/-Suche/-Musik) inhaltlich
  vollständig abgeschlossen** - nächster Schritt laut Nutzervorgabe: Phase
  7 (Voice Studio, §28/§29).

**Status:** Angenommen, 2026-10-01 (Sitzung 10/Phase 6, Abschluss).

## ADR-0018: Voice Studio (§28/§29) — Piper als lokale TTS-Engine, GPL-3.0-Engine-Lizenz akzeptiert, Profil-Lizenz-Disclosure statt Automatik, lokale API als §29-Schnittstelle, Voice-Cloning zurückgestellt

**Datum:** 2026-10-01 (Sitzung 10/Phase 7)

**Kontext:**

Der Originalauftrag verlangt in §28 ein eigenständiges "GENESIS VOICE
STUDIO"-Modul mit: Stimme aufnehmen, Sprachproben verwalten, Voice Profile
erstellen/testen/löschen/sichern, Text-to-Speech, Audio exportieren, rein
lokale Verarbeitung. Die Anwendung MUSS dabei immer klar anzeigen: Welche
Engine? Welche Modell-Lizenz? Offline? Open Source? Kommerzielle Nutzung
erlaubt? Keine Sprachdaten dürfen ohne ausdrückliche Nutzeraktion an externe
Server übertragen werden. §29 verlangt zusätzlich eine lokale TTS-
Schnittstelle für ANDERE Anwendungen (mögliche Formen: lokaler HTTP-
Endpunkt, REST API, CLI, Windows-TTS-Integration, WAV/MP3-Export) nach dem
Muster "Andere lokale Anwendung → GENESIS Voice API → Voice Engine →
Audio" — die Voice Engine muss austauschbar sein.

**Entscheidung 1 — Piper (OHF-Voice/piper1-gpl) als primäre, real
getestete lokale TTS-Engine:**

Nach Recherche der verfügbaren vollständig offline-fähigen Open-Source-
TTS-Engines (Piper, Coqui TTS/XTTS, eSpeak-NG, Festival) fiel die Wahl auf
Piper:
- Rein lokale VITS/ONNX-Synthese, kein GPU-Zwang, sehr klein (CPU-Echtzeit-
  Faktor >1 selbst auf bescheidener Hardware, in der Sandbox real
  gemessen: ~3-6s Audio in ~1-2s Rechenzeit).
- Als `pip install piper-tts` installierbar, bündelt die
  Phonemisierungsdaten (espeak-ng-data) selbst mit - KEINE zusätzliche
  System-Abhängigkeit nötig (real getestet: funktioniert ohne separates
  `apt install espeak-ng`).
- Über 100 vortrainierte Stimmen in >30 Sprachen verfügbar
  (rhasspy/piper-voices auf Hugging Face), darunter Deutsch und Englisch
  (real heruntergeladen und getestet: `de_DE-thorsten-low`,
  `en_US-amy-low`).
- Alternative Coqui XTTS v2 böte Voice-Cloning aus kurzen Samples, hat
  aber eine restriktive Lizenz (Coqui Public Model License, nicht klar
  kommerziell nutzbar) und benötigt deutlich mehr Rechenleistung/RAM -
  passt schlechter zum Projektziel "läuft auf bescheidener Hardware,
  offline, Open-Source-Lizenzen vorrangig".

**Wichtiger Lizenz-Fund (reale Recherche, nicht aus Trainingsdaten
übernommen):** Das aktuell gepflegte `piper-tts`-Python-Paket (Version
1.8.0, PyPI-Metadaten real geprüft: `License: GPL-3.0-or-later`,
Homepage `github.com/OHF-voice/piper1-gpl`) ist GPL-3.0-or-later, NICHT
MIT. Das ursprüngliche `rhasspy/piper`-Repository war MIT-lizenziert,
wurde aber im Oktober 2025 archiviert (read-only, unmaintained) - die
aktive Entwicklung liegt seitdem bei der Open Home Foundation unter
GPL-3.0. Die Stimmen-GEWICHTE selbst (die `.onnx`-Dateien in
`rhasspy/piper-voices`) bleiben separat MIT-lizenziert - Engine-Code und
Modellgewichte sind zwei getrennte Werke mit getrennten Lizenzen (siehe
Quellenbeleg in der Sitzungs-Recherche).

Das ist für GENESIS unproblematisch: das Projekt verwendet bereits an
anderer Stelle eine GPL-Abhängigkeit (`mutagen`, GPL-2.0-or-later, siehe
`core/requirements.txt`-Kommentar), und GENESIS selbst soll am Ende unter
einer Open-Source-Lizenz veröffentlicht werden (Prinzip #1, kein
proprietäres Closed-Source-Produkt) - GPL-Copyleft-Pflichten greifen vor
allem bei der Weitergabe von Closed-Source-Derivaten, was hier nicht der
Plan ist. Die genaue projektweite Gesamtlizenz-Kompatibilitätsprüfung
bleibt wie beschlossen Teil von Phase 10 (License Center, ADR-0005) - für
Phase 7 wird nur sichergestellt, dass Engine- UND Modell-Lizenz pro
Profil TRANSPARENT in der Datenbank/UI sichtbar sind (siehe Entscheidung
2), damit diese spätere Prüfung vollständige Information vorfindet.

**Entscheidung 2 — Lizenz-/Transparenz-Disclosure liegt am
`VoiceProfile`, nicht an der Engine, und wird NIE automatisch
übernommen:**

Ein einzelner Provider (z.B. "piper") kann mehrere Stimmen-Modelle mit
UNTERSCHIEDLICHEN Modell-Lizenzen bedienen - die vier Pflichtfelder aus
§28 (Engine/Modell-Lizenz/Offline/Open-Source) plus "kommerziell nutzbar"
werden daher pro `VoiceProfile`-Datenbankzeile gespeichert, nicht pro
Provider-Klasse. `genesis_core.voice.catalog.ENGINE_CATALOG` liefert nur
UNVERBINDLICHE Vorschlagswerte für das Anlage-Formular (z.B. "Piper ist
typischerweise GPL-3.0-or-later") - der Nutzer sieht und bestätigt diese
Werte beim Anlegen eines Profils immer explizit (Prinzip #9/#17), die
tatsächlich gespeicherten Werte kommen ausschließlich aus der
Nutzereingabe. Das ist nötig, weil GENESIS die Lizenz einer einzelnen
heruntergeladenen Stimmen-Datei nicht automatisch zuverlässig feststellen
kann (keine standardisierte Lizenz-Metadatei in der `.onnx`-Datei selbst)
- eine automatische Annahme wäre eine unbelegte Tatsachenbehauptung
(Prinzip #16).

**Entscheidung 3 — Löschen eines Voice-Profils erfordert eine
VERSCHÄRFTE Bestätigung (erstmals im Projekt umgesetzt):**

Der Originalauftrag verlangt allgemein "Löschen = extra confirm"
(strenger als eine normale Änderung). Bisher gab es im gesamten Projekt
noch KEINEN einzigen Lösch-Endpunkt (alle bisherigen Phasen erzeugen nur
neue Dateien/Zeilen, nichts wird je gelöscht). `DELETE
/voice/profiles/{id}` ist der erste Lösch-Endpunkt und setzt dafür einen
neuen, wiederverwendbaren Präzedenzfall: zusätzlich zu `confirm=true`
muss der Aufrufer `confirm_name` exakt auf den Profilnamen setzen (Server
validiert dies authoritativ, die UI prüft zusätzlich lokal vorab über
einen `QInputDialog`, bevor überhaupt ein API-Aufruf erfolgt). Eine
optionale Referenz-Sprachprobe (`sample_path`) wird beim Löschen NIE von
der Festplatte entfernt (Prinzip #4) - nur die Datenbankzeile
verschwindet.

**Entscheidung 4 — Jede Sprachsynthese erzeugt eine neue, unveränderliche
`VoiceSynthesis`-Zeile (volle Historie) statt etwas zu überschreiben:**

Analog zu `AudioCut`/`Loudness` aus früheren Phasen. Jede Ausgabedatei
landet in einem eigenen `voice_output`-Unterordner des Datenverzeichnisses
(nie im Ordner einer Original-Mediendatei). Synthese UND der feste
"Profil testen"-Button (ADR-0018 nutzt denselben Code-Pfad mit einem
sprachabhängigen Festtext) erfordern beide `confirm=true`, da beide eine
neue Datei erzeugen (Prinzip #17, konsistent mit Cutter/Convert/
Loudness-Normalisierung aus früheren Phasen).

**Entscheidung 5 — §29 "lokale TTS-API für andere Programme" wird NICHT
als zweiter Server/Port umgesetzt, sondern über dieselben Core-API-
Endpunkte:**

Von den vier im Auftrag vorgeschlagenen Schnittstellenformen (lokaler
HTTP-Endpunkt, REST API, CLI, Windows-TTS-Integration) deckt GENESIS
bereits zwei vollständig über die bestehende, Token-geschützte
127.0.0.1-only Core-API ab (ADR-0001/ADR-0006) - ein zweiter Server/Port
hätte nur unnötige Komplexität und ein zweites Angriffsflächen-/
Auth-System bedeutet, ohne einen echten Mehrwert zu bieten. Zur Demonstration
und als konkretes Test-Artefakt für "Andere lokale Anwendung → GENESIS
Voice API → Voice Engine → Audio" liegt `scripts/genesis_voice_cli.py`
bei - ein eigenständiges CLI-Skript, das GENESIS ausschließlich über HTTP
nutzt (kein Import von `genesis_core`), real gegen einen laufenden Server
getestet (siehe Konsequenzen). Das deckt zugleich den dritten
Interfacetyp ("CLI") kostengünstig mit ab.

Windows-SAPI5-Integration (vierter Interfacetyp) ist explizit
zurückgestellt (Backlog) - plattformspezifisch, in der Linux-Sandbox
weder baubar noch testbar, und kein Blocker für die Kernfunktionalität.

**Entscheidung 6 — Echtes Voice-Cloning aus Sprachproben ("Stimme
aufnehmen") ist zurückgestellt, `sample_path` bleibt rein informativ:**

§28 nennt "Stimme aufnehmen" und "Sprachproben verwalten" als Funktionen.
Piper ist eine Stimmen-Wiedergabe-Engine mit vortrainierten Modellen, KEIN
Voice-Cloning-System (es kann keine neue Stimme aus einer kurzen Aufnahme
lernen). Echtes Few-Shot-Voice-Cloning (z.B. Coqui XTTS v2) hätte eine
restriktive Lizenz (CPML, nicht eindeutig kommerziell nutzbar) und einen
deutlich höheren Ressourcenbedarf - beides passt nicht zum aktuellen
Projektstand (siehe Entscheidung 1). `VoiceProfile.sample_path`
existiert bereits als Datenbankfeld (aus der Phase-1-Grundstruktur) und
bleibt als rein informative/optionale Referenz-Sprachprobe erhalten (z.B.
zur späteren Zuordnung, falls ein Cloning-fähiger Plugin-Provider in einer
späteren Phase ergänzt wird) - wird aber von der aktuellen Piper-Engine
NICHT für die Synthese verwendet. Das Mikrofon-Aufnahme-UI selbst
(`QAudioInput`) ist ebenfalls zurückgestellt, da ohne einen
Cloning-fähigen Provider kein funktionaler Nutzen entstünde - der
Nutzer kann stattdessen über den vorhandenen Datei-Browser-Dialog eine
bereits existierende Aufnahme als Referenz hinterlegen.

**Konsequenzen:**

- Neue Tabelle `AIEmbedding`-analoge Struktur: `VoiceProfile` (erweitert
  um `model_path`/`language`/`description`, Cascade-Delete zu
  `VoiceSynthesis`) und neue Tabelle `VoiceSynthesis` (volle Historie
  jeder Sprachausgabe) in `db/models.py`.
- Neues `VoiceSettings` (`enabled=False` Standard, `provider`,
  `default_export_format`) in `config/__init__.py`, konsistent mit dem
  AISettings-Muster aus Phase 6 (§56: auch eine rein lokale Funktion ist
  standardmäßig AUS, bis der Nutzer sie bewusst aktiviert).
- Neues Modul `core/genesis_core/voice/` (`base.py` mit
  `TTSProvider`-Interface, `null_provider.py`, `piper_provider.py`,
  `catalog.py`, `engine.py` mit DB-bewussten CRUD-/Synthese-Funktionen
  analog zum `ai/music_provenance.py`-Muster aus Phase 6).
- `core/requirements.txt` um `piper-tts>=1.8,<2.0` ergänzt (mit
  Lizenzhinweis-Kommentar); `scripts/generate_license_report.py` um
  `piper-tts`/`onnxruntime`/`pathvalidate` ergänzt.
- Neues Hilfsskript `scripts/setup_voice_studio.sh` (analog zu
  `setup_ollama.sh`) lädt zwei kleine Testmodelle
  (`de_DE-thorsten-low`, `en_US-amy-low`, zusammen ~126 MB) nach
  `/opt/piper_voices` (bewusst außerhalb `/home/user`, siehe
  Ressourcen-Disziplin - persistiert NICHT sitzungsübergreifend, muss bei
  Bedarf erneut ausgeführt werden).
- 10 neue REST-Endpunkte: `GET /voice/status`, `GET /voice/engines`,
  `GET/POST /voice/profiles`, `GET/DELETE /voice/profiles/{id}`, `POST
  /voice/profiles/{id}/synthesize`, `POST /voice/profiles/{id}/test`,
  `GET /voice/syntheses`, `GET /voice/syntheses/{id}/audio` - Apply-
  Endpunkte mit `confirm`-Pflicht (422 sonst), Löschen zusätzlich mit
  `confirm_name`-Pflicht (403 bei Namens-Mismatch), protokolliert über
  `ProcessingJob`/`ProcessingHistory`.
- PySide6-UI: neue eigenständige Seite `VoiceStudioView` (zwei Tabs:
  "Profile" und "Text-zu-Sprache") ersetzt die bisherigen Platzhalter für
  BEIDE Nav-Einträge "Voice Studio" und "TTS" (beide zeigen bewusst
  dieselbe Seiteninstanz, da eine TTS-Funktion ohne Profilverwaltung
  wenig sinnvoll wäre - vermeidet doppelten Code). `api_client.py` um 9
  Voice-Methoden ergänzt (inkl. neuer `_delete()`-Hilfsmethode, dem
  ersten DELETE-Aufruf im gesamten Client).
- i18n: 63 neue `voice_studio.*`-Schlüssel in DE/EN/JA/RU ergänzt
  (exakte 1:1-Übereinstimmung mit den tatsächlich verwendeten
  `tr()`-Aufrufen geprüft).
- Tests: 20 neue Engine-Tests (`test_voice_engine.py`, deterministischer
  Stub-Provider), 6 neue ECHTE Piper-Tests (`test_voice_piper_provider.py`,
  automatisch übersprungen ohne lokale Testmodelle), 17 neue API-Tests
  (`test_api_voice.py`). Core-Gesamtsuite jetzt 385 passed/1 skipped
  (vorher 343 passed/1 skipped) - alle 43 neuen Tests grün.
- **Echter End-to-End-Test mit real installiertem Piper durchgeführt**
  (kein Mock): Core-API-Server mit `voice.enabled=true,
  provider=piper` gestartet, echtes deutsches Profil
  (`de_DE-thorsten-low`) angelegt, echte deutsche Sprachsynthese erzeugt
  (5.98s Audio aus 104 Zeichen Text), MP3-Export via bestehendem
  `convert/ffmpeg_convert.py`-Modul erfolgreich (122 KB, von `ffprobe`
  als valides MP3 mit 6.08s Dauer bestätigt), "Profil testen"-Endpunkt
  erfolgreich (2.99s Audio mit dem deutschen Testsatz). Zusätzlich
  `VoiceStudioView` DIREKT (reale HTTP-Aufrufe über `GenesisAPIClient`,
  kein Mock) gegen denselben laufenden Server getestet: Statusbanner,
  Engine-Katalog, Profilanlage mit allen Transparenzfeldern,
  Text-zu-Sprache-Synthese (3.7s MP3), Testsatz-Synthese (3.1s WAV),
  Verlaufsliste, sowie der komplette Lösch-Fluss (falscher
  Bestätigungsname blockiert lokal, korrekter Name löscht erfolgreich)
  - alle über die volle UI-Schicht verifiziert. Zusätzlich
  `scripts/genesis_voice_cli.py` als eigenständiger externer Konsument
  real gegen denselben Server getestet (fremdes Profil angelegt, Audio
  synthetisiert, als MP3 exportiert, von `ffprobe` als valide bestätigt)
  - belegt die §29-Architektur "Andere lokale Anwendung → GENESIS Voice
  API → Voice Engine → Audio" konkret und lauffähig. Alle Testserver
  sauber gestoppt, alle temporären Testverzeichnisse aufgeräumt.
- Bewusst zurückgestelltes Backlog (nicht Teil dieser Phase): echtes
  Voice-Cloning aus Sprachproben (Entscheidung 6), Mikrofon-Aufnahme-UI,
  Windows-SAPI5-Integration, projektweite Settings-UI zum Aktivieren von
  Voice Studio (aktuell nur über `config.yaml`, gleiches Backlog-Item wie
  bereits in ADR-0017 für KI vermerkt).

## ADR-0019: Download-/Import-Center (§30-§32) — swappable Provider, DRM-blockierte Dienste als korrekt gemeldete Nichtverfügbarkeit statt Umgehung, Wiederverwendung von Scanner/Fingerprint/Lautheit statt Doppelimplementierung, Speicherplatzprüfung als eigenständiges Modul

**Datum:** 2026-10-01 (Sitzung 10/Phase 8)

**Kontext:**

Der Originalauftrag verlangt in §30 ein separates Download-/Import-System
mit austauschbaren Providern (Beispiele: YouTube, TikTok, Spotify, Audible,
Pocket FM, direkte Medien-URLs, lokale Dateien). Zwei harte Grenzen sind
ausdrücklich genannt: Die Anwendung darf KEINE DRM-Schutzmechanismen
umgehen, und sie darf KEINE Zugangsdaten/Cookies unsicher speichern. Wenn
ein Dienst keinen zulässigen Download ermöglicht, muss die Anwendung dies
erkennen und entsprechend MELDEN (nicht einfach schweigen oder versuchen,
es doch irgendwie zu lösen). §31 definiert einen festen Workflow (URL
eingeben → Quelle erkennen → Provider auswählen → Verfügbarkeit prüfen →
Metadaten abrufen → Downloadoptionen anzeigen → Benutzer bestätigt →
Download → Datei analysieren → Metadaten ergänzen → Fingerprint → Lautheit
analysieren → Dateiname bestimmen → Bibliothek importieren). §32 verlangt
vollständige Quellenverwaltung (Source, Provider, Original-URL,
Original-ID, Importdatum, Importmethode) pro importierter Datei.

**Entscheidung 1 — Provider-Architektur analog zu Metadaten-/Voice-Providern,
mit einer harten dritten Kategorie "DRM-blockiert":**

Drei Arten von Providern werden unterschieden: (a) voll funktionsfähige
Provider ohne Einschränkung (`LocalFileProvider`, `DirectURLProvider`),
(b) funktionsfähige, aber auf öffentlich zugängliche Inhalte beschränkte
Provider über `yt-dlp` (YouTube, TikTok — siehe Entscheidung 2), und (c)
bewusst und dauerhaft BLOCKIERTE Provider (`DRMBlockedProvider` für
Spotify/Audible/Pocket FM, siehe `genesis_core/download/drm_blocked.py`),
die niemals einen Netzwerkaufruf tätigen (`requires_internet=False`) und
sofort mit einer erklärenden Begründung "nicht verfügbar" melden. Kategorie
(c) ist eine bewusste architektonische Entscheidung, keine fehlende
Funktion: Spotify liefert Musik ausschließlich DRM-verschlüsselt aus,
Audible verwendet das proprietäre AAX/AAXC-DRM-Format, Pocket FM bindet
Inhalte an die eigene App/Konto — ein "Download-Adapter" für diese Dienste
wäre zwangsläufig entweder eine DRM-Umgehung oder eine unsichere
Wiederverwendung gespeicherter Zugangsdaten/Sitzungscookies, beides durch
§30 ausdrücklich verboten. Diese Provider werden trotzdem als vollwertige,
registrierte Provider geführt (erkennen die URL, zeigen eine klare
Begründung), statt die URL einfach nicht zu erkennen — das macht das
Verhalten für Nutzer nachvollziehbar statt sie im Unklaren zu lassen, und
erfüllt wörtlich die §31-Anforderung "muss die Anwendung dies erkennen und
entsprechend melden".

**Entscheidung 2 — YouTube/TikTok über `yt-dlp` (Unlicense), nicht über
offizielle, aber stark eingeschränkte APIs:**

`yt-dlp` ruft ausschließlich Formate/Daten ab, die der jeweilige Dienst
einem gewöhnlichen, nicht angemeldeten Browser ohnehin ausliefert — keine
DRM-Entschlüsselung (z.B. Widevine), keine Zugangsdaten/Cookies. Ein
echter End-to-End-Test in dieser Sandbox (siehe Konsequenzen) hat gezeigt,
dass YouTube gelegentlich eine Bot-Prüfung auslöst ("Sign in to confirm
you're not a bot") — `yt-dlp` schlägt dann kontrolliert fehl, GENESIS
reicht dies unverändert als normale Nichtverfügbarkeit (403/`reason`)
weiter, OHNE auf die von `yt-dlp` vorgeschlagene Cookie-Umgehung
auszuweichen (das wäre genau die durch §30 verbotene unsichere
Zugangsdatenspeicherung). TikTok läuft über dieselbe generische
`YtDlpProvider`-Basisklasse und wird als "experimentell/best effort"
geführt (`is_experimental=True`), weil TikToks Erkennung/Blockaden sich
häufig ändern — ein Fehlschlag ist dort ein normales, erwartbares
Ergebnis, kein Bug.

**Entscheidung 3 — Downloads landen in einem eigenen Zwischenordner, nicht
automatisch in den konfigurierten `media_folders`:**

Analog zu `backup_dir`/`temp_dir`/`voice_output_dir` bekommt der Download-
Workflow einen eigenen Ordner (`paths.data_dir/downloads`, konfigurierbar
über `DownloadSettings.downloads_dir`). Importierte Dateien werden NICHT
automatisch in eine vom Nutzer bereits organisierte Bibliotheksstruktur
einsortiert — der Nutzer entscheidet selbst, ob/wie er sie dort einordnet.
Das vermeidet eine stillschweigende Vermischung mit bestehenden,
sorgfältig organisierten Ordnern (Prinzip #4/#5) und ist konsistent mit
der bereits etablierten Praxis für alle anderen GENESIS-eigenen
Ausgabeordner.

**Entscheidung 4 — "Datei analysieren"/"Fingerprint"/"Lautheit analysieren"
werden durch Wiederverwendung bestehender Phase-1/3-Module erledigt, nicht
neu implementiert; die automatische Dateinamens-Anwendung (§15) bleibt
explizit NICHT Teil des Imports:**

Nach einem erfolgreichen Download ruft die `DownloadEngine`
`genesis_core.scanner.scan_directories` (Phase 1), `compute_fingerprint`
(Phase 3/Chromaprint) und `measure_loudness` (Phase 3/ffmpeg loudnorm,
reine MESSUNG ohne Normalisierung) direkt auf, statt die technische
Analyse ein zweites Mal zu implementieren. Fingerprint und
Lautheitsmessung sind bewusst BEST EFFORT: ein fehlendes `fpcalc`/`ffmpeg`
lässt den Import NICHT fehlschlagen, sondern erzeugt nur eine Warnung im
Ergebnis (gleiches Muster wie die bestehenden, eigenständigen Fingerprint-/
Lautheits-Endpunkte). "Dateiname bestimmen" liefert nur einen bereits
dateisystemsicheren Namensvorschlag (`sanitize_filename_component`) im
Ergebnis zurück — die tatsächliche Umbenennung bleibt ein eigenständiger,
vom Nutzer über das bestehende Umbenennungs-Werkzeug (§15, mit Vorlagen-
Vorschau) bestätigter Schritt, statt eine zweite, konkurrierende
Umbenennungslogik im Download-Center zu erfinden.

**Entscheidung 5 — neues eigenständiges Modul `genesis_core.storage` für
Speicherplatzprüfungen vor großen Operationen:**

Der Originalauftrag verlangt allgemein, vor großen Operationen zu prüfen,
ob genügend Speicherplatz verfügbar ist — bisher aber nirgends konkret
umgesetzt. Ein Download ist der klassische Fall, bei dem die Zielgröße
vorab unsicher ist (Server-Angaben wie `Content-Length` können fehlen oder
falsch sein). `genesis_core/storage/__init__.py` stellt
`check_free_space`/`ensure_free_space` bereit (reine Prüfung vs.
`InsufficientStorageError`-werfende Variante, HTTP 507 "Insufficient
Storage" an der API-Grenze) und wird vor jedem Download/Import-Schreiben
aufgerufen. Backlog (siehe PROGRESS.md): weitere große Operationen
(Backups, Stapel-Konvertierung) sollten dieses Modul in einer späteren
Härtungsphase ebenfalls konsultieren.

**Konsequenzen:**

- Neues Modul `core/genesis_core/storage/` (`check_free_space`,
  `ensure_free_space`, `InsufficientStorageError`).
- Neues Modul `core/genesis_core/download/` mit `base.py`
  (`DownloadProvider`-Interface, `AvailabilityResult`, `SourceMetadata`,
  `DownloadOption`, `DownloadedFile`, `DownloadError`/
  `DownloadNotPermittedError`/`ConfirmationRequiredError`/
  `ProviderNotFoundError`), `local_file_provider.py`,
  `direct_url_provider.py`, `ytdlp_provider.py` (`YtDlpProvider`-Basis für
  YouTube/TikTok), `drm_blocked.py` (Spotify/Audible/Pocket FM),
  `registry.py` (`build_download_providers`/`detect_provider`) und
  `engine.py` (`DownloadEngine` mit `import_from_url`/`import_local_file`,
  orchestriert den vollständigen §31-Workflow inkl. Speicherplatzprüfung,
  Scan, Fingerprint, Lautheitsmessung, Quellenverwaltung, Job-Protokoll).
- Keine neuen DB-Tabellen nötig: `Source`/`Provider` aus Phase 1 passen
  exakt zu den §32-Feldern (`source_name`, `provider_name`,
  `original_url`, `original_id`, `imported_at`, `import_method`).
- Neues `DownloadSettings` (`enabled=False` Standard, §56) in
  `config/__init__.py`, inkl. `resolved_downloads_dir()` auf `Settings`.
- `core/requirements.txt` um `yt-dlp>=2026.8,<2027.0` ergänzt (Unlicense);
  `scripts/generate_license_report.py` entsprechend erweitert.
- 7 neue REST-Endpunkte: `GET /download/providers`, `POST
  /download/detect`, `POST /download/availability`, `POST
  /download/metadata`, `POST /download/options`, `POST /download/import`
  (confirm-Pflicht, 422 sonst; 403 bei DRM/Nichtverfügbarkeit; 507 bei
  Speicherplatzmangel), `POST /import/local-file` (gleiche Semantik), plus
  `GET /media/{id}/sources` (§32 Quellenabfrage).
- PySide6-UI: neue eigenständige Seite `DownloadCenterView` (Tabs
  "URL / Online-Quelle" und "Lokale Datei") ersetzt die bisherigen
  Platzhalter für BEIDE Nav-Einträge "Download Center" und "Import"
  (dieselbe Seiteninstanz, analog zum Voice-Studio/TTS-Muster aus Phase 7).
  `api_client.py` um 8 Download-Methoden ergänzt.
- i18n: 49 neue `download_center.*`-Schlüssel in DE/EN/JA/RU. Neuer
  projektweiter Regressionstest `test_all_languages_have_identical_key_sets`
  in `ui-reference-pyside/tests/test_i18n.py` ergänzt (prüft ab sofort bei
  JEDER künftigen Phase automatisch, dass alle vier Sprachdateien exakt
  dieselbe Schlüsselmenge haben — bisher nur manuell geprüft).
- Tests: 23 neue Engine-/Provider-Tests (`test_download_engine.py`,
  deterministischer Stub-Provider + echter `LocalFileProvider`-Dateisystem-
  Test + echte Speicherplatzprüfung), 11 neue API-Tests
  (`test_api_download.py`), 6 neue PySide6-UI-Tests
  (`test_download_center_view.py`, erster dedizierter View-Test im
  Projekt). Core-Suite 419 passed/1 skipped (vorher 385/1), UI-Suite 11
  passed (vorher 5).
- **Echte End-to-End-Tests mit echtem Internetzugriff durchgeführt** (kein
  Mock): (1) lokaler Datei-Import (Original unverändert, Kopie im
  Downloads-Ordner, Fingerprint+Lautheit erfolgreich), (2) echter
  Direkt-URL-Download einer 7,3-MB-MP3-Datei von GitHub (vollständiger
  §31-Workflow über HTTP, von `ffprobe` als valide bestätigt), (3) echter
  YouTube-Metadatenabruf über `yt-dlp` — bei einem zweiten Versuch löste
  YouTube eine Bot-Prüfung aus, die korrekt als Nichtverfügbarkeit (403)
  gemeldet wurde, OHNE auf die von yt-dlp vorgeschlagene Cookie-Umgehung
  auszuweichen (siehe Entscheidung 2) — ein unmittelbarer Praxisbeweis für
  korrektes Verhalten an der §30-Grenze, (4) echter TikTok-Download eines
  bekannten öffentlichen Testvideos (2 MB, 10,5s, von `ffprobe` bestätigt,
  inkl. Fingerprint/Lautheit), (5) Spotify/Audible/Pocket-FM-URLs korrekt
  und ohne jeden Netzwerkaufruf (`requires_internet=False`, Zeitmessung
  <20ms) als "nicht verfügbar: DRM-geschützt" gemeldet, (6) Import ohne
  `confirm=true` korrekt mit 422 abgelehnt. Alle Testserver sauber
  gestoppt, alle temporären Testverzeichnisse/Downloads aufgeräumt.
- Sandbox-Hinweis (kein Code-Fehler): Zu Beginn dieser Phase hatte die
  Sandbox erneut ihre nicht in `/home/user` persistierten Pakete verloren
  (uvicorn/PySide6/yt-dlp fehlten, Chromaprint/`fpcalc` fehlte) — durch
  `scripts/setup_python_env.sh` vollständig behoben. Die zuvor für Phase 7
  heruntergeladenen Piper-Testmodelle unter `/opt/piper_voices` sind
  dadurch ebenfalls wieder verschwunden (6 Tests in
  `test_voice_piper_provider.py` werden deshalb aktuell wieder
  übersprungen statt zu laufen) - kein Rückschritt im Code, nur ein
  bekanntes Sandbox-Persistenz-Verhalten (siehe bereits dokumentierte
  Einträge zu diesem Thema), bei Bedarf durch erneutes Ausführen von
  `scripts/setup_voice_studio.sh` behebbar.

---

## ADR-0020: Phase 9 Härtung (§34–§43) — fehlerisoliertes Plugin-System, kooperative Job-Steuerung, zentrales Fehler-Center mit Error-ID, lesende Diagnose, DB/Konfig-Backups ohne Mediendateien, geführtes Scan & Repair, automatisches Temp-Aufräumen, Multi-Format-Export, hash-basierte Pfad-Relokation

**Datum:** 2026-10-01 (Sitzung 11/Phase 9)

**Kontext:**

Phase 9 ("Hardening") bündelt neun Abschnitte des Originalauftrags, die
alle denselben Zweck verfolgen: die Anwendung robust, nachvollziehbar und
sicher gegenüber eigenen Fehlern, Plugins Dritter, Pfadverschiebungen und
Datenverlust zu machen, OHNE die zentrale Leitregel zu verletzen ("Datei
gefunden → automatisch verändern" ist verboten; jede Änderung braucht
Erkennen→Analysieren→Vorschlag→Confidence→Vorschau→Freigabe→Protokoll→
Rollback). Konkret: §34 Plugin-System, §35/§36 Job-Steuerung (Pause/
Resume/Cancel), §37 strukturierte Fehlerbehandlung, §38 Diagnose, §39
Scan & Repair, §40 Backup, §41 Temp-Aufräumung, §42 Export, §43
Pfad-Relokation — ergänzt um die zugehörige PySide6-Oberfläche
(Job-Warteschlange, Fehler-Center, Diagnose-, Backup- und Plugin-Ansicht)
und einen globalen UI-Fehlerdialog. Diese ADR dokumentiert die
Entscheidungen über alle neun Abschnitte hinweg gebündelt, weil sie in
derselben Sitzung entstanden sind und mehrfach aufeinander aufbauen (z.B.
nutzt Diagnose die Plugin-Registry, nutzt Scan & Repair den Job-Manager).

**Entscheidung 1 — Plugin-System: Python-Modul-Isolation statt echter
Prozess-/OS-Sandbox, aber mit lückenloser Fehlerisolierung beim Laden UND
beim Aufruf:**

Jedes Plugin liegt als eigenständiger Ordner mit `plugin.py` unter
`data_dir/plugins/<name>/`. Das Laden geschieht über
`importlib.util.spec_from_file_location` mit einem UUID-suffixierten,
garantiert eindeutigen Modulnamen (verhindert Kollisionen zwischen
gleichnamigen Plugin-Ordnern verschiedener Nutzer/Installationen), der
komplette Import+Instanziierung+Validierung läuft in einem einzigen
`try/except Exception`-Block, und das Modul wird in jedem Fall (auch bei
Erfolg) wieder aus `sys.modules` entfernt. Ein Plugin, das bereits beim
reinen Dateiimport eine Exception wirft (siehe `examples/broken_example/
plugin.py` — wirft absichtlich eine `RuntimeError`, der zentrale
Härtungsbeweis für §34), landet mit `load_error` in der Registry, OHNE die
übrigen Plugins am Laden zu hindern oder den Host-Prozess zum Absturz zu
bringen. Zusätzlich fängt `PluginRegistry.call_exporter()` auch Fehler ab,
die erst ZUR LAUFZEIT eines bereits erfolgreich geladenen Plugins
auftreten (z.B. eine Exception im eigentlichen `export()`-Aufruf) — Lade-
Sicherheit allein reicht nicht, ein Plugin kann auch später noch
"kaputtgehen". Eine ECHTE Betriebssystem-Sandbox (separater Prozess mit
eingeschränkten Rechten, z.B. über `multiprocessing` + Ressourcenlimits)
wäre robuster gegen böswillige statt nur fehlerhafte Plugins, wurde aber
für den aktuellen Funktionsumfang bewusst zurückgestellt (Backlog, siehe
Moduldocstring) — GENESIS lädt ausschließlich Plugins aus einem vom Nutzer
selbst befüllten lokalen Ordner (kein automatischer Download/keine
automatische Codeausführung von irgendwo sonst), das Bedrohungsmodell ist
also in erster Linie "eigene/Community-Plugins mit Programmierfehlern",
nicht "aktiv bösartiger Fremdcode". Von den zehn in §34 genannten
Plugin-Kategorien (metadata/fingerprint/downloader/tts/ai/artwork/db/
exporter/importer/converter) ist bislang nur `exporter` voll ausgearbeitet
— bewusst kleiner, gründlich getesteter Funktionsumfang statt zehn nur
oberflächlich angebundener Kategorien (dasselbe Vorgehen wie bereits bei
der Rename-Engine in Phase 2 dokumentiert).

**Nachtrag (Deep-Review-Sitzung 11) — Zeitlimit ergänzt, da Exceptions
allein nicht ausreichen:** Der ursprüngliche Beweis dieser Entscheidung
deckte nur Plugins ab, die beim Laden/Aufruf eine EXCEPTION werfen. Ein
Deep-Review-Pass hat empirisch nachgewiesen (siehe `docs/REVIEW_LOG.md`,
Sitzung 11), dass ein Plugin, das stattdessen HAENGT (Endlosschleife,
blockierender Aufruf ohne eigenes Timeout — ein klassischer, nicht
bösartiger Programmierfehler, also exakt im oben beschriebenen
Bedrohungsmodell), `discover_and_load()` und damit beim echten
Core-Service-Start den KOMPLETTEN Anwendungsstart unbegrenzt blockierte.
Fix: Laden und jeder Laufzeitaufruf eines Plugins laufen jetzt zusätzlich
mit einem Zeitlimit in einem Daemon-Thread (`_run_with_timeout` in
`genesis_core/plugins/__init__.py`) — nach Ablauf kehrt der Host sofort
mit einem klaren Fehler zurück und bleibt bedienbar/sauber beendbar. Der
gehängte Hintergrund-Thread selbst kann in Python nicht hart terminiert
werden und läuft im schlimmsten Fall bis zum Prozessende weiter — eine
bewusst unvollständige, aber ehrlich dokumentierte Verbesserung; die volle
Lösung (Prozess- statt Thread-Isolation mit hartem `terminate()`) bleibt
Teil des bereits oben benannten "echte OS-Sandbox"-Backlogs.

**Entscheidung 2 — Job-Steuerung ist kooperativ, nicht präemptiv:**

`JobManager.pause/resume/cancel` setzen lediglich den gewünschten
Zielstatus in der Datenbank; ein laufender Job prüft diesen Status
zwischen einzelnen Arbeitsschritten (`cooperative_checkpoint`) und reagiert
erst am nächsten sicheren Prüfpunkt. Ein hartes, sofortiges Abbrechen
mitten in einer Dateioperation (z.B. während ein Tag geschrieben wird)
würde dem Kernprinzip "Original darf nie in einem unbekannten/korrupten
Zustand zurückbleiben" widersprechen — ein kooperativer Checkpoint
garantiert, dass ein Abbruch immer zwischen zwei abgeschlossenen,
protokollierten Einzelschritten erfolgt. Die PySide6-"Job-Warteschlange"
(`job_queue_view.py`) macht diese Verzögerung transparent (Bestätigungstext
bei Abbruch erklärt ausdrücklich, dass bereits verarbeitete Elemente wie
protokolliert erhalten bleiben) statt eine sofortige Wirkung vorzutäuschen.

**Nachtrag (Deep-Review-Sitzung 11) — Statusübergänge jetzt serverseitig
validiert UND atomar:** Die ursprüngliche Fassung setzte den Zielstatus
unconditional (`resume()` z.B. ohne zu prüfen, ob der Job überhaupt
PAUSED war) und las/schrieb den aktuellen Status in zwei getrennten
DB-Sitzungen — eine Rennbedingung zwischen zwei nahezu gleichzeitigen
Anfragen auf denselben Job (z.B. "abbrechen" und "fortsetzen" kurz
hintereinander). Konkret konnte `resume()` einen bereits COMPLETED/
FAILED/CANCELLED-Job fälschlich wieder auf RUNNING zurücksetzen (ein
"Geister-Job", der im UI ewig "läuft", aber nie wieder Fortschritt macht).
Fix: `JobManager._transition()` prüft den erlaubten Herkunftsstatus und
schreibt den neuen Status jetzt ATOMAR (ein Prozess-Lock + eine einzige
DB-Transaktion) — ungültige Übergänge lösen `JobTransitionError` aus
(API-Schicht: HTTP 409), `cancel()` bleibt bewusst idempotent bei
bereits CANCELLED (siehe Docstring in `genesis_core/jobs/__init__.py`).

**Entscheidung 3 — Zentrales Fehlerformat mit dauerhafter Fehler-ID statt
nackter HTTP-Fehlercodes, konsequent bis in die UI durchgezogen:**

Ein globaler FastAPI-`exception_handler(Exception)` fängt JEDE sonst
unbehandelte Exception, protokolliert sie mit einer eindeutigen,
nachschlagbaren Fehler-ID (`ErrorLog`-Tabelle, §37) und liefert dem Client
`{error_id, timestamp, component, message, solution_hint}` statt einer
kontextlosen 500-Antwort. Erwartete Validierungsfehler (`HTTPException`
mit `detail`) durchlaufen diesen Handler bewusst NICHT — sie sind bereits
klar genug und brauchen keine Fehler-ID. Der PySide6-Client
(`api_client._build_api_error`) unterscheidet beide Formate und reicht
die Fehler-ID an `error_dialog.show_api_error()` weiter, die sie dem
Nutzer sichtbar macht ("im Fehler-Center nachschlagbar") — ein Nutzer kann
damit einen Vorfall exakt wiederfinden, ohne selbst Logdateien lesen zu
müssen. Ergänzend fängt `error_dialog.install_global_excepthook()` echte,
unerwartete Python-/Qt-Exceptions INNERHALB der Oberfläche selbst ab
(Programmierfehler beim Aufbau einer View o.ä.) und zeigt einen
verständlichen Dialog mit ausklappbaren technischen Details statt eines
kommentarlosen Einfrierens/Abstürzens. Bewusste Einschränkung: nur die in
dieser Sitzung neu entstandenen Ansichten (Job-Warteschlange,
Fehler-Center, Diagnose, Backups, Plugins) nutzen bereits konsequent
`show_api_error()`; ältere Ansichten (z.B. `rename_dialog.py`) behalten
ihre ursprünglichen, einfacheren `QMessageBox.critical(...)`-Aufrufe bei —
eine vollständige Umstellung aller bestehenden Aufrufstellen ist als
Backlog-Punkt vermerkt, siehe `error_dialog.py`-Moduldocstring.

**Entscheidung 4 — Diagnose ist rein lesend, Reparatur ausschließlich über
einen separaten, vorschaupflichtigen Workflow:**

`/diagnostics` prüft DB-Integrität, Dateisystem-Erreichbarkeit,
konfigurierte Provider (KI/TTS/Download) UND seit dieser Sitzung auch das
Plugin-System (ein fehlgeschlagenes Plugin erscheint als `warning`, nicht
als verstecktes `None`) — verändert dabei aber nichts. Eine tatsächliche
Reparatur erkannter Probleme (z.B. verwaiste DB-Einträge nach
Pfadverschiebung) läuft ausschließlich über den bereits in Gruppe A–E
dieser Phase etablierten "Scan & Repair"-Dreischritt (Plan → Vorschau →
Ausführen mit Bestätigung) — Diagnose und Reparatur bewusst getrennt
gehalten, damit ein reiner Gesundheitscheck niemals versehentlich etwas
verändern kann.

**Entscheidung 5 — Backups betreffen ausschließlich DB und Konfiguration,
niemals Mediendateien; Erstellen ist unkritisch, Wiederherstellen ist eine
bestätigungspflichtige, destruktive Änderung:**

Der Originalauftrag (§40/§6) verbietet ausdrücklich automatische
Vollsicherungen riesiger Medienbibliotheken (Speicherplatz, Redundanz zu
den Originaldateien selbst). `create_db_backup`/`create_config_backup`
legen nur eine versionierte Kopie der SQLite-Datei bzw. der
Konfigurationsdatei an — unkritisch, keine Bestätigung nötig.
`restore_db_backup` hingegen ERSETZT die aktive Datenbank und verlangt
zwingend `confirm=True` (sonst HTTP 403,
`BackupRestoreNotConfirmedError`) — konsistent mit der projektweiten
Regel "Löschen/Ersetzen = extra Bestätigung". Die PySide6-"Backups"-Ansicht
spiegelt das 1:1 (Erstellen-Buttons ohne Dialog, Wiederherstellen nur nach
`QMessageBox.question`).

**Entscheidung 6 — Export/Relokation als eigenständige, lesende/
analysierende Werkzeuge statt in bestehende Workflows gepresst (Gruppe
F+G, bereits in einem Vor-Commit dieser Sitzung umgesetzt, hier nur
nochmals eingeordnet):** `/export` (JSON/CSV/XML/M3U/M3U8) liest nur,
verändert nie Dateien. `/relocate/scan` schlägt anhand von Hash/
Fingerprint-Vergleich Kandidaten für verschobene/umbenannte Dateien vor
(Confidence-bewertet), `/relocate/apply` übernimmt NUR nach expliziter
Bestätigung pro Kandidat — exakt dasselbe Erkennen→Vorschlag→Bestätigen-
Muster wie überall sonst im Projekt, keine Sonderbehandlung nur weil es
sich "nur" um einen Pfad statt um Metadaten handelt.

**Konsequenzen:**

- Neue Module: `genesis_core/plugins/__init__.py` (+ zwei Beispiel-Plugins),
  `genesis_core/exporter/__init__.py`, `genesis_core/relocate/__init__.py`
  (Gruppe F+G), sowie die bereits in Gruppe A–E entstandenen
  `genesis_core/diagnostics/`, `genesis_core/backup/`, `genesis_core/
  repair/`, Fehlerprotokollierung in `genesis_core/api/app.py` und
  `genesis_core/jobs/__init__.py`-Erweiterungen um Pause/Resume/Cancel.
- Neue API-Endpunkte: `GET/POST /jobs*`, `GET /errors`, `POST /errors/
  {id}/resolve`, `GET /diagnostics`, `POST /backup/db`, `POST /backup/
  config`, `GET /backup`, `POST /backup/{id}/restore`, `GET/POST
  /repair/*`, `GET /export`, `POST /relocate/scan`, `POST /relocate/
  apply`, `GET /plugins`, `POST /plugins/reload`, `GET /plugins/export/
  {plugin_id}`.
- Neue PySide6-Ansichten: `job_queue_view.py`, `error_center_view.py`,
  `diagnostics_view.py`, `backups_view.py`, `plugins_view.py`, dazu
  `dialogs/error_dialog.py` (strukturierter API-Fehlerdialog +
  projektweiter `sys.excepthook`). Zwei neue Navigationseinträge
  ("Job-Warteschlange", "Fehler-Center") ergänzt, drei bisherige
  Platzhalter ("Plugins", "Backups", "Diagnose") auf echte Ansichten
  umgestellt.
- i18n: 52 neue Schlüssel (`job_queue_view.*`, `error_center_view.*`,
  `diagnostics_view.*`, `backups_view.*`, `plugins_view.*`,
  `error_dialog.*`, plus `nav.job_queue`/`nav.error_center`/
  `common.success_title`) in allen vier Sprachen DE/EN/JA/RU ergänzt —
  Schlüsselmengen-Paritätstest (`test_all_languages_have_identical_key_
  sets`) weiterhin grün (685 Schlüssel je Sprache, vorher 633).
- Tests: Core-Suite 503 passed/7 skipped (vorher 464/7 vor Phase-9-Beginn;
  17 neue Plugin-/API-Tests in dieser Teilsitzung, 22 weitere aus Gruppe
  A–G). UI-Suite 20 passed (vorher 11) — 9 neue Smoke-Tests für die fünf
  neuen Ansichten, Fake-API-Clients statt echtem Core Service, läuft unter
  `QT_QPA_PLATFORM=offscreen`.
- Ein einzelner Testlauf zeigte einen transienten Fehlschlag von
  `test_musicbrainz_live_search_then_lookup_round_trip` (echter
  Live-Netzwerktest gegen die öffentliche MusicBrainz-API, nicht mit
  Phase 9 verwandt) — in einem erneuten Lauf sowohl isoliert als auch in
  der Gesamtsuite wieder grün; dokumentiert als bekannte Flakiness externer
  Live-Tests, kein Code-Fehler.
- Offen (bewusst zurückgestellt, siehe PROGRESS.md): echte OS-Prozess-
  Sandbox für Plugins, die übrigen neun Plugin-Kategorien, vollständige
  Migration aller älteren UI-Aufrufstellen auf `show_api_error()`, Export/
  Relokation als eigene PySide6-Ansicht (bisher nur über die Core-API
  nutzbar), `.NET`/WPF-Client ohne jegliche Phase-9-Endpunkte.
