#!/usr/bin/env bash
# Setzt die lokale Git-Commit-Identitaet fuer dieses Repository.
#
# Hintergrund: .git/config ist laut Sandbox-Regeln explizit von
# Workspace-Snapshots ausgeschlossen (Credential-Pfad) - die hier gesetzte
# Identitaet geht daher bei jedem Sandbox-Neustart verloren und muss erneut
# gesetzt werden, bevor der erste Commit einer neuen Sitzung gelingt.
# Siehe PROGRESS.md "Sandbox-Hinweis" fuer den vollen Kontext.
set -euo pipefail
cd "$(dirname "$0")/.."

git config user.email "genesis-dev@example.local"
git config user.name "GENESIS Media Manager Dev"
echo ">>> Git-Identitaet gesetzt: $(git config user.name) <$(git config user.email)>"
