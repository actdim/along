---
protocol: along
protocol_version: "3.7.0"
slug: deepseek-harness-bridge
type: feat
status: open
priority: medium
created: 2026-09-18
updated: 2026-09-18
agent: antigravity
tags: [deepseek-harness, dsh, hooks, bridge, providers, documentation]
milestone: v5.0.0-external-harness-expansion
blocked_by: []
related: [feat--runtime-enforcement-of-prose-rules, feat--pi-harness-support]
---

# DeepSeek Harness (DSH) Hooks Bridge & Provider Integration

## Problem
DeepSeek Harness (DSH, `dsh`) introduces bridge plugins (`@deepseek-ai/dsh-hooks-claude-code` and `@deepseek-ai/dsh-hooks-codex`) that mount existing `.claude/hooks.json` or `.codex/hooks.json` shell hooks directly to DSH internal interception points (`tools/pre-execute`, `agent/turn-stopping`, etc.). While Along already generates `.claude/settings.json` and `.codex/hooks.json` with mechanical gates (`TypographyGate`, `ProjectionProtectionGate`, `CliSafetyGate`), Along does not yet provide verified setup, automated configuration, or documentation for DSH:
1. Verification of wire protocol compatibility:
   - DSH relies on stdin payloads, exit code 0 (allow), and exit code 2 (deny/block) with stderr summaries.
   - Along's `scripts/along_hook.py` dispatcher must be tested and confirmed against DSH bridge specifications.
2. Configuration automation in CLI:
   - `along hook install` currently supports `--runtime {antigravity,claude,codex,cursor,all}`.
   - Users of DSH need either an explicit `--runtime dsh` target or automated generation of a `cordis.yml` patch connecting DSH to Along's existing hooks.
3. Documentation gaps:
   - DSH is not documented in `docs/topic--runtime-hooks-and-gates.md` or `docs/topic--cli-reference.md`.

## Requirements
1. Protocol & Execution Verification:
   - Validate that DSH's Claude Code and Codex hook bridges execute `along_hook.py` events without serialization failures.
   - Verify that exit code 2 gate denials correctly translate to DSH typed block decisions and that stderr messages are surfaced to the model.
2. CLI Hook Installer & Configuration Support:
   - Update `scripts/along_hook.py` and `alongkit/hooks/engine.py` to support DSH configuration (e.g. generating `cordis.yml` hook bridge config pointing to `.claude/hooks.json` or `.codex/hooks.json`).
   - Ensure installer and manifest engines remain unpolluted and maintain clean uninstall semantics.
3. Documentation:
   - Document DeepSeek Harness integration in `docs/topic--runtime-hooks-and-gates.md`.
   - Provide explicit `cordis.yml` examples and verification steps with `along hook eval` / `along hook verify`.
   - Add DSH to `docs/INDEX.md` and related topic articles.

## Acceptance Criteria
- [ ] DSH hook bridge compatibility with `along_hook.py` verified across PreToolUse and Stop events.
- [ ] `along hook install` provides verified DSH configuration or documentation recipe.
- [ ] `docs/topic--runtime-hooks-and-gates.md` includes dedicated section on DeepSeek Harness bridge.
- [ ] Tests covering hook dispatch and installer integrity pass without regression.
- [ ] `python scripts/along_kb_sync.py --check` passes cleanly.
