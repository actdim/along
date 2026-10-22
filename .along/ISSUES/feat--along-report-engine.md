---
protocol: along
protocol_version: "4.5.1"
slug: along-report-engine
type: feat
status: open
priority: medium
created: 2026-10-22
updated: 2026-10-22
agent: antigravity
tags: [reporting, verification, dod, artifacts, sharepoint, s3]
blocked_by: [feat--along-storage-providers]
related: [feat--along-webdev-runner]
---

# Universal Reporting Engine and Verification Delivery

## Goal
Design and implement a universal reporting engine for Along that transforms raw execution outputs, test runs, and agent findings into structured, stakeholder-ready reports (Markdown and standalone HTML). The engine acts as the formal Definition of Done (DoD) verification mechanism for tasks across all domains (web UI, backend services, CLI tools, audits), binds reports directly to their parent issue in `.along/ISSUES/`, and dispatches them to configured storage backends (Local/Git fallback, S3, SharePoint, Telegram).

## Problem Statement
In agentic workflows, work is anchored to issues, but verification artifacts are currently fragmented. Green unit tests alone do not provide verifiable proof of delivery (Proof of Delivery / Acceptance Proof) for stakeholders or team leads. There is no unified mechanism to:
1. Synthesize multi-step execution logs, visual evidence, metrics, and diagnostics into a single clean report.
2. Bind this report back to the initiating issue in `.along/ISSUES/` and the active `.along/SESSIONS/` entry.
3. Automatically publish the report and its media to stakeholder destinations (SharePoint, S3, or Telegram) while keeping Git clean.

## Architecture & Interfaces

### 1. Issue-Centric Workflow
- Every report is strictly bound to an active issue slug (`--issue <slug>`).
- In Along, `.along/ISSUES/<type>--<slug>.md` is the single source of truth for scope and acceptance criteria.
- When a report is compiled:
  - It references the issue's `## Acceptance Criteria`.
  - It assesses each criterion as SATISFIED or FAILED based on execution data.
  - It appends or updates the `## Verification & Delivery Report` section in the issue file, embedding links to published artifacts.

### 2. Report Data Contract & Generation (`scripts/alongkit/report/`)
- Standard input JSON schema (`ReportPayload`):
  ```json
  {
    "issue": "feat--checkout-flow",
    "title": "Checkout Flow Verification",
    "type": "acceptance",
    "status": "passed",
    "timestamp": "2026-10-22T16:30:00Z",
    "agent": "antigravity",
    "summary": "Verified complete user journey from cart to confirmation.",
    "metrics": { "duration_ms": 4200, "steps_total": 5, "steps_passed": 5, "network_errors": 0 },
    "steps": [
      {
        "index": 1,
        "name": "Navigate to catalog",
        "status": "passed",
        "evidence": { "screenshot": "step-1.webp", "dom_snapshot": null }
      }
    ],
    "diagnostics": {
      "console_errors": [],
      "failed_requests": []
    }
  }
  ```
- Output formats:
  - **Structured Markdown**: Compact, GitHub/Along-flavored markdown linked into issue and session files.
  - **Self-Contained HTML**: Clean, responsive single-file HTML report with embedded responsive image previews, collapsible error stacks, and audit metadata.

### 3. Report Types
- `acceptance`: Formal verification against issue criteria before closing (DoD proof).
- `audit`: Diagnostic or architectural deep dive (security scan, performance metrics, dependency health).
- `progress`: Intermediate state of large epic features.
- `regression`: Visual or functional regression comparison against a baseline.

### 4. Storage & Multi-Target Dispatch Integration
- Uses `along-storage-providers` abstraction:
  - **Local fallback**: Saves Markdown and images in `.along/artifacts/<slug>/` right next to the issue.
  - **Remote upload**: Uploads HTML and heavy media to S3 or SharePoint folder.
  - **Notification**: Posts summary preview + link to Telegram channel or team webhook.

### 5. CLI & Skill Integration
```bash
# Generate and publish report from a test/webdev run:
along report generate --input .along/artifacts/run-result.json --issue feat--checkout-flow --type acceptance

# Publish an existing report to specific targets:
along report publish .along/artifacts/checkout-report.html --issue feat--checkout-flow --target sharepoint,telegram

# Verification check (DoD gate for along wrap):
along report verify --issue feat--checkout-flow
```

## Acceptance Criteria
- [ ] Universal `ReportPayload` schema defined and validated.
- [ ] Markdown and standalone HTML report generators implemented in `scripts/alongkit/report/`.
- [ ] Issue linkage: automatic update of `.along/ISSUES/<type>--<slug>.md` with report references.
- [ ] Integration with `StorageProvider` for publishing to Local, S3, SharePoint, and Telegram.
- [ ] Verification gate: `along report verify` command enforcing report presence prior to issue wrap.
- [ ] CLI commands `along report generate` and `along report publish` implemented.
- [ ] Comprehensive unit tests for report formatting and issue-binding logic.
