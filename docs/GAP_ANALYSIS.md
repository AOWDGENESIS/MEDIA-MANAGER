# Gap-Analyse — GENESIS Media Manager (nach Deep-Review Sitzung 13)

**Stand:** 2026-10-02, nach Abschluss des fehler-/warnungsfreien Deep-Review-
Durchlaufs (siehe `docs/REVIEW_LOG.md` Sitzung 13). Diese Analyse vergleicht
den aktuellen Implementierungsstand Punkt für Punkt gegen
`docs/ORIGINAL_SPEC_DE.md` (§1–§71) und benennt **nur belegte** Lücken
(verifiziert per Code-/API-Durchsicht, keine Vermutungen).

## Methode

Für jeden der 71 Abschnitte wurde geprüft, ob eine entsprechende
Backend-Fähigkeit (API-Endpunkt/DB-Modell/Engine-Modul) UND eine
entsprechende GUI-Anbindung existiert. Befunde unten sind nach
Schweregrad geordnet; jeder Punkt nennt die Belegstelle.

---

## 1. Bestätigt korrekt/vollständig umgesetzt (Auswahl, zur Einordnung)

Diese Punkte wurden geprüft und sind **keine Lücken** — hier nur als
Gegengewicht genannt, damit klar ist, dass die Architektur insgesamt trägt:

- DB-Modell deckt alle 28 in §7 geforderten Entitäten ab, inkl. `Person`/
  `PersonRole`/`PersonRoleType` für den optionalen Wissensgraphen (§63).
- DRM-Grenze (§30/§31) ist vorbildlich umgesetzt: Spotify/Audible/Pocket FM
  sind als `DRMBlockedProvider` **aktiv registriert** und melden dem Nutzer
  explizit "DRM-geschützt, kein Download möglich" statt die Quelle einfach
  zu ignorieren oder zu umgehen (`genesis_core/download/drm_blocked.py`).
- Export (§42) JSON/CSV/XML/M3U/M3U8 vollständig (`genesis_core/exporter`).
- Pfad-Relokation per Hash/Fingerprint (§43) vorhanden (`genesis_core/relocate`).
- Scan & Repair (§39, Plan→Vorschau→Ausführen) vollständig (`genesis_core/repair`).
- Job Queue (§35/§36) mit Pause/Resume/Cancel + Fortschritt vollständig.
- Sicherheitsmodell (§44), Fehlerbehandlung mit Error-ID (§37), KI-Kennzeichnungspflicht
  (§25/§27) sind durchgängig im Backend verankert und per Tests abgesichert.

## 2. Bestätigte Lücken

> **Update 2026-10-02 (Sitzung 14):** Nach ausdrücklicher Nutzerfreigabe
> ("mach es der reihe nach bis du fertig bist") wurde die unten in Abschnitt
> 4 empfohlene Reihenfolge sequenziell abgearbeitet. Der Status je Lücke ist
> jetzt direkt unter der jeweiligen Überschrift vermerkt; der ursprüngliche
> Befund-Text bleibt darunter unverändert als historisches Protokoll
> stehen. Details/Tests/Belege siehe `PROGRESS.md` (Abschnitte "Sitzung 14").

### A. [HOCH] Einstellungen sind nur lesbar — widerspricht §55 explizit

**Status: ✅ GESCHLOSSEN (Sitzung 14).** `PATCH /settings` existiert
(`core/genesis_core/api/app.py`, `update_settings_endpoint`, confirm-
pflichtig gemäß Prinzip #17) und die GUI-Seite `nav.settings` ist über
`ui-reference-pyside/genesis_ui/views/settings_view.py` real verdrahtet
(General/Medienordner/KI/Sprachausgabe/Lautheit/Download-Import/
Datenschutz), inkl. Speichern-Bestätigungsdialog und Neustart-Hinweis.
Dabei zusätzlich entdeckte und behobene Lücke: Der Client-Aufruf
`trigger_scan()` (Bibliotheksscan) war VOR dieser Sitzung über die
gesamte GUI gar nicht erreichbar — jetzt über den "Bibliothek jetzt
scannen"-Button auf der Settings-Seite verfügbar. Siehe
`tests/test_gap_closure_settings_providers_view.py` (UI) sowie die
bestehende Backend-Testabdeckung für `PATCH /settings`.

- **Beleg:** `core/genesis_core/api/app.py` — nur `GET /settings` existiert,
  kein `PATCH`/`PUT`. Docstring im Code selbst: *"Schreibzugriff ... ist Teil
  von Phase 9 (System/Einstellungen) und absichtlich noch nicht Teil dieses
  Endpunkts."* `Settings.save()` existiert bereits im Backend
  (`genesis_core/config/__init__.py`), ist aber nicht per API erreichbar.
  Die Settings-Navigationsseite in der UI ist ein reiner Platzhalter
  (`main_window.py`, `NAV_STRUCTURE`, `"nav.settings" → "placeholder"`).
- **Spec-Bezug:** §55 fordert ausdrücklich *"Keine manuelle Bearbeitung von
  Konfigurationsdateien voraussetzen"* — aktuell ist das aber faktisch der
  einzige Weg, Einstellungen zu ändern.
- **Aufwand:** mittel (Backend-Baustein existiert schon; v.a. API-Endpunkt +
  GUI-Formular nötig).

### B. [HOCH] Bibliotheks-Drill-down (Interpreten/Alben/Titel/Genres/Personen/Quellen) nur Platzhalter

**Status: ✅ GESCHLOSSEN (Sitzung 14).** Neues, rein lesendes Backend-Modul
`core/genesis_core/library.py` plus sechs Endpunktpaare unter `GET
/library/{artists,albums,tracks,genres,persons,sources}` (+ `/{id}`-Detail
für artists/albums/genres/persons). GUI-seitig löst EINE parametrisierte
`LibraryBrowserView` (`ui-reference-pyside/genesis_ui/views/library_view.py`)
alle sechs vormaligen Platzhalter ab (durchsuchbare Liste + Detailbereich,
analog zum bereits etablierten Master-Detail-Muster aus `backups_view.py`/
`media_table.py`). Dokumentierte, bewusst nicht behobene Modellgrenze:
`Track` hat keine direkte FK-Beziehung zu `Artist`, nur über
`Track.album_id -> Album.artist_id` (s. Docstring in `library.py`) — ein
Titel ohne Album taucht daher nicht unter seinem Interpreten auf (wohl aber
in der flachen Titelliste, wo `album_artist` als Freitext-Fallback dient).
Backend: 7 neue Tests (`tests/test_api_library.py`); UI: 9 neue Tests
(`tests/test_library_view.py`); zusätzlich end-to-end gegen einen echten,
befüllten Core-Service verifiziert (alle sechs Seiten + volle
`MainWindow`-Navigation, ausschließlich `200 OK`-Antworten im Server-Log).

- **Beleg (historisch, vor Schließung):** In `NAV_STRUCTURE` sind `nav.artists`, `nav.albums`,
  `nav.titles`, `nav.genres`, `nav.persons`, `nav.sources` alle auf
  `"placeholder"` gemappt. Nur `nav.search` (die flache Medientabelle) ist
  real. Die DB-Modelle und Relationen dafür existieren bereits vollständig
  (Artist→Album→Track, Person→PersonRole).
- **Spec-Bezug:** §62 (*"Klick auf Interpret zeigt alle Titel..."*) und der
  komplette "Bibliothek"-Navigationszweig aus §4 sind damit nur als
  Menüpunkt, nicht als Funktion vorhanden.
- **Aufwand:** mittel-hoch (mehrere neue Listen-/Drill-down-Views + je ein
  schlanker API-Endpunkt pro Entität, Backend-Daten sind aber schon da).

### C. [MITTEL-HOCH] Globale Suche deckt nur einen Bruchteil der geforderten Filter ab

**Status: ✅ GESCHLOSSEN (Sitzung 14, Fortsetzung 5).** `GET /media`
akzeptiert jetzt 19 zusätzliche optionale Query-Parameter; die eigentliche
Abfrage (inkl. aller Joins/Teilabfragen) lebt in
`genesis_core.library.build_media_search_statement`. `search` deckt jetzt
zusätzlich Interpret/Album/Genre/Autor/Sprecher/Serie/Quelle/Person ab
(nicht mehr nur Dateiname/Pfad); dedizierte Parameter decken Jahr, Genre,
Format, Dateigrößen-/Dauer-/Lautheits-Bereiche, Quelle, Person, Serie/
Staffel/Episode, KI-Status, Qualitätsverdacht, fehlende Metadaten,
fehlendes Cover und Duplikate ab. Neuer `SearchFiltersDialog`
(`ui-reference-pyside/genesis_ui/dialogs/search_filters_dialog.py`) bietet
dafür eine GUI, erreichbar über einen neuen "Filter …"-Button neben dem
bestehenden Suchschlitz in `media_table.py`.

- **Beleg (historisch, vor Schließung):** `GET /media` (`app.py`) filterte nur nach `kind` und einem
  Dateiname-/Pfad-Substring. Von den in §9 geforderten Suchfeldern
  (Interpret, Album, Genre, Autor, Sprecher, Regisseur, Schauspieler, Serie,
  Staffel, Episode, Quelle, Jahr, KI-Status) und Filtern (Format, Dateigröße,
  Dauer, Jahr, Genre, Lautheit, Qualität, Quelle, KI/Nicht-KI, fehlende
  Metadaten, fehlendes Cover, Duplikate) war **keines** per API ansteuerbar.
- **Umsetzung:** `genesis_core/library.py` (neu:
  `build_media_search_statement()`, `_person_match_subquery()`,
  `_series_match_subquery()` - Ein-zu-viele-Beziehungen bewusst als
  EXISTS-/IN-Unterabfragen statt JOIN, damit eine Datei mit z.B. drei
  Quellen nicht mehrfach in der Trefferliste erscheint),
  `genesis_core/api/app.py` (`GET /media` um die neuen Parameter erweitert),
  `ui-reference-pyside/genesis_ui/api_client.py` (`list_media(**filters)`
  reicht beliebige Filter durch), `ui-reference-pyside/genesis_ui/dialogs/
  search_filters_dialog.py` (neu), `media_table.py` ("Filter …"-Button +
  Statusanzeige "Filter aktiv (n)"). Tests: `core/tests/
  test_api_media_search.py` (19 Fälle, alle Filter einzeln und kombiniert
  gegen eine realistische Testbibliothek mit Musik/Hörbuch/Film/Episode/
  Duplikat), `ui-reference-pyside/tests/test_search_filters_dialog.py` (13
  Fälle) und `test_media_table_filters_integration.py` (4 Fälle).
- **Bekannte, bewusst nicht geschlossene Lücke:** keine eigene
  Rollen-Einschränkung beim Personenfilter (z.B. "nur als Regisseur", nicht
  "in irgendeiner Rolle") - §9 fordert das nicht explizit, wäre aber eine
  sinnvolle spätere Verfeinerung.

### D. [MITTEL] Cover/Artwork wird an keiner Stelle der UI tatsächlich angezeigt

**Status: ✅ GESCHLOSSEN (Sitzung 14).** Cover wird im Detail-Panel von
`media_table.py` über `/media/{id}/artwork` + `pixmap_from_artwork_bytes`
als `QLabel`/`QPixmap` gerendert (mit "kein Cover"-Platzhalter bei
fehlendem/nicht dekodierbarem Bild).

- **Beleg (historisch, vor Schließung):** `grep -rn "QPixmap\|setPixmap" ui-reference-pyside/` liefert
  **keinen einzigen Treffer** im gesamten Referenz-Client. Der
  `ArtworkDialog` kann Cover einbetten/extrahieren/ersetzen, aber nirgends
  wird das Bild selbst gerendert — weder im Detail-Panel noch im Dialog.
- **Spec-Bezug:** §8 und §59 listen "COVER" explizit als ersten Bestandteil
  der Detailansicht; §22 fordert ausdrücklich "Artwork anzeigen".
- **Aufwand:** gering-mittel (ein `QLabel`+`QPixmap` aus den bereits
  vorhandenen `/media/{id}/artwork`-Bytes, an zwei Stellen einbinden).

### E. [MITTEL] Keine "Datei öffnen"/"Ordner öffnen"/"Pfad kopieren"-Aktionen

**Status: ✅ GESCHLOSSEN (Sitzung 14).** `open_path_in_os()` (via
`QDesktopServices`) und `copy_path_to_clipboard()` in `media_table.py`,
verdrahtet an die Buttons "Datei öffnen"/"Ordner öffnen"/"Pfad kopieren"
im Detail-Panel.

- **Beleg (historisch, vor Schließung):** `grep -rln "QDesktopServices\|os.startfile"
  ui-reference-pyside/` → keine Treffer in der gesamten UI.
- **Spec-Bezug:** §8 (Detailansicht-Buttons) und §61 (globale
  Medienaktionen) fordern diese Aktionen ausdrücklich und wiederholt.
- **Aufwand:** gering (reine Client-Seite, `QDesktopServices.openUrl`/
  `QFileDialog`-Analog, kein Backend-Zugriff nötig, sogar ohne API-Aufruf
  möglich, da der volle Pfad dem Client schon vorliegt).

### F. [NIEDRIG-MITTEL] Loudness- und KI-Analyse-Daten fehlen im zentralen Detail-Panel

**Status: ✅ GESCHLOSSEN (Sitzung 14).** Detail-Panel in `media_table.py`
zeigt jetzt eigene LOUDNESS- (LUFS/True-Peak/LRA/normalisiert) und
KI-ANALYSE-Abschnitte (je Feld mit Modell/Confidence/Übernahme-Status),
analog zum bereits vorhandenen Qualitäts-Block.

- **Beleg (historisch, vor Schließung):** `MediaTableView._on_selection_changed`/Detail-Rendering zeigt
  Pfad, Technik, Qualitätsverdacht und Track-Metadaten — aber keine
  LUFS/True-Peak-Werte und keine KI-Metadaten-Felder (Modell/Confidence/
  Zeitstempel), obwohl beide APIs (`/media/{id}/loudness`,
  `/media/{id}/ai/metadata`) bereits existieren und in eigenen Dialogen
  genutzt werden.
- **Spec-Bezug:** §59 listet LOUDNESS und KI-ANALYSE als eigene Sektionen
  **innerhalb** der einen zentralen Detailansicht, nicht nur als separat zu
  öffnende Dialoge.
- **Aufwand:** gering (Daten/APIs existieren, nur zusätzliche Textblöcke im
  bereits vorhandenen Detail-Panel nötig, analog zum Qualitäts-Block).

### G. [MITTEL] Kein allgemeiner, eingebauter Medienplayer für die Bibliothek

**Status: ✅ GESCHLOSSEN (Sitzung 14, Fortsetzung 4).** Neue
wiederverwendbare `PlayerBarWidget`
(`ui-reference-pyside/genesis_ui/widgets/player_bar.py`) ist in
`MediaTableView` fest eingebettet (unterhalb des Splitters, immer
sichtbar statt eines Wegwerf-Dialogs) und bietet Play/Pause/Stopp,
Suchleiste (Seek), Lautstärkeregler, Zeitanzeige sowie ein optionales
Videofenster (nur für `movie`/`episode` eingeblendet) und eine sichtbare
Fehleranzeige statt stillem Fehlschlag. Neuer "Abspielen …"-Button in der
Aktionsleiste (aktiv bei genau einer Auswahl) ruft
`player_bar.load_and_play(absolute_path, filename, kind)` auf; ein Neuladen
der Trefferliste (`refresh()`) beendet laufende Wiedergabe bewusst, statt
sie unsichtbar im Hintergrund weiterlaufen zu lassen.

- **Beleg (historisch, vor Schließung):** Audio-Wiedergabe existierte nur eng
  gekoppelt im Cutter (Schnitt-Vorschau) und im Voice Studio
  (TTS-Testwiedergabe). Es gab keine Play/Pause/Stop/Seek/Lautstärke-
  Komponente, die beliebige Bibliotheksmedien direkt abspielt.
- **Spec-Bezug:** §60 fordert explizit einen "einfachen lokalen Player" für
  die Bibliothek (nicht nur für Werkzeug-Vorschauen) — erfüllt mit
  Play/Pause/Stopp/Seek/Lautstärke; Playlist/AB-Wiedergabe bleiben bewusst
  als mögliche spätere Ausbaustufe offen (vom Spec-Text nicht gefordert).
- **Umsetzung:** `genesis_ui/widgets/player_bar.py` (neu, `QMediaPlayer`+
  `QAudioOutput`+optionales `QVideoWidget`, reine Wiedergabe ohne jede
  Dateiveränderung, Prinzip #4/#5), `genesis_ui/views/media_table.py`
  (Einbettung + "Abspielen …"-Button + Enablement-Regel +
  Stop-bei-Refresh), `i18n/{de,en,ja,ru}.json` (`player_bar.*` +
  `media_table.play_button`), Tests in `tests/test_player_bar.py` (12
  Fälle: Zeitformatierung, Zustandsübergänge, Lautstärke-Mapping,
  Fehleranzeige, Video-Sichtbarkeit je Medienart) und
  `tests/test_media_table_player_integration.py` (6 Fälle: Einbettung,
  Mehrfachauswahl-Regel, korrekte Pfad-/Titel-/Art-Übergabe, No-Op ohne
  Auswahl, Stop-bei-Refresh). Tatsächliche Tonausgabe ist in der
  Linux-Sandbox ohne Audiogerät nicht hörbar prüfbar — getestet wird die
  vollständige Verdrahtung (wie bereits bei Cutter/Voice-Studio-Vorschau).

### H. [NIEDRIG] Globale Aktionen als Toolbar statt Kontextmenü; einzelne Aktionen fehlen ganz

**Teilweise geschlossen (Sitzung 14):** Alle zuvor fehlenden Einzel-
Aktionen sind jetzt vorhanden — "Abspielen …" (Gap G, Fortsetzung 4),
"Datei öffnen"/"Ordner öffnen"/"Pfad kopieren" (Gap E) sowie "In
Bibliothek anzeigen" (Gap B). Offen bleibt nur noch der rein strukturelle
Punkt: diese Aktionen stehen weiterhin als Werkzeugleisten-Buttons statt
als Rechtsklick-Kontextmenü, wie im Spec-Text angegeben.

**Status: ✅ VOLLSTÄNDIG GESCHLOSSEN (Sitzung 14, Fortsetzung 6).**
`media_table.py` hat jetzt zusätzlich zur bestehenden Werkzeugleiste ein
Rechtsklick-Kontextmenü auf der Tabelle (`QTableWidget.
customContextMenuRequested`) mit genau den 15 selben Aktionen wie die
Toolbar (identische `_on_..._clicked`-Handler, keine Zweitimplementierung).
Rechtsklick auf eine noch nicht ausgewählte Zeile wählt zunächst nur diese
aus (übliches Dateimanager-Verhalten); Rechtsklick innerhalb einer
bestehenden Mehrfachauswahl lässt diese unangetastet, damit
Sammelaktionen weiter über die gesamte Auswahl wirken. Die Toolbar bleibt
bewusst zusätzlich bestehen (schnellerer Zugriff ohne Rechtsklick,
zusätzlich kein Verlust für bestehende, bereits gegen die Toolbar-Buttons
geschriebene Tests).

- **Beleg (historisch, vor Schließung):** Die in §61 geforderten Aktionen waren in
  `media_table.py` nur als Werkzeugleisten-Buttons (abhängig von der Auswahl)
  umgesetzt — funktional vollständig vorhanden, aber nicht als Rechtsklick-
  Kontextmenü.
- **Umsetzung:** `media_table.py::_on_table_context_menu()` (Zeilen-
  Auswahllogik) + `_build_context_menu()` (reine Menü-Aufbau-Funktion,
  bewusst von `QMenu.exec()` getrennt, damit Tests den Menüinhalt prüfen
  können, ohne den blockierenden modalen Aufruf auszulösen). Tests:
  `tests/test_media_table_context_menu.py` (7 Fälle - Anzahl/Beschriftung/
  Aktivierungszustand der Einträge, Verhalten ohne Auswahl, kind-abhängige
  Aktivierung, Zeilen-Auswahllogik bei Einzel-/Mehrfachauswahl, Klick auf
  einen Menüeintrag ruft denselben Handler wie der Button).

### I. [MITTEL] Keine Verwaltung der Metadaten-Provider über GUI/API

**Status: ✅ GESCHLOSSEN (Sitzung 14).** Neue GUI-Seite `nav.providers`
(`ui-reference-pyside/genesis_ui/views/providers_view.py`) verwaltet
MusicBrainz/AcoustID/Cover Art Archive (Aktivierung, AcoustID-API-Schlüssel,
Kontakt-E-Mail, Zeitlimit, Mindest-Konfidenz) über dasselbe `PATCH
/settings` wie Gap A, beschränkt auf den `"metadata"`-Teilbaum. Getrennt
von den bereits bestehenden Download-Providern (`GET /download/providers`).

- **Beleg (historisch, vor Schließung):** `GET /download/providers` existiert nur für Download-Adapter.
  Für Metadaten-Provider (MusicBrainz/AcoustID/Cover Art Archive) gibt es
  weder einen API-Endpunkt noch eine GUI-Seite (`nav.providers` ist
  Platzhalter), obwohl `build_providers(settings.metadata)` im Backend
  bereits austauschbar und konfigurierbar implementiert ist.
- **Spec-Bezug:** §10 ("Provider sollen austauschbar sein") und §55
  (Provider gehört zur Liste der GUI-konfigurierbaren Einstellungen).
- **Aufwand:** gering-mittel (hängt mit Gap A zusammen — am saubersten im
  selben "Settings/Provider"-Zug lösen).

### J. [NIEDRIG-MITTEL] Kein Log-Viewer in der GUI

**Status: ✅ GESCHLOSSEN (Sitzung 14, Fortsetzung 6).** Neuer, rein
lesender `GET /logs`-Endpunkt (gefiltert nach Mindest-Level/Komponente/
Freitext, paginiert, neueste Einträge zuerst) sowie eine echte
`LogViewerView`-Seite unter `nav.logs` (löst die bisherige
`nav.logs_detail`-Platzhalterseite ab).

- **Beleg (historisch, vor Schließung):** Strukturiertes Datei-Logging (TRACE…CRITICAL, §54) war
  implementiert (`genesis_core/logutil`), aber es gab weder einen
  `/logs`-API-Endpunkt noch eine echte `nav.logs`-Seite (Platzhalter).
- **Umsetzung:** `genesis_core/logutil/reader.py` (neu -
  `read_log_entries()`: parst die vom bestehenden `StructuredFormatter`
  erzeugten Logzeilen inkl. rotierter Backup-Dateien, gruppiert
  kopflose Folgezeilen [z.B. Exception-Tracebacks] korrekt als
  Fortsetzung des vorangehenden Eintrags statt sie als eigene,
  unvollständige Zeilen zu behandeln), `GET /logs` in `api/app.py`,
  `ui-reference-pyside/genesis_ui/views/log_viewer_view.py` (neu -
  Filterleiste, Tabelle, Detailbereich für mehrzeilige Meldungen,
  Seitenweise Blättern), `api_client.py::get_logs()`. Tests:
  `core/tests/test_logutil_reader.py` (10 Fälle), `core/tests/
  test_api_logs.py` (6 Fälle, gegen einen echten Scan-Lauf statt
  künstlicher Logzeilen) und `tests/test_log_viewer_view.py` (8 Fälle).

### K. [MITTEL, bereits bekannt] .NET/WPF-Client hinkt der Python-Referenz-UI hinterher

- **Beleg:** Bereits in `docs/REVIEW_LOG.md` (Sitzung 11/12/13) als
  offener Punkt dokumentiert — nicht neu, hier nur zur Vollständigkeit
  erneut gelistet, da auch dies eine Spec-Abweichung ist (Original-Auftrag
  des Nutzers verlangte explizit BEIDE Clients gleichwertig).

**Status: 🟡 LAUFEND, INKREMENTELL (Sitzung 14, Fortsetzung 7) — bewusst
NICHT als geschlossen markiert.** Dies ist der einzige Punkt dieser Liste,
der NICHT in einer Sitzung vollständig geschlossen werden kann: der
Umfangsunterschied ist massiv (.NET-Client vorher ein ~825-Zeilen-Grundgerüst
mit genau EINER echten Seite [Dashboard, nur Lesezugriff] gegenüber der
Python-Referenz-UI mit ~20 Ansichten/~15 Dialogen). Der Nutzer wurde dazu
explizit befragt (siehe `PROGRESS.md`/Session-Memory) und hat sich für
**"inkrementell"** entschieden: schrittweise die wichtigsten Ansichten
nachziehen, über mehrere Sitzungen hinweg, statt eines einzigen
Kraftakts. Diese Sitzung lieferte den ersten Schritt:

- Neue **Medientabellen-Ansicht** (`MainWindow.xaml.cs::ShowMediaTableAsync`
  + ausgelagerte, WPF-freie Hilfslogik `MediaTableSupport.cs`) — deckt
  dieselbe `GET /media` + `GET /media/{id}`-API ab wie
  `ui-reference-pyside/genesis_ui/views/media_table.py`: Freitextsuche,
  sortierbare Tabelle (Titel/Art/Format/Größe/Pfad), Detailpanel bei
  Auswahl (Pfad, Existenz auf Datenträger, Technik-Metadaten,
  Track-Metadaten, eingebettetes Artwork — dieselben i18n-Schlüssel
  `media_table.*`/`media_table.detail.*` wie die Python-UI, keine
  Doppelpflege der Texte). Verdrahtet für alle sieben Medienarten-
  Navigationspunkte (`nav.music`, `nav.audiobook`, `nav.movie`,
  `nav.episode`, `nav.podcast`, `nav.ai_music`, `nav.unknown`) sowie
  `nav.search` (ungefilterte Suche über alle Arten) — 1:1 dieselbe
  Zuordnung wie `NAV_STRUCTURE` in `main_window.py` (Python).
- **Bewusst NICHT** enthalten in diesem ersten Schritt (vorgemerkt für
  eine Folgesitzung): Qualitätsprüfung/Loudness/KI-Analyse/Quellen-
  Abschnitt im Detailpanel (benötigen zusätzliche, in
  `GenesisApiClient.cs` noch fehlende Endpunkt-Methoden/DTOs),
  Kontextmenü, Mehrfachauswahl-Aktionen (Umbenennen/Metadaten-Vorschläge/
  Artwork — die zugehörigen API-Client-Methoden existieren in
  `GenesisApiClient.cs` bereits, sind aber noch an keiner UI-Stelle
  verdrahtet), erweiterte Filter (Pendant zu `SearchFiltersDialog`),
  eingebetteter Player, Settings-Ansicht, Log-Viewer, Bibliotheks-
  Drill-down-Ansichten.
- Tests: neue, WPF-unabhängige `MediaTableSupportTests.cs`
  (14 Fälle: Nav-Key→Art-Zuordnung, Detailtext-Aufbau für
  verschiedene `MediaDetail`-Kombinationen) nach demselben Muster wie
  die bereits bestehenden `TranslatorTests.cs` (Quelldatei ohne
  WPF-Abhängigkeit, per `<Compile Include>` in beide Projekte verlinkt,
  damit das reine `net8.0`-Testprojekt ohne Windows-Targeting-Pack
  lauffähig bleibt). `dotnet test`: **25/25 bestanden** (vorher 11).
  `dotnet build -p:EnableWindowsTargeting=true` für den WPF-Client
  selbst: 0 Warnungen/0 Fehler.
**Zweiter Schritt (Sitzung 14, Fortsetzung 8) — Einstellungen-Ansicht:**

- Neue **Einstellungen-Ansicht** (`MainWindow.xaml.cs::ShowSettingsAsync`
  + ausgelagerte, WPF-freie Hilfslogik `SettingsViewSupport.cs`) ersetzt
  den bisherigen `nav.settings`-Platzhalter: deckt vier der sieben
  Abschnitte von `ui-reference-pyside/genesis_ui/views/settings_view.py`
  ab (Allgemein/KI/Lautheit/Datenschutz), inkl. Lesen via `GET /settings`
  UND Schreiben via neu ergänztes `GenesisApiClient.cs::
  UpdateSettingsAsync()` (`PATCH /settings`). Dieselbe
  Bestätigungslogik wie die Python-Referenz-UI: ein `MessageBox.
  Show(...)`-Ja/Nein-Dialog VOR dem Senden, `confirm: true` wird erst nach
  expliziter Zusage gesetzt (Prinzip #17, §44) — kein automatisches
  Übernehmen. Erfolgreiches Speichern aktualisiert sofort die
  UI-Sprache, falls geändert (`Translator.ConfigureDefaultLanguage`).
  Nutzt dieselben `settings_view.*`-i18n-Schlüssel wie die Python-UI.
- `GenesisApiClient.cs` dafür erweitert: `GeneralSettings` um
  `SafeTestMode`/`RequireConfirmationForBulkChanges`, neue DTOs
  `AiSettingsInfo`/`LoudnessSettingsInfo`/`PrivacySettingsInfo`,
  `SettingsResponse` entsprechend erweitert, neue
  `SettingsUpdateRequest`/`SettingsUpdateResult`-Records,
  `UpdateSettingsAsync()` nutzt `HttpClient.PatchAsJsonAsync` (seit .NET 5
  Teil von `System.Net.Http.Json`, verifiziert durch erfolgreichen Build).
  WICHTIG dokumentiert: die PATCH-Payload wird bewusst als
  `Dictionary<string, object>` mit EXPLIZITEN snake_case-Schlüsseln gebaut
  (nicht über reflektierte Records), weil `JsonNamingPolicy` nur auf echte
  Record-/Klassen-Properties wirkt, NICHT auf Dictionary-Schlüssel — ein
  stiller Namensfehler hier hätte am Core Service zu ignorierten Feldern
  geführt (Verstoß gegen Prinzip "kein stiller Fehlschlag").
- **Bewusst NICHT** enthalten in diesem zweiten Schritt (vorgemerkt für
  eine Folgesitzung): Medienordner-Liste (braucht Ordner-Auswahldialog +
  "Jetzt scannen"-Button), Sprachausgabe/Voice-Studio-Abschnitt,
  Download-/Import-Center-Abschnitt (braucht ebenfalls einen
  Ordner-Auswahldialog) — alle drei sind in der Python-Referenz-UI
  vorhanden, aber für dieses Inkrement bewusst zurückgestellt, da sie
  zusätzliche Dialogkomponenten (Ordnerauswahl) benötigen, die noch nicht
  existieren.
- Tests: neue, WPF-unabhängige `SettingsViewSupportTests.cs` (3 Fälle:
  vollständige Übernahme aller abgedeckten Felder aus `SettingsResponse`,
  exakte snake_case-Schlüssel in der PATCH-Payload, Payload spiegelt
  geänderte Werte korrekt wider). `dotnet test`: **28/28 bestanden**
  (vorher 25). `dotnet build -p:EnableWindowsTargeting=true`: weiterhin
  0 Warnungen/0 Fehler.

**Nächste Schritte (Folgesitzung(en)):** Medienordner-Verwaltung +
Ordner-Auswahldialog (gemeinsame Grundlage für Settings-Medienordner UND
Download-Center), danach schrittweise weitere Werkzeuge/Dialoge je nach
Priorität der verbleibenden Python-Ansichten. Dieser Punkt bleibt bis zur
vollständigen Parität als "laufend" markiert, nicht als "geschlossen".

**Dritter Schritt (Sitzung 14, Fortsetzung 9) — Einstellungen-Ansicht
vervollständigt (jetzt 7/7 Abschnitte, volle Parität zur Python-UI):**

- Die drei in Fortsetzung 8 zurückgestellten Abschnitte wurden ergänzt:
  **Medienordner** (Liste + "Hinzufügen …"/"Entfernen"/"Jetzt scannen"
  via bereits bestehendem `TriggerScanAsync()`), **Sprachausgabe/Voice
  Studio** (Aktiviert/Provider/Standard-Exportformat — nur drei triviale
  Felder) und **Download-/Import-Center** (Aktiviert/YouTube/TikTok/
  Zielordner mit Durchsuchen-Button/max. Downloadgröße/Mindest-Freispeicher/
  Zeitlimit). Die Einstellungen-Ansicht des .NET-Clients deckt damit JEDEN
  der sieben Abschnitte aus
  `ui-reference-pyside/genesis_ui/views/settings_view.py` ab — innerhalb
  des Settings-Bereichs besteht nun vollständige funktionale Parität.
- Ordnerauswahl für "Medienordner hinzufügen" und "Download-Zielordner
  durchsuchen" nutzt `Microsoft.Win32.OpenFolderDialog` — seit .NET 8 Teil
  von WPF selbst, KEIN zusätzlicher `System.Windows.Forms`-Verweis nötig
  (durch erfolgreichen `dotnet build -p:EnableWindowsTargeting=true`
  verifiziert, dass der Typ in den Windows-Referenzassemblies vorhanden
  ist — kann in der Linux-Sandbox naturgemäß nicht interaktiv
  ausgeführt/visuell geprüft werden, siehe `README.md`).
- "Jetzt scannen" verwendet exakt die aktuell in der Liste sichtbaren
  Ordner (unabhängig davon, ob sie bereits gespeichert wurden) — identisch
  zum Verhalten/Kommentar in `settings_view.py::_on_scan_clicked`
  (Prinzip #4/#5: rein lesende Analyse, keine Mediendatei wird verändert).
  Rückgabe von `POST /scan` wird als `JsonElement` ausgelesen
  (`result.files_found`), da `ScanResponse.Result` bewusst als `object`
  typisiert ist (siehe bestehender Code-Kommentar dort).
- `GenesisApiClient.cs` erneut erweitert: `SettingsResponse` um `Paths`
  (`PathsSettingsInfo.MediaFolders`), `Voice` (`VoiceSettingsInfo`) und
  `Download` (`DownloadSettingsInfo`) ergänzt.
- `SettingsViewSupport.cs` erweitert: `SettingsFormValues` und
  `BuildUpdatePayload()`/`FromSettingsResponse()` decken jetzt alle sieben
  Abschnitte ab; neue, WPF-freie `AddFolderIfMissing()`-Hilfsfunktion
  (keine Duplikate in der reinen Merkliste, identisch zu
  `settings_view.py::_on_add_folder_clicked`) — rein listenverwaltend,
  keine Dateisystem-Nebenwirkung, daher gut isoliert testbar.
  Leerstring im Downloadordner-Feld wird beim Senden zu `null`
  (=> Core-Default), identisch zu `self.download_dir_edit.text() or None`
  in der Python-Referenz-UI.
- Tests: `SettingsViewSupportTests.cs` um 4 Fälle erweitert (Übernahme der
  Medienordner-/Voice-/Download-Felder, Leerstring→`null`-Umwandlung für
  den Downloadordner, `AddFolderIfMissing` dedupliziert und mutiert die
  Eingabeliste nicht). `dotnet test`: **32/32 bestanden** (vorher 28).
  `dotnet build -p:EnableWindowsTargeting=true`: weiterhin 0 Warnungen/
  0 Fehler.
- **Weiterhin NICHT Teil der Einstellungen-Ansicht** (unverändert
  gegenüber Python, keine neue Lücke): Metadaten-Provider-Einstellungen
  leben bewusst auf der separaten `nav.providers`-Seite (Gap I), nicht im
  Settings-Formular selbst — für den .NET-Client noch offen (siehe
  "Nächste Schritte" unten).

**Nächste Schritte:** Metadaten-Provider-Verwaltung (Pendant zu Gap I,
eigene Seite `nav.providers`) oder die Medientabellen-Detailpanel-
Erweiterungen aus Schritt 1 (Qualität/Loudness/KI/Quellen) — Priorität in
einer künftigen Sitzung neu zu bewerten. Dieser Punkt bleibt weiterhin als
"laufend/inkrementell" markiert: die Einstellungen-Ansicht hat volle
Parität erreicht, aber Gap K als Ganzes (alle ~20 Python-Ansichten) ist
das noch nicht.

**Vierter Schritt (Sitzung 14, Fortsetzung 10) — Medientabellen-
Detailpanel vervollständigt (Qualität/Loudness/KI/Quelle):**

- Die in Schritt 1 (Fortsetzung 7) bewusst zurückgestellten vier
  Detailpanel-Abschnitte wurden ergänzt — das Detailpanel der .NET-
  Medientabellen-Ansicht deckt jetzt GENAU dieselben Informationen ab wie
  `ui-reference-pyside/genesis_ui/views/media_table.py::
  _on_selection_changed`, inkl. identischer Reihenfolge (Pfad → Technik →
  **Qualität** → Track-Metadaten → eingebettetes Artwork → **Loudness** →
  **KI-Analyse** → **Quelle**) und identischem Sonderverhalten: der
  Qualitäts-Abschnitt (inkl. Kopfzeile) entfällt komplett, wenn noch keine
  Analyse vorliegt, während Loudness/KI/Quelle immer eine Kopfzeile mit
  explizitem "noch nicht vorhanden"-Text zeigen.
- `GenesisApiClient.cs` um vier neue, rein lesende Methoden erweitert:
  `GetQualityAsync` (`GET /media/{id}/quality`, liefert bewusst `null` bei
  "noch nicht analysiert" — die Core-API antwortet dafür mit JSON `null`
  und Status 200, kein 404, da das kein Fehlerfall ist), `ListLoudnessAsync`
  (`GET /media/{id}/loudness`, volle Historie neueste zuerst),
  `GetAiMetadataAsync` (`GET /media/{id}/ai/metadata`, immer mit Modell/
  Version/Confidence/Übernahme-Status, nie ohne diese Herkunft — §25/
  Prinzip #9), `ListMediaSourcesAsync` (`GET /media/{id}/sources`,
  entpackt das servierseitige `{"sources": [...]}`-Wrapper-Objekt). Neue
  DTOs `QualityInfo`, `LoudnessEntry`, `AiMetadataEntry`,
  `MediaSourceEntry`/`MediaSourcesResponse` spiegeln exakt die
  `*_to_dict()`-Funktionen in `core/genesis_core/api/app.py`.
- `MediaTableSupport.BuildMediaDetailText()` um vier optionale Parameter
  erweitert (`quality`, `loudnessHistory`, `aiEntries`, `sources`, alle
  mit Default `null`) — bestehende Aufrufer/Tests, die nur den
  Basis-Detailtext brauchen, bleiben unverändert funktionsfähig
  (Abwärtskompatibilität durch optionale Parameter statt einer
  brechenden Signaturänderung).
- `MainWindow.xaml.cs`: die Selektionsänderung der Medientabelle ruft jetzt
  zusätzlich alle vier neuen Endpunkte ab — JEDER einzeln in ein eigenes
  `try`/`catch` gefasst (identisch zum Python-Muster "ein nicht
  erreichbarer Zusatz-Endpunkt darf die restliche Detailansicht nicht
  verhindern"), fällt bei Fehlschlag auf `null`/eine leere Liste zurück,
  statt die gesamte Detailansicht scheitern zu lassen.
- Tests: `MediaTableSupportTests.cs` um 8 Fälle erweitert (Qualitäts-
  Abschnitt entfällt komplett ohne Analyse / zeigt Flags+Notizen bei
  vorhandener Analyse, Loudness zeigt "none"-Fallback / den neuesten
  Eintrag zuerst, KI-Analyse zeigt "none"-Fallback / Modell+Confidence+
  Wert, Quelle zeigt "none"-Fallback / Provider+Importzeitstempel).
  `dotnet test`: **40/40 bestanden** (vorher 32). `dotnet build
  -p:EnableWindowsTargeting=true`: weiterhin 0 Warnungen/0 Fehler.
- Damit sind **sowohl die Medientabellen-Ansicht als auch die
  Einstellungen-Ansicht** des .NET-Clients auf vollem fachlichem
  Funktionsumfang der jeweiligen Python-Pendants (abzüglich rein
  struktureller/kosmetischer Unterschiede wie Kontextmenü statt
  Toolbar-Mehrfachauswahl, Cover-Bildanzeige, Filter-Dialog — diese bleiben
  für eine künftige Sitzung vorgemerkt).

**Nächste Schritte:** Metadaten-Provider-Verwaltung (Pendant zu Gap I,
eigene `nav.providers`-Seite) ODER eine der beiden verbliebenen
Medientabellen-Verfeinerungen (Cover-Anzeige, Filter-Dialog) ODER eine
gänzlich neue Ansicht (z.B. Bibliotheks-Drill-down, Pendant zu Gap B) —
Priorität in einer künftigen Sitzung neu zu bewerten, gemäß stehender
"inkrementell"-Freigabe.

**Fünfter Schritt (Sitzung 14, Fortsetzung 11) — Metadaten-Provider-Seite
(`nav.providers`, Pendant zu Gap I):**

- Neue eigenständige Ansicht `ShowProvidersAsync` in `MainWindow.xaml.cs`,
  1:1 nachgebildet nach
  `ui-reference-pyside/genesis_ui/views/providers_view.py::ProvidersView`.
  Betrifft AUSSCHLIESSLICH die ONLINE-Metadatenabgleich-Provider
  (MusicBrainz, AcoustID, Cover Art Archive) — nicht zu verwechseln mit den
  Download-/Import-Providern (YouTube/TikTok/…), deren Verwaltung bereits
  über die Einstellungen-Ansicht (Download-Abschnitt) existiert. Nutzt
  denselben `PATCH /settings`-Endpunkt wie die Einstellungen-Ansicht,
  schreibt aber ausschließlich in den `metadata`-Abschnitt.
- Drei Gruppen wie im Original: "Online-Abgleich" (Checkbox + Hinweistext,
  dass der komplette Online-Abgleich standardmäßig AUS ist, §56 "kein
  Internetzwang"), "Provider" (MusicBrainz-/AcoustID-/Cover-Art-Archive-
  Checkboxen + AcoustID-API-Schlüssel-Feld mit Hinweis auf
  acoustid.org/api-key), "Kontakt & Grenzwerte" (Kontakt-E-Mail für den
  MusicBrainz-User-Agent, Zeitlimit, Mindest-Konfidenz für Vorschläge).
  Speichern fragt — identisch zur Einstellungen-Ansicht — vorher per
  `MessageBox.Show` (Ja/Nein, Default Nein) nach, Neu-Laden verwirft
  ungespeicherte Änderungen (ruft `ShowProvidersAsync()` erneut auf).
- `GenesisApiClient.cs`: `SettingsResponse` um ein neues Pflichtfeld
  `Metadata` (`MetadataSettingsInfo`) erweitert — ruft weiterhin denselben
  `GET/PATCH /settings`-Endpunkt auf, nur ein zusätzliches Feld im
  bestehenden Antwort-Schema.
- Neue WPF-freie Hilfsklasse `ProvidersViewSupport.cs` (`ProviderFormValues`,
  `BuildUpdatePayload`, `FromSettingsResponse`) nach demselben Muster wie
  `SettingsViewSupport.cs` — testbar ohne echten WPF-Control-Baum.
- Tests: neue Datei `ProvidersViewSupportTests.cs` (3 Fälle: alle
  Metadaten-Felder werden korrekt übernommen, die PATCH-Payload enthält
  NUR den `metadata`-Schlüssel, alle Schlüssel/Werte sind exakt
  snake-case). Bestehende `SettingsViewSupportTests.cs` angepasst (neues
  Pflichtfeld `Metadata` im Test-Fixture `SampleSettings()`). `dotnet test`:
  **43/43 bestanden** (vorher 40). `dotnet build
  -p:EnableWindowsTargeting=true`: weiterhin 0 Warnungen/0 Fehler.
- Navigation: `nav.providers` (Sektion "System") ruft jetzt `ShowProvidersAsync()`
  auf, statt wie zuvor auf den generischen Platzhaltertext zurückzufallen.

**Nächste Schritte:** eine der beiden verbliebenen Medientabellen-
Verfeinerungen (Cover-Anzeige, Filter-Dialog) ODER eine gänzlich neue
Ansicht (z.B. Bibliotheks-Drill-down, Pendant zu Gap B, oder der
Lautheits-Dialog `nav.loudness`) — Priorität in einer künftigen Sitzung neu
zu bewerten, gemäß stehender "inkrementell"-Freigabe.

**Sechster Schritt (Sitzung 14, Fortsetzung 12) — Cover-Anzeige im
Medientabellen-Detailpanel (letzte der vier in Schritt 4 offen gelassenen
Verfeinerungen):**

- "COVER" ist laut Originalauftrag §8/§59 der ERSTE Bestandteil der
  Detailansicht (Gap-Analyse D) — vorher wurde eingebettetes/gespeichertes
  Artwork im .NET-Client nirgends tatsächlich ANGEZEIGT, nur über
  `EmbedArtworkAsync`/`FetchArtworkOnlineAsync` bearbeitet. Jetzt zeigt das
  Detailpanel der Medientabellen-Ansicht links neben dem Text das über
  `GET /media/{id}/artwork` gelieferte Bild (eigener `Image`-Bereich links
  vom Textpanel statt — wie im Python-Vorbild — darüber, eine bewusste
  Anpassung an die bestehende, bereits enger bemessene Grid-Zeilenhöhe
  dieser .NET-Oberfläche; funktional identisch: zeigt dasselbe Bild oder
  denselben "kein Cover"-Text).
- `GenesisApiClient.GetArtworkBytesAsync` existierte bereits aus einer
  früheren Phase (Artwork-Einbetten/-Online-Suche) und wird jetzt erstmals
  auch zur reinen Anzeige verwendet — keine neue API-Methode nötig, nur
  neue UI-Verdrahtung.
- Neue WPF-freie Hilfsklasse `MediaCoverSupport.cs`
  (`LooksLikeDecodableImage`) — Pendant zu
  `pixmap_from_artwork_bytes()` in `media_table.py`: dort entscheidet
  Qt's `QPixmap.loadFromData()` per echtem Decodierversuch, ob Bytes ein
  darstellbares Bild sind; in .NET übernimmt das WPF-seitig
  `BitmapImage.EndInit()`, das bei kaputten Daten eine Exception wirft.
  `LooksLikeDecodableImage` ist eine bewusste, dokumentierte Vereinfachung:
  eine reine Signatur-/Magic-Bytes-Prüfung (PNG/JPEG/GIF/BMP/WEBP) OHNE
  WPF-Abhängigkeit, die eindeutig invalide/fremde Daten VOR dem WPF-Aufruf
  erkennt und damit ohne echten WPF-Control-Baum testbar bleibt. Ein
  tatsächlich beschädigtes Bild MIT korrektem Dateikopf fällt weiterhin
  über den `try`/`catch` um `BitmapImage.EndInit()` in `MainWindow.xaml.cs`
  auf den "kein Cover"-Platzhalter zurück — kein erfundenes Bild, kein
  Absturz (Grundprinzip #16).
- `MainWindow.xaml.cs::ShowMediaTableAsync`: Cover wird — identisch zur
  Reihenfolge in `_on_selection_changed` — VOR dem Detailtext aktualisiert,
  in einem eigenen, isolierten `try`/`catch` (ein nicht erreichbarer
  Artwork-Endpunkt darf die restliche Detailansicht nicht verhindern,
  gleiches Muster wie bei Qualität/Loudness/KI/Quelle aus Schritt 4).
- Tests: neue Datei `MediaCoverSupportTests.cs` (9 Fälle: `null`/leere/zu
  kurze/zufällige Daten liefern `false`, jede der fünf unterstützten
  Signaturen PNG/JPEG/GIF/BMP/WEBP liefert `true`). `dotnet test`:
  **52/52 bestanden** (vorher 43). `dotnet build
  -p:EnableWindowsTargeting=true`: weiterhin 0 Warnungen/0 Fehler.
- Damit sind nun DREI der vier in Schritt 4 zurückgestellten
  Medientabellen-Verfeinerungen erledigt (Detailpanel-Abschnitte,
  Cover-Anzeige) — offen bleiben weiterhin Kontextmenü/Mehrfachauswahl-
  Aktionen und der Filter-Dialog.

**Nächste Schritte:** Filter-Dialog in der Medientabelle (Pendant zu
`SearchFiltersDialog`) ODER Kontextmenü/Mehrfachauswahl-Aktionen
(Öffnen/Ordner öffnen/Pfad kopieren, AI-/Convert-/Cutter-/Audiobook-/
Video-Dialoge) ODER eine gänzlich neue Ansicht (z.B. Bibliotheks-
Drill-down, Pendant zu Gap B, oder der Lautheits-Dialog `nav.loudness`) —
Priorität in einer künftigen Sitzung neu zu bewerten, gemäß stehender
"inkrementell"-Freigabe.

**Siebter Schritt (Sitzung 14, Fortsetzung 13) — die letzten drei der
neun Werkzeug-Dialoge der Medientabelle (Hörbuch/Video/KI):**

- `ShowAiDialogAsync` (§25/§27, `MainWindow.ToolDialogsAi.cs`): Tab
  "KI-Vorschläge" + Tab "KI-Musik" (nur bei `kind` `music`/`ai_music`).
- `ShowAudiobookDialogAsync` (§23, `MainWindow.ToolDialogsAudiobook.cs`):
  Tab "Metadaten" (eingebettete Tags, Quelle immer angezeigt) + Tab
  "Kapitel" (Erkennen/Intervall-Generieren als Vorschau mit Ersetzen-
  Bestätigung, Umbenennen, JSON/CSV-Export).
- `ShowVideoDialogAsync` (§24, `MainWindow.ToolDialogsVideo.cs`): Tab
  "Film" + Tab "Serie/Episode", Übernahme als Film ODER Episode erfordert
  explizite Nutzerentscheidung (kein automatisches Umschalten der
  Medienart).
- Neue API-Infrastruktur `Api/DtosTools.cs` + `Api/GenesisApiClient.Tools.cs`
  deckt jetzt alle neun Werkzeuge ab (Umbenennen/Metadaten/Artwork/
  Lautheit/Cutter/Konvertieren/Hörbuch+Kapitel/Video+Film+Episode/KI/
  Fingerprint/Qualität). `dotnet build`: 0 Warnings/0 Errors.
- Bei dieser Gelegenheit per Dateidurchsicht festgestellt: die zehn
  gänzlich neuen Ansichten (Bibliotheks-Drill-down, Duplikate, Download-
  Center, KI-Center, Voice Studio, Plugins, Log-Viewer, Backups, Diagnose,
  Job-Queue, Fehler-Center) sowie der Filter-Dialog waren zu diesem
  Zeitpunkt bereits vollständig umgesetzt UND in die Navigation
  eingehängt — ohne eigenen PROGRESS.md/GAP_ANALYSIS.md-Eintrag.

**Achter Schritt (Sitzung 14, Fortsetzung 14) — Kontextmenü +
Werkzeugleisten-Verdrahtung in der Medientabelle (damit Gap K's
Medientabellen-Teilaufgabe vollständig abgeschlossen):**

- `ShowMediaTableAsync` (`MainWindow.xaml.cs`): Werkzeugleiste um die neun
  Werkzeug-Dialog-Knöpfe (Metadaten/Umbenennen/Artwork/Lautheit/Cutter/
  Konvertieren/Fingerprint/Qualität/Hörbuch/Video/KI) ergänzt, exakt in
  der Reihenfolge aus `media_table.py::action_row`. Alle außer "Filter"
  starten deaktiviert und werden über `UpdateButtonStates()` abhängig von
  der Tabellenauswahl (de)aktiviert — Pendant zu
  `_on_selection_changed()`: Umbenennen wirkt auf eine Mehrfachauswahl
  (`DataGridSelectionMode.Extended` statt `Single`), alle anderen
  Werkzeuge nur bei Einzelauswahl; Hörbuch-Knopf nur bei
  `kind == "audiobook"`, Video-Knopf nur bei `kind` in
  (`movie`, `episode`).
- Neues Kontextmenü (`grid.ContextMenuOpening`) mit identischer
  Aktionsreihenfolge wie `_build_context_menu()` (Abspielen, Metadaten,
  Umbenennen, Artwork, Lautheit, Cutter, Konvertieren, Fingerprint,
  Qualität, Hörbuch, Video, KI, Datei öffnen, Ordner öffnen, Pfad
  kopieren). Jeder Menüpunkt löst denselben Button-`Click` aus
  (`sourceButton.RaiseEvent(new RoutedEventArgs(Button.ClickEvent))`) —
  identisch zur Python-Architekturentscheidung "beide bedienen dieselben,
  bereits vorhandenen Handler, es gibt also keine zweite Implementierung
  derselben Aktion". `PreviewMouseRightButtonDown` wählt beim Rechtsklick
  auf eine noch nicht ausgewählte Zeile zunächst nur diese Zeile aus,
  lässt eine bestehende Mehrfachauswahl aber unangetastet (Pendant zu
  `_on_table_context_menu`).
- `dotnet build -p:EnableWindowsTargeting=true`: 0 Warnings/0 Errors.
  `dotnet test`: weiterhin 52/52 (keine Regression, keine neuen Testfälle
  in diesem Schritt — reine UI-Verdrahtung ohne neue testbare
  WPF-freie Logik).
- Damit ist die Medientabellen-Teilaufgabe aus Gap K vollständig
  abgeschlossen: Suche, Filter-Dialog, eingebetteter Player,
  Kontextmenü/Werkzeugleiste mit allen neun Werkzeug-Dialogen +ein-/
  zweifachen One-Shot-Aktionen (Fingerprint/Qualität), Detailpanel
  (Pfad/Technik/Qualität/Track-Metadaten/Cover/Loudness/KI/Quelle).

**Nächste Schritte:** Bestandsaufnahme der zehn in Schritt 7 gelisteten,
bereits existierenden neuen Ansichten verifizieren (`dotnet test` +
stichprobenartige Durchsicht gegen die jeweilige Python-Referenz), danach
die seit mehreren Sitzungen zurückgestellten `MediaSearchFiltersTests.cs`
sowie die `media_table.open_file_failed_title`/`_text`-i18n-Prüfung,
danach die vom Nutzer angeforderte Deep-Search/Review auf Fehler im
gesamten bisherigen Werk.

---


## 3. Bewusst zurückgestellt — KEINE Lücken (Nutzerentscheidung)

- **License Center / THIRD-PARTY-LICENSES-Einträge** (§33, §64, §65): wird
  laut ausdrücklicher Nutzeranweisung erst ganz am Ende sauber befüllt.
- **Phase 10 (Installer, portable Version, Update-System, Release-Doku)**
  (§65–§68): explizit zurückgestellt, kein Release in dieser Phase gewünscht.
- **Echte OS-Prozess-Sandbox für Plugins** (§34/ADR-0020): bewusste
  Zwischenentscheidung mit dokumentiertem Restrisiko (Zeitlimit statt
  echter Sandbox), spätere Härtung vorgemerkt.

---

## 4. Priorisierte Empfehlung

Reihenfolge nach Nutzen/Aufwand-Verhältnis, nicht nach Abschnittsnummer.
Der Nutzer hat am 2026-10-02 die sequenzielle, autonome Abarbeitung dieser
gesamten Liste freigegeben ("mach es der reihe nach bis du fertig bist").

1. ✅ **E + D + F** (Datei/Ordner öffnen, Cover anzeigen, Loudness/KI im
   Detail-Panel) — **GESCHLOSSEN, Sitzung 14.**
2. ✅ **A + I** (Settings-Schreibzugriff + Provider-Verwaltung) —
   **GESCHLOSSEN, Sitzung 14.**
3. ✅ **B** (Bibliotheks-Drill-down) — **GESCHLOSSEN, Sitzung 14.**
4. ✅ **G** (Medienplayer) — **GESCHLOSSEN, Sitzung 14 (Fortsetzung 4).**
5. ✅ **C** (erweiterte Suche/Filter) — **GESCHLOSSEN, Sitzung 14
   (Fortsetzung 5).** *(Nachtrag: war in einer früheren Fassung dieser
   Liste versehentlich nicht aufgeführt, obwohl ihr Schweregrad
   MITTEL-HOCH über J/H liegt — wird hier nachträglich korrekt
   eingeordnet und noch vor J/H abgearbeitet.)*
6. ✅ **J** (Log-Viewer), **H** (Rest: Kontextmenü-Umbau) — **GESCHLOSSEN,
   Sitzung 14 (Fortsetzung 6).**
7. 🟡 **K** (.NET-Parität) — **laufend, inkrementell** (Nutzerentscheidung,
   Sitzung 14 Fortsetzung 7): seit Fortsetzung 14 hat JEDE der ~20
   Python-Ansichten/-Dialoge (`ui-reference-pyside/genesis_ui/views/*.py`
   + `dialogs/*.py`) ein .NET-Pendant, inklusive aller neun
   Werkzeug-Dialoge der Medientabelle samt Kontextmenü/Werkzeugleisten-
   Verdrahtung (siehe Siebter/Achter Schritt oben). Kein Showstopper mehr,
   aber NOCH NICHT final "geschlossen": eine stichprobenartige
   Tiefenprüfung jeder einzelnen .NET-Ansicht gegen ihre Python-Referenz
   (insbesondere der zehn in Fortsetzung 13 nachträglich inventarisierten
   Ansichten, die ohne eigenen Dokumentationseintrag entstanden) sowie die
   vom Nutzer angeforderte Deep-Search/Review stehen noch aus (nächste
   Sitzung).

## 5. Nachtrag 2026-10-08 — Stichprobenartige WPF-Tiefenprüfung (ABGESCHLOSSEN 2026-10-09)

Fortsetzung von Gap K ("stichprobenartige Tiefenprüfung jeder einzelnen
.NET-Ansicht gegen ihre Python-Referenz"). Seit 2026-10-09 sind ALLE
§1-§54-Ansichten tiefengeprüft (Gap K vollständig) und Gap L (zentraler
API-Fehlerdialog) ist geschlossen. Geprüft und abgeschlossen:
Medientabelle (Filter-Dialog/Player/Kontextmenü — ein LUFS-Parse-Bug
behoben, Player-Parität zu `player_bar.py` geschlossen, siehe
PROGRESS.md 2026-10-08) und Bibliotheks-Drill-down (Rendering 1:1,
28 bestehende Tests; zwei Kleinstlücken geschlossen: Null-Zellen zeigen
jetzt den Leerwert "-" via Binding-Converter, Suchfeld hat den
Platzhalterhinweis der Python-Referenz). Dabei systematisch aufgefallen:

### L. [MITTEL] WPF zeigt bei fehlgeschlagenen Core-API-Anfragen keinen Fehler-Dialog (Parität zu `show_api_error`, §37)

**Status: GESCHLOSSEN (2026-10-09, Fortsetzung 7).** `GenesisApiException`
transportiert jetzt `ErrorId`/`SolutionHint`; ein zentraler
`ApiErrorDetailHandler` parst BEIDE §37-Fehlerformate (`error_id`-Format
des globalen Exception-Handlers mit Vorrang, dann `detail`), bevor
`GetFromJsonAsync` eine kontextlose `HttpRequestException` werfen kann.
Die neue `MainWindow.ShowApiError()` (Textaufbau WPF-frei in
`ApiErrorSupport`, getestet) ist an ALLEN 35 `show_api_error`-Stellen der
Python-Referenz 1:1 übernommen (Zählprobe 35/35); Abbruch-ohne-Reload-
Verhalten der Referenz ebenfalls übernommen. Bewusst NICHT umgestellt:
reine Listen-Ladefehler (Statuszeile), Dashboard-Verbindungsfehler,
lokale Validierung und der lokale Datei-Lesefehler im Cover-Dialog
(`OSError`-Ausnahme laut error_dialog.py-Docstring). Details in
PROGRESS.md 2026-10-09 (Fortsetzung 7).

Ursprünglicher Befund: Die Python-Referenz-UI zeigt bei
JEDER fehlgeschlagenen Core-API-Anfrage über
`genesis_ui/dialogs/error_dialog.py::show_api_error()` (30 Aufrufstellen
in `views/*.py`) zusätzlich zur Meldung die nachschlagbare Fehler-ID und
einen Lösungshinweis an — genau die Angaben, die der Nutzer braucht, um
den Vorfall im Fehler-Center wiederzufinden (§37-Format des globalen
Exception-Handlers der Core-API). Der WPF-Client stellt API-Fehler
dagegen überall nur als Inline-Statustext dar
(`*_view.load_failed`-Muster in allen `MainWindow.*.cs`-Ansichten) und
parst im `GenesisApiClient` auch nur das `detail`-Feld der
Fehlerantwort, nicht `error_id`/`solution_hint`. Die Fehlerinformation
ist damit zwar sichtbar (kein stiller Fehlschlag), aber ohne die
§37-Referenzdaten und ohne den in der Python-Referenz üblichen Dialog.

**Betroffen:** alle WPF-Ansichten mit API-Abrufen (systematisch, nicht
auf eine Ansicht beschränkt).

**Empfohlene Umsetzung (ein eigener Inkrement):** `GenesisApiException`
um `ErrorId`/`SolutionHint` erweitern (Parsen des §37-JSON-Fehlerkörpers
in `EnsureSuccessWithDetailAsync`), dazu eine zentrale, lokalisierte
`ShowApiError`-Hilfsfunktion im WPF-Client und deren Nutzung an den
betroffenen Aufrufstellen (analog zu den 30 `show_api_error`-Stellen).
