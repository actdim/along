# Living Plan: bug--antigravity-manifest-matcher-unenforceable-invariants

Execution Mode: Direct (bug fix scoped to runtime hook matchers, adapter tool maps, preflight path expansion, and doctor manifest auditing; plan pre-approved by user)

## Context

`get_antigravity_hook_manifest()` (`scripts/alongkit/hooks/config.py`) previously emitted a hardcoded 3-tool matcher (`write_to_file|replace_file_content|run_command`), preventing Antigravity from ever invoking `along_hook.py` for read, search, list, delete, or subagent tools declared in `default_gates.yaml` (including `tier: invariant` gates `workspace_containment` and `entity_deletion_protection`).

Sibling manifests had matching gaps:
- `get_codex_hook_manifest()` only matched writes and shells (excluding deletes, reads, searches, lists, subagents, and shell `PostToolUse`).
- `CLAUDE_PRE_TOOL_MATCHER` omitted `LS`, `Task`, `Agent`, `TodoWrite`, and canonical aliases despite `ClaudeCodeAdapter` mapping them.
- `DSH_PRE_TOOL_MATCHER` omitted `list_dir` and delete/canonical names.
- `get_cursor_hook_manifest()` had no matcher, while `GenericCliAdapter.TOOL_NAME_MAP` omitted Cursor's native tool names (`Shell`, `Read`, `Grep`, `Glob`, `LS`, `StrReplace`, etc.) and `along doctor` did not report Cursor's narrowing or audit installed manifests for missing gate tools.
- `alongkit.hookpreflight.is_workspace_read()` did not call `os.path.expanduser()` before `os.path.isabs()`, so a `~`-prefixed credential path like `~/.ssh/id_ed25519` would be treated as workspace-relative and allowed before reaching `HookEngine`.

## Steps

- [x] Step 1: Derive runtime gate tool union and align all runtime hook manifests (`scripts/alongkit/hooks/config.py`)
  - Add `runtime_gate_tool_union(gates_file=None, event_type=None)` reading `default_gates.yaml` for all enabled gates whose `enforcement` includes `runtime`.
  - Build `PreToolUse` and `PostToolUse` matchers via shared helpers (`build_pre_tool_matcher`, `build_post_tool_matcher`) across Antigravity, Claude Code, Codex, Cursor, and DSH (keeping DSH free of Claude-only capitalised names `Write|Edit|Bash|Read|Glob|Grep`).
  - Record explicit runtime narrowing metadata (`RUNTIME_HOOK_NARROWINGS`) and implement `audit_manifest_coverage()` / `audit_installed_hook_manifests()`.
- [x] Step 2: Close adapter and preflight gaps (`adapters/*.py`, `hookpreflight.py`, `predicates.py`)
  - Expand `GenericCliAdapter.TOOL_NAME_MAP` with Cursor's own names (`Shell`, `Read`, `Grep`, `Glob`, `LS`, `StrReplace`, `run_terminal_cmd`, etc.) and canonical tools; normalize `workspace_roots`, extra path keys, and `beforeReadFile`.
  - Expand `CodexAdapter.TOOL_NAME_MAP` (and path/workspace normalization), `ClaudeCodeAdapter.TOOL_NAME_MAP` (`SendMessage`), `DeepSeekHarnessAdapter.DSH_TOOL_NAME_MAP`, and `AntigravityAdapter.parse()` fallbacks.
  - Fix `hookpreflight.is_workspace_read()` to call `os.path.expanduser()`, match `containment.PATH_ARG_KEYS`, check `workspace_roots`, and fall through on absolute/home-relative search patterns.
  - Include `AbsolutePath`, `TargetPath`, `target_path` in `predicates._extract_all_target_paths()`.
- [x] Step 3: Report manifest matcher gaps and Cursor narrowing in `along doctor` (`runtime.py`, `commands/doctor.py`)
  - Surface `audit_installed_hook_manifests(repo_root)` warnings for stale/narrow installed manifests and report Cursor narrowing when `agent == "cursor"` or Cursor hooks are installed.
- [x] Step 4: Update documentation and add comprehensive hermetic and payload-level tests
  - Update `docs/topic--runtime-hooks-and-gates.md` for accurate matcher, Cursor, and doctor behavior; run `along kb sync` if needed.
  - Add `tests/test_hook_manifest_coverage.py` covering REQ-1..REQ-4 (superset invariant over `default_gates.yaml` across all installed runtimes, synthetic new-gate failure assertion, `along_hook.py --runtime antigravity` payload tests for `view_file` `~/.ssh/id_ed25519` and `delete_file` `.along/ISSUES/*.md`, Cursor/Codex/Claude/DSH payload tests, and `along doctor` reporting).
  - Run targeted tests, full test suite, and `along sanitize`.
