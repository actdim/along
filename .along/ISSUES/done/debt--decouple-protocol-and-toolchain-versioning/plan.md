# Living Plan: debt--decouple-protocol-and-toolchain-versioning (Revision 2)

Execution Mode: Role-Based (along-team: spans core packaging, release bumper, doctor diagnostics, and test suites across 4 subsystems)

## 1. Context and Problem Statement
In `scripts/alongkit/version.py`, `CURRENT_VERSION` is aliased directly to `CURRENT_PROTOCOL_VERSION` (`"4.9.1"`).
`pyproject.toml` uses hatch dynamic pattern `CURRENT_PROTOCOL_VERSION = "(?P<version>[^"]+)"`.
In `scripts/along_version_bump.py`:
- `detect_and_bump_project` extracts `cur_v` from `skills/along-init/protocol.md` (`# ALONG-PROTOCOL v...`).
- `bump_along_dev_repo` rewrites protocol headers (`AGENTS.md`, `protocol.md`, `.along/.protocol-version`, `docs/topic--*.md`) on every toolchain bump.
- Dead regex substitutions target files that already import `version.py` (and non-existent `.well-known/` / `Skills & Slash Commands (v...)` strings).
- `main()` parses `sys.argv` manually and lacks `--protocol` mode.

This plan decouples toolchain package versioning (`CURRENT_VERSION`) from repository protocol specification versioning (`CURRENT_PROTOCOL_VERSION`) per Section 4 of `.along/VISION.md`.

---

## 2. File-to-Version Mapping Table

| File / Location | Target Version | Mode |
| :--- | :--- | :--- |
| `scripts/alongkit/version.py` (`CURRENT_VERSION`, `__version__`) | **Toolchain** | Default bump (`along version-bump [type]`) |
| `scripts/alongkit/version.py` (`CURRENT_PROTOCOL_VERSION`) | **Protocol** | Protocol bump (`--protocol <type>`) |
| `scripts/alongkit/__init__.py` | **Both** | Exports `CURRENT_VERSION`, `__version__`, `CURRENT_PROTOCOL_VERSION` |
| `pyproject.toml` (`[tool.hatch.version]`) | **Toolchain** | Dynamic pattern extracts `CURRENT_VERSION` |
| `package.json` & `packages/dashboard-ui/package.json` | **Toolchain** | Default bump |
| `README.md`: `# ActDim Along (vX.Y.Z)` | **Toolchain** | Default bump |
| `README.md`: `ALONG-PROTOCOL vX.Y.Z` | **Protocol** | Protocol bump |
| `llms-full.txt`: `# ActDim Along (vX.Y.Z)` | **Toolchain** | Default bump |
| `llms-full.txt`: `ALONG-PROTOCOL vX.Y.Z` | **Protocol** | Protocol bump |
| `.along/.protocol-version` | **Protocol** | Protocol bump ONLY |
| `AGENTS.md`: `# ALONG-PROTOCOL vX.Y.Z` | **Protocol** | Protocol bump ONLY |
| `skills/along-init/protocol.md`: `# ALONG-PROTOCOL vX.Y.Z` | **Protocol** | Protocol bump ONLY |
| `.along/VISION.md`: `protocol_version` | **Protocol** | Protocol bump ONLY |
| `docs/topic--*.md`: `ALONG-PROTOCOL vX.Y.Z` | **Protocol** | Protocol bump ONLY |
| `.along/MILESTONES/*.md` & `CHANGELOG.md` & git tag `vX.Y.Z` | **Toolchain** | Default bump ONLY |

---

## 3. Execution Steps (Mapped to REQ-1..REQ-6)

### Step 1: Core Version Constants, Packaging, and CLI (REQ-1, REQ-2, REQ-5)
- `scripts/alongkit/version.py`:
  - Decouple constants: `CURRENT_PROTOCOL_VERSION = "4.9.1"`, `CURRENT_VERSION = "4.9.1"`, `__version__ = CURRENT_VERSION`.
  - Define `MIN_SUPPORTED_PROTOCOL_VERSION = "4.8.0"`.
  - Implement `is_protocol_supported(ver_str: str) -> bool` using `alongkit.semver.parse`: returns `True` iff `parse(MIN_SUPPORTED_PROTOCOL_VERSION) <= parse(ver_str) <= parse(CURRENT_PROTOCOL_VERSION)`.
  - Update module docstring.
- `scripts/alongkit/__init__.py`:
  - Export `CURRENT_VERSION`, `__version__`, and `CURRENT_PROTOCOL_VERSION` in `__all__`.
- `pyproject.toml`:
  - Change `[tool.hatch.version]` `pattern` to `'CURRENT_VERSION = "(?P<version>[^"]+)"'`.
- `scripts/alongkit/cli.py`:
  - Format `along --version` / `-V` as `along {CURRENT_VERSION} (protocol v{CURRENT_PROTOCOL_VERSION})`.
- **Acceptance**: `alongkit` exports both constants, `cli.py --version` prints both versions, `pyproject.toml` pattern matches `CURRENT_VERSION`, `is_protocol_supported` handles `<4.8.0`, `4.8.0..4.9.1`, `>4.9.1`, and invalid strings.

### Step 2: Release Engine Refactoring (`scripts/along_version_bump.py`) (REQ-3, REQ-4)
- Migrate `main()` CLI parsing to `argparse` while preserving ALL existing flags:
  - Optional positional `bump_arg` (`nargs="?"`, default `None`; resolves to `"patch"` when `--protocol` is not specified).
  - `--protocol` (`metavar="TYPE_OR_VER"`, required value `patch|minor|major|<ver>`, avoiding `nargs="?"` ambiguity with positional `bump_arg`).
  - `-c`/`--commit`, `-p`/`--push`, combined `-cp`/`-pc` (normalized to `-c -p` before `parse_args`), `--fix-typography`, `-n`/`--no-verify`, `--skip-ci`, `--reason`, `--carry-over`.
- Refactor `bump_along_dev_repo` / `detect_and_bump_project`:
  - **Default toolchain bump** (when `bump_arg` is provided or `--protocol` is omitted): resolve `cur_v` from `version.CURRENT_VERSION`, update `CURRENT_VERSION` in `scripts/alongkit/version.py`, `package.json`, `packages/dashboard-ui/package.json`, `# ActDim Along (vX.Y.Z)` in `README.md` and `llms-full.txt`. MUST NOT touch `CURRENT_PROTOCOL_VERSION`, `.along/.protocol-version`, `AGENTS.md`, `protocol.md`, `VISION.md`, or `docs/topic--*.md`. Run `update_along_milestones`, `update_changelog`, and `create_release_commit` (with tag `v{new_toolchain_v}`).
  - **Protocol bump** (`--protocol <val>`): resolve `cur_v` from `version.CURRENT_PROTOCOL_VERSION`, update `CURRENT_PROTOCOL_VERSION` in `scripts/alongkit/version.py`, `.along/.protocol-version`, `AGENTS.md`, `skills/along-init/protocol.md`, `ALONG-PROTOCOL vX.Y.Z` in `README.md`, `llms-full.txt`, and `docs/topic--*.md`, and `protocol_version` in `.along/VISION.md` frontmatter.
  - When `--protocol` is run **without** a toolchain bump (`bump_arg is None`), skip `update_along_milestones`, `update_changelog`, and release tag creation; if `--commit` is passed, commit protocol changes with `chore(protocol): ALONG-PROTOCOL v{new_proto_v}` without creating a toolchain release tag.
  - Remove dead regex substitutions targeting `migrate_protocol.py`, `along_kb_sync.py`, `along_update.py` (and `skills/` copies), `.well-known/`, and `Skills & Slash Commands (v...)`.
- **Acceptance**: `along version-bump patch` bumps toolchain only; `along version-bump --protocol minor` bumps protocol only; existing release engine flags (`-c`, `-p`, `-cp`, `-n --reason`, `--carry-over`) remain functional.

### Step 3: Diagnostics Alignment (`scripts/alongkit/commands/doctor.py`) (REQ-5)
- Keep `audit_subproject_protocol_versions(repo_root)` `mismatch` field backward-compatible (`str(not is_root and ver != root_ver)`).
- In `handle_doctor_command`:
  - Check root protocol version `root_v` using `version.is_protocol_supported(root_v)` **unconditionally** (outside `if len(sub_contexts) > 1:`) so single-root repos are also audited.
  - Emit `[WARN]` and increment `warnings` if root protocol version is outside `[MIN_SUPPORTED_PROTOCOL_VERSION, CURRENT_PROTOCOL_VERSION]`.
  - Keep existing `--- Subproject Protocol Versions ---` skew warnings when `len(sub_contexts) > 1`.
- **Acceptance**: `doctor` warns on unsupported root protocol in single-root repos and preserves subproject skew warnings.

### Step 4: Test Suite Adaptation & Hermetic Verification (REQ-6)
- `tests/test_skills_and_scripts.py`:
  - Update `test_04_protocol_version_consistency`: check `README.md` header against `CURRENT_VERSION`; check `AGENTS.md`, `protocol.md`, `.along/.protocol-version`, and `README.md` `ALONG-PROTOCOL v...` against `CURRENT_PROTOCOL_VERSION`; verify `pyproject.toml` `[tool.hatch.version]` pattern references `CURRENT_VERSION`.
- `tests/test_version_bump.py`:
  - Add hermetic dev-repo fixture tests for toolchain `patch` bump, `--protocol minor` bump, combined `-cp` / `--no-verify --reason` CLI parsing, and `is_protocol_supported`.
- `tests/test_lint_unstaged.py`:
  - Add test for `doctor` root protocol compatibility warning on unsupported version (e.g. `4.0.0`).
- **Acceptance**: All unit tests in `test_version_bump.py`, `test_release_engine.py`, `test_migration.py`, `test_lint_unstaged.py`, and `test_skills_and_scripts.py` pass, and `along hook verify --strict` / `along_kb_sync.py --strict` pass.
