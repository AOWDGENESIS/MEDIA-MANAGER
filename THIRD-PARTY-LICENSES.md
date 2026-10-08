# THIRD-PARTY-LICENSES — GENESIS Media Manager

> **STATUS: ENTWURF / IN ARBEIT — NICHT RELEASE-FINAL**
> Gemäß Nutzervorgabe ("hier muss am Ende alles sauber eingetragen werden
> aber erst wenn es fertig ist", siehe DECISIONS.md ADR-0005) wird dieser
> Bericht laufend gepflegt, aber erst im Release-Gate (Phase 10) final
> geprüft, unterschrieben und als verbindlich markiert. Automatisch von
> `pip-licenses` erkannte Lizenzangaben ("UNKNOWN") wurden, wo dem Autor
> zum Erstellungszeitpunkt bekannt, manuell ergänzt — dies ersetzt KEINE
> abschließende juristische Prüfung (Prinzip #10/#64).

Stand: 2026-09-30 (Sitzung 1, Phase 1 Foundation)

## Python Core Service (`core/`)

| Paket | Version | Lizenz | Redistribution | Kommerziell | Hinweis |
|---|---|---|---|---|---|
| SQLAlchemy | 2.1.1 | MIT | ja | ja | pip-licenses meldete "UNKNOWN" — MIT laut offiziellem Projekt, vor Release verifizieren |
| Alembic | 1.20.0 | MIT | ja | ja | s.o. |
| anyio | 4.14.2 | MIT | ja | ja | s.o. |
| click | 8.4.2 | BSD-3-Clause | ja | ja | s.o. |
| FastAPI | 0.142.2 | MIT | ja | ja | s.o. |
| h11 | 0.16.0 | MIT | ja | ja | erkannt |
| httpx | 0.28.1 | BSD-3-Clause | ja | ja | erkannt |
| **mutagen** | 1.48.1 | **GPL-2.0-or-later** | ja (Copyleft!) | ja, aber Copyleft-Pflichten beachten | **WICHTIG**: GPL ist ansteckend für direkt darauf linkende Codeteile. Beeinflusst die Wahl der GENESIS-Gesamtlizenz (§64) — wird im Release-Gate gesondert bewertet. Ggf. Alternative pruefen (z.B. TinyTag fuer reines Lesen, MIT) falls eine permissivere Gesamtlizenz gewuenscht ist. |
| pydantic | 2.13.4 | MIT | ja | ja | pip-licenses "UNKNOWN" |
| pydantic-settings | 2.15.0 | MIT | ja | ja | erkannt |
| python-multipart | 0.0.32 | Apache-2.0 | ja | ja | erkannt |
| PyYAML | 6.0.3 | MIT | ja | ja | erkannt |
| starlette | 1.7.0 | BSD-3-Clause | ja | ja | pip-licenses "UNKNOWN" |
| uvicorn | 0.54.0 | BSD-3-Clause | ja | ja | pip-licenses "UNKNOWN" |
| pytest / pytest-cov | 8.4.2 / 5.0.0 | MIT | ja (nur Dev/Test) | ja | nur Testabhaengigkeit, nicht Teil der Auslieferung |
| httpx2 | 2.13.1 | BSD-3-Clause | ja (nur Dev/Test) | ja | nur Testabhaengigkeit (Deep-Review Sitzung 13): `starlette.testclient` warnt sonst, `httpx` sei dafuer veraltet. Offizieller Nachfolger von httpx, gleiche Maintainer (Encode/Pydantic Services). Produktivcode nutzt weiterhin regulaeres `httpx`. |
| pip-licenses | (Dev-Tool) | MIT | n/a | n/a | nur zur Berichtserstellung, nicht Teil der Auslieferung |

## PySide6 Referenz-UI (`ui-reference-pyside/`)

| Paket | Version | Lizenz | Redistribution | Kommerziell | Hinweis |
|---|---|---|---|---|---|
| PySide6 / shiboken6 | 6.11.2 | **LGPL-3.0-only** (Wahlmöglichkeit GPL-2.0/3.0 besteht, wir nutzen LGPL) | ja, bei **dynamischem Linking** (Standard bei PyPI-Wheels) | ja | LGPL erlaubt kommerzielle/proprietäre Nutzung, solange PySide6 selbst nicht statisch verändert eingebettet wird und Nutzer die Bibliothek austauschen können. Vor Release: genaue Redistribution-Bedingungen (Qt-Module, ggf. Qt-Commercial-Grauzonen) mit Profil `06-csharp-dotnet` / allgemeiner Lizenzprüfung final klären. |
| httpx (in UI) | s.o. | BSD-3-Clause | ja | ja | |

## Externe Werkzeuge (system-installiert, nicht mit ausgeliefert)

| Werkzeug | Version (Sandbox) | Lizenz | Hinweis |
|---|---|---|---|
| FFmpeg / FFprobe | 7.1.5 (Debian-Paket `ffmpeg` 7:7.1.5-0+deb13u1) | LGPL/GPL je nach Build-Konfiguration | Debian-Standardbuild verwendet u.a. `libx264`/`libmp3lame` → GPL-Build. Für die finale Windows-Distribution muss die konkrete FFmpeg-Build-Variante (LGPL- vs. GPL-Build) bewusst gewählt und dokumentiert werden (§47: "Lizenz und verwendete Build-Variante müssen dokumentiert werden"). **Offen für Phase 9/10.** |
| SQLite | 3.46.1 | Public Domain | unkritisch |
| Ollama (Laufzeit) | 0.35.0 | MIT | Ollama selbst ist MIT-lizenziert |
| Modell `qwen2.5:0.5b` | (Ollama-Registry) | **Apache-2.0** (Qwen2.5-Reihe, Alibaba Cloud) | Kommerzielle Nutzung laut Apache-2.0 erlaubt; als Standard-Referenzmodell fuer die lokale KI-Anbindung (ADR-0003) gewaehlt. Für andere/größere Qwen2.5-Modellgrößen gilt teils eine abweichende "Qwen License" — bei Modellwechsel jeweils erneut prüfen. |

## Referenzmaterial (nicht Teil der Auslieferung)

| Ressource | Lizenz | Verwendung |
|---|---|---|
| AI Deep-Review Prompt Pack (`reference/review-prompt-pack/`) | MIT | Nur als internes Entwicklungswerkzeug für Code-Reviews genutzt (siehe docs/DEEP_REVIEW_USAGE.md), wird nicht mit dem Produkt ausgeliefert. |

## Offene Punkte bis Release-Gate (Phase 10)

1. Alle "UNKNOWN"-Einträge oben durch tatsächliche SPDX-Verifikation ersetzen
   (z.B. via `licensecheck`, manuelle Prüfung von PyPI-Metadaten/Quellcode).
2. Endgültige Entscheidung zur GENESIS-Gesamtlizenz erst nach Klärung der
   Mutagen-GPL-Frage und der finalen FFmpeg-Build-Variante treffen (§64).
3. .NET/WPF-Abhängigkeiten (sobald implementiert) hier ergänzen (z.B. TagLib#,
   NAudio, falls verwendet — jeweils mit Lizenzprüfung).
4. Voice/TTS-Engine-Wahl (Phase 7, z.B. Piper TTS/MIT) ergänzen.
5. Automatisierten Lizenz-Check-Lauf vor jedem Release in
   `scripts/generate_license_report.py` verankern (§33: "Vor jedem Release
   soll automatisch eine Lizenzprüfung laufen").
