---
protocol: along
slug: feedback-inbox-and-pr-transport
type: decision
title: "Feedback Inbox Location and GitHub PR Transport"
date: 2026-11-13
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-11-13--feedback-inbox-and-pr-transport - Feedback Inbox Location and GitHub PR Transport

- Date: 2026-11-13
- Status: accepted
- Context: User feedback from client repositories needs to land directly in the Along repository without requiring custom microservices or manual harvesting from issues.
- Decision: Place feedback notes under .along/inbox/ as tracked Markdown files with front-matter. Target PRs directly against main branch, avoiding orphaned base branches.
- Consequences: Inbox files do not clutter the active ISSUES board until maintainers triage them. Standard PR review flow applies.
