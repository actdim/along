---
name: along-wrap
description: Wrap up the current coding session or completed work stage by updating the repo's .along/ state - execute code review checklist, write a session log file, synchronize ISSUES.md projection, move completed issues to ISSUES/done/, append a HISTORY line, and record decisions/glossary terms. Use when ending work, wrapping up, or when invoking /along-wrap.
---

# Along Wrap
Universal finalization and memory synchronization protocol for sessions, tasks, and milestone stages.

## Scope & Nearest Placement (Strict Rule)
- **Always target the NEAREST `.along/`**: If the work was conducted in a subproject, Git submodule, or symlinked component (e.g. `packages/common/`, `libs/logger/`), execute wrap-up and write session logs, history, and issue updates directly in that subproject's `.along/`.
- Never pollute the parent workspace root `.along/` with subproject-internal bug fixes or tasks.

## When to Use
- The user or agent completes a feature, bugfix, stage, or ends a work session (triggers: "wrap up", "finish session", "close stage", `/along-wrap`, `/wrap`, `/along-wrap-session`, `/along-wrap-stage`).
- An active issue acceptance criteria have been verified and ready to close.

## Automated Wrap Engine (`along wrap`)

The mechanical synchronization steps (tests gate, moving the issue to `done/`, updating YAML front-matter, recompiling `ISSUES.md` and KB projections, purging the session blackboard, and appending to `HISTORY.md`) are executed transactionally in a single command:

```bash
along wrap <slug> --no-decisions [-m "Summary of completed work"]
along wrap <slug> --decisions ADR-2026-10-01--my-choice -m "Summary"
along wrap <slug> --no-decisions --dry-run
along wrap <slug> -s superseded --no-decisions
```
*(Or fallback: `python ~/.along/bin/along_exec.py wrap <slug> --no-decisions` or `along session wrap <slug> --no-decisions`)*

### Command Flags:
- `-d`, `--decisions "ADR-a,ADR-b"` or `--no-decisions` (one is required): Answer "were architectural decisions made in this session?". Create the ADRs first (`along decision create`). `--no-decisions` is an explicit confirmation, not a default.
- `--force-reason "<text>"`: Wrap a role-based (along-team) blackboard although steps are open or reviews are missing; the reason is recorded.
- `-s`, `--status <done|superseded|cancelled|duplicate>`: Terminal status to set in the issue front-matter (default: `done`).
- `-m`, `--summary "<text>"`: One-line summary appended to `.along/HISTORY.md`.
- `--dry-run`: Inspect planned actions without writing or moving files.
- `-n`, `--no-verify`: Skip pre-flight automated tests.
- `-a`, `--agent "<name>"`: Explicit agent name (defaults to detected agent).

---

## Mandatory Execution Flow

### Phase A: Cognitive Review (Agent)
1. **Code Review & Blast Radius Assessment**:
   - Inspect `git diff` for unintended side effects, unhandled nulls/errors, and edge cases.
   - Synchronize the AST code graph (`along graph-sync`) to reflect recent modifications.
   - Mandatorily evaluate systemic blast radius by running `/along-graph-impact` (or `along graph-impact`) across all modified files and symbols. Inspect direct callers, affected execution flows, and verify candidate test coverage.
   - Run `/along-graph-arch` (or `along graph-arch`) if module boundaries or subsystem imports were restructured to verify coupling invariants.
   - Factually update all affected `docs/topic--*.md` articles identified in the impact report before proceeding to Phase B.
2. **Session Log & Engineering Provenance**:
   - `along wrap` writes (or extends) `.along/SESSIONS/<YYYY>/<YYYY-MM-DD>--<slug>.md` in the issue's `.along/`, with `issues_completed: [<type>--<slug>]`, the decisions answer and the blackboard record (plan, step table, research, execution trace, reviews). Add the narrative (what changed, verification) to that file, before or after the wrap.
   - When orchestrating non-trivial multi-step tasks, compile the 3 Engineering Provenance sections: Baseline Plan, Execution Trace, and Verification Walkthrough.
   - **Decisions**: ask yourself whether the session made an architectural choice or trade-off. If yes, record ADRs (`along decision create`) and pass them with `--decisions`; otherwise pass `--no-decisions`.

### Phase B: Automated Finalization (CLI Engine)
3. **Execute Transactional Wrap**:
   - Run: `along wrap <slug> --no-decisions --summary "Concise summary of work"` (or `--decisions ADR-...`)
   - The engine automatically:
     - Runs pre-flight automated tests (halts if failing, leaving repo untouched).
     - Audits working tree for zero-byte corrupt files.
     - Sets `status: done`, `completed: YYYY-MM-DD`, `updated: YYYY-MM-DD` in issue front-matter.
     - Adjusts sibling issue markdown links and relocates issue file to `.along/ISSUES/done/`.
     - Recompiles `.along/ISSUES.md` projection board.
     - Runs `along kb sync` to compile Knowledge Base links and index.
     - Refuses while a role-based blackboard has open steps or passed steps without `reviews/step-N.md`.
     - Writes the session log with the blackboard record, then purges `.along/.session/<slug>/` and the agent-session bindings to it.
     - Appends formatted line to `.along/HISTORY.md` linking to the session log.
     - Protects all mutations with `alongkit.transaction.FileTransaction` (clean rollback on failure).

### Phase C: Clean Up
4. **Compaction Prompt**: Advise user to run `/compact` to free up token budget.


