# 5. Optional: CODEOWNERS / Optional: CODEOWNERS

## Deutsch

Nutze CODEOWNERS nur, wenn ein echter GitHub-Benutzer oder ein Team als verantwortliche Review-Stelle
festgelegt ist. Die Datei `.github/CODEOWNERS.example` ist absichtlich **nicht aktiv**, damit kein
Platzhalter Pull Requests blockiert.

1. `@REPLACE_WITH_GITHUB_USER_OR_TEAM` in der Beispieldatei durch einen realen Benutzer oder ein
   Team, z. B. `@org/security-team`, ersetzen.
2. Datei als `.github/CODEOWNERS` speichern.
3. Pull Request eröffnen und von den benannten Verantwortlichen prüfen lassen.
4. Erst danach in den Ruleset-Einstellungen „Require review from Code Owners“ aktivieren.

## English

Use CODEOWNERS only when a real GitHub user or team has been designated as the responsible reviewer.
The `.github/CODEOWNERS.example` file is deliberately **inactive**, so that a placeholder cannot
block pull requests.

1. Replace `@REPLACE_WITH_GITHUB_USER_OR_TEAM` in the example file with a real user or team,
   for example `@org/security-team`.
2. Save the file as `.github/CODEOWNERS`.
3. Open a pull request and have the named owners review it.
4. Only then enable “Require review from Code Owners” in the ruleset.
