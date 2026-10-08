# ARCHITECTURE — GENESIS Media Manager

Siehe `PROJECT_BRIEF.md` §3 und `DECISIONS.md` ADR-0001 für die
Grundsatzentscheidung. Dies hier ist die technische Detailsicht.

## Repository-Layout

```
genesis-media-manager/
├── PROJECT_BRIEF.md          Kondensierte, autoritative Zusammenfassung
├── ARCHITECTURE.md           (diese Datei)
├── DECISIONS.md              ADR-Log
├── PROGRESS.md               Lebender Fortschritts-Tracker
├── docs/
│   ├── ORIGINAL_SPEC_DE.md   Vollständiger Originalauftrag, unverändert
│   ├── DEEP_REVIEW_USAGE.md  Wie das Review-Prompt-Pack genutzt wird
│   └── ...                   (API.md, DB_SCHEMA.md etc. folgen)
├── core/                     Python "Gehirn" — genesis_core Package
│   ├── genesis_core/
│   │   ├── config/           Settings (pydantic-settings, YAML)
│   │   ├── logutil/          Strukturiertes Logging (§54)
│   │   ├── db/                SQLAlchemy-Modelle + Session + Alembic
│   │   ├── models/            Domänen-/DTO-Modelle (pydantic)
│   │   ├── scanner/            Rekursiver, read-only Medien-Scanner (§6)
│   │   ├── metadata/            Metadata-Engine + Trefferbewertung (§10/§11)
│   │   ├── providers/            Provider-Interfaces + Implementierungen (§10)
│   │   ├── fingerprint/           Audio-Fingerprint-Engine (§12/§13)
│   │   ├── loudness/               Lautheitsanalyse/-normalisierung (§19)
│   │   ├── quality/                 Qualitätsanalyse (§20)
│   │   ├── duplicates/                Duplikaterkennung (§21)
│   │   ├── rename/                     Rename-Engine + Preview (§15/§16)
│   │   ├── backup/                      Backup-Engine (§40)
│   │   ├── rollback/                     Rollback-Engine (§17)
│   │   ├── jobs/                          Job Queue (§35/§36)
│   │   ├── ai/                             AI-Provider-Abstraktion (§25/§46)
│   │   ├── voice/                           Voice/TTS-Engine (§28/§29)
│   │   ├── download/                         Download-/Import-Adapter (§30-32)
│   │   ├── plugins/                           Plugin-Engine (§34)
│   │   ├── license/                            License Engine (§33)
│   │   ├── i18n/                                Sprachressourcen (§53)
│   │   ├── api/                                  FastAPI lokale REST-API
│   │   └── utils/                                 Hilfsfunktionen
│   ├── tests/                 pytest-Suite (SAFE TEST MODE, §50/§51)
│   └── testdata_generator/    Erzeugt synthetische Testbibliothek (ADR-0004)
├── ui-reference-pyside/       PySide6 Referenz-/Test-Client (läuft in Sandbox)
├── ui-windows-dotnet/         Natives WPF/.NET Windows-Ziel (Quellcode, Build unter Windows)
├── licenses/                  THIRD-PARTY-LICENSES.md (ENTWURF bis Release), NOTICE.md
├── scripts/                   setup_ollama.sh, run_tests.sh, generate_license_report.py …
└── reference/
    └── review-prompt-pack/    Lokale Kopie des Deep-Review-Prompt-Packs (MIT)
```

## Kommunikationsvertrag: Core-API

- Transport: HTTP/REST, ausschließlich `127.0.0.1` (kein `0.0.0.0`-Bind nötig,
  da nur lokale Clients zugreifen — Ausnahme: Voice-API kann optional für
  "andere lokale Programme" auf einen konfigurierbaren Port gebunden werden,
  §29, standardmäßig ebenfalls nur `127.0.0.1`).
- Framework: FastAPI (OpenAPI-Schema automatisch generiert, wichtig für den
  späteren .NET-Client: dort kann aus dem OpenAPI-Schema ein typisierter
  C#-Client generiert werden, z. B. via NSwag/Kiota — reduziert
  Doppelarbeit).
- Alle mutierenden Endpunkte (Rename, Delete, Overwrite-Metadata, ...) folgen
  strikt der "Goldenen Prozesskette" (PROJECT_BRIEF.md §"Goldene
  Prozesskette"): sie erzeugen zunächst nur einen **Plan/Preview** mit
  Job-ID; eine zweite, explizite Bestätigung führt die Änderung aus.
- Kein Endpunkt darf Dateien löschen ohne zusätzliche explizite Bestätigung
  (Prinzip #4/#44).

## Datenmodell (Auszug, siehe `core/genesis_core/db/models.py`)

Entspricht 1:1 der Entitätsliste aus Originalauftrag §7. Wichtige
Modellierungsentscheidungen:

- `MediaFile` ist die zentrale Tabelle mit dem **physischen Pfad** (Prinzip
  #15) — niemals nur ein DB-Datensatz ohne Dateisystembezug (Prinzip #14).
  Felder: `absolute_path` (eindeutig, indiziert), `directory`, `filename`,
  `size_bytes`, `mtime`, `format`, `content_hash_sha256`, `first_seen_at`,
  `last_seen_at`, `last_scanned_at`, `is_missing` (bool — Datei war da, ist
  jetzt weg, wird NICHT automatisch aus der DB gelöscht, Prinzip #4/#43).
- `MediaKind` Enum: `MUSIC, AUDIOBOOK, MOVIE, EPISODE, PODCAST, AI_MUSIC,
  UNKNOWN` — entspricht der Hauptnavigation "MEDIEN" (§4).
- Jede automatisch erzeugte/vorgeschlagene Information trägt Pflichtfelder
  `source` (z. B. "musicbrainz", "acoustid", "filename-heuristic",
  "ollama:qwen2.5:0.5b", "user"), `confidence` (0.0–1.0, nullable für
  Nutzereingaben) und `is_ai_generated` (bool, Prinzip #9). Roh-Nutzertags
  (`user`-Quelle) werden nie automatisch überschrieben, wenn eine neue
  Erkennung eine niedrigere oder gleiche Konfidenz hat (Prinzip #17).
- `ProcessingJob` / `ProcessingHistory` bilden zusammen die Grundlage für
  Rollback (§17): jeder Job hat eine eindeutige ID (`JOB-YYYYMMDD-NNNNN`),
  speichert Vorher-/Nachher-Zustand strukturiert (JSON-Spalte) sowie
  Programmversion, Fehler, Warnungen.

## Sicherheitsmodell in Code

- Alle destruktiven Operationen (Löschen, Überschreiben, Massenumbenennung)
  müssen zwingend durch `genesis_core.jobs.plan_and_confirm()` laufen: sie
  erzeugen zuerst ein `JobPlan`-Objekt (reine Vorschau, keine Seiteneffekte),
  das erst nach `confirm=True` durch den aufrufenden Client ausgeführt wird.
- `SAFE_TEST_MODE` (Konfigurationsflag) leitet alle Dateisystem- und
  Netzwerkoperationen auf gemockte/temporäre Ziele um; per Default AUS im
  Normalbetrieb, aber die gesamte Testsuite erzwingt es programmatisch
  (pytest-Fixture `safe_test_mode` in `core/tests/conftest.py`).

## Offene technische Punkte für spätere Phasen

- Phase 2: `providers/musicbrainz.py`, `providers/acoustid.py`,
  `providers/coverartarchive.py` (alle: HTTP-Client mit Timeout, Retry,
  Rate-Limit-Respekt, klar gekennzeichnete Fehlermeldungen statt stiller
  Fehler, §37).
- Phase 6: `ai/embeddings.py` für semantische Suche (lokale Embedding-Modelle
  via Ollama, z. B. `nomic-embed-text`, oder `sentence-transformers` falls
  lizenzrechtlich sauber redistributierbar — muss vor Einsatz geprüft
  werden, Prinzip #10).
- Phase 7: `voice/` — TTS-Engine-Auswahl (z. B. Piper TTS, MIT-lizenziert,
  komplett offline, gute Kandidatenwahl — Lizenzprüfung folgt in
  `licenses/THIRD-PARTY-LICENSES.md`, wenn Phase 7 beginnt).
- Phase 8: `download/` Adapter — nur für Quellen, bei denen ein rechtlich
  zulässiger, DRM-freier Download technisch möglich ist; alle anderen
  Quellen liefern eine klare "nicht unterstützt/nicht zulässig"-Meldung statt
  eines Workarounds (Prinzip #11).
