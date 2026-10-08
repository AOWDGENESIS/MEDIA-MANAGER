# 4. GitHub Release veröffentlichen / Publish GitHub Release

## Deutsch

1. Auf **Releases** → **Draft a new release** gehen.
2. Tag: `v1.2.2`. Titel: `AI Deep Review Prompt Pack v1.2.2`.
3. Target: Branch `main`.
4. Inhalt von `RELEASE_NOTES_v1.2.2.md` in die Beschreibung kopieren.
5. Genau diese drei Dateien als Release-Artefakte hochladen:
   - `ai-deep-review-prompt-pack-v1.2.2.zip`
   - `ai-deep-review-prompt-pack-v1.2.2.zip.sha256`
   - `RELEASE_NOTES_v1.2.2.md`
6. **Nicht** zusätzlich hochladen: entpackte Repository-Dateien, ältere ZIPs, Workspace-Dateien, Caches,
   `.git`-Daten, Logs, Testdaten oder Secrets.
7. Prüfe nach Upload den SHA-256-Wert der ZIP gegen die `.sha256`-Datei.
8. Falls dieses Release einen bestehenden Remote-Stand v1.2.1 korrigiert, kann zusätzlich
   `github-fix-v1.2.2.patch` als einmaliges Wartungsartefakt hochgeladen werden. Die Patch-Datei ist
   kein Ersatz für die ZIP-Datei und nur gegen den in `docs/GITHUB_REMOTE_AUDIT_v1.2.2_DE_EN.md`
   genannten Ausgangsstand anwendbar.
9. „Set as the latest release“ auswählen und veröffentlichen.

## English

1. Open **Releases** → **Draft a new release**.
2. Tag: `v1.2.2`. Title: `AI Deep Review Prompt Pack v1.2.2`.
3. Target: branch `main`.
4. Copy the content of `RELEASE_NOTES_v1.2.2.md` into the release description.
5. Upload exactly these three release assets:
   - `ai-deep-review-prompt-pack-v1.2.2.zip`
   - `ai-deep-review-prompt-pack-v1.2.2.zip.sha256`
   - `RELEASE_NOTES_v1.2.2.md`
6. Do **not** additionally upload extracted repository files, older ZIPs, workspace files, caches,
   `.git` data, logs, test data, or secrets.
7. After upload, verify the ZIP SHA-256 against the `.sha256` file.
8. If this release corrects an existing v1.2.1 remote state, `github-fix-v1.2.2.patch` may additionally
   be uploaded as a one-time maintenance asset. The patch does not replace the ZIP and applies only to
   the baseline named in `docs/GITHUB_REMOTE_AUDIT_v1.2.2_DE_EN.md`.
9. Select “Set as the latest release” and publish.
