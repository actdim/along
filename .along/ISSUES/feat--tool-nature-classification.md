---
protocol: along
protocol_version: "4.4.5"
slug: tool-nature-classification
type: feat
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [hooks, gates, config, rule-packs]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [bug--plan-gate-blocks-readonly-git]
---

# Classify tools by nature: one rule model for shell and agent tools, versioned layers

The plan gate decides on tools from a hardcoded list. That cannot scale: users install their
own CLIs and MCP servers, and they differ per agent and per machine. Every tool, shell command
or agent tool, must get a nature (class) from versioned, layered rules, and the protocol acts
by that class. Unknown tools are asked about, never silently allowed or denied.

## Current state (verified 2026-10-05)
- `predicates.check_mutation_authorization` inspects only shell tools and file-write tools.
  Any other tool (MCP servers, plugins, unknown agent tools) passes unchecked ("Other / unknown
  tools: do not block"), even if it writes or has external effects.
- Shell commands outside the built-in lists in `alongkit/hooks/shellparse.py` are held before
  plan approval (`gh pr view`, `kubectl get`, `jq`, ...). The lists are code; config cannot
  extend them. `shellparse` answers read-only yes/no, not a class (`git push` is just "not
  read-only").
- Per-repository gate options already exist: `load_config` / gate entries in
  `.along/rules/gates.yaml` (`workspace_containment`: `allowed_roots`, `write_scope`,
  `on_violation`; `require_plan_approval`: `enforce_unbound`). There is no global (user) layer
  and no tool rules.
- `~/.along/` is unversioned; anything recorded there is lost with the machine.

## Design (agreed 2026-10-05)

### Rejected: effect-based checks
Diffing the work tree after a call misses external side effects (push, deploy, API calls,
messages). At most a later safety net for workspace writes, never the basis.

### REQ-1: Classes and protocol rules
| Class | Examples | Rule |
| :--- | :--- | :--- |
| `read-only` | `gh pr view`, `kubectl get`, `jq` | allowed in every phase |
| `verification` | build, test, lint | allowed in every phase (as today) |
| `workspace-write` | generators, formatters | after plan approval |
| `external` | `gh pr merge`, deploy, push, send | after plan approval, asked every time |
| `destructive` | deletes outside the repo, drop database, run arbitrary code | always asked |

A compound shell command gets the most dangerous class among its segments.

### REQ-2: One rule model, two levels (no double standard)
- Level 1, call parsing (code, per transport): shell syntax (segments, redirections,
  substitutions) and MCP JSON arguments are normalized to tool + subcommand + arguments. This
  is a parser, not classification.
- Level 2, classification (same for every tool): ordered rules "tool + optional argument
  conditions -> class"; the first match decides. Conditions: subcommand (with wildcards and
  alternatives), flag present / absent, flag value, argument regex, MCP JSON field value.
- Shell structure rules stay code and apply to every command, user-classified ones too, and
  config cannot weaken them: a redirection into a file is always a write, a non-read-only
  substitution poisons the command. These are shell syntax, not tool properties.
- Today's git rules (`tag -l` vs `tag v1`, ...) are expressed in the same rule format; git has
  no special status.

### REQ-3: Three levels of where the nature lives
1. Name: single-operation MCP tools (`list_issues`, `create_issue`), simple utilities.
2. Verb or flag: most CLIs (`gh`, `kubectl`, `docker`, `git`, `curl -X`). Declarative rules
   are enough. "Depends on arguments" does not mean "needs code".
3. Embedded language: `sed` scripts, `python -c`, SQL, `bash -c`. Regex is unsafe here
   (`^SELECT` passes `SELECT 1; DROP TABLE x`). Needs a code classifier or a conservative class.

### REQ-4: Unknown tools: ask the nature, record it, learn incrementally
- The gate holds an unclassified tool with a reason that tells the agent to ask the user for
  its nature (not allow/deny) and record it: `along tool classify "<pattern>" <class>`.
- Answer "depends on arguments": the tool gets its most dangerous class as default, and the
  current form gets a refining rule (`kubectl` -> `destructive`, `kubectl get` -> `read-only`).
- The agent offers to generalize ("all `list|view|status|diff|checks` of `gh` read-only?").
- Tool self-description (MCP `readOnlyHint` / `destructiveHint`, verbs like `list`) is only a
  suggested default in the question, never trusted on its own.
- Unknown agent tools (MCP etc.) go through the same flow, closing today's pass-through.

### REQ-5: Versioned layers, nearest wins; no unmanaged location
1. Built-in (Along): rules and classifiers for common tools (`git`, `sed`, `awk`, `find`,
   `python -c`, later `gh`, `kubectl`, `docker`, `npm`). Today's `shellparse` lists move to a
   built-in rules file in the same format. Versioned, tested and maintained by Along; rules
   that many users need are proposed upstream (issue / PR) instead of staying personal.
2. Rule packs: a platform pack may ship tool rules and classifiers (`along rules attach`).
3. Global user layer: a personal pack `~/.along/user-pack/` that is a git repository managed by
   Along. `along tool classify` and classifier writes commit there automatically (history and
   rollback from day one); an optional remote syncs machines and restores after loss (dotfiles
   model). `along doctor` warns about no remote or uncommitted changes.
4. Repository: `.along/rules/gates.yaml` (tool rules) and `.along/classifiers/` (code),
   versioned with the project and shared with the team. Overrides the global layer.
- The agent never writes rules or classifier code anywhere else; a classifier is a task with
  test examples that the user approves like a plan.

### REQ-6: Code classifiers (plugins)
- Interface: a Python module with `classify(call) -> class | None` and a mandatory list of
  examples (call -> expected class). Built-in analyzers (`git`, `sed`, `awk`, `find`, `sort`,
  `python -c`) move to this interface and stay Along's.
- Trust: repository classifiers run only after `along tool trust`, pinned by hash; a changed
  file asks again (model: `direnv allow`, VS Code workspace trust). A cloned repository must not
  run code inside the hook on the first agent action.
- Fail closed: a classifier that raises, hangs or exceeds its timeout makes the tool unknown
  (ask), never allowed.
- `along tool explain "<command>"` prints the class and the rule or classifier that decided;
  `along doctor` runs every classifier's examples.

### REQ-7: Gates resolve through the repository's rules
`require_plan_approval` (and later other gates that care about tool effects) resolves the
class of each call through the layers of the repository the session works in (nearest
`.along/`, as for every other entity), then applies the REQ-1 rule. This extends the existing
per-repository gate options in `.along/rules/gates.yaml`; `load_config` gains the global
user-pack layer.

Which repository's rules apply when a hook fires (reuses `repo.find_hook_root` and
`subproject_context`):
1. File edit: the nearest `.along/` of the target file (a subproject edit follows the
   subproject's rules).
2. Shell command: the nearest `.along/` of the directory the command runs in, following `cd`
   and `git -C <dir>` inside the command when the path can be resolved.
3. No resolvable target (MCP tools, commands without a path): the session's repository (the
   one its bound issue belongs to).
4. Layer merge for the chosen repository, nearest wins: built-in -> rule packs -> global user
   pack -> repository -> nested subproject.
5. A tool acting on a remote system (`gh` against GitHub) is classified by the rules of the
   local repository where the hook fired, not by the remote it talks to.

## Example: `gh` introduced into a repository
1. In the inquiry phase the agent runs `gh pr list`; no rule for `gh` -> held, "unclassified".
2. The agent asks; the verb `list` suggests `read-only`. The user answers "depends on
   arguments": `gh` -> `destructive`, `gh pr list` -> `read-only`. The call passes.
3. The agent offers one rule for all read verbs of `gh`.
4. `gh api repos/x/pulls`: GET unless `-X` or `-f/-F/--input` (which silently make it POST):
   a flag condition, not code.
5. `gh api graphql -f query='mutation {...}'`: argument regex `^\s*mutation` -> `external`.
6. `gh extension exec`, `gh alias set`: run arbitrary code -> `destructive`, always asked.

```yaml
tools:
  gh:
    default: destructive
    rules:
      - match: { subcommand: "* list|view|status|diff|checks" }
        class: read-only
      - match: { subcommand: "api", no_flags: [-X, --method, -f, -F, --input] }
        class: read-only
      - match: { subcommand: "api", flag_value: { -X: "GET" } }
        class: read-only
      - match: { subcommand: "api graphql", arg_regex: "^\\s*mutation" }
        class: external
      - match: { subcommand: "pr create|pr merge|issue create" }
        class: external
```

## Phases
1. Class model; built-in rules file replaces the `shellparse` lists; `shellparse` and the git
   analyzers return classes; plan gate applies REQ-1. Repository layer in `gates.yaml`.
2. Unknown-tool flow for shell and agent tools (REQ-4); `along tool classify|list|explain`.
3. Global user pack as an Along-managed git repository (REQ-5.3), `along doctor` checks.
4. Code classifier plugins with trust and fail-closed (REQ-6), only once a real case needs a
   classifier that declarative rules cannot express.

## Acceptance Criteria
- [ ] Phase 1: classes returned for every shell segment; built-in rules in data; repository
      tool rules honoured by `require_plan_approval`; existing classification tests still pass
- [ ] Phase 2: unknown shell commands and agent tools held with an "ask the nature" reason;
      `along tool classify|list|explain`
- [ ] Phase 3: `~/.along/user-pack/` git-backed, auto-commit on classify, doctor warnings
- [ ] Phase 4: plugin interface, `along tool trust` with hash pinning, fail-closed, examples
      run by doctor
- [ ] Docs: `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--cli-reference.md`
- [ ] Automated tests passing (hermetic fixtures for every layer)
