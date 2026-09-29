---
protocol: along
protocol_version: "4.1.0"
slug: bootstrap-resilience-and-subcommand-proxying
type: feat
status: open
priority: medium
created: 2026-09-27
updated: 2026-09-29
agent: antigravity
tags: [bootstrap, uv, python, resilience, cli]
milestone: v4.5.0-multi-user-merge-automation
blocked_by: []
blocks: []
related: [feat--dev-environment-setup-and-editable-install]
---

# Bootstrap Resilience and Inline Subcommand Proxying

## Problem

Along engines rely on `alongkit.bootstrap.ensure_deps()` to transparently ensure third-party runtime dependencies (such as `ruamel.yaml>=0.18`) via `uv run`.
Currently, `scripts/alongkit/bootstrap.py` line 94 validates that `sys.argv[0]` is a valid file (`os.path.isfile(script)`). When Python is invoked with `-c` or when the entrypoint is not an on-disk script, `bootstrap.ensure_deps()` aborts with exit code 2 and outputs `[Error] missing required package ruamel.yaml`.

## Requirements

1. **Inline Invocation Support**: In `scripts/alongkit/bootstrap.py`, support cases where `sys.argv[0] == "-c"` by re-executing `[uv, "run", "--quiet", "--with", spec, "python", *sys.argv[1:]]` rather than aborting.
2. **Graceful Degradation**: Ensure that when `uv` is available, inline commands with `sys.argv[0] == "-c"` receive runtime dependencies seamlessly.
3. **Automated Unit Tests**: Add unit tests in `tests/test_bootstrap.py` covering inline invocation bootstrapping.
