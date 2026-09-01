---
protocol: along
protocol_version: 2.2.8
slug: team-skill-uses-provider-specific-subagent-api
type: bug
status: open
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [along-team, multi-agent, provider-agnostic, subagents]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [team-skill-state-not-persisted, skill-commands-reference-missing-script-paths]
parent: protocol-quality-audit-remediation
---

# along-team is executable on only one of the four advertised providers

## Problem

`skills/along-team/SKILL.md` is the flagship orchestration skill. Its role definitions
prescribe a concrete subagent API:

```text
skills/along-team/SKILL.md:50   Execution: `invoke_subagent` with `TypeName: "research"`, `enable_write_tools: false`.
skills/along-team/SKILL.md:60   Execution: `invoke_subagent` with `TypeName: "self"`, `Role: "Implementer"`, `Workspace: "branch"` or `"inherit"`.
skills/along-team/SKILL.md:65   Execution: `invoke_subagent` with `TypeName: "self"`, `Role: "Code Reviewer"`.
skills/along-team/SKILL.md:126-136  JSON payload with "Subagents": [{ "TypeName": "research", ... }]
```

`invoke_subagent`, `TypeName`, `Workspace: "branch"`, and `enable_write_tools` are
Antigravity-specific. The other three advertised providers have different or absent
primitives:

- **Claude Code**: subagents are spawned through a different tool with different parameters
  (agent type, prompt, background execution); there is no `invoke_subagent`.
- **OpenAI Codex**: no equivalent subagent spawning primitive at all.
- **OpenCode**: skills are flattened to slash commands by `install.ps1` /
  `install.sh`; no subagent contract is defined.

The skill provides no capability mapping and no degradation path. On three of four
providers the agent reads instructions naming a tool it does not have, and improvises.

## Additional gaps

1. **No fallback contract.** The skill should define what happens when subagents are
   unavailable: run the same state machine single-agent, with the phases as explicit
   self-prompted stages, and say so.
2. **Reviewer gates depend on unavailable tooling.** The mandatory reviewer rubric
   (`SKILL.md:66-74`) requires `code-review-graph` MCP tools and
   `python scripts/along_exec.py test`. The MCP server is an unpinned third-party
   dependency that failed to connect during this audit
   (`code-review-graph (CONNECTION_CLOSED)`), and the script path does not resolve in
   consumer repositories. So the "Fail if any check fails" rubric degrades to a visual diff
   read, while still being described as mandatory.
3. **`Workspace: "branch"` implies git isolation** ("Merge branch workspace changes" in
   Phase 7) with no specification of branch naming, conflict handling, or cleanup.

## Impact

The provider-agnostic claim is the product's central differentiator, and the most
sophisticated skill is the least portable component in the repository. An agent on Claude
Code or Codex cannot execute the documented protocol as written.

## Requirements

- REQ-1: Introduce a provider capability abstraction in the skill: a named set of
  primitives (`spawn_readonly_researcher`, `spawn_worker`, `spawn_reviewer`) with a mapping
  table to each provider's concrete tool and parameters.
- REQ-2: Define the single-agent degradation path explicitly, including how phase
  boundaries, review verdicts, and retry counters are represented without subagents.
- REQ-3: Make every gate in the reviewer rubric conditional and observable: state what to do
  when `code-review-graph` is unavailable, and require the agent to record which gates ran
  and which were skipped in the session log.
- REQ-4: Specify the isolated-workspace contract (branch naming, merge strategy, cleanup on
  abort) or remove `Workspace: "branch"` from the skill.
- REQ-5: Replace all engine invocations with the canonical resolved entry point from
  `[bug--skill-commands-reference-missing-script-paths]`.
- REQ-6: Record an ADR for the provider abstraction, since it changes how all future skills
  express agent orchestration.
- REQ-7: Validation: for each provider, a documented smoke procedure (or automated check
  where a CLI exists) proving the skill's first two phases are executable.

## Acceptance Criteria

- [ ] Capability mapping table present for Claude Code, Codex, OpenCode, Antigravity.
- [ ] Documented single-agent fallback for providers without subagents.
- [ ] Reviewer rubric states behavior when MCP tools are unavailable, and requires
      recording which gates actually ran.
- [ ] ADR recorded.
- [ ] Smoke procedure documented per provider.
