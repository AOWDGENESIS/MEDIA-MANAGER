# Vollständigkeitsprüfung und Ergänzungen / Completeness Audit and Improvements

**Version:** 1.1.0
**Datum / Date:** 2026-09-30
**Prüfobjekt / Review target:** Prompt-Paket Version 1.0

---

## Deutsch

### Prüfweise

Geprüft wurden der deutsche und englische Master-Prompt auf:

- Gleichstand der Profile in beiden Sprachfassungen,
- Abdeckung verbreiteter produktiver Sprachfamilien und Artefakttypen,
- eindeutige Anweisungen für KI-Agenten,
- Sicherheitsgrenzen gegen Prompt Injection im Prüfling,
- Nachweisqualität, reproduzierbare Findings und Online-Referenzen,
- GitHub-taugliche Release- und Governance-Unterlagen.

### Festgestellte Lücken in Version 1.0

1. **Keine expliziten API-Profile.** REST, GraphQL, gRPC und WebSockets waren nur indirekt im universellen Kern enthalten. Es fehlten insbesondere Objekt-/Feldautorisierung, Query-Komplexität, Batching und Streaming.
2. **NoSQL, Cache und Event Stores nicht gesondert abgedeckt.** Der SQL-Abschnitt deckte nicht ausreichend Operator-Injection, Cache Poisoning, TTL-/Invalidierungsfehler und Event-Replay ab.
3. **CI/CD- und GitHub-Actions-Risiken nicht ausreichend konkret.** Workflow-Permissions, SHA-Pinning von Actions, OIDC, untrusted PR-Daten, Cache-/Artefakt-Poisoning und Runner-Isolation fehlten als eigenes Profil.
4. **Android fehlte als separates mobiles Profil.** Kotlin deckt AndroidManifest, exported Components, Intents, WebViews, Keystore, Backups und Release Signing nicht vollständig ab.
5. **KI-/LLM-/RAG-/Agentensysteme fehlten.** Prompt Injection, untrusted Retrieval, Tool-Use, excessive agency, Vektorzugriff und Modelloutput als Injection-Quelle erfordern eigene Prüfregeln.
6. **Hochintegritäts- und Legacy-Familien waren unterrepräsentiert.** Ada/SPARK, Fortran und COBOL/Mainframe hatten kein Profil, obwohl sie in sicherheitskritischen, wissenschaftlichen und geschäftskritischen Systemen verbreitet sind.
7. **Groovy und Clojure fehlten als JVM-Sonderfälle.** Ihre dynamischen Ausführungsmechanismen und CI-/Build-Verwendung brauchen zusätzliche Prüfhinweise.
8. **Maschinenlesbarer Vertrag war unvollständig.** Der Prompt enthielt eine lesbare Ausgabeform, aber keine klare Option für JSON/SARIF, keine Beweisstatus-Taxonomie und keine Patch-Policy.
9. **Governance-/Release-Nachweise waren zu wenig explizit.** SBOM, Artefaktintegrität, reproduzierbare Builds, Lizenz-/Herkunftsrisiken und Disclosure-Prozess waren nicht klar genug genannt.
10. **False-Positive-Disziplin fehlte.** Es war nicht ausreichend festgelegt, wie Scanner-Hinweise, Hypothesen und nicht verifizierbare Konfigurationen getrennt werden.
11. **Für eine eigenständige GitHub-Veröffentlichung fehlten Repository-Unterlagen.** LICENSE, CHANGELOG, SECURITY, CONTRIBUTING, Release Notes, Release Checklist, NOTICE und ein Validierungsskript waren nicht Bestandteil des ursprünglichen Pakets.

### Umgesetzte Ergänzungen in Version 1.1.0

- Beide Master-Prompts enthalten jetzt einen **Agenten-Interoperabilitätsvertrag** mit YAML/JSON-Eingaben, JSON-/SARIF-Option, Beweisstatus und minimaler Patch-Policy.
- Der universelle Kern enthält zusätzliche Abschnitte für **Bedrohungsmodell, Traceability, Release Governance, Lieferkette, Lizenz-/Herkunftsprüfung und Fehlalarm-Disziplin**.
- Beide Sprachfassungen wurden von **32 auf 41 inhaltsgleiche Profile** erweitert:
  - API (REST/GraphQL/gRPC/WebSocket)
  - NoSQL/Cache/Message Store
  - GitHub Actions/CI-CD/Release Automation
  - Android
  - KI/LLM/Agent/RAG
  - Ada/SPARK
  - Fortran
  - COBOL/Mainframe
  - weitere JVM-Sprachen (Groovy/Clojure)
- Neue Referenzen wurden ergänzt, unter anderem für OWASP API Security, OWASP GenAI, NIST AI RMF, Android Security, GitHub Actions Hardening, Ada/SPARK und SEI CERT Fortran.
- Für die GitHub-Veröffentlichung enthält das isolierte Release-Paket zusätzlich alle üblichen Projekt- und Release-Dokumente sowie ein lokales Validierungsskript und SHA-256-Manifest.

### Verbleibende, bewusste Grenzen

- Ein Paket kann nicht Hunderte historische und Nischensprachen einzeln normativ abbilden. Das Profil **„Andere Sprache / Discovery“** ist verpflichtend für nicht gelistete Sprachen und verlangt offizielle Primärquellen.
- Die Referenzlinks ersetzen keine verbindliche Rechts-, Compliance-, Safety- oder Zertifizierungsprüfung.
- Online-Quellen ändern sich. Der Agent muss bei Nutzung Datum, Version und konkrete Relevanz der Quelle dokumentieren.
- Kein Prompt, Linter oder Scanner kann eine vollständige Sicherheitsgarantie geben. Autorisierte Laufzeit-, Integrations-, Fuzz-, Last- und Penetrationstests bleiben erforderlich.

---

## English

### Review method

The German and English master prompts were reviewed for:

- profile parity between both language editions,
- coverage of common production language families and artifact types,
- unambiguous instructions for AI agents,
- security boundaries against prompt injection in reviewed material,
- evidence quality, reproducible findings, and online references,
- GitHub-ready release and governance documentation.

### Gaps identified in version 1.0

1. **No explicit API profiles.** REST, GraphQL, gRPC, and WebSockets appeared only indirectly in the universal core. Object/property authorization, query complexity, batching, and streaming were missing.
2. **No dedicated NoSQL, cache, and event-store coverage.** The SQL section did not sufficiently address operator injection, cache poisoning, TTL/invalidation defects, and event replay.
3. **CI/CD and GitHub Actions risks were not concrete enough.** Workflow permissions, action SHA pinning, OIDC, untrusted PR data, cache/artifact poisoning, and runner isolation were missing as a dedicated profile.
4. **Android lacked a dedicated mobile profile.** Kotlin does not fully cover AndroidManifest, exported components, intents, WebViews, Keystore, backups, and release signing.
5. **AI/LLM/RAG/agent systems were absent.** Prompt injection, untrusted retrieval, tool use, excessive agency, vector access, and model output as an injection source require dedicated checks.
6. **High-integrity and legacy families were underrepresented.** Ada/SPARK, Fortran, and COBOL/mainframe had no profile despite use in safety-critical, scientific, and business-critical systems.
7. **Groovy and Clojure were missing as JVM-specific cases.** Their dynamic execution mechanisms and CI/build use need additional review guidance.
8. **The machine-readable contract was incomplete.** The prompt had a readable report format but no clear JSON/SARIF option, evidence-status taxonomy, or patch policy.
9. **Governance and release evidence was insufficiently explicit.** SBOM, artifact integrity, reproducible builds, license/provenance risks, and disclosure process were not named clearly enough.
10. **False-positive discipline was missing.** The prompt did not sufficiently distinguish scanner signals, hypotheses, and non-verifiable configurations.
11. **A standalone GitHub publication lacked repository documents.** LICENSE, CHANGELOG, SECURITY, CONTRIBUTING, release notes, a release checklist, NOTICE, and a validation script were absent from the original package.

### Improvements implemented in version 1.1.0

- Both master prompts now include an **agent interoperability contract** for YAML/JSON input, optional JSON/SARIF output, evidence status, and a minimal patch policy.
- The universal core now includes sections for **threat modeling, traceability, release governance, supply chain, license/provenance review, and false-positive discipline**.
- Both language editions were expanded from **32 to 41 equivalent profiles**:
  - API (REST/GraphQL/gRPC/WebSocket)
  - NoSQL/cache/message store
  - GitHub Actions/CI-CD/release automation
  - Android
  - AI/LLM/agent/RAG
  - Ada/SPARK
  - Fortran
  - COBOL/mainframe
  - other JVM languages (Groovy/Clojure)
- New reference sources include OWASP API Security, OWASP GenAI, NIST AI RMF, Android Security, GitHub Actions Hardening, Ada/SPARK, and SEI CERT Fortran.
- The isolated GitHub release package additionally includes standard project/release documents, a local validation script, and a SHA-256 manifest.

### Remaining intentional boundaries

- No package can individually and normatively cover hundreds of historical and niche languages. The **“Other Language / Discovery”** profile is mandatory for unlisted languages and requires official primary sources.
- Reference links do not replace formal legal, compliance, safety, or certification review.
- Online sources change. An agent must record source date, version, and concrete relevance when using them.
- No prompt, linter, or scanner can provide a complete security guarantee. Authorized runtime, integration, fuzz, load, and penetration testing remain necessary.
