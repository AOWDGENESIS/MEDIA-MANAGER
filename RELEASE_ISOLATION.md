# Release Isolation / Release-Isolation

## Deutsch

Dieses Release wird in einem dedizierten Staging-Ordner gebaut. Die Archivierung erfolgt ausschließlich
von dessen Elternordner aus und enthält genau einen Top-Level-Ordner. Nicht in das Release aufnehmen:
Workspace-Dateien, `.git`, lokale Konfiguration, Caches, virtuelle Umgebungen, Abhängigkeiten,
Build-Artefakte, Logs, Testdaten und Secrets.

Empfohlene Veröffentlichung:

1. Aus dem geprüften Staging-Ordner die Validierung ausführen.
2. SHA-256-Manifest neu erzeugen.
3. ZIP neu erzeugen und dessen Hash separat veröffentlichen.
4. GitHub Release als `v1.2.2` anlegen und nur die drei Artefakte hochladen: ZIP, ZIP-Hash, Release Notes.

## English

This release is built in a dedicated staging directory. Archive only from its parent directory and
include exactly one top-level folder. Do not include workspace files, `.git`, local configuration,
caches, virtual environments, dependencies, build artifacts, logs, test data, or secrets.

Recommended publication:

1. Run validation from the reviewed staging directory.
2. Regenerate the SHA-256 manifest.
3. Rebuild the ZIP and publish its hash separately.
4. Create GitHub Release `v1.2.2` and upload only three artifacts: ZIP, ZIP hash, and release notes.
