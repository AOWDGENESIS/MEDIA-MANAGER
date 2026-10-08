# GENESIS MEDIA MANAGER – Projekt-Gedächtnis (AUTORITATIV)

> **WICHTIG FÜR JEDE KÜNFTIGE SITZUNG (Mensch + KI-Agent):**
> Dieses Dokument + `PROGRESS.md` + `ARCHITECTURE.md` + `DECISIONS.md` sind die
> **einzige verlässliche Quelle der Wahrheit** für dieses Projekt. Der Chatverlauf
> kann jederzeit gekürzt/komprimiert werden — diese Dateien dürfen das nicht.
>
> **Regel: Vor jeder neuen Arbeitssitzung zuerst diese 4 Dateien lesen, danach weiterarbeiten.**
> **Regel: Nach jeder Arbeitssitzung `PROGRESS.md` aktualisieren, bevor die Sitzung endet.**
> **Regel: Workspace & Chat dürfen niemals "volllaufen"** → siehe Abschnitt "Ressourcen-Disziplin" unten.

Die vollständige Originalspezifikation des Auftraggebers liegt unverändert in
`docs/ORIGINAL_SPEC_DE.md`. Dieses Dokument hier ist die **kondensierte
Arbeitsgrundlage** daraus. Bei Widersprüchen gilt immer `docs/ORIGINAL_SPEC_DE.md`.

## 1. Was ist GENESIS Media Manager?

Eine modulare, offline-first, Open-Source Windows-Anwendung zur zentralen
Verwaltung von Musik, Hörbüchern, Filmen, Serien, Podcasts und KI-Musik:
Scannen, Erkennen, Taggen, Umbenennen, Normalisieren (Loudness), Schneiden,
Konvertieren, Duplikate finden, Fingerprinting, KI-Metadaten (lokal),
Voice Studio/TTS, Download/Import-Center, durchsuchbare lokale Datenbank.

## 2. Die 20 unumstößlichen Grundprinzipien (siehe Original Abschnitt 2)

1. Open Source hat höchste Priorität.
2. Offline-first.
3. Keine zwingende Cloud-Abhängigkeit.
4. Lokale Dateien werden **niemals ungefragt gelöscht**.
5. Originaldateien werden grundsätzlich geschützt.
6. Massenänderungen benötigen **Vorschau + Bestätigung**.
7. Jede Änderung ist nachvollziehbar & möglichst rückgängig machbar (Rollback).
8. Externe Datenquellen nur über austauschbare Provider/Adapter.
9. KI-generierte Informationen müssen **als solche gekennzeichnet** werden.
10. Jede externe Abhängigkeit wird auf Lizenz & Redistribution geprüft.
11. **Keine** Umgehung von DRM/Kopierschutz.
12. Muss mit sehr großen Bibliotheken umgehen können.
13. Modular — Komponenten müssen austauschbar sein.
14. Die DB ist niemals die einzige Quelle für die tatsächlichen Dateien.
15. Vollständiger physischer Dateipfad wird immer gespeichert.
16. Alle automatischen Entscheidungen transparent darstellen.
17. Unsichere Erkennungen überschreiben niemals automatisch bestehende Metadaten.
18. Muss auch ganz ohne Internet sinnvoll nutzbar sein.
19. Alle Verarbeitungsvorgänge werden protokolliert.
20. Es gibt ein vollständiges Backup-/Rollback-Konzept.

**Goldene Prozesskette (Original Abschnitt 70) — gilt für JEDE automatische
Funktion, die in diesem Projekt gebaut wird:**

```
ERKENNEN → ANALYSIEREN → VORSCHLAG → CONFIDENCE → VORSCHAU
→ BENUTZERFREIGABE → ÄNDERUNG → PROTOKOLL → ROLLBACK-MÖGLICHKEIT
```

Nie: "Datei gefunden → automatisch verändern".

## 3. Architektur-Entscheidung (siehe DECISIONS.md ADR-0001 für Details)

Hybrid-Architektur, weil der Auftraggeber ausdrücklich **sowohl** .NET/C# **als
auch** Python wünschte, und weil das Sandbox-Entwicklungssystem nur Linux ist
(WPF/WinUI3 lassen sich dort nicht bauen/testen):

```
                     ┌───────────────────────────┐
                     │   GENESIS CORE SERVICE     │   Python 3.13
                     │  (das "Gehirn", offline)   │   FastAPI lokale REST-API
                     │  Scanner / DB / Metadaten  │   nur 127.0.0.1, kein Cloud-Zwang
                     │  Fingerprint / Loudness /  │
                     │  AI-/Voice-/Download-      │
                     │  Provider / Jobs / Backup  │
                     └─────────────┬─────────────┘
                                   │ lokale HTTP/REST API (127.0.0.1)
                 ┌─────────────────┼─────────────────────┐
                 │                                        │
      ui-reference-pyside/                     ui-windows-dotnet/
      PySide6 (Qt) Referenz-Client             WPF/WinUI3 .NET Windows-Client
      - läuft/testbar in der Sandbox (Linux)   - natives Windows-Zielprodukt
      - Dark Mode, Dashboard, Bibliothek       - baut auf derselben REST-API
      - dient auch als Test-/Debug-UI          - muss unter Windows gebaut werden
```

Begründung: Die gesamte Fachlogik lebt in **einem** Python-Kern (testbar, riesiges
Audio/KI-Ökosystem: mutagen, pyacoustid/chromaprint, pyloudnorm, ffmpeg,
faster-whisper, Ollama-Client). Die Windows-GUI kann nativ in C#/WPF gebaut
werden UND parallel existiert eine PySide6-Oberfläche, die genau dieselbe
API nutzt — das ist zugleich unsere Test-/Entwicklungsoberfläche hier in der
Sandbox. Kein Modul muss doppelt in zwei Sprachen implementiert werden.

## 4. Lokale KI (bereits eingerichtet & getestet in dieser Sandbox)

- Ollama ist installiert (`/usr/local/bin/ollama`, Dienst läuft).
- Modell **qwen2.5:0.5b** (klein, ~397 MB, läuft in <2 GB RAM) ist gezogen und
  wurde erfolgreich getestet (`ollama pull` + `/api/generate`).
- Der `AIProvider`-Adapter in `core/genesis_core/ai/` spricht die
  Ollama-kompatible HTTP-API (`http://127.0.0.1:11434`) — austauschbar,
  konfigurierbar, keine Cloud-Pflicht.

## 5. Datenbank

SQLite (Empfehlung des Nutzers), Zugriff über SQLAlchemy 2.x ORM, WAL-Modus,
Migrationen über Alembic. Schema siehe `ARCHITECTURE.md` §DB und
`core/genesis_core/db/models.py`.

## 6. Ressourcen-Disziplin (Workspace & Chat dürfen nie volllaufen)

- **Keine echten/großen Mediendateien** im Workspace ablegen. Nur winzige
  synthetische Testdateien (wenige Sekunden Ton/Video, per FFmpeg erzeugt,
  typischerweise < 50 KB pro Datei).
- Node/Python `venv`-Ordner, `__pycache__`, Caches etc. gehören zu den vom
  Snapshot ausgeschlossenen Verzeichnissen — dürfen dort bleiben.
- Große Downloads (z. B. Ollama-Modelle) leben außerhalb `/home/user`
  (Standard-Ollama-Pfad `~/.ollama` wird nicht persistiert — das ist
  gewünscht, sonst läuft der Snapshot voll. Modell ggf. in neuer Sitzung
  erneut ziehen, Skript liegt unter `scripts/setup_ollama.sh`).
- Logs werden rotiert (`logutil`), nicht unbegrenzt wachsen lassen.
- Fortschritt/Entscheidungen werden in kompakten Markdown-Dateien
  festgehalten statt im Chat wiederholt zu werden — **immer diese Dateien
  fortschreiben statt lange Historie im Chat aufzubauen.**
- Bei sehr langen Sitzungen: lieber öfter kleine, committete Arbeitsschritte
  + `PROGRESS.md`-Update, als eine riesige monolithische Antwort.

## 7. Lizenz-Politik

Lizenz-Review-Tools liegen in `reference/review-prompt-pack/` (siehe
`docs/DEEP_REVIEW_USAGE.md`). Diese werden **regelmäßig für Code-Reviews**
genutzt, aber der offizielle `licenses/THIRD-PARTY-LICENSES.md` Bericht wird
erst **kurz vor Release** final "sauber eingetragen" — vorher bleibt er klar
als **ENTWURF / UNVOLLSTÄNDIG** markiert (Nutzer-Vorgabe: "muss am Ende
sauber eingetragen werden aber erst wenn es fertig ist").

## 8. Entwicklungsphasen (Original Abschnitt 69) – Status siehe PROGRESS.md

Phase 1 Foundation → Phase 2 Musik → Phase 3 Audio → Phase 4 Hörbücher →
Phase 5 Video → Phase 6 KI → Phase 7 Voice → Phase 8 Import/Download →
Phase 9 Hardening → Phase 10 Release.
