---
protocol: along
slug: declarative-gates-and-traceability
title: Declarative Gate Engine & Protocol Traceability Matrix
type: architecture
created: 2026-09-13
updated: 2026-09-27
tags: [hooks, gates, declarative, traceability, verification, protocol, predicates]
sources:
  - path: scripts/alongkit/hooks/default_gates.yaml
  - path: scripts/alongkit/hooks/declarative.py
  - path: scripts/alongkit/hooks/predicates.py
  - path: scripts/alongkit/hooks/traceability.py
  - path: scripts/along_hook.py
---

# Declarative Gate Engine & Protocol Traceability Matrix

## 1. System Topology & Overview

Natural language guidelines and prose instructions in `AGENTS.md` and `skills/*/SKILL.md` are vulnerable to context truncation and probabilistic LLM compliance degradation. While runtime hooks provide interception at the agent harness boundary, hardcoded Python gates create maintenance overhead and opacity: agents and developers cannot easily inspect which prose instructions correspond to active enforcement logic.

The Along Declarative Gate Engine and Bi-Directional Traceability Matrix bridges this gap. It replaces opaque programmatic gates with an extensible, metadata-driven YAML gate catalogue (`scripts/alongkit/hooks/default_gates.yaml` and repository-level `.along/rules/gates.yaml`), paired with explicit inline prose badges (`[gate: <id>]`) embedded across protocol specifications and skill manifests.

```text
+-------------------------------------------------------------------------+
|                  Prose Specifications & Skill Manifests                 |
|  AGENTS.md, skills/along-init/protocol.md, skills/along-commit/SKILL.md |
|  Embedded Badges: [gate: <id>] (e.g. [gate: commit_issue_binding])      |
+-------------------------------------------------------------------------+
                                    |
                    Machine-Checked Bi-Directional Audit
                    (along hook verify / traceability.py)
                                    v
+-------------------------------------------------------------------------+
|                   Declarative Gate Engine Catalogue                     |
|  scripts/alongkit/hooks/default_gates.yaml                              |
|  .along/rules/gates.yaml (repository overrides)                         |
+-------------------------------------------------------------------------+
       |                                                    |
       v (Regex/Match rules)                                v (Stateful predicates)
+----------------------------+             +------------------------------+
| Declarative Content Gates  |             | Stateful Predicates Engine   |
| - anti_stub_injection      |             | - require_active_issue       |
| - cli_safety               |             | - test_before_stop           |
| - projection_protection    |             | - wrap_before_stop           |
| - typography               |             | - projection_sync_before_stop|
| - commit_issue_binding     |             | - subproject_boundary        |
| - commit_no_conflict_marker|             +------------------------------+
+----------------------------+                            |
               \                                         /
                v                                       v
+-------------------------------------------------------------------------+
|                         Runtime Hook Execution                          |
|         Universal Dispatcher: scripts/along_hook.py                     |
|         Runtimes: Antigravity, Claude Code, OpenAI Codex                |
+-------------------------------------------------------------------------+
```

---

## 2. Core Components & Engine Implementation

### 2.1 Declarative Schema & Gate Catalogue (`default_gates.yaml`)

Gates are declared in YAML format with standard schema fields:
- `id`: Canonical identifier matching prose badges (e.g., `commit_issue_binding`).
- `description`: Human-readable summary of the invariant.
- `event`: Lifecycle trigger event (`PreToolUse`, `PostToolUse`, `Stop`).
- `decision`: Action on match (`deny`, `ask`, `force_ask`).
- `target_tools`: List of tools intercepted (e.g., `run_command`, `write_to_file`).
- `match_type`: Evaluation strategy (`regex`, `predicate`, `composite`).
- `patterns`: Regex patterns for argument matching (for `regex` matchers).
- `predicate`: Name of python predicate handler in `alongkit.hooks.predicates`.
- `remediation`: Explicit remediation message returned to the agent on violation.
- `enforcement`: Layers that enforce the gate, any of `runtime` (agent hooks, the default), `git` (opt-in `along hooks install --git`), `ci` (`along gates check --ci`). An unknown layer is a schema error. `alongkit.gitgates` reads its patterns (issue binding, anti-stub) from the same entries, so the layers cannot disagree. `along hook verify` prints the resulting matrix.

The 25 canonical gates defined in the catalogue:
1. `commit_issue_binding`: Intercepts `git commit` to require issue binding: `[<type>--<slug>]` or `(refs #<slug>)`, the form `/along-commit` appends. In git/CI mode, subjects starting with `release: `, `Merge `, `Revert "`, `fixup! `, `squash! ` are exempt.
2. `commit_no_conflict_markers`: Intercepts `git commit` and inspects the lines the commit would add (`git diff --cached`, or `git diff HEAD` for `commit -a`) for unresolved merge conflict markers at line start (`<<<<<<< `, `=======`, `>>>>>>> `). The commit message itself is not inspected, so a Markdown rule of `=======` in a message is allowed. No file class is exempt: `merge=union` files never receive markers from git, so a marker there is a real conflict too.
3. `anti_stub_injection`: Intercepts file mutation tools to forbid stub markers and lazy truncation skeletons.
4. `cli_safety`: Intercepts shell commands to block heredocs (`<<EOF`), inline python file writers, destructive wipes (`git reset --hard`), and global installs.
5. `projection_protection`: Intercepts file writes to derived projections (`.along/ISSUES.md`, `docs/INDEX.md`, `DECISIONS.md`).
6. `typography`: Intercepts text writes to enforce ASCII typography (no em-dashes, curly quotes, guillemets, ellipsis glyphs, or NBSP).
7. `require_active_issue`: Stateful predicate requiring an active `in-progress` issue in `.along/ISSUES/` bound to the current session.
8. `test_before_stop`: Intercepts session termination (`Stop`) to ensure `/along-test` or test suites ran cleanly if code was modified.
9. `wrap_before_stop`: Intercepts session termination (`Stop`) to ensure a session log exists if an issue was marked done.
10. `projection_sync_before_stop`: Intercepts session termination (`Stop`) to require `/along-issue-sync` if issue files changed.
11. `subproject_boundary`: Enforces context localization in monorepos, preventing subproject entities from leaking to workspace root `.along/`.
12. `worktree_env_readiness`: Verifies dependency junctions and environment config propagation before worktree tool execution.
13. `circuit_breaker`: Hard stop that halts mutating commands and edits upon systemic environment anomalies.
14. `require_plan_approval`: Blocks repository file mutations and mutating shell commands in inquiry mode without an approved plan.
15. `commit_no_ai_coauthor`: Intercepts `git commit` and denies a message (command line or `-F` file) carrying a `Co-Authored-By:` trailer that names an AI agent. Human co-authors pass. Opt-out: `.along/config.json` `commits.allow_ai_coauthor: true`. See [Runtime Hooks & Gates](./topic--runtime-hooks-and-gates.md).
16. `workspace_containment`: Keeps file, search and shell `Cwd` paths inside the workspace (`alongkit.hooks.containment`). Paths are canonicalized with `os.path.realpath`, so `..` and symlinks cannot escape. Writes are allowed in the workspace (limited to `write_scope` plus `.along/` when declared), the system temp dir, the runtime brain dir of the current conversation and `~/.claude/projects/`. Reads are also allowed in declared `allowed_roots`, a worktree's main checkout, and the read-only global dirs `~/.gemini`, `~/.claude`, `~/.codex`, `~/.along`. Credential stores (`~/.ssh`, `~/.aws`, ...) are never accessible. A write outside scope is denied. A read outside scope returns `ask` in interactive mode and `deny` in autonomous mode (Claude Code `bypassPermissions`, `ALONG_AUTONOMOUS=1`, or `on_violation: deny`). Runtimes without an ask channel receive `deny` (the engine converts `ask` for every runtime except Antigravity). Scopes come from the gate options, the in-progress issue frontmatter (`allowed_roots`, `write_scope`) and `along start --allow-root/--write-scope`.

Repository-state gates (17-23) declare `enforcement: [git, ci]` and no runtime layer, so the runtime pipeline skips them. `along gates check` runs their `alongkit.repochecks` handlers over the staged blobs (pre-commit) or every tracked file (`--ci`). A line containing `along: allow-<gate-id>` is exempt (for fixtures), and `exclude_paths` (fnmatch globs) exempts whole files:

17. `windows_safe_filenames`: No `<>:"|?*`, control characters, trailing dot/space or reserved device names (`CON`, `NUL`, `COM1`, ...) in any path component.
18. `untracked_exports`: `.along/dashboard.html` and `.along/DASHBOARD.md` are never tracked.
19. `code_fence_language`: Every opening Markdown code fence names a language (`text` for plain output).
20. `portable_links`: Markdown link targets use no `file://` scheme and no backslashes. Inline code and fenced blocks are ignored.
21. `stable_entry_point`: Files in `scope` (default `README.md`, `docs/*`) never link into `.along/`.
22. `issue_lifecycle`: Closed issues (`done`, `cancelled`, `superseded`, ...) live in `.along/ISSUES/done/`; open, in-progress or blocked ones never do.
23. `no_tracked_secrets`: No private key headers or well-known token shapes (AWS, GitHub, Anthropic, OpenAI, Slack, Google).

The entity graph gate spans all three layers:

24. `entity_reference_integrity`: `alongkit.entities.validate_entities` finds no dangling reference (`related`, `blocked_by`, `parent`, `superseded_by`, `duplicate_of`, `milestone`, `target_issues`, session `issues_*`) and no schema or enum violation. References resolve in the nearest `.along/` and in enclosing contexts up to the git root. Runtime: a `Stop` predicate once git reports a changed entity file; `along wrap` (rolls back) and `along issue sync` (exit `1`) call `alongkit.gates.entity_integrity_gate`, which only warns in `shadow` mode. Git/CI: `along gates check` and `along commit` validate a snapshot of the staged (or checked-out) `.along/` against HEAD (or the range base) and block only problems the change introduces; pre-existing ones are printed as a notice. Renaming or retiring a referenced issue goes through `along issue rename` / `along issue supersede`, which rewrite the inbound references.

The managed rule pack gate also spans all three layers:

25. `rule_pack_protection`: Managed rule packs (`.along/rules/**/*.md` in any `.along/`) belong to `along rules attach`. Runtime: denies file-tool writes to them and shell commands whose non-read-only segment names one (`along rules ...` is exempt); `.along/rules/gates.yaml` stays editable. Git/CI: `alongkit.gitgates.check_rule_packs` runs `repochecks.check_rule_pack_integrity` over staged (or tracked) rule packs, which must carry the managed header with a body matching its `sha256`. The gate's catalogue rule is the runtime predicate, so the repository-state loop does not run it. Project guidelines go to `docs/topic--<slug>.md` or `AGENTS.md` "Project specifics"; `along rules restore` reverts a pack.

Gate options: keys of a gate entry other than the definition keys (`id`, `title`, `description`, `event`, `tools`, `match_args`, `rule(s)`, `enforcement`, `enabled`) are passed to predicate handlers as `options=`. A `.along/rules/gates.yaml` entry whose `id` names a built-in gate is merged into it: keys it sets win and the rest is inherited, so an entry can just add options or set `enabled: false`:

```yaml
gates:
  - id: workspace_containment
    allowed_roots: ["../contracts", "../shared-lib"]
    write_scope: ["packages/auth"]
    on_violation: deny      # auto (default) | ask | deny
```


### 2.2 Stateful Predicate Handlers (`alongkit.hooks.predicates`)

While regex gates evaluate single tool calls in isolation, complex invariants require session state:
- `record_tool_activity()`: Records executed commands and modified paths into `.along/diagnostics/activity_trace.jsonl`.
- `load_activity_trace()`: Reconstructs session tool call history to evaluate post-conditions.
- Predicate functions (`check_require_active_issue`, `check_test_before_stop`, `check_wrap_before_stop`, `check_projection_sync_before_stop`, `check_subproject_boundary`) return a violation message string or `None`.

### 2.3 Bi-Directional Traceability Scanner (`alongkit.hooks.traceability`)

The traceability engine guarantees zero drift between written instructions and active enforcement:
- `scan_prose_anchors()`: Parses Markdown files across `AGENTS.md` and `skills/*/SKILL.md` using regex `r"\[gate:\s*([a-zA-Z0-9_-]+)\]"`.
- `audit_traceability()`: Correlates prose anchors against active gates loaded from YAML.
  - Reports missing anchors (gates defined in YAML with no prose badge).
  - Reports dangling badges (badges in prose with no corresponding YAML gate).
  - Returns boolean pass/fail status.
- CLI verification: `along hook verify` (or `python scripts/along_hook.py verify`) runs the audit and outputs a structured matrix report.

---

## 3. Data Flow & Execution Workflow

### 3.1 Declarative Gate Evaluation Flow

```text
[Tool Invocation Event]
          |
          v
[Declarative Engine: load_gates()]
  Reads: scripts/alongkit/hooks/default_gates.yaml
  Reads: .along/rules/gates.yaml (if present)
          |
          v
[Filter Gates by event_type and target_tools]
          |
   +------+------+
   |             |
(Regex)     (Predicate)
   |             |
   |             +--> [Execute alongkit.hooks.predicates]
   |                  Reads repository state & activity trace
   v                  Returns violation string or None
[Regex Match on Args]    |
   |                     |
   +----------+----------+
              |
         (Violation?)
          /        \
        YES         NO
         |           |
         v           v
    [GateResult:   [GateResult:
     DENY]          ALLOW]
```

### 3.2 Machine-Checked Traceability Verification Flow

```text
[Developer / Agent invokes: along hook verify]
                       |
                       v
         [audit_traceability(repo_root)]
          /                           \
         v                             v
[Parse Prose Badges]          [Load Declarative Gates]
AGENTS.md, skills/*/SKILL.md   default_gates.yaml + gates.yaml
         \                             /
          v                           v
         [Cross-Reference Badges <-> Gate IDs]
                       |
        +--------------+--------------+
        |                             |
 (Clean 1:1 Match)             (Drift Detected)
        |                             |
        v                             v
[Verdict: PASSED]             [Verdict: FAILED]
Exit Code: 0                  Exit Code: 1 (lists missing/dangling)
```

---

## 4. Invariants & Failure Modes

1. **Strict Bi-Directional Traceability Invariant**:
   - Every active gate in `default_gates.yaml` MUST have at least one corresponding `[gate: <id>]` badge in prose documentation (`AGENTS.md` or `skills/`).
   - Every `[gate: <id>]` badge in documentation MUST map to an active gate in the catalogue.
   - `along hook verify` MUST exit with code 0 in CI and local test suites (`tests/test_gates_traceability.py`).
2. **Deterministic Isolation**:
   - Predicate handlers and file parsers use narrow exception handling `(OSError, UnicodeDecodeError, ValueError)`. Generic exceptions (`except Exception:`) and unhandled crashes are forbidden.
3. **Repository Extensibility**:
   - Projects can extend or override default gates by adding `.along/rules/gates.yaml`.
   - Repository-specific gates are merged with `default_gates.yaml`, allowing local project rules to participate in declarative verification.
4. **Hermetic Test Guarantees**:
   - All tests for declarative gate loading, predicate evaluation, and traceability verification run strictly within throwaway temporary directories (`tempfile.mkdtemp()`).
