# Fortschritt – Sicherheit nach Scan-Vorfall (22.10.2026)

**Status: Implementierung und synthetische Tests; KEINE Freigabe für einen Scan auf dem Nutzer-PC.** Das bisherige Vorab-Release bleibt zurückgezogen (`draft:true`). Bereits heruntergeladene alte Kopien können weiterhin vorhanden sein.

## Durchgeführt

- Start-Skript: localhost-Healthcheck mit gebündeltem Python statt wiederholter PowerShell-Aufrufe. Die Probe akzeptiert nur `status=ok` und die GENESIS-Kennung; ZIP, MSI und Inno enthalten den Helfer. Windows-Smokes prüfen seine Präsenz.
- Scanner: begrenzte Dateizahl (200), Hash-I/O (512 MiB) und Laufzeit (120 s) bleiben aktiv; Hash prüft Deadline/Abbruch zwischen Lesechunks. FFprobe-Aufrufe sind nun zusätzlich auf höchstens 10 s je Datei begrenzt. Bei Fehler/Abbruch wird die SQLite-Transaktion zurückgerollt; Originalmedien werden nur gelesen.
- Neue authentifizierte Endpunkte: `POST /scan/start` liefert sofort eine Job-ID, `GET /scan/{id}/status` liefert Fortschritt, `POST /scan/{id}/cancel` fordert Abbruch an. Die WPF-Einstellungsansicht bietet Fortschritt und Abbruch, blockiert Doppelstarts. Der ältere synchrone `/scan`-Endpunkt bleibt für existierende API-Clients begrenzt verfügbar. Scans können nicht pausiert werden.
- Reproduzierbare synthetische Tests für Status, Einzellauf-Sperre, Abbruch/DB-Rollback, erfolgreiches Ergebnis, Medien-Hash-Abbruch und Healthcheck. Windows-CI führt diese Tests mit dem ausgelieferten Python/Backend auf temporären Testdaten aus; pytest wird nur auf dem Runner separat installiert, nicht ins Nutzerpaket aufgenommen.

## Nachweise / Grenzen

- Lokale Linux-Tests: 28 bestanden, 5 übersprungen (API-/Sicherheitsauswahl), 1 Warnung. Scanner-Gesamtauswahl zuvor: 28 bestanden, 8 übersprungen, 1 gezielt abgewählt (ohne ffmpeg). Synthetische Tests einschließlich Neustart: bestanden. Keine interaktive Windows-Desktop-/Fensterzählung hier möglich; die konkrete Ursache der gemeldeten Fensterflut ist ohne Prozessbaum/Logs nicht bewiesen.
- Ein einzelnes blockierendes Betriebssystem-I/O oder ein hängenbleibender fremder Prozess kann ein kooperatives Python-Checkpoint nicht hart unterbrechen. FFprobe-Timeout ist eine zusätzliche, aber keine absolute Hardware-Garantie. Nach Core-Neustart sind laufende Scan-Snapshots im Speicher verloren; verwaiste laufende/pending Scan-Job-Datensätze werden als fehlgeschlagen markiert.
- Windows-CI-Ergebnis für **diesen** Stand, visuelle Sichtbarkeit unter Windows »Installierte Apps«, manuelle Klick-Abnahme aller UI-Pfade, signierter Installer, nichtadministrativer PC-Test und sichere Abnahme auf dem tatsächlich betroffenen Rechner: **noch offen**. Alte erfolgreiche CI-Läufe belegen diese Punkte nicht.

Eine neue öffentliche ZIP-/Release-Veröffentlichung setzt eine gesonderte Sicherheits- und Installationsfreigabe voraus. Das bestehende Draft-Release wird nicht erneut veröffentlicht.
