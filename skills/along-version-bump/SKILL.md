---
name: along-version-bump
description: Increment project or protocol version (patch by default) behind a pre-release quality gate, reconcile the target milestone, update CHANGELOG.md, and create the release commit and annotated tag. Universal support for Node, Python, Rust, .NET, and custom .along/scripts/bump_version.py hooks. Use when invoking /along-version-bump.
---

# Along Version Bump  [v2.2.15]

Universal project version bumper and release pipeline engine for repositories adopting Along.

## When to Use
- Finalizing a milestone, stage, or version release (`/along-version-bump`, `/version-bump`, "bump version", "release new version").
- Incrementing `package.json`, `pyproject.toml`, `Cargo.toml`, or `.along/` state.
- Verifying clean ASCII typography and preparing the release git commit.

## What a Release Does, In Order
1. **Gates, on the untouched tree**: the repository's tests, the typography check, and the Markdown link integrity check (`along_kb_sync.py --check --strict`). All three run on every invocation, not only with `--commit`. A failing gate aborts before anything is written.
2. **Version**: `.along/scripts/bump_version.py` if the project has one, otherwise the detected manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, `VERSION`, or the Along protocol files).
3. **Milestone**: the milestone in `.along/MILESTONES/` whose front-matter `slug` names the released version is set to `status: completed`, `progress_pct: 100`. Front-matter only; the body is never rewritten.
4. **CHANGELOG.md**: a `## v<version>` section listing the commit subjects since the previous tag.
5. **Commit and tag** (with `-c`): stages only the paths the release wrote, commits `release: v<version>`, and creates the annotated tag `v<version>`. With `-p` it pushes the commit and the tag.

Every step from 2 onward is transactional: if a later step fails, each file is restored byte for byte and the abort message names what was put back. A release never touches machine-global state; installing skills globally is `/along-update` or the installer.

## Usage
```bash
python scripts/along_version_bump.py patch
python scripts/along_version_bump.py minor
python scripts/along_version_bump.py major
python scripts/along_version_bump.py 1.5.0
```

### Flags
- `-c`, `--commit`: Automatically create release `git commit` (`release: vX.Y.Z`).
- `-p`, `--push`: Automatically push release commit and tags to remote repository (`git push`).
- `-cp`, `-pc`: Combine commit and push in one command (`python scripts/along_version_bump.py patch -cp`).
- `--fix-typography`: Apply the ASCII replacements the release gate found. Without it the gate reports findings by file and line and aborts the release; a release never rewrites the tree on its own. The repair is applied inside the transaction, so a later abort restores it too.
- `-n`, `--no-verify`: Skip the tests, typography, and link gates. The one documented way past them; the release still rolls back on a later failure.
- Command: `/along-version-bump`
