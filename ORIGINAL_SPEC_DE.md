# GENESIS MEDIA MANAGER — Original-Entwicklungsauftrag (unverändert übernommen)

> Diese Datei enthält den vollständigen, unveränderten Originalauftrag des
> Nutzers vom 2026-09-30. Sie ist die rechtlich/inhaltlich bindende
> Referenzspezifikation. `PROJECT_BRIEF.md` ist die kondensierte
> Arbeitszusammenfassung daraus — bei jedem Zweifel gilt DIESES Dokument.

# GENESIS MEDIA MANAGER
## Vollständiger Entwicklungsauftrag und technische Gesamtspezifikation

## 1. Ziel des Projekts

Entwickle eine moderne, modulare, vollständig erweiterbare und möglichst lokal/offline arbeitende Windows-Anwendung mit dem Arbeitstitel:

**GENESIS Media Manager**

Die Anwendung soll eine zentrale Medienverwaltung für Musik, Hörbücher, Filme, Serien, Podcasts und KI-generierte Audioinhalte werden.

Das Programm soll nicht nur Dateien verwalten, sondern Medien automatisch analysieren, erkennen, mit Metadaten versehen, sinnvoll benennen, katalogisieren, normalisieren, schneiden, konvertieren und über eine leistungsfähige lokale Datenbank durchsuchbar machen.

Das gesamte Projekt soll konsequent auf **Open-Source-Komponenten** und eine nachvollziehbare Lizenzstruktur setzen.

Es darf keine unnötige Cloud-Abhängigkeit geben.

Lokale Verarbeitung und lokale KI sollen grundsätzlich bevorzugt werden.

---

# 2. Grundprinzipien

Die folgenden Regeln gelten für die gesamte Entwicklung:

1. Open Source hat höchste Priorität.
2. Offline-first.
3. Keine zwingende Cloud-Abhängigkeit.
4. Lokale Dateien werden niemals ungefragt gelöscht.
5. Originaldateien werden grundsätzlich geschützt.
6. Massenänderungen benötigen eine Vorschau und Bestätigung.
7. Jede Änderung muss nachvollziehbar und möglichst rückgängig machbar sein.
8. Externe Datenquellen werden über austauschbare Provider/Adapter eingebunden.
9. KI-generierte Informationen müssen als solche gekennzeichnet werden.
10. Jede externe Abhängigkeit muss hinsichtlich Lizenz und Verteilung geprüft werden.
11. DRM- oder sonstige technische Schutzmaßnahmen dürfen nicht umgangen werden.
12. Das Programm soll mit großen Medienbibliotheken umgehen können.
13. Das Programm soll modular entwickelt werden, damit einzelne Komponenten später ausgetauscht werden können.
14. Die Datenbank darf niemals die einzige Quelle für die tatsächlichen Dateien sein.
15. Der vollständige physische Dateipfad muss für jede bekannte Mediendatei gespeichert werden.
16. Alle automatischen Entscheidungen müssen transparent dargestellt werden.
17. Unsichere Erkennungen dürfen nicht automatisch bestehende Metadaten überschreiben.
18. Das Programm soll auch ohne Internet sinnvoll nutzbar bleiben.
19. Verarbeitungsvorgänge müssen protokolliert werden.
20. Es muss ein vollständiges Backup-/Rollback-Konzept geben.

---

# 3. Unterstützte Medien

## Musik

Unterstütze möglichst alle gängigen Audioformate über eine geeignete Open-Source-Medienengine, insbesondere:

- MP3
- FLAC
- WAV
- AIFF
- AAC
- M4A
- ALAC
- OGG
- Opus
- WMA
- weitere verbreitete FFmpeg-kompatible Audioformate

## Hörbücher

Unterstütze insbesondere:

- MP3
- M4A
- M4B
- AAC
- FLAC
- WAV

Hörbuch-spezifische Informationen:

- Autor
- Titel
- Reihe
- Bandnummer
- Sprecher
- Verlag
- Erscheinungsjahr
- Sprache
- Kapitel
- Kapitelnummer
- Cover
- Beschreibung

## Filme

Unterstütze insbesondere:

- MP4
- MKV
- AVI
- MOV
- WebM
- weitere verbreitete Videoformate

Analysiere zusätzlich:

- Codec
- Auflösung
- FPS
- HDR
- Bitrate
- Audioformate
- Audiokanäle
- Sprachen
- Untertitel
- Kapitel
- Laufzeit

## Serien

Unterstütze:

- Serie
- Staffel
- Episode
- Episodennummer
- Titel
- Jahr
- Beschreibung
- Schauspieler
- Regisseur
- Cover
- technische Medieninformationen

## Podcasts

Unterstütze:

- Podcastname
- Episode
- Episodennummer
- Veröffentlichungsdatum
- Beschreibung
- Sprecher
- Cover
- Quelle
- URL

## KI-Musik

Unterstütze ausdrücklich KI-generierte Musik.

Speichere nach Möglichkeit:

- AI / Human / Hybrid / Unknown
- Quelle
- verwendetes Modell
- Erstellungsdatum
- Prompt
- Beschreibung
- Instrumental/Vocal
- Sprache
- Genre
- Stil
- Stimmung

Keine Information darf erfunden werden. Unbekannte Werte müssen als unbekannt gespeichert werden.

---

# 4. Benutzeroberfläche

Erstelle eine moderne Windows-GUI im Dark Mode.

Die Oberfläche soll professionell, übersichtlich und für große Bibliotheken geeignet sein.

## Hauptnavigation

```text
DASHBOARD

MEDIEN
  Musik
  Hörbücher
  Filme
  Serien
  Podcasts
  KI-Musik
  Unbekannt

BIBLIOTHEK
  Suche
  Interpreten
  Alben
  Titel
  Genres
  Personen
  Quellen

WERKZEUGE
  Medienanalyse
  Metadaten
  Umbenennen
  Lautheit
  Schneiden
  Konvertieren
  Audio-Erkennung
  Duplikate
  Qualitätsprüfung
  Artwork

DOWNLOAD / IMPORT
  Download Center
  Import
  Quellen

KI
  KI-Metadaten
  Audioanalyse
  Voice Studio
  TTS

SYSTEM
  Einstellungen
  Datenbanken
  Provider
  Plugins
  Lizenzen
  Logs
  Backups
  Diagnose
```

Die Benutzeroberfläche soll:

- Dark Mode
- skalierbar
- moderne Icons
- Suchfeld
- Tabellenansicht
- Kartenansicht
- Detailansicht
- Filter
- Sortierung
- Mehrfachauswahl
- Drag & Drop
- Fortschrittsanzeigen
- Warnungen
- Bestätigungsdialoge
- Vorschau vor Massenänderungen

unterstützen.

---

# 5. Dashboard

Das Dashboard soll einen Überblick über die komplette Bibliothek liefern.

Beispiel:

```text
Musik                  14.382
Hörbücher               1.247
Filme                   2.381
Serien                    732
Podcasts                  418
KI-Musik                  213

Gesamt                   19.373
```

Zusätzlich:

- fehlende Metadaten
- fehlende Cover
- Duplikate
- beschädigte Dateien
- unbekannte Medien
- nicht analysierte Dateien
- Lautheitsprobleme
- verdächtige Qualitätsprobleme
- letzte Verarbeitung
- laufende Jobs

---

# 6. Medien-Scanner

Entwickle einen leistungsfähigen Scanner.

Der Scanner soll:

1. Verzeichnisse rekursiv durchsuchen.
2. Medienformate erkennen.
3. Dateien klassifizieren.
4. technische Informationen auslesen.
5. vorhandene Metadaten auslesen.
6. Hash erzeugen.
7. Audio-Fingerprint erzeugen, sofern möglich.
8. Dateipfad speichern.
9. Datenbank aktualisieren.
10. bereits bekannte Dateien erkennen.
11. geänderte Dateien erkennen.
12. verschwundene Dateien erkennen.

Keine Datei darf durch einen Scan verändert werden.

---

# 7. Datenbank

Verwende eine lokale relationale Datenbank.

Die Architektur muss mindestens folgende Entitäten berücksichtigen:

```text
Media
Files
Artists
Albums
Tracks
Genres
Persons
Books
Audiobooks
Series
Episodes
Movies
Podcasts
Chapters
Sources
Providers
Tags
Artwork
Fingerprints
Loudness
TechnicalMetadata
AIMetadata
VoiceProfiles
ProcessingJobs
ProcessingHistory
Backups
Licenses
Settings
```

Die Datenbank muss für große Bibliotheken optimiert werden.

---

# 8. Physischer Dateipfad

Für jede Mediendatei muss der vollständige Pfad gespeichert werden.

Beispiel:

```text
F:\Media\Music\Metallica\Metallica\
02 - Nothing Else Matters.flac
```

Die Detailansicht muss anzeigen:

- vollständigen Dateipfad
- Dateiname
- Ordner
- Dateigröße
- Änderungsdatum
- Format

Buttons:

```text
Datei öffnen
Ordner öffnen
Pfad kopieren
Datei analysieren
Metadaten bearbeiten
```

Die Datenbank darf niemals stillschweigend falsche Pfade anzeigen.

---

# 9. Globale Suche

Implementiere eine leistungsfähige Suche.

Suche nach:

- Titel
- Interpret
- Album
- Genre
- Autor
- Sprecher
- Regisseur
- Schauspieler
- Serie
- Staffel
- Episode
- Dateiname
- Dateipfad
- Quelle
- Format
- Jahr
- KI-Status

Zusätzlich Filter:

```text
Format
Dateigröße
Dauer
Jahr
Genre
Lautheit
Qualität
Quelle
KI / Nicht-KI
fehlende Metadaten
fehlendes Cover
Duplikate
```

Später optional:

```text
"Zeige mir ruhige Rockmusik aus den 1990ern."
```

über lokale KI-Suche.

---

# 10. Metadaten-Engine

Entwickle eine zentrale Metadaten-Engine.

Sie muss mehrere Quellen kombinieren können.

Provider sollen austauschbar sein.

Beispiele:

- MusicBrainz
- AcoustID
- Cover Art Archive
- weitere offene Musikdatenbanken
- lokale Datenbanken
- lokale Benutzerdaten
- lokale KI

Die Provider dürfen nicht fest in die Anwendung eingebaut sein.

Verwende ein Provider-Interface.

---

# 11. Trefferbewertung

Wenn mehrere Quellen unterschiedliche Ergebnisse liefern, muss ein Abgleich stattfinden.

Beispiel:

```text
MusicBrainz       99 %
AcoustID           98 %
Dateiname          94 %
lokale KI          91 %
```

Das System soll daraus einen nachvollziehbaren Vorschlag erzeugen.

Beispiel:

```text
Vorschlag:

Metallica
Nothing Else Matters
Metallica
1991

Erkennungswahrscheinlichkeit:
98.7 %

[Übernehmen]
[Bearbeiten]
[Alternative anzeigen]
[Ignorieren]
```

Unsichere Ergebnisse niemals automatisch übernehmen.

---

# 12. Audio-Fingerprinting

Integriere eine Open-Source-Fingerprint-Engine.

Ziel:

Ein Lied soll auch erkannt werden können, wenn:

- der Dateiname falsch ist
- Metadaten fehlen
- die Datei umbenannt wurde
- nur ein Teil des Liedes vorhanden ist

Fingerprint-Ergebnisse müssen gespeichert werden.

---

# 13. Audio-Erkennung

Erstelle ein eigenes Modul:

```text
Audio Recognition
```

Funktionen:

- Datei analysieren
- Fingerprint erstellen
- Datenbanken abfragen
- Treffer vergleichen
- Confidence anzeigen
- Vorschlag erstellen
- Benutzer bestätigen lassen

---

# 14. Metadaten-Bearbeitung

Der Benutzer muss sämtliche relevanten Tags manuell bearbeiten können.

Unterstütze mindestens:

- Titel
- Interpret
- Album
- Album Artist
- Tracknummer
- Discnummer
- Genre
- Jahr
- Composer
- Comment
- Copyright
- Lyrics
- Sprache
- Cover

Hörbuch-/Film-spezifische Felder entsprechend ergänzen.

---

# 15. Automatische Dateibenennung

Implementiere einen frei konfigurierbaren Template-Mechanismus.

Beispiele:

```text
%Artist% - %Title%
```

oder:

```text
%Artist%\%Album%\%Track% - %Title%
```

Hörbücher:

```text
%Author%\%Series%\%BookTitle%
```

Filme:

```text
%Title% (%Year%)
```

Vor Änderungen immer Vorschau anzeigen.

---

# 16. Rename Preview

Beispiel:

```text
ALT:
unknown123.mp3

NEU:
Metallica - Enter Sandman.mp3
```

Massenänderungen:

```text
127 Dateien werden umbenannt.

[Änderungen durchführen]
[Abbrechen]
```

Jede Änderung muss protokolliert werden.

---

# 17. Rollback

Jeder Verarbeitungslauf bekommt eine eindeutige Job-ID.

Speichere:

- ursprünglichen Pfad
- neuen Pfad
- ursprüngliche Metadaten
- neue Metadaten
- Zeit
- Benutzeraktion
- Programmversion
- Fehler
- Warnungen

Ermögliche:

```text
Job auswählen
↓
Rollback
↓
vorheriger Zustand wiederherstellen
```

---

# 18. Audio Cutter

Implementiere einen grafischen Audioeditor.

Darstellung:

```text
Waveform
│
├── Start
├─────────────────────
│                     │
│                  Ende
└─────────────────────
```

Funktionen:

- Wiedergabe
- Pause
- Start setzen
- Ende setzen
- Zoom
- Waveform
- exakte Zeitposition
- Vorschau
- Fade In
- Fade Out
- Auswahl speichern

Export mindestens:

```text
MP3
WAV
FLAC
```

Bei verlustfreien bzw. geeigneten Formaten soll möglichst ohne unnötige Neukodierung gearbeitet werden.

---

# 19. Lautheitsanalyse

Implementiere eine professionelle Loudness Engine.

Analysiere:

- LUFS
- Integrated Loudness
- True Peak
- Peak
- optional ReplayGain

Konfigurierbarer Zielwert:

```text
-14 LUFS
```

True Peak beispielsweise:

```text
-1 dBTP
```

Der Zielwert muss veränderbar sein.

Vorher/Nachher anzeigen.

Originale niemals ungefragt überschreiben.

---

# 20. Qualitätsanalyse

Analysiere:

- Codec
- Bitrate
- Samplerate
- Bit depth
- Kanäle
- Dauer
- Peak
- Loudness
- mögliche Beschädigung

Erkenne nach Möglichkeit:

- verdächtige Upscales
- ungewöhnliche Transcodierungen
- beschädigte Dateien
- abgeschnittene Dateien

Kennzeichne solche Ergebnisse ausdrücklich als Analyse/Verdacht und nicht als absolute Wahrheit.

---

# 21. Duplikaterkennung

Mehrstufig:

1. Dateihash
2. Größe
3. Dauer
4. technische Parameter
5. Audio-Fingerprint
6. Metadaten

Unterscheide:

```text
Exaktes Duplikat
wahrscheinliches Duplikat
gleicher Inhalt / anderes Format
ähnlicher Inhalt
```

Niemals automatisch löschen.

---

# 22. Artwork Engine

Unterstütze:

- Cover suchen
- Cover herunterladen, sofern Quelle dies erlaubt
- Cover einbetten
- Cover extrahieren
- Cover ersetzen
- Artwork anzeigen

Speichere Quelle und Status des Artwork.

---

# 23. Hörbuch-System

Eigene Hörbuchansicht.

Unterstütze:

- Autor
- Sprecher
- Verlag
- Reihe
- Band
- Kapitel
- Cover
- Beschreibung

Große Hörbuchdateien sollen analysiert werden können.

Optional:

```text
Kapitel erkennen
Kapitel erzeugen
Kapitel umbenennen
Kapitel exportieren
```

---

# 24. Film- und Serienverwaltung

Eigene Datenmodelle.

Film:

```text
Titel
Originaltitel
Jahr
Regisseur
Schauspieler
Genre
Laufzeit
Sprache
Untertitel
Codec
Auflösung
HDR
Audio
Cover
Dateipfad
```

Serie:

```text
Serie
Staffel
Episode
Titel
Jahr
Schauspieler
Regisseur
Beschreibung
Dateipfad
```

---

# 25. KI-Metadaten

Binde lokale KI über eine Provider-Abstraktion ein.

Bevorzugt:

- Ollama
- lokale LLMs
- lokale Audioanalyse
- lokale Embeddings

Die KI darf Vorschläge erzeugen für:

- Genre
- Stimmung
- Sprache
- Instrumente
- Gesang
- Thema
- Beschreibung
- Tags
- Klassifikation

Alle KI-Ergebnisse müssen mit:

```text
AI generated
Model
Model version
Timestamp
Confidence
```

gespeichert werden.

---

# 26. KI-Suche

Implementiere später semantische Suche.

Beispiele:

```text
"ruhige Musik zum Einschlafen"

"düstere Rockmusik"

"Hörbücher von diesem Sprecher"

"Filme mit ähnlicher Stimmung"
```

Dafür kann eine lokale Embedding-Datenbank verwendet werden.

Keine Cloud-KI voraussetzen.

---

# 27. KI-Musik

Unterstütze ausdrücklich:

```text
AI Generated
Human Generated
Hybrid
Unknown
```

Metadaten:

- Quelle
- Modell
- Prompt
- Erstellungsdatum
- Besitzer
- Künstlername
- Genre
- Stil
- Sprache

---

# 28. Voice Studio

Integriere ein separates Modul:

```text
GENESIS VOICE STUDIO
```

Funktionen:

- Stimme aufnehmen
- Sprachproben verwalten
- Voice Profile erstellen
- Voice Profile testen
- Text-to-Speech
- Audio exportieren
- Voice Profile löschen
- Voice Profile sichern
- lokale Verarbeitung

Die Anwendung muss klar anzeigen:

```text
Welche Engine?
Welche Modell-Lizenz?
Offline?
Open Source?
Kommerzielle Nutzung erlaubt?
```

Keine Sprachdaten dürfen ohne ausdrückliche Benutzeraktion an externe Server übertragen werden.

---

# 29. Eigene Stimme für andere Programme

Erstelle eine lokale TTS-Schnittstelle.

Mögliche Schnittstellen:

```text
lokaler HTTP-Endpunkt
REST API
CLI
Windows TTS Integration
WAV/MP3 Export
```

Beispielarchitektur:

```text
Andere lokale Anwendung
        ↓
GENESIS Voice API
        ↓
Voice Engine
        ↓
Audio
```

Die Voice Engine muss austauschbar sein.

---

# 30. Download Center

Integriere ein separates Download-/Import-System.

Unterstützte Quellen sollen über Adapter angebunden werden, beispielsweise:

```text
YouTube
TikTok
Spotify
Audible
Pocket FM
direkte Medien-URLs
lokale Dateien
```

Wichtig:

Die Anwendung darf keine DRM-Schutzmechanismen umgehen.

Wenn ein Dienst keinen zulässigen Download ermöglicht, muss die Anwendung dies erkennen und entsprechend melden.

Das System soll keine Zugangsdaten oder Cookies unsicher speichern.

Provider müssen austauschbar sein.

---

# 31. Download-Workflow

```text
URL eingeben
↓
Quelle erkennen
↓
Provider auswählen
↓
Verfügbarkeit prüfen
↓
Metadaten abrufen
↓
Downloadoptionen anzeigen
↓
Benutzer bestätigen
↓
Download
↓
Datei analysieren
↓
Metadaten ergänzen
↓
Fingerprint
↓
Lautheit analysieren
↓
Dateiname bestimmen
↓
Bibliothek importieren
```

---

# 32. Quellenverwaltung

Jede importierte Datei soll ihre Herkunft speichern können:

```text
Source
Provider
Original URL
Original ID
Importdatum
Importmethode
```

Damit bleibt nachvollziehbar, woher ein Medium stammt.

---

# 33. Lizenzverwaltung

Erstelle ein eigenes:

```text
License Center
```

Jede Abhängigkeit und jedes Modell erhält:

```text
Name
Version
Lizenz
URL
Verwendung
Redistribution erlaubt?
Commercial use?
Hinweise
```

Vor jedem Release soll automatisch eine Lizenzprüfung laufen.

---

# 34. Plugin-System

Baue die Architektur von Anfang an pluginfähig.

Mögliche Plugins:

```text
Metadata Provider
Audio Fingerprint
Downloader
TTS Engine
AI Engine
Artwork Provider
Database Provider
Exporter
Importer
Converter
```

Ein Plugin darf das Hauptprogramm nicht destabilisieren.

---

# 35. Job Queue

Alle längeren Operationen laufen über eine zentrale Job Queue.

Beispielsweise:

```text
Analyse
Metadaten
Fingerprint
Cover
Lautheit
Konvertierung
Download
Import
KI
```

Jobs müssen:

- pausierbar
- fortsetzbar
- abbrechbar
- protokollierbar

sein.

---

# 36. Fortschrittsanzeige

Beispiel:

```text
JOB-20260930-00127

Analyse Bibliothek

████████████████░░░░ 82 %

18.231 / 22.104

Aktuell:
Metallica - Enter Sandman.flac

Fehler: 2
Warnungen: 17
```

---

# 37. Fehlerbehandlung

Keine stillen Fehler.

Jeder Fehler erhält:

```text
Error ID
Zeit
Komponente
Datei
Aktion
Fehlermeldung
technische Details
Lösungsvorschlag
```

Benutzerfreundliche Darstellung:

```text
Metadaten konnten nicht abgerufen werden.

Grund:
Provider nicht erreichbar.

Datei wurde nicht verändert.

[Erneut versuchen]
[Später]
[Details]
```

---

# 38. Diagnose

Integriere ein Diagnosemodul.

Prüfe:

- Datenbank
- Speicherplatz
- Medienpfade
- FFmpeg
- Provider
- Plugins
- KI
- TTS
- Download Engine
- Dateiberechtigungen
- beschädigte Datenbankeinträge

---

# 39. Bibliotheksreparatur

Ein zentraler Button:

```text
SCAN & REPAIR
```

Erkennt:

```text
fehlende Dateien
fehlende Metadaten
fehlende Cover
Duplikate
kaputte Dateien
falsche Dateinamen
fehlende Fingerprints
fehlende Loudness-Daten
verwaiste Datenbankeinträge
```

Zuerst:

```text
Reparaturplan erstellen
```

Danach:

```text
Änderungen anzeigen
```

Danach erst:

```text
Reparatur durchführen
```

---

# 40. Backup

Vor kritischen Operationen:

- Datenbankbackup
- Metadatenbackup
- Rename Journal
- Konfigurationsbackup

Backups müssen versioniert werden.

Keine unnötigen Backups riesiger Mediendateien erstellen.

---

# 41. Speicherverwaltung

Die Anwendung darf Arbeitslaufwerke nicht unkontrolliert füllen.

Vor größeren Operationen:

```text
freier Speicher
benötigter Speicher
Sicherheitsreserve
```

prüfen.

Temporäre Dateien müssen automatisch bereinigt werden.

---

# 42. Import und Export

Unterstütze Bibliotheksexport mindestens als:

```text
JSON
CSV
XML
M3U
M3U8
```

Der Benutzer soll die Datenbank nicht in einem proprietären Gefängnis behalten.

---

# 43. Pfadänderungen

Wenn ein Medienordner verschoben wurde, soll das Programm Dateien möglichst wiederfinden können.

Beispiel:

```text
Alter Pfad:
F:\Music\

Neuer Pfad:
G:\Music\
```

Das Programm soll anhand von:

- Dateiname
- Hash
- Fingerprint
- Datenbankinformationen

die Dateien wieder zuordnen können.

---

# 44. Sicherheitsmodell

Grundsätzlich:

```text
Analyse = ungefährlich
Vorschlag = ungefährlich
Änderung = Benutzerbestätigung
Löschen = zusätzliche Bestätigung
Massenänderung = Preview + Bestätigung
```

Keine destruktive Aktion ohne explizite Benutzerfreigabe.

---

# 45. Datenschutz

Besonders schützen:

- Sprachaufnahmen
- Voice Profiles
- lokale Medienpfade
- persönliche Bibliotheksdaten
- Zugangsdaten
- Provider-Tokens

Keine Telemetrie ohne ausdrückliche Zustimmung.

---

# 46. Lokale KI-Anbindung

Die Architektur soll lokale KI-Systeme unterstützen, insbesondere:

```text
Ollama
LM Studio
weitere lokale OpenAI-kompatible APIs
```

Die KI-Verbindung muss konfigurierbar sein.

Beispiel:

```text
Provider:
Ollama

Endpoint:
http://127.0.0.1:11434

Model:
...
```

Keine zwingende Cloud-API.

---

# 47. Technische Medienengine

Nutze eine bewährte Open-Source-Medienengine wie FFmpeg für:

- Analyse
- Konvertierung
- Extraktion
- Audio
- Video
- Kapitel
- Metadaten
- Schnitt
- Normalisierung

Lizenz und verwendete Build-Variante müssen dokumentiert werden.

---

# 48. Architektur

Empfohlene Struktur:

```text
GENESIS Media Manager
│
├── UI
├── Application Core
├── Media Scanner
├── Metadata Engine
├── Provider Engine
├── Fingerprint Engine
├── Loudness Engine
├── Audio Cutter
├── Video Engine
├── Audiobook Engine
├── Podcast Engine
├── AI Engine
├── Voice Engine
├── Download Engine
├── Artwork Engine
├── Duplicate Engine
├── Quality Engine
├── Rename Engine
├── Conversion Engine
├── Search Engine
├── Database
├── Job Queue
├── Backup Engine
├── Rollback Engine
├── Plugin Engine
├── License Engine
├── Diagnostics
└── Logging
```

---

# 49. Entwicklungsprinzip

Das Projekt muss modular und testbar entwickelt werden.

Keine riesige monolithische Datei.

Jede wichtige Funktion erhält ein eigenes Modul.

Die Komponenten müssen möglichst über klare Interfaces miteinander kommunizieren.

---

# 50. Testsystem

Erstelle Tests für:

- Datenbank
- Scanner
- Metadaten
- Fingerprint
- Rename
- Rollback
- Loudness
- Audio Cutter
- Videoanalyse
- Downloader
- Provider
- KI
- TTS
- Plugin-System
- Backup
- Lizenzprüfung

Verwende Testmedien.

Niemals Tests direkt auf der echten persönlichen Medienbibliothek durchführen.

---

# 51. Testmodus

Implementiere einen vollständigen:

```text
SAFE TEST MODE
```

Dabei werden:

- keine echten Dateien verändert
- keine Dateien gelöscht
- keine echten Downloads durchgeführt
- keine echten Voice Profiles überschrieben

Stattdessen wird mit einer Testbibliothek gearbeitet.

---

# 52. Benutzerrechte

Die Anwendung soll möglichst ohne Administratorrechte funktionieren.

Administratorrechte nur verlangen, wenn sie technisch wirklich erforderlich sind.

---

# 53. Internationalisierung

Von Anfang an vorbereiten für:

```text
Deutsch
English
日本語
Русский
```

Keine Texte fest im Programmcode verteilen.

Alle UI-Texte über Sprachressourcen.

---

# 54. Logging

Logs müssen strukturiert sein.

Beispiel:

```text
2026-09-30 21:00:01
INFO
MediaScanner
Scan started

2026-09-30 21:00:04
WARNING
MetadataProvider
MusicBrainz timeout
```

Log-Level:

```text
TRACE
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

---

# 55. Konfigurationssystem

Alle wichtigen Einstellungen sollen über die GUI konfigurierbar sein.

Keine manuelle Bearbeitung von Konfigurationsdateien voraussetzen.

Konfigurierbar:

- Medienordner
- Datenbankpfad
- Backup-Pfad
- Temp-Pfad
- FFmpeg
- KI
- Ollama
- Provider
- Download
- TTS
- Lautheit
- Rename Templates
- Sprache
- UI
- Plugins

---

# 56. Datenschutzfreundliche Grundeinstellung

Default:

```text
Offline
Keine Telemetrie
Keine Cloud-KI
Keine automatische Löschung
Keine automatische Überschreibung
Keine automatischen Downloads
```

Der Benutzer aktiviert zusätzliche Funktionen bewusst.

---

# 57. Performance

Das Programm muss auch mit sehr großen Bibliotheken umgehen können.

Vermeide:

- vollständiges Einlesen aller Dateien in den RAM
- unnötige Neuanalyse
- unnötige Neukodierung
- doppelte Downloads
- doppelte Fingerprints
- unnötige KI-Anfragen

Verwende Caching und inkrementelle Verarbeitung.

---

# 58. Intelligentes Caching

Speichere Ergebnisse von:

- Fingerprints
- Metadaten
- Artwork
- KI-Analyse
- technischen Analysen
- Provider-Abfragen

Erneute Verarbeitung nur wenn nötig.

---

# 59. Benutzerfreundliche Detailansicht

Beim Anklicken eines Mediums:

```text
┌──────────────────────────────────────────────┐
│ COVER                                        │
│                                              │
│ Titel                                        │
│ Interpret                                    │
│ Album                                        │
│                                              │
│ METADATEN                                    │
│                                              │
│ TECHNIK                                      │
│                                              │
│ LOUDNESS                                     │
│                                              │
│ ERKENNUNG                                    │
│                                              │
│ KI-ANALYSE                                   │
│                                              │
│ QUELLE                                       │
│                                              │
│ DATEIPFAD                                    │
│                                              │
│ [Abspielen]                                  │
│ [Bearbeiten] [Schneiden] [Normalisieren]    │
│ [Datei öffnen] [Ordner öffnen]              │
└──────────────────────────────────────────────┘
```

---

# 60. Medienplayer

Integriere einen einfachen lokalen Player.

Unterstütze:

- Play
- Pause
- Stop
- Seek
- Lautstärke
- Playlist
- Kapitel
- Waveform
- AB-Wiedergabe

Keine vollständige Streamingplattform notwendig.

---

# 61. Globale Medienaktionen

Über Kontextmenü:

```text
Abspielen
Metadaten bearbeiten
Analysieren
Erkennen
Umbenennen
Normalisieren
Schneiden
Konvertieren
Cover bearbeiten
Duplikate suchen
Datei öffnen
Ordner öffnen
Pfad kopieren
In Bibliothek anzeigen
```

---

# 62. Datenbank-Navigation

Klick auf:

```text
Interpret
```

zeigt alle Titel.

Klick auf:

```text
Album
```

zeigt alle Titel.

Klick auf:

```text
Titel
```

zeigt vollständige Detailinformationen inklusive physischem Dateipfad.

---

# 63. Medien-Wissensgraph

Bereite die Datenbank optional für Beziehungen vor:

```text
Artist
  ↓
Album
  ↓
Track
  ↓
File
```

und:

```text
Person
 ↓
Artist / Actor / Director / Author / Speaker
```

Dadurch können später komplexe Beziehungen durchsucht werden.

---

# 64. Open-Source-Richtlinie

Das Projekt selbst soll unter einer geeigneten Open-Source-Lizenz veröffentlicht werden.

Vor der Festlegung der Lizenz:

- Abhängigkeiten analysieren
- Modelllizenzen prüfen
- FFmpeg-Build prüfen
- Datenbanklizenzen prüfen
- Providerbedingungen prüfen
- Redistributable-Komponenten prüfen

Keine Lizenzbehauptung ohne Prüfung.

---

# 65. Release-System

Ein Release muss enthalten:

```text
Programm
Dokumentation
LICENSE
THIRD-PARTY-LICENSES
NOTICE
CHANGELOG
Konfigurationsschema
Testreport
Abhängigkeitsliste
Lizenzreport
```

---

# 66. Installer

Erstelle später:

- portable Version
- Installer
- frei wählbaren Installationspfad
- keine feste C:-Pfadannahme
- Deinstallation
- Updatefähigkeit
- Backup vor Update

---

# 67. Update-System

Updates dürfen nicht einfach Dateien überschreiben.

Vor Update:

```text
Backup
↓
Kompatibilitätsprüfung
↓
Update
↓
Migration
↓
Test
↓
Rollback bei Fehler
```

---

# 68. Dokumentation

Dokumentiere:

- Installation
- Konfiguration
- Provider
- KI
- Voice
- Downloads
- Datenbank
- Backup
- Wiederherstellung
- Plugins
- Lizenzierung
- Fehlerbehebung
- Entwicklerdokumentation

---

# 69. Entwicklungsphasen

## Phase 1: Foundation

- Projektstruktur
- UI
- Datenbank
- Settings
- Logging
- Scanner
- Medienmodell

## Phase 2: Musik

- Metadaten
- MusicBrainz
- Fingerprinting
- Artwork
- Suche
- Rename

## Phase 3: Audio

- Loudness
- Audio Cutter
- Qualitätsanalyse
- Konvertierung
- Duplikate

## Phase 4: Hörbücher

- Bücher
- Sprecher
- Kapitel
- M4B
- Cover

## Phase 5: Video

- Filme
- Serien
- technische Analyse
- Kapitel
- Untertitel

## Phase 6: KI

- Ollama
- lokale LLMs
- semantische Suche
- KI-Metadaten
- KI-Musik

## Phase 7: Voice

- Voice Studio
- TTS
- Voice Profiles
- lokale API

## Phase 8: Import/Download

- Provider
- Download Center
- Quellenverwaltung
- Importpipeline

## Phase 9: Hardening

- Backup
- Rollback
- Lizenzprüfung
- Sicherheitsprüfung
- Performance
- Fehlerbehandlung

## Phase 10: Release

- Installer
- portable Version
- Dokumentation
- Tests
- Release Gate

---

# 70. Wichtigste Qualitätsanforderung

Das Programm darf niemals nach dem Prinzip:

```text
Datei gefunden
→ automatisch verändern
```

arbeiten.

Stattdessen:

```text
ERKENNEN
↓
ANALYSIEREN
↓
VORSCHLAG
↓
CONFIDENCE
↓
VORSCHAU
↓
BENUTZERFREIGABE
↓
ÄNDERUNG
↓
PROTOKOLL
↓
ROLLBACK-MÖGLICHKEIT
```

Automatische Verarbeitung darf für eindeutig sichere, vom Benutzer freigegebene Regeln aktiviert werden.

---

# 71. Endziel

Das fertige Programm soll eine zentrale lokale Medienplattform bilden:

```text
                GENESIS MEDIA MANAGER
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
      MUSIK           HÖRBÜCHER          VIDEO
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                  MEDIEN-DATENBANK
                         │
       ┌─────────┬───────┼────────┬─────────┐
       │         │       │        │         │
    Suche    Analyse   KI       Voice    Quellen
       │         │       │        │         │
       └─────────┴───────┼────────┴─────────┘
                         │
                   LOKAL / OFFLINE
```

Das Programm soll am Ende nicht nur ein Tagger sein, sondern eine **vollständige Open-Source-Medienverwaltung mit intelligenter Analyse, lokaler KI, Audio-/Videoverarbeitung, Datenbank, Fingerprinting, Loudness-Management, Voice Studio, Import-/Download-System, Suchmaschine und nachvollziehbarem Archiv**.

Alle Komponenten müssen modular bleiben, damit zukünftige offene Datenbanken, KI-Modelle, TTS-Engines, Medienformate und Provider hinzugefügt werden können, ohne die Kernarchitektur neu schreiben zu müssen.

**Bei jeder technischen Entscheidung ist die langfristig wartbare, sichere, lizenzrechtlich saubere und lokal nutzbare Lösung zu bevorzugen.**

---

## Zusatzauftrag des Nutzers (im selben Auftrag enthalten)

> der workspace und der chat verlauf dürfen niemals voll laufen dass es immer
> zusammen und merke dir immer das ziel außerdem baust du dir bitte eine
> vollständige testumgebung hohl dir hier alles was du brauchst um es richtig
> zu machen
> https://github.com/AOWDGENESIS/AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen
>
> und hier muss am ende alles sauber eingetragen werden aber erst wenn es
> fertig ist
