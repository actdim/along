---
protocol: along
protocol_version: "4.4.6"
slug: release-ci-precondition-check
type: feat
status: open
priority: medium
created: 2026-10-07
updated: 2026-10-07
agent: claude
tags: [release, ci, gates]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
related: [task--ci-test-matrix-workflow, bug--release-tags-not-pushed]
---

# Release checks CI status of the released commit

## Problem

The `along-version-bump` skill states a precondition: the `Tests` workflow
(`.github/workflows/tests.yml`, Python 3.10-3.13 on Linux and Windows) is green on the commit
being released, because local gates see one interpreter and one OS. `along bump` does not
check it: v4.4.7 (2026-10-07) was released with the batch commit pushed seconds earlier and
CI never consulted.

## Requirements

- REQ-1: Before mutating, `along bump` looks up the CI status of `HEAD` (`gh run list
  --commit <sha>` / GitHub API) when the repository has a workflow and `gh` is available.
- REQ-2: Green -> proceed; failed -> abort with the run URL; pending / not pushed -> abort
  with a hint (push first, wait), unless `--skip-ci` with a reason is given.
- REQ-3: No `gh`, no remote, or no workflow -> warning, not a block.
- REQ-4: Repository opt-out / workflow name in `.along/config.json`.

## Acceptance Criteria
- [ ] Hermetic tests with a stubbed `gh`: green, failed, pending, missing
- [ ] Skill and docs updated
- [ ] Automated tests passing
