---
protocol: along
slug: projection-merge-driver-defers-recompile
type: decision
title: "Projection merge driver keeps ours and defers recompilation"
date: 2026-09-29
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-09-29--projection-merge-driver-defers-recompile - Projection merge driver keeps ours and defers recompilation

- Date: 2026-09-29
- Status: accepted
- Context: Git runs merge drivers before merged entity files reach the working tree, and .along/ISSUES.md sorts before .along/ISSUES/*, so a driver that recompiles projections in place rebuilds the pre-merge board. Broad **/ gitattributes patterns can also match files that are not Along projections.
- Decision: The along-projection driver keeps ours, exits 0, and records the path in GIT_DIR/along-projection-resync; along git sync recompiles and clears it, and doctor/git status warn while it exists. Drivers verify the file is a real projection or parseable entity and otherwise fall back to git merge-file. No git hooks are installed, so the Zero Git Hooks invariant stands. Legacy monolithic DECISIONS.md stays merge=union.
- Consequences: Pulls never stop on projection conflicts, but boards are stale until along git sync runs. Driver config is per clone (.git/config, absolute paths), so a fresh clone needs along git setup or along update; without it git silently uses its default text merge.
