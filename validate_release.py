#!/usr/bin/env python3
"""Dependency-free integrity validation for the isolated v1.2.2 release."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.2.2"
REQUIRED = {
    "README.md", "DEEP_REVIEW_PROMPT_DE.md", "DEEP_REVIEW_PROMPT_EN.md",
    "COMPLETENESS_AUDIT_DE_EN.md", "VERSION", "LICENSE", "NOTICE.md", "CHANGELOG.md",
    "SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "RELEASE_NOTES_v1.2.2.md",
    "RELEASE_CHECKLIST.md", "RELEASE_MANIFEST.sha256", ".gitignore", ".gitattributes",
    "docs/RELEASE_ISOLATION.md", "docs/QUALITY_ASSURANCE_v1.2.2_DE_EN.md", "docs/GITHUB_REMOTE_AUDIT_v1.2.2_DE_EN.md",
    "scripts/validate_release.py", ".github/PULL_REQUEST_TEMPLATE.md", ".github/CODEOWNERS.example",
    ".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/feature_request.yml",
    "prompts/standalone/README_DE_EN.md", "prompts/standalone/PROFILE_MANIFEST.json",
    "github-setup/README_DE_EN.md", "github-setup/01_CREATE_REPOSITORY_DE_EN.md",
    "github-setup/02_UPLOAD_CONTENT_DE_EN.md", "github-setup/03_SECURITY_AND_BRANCH_SETTINGS_DE_EN.md",
    "github-setup/04_PUBLISH_RELEASE_DE_EN.md", "github-setup/05_OPTIONAL_CODEOWNERS_DE_EN.md", "github-setup/06_APPLY_REMOTE_FIX_v1.2.2_DE_EN.md",
}
FORBIDDEN_DIRS = {"node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
PROFILE_RE = re.compile(r"^## PROFILE: (.*?)\n\n```text\n(.*?)\n```", re.MULTILINE | re.DOTALL)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def parse_profiles(path: Path) -> list[tuple[str, str]]:
    return PROFILE_RE.findall(path.read_text(encoding="utf-8"))


def main() -> None:
    # The validator must work both in the isolated release directory and in a Git checkout.
    # ZIP isolation (one expected top-level directory and no .git) is checked by the packaging procedure.
    checkout_mode = (ROOT / ".git").exists()
    if (ROOT / "VERSION").read_text(encoding="utf-8").strip() != EXPECTED_VERSION:
        fail("VERSION does not match expected version")
    missing = sorted(item for item in REQUIRED if not (ROOT / item).is_file())
    if missing:
        fail(f"missing required files: {', '.join(missing)}")
    forbidden = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_dir() and p.name in FORBIDDEN_DIRS]
    if forbidden:
        fail(f"forbidden directories included: {', '.join(forbidden)}")

    # Structural Markdown checks: every document must have balanced fenced blocks and no accidental trailing whitespace.
    for md in ROOT.rglob("*.md"):
        markdown = md.read_text(encoding="utf-8")
        if markdown.count("```") % 2:
            fail(f"unbalanced Markdown code fence: {md.relative_to(ROOT)}")
        if any(line != line.rstrip() for line in markdown.splitlines()):
            fail(f"trailing whitespace in Markdown: {md.relative_to(ROOT)}")

    de_profiles = parse_profiles(ROOT / "DEEP_REVIEW_PROMPT_DE.md")
    en_profiles = parse_profiles(ROOT / "DEEP_REVIEW_PROMPT_EN.md")
    if len(de_profiles) != 41 or len(en_profiles) != 41:
        fail(f"expected 41 profiles per master prompt, found DE={len(de_profiles)} EN={len(en_profiles)}")
    if len({name for name, _ in de_profiles}) != 41 or len({name for name, _ in en_profiles}) != 41:
        fail("duplicate master-profile heading")

    standalone_dir = ROOT / "prompts" / "standalone"
    standalone_files = sorted(standalone_dir.glob("[0-9][0-9]-*_DE_EN.md"))
    if len(standalone_files) != 41:
        fail(f"expected 41 standalone prompts, found {len(standalone_files)}")
    profile_manifest = json.loads((standalone_dir / "PROFILE_MANIFEST.json").read_text(encoding="utf-8"))
    entries = profile_manifest.get("profiles", [])
    if profile_manifest.get("package_version") != EXPECTED_VERSION or profile_manifest.get("profile_count") != 41 or len(entries) != 41:
        fail("standalone profile manifest is incomplete or has the wrong version")
    de_map, en_map = dict(de_profiles), dict(en_profiles)
    manifest_files = set()
    for item in entries:
        filename = item.get("file")
        de_name, en_name = item.get("de_profile"), item.get("en_profile")
        if not filename or filename in manifest_files:
            fail("invalid or duplicate standalone manifest file entry")
        manifest_files.add(filename)
        standalone = standalone_dir / filename
        if not standalone.is_file():
            fail(f"standalone file missing: {filename}")
        text = standalone.read_text(encoding="utf-8")
        if "## Deutscher Standalone-Prompt" not in text or "## English Standalone Prompt" not in text:
            fail(f"standalone prompt is not bilingual: {filename}")
        if de_name not in de_map or en_name not in en_map:
            fail(f"standalone manifest profile not found in master: {filename}")
        if de_map[de_name] not in text or en_map[en_name] not in text:
            fail(f"standalone prompt lacks its exact specialized master profile: {filename}")
    if manifest_files != {p.name for p in standalone_files}:
        fail("standalone manifest/file set mismatch")

    # Basic GitHub Issue Form rule: every input/textarea/dropdown needs a unique id.
    for form_name in ("bug_report.yml", "feature_request.yml"):
        form = (ROOT / ".github" / "ISSUE_TEMPLATE" / form_name).read_text(encoding="utf-8")
        controls = re.findall(r"^  - type: (?:input|textarea|dropdown)\n(?:    .*\n)*?    id: ([a-z0-9_]+)", form, re.MULTILINE)
        if not controls or len(controls) != len(set(controls)):
            fail(f"invalid or duplicate Issue Form IDs: {form_name}")

    for filename in ("DEEP_REVIEW_PROMPT_DE.md", "DEEP_REVIEW_PROMPT_EN.md"):
        if "https://" not in (ROOT / filename).read_text(encoding="utf-8"):
            fail(f"no HTTPS references in {filename}")

    # Verify the internal manifest last; manifest deliberately does not hash itself.
    for line in (ROOT / "RELEASE_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        expected, rel = line.split(maxsplit=1)
        target = ROOT / rel.strip().removeprefix("*")
        if not target.is_file():
            fail(f"manifest target missing: {rel}")
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            fail(f"manifest checksum mismatch: {rel}")
    mode = "Git checkout" if checkout_mode else "release directory"
    print(f"PASS: {mode} 1.2.2; master profiles=41/41; standalone prompts=41; manifest, parity, forms, and fences verified")


if __name__ == "__main__":
    main()
