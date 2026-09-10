---
protocol: along
slug: external-issue-trackers-sync-and-import
type: feat
status: open
priority: medium
created: 2026-08-27
updated: 2026-09-10
agent: antigravity
tags: [integration, issue-tracking, jira, redmine, linear, github, import, backlog]
milestone: ~
blocked_by: []
related: [feat--openclaw-and-hermes-agent-integration]
---

# External Issue Trackers Integration & Bi-Directional Importer (Jira, Redmine, Linear, GitHub, GitLab)

## Goal
Design and implement an extensible issue import and synchronization bridge (`/along-import`) that enables teams to seamlessly import tasks, epics, and bugs from external trackers (Jira, Redmine, Linear, GitHub Issues, GitLab Issues) directly into `.along/ISSUES/` with automatic YAML front-matter mapping and relationship tracking.

## Problem Statement
While `Along` provides a zero-overhead local repository memory format (`.along/ISSUES/`), software engineering organizations maintain macro backlogs in central issue management systems (Jira, Redmine, Linear). Manually recreating external tickets as local `.along/ISSUES/` files creates friction, duplication of effort, and status drift between enterprise trackers and local agent sessions.

## Key Capabilities & Architecture

### 1. Pluggable Tracker Adapters
Implement a modular adapter interface (`scripts/along_import.py`):
- **Jira Adapter**: Fetch issues via Jira REST API v2/v3 using JQL queries (`project = PROJ AND sprint in openSprints()`).
- **Redmine Adapter**: Fetch issues and subtasks via Redmine REST API (`/issues.json?project_id=...`).
- **Linear Adapter**: GraphQL queries for assigned issues within the current cycle.
- **GitHub & GitLab Issues**: Fetch repository issues and milestone boards.

### 2. Schema Transformation & Metadata Mapping
Map external tracker fields to the canonical `Along` front-matter schema:
- **Type Mapping**:
  - `Bug`, `Defect` -> `type: bug`
  - `Story`, `Feature`, `New Feature` -> `type: feat`
  - `Tech Debt`, `Refactor` -> `type: debt`
  - `Task`, `Sub-task` -> `type: task`
- **Status Mapping**:
  - `To Do`, `Open`, `New` -> `status: open`
  - `In Progress`, `Active` -> `status: in-progress`
  - `Blocked`, `Waiting` -> `status: blocked`
  - `Done`, `Closed`, `Resolved` -> `status: done` (stored directly in `ISSUES/done/`)
- **Traceability Metadata**:
  - Store `external_tracker: jira | redmine | linear | github`
  - Store `external_id: PROJ-1042`
  - Store `external_url: https://jira.company.com/browse/PROJ-1042`

### 3. CLI & Slash Command (`/along-import`)
Provide an interactive command and CLI utility:
```bash
python scripts/along_import.py --from jira --jql "assignee = currentUser() AND statusCategory != Done"
python scripts/along_import.py --from redmine --project my-project --assigned-to me
python scripts/along_import.py --from github --repo org/repo --milestone "Sprint 14"
```
- Safe merge: avoids overwriting existing local modifications if `updated` timestamp is newer.
- Automatically updates `.along/ISSUES.md` board.

### 4. Status Sync-Back (Phase 2)
- Optional capability to push status transitions or comment links back to the external tracker when an Along issue is concluded (`status: done`).

## Acceptance Criteria
- [ ] Base importer architecture and CLI script created (`scripts/along_import.py`).
- [ ] Connectors implemented for Jira, Redmine, Linear, and GitHub.
- [ ] Automatic front-matter synthesis with `external_id` and `external_url`.
- [ ] Slash command `/along-import` skill added to `skills/along-import/`.
- [ ] Documentation added to `README.md` and `docs/`.

