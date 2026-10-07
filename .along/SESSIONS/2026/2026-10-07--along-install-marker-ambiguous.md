---
protocol: along
protocol_version: "4.4.6"
date: 2026-10-07
slug: along-install-marker-ambiguous
agent: claude-code
branch: main
commit: dec9a6e
summary: 'An Along installation is Along state, never an AGENTS.md: only along init creates one, board commands refuse outside it, folder guides untouched, package docs compile without .along, known-runner silence is no test run'
milestone: v4.5.0-multi-user-merge-automation
issues_advanced: []
issues_completed: [bug--along-install-marker-ambiguous]
decisions: [ADR-2026-10-07--along-installation-is-state-not-agents-md]
risks_logged: []
spikes_conducted: []
---

# Session: Along install marker ambiguous

## Summary
An Along installation is Along state, never an AGENTS.md: only along init creates one, board commands refuse outside it, folder guides untouched, package docs compile without .along, known-runner silence is no test run

## Decisions
- [ADR-2026-10-07--along-installation-is-state-not-agents-md]

## Blackboard Record

Execution mode: direct; plan revision 1; approved: true.

### Attributed Files

| Path | Kind | Edits | Last edit | Sessions |
| --- | --- | --- | --- | --- |
| `.along/DECISIONS/ADR-2026-10-07--along-installation-is-state-not-agents-md.md` | state | 1 | 2026-10-07T11:48:22Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `.along/GLOSSARY.md` | state | 1 | 2026-10-07T11:49:08Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `.along/ISSUES/bug--along-install-marker-ambiguous.md` | state | 2 | 2026-10-07T11:49:09Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--architecture.md` | docs | 1 | 2026-10-07T11:48:45Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--cli-reference.md` | docs | 1 | 2026-10-07T11:49:08Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `docs/topic--runtime-hooks-and-gates.md` | docs | 1 | 2026-10-07T11:48:45Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_exec.py` | source | 5 | 2026-10-07T11:33:21Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_history_sync.py` | source | 1 | 2026-10-07T11:32:49Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_kb_sync.py` | source | 1 | 2026-10-07T11:39:46Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/along_update.py` | source | 2 | 2026-10-07T11:39:13Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/hooks/config.py` | source | 1 | 2026-10-07T11:38:48Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/lifecycle.py` | source | 6 | 2026-10-07T11:40:20Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `scripts/alongkit/repo.py` | source | 7 | 2026-10-07T11:39:46Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_alongkit.py` | source | 1 | 2026-10-07T11:37:29Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_hooks_claude.py` | source | 3 | 2026-10-07T11:44:35Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_hooks_codex.py` | source | 2 | 2026-10-07T11:44:45Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_hooks_core.py` | source | 2 | 2026-10-07T11:44:45Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_hooks_generic.py` | source | 2 | 2026-10-07T11:38:18Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_install_marker.py` | source | 1 | 2026-10-07T11:41:06Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_lifecycle_test_evidence.py` | source | 1 | 2026-10-07T11:37:29Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_skills_and_scripts.py` | source | 3 | 2026-10-07T11:39:25Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_subproject_model.py` | source | 1 | 2026-10-07T11:37:30Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |
| `tests/test_update_and_hooks_hardening.py` | source | 1 | 2026-10-07T11:38:37Z | claude--be725b0a-d7a4-4583-8108-25f6e13c07c4 |

### Plan

#### Living Plan: along-install-marker-ambiguous

##### Revision 1 (2026-10-07T11:31:35Z, plan approve --plan-file)

#### Plan: bug--along-install-marker-ambiguous - approved by the user in chat on 2026-10-07 ("do it right now")

1. REQ-1 repo.py: positive STATE_ENTRIES list; is_along_state_dir needs a state entry; empty or
   side-effect-only .along/ is not installed; is_installed(dir).
2. REQ-2 ROOT_MARKERS drops AGENTS.md; find_repo_root stops at an installed context or .git;
   find_agent_contexts lists installed contexts only; lifecycle template fallback updated;
   writable_context_root folded into find_repo_root.
3. REQ-3 only along init starts a context: state-writing CLI commands exit 2 without an
   installation; lifecycle without installation runs the detected command and writes no hook;
   history-sync / wrap / commit guarded; diagnostics_dir uses is_installed.
4. REQ-4 kb-sync cascades into package doc roots (docs/ + AGENTS.md | llms.txt | manifest).
5. REQ-5 known runner with exit 0 and no summary = no tests ran.
6. Fixtures, docs, ADR along-installation-is-state-not-agents-md, glossary.

Execution Mode: Direct (fallback recorded).

### Execution Trace

#### Execution Trace: along-install-marker-ambiguous
- 2026-10-07T11:31:25Z edit .along/ISSUES/bug--along-install-marker-ambiguous.md
- 2026-10-07T11:31:35Z plan recorded: revision 1 (plan approve --plan-file)
- 2026-10-07T11:31:35Z plan approved (along plan approve)
- 2026-10-07T11:31:36Z Single-agent fallback: Central helper change in repo.py with guarded callers; user asked for immediate direct execution
- 2026-10-07T11:32:30Z edit scripts/alongkit/repo.py (x4)
- 2026-10-07T11:32:49Z edit scripts/alongkit/lifecycle.py
- 2026-10-07T11:32:49Z edit scripts/along_history_sync.py
- 2026-10-07T11:33:21Z edit scripts/along_exec.py (x5)
- 2026-10-07T11:33:36Z denied [test_before_stop] : Turn Completion Rejected [gate: test-before-stop]: Source files were modified in this session, but automated tests have not been executed afterward. Run test...
- 2026-10-07T11:33:49Z edit scripts/alongkit/lifecycle.py
- 2026-10-07T11:33:50Z edit scripts/alongkit/repo.py
- 2026-10-07T11:37:29Z edit tests/test_alongkit.py
- 2026-10-07T11:37:29Z edit tests/test_lifecycle_test_evidence.py
- 2026-10-07T11:37:30Z edit tests/test_subproject_model.py
- 2026-10-07T11:38:00Z denied [cli_safety] run_command: CLI Safety Gate Violation: In-place shell edit (sed -i / perl -i) detected in command: cd /d/Src/my/actdim/public/along; sed -i 's/os\.makedirs(along_dir, ex...
- 2026-10-07T11:38:16Z edit tests/test_hooks_claude.py (x2)
- 2026-10-07T11:38:16Z edit tests/test_hooks_codex.py
- 2026-10-07T11:38:17Z edit tests/test_hooks_core.py
- 2026-10-07T11:38:18Z edit tests/test_hooks_generic.py (x2)
- 2026-10-07T11:38:37Z edit tests/test_update_and_hooks_hardening.py
- 2026-10-07T11:38:48Z edit scripts/alongkit/hooks/config.py
- 2026-10-07T11:38:48Z edit scripts/alongkit/repo.py
- 2026-10-07T11:39:13Z edit scripts/along_update.py (x2)
- 2026-10-07T11:39:25Z edit tests/test_skills_and_scripts.py (x3)
- 2026-10-07T11:39:46Z edit scripts/alongkit/repo.py
- 2026-10-07T11:39:46Z edit scripts/along_kb_sync.py
- 2026-10-07T11:40:20Z edit scripts/alongkit/lifecycle.py (x4)
- 2026-10-07T11:41:06Z edit tests/test_install_marker.py
- 2026-10-07T11:44:35Z edit tests/test_hooks_claude.py
- 2026-10-07T11:44:45Z edit tests/test_hooks_codex.py
- 2026-10-07T11:44:45Z edit tests/test_hooks_core.py
- 2026-10-07T11:48:22Z edit .along/DECISIONS/ADR-2026-10-07--along-installation-is-state-not-agents-md.md
- 2026-10-07T11:48:45Z edit docs/topic--runtime-hooks-and-gates.md
- 2026-10-07T11:48:45Z edit docs/topic--architecture.md
- 2026-10-07T11:49:08Z edit docs/topic--cli-reference.md
- 2026-10-07T11:49:08Z edit .along/GLOSSARY.md
- 2026-10-07T11:49:09Z edit .along/ISSUES/bug--along-install-marker-ambiguous.md
- 2026-10-07T11:52:23Z test pass (Wrap Quality Gate)
