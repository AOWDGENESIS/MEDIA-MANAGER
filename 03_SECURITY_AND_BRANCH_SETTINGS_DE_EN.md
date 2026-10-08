# 3. GitHub security and branch settings / Sicherheits- und Branch-Einstellungen

## Deutsch

Öffne im Repository **Settings**.

### General

- **Features:** Issues und Pull Requests aktivieren, wenn externe Beiträge gewünscht sind.
- **Pull Requests:** Merge Commits deaktivieren; Squash merging aktivieren. Rebase optional.
- **Pull Requests:** „Automatically delete head branches“ aktivieren.
- **Pull Requests:** „Allow auto-merge“ nur aktivieren, wenn Branch Protection vorhanden ist.

### Branches / Rulesets für `main`

Unter **Settings → Rules → Rulesets** oder **Branches** eine Regel für `main` anlegen:

- Require a pull request before merging: aktivieren.
- Require approvals: mindestens 1; bei interner Nutzung nach Teamvorgabe.
- Dismiss stale approvals: aktivieren.
- Require review from Code Owners: aktivieren, sobald CODEOWNERS gepflegt wird.
- Require conversation resolution before merging: aktivieren.
- Block force pushes und block deletions: aktivieren.
- Require signed commits: optional, aber empfohlen, wenn die Organisation dies unterstützt.

### Security / Code security and analysis

- Private vulnerability reporting: aktivieren, falls verfügbar.
- Dependabot alerts und Dependabot security updates: aktivieren, sobald Abhängigkeiten oder GitHub Actions genutzt werden.
- Secret scanning und push protection: aktivieren, falls im Plan verfügbar.
- Code scanning ist für dieses reine Dokumentationspaket optional. Wenn später Workflows oder Skripte erweitert werden,
  prüfe sie vor dem Aktivieren auf minimale Rechte und SHA-Pinning.

### Actions

- Dieses Release benötigt **keine** GitHub Action und **keine** GitHub Secrets.
- Wenn später Actions ergänzt werden: Actions auf vertrauenswürdige Quellen beschränken, Drittanbieter-Actions an
  vollständige Commit-SHAs pinnen, Default-`GITHUB_TOKEN` auf read-only setzen, OIDC statt langlebiger Cloud-Secrets nutzen.
- Niemals Inhalte aus Issues, PR-Titeln, Commit-Messages oder Branch-Namen direkt in `run:`-Shell-Befehle interpolieren.

## English

Open **Settings** in the repository.

### General

- **Features:** Enable Issues and Pull Requests if outside contributions are wanted.
- **Pull Requests:** Disable merge commits; enable squash merging. Rebase is optional.
- **Pull Requests:** Enable “Automatically delete head branches”.
- **Pull Requests:** Enable “Allow auto-merge” only when branch protection exists.

### Branches / Rulesets for `main`

Under **Settings → Rules → Rulesets** or **Branches**, create a rule for `main`:

- Enable Require a pull request before merging.
- Require at least 1 approval; use team policy for internal repositories.
- Enable Dismiss stale approvals.
- Enable Require review from Code Owners once CODEOWNERS is maintained.
- Enable Require conversation resolution before merging.
- Enable Block force pushes and block deletions.
- Require signed commits is optional but recommended where supported by the organization.

### Security / Code security and analysis

- Enable Private vulnerability reporting where available.
- Enable Dependabot alerts and Dependabot security updates when dependencies or GitHub Actions are used.
- Enable secret scanning and push protection when available in the plan.
- Code scanning is optional for this documentation-only package. If workflows or scripts are added later,
  review them for minimal permissions and SHA pinning before enabling them.

### Actions

- This release needs **no** GitHub Action and **no** GitHub Secrets.
- If Actions are added later: restrict action sources, pin third-party actions to full commit SHAs,
  set default `GITHUB_TOKEN` permissions to read-only, and use OIDC instead of long-lived cloud secrets.
- Never interpolate issue content, PR titles, commit messages, or branch names directly into `run:` shell commands.
