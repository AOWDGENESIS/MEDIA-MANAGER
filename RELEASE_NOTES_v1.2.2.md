# Release Notes — v1.2.2

## Deutsch

Version 1.2.2 korrigiert die GitHub-Repository-Veröffentlichung. Bei der Remote-Prüfung wurde festgestellt,
dass versteckte, für GitHub relevante Dateien (`.github/`, `.gitignore`, `.gitattributes`) nicht im Repository
angekommen waren. Dadurch waren Issue Forms, CODEOWNERS-Beispiel und die interne Release-Manifest-Prüfung
unvollständig. Diese Dateien sind wieder enthalten.

Das lokale Validierungsskript funktioniert nun sowohl in einem isolierten Release-Ordner als auch in einem
normalen Git-Checkout. Die ZIP-Erzeugung prüft weiterhin separat, dass kein `.git`-Verzeichnis oder anderer
Workspace-Inhalt im Release-Archiv enthalten ist. Die GitHub-Upload-Anleitung weist nun ausdrücklich darauf
hin, dass für Dotfiles und `.github` der Git-Terminal-Workflow bevorzugt werden muss.

## English

Version 1.2.2 corrects the GitHub repository publication. Remote verification found that hidden GitHub-relevant
files (`.github/`, `.gitignore`, `.gitattributes`) had not reached the repository. This made Issue Forms, the
CODEOWNERS example, and internal release-manifest verification incomplete. Those files are included again.

The local validation script now works both in an isolated release directory and in a normal Git checkout.
ZIP generation still separately verifies that no `.git` directory or other workspace content is included in the
release archive. GitHub upload instructions now explicitly state that the Git terminal workflow is preferred for
dotfiles and `.github`.
