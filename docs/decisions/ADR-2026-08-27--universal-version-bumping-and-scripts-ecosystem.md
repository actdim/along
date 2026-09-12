---
protocol: along
slug: universal-version-bumping-and-scripts-ecosystem
title: "Universal Project Version Bumping & Repository Scripts Ecosystem (.along/scripts/)"
date: 2026-08-27
status: accepted
tags: [adr, architecture, decision]
---

# ADR-2026-08-27--universal-version-bumping-and-scripts-ecosystem - Universal Project Version Bumping & Repository Scripts Ecosystem (.along/scripts/)

- Date: 2026-08-27
- Status: accepted
- Context: `along-bump-version` was initially hardcoded for `actdim/along` internal development, failing when executed in external consumer repositories (Node, Python, Rust, .NET).
- Decision:
  1. Transform `/along-bump-version` (`along_bump_version.py`) into a universal release engine.
  2. Establish `.along/scripts/` convention in project memory directories for repo-tailored automation scripts.
  3. Support execution of custom `.along/scripts/bump_version.py` hooks with fallback to automatic stack detection (Node `package.json`, Python `pyproject.toml`, Rust `Cargo.toml`, .NET `*.csproj`, Along dev).
  4. Auto-synthesize `.along/scripts/bump_version.py` on first run for detected stacks, with diagnostic templates for custom environments.
- Consequences: Every project adopting Along gains automated, stack-agnostic version bumping and release orchestration out-of-the-box.
