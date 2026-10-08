# 6. Remote-Fix v1.2.2 anwenden / Apply remote fix v1.2.2

## Deutsch

Dieser Schritt korrigiert gezielt ein Repository, dem versteckte Dateien wie `.github/`, `.gitignore`
oder `.gitattributes` fehlen. Nutze bevorzugt das vollständige Release-Verzeichnis oder den Patch
`github-fix-v1.2.2.patch`.

### Variante A — Vollständige Release-Dateien übernehmen

```bash
git clone https://github.com/AOWDGENESIS/AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen.git
cd AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen

# Kopiere den INHALT des entpackten v1.2.2-Release-Ordners hierher.
# Die lokale .git/-Struktur darf nicht überschrieben oder kopiert werden.
python3 scripts/validate_release.py
git status
git add -A
git commit -m "Fix GitHub release packaging and validation for v1.2.2"
git push origin main
```

### Variante B — Patch anwenden

```bash
git clone https://github.com/AOWDGENESIS/AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen.git
cd AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen

git apply --index ../github-fix-v1.2.2.patch
python3 scripts/validate_release.py
git diff --cached --check
git commit -m "Fix GitHub release packaging and validation for v1.2.2"
git push origin main
```

Danach in GitHub einen Tag `v1.2.2` und ein Release gemäß `04_PUBLISH_RELEASE_DE_EN.md` erstellen.

## English

This step specifically corrects a repository missing hidden files such as `.github/`, `.gitignore`,
or `.gitattributes`. Prefer the complete release directory or `github-fix-v1.2.2.patch`.

### Option A — Apply complete release files

```bash
git clone https://github.com/AOWDGENESIS/AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen.git
cd AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen

# Copy the CONTENTS of the extracted v1.2.2 release folder here.
# Do not overwrite or copy the local .git/ structure.
python3 scripts/validate_release.py
git status
git add -A
git commit -m "Fix GitHub release packaging and validation for v1.2.2"
git push origin main
```

### Option B — Apply patch

```bash
git clone https://github.com/AOWDGENESIS/AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen.git
cd AI-Deep-Review-Prompt-Pack-KI-Prompt-Paket-f-r-Tiefenpr-fungen

git apply --index ../github-fix-v1.2.2.patch
python3 scripts/validate_release.py
git diff --cached --check
git commit -m "Fix GitHub release packaging and validation for v1.2.2"
git push origin main
```

Then create GitHub tag `v1.2.2` and a release as described in `04_PUBLISH_RELEASE_DE_EN.md`.
