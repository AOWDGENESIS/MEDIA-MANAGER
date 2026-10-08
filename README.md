# GENESIS Media Manager

Eine modulare, offline-first, Open-Source Medienverwaltung für Musik,
Hörbücher, Filme, Serien, Podcasts und KI-Musik.

> **Lies zuerst:** [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) (kondensierte
> Zusammenfassung), [`docs/ORIGINAL_SPEC_DE.md`](docs/ORIGINAL_SPEC_DE.md)
> (vollständiger Originalauftrag), [`ARCHITECTURE.md`](ARCHITECTURE.md),
> [`DECISIONS.md`](DECISIONS.md) und [`PROGRESS.md`](PROGRESS.md) — diese
> vier/fünf Dateien sind die verbindliche Quelle der Wahrheit für dieses
> Projekt, unabhängig vom Chatverlauf.

## Architektur in Kürze

```
core/                    Python "Gehirn" (Scanner, DB, Metadaten, KI, Jobs, REST-API)
ui-reference-pyside/      PySide6 Dark-Mode-Referenz-Client (läuft plattformübergreifend)
ui-windows-dotnet/         Natives WPF/.NET-Windows-Ziel (Quellcode, Build unter Windows)
reference/review-prompt-pack/  Deep-Review-Prompts für Code-/Lizenzqualität (MIT)
licenses/                 Lizenzberichte (ENTWURF bis Release, siehe ADR-0005)
docs/                     Originalspezifikation, Screenshots, Nutzungsanleitungen
scripts/                  Setup-/Test-/Release-Hilfsskripte
```

Details und Begründung: [`ARCHITECTURE.md`](ARCHITECTURE.md) (ADR-0001).

## Schnellstart (Entwicklung/Test in dieser Sandbox)

```bash
# 1) Python-Umgebung einrichten (FFmpeg, SQLite, Python-Pakete)
bash scripts/setup_python_env.sh

# 2) (Optional) lokale KI vorbereiten
bash scripts/setup_ollama.sh

# 3) Tests ausführen (SAFE TEST MODE - keine echten Dateien betroffen)
bash scripts/run_tests.sh

# 4) Core-API lokal starten
cd core && python3 run_api.py --port 8420
# -> Interaktive API-Doku: http://127.0.0.1:8420/docs

# 5) In einem zweiten Terminal: PySide6-Referenz-UI starten
cd ui-reference-pyside
PYTHONPATH=../core python3 main.py
```

## Aktueller Stand

Siehe [`PROGRESS.md`](PROGRESS.md) für den tagesaktuellen Fortschritt nach
Phasen. Kurzfassung nach Sitzung 1 (Phase 1 „Foundation“, größtenteils
abgeschlossen):

- ✅ Vollständiges Datenbankschema (SQLite/SQLAlchemy) für alle in der
  Spezifikation geforderten Entitäten
- ✅ Rekursiver, read-only Media-Scanner mit Hashing, FFprobe-Technikanalyse,
  Erkennung neuer/geänderter/vermisster Dateien
- ✅ Konfigurationssystem mit datenschutzfreundlichen Defaults (offline, keine
  Telemetrie, keine Cloud-KI)
- ✅ Strukturiertes, rotierendes Logging
- ✅ Job-Queue mit eindeutigen Job-IDs (Grundlage für Rollback)
- ✅ Lokale REST-API (FastAPI) mit automatischer OpenAPI-Doku
- ✅ Lokale KI-Anbindung über Ollama (getestet, Modell `qwen2.5:0.5b`)
- ✅ PySide6-Referenz-UI: Dark Mode, vollständige Navigationsstruktur,
  Dashboard mit echten Live-Daten, Medientabelle mit Detailansicht
  (Screenshots: `docs/screenshot_dashboard.png`, `docs/screenshot_media_table.png`)
- ✅ .NET/WPF-Windows-Client als vollständiges Quellcode-Grundgerüst
  (Build/Test nur unter Windows möglich)
- ✅ 16/16 automatisierte Tests grün (`scripts/run_tests.sh`)
- ✅ Lizenz-Entwurf (`licenses/THIRD-PARTY-LICENSES.md`, Status: ENTWURF)
- ⏳ Phasen 2–10 (Musik-Metadaten, Audio-Werkzeuge, Hörbücher, Video, KI-Suche,
  Voice Studio, Download-Center, Hardening, Release) — offen, siehe Roadmap

## Grundprinzipien (nicht verhandelbar)

Siehe `PROJECT_BRIEF.md` Abschnitt 2 für die vollständige Liste. Die
wichtigste Regel für jede automatische Funktion:

```
ERKENNEN → ANALYSIEREN → VORSCHLAG → CONFIDENCE → VORSCHAU
→ BENUTZERFREIGABE → ÄNDERUNG → PROTOKOLL → ROLLBACK-MÖGLICHKEIT
```

Niemals: „Datei gefunden → automatisch verändern.“

## Danksagung / Herkunftsnachweise

GENESIS entsteht nicht im luftleeren Raum. Wo die technische Arbeit
anderer Entwickler als Inspiration oder Referenz in dieses Projekt
eingeflossen ist, wird das sichtbar und ehrlich dokumentiert statt in
einer Fußnote zu verschwinden — siehe [`docs/G4S-LEGACY.md`](docs/G4S-LEGACY.md)
für die laufend gepflegte Auswertung des öffentlichen GitHub-Bestands von
Gregor Segner (`g4s`).

