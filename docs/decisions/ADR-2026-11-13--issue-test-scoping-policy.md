---
protocol: along
slug: issue-test-scoping-policy
type: decision
title: "Issue-Level Test Scoping and Verify Policy Invariants"
date: 2026-11-13
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-11-13--issue-test-scoping-policy - Issue-Level Test Scoping and Verify Policy Invariants

- Date: 2026-11-13
- Status: accepted
- Context: Repositories previously supported verify policies only at the repository level in .along/config.json (required | none). This forced full test suites on every wrap and commit, creating friction for focused changes. Furthermore, partial runs could not be distinguished from full runs, and test runs dirtying the tree caused silent failures of test reuse.
- Decision: Issue-level verify policy (required, affected, scoped, none) is taken exclusively from the plan-approval snapshot. Wrap never auto-bypasses pre-commit quality gates with -n. Scoped and affected test runs satisfy only requests with matching mode and scope; partial runs never satisfy a full request.
- Consequences: Reduces test runtime friction and unnecessary full-suite executions for scoped changes without sacrificing safety. Drift between frontmatter and approved plans is detected and rejected. Wrap outputs a hermeticity warning if the test run dirties the working tree.
