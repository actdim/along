---
name: along-version-bump
description: Increment project or protocol version (patch by default), sanitize typography, execute wrap-session reconciliation, and create a release git commit. Universal support for Node, Python, Rust, .NET, and custom .along/scripts/bump_version.py hooks. Use when invoking /along-version-bump.
---

# Along Version Bump  [v2.2.9]

Universal project version bumper and release pipeline engine for repositories adopting Along.

## When to Use
- Finalizing a milestone, stage, or version release (`/along-version-bump`, `/version-bump`, "bump version", "release new version").
- Incrementing `package.json`, `pyproject.toml`, `Cargo.toml`, or `.along/` state.
- Preparing clean ASCII typography and release git commit.

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
- Command: `/along-version-bump`
