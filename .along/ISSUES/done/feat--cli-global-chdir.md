---
protocol: along
protocol_version: "4.6.0"
slug: cli-global-chdir
type: feat
status: done
completed: 2026-11-06
priority: high
created: 2026-11-05
updated: 2026-11-06
agent: antigravity
tags: [cli, submodules, navigation]
blocked_by: []
related: []
plan_status: needs-approval
---

# Global -C <dir> option for the Along CLI

Support a global `-C <dir>` / `--chdir <dir>` option for `along`, identical to `git -C <dir>`. Currently, executing Along commands in a nested subproject or submodule requires `(cd <dir> && along ...)`, which breaks runtime hooks that inspect the initial working directory of the process.

## Requirements
- REQ-1: The Along CLI router (`scripts/along_exec.py`) MUST accept `-C <dir>` and `--chdir <dir>` before the subcommand.
- REQ-2: Multiple `-C` arguments MUST be evaluated sequentially, matching standard `git -C` semantics.
- REQ-3: If `<dir>` does not exist or is not a directory, Along MUST print an error message and exit with code 2 immediately without invoking subcommands.
- REQ-4: All relative paths passed to subcommands (such as `--plan-file` or target files) MUST be resolved relative to the changed directory.
- REQ-5: Subprocesses spawned by Along (`git`, Python lifecycle scripts, etc.) MUST execute with `cwd` set to the resolved directory.
- REQ-6: Unit tests MUST verify `-C` behavior for entity commands, lifecycle commands, and invalid directory paths.

## Acceptance Criteria
- [x] Along CLI router pre-parses `-C <dir>` and `--chdir <dir>` flags before subcommands.
- [x] Non-existent target directory exits with code 2.
- [x] All subcommands and subprocesses execute in the context of the resolved directory.
- [x] Automated unit tests verify single, multiple, and chained `-C` invocations.
