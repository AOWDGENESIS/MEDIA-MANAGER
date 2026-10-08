# Deep Quality Assurance — v1.2.2 / Tiefgehende Qualitätssicherung — v1.2.2

## Deutsch

### Prüfumfang

- Struktur, Dateigrenzen und isolierte ZIP-Erzeugung
- Versionen, Release-Namen, Prüfsummenmanifest und Extraktionstest
- 41 deutsche und 41 englische Masterprofile
- 41 eigenständige, zweisprachige Standalone-Prompts
- Abhängigkeitsprofile für TypeScript, Kotlin, F#, Scala, Android und weitere JVM-Sprachen
- Markdown-Code-Fences, JSON-Manifest, GitHub Issue Forms, GitHub-Setup-Anweisungen
- URL-Syntax und erreichbare Primärquellen, soweit ohne Authentisierung oder Rate Limits prüfbar; zum Auditzeitpunkt waren 93 von 94 Dokumentations-URLs mit 2xx erreichbar, eine offizielle Groovy-Dokumentationsseite blockierte automatisierte HEAD-Anfragen mit 403.

### Befunde und Korrekturen

| ID | Befund | Korrektur |
|---|---|---|
| QA-001 | Einige NIST-PDF-Links und ältere OWASP-Projektlinks waren nicht stabil erreichbar. | Stabile NIST-Publikationsseite und aktuelle OWASP-API-Adresse eingesetzt. |
| QA-002 | OWASP-Java-Projekt- und Groovy/Clojure-Links waren nicht ausreichend robust. | Durch gepflegte OWASP Cheat Sheet Series sowie offizielle Groovy-/Clojure-Dokumentation ersetzt. |
| QA-003 | GitHub Issue Forms hatten keine eindeutigen `id`-Felder. | Alle nicht-Markdown-Felder enthalten nun gültige IDs. |
| QA-004 | Der Validator prüfte primär Anzahl, nicht die Zuordnung der Standalone-Profile. | Validator prüft nun Profile, Manifest, Sprachblöcke, Code-Fences und eingebettete Spezialprofile. |
| QA-005 | CODEOWNERS war in den GitHub-Anweisungen erwähnt, aber ohne sichere Vorlage. | Inaktive Beispieldatei und Anleitung zur sicheren Aktivierung ergänzt. |
| QA-006 | Im Remote-GitHub-Checkout fehlten versteckte Dateien `.github/`, `.gitignore` und `.gitattributes`; Manifest-Prüfung und Issue Forms waren dadurch unvollständig. | Versteckte Dateien wiederhergestellt, Checkout-Validierung unterstützt und Git-Upload-Anforderungen präzisiert. |

### Verifikation

- 41 Profile pro Master-Fassung bestätigt.
- 41 nummerierte Standalone-Prompt-Dateien bestätigt.
- Jede Standalone-Datei enthält deutschen und englischen Prompt-Block.
- ZIP enthält genau einen Top-Level-Ordner und keine `.git`-, Cache-, Build- oder Secret-Artefakte.
- Das interne SHA-256-Manifest und der Extraktionstest müssen vor Veröffentlichung erfolgreich laufen.
- Zusätzlich muss die Validierung in einem frischen Git-Clone erfolgreich sein.

## English

### Review scope

- Structure, file boundaries, and isolated ZIP generation
- Versions, release names, checksum manifest, and extraction test
- 41 German and 41 English master profiles
- 41 self-contained, bilingual standalone prompts
- Dependency profiles for TypeScript, Kotlin, F#, Scala, Android, and other JVM languages
- Markdown code fences, JSON manifest, GitHub Issue Forms, and GitHub setup instructions
- URL syntax and reachable primary sources where checkable without authentication or rate limits; at audit time, 93 of 94 documentation URLs returned 2xx, while one official Groovy documentation page blocked automated HEAD requests with 403.

### Findings and corrections

| ID | Finding | Correction |
|---|---|---|
| QA-001 | Some NIST PDF links and older OWASP project links were not reliably reachable. | Replaced with stable NIST publication page and current OWASP API address. |
| QA-002 | OWASP Java and Groovy/Clojure links were not sufficiently robust. | Replaced with maintained OWASP Cheat Sheet Series and official Groovy/Clojure documentation. |
| QA-003 | GitHub Issue Forms had no unique `id` fields. | Every non-markdown field now has a valid ID. |
| QA-004 | The validator mostly checked counts, not standalone-profile mappings. | It now checks profiles, manifest, language blocks, code fences, and embedded specialized profiles. |
| QA-005 | CODEOWNERS was mentioned in setup instructions without a safe template. | Added an inactive example and safe activation instructions. |
| QA-006 | Remote GitHub checkout lacked hidden `.github/`, `.gitignore`, and `.gitattributes` files; manifest verification and Issue Forms were therefore incomplete. | Restored hidden files, made checkout validation supported, and clarified Git upload requirements. |

### Verification

- 41 profiles per master edition confirmed.
- 41 numbered standalone prompt files confirmed.
- Every standalone file contains German and English prompt blocks.
- ZIP contains exactly one top-level directory and no `.git`, cache, build, or secret artifacts.
- Internal SHA-256 manifest and extraction test must pass before publication.
- Validation must also pass in a fresh Git clone.
