---
protocol: along
protocol_version: "4.7.0"
slug: issue-drafts-lifecycle
type: feat
status: open
priority: medium
created: 2026-11-07
updated: 2026-11-07
agent: antigravity
tags: [drafts, lifecycle, issues, entity-management]
blocked_by: []
related: [feat--workspace-activity-tracking]
---

# First-Class Issue Drafts with Seamless Promotion and Lifecycle Guards

Introduce a dedicated, untracked drafts zone (`.along/.drafts/`) for formulating and refining issues in private before publication, featuring seamless promotion on start, wrap audits, and doctor hygiene checks.

## Context and Problem Statement

In multi-agent and fast-paced developer workflows, creating an issue directly inside `.along/ISSUES/` exposes an in-flight, unfinished task to the rest of the repository. Background schedulers, autonomous agent loops, or other team members can detect the new issue file or see updates in `ISSUES.md` before the author has finished specifying requirements and acceptance criteria.

Furthermore, drafting issues in `.along/ISSUES/` pollutes the Git commit history with intermediate drafts or typo-fixes, and runs the risk of colliding with concurrent test runs that validate issue schema.

Introducing a dedicated draft stage allows authors and agents to work on issue drafts safely outside Git tracking, with seamless one-step promotion when work actually begins.

## Requirements

- REQ-1 (Drafts Storage Isolation): Establish `.along/.drafts/` as an untracked directory explicitly listed in `.gitignore`. Entity walkers and projection compilers (`along issue sync`, `along kb sync`) MUST ignore `.along/.drafts/` by virtue of its dot-prefixed path.
- REQ-2 (CLI Draft Creation & Promotion):
  - Support `along issue draft <type>--<slug>` (and `along issue create --draft ...`) to scaffold draft markdown files with flexible frontmatter validation.
  - Support `along issue promote <slug>` to validate required schema fields, move the draft to `.along/ISSUES/<type>--<slug>.md`, and trigger projection sync.
- REQ-3 (Seamless Promotion on Start): If a developer or agent runs `along start <slug>` where `<slug>` exists in `.along/.drafts/`, Along MUST automatically validate the draft, promote it to `.along/ISSUES/`, set its status to `in-progress`, and bind the session in a single seamless operation.
- REQ-4 (Wrap Draft Guard): When `along wrap` runs, it MUST inspect `.along/.drafts/`. If unpromoted drafts exist, it MUST emit an informative warning listing the unpromoted slugs, ensuring ideas are not inadvertently abandoned.
- REQ-5 (Doctor Draft Audit): `along doctor` MUST inspect `.along/.drafts/` and report any abandoned drafts older than 7 days.
- REQ-6 (ASCII Typography and Testing): All code, documentation, and tests must adhere strictly to ASCII typography rules and be validated by hermetic unit tests.

## Acceptance Criteria

- [ ] `.along/.drafts/` added to `.gitignore`.
- [ ] `along issue draft` scaffolds new draft issues without publishing to `ISSUES.md`.
- [ ] `along issue promote` validates schema and promotes drafts into `.along/ISSUES/`.
- [ ] `along start <slug>` automatically promotes draft issues when starting work.
- [ ] `along wrap` reports unpromoted drafts to prevent forgotten ideas.
- [ ] `along doctor` flags stale drafts with actionable remediation tips.
- [ ] Unit tests verify drafting, promotion, and wrap warnings.
- [ ] Passes `python scripts/sanitize_typography.py --check` with 0 banned characters.
