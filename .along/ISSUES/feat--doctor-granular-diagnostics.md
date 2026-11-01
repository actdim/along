---
protocol: along
protocol_version: "4.5.4"
slug: doctor-granular-diagnostics
type: feat
status: open
priority: medium
created: 2026-10-30
updated: 2026-10-30
agent: antigravity
tags: [doctor, diagnostics, environment, health]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Granular environment diagnostic states in along doctor

Introduce a structured, multi-tier diagnostic classification into `along doctor` to clearly separate tool installation, configuration, network reachability, functional health, and credentials.

## Context and Problem Statement
Currently, `along doctor` performs largely binary checks (pass vs warning/error) for external tools, runtime hooks, and environment prerequisites. When an integration (e.g., git merge drivers, MCP servers, Telegram gateway, or agent CLI harnesses) is detected on the filesystem but lacks valid credentials or hangs during health probes, the agent or developer receives generic failure messages. Alternatively, a tool may be marked present ("OK") while failing downstream due to authorization or connectivity failures.

A clear 5-tier diagnostic model resolves ambiguity and allows deterministic automated remediation.

## Requirements
- REQ-1: `along doctor` diagnostic checks MUST classify external tool and runtime health into five distinct tiers:
  1. `registered`: Binary or script is discovered on PATH or in repository configuration.
  2. `configured`: Valid settings, flags, or manifests exist for the tool.
  3. `reachable`: Process launches or local socket responds within the diagnostic timeout.
  4. `healthy`: Basic smoke execution or version probe returns expected output code.
  5. `authorized`: Required API tokens, session credentials, or signatures are verified.
- REQ-2: CLI output of `along doctor` MUST display the exact tier status for each inspected component, avoiding misleading binary OK badges.
- REQ-3: Diagnostic guidance and automated suggestions (`--fix`) MUST target the earliest failing tier (e.g., prompt for authentication when reachable but unauthorized; prompt for PATH configuration when unregistered).
- REQ-4: Structured JSON export (`along doctor --json`) MUST serialize status objects using the 5-tier schema for machine consumption by orchestrators and dashboards.

## Acceptance Criteria
- [ ] 5-tier diagnostic status model defined and implemented in `scripts/alongkit/commands/doctor.py`
- [ ] Runtime and provider checks updated to evaluate all five tiers
- [ ] Targeted diagnostic suggestions printed per failing tier
- [ ] JSON output updated to include structured tier states
- [ ] Unit tests added covering tier transitions in `tests/test_alongkit.py`
