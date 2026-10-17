---
protocol: along
slug: gates-judge-results-not-commands
type: decision
title: "Gates judge results, not commands"
date: 2026-10-17
status: accepted
tags: [adr, architecture, decision, gates, hooks]
---

# ADR-2026-10-17--gates-judge-results-not-commands - Gates judge results, not commands

- Date: 2026-10-17
- Status: accepted
- Context: In three repositories 86% of gate events were `require_plan_approval` and 77% of all events were inquiry blocks on read-only shell commands. A 1700-line tool-nature classifier asked users to classify `git`, `python` and `findstr`, still missed scripts that delete files, and agents looped on identical blocks (up to 94 in one conversation). Whether a command writes is not decidable from its text; isolation is the container's job (docker-isolation-now-gvisor-later). Refines point 2 of gate-friction-fixes (read-only command lists, circuit_breaker as an invariant gate). [debt--gate-simplification]
- Decision:
  1. Gates decide only from exact facts: the target path of a file-writing tool, a short list of explicit destructive forms, and `git status`.
  2. Shell commands are never classified before they run. `require_plan_approval` snapshots the working tree at the user's message and, at Stop, holds the turn once when it changed files outside Along state and planning artifacts without an approved plan (ask the user: approve or revert).
  3. `destructive_command` covers recursive `rm` / `Remove-Item` / `del /s` / `rd /s`, `git clean -f`, `git reset --hard` and `git push --force`; it asks (interactive) or denies (autonomous) only when a target is outside the repository, empty, unexpandable or holds uncommitted work.
  4. Removed: the tool-nature classifier and `along tool`, `circuit_breaker` and `along circuit`, `fast_retrieval`, destructive/external confirmations. `cli_safety` only warns.
  5. Content rules (typography, stubs, AI co-authors, fences, links, filenames, secrets) run at commit and through `along lint`, not at runtime; their tags leave AGENTS.md.
  6. The audit log records a redacted `target` and `warn` for shadow records; `along gates stats` reports repeated identical blocks per conversation.
  7. A new runtime gate needs a problem observed at least twice, not catchable at commit, and must replace or merge an existing gate.
- Consequences: Read-only work raises no gate events and nothing asks the user to classify tools. A shell change without a plan is caught after it happened, not before; a script can still delete untracked work, and the container is the limit. Runtimes without a UserPromptSubmit hook get no end-of-turn check. Mode resolution (five layers) remains to be reduced in a follow-up.
