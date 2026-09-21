---
protocol: along
protocol_version: "3.9.0"
slug: workspace-containment-and-path-scoping
type: feat
status: open
priority: high
created: 2026-09-21
updated: 2026-09-21
agent: antigravity
tags: [runtime, gates, security, isolation, workspace-containment, hooks]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: []
---

# Runtime Workspace Containment Gate and Granular Path Scoping

## Problem
In autonomous ("YOLO") mode, agents frequently drift outside the designated repository workspace when exploring code or resolving context (for example, invoking `find_by_name`, `grep_search`, or `view_file` on sibling repositories, user home directories, or root paths).

1. **Prompt Instruction Decay**:
   Prose instructions in `AGENTS.md` and system prompts decay over long conversation transcripts and cannot deterministically prevent an agent from wandering into external directories.
2. **Breakage from Naive Path Containment**:
   A naive check (`path.startswith(repo_root)`) breaks essential agent runtime functions:
   - **Brain Artifacts and Plans**: Antigravity writes plans and conversation artifacts to `~/.gemini/antigravity/brain/<conversation-id>/`.
   - **Hermetic Testing and Temp Dirs**: Automated tests require `tempfile.gettempdir()` for throwaway fixtures.
   - **Global Skills and Configurations**: Agents must read `SKILL.md` from `~/.gemini/antigravity/builtin/skills/...` or `~/.claude/...`.
3. **Blind Code Generation from Subfolder Siloing**:
   Restricting read access to a narrow subfolder prevents the agent from reading imported shared types, project configurations (`tsconfig.json`, `package.json`), or root manifests, leading to type errors, code duplication, and error loops.

## Architecture and Requirements

### 1. New Declarative Gate: `workspace_containment` (`[gate: workspace-containment]`)
Register `workspace_containment` in `scripts/alongkit/hooks/default_gates.yaml` and implement the predicate handler in `alongkit.hooks.predicates.check_workspace_containment`:
- Intercepts `PreToolUse` for file tools (`view_file`, `write_to_file`, `replace_file_content`, `list_dir`, `find_by_name`, `grep_search`) and shell tools (`run_command`, `execute_command`, `bash`, `shell`).
- Canonicalizes all input paths using `os.path.realpath` to prevent directory traversal (`..`) and symlink bypasses.

### 2. Read vs. Write Boundary Asymmetry
Enforce different containment rules for reading and writing:
- **Write Scope (Strict)**:
  - Allowed only within the governed workspace root (or specific subproject/subfolder if declared via `write_scope`).
  - Writes outside the workspace are rejected, with explicit exceptions for the brain artifacts directory and system temp directory.
- **Read Scope (Permissive within declared roots)**:
  - Allowed across the governed workspace and any explicitly declared `allowed_roots`.
  - Prohibited from accessing arbitrary filesystem roots (`/etc`, `C:\Windows`), user home directories (`~/.ssh`, `~/.aws`), or undeclared sibling repositories.

### 3. Sensible Defaults (Zero-Config Built-in Whitelist)
The gate must function out-of-the-box without manual configuration by including sensible defaults:
- **Workspace Root**: Current repository root, subprojects, and active Git worktrees (read/write).
- **Brain Artifacts**: `<appDataDir>/brain/<conversation-id>/**` (read/write for plans, walkthroughs, scratchpads).
- **System Temp**: `tempfile.gettempdir()/**` (read/write for hermetic test execution).
- **Global Skills and Rules**: `~/.gemini/**`, `~/.claude/**`, `~/.codex/**` (read-only for reading skill manifests; write operations blocked).

### 4. Granular Multi-Root Configuration
Support explicit declaration of multiple allowed roots:
- **Repository Configuration (`.along/rules/gates.yaml`)**:
  ```yaml
  gates:
    - id: workspace_containment
      enabled: true
      allowed_roots:
        - "../contracts"
        - "../shared-lib"
      write_scope:
        - "packages/auth"
  ```
- **Issue Frontmatter**:
  Support `allowed_roots: [...]` and `write_scope: [...]` in the active issue file (`.along/ISSUES/<type>--<slug>.md`).
- **CLI Options**:
  Support `--allow-root <path>` and `--write-scope <path>` in `along start`.

### 5. Shell Command Containment
- Validate the `Cwd` parameter of `run_command` against `allowed_roots`.
- Deny execution if `Cwd` points outside allowed roots.

### 6. Mode-Aware Decision Routing
- **Interactive Mode**: Return `GateDecision.ASK` when an unlisted path is requested, prompting the user for confirmation.
- **Autonomous / YOLO Mode**: Return `GateDecision.DENY` immediately to prevent runaway path traversal.

## Acceptance Criteria
- [ ] Gate `workspace_containment` defined in `default_gates.yaml` and verified by `along hook verify`.
- [ ] Canonical path resolution (`os.path.realpath`) eliminates `..` traversal and symlink bypasses.
- [ ] Built-in whitelist allows brain artifacts, temp dir, and global skills without manual configuration.
- [ ] Multi-root lists in `.along/rules/gates.yaml` and issue frontmatter correctly expand allowed read/write scopes.
- [ ] Write attempts outside workspace root (and outside brain/temp) are strictly blocked.
- [ ] Read attempts outside declared roots trigger `deny` in autonomous mode.
- [ ] Comprehensive hermetic unit tests in `tests/test_workspace_containment.py` pass cleanly.
