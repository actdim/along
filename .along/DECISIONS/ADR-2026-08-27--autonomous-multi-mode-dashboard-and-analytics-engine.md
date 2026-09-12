---
protocol: along
slug: autonomous-multi-mode-dashboard-and-analytics-engine
title: "Autonomous Multi-Mode Repository Dashboard & Analytics Engine"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--autonomous-multi-mode-dashboard-and-analytics-engine - Autonomous Multi-Mode Repository Dashboard & Analytics Engine

- Date: 2026-08-27
- Status: accepted
- Context: Developers and agents require instant visibility into entity lifecycles, milestone completion rates, active blockers, and dependency DAGs without manual data compilation or heavy infrastructure.
- Decision:
  1. Implement an autonomous Python script (`scripts/along_dash.py`) using PEP 723 inline dependencies (`# /// script ...`) executable directly via `uv run scripts/along_dash.py`.
  2. Provide 4 decoupled operational modes in a single codebase: CLI Mode, Interactive Web Mode, Static HTML Export, and Markdown Dashboard Report (`.along/DASHBOARD.md`).
  3. Expose the `/along-dash` skill across Claude Code, Codex, OpenCode, and Antigravity.
- Consequences: Zero setup cost, instant offline/online dashboard visualization across all execution environments.
