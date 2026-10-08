# GENESIS Media Manager UI v2

Stand: 2026-10-07
Version: 0.2.0

## Ziel

Die WPF-Oberflaeche wurde auf Basis des UI-Mockups modernisiert, ohne die bestehende Core-/API-Funktionalitaet zu ersetzen. Die neue Gestaltung ist eine Presentation-Layer-Aenderung.

## Umgesetzt

- moderne dunkle Charcoal/Navy-Palette
- Blau-Lila-Akzent mit dezenten Verlaeufen
- modernisierte Sidebar mit Icons und aktivem Navigationszustand
- pill-formige Suchleiste und Aktionsbuttons
- Connection-Status im Kopfbereich
- modernisierte Dashboard-Karten fuer Musik, Hoerbuecher, Filme und Serien
- kompakte Statistik-Karten fuer fehlende, nicht analysierte und laufende Medienjobs
- Format-Chips in der Medientabelle
- Lazy geladene Cover-Thumbnails fuer sichtbare Medientabellenzeilen
- vorhandene Detail-Cover-Anzeige bleibt erhalten
- keine erfundenen Trenddaten; daher bewusst keine Fake-Sparklines

## Bewusst nicht geaendert

- lokale REST-API
- Datenmodell und SQLite
- Scan/Repair
- Job Queue
- AI/LLM-Logik
- Sicherheits- und Bestaetigungsgrenzen
- Installer-Architektur

## Release-Gate

Version 0.2.0 ist ein UI-/Packaging-Entwicklungsstand. Eine GitHub-Release-Freigabe erfolgt erst nach sauberem Build, allen relevanten Tests, Security-/Regression-Pruefung und dokumentierter Windows-UI-Abnahme.
