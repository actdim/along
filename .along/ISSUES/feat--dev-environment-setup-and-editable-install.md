---
protocol: along
protocol_version: "4.1.0"
slug: dev-environment-setup-and-editable-install
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-29
agent: antigravity
tags: [dev-environment, venv, packaging, editable, alongkit]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
blocks: []
related: [feat--bootstrap-resilience-and-subcommand-proxying]
---

# Dev Environment Setup and Editable Package Installation

## Problem

In the development checkout of `actdim-along`, the `alongkit` package lives in `scripts/alongkit/` and is not installed in the global Python environment.
As a result:
1. Standard tools like `pytest` fail with `No module named pytest` or `No module named alongkit` unless invoked through `.along/scripts/test.py`.
2. Developer IDEs (VS Code, Cursor, Antigravity) cannot resolve `alongkit` imports without custom workspace settings.
3. Ad-hoc Python testing requires manual path manipulation.

## Requirements

1. **Automated Dev Environment Setup**: Provide a command or hook (`along dev-env` or in `.along/scripts/dev.py`) that initializes a local `.venv` and installs the package in editable mode (`uv pip install -e .` or `.pth` link).
2. **Interpreter Parity**: Ensure `python` and `pytest` work seamlessly inside the dev environment with all required dependencies pre-installed.
3. **Hermetic Safety**: The dev environment must remain isolated to the local repository root and not pollute the host global site-packages.
