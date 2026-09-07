---
protocol: along
protocol_version: "2.2.25"
slug: github-copilot-integration
type: feat
status: open
priority: medium
created: 2026-09-07
updated: 2026-09-07
agent: antigravity
tags: [copilot, github, provider, mcp]
blocked_by: []
related: []
---

# GitHub Copilot Integration via copilot-instructions.md and MCP

## Context & Critical Technical Assessment
GitHub Copilot is widely used across VS Code, Visual Studio, and JetBrains. However, its architecture differs fundamentally from autonomous agent runtimes (Claude Code, Google Antigravity, OpenAI Codex, OpenCode):

### Key Architectural Differences & Trade-offs
1. **Passive vs Autonomous**: Copilot (chat and inline completion) is a reactive context consumer. It does not possess an autonomous living-plan state machine (`along-team`), cannot run background bash commands, execute test runners (`along test`), or manage git commit gates (`along commit`).
2. **Repository Instructions Mechanism**: GitHub Copilot explicitly reads repository-wide instructions from `.github/copilot-instructions.md` and prompt templates from `.github/prompts/*.prompt.md`.
3. **MCP Support**: VS Code Copilot Chat now supports MCP (Model Context Protocol) servers configured in `.vscode/mcp.json` or settings.
4. **Drift Risk**: Hardcoding project instructions directly into `.github/copilot-instructions.md` would create a 6th redundant protocol surface, violating the Single Source of Truth (SSOT) principle.

### Recommended Scope & Strategy
1. **Thin Pointer Scaffolding (`.github/copilot-instructions.md`)**:
   - `along-init` should scaffold `.github/copilot-instructions.md` as a lightweight pointer directing Copilot to read `AGENTS.md` and `docs/INDEX.md`.
   - Prevent documentation duplication while ensuring Copilot Chat and inline completions respect repository constraints and ADRs.
2. **VS Code Copilot MCP Integration**:
   - Provide documented setup or automated scaffolding for `.vscode/mcp.json` exposing `along-kb-search` and `code-review-graph` to Copilot Chat.
3. **Provider Classification (Tier-1 vs Tier-2)**:
   - Formally document GitHub Copilot in `docs/topic--architecture.md` as a **Tier-2 Passive Context Consumer**, distinguishing it from **Tier-1 Autonomous Agents** (Claude Code, Antigravity, Codex, OpenCode) that actively execute the Along lifecycle.

## Acceptance Criteria
- [ ] `along-init` optionally or automatically scaffolds `.github/copilot-instructions.md` pointing to `AGENTS.md` and `docs/INDEX.md`.
- [ ] Scaffolding is idempotent and does not overwrite existing custom instructions unless forced.
- [ ] `.github/copilot-instructions.md` is registered in `along_kb_sync` link integrity gates and source scanners.
- [ ] Documentation updated in `docs/topic--architecture.md` and `docs/topic--setup-and-workflow.md` detailing Copilot integration and MCP configuration.
- [ ] Automated tests added to verify `.github/copilot-instructions.md` creation and non-destructive behavior.
