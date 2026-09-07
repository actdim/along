---
protocol: along
slug: automated-ui-screenshots-and-visual-verification
type: feat
status: open
priority: medium
created: 2026-08-27
updated: 2026-08-27
agent: antigravity
tags: [ui, visual-testing, web, verification, screenshots]
milestone: v2.0.0-along-transition
blocked_by: []
related: [feat--agentic-code-review-and-impact-radius-assessment]
---

# Automated UI Screenshots & Visual Verification Attached to Issues

## Goal
Design and implement an automated visual capture mechanism for web and UI projects that enables agents to launch the local application or component preview, capture high-fidelity screenshots, and embed/attach them directly into issue acceptance logs (`.along/ISSUES/` / `.along/SESSIONS/`) as verifiable visual proof of delivery.

## Problem Statement
When agents build frontend features, UI components, or fix visual layout bugs, they often verify only static code or unit tests without visually inspecting the rendered DOM. Humans must manually run the dev server, navigate to the route, and verify visual appearance. Additionally, issue tracking lacks embedded visual artifacts demonstrating completed states over time.

## Key Capabilities & Architecture

### 1. Headless Browser / Web Automation Runner
- Provide a lightweight runner (e.g. Playwright, Puppeteer, or Chrome DevTools Protocol via Python/Node) to spin up a headless session against local dev servers (`localhost:3000`, `localhost:5173`, etc.).
- Support waiting for network idle or MSW mock handlers before capturing viewport.

### 2. Issue & Session Attachment Protocol
- Save captured screenshots into a dedicated directory: `.along/artifacts/screenshots/<slug>--<timestamp>.png`.
- Automatically embed Markdown image references (`![Visual Proof](../artifacts/screenshots/<slug>--<timestamp>.png)`) in:
  - The corresponding `.along/ISSUES/<type>--<slug>.md` under `## Visual Verification`.
  - The session log in `.along/SESSIONS/`.

### 3. Direct Invocation & Skill Integration
- Provide a direct slash command (e.g. `/along-shot` or `/along-verify-ui`) to trigger on-demand viewport capture:
  ```bash
  along verify-ui --url http://localhost:5173/dashboard --issue feat--project-dashboard
  ```
- Expose visual comparisons in the executive dashboard (`/along-dash`).

## Acceptance Criteria
- [ ] Visual verification capture runner specified and integrated.
- [ ] Standard convention for saving and embedding visual proof in `.along/ISSUES/` established.
- [ ] Slash command / CLI script implemented for capturing local web routes.
- [ ] Dashboard updated to preview attached visual verification assets.

