---
protocol: along
protocol_version: 2.2.8
slug: generated-lifecycle-hooks-use-shell-string-concat
type: bug
status: open
priority: medium
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [along-exec, codegen, shell-injection, determinism]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [extract-shared-python-library]
parent: protocol-quality-audit-remediation
---

# Synthesized lifecycle hooks concatenate arguments into a shell string

## Problem

When a lifecycle hook is missing, `along_exec.py` writes a Python file that concatenates
user arguments into a single shell command string:

```python
# scripts/along_exec.py (lifecycle synthesis, ~line 756-772)
py_content = f'''#!/usr/bin/env python3
# Status: {status_tag}
import sys, subprocess, os

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cmd = "{detected_cmd}"
    extra = " ".join(sys.argv[1:])
    full_cmd = f"{{cmd}} {{extra}}".strip()
    print(f"-> Running: {{full_cmd}}")
    res = subprocess.run(full_cmd, shell=True, cwd=repo_root)
    sys.exit(res.returncode)
'''
```

and the immediate execution path does the same:

```python
# scripts/along_exec.py:775
res = subprocess.run(f"{detected_cmd} {' '.join(extra_args)}".strip(), shell=True, cwd=repo_root)
```

Plus a third site for non-Python hooks:

```python
# scripts/along_exec.py:748
res = subprocess.run([script_file] + extra_args, cwd=repo_root, shell=True)
```

Issues:

1. **Argument injection.** Anything after `along test` is spliced into a shell string, so
   `along test "; <command>"` executes the injected command. Local-only, but this is the
   engine that a "quality gates" product uses to run tests.
2. **Quoting breakage.** Paths or test filters containing spaces are silently split; on
   Windows a backslash path can be reinterpreted by the shell.
3. **Violates the protocol's own determinism rule.** `AGENTS.md` mandates deterministic
   subcommand execution and bans fragile shell string composition on Windows/PowerShell.
4. **`shell=True` with a list argument** (line 748) is a platform-dependent bug: on POSIX
   only the first element is executed and the remaining arguments are dropped.
5. **Generated code is unversioned and untested.** The template is embedded in an f-string,
   is not linted, is not covered by tests, and duplicates `repo_root` discovery with a
   fragile triple `dirname` instead of the shared resolver.

## Requirements

- REQ-1: Pass arguments as a list; use `shell=False` everywhere. Where a detected command is
  a shell one-liner (for example an npm script), split it with `shlex.split` at generation
  time and store the argv list in the generated hook.
- REQ-2: Fix the `shell=True` + list call at line 748; select the interpreter explicitly per
  extension (`.py` -> `sys.executable`, `.sh` -> `bash`, `.ps1` -> `powershell -File`,
  `.bat` -> `cmd /c`).
- REQ-3: Move the generated hook template into a real template file under
  `skills/along-init/` or the shared package, so it can be linted and tested.
- REQ-4: The generated hook must use the shared repo-root resolver, not nested `dirname`
  calls.
- REQ-5: Tests: an argument containing a space and a shell metacharacter is passed through
  verbatim and not interpreted; generated hook compiles and runs on Windows and POSIX;
  `.sh` and `.ps1` hooks are dispatched with the correct interpreter.

## Acceptance Criteria

- [ ] No `shell=True` remains in `along_exec.py`.
- [ ] Arguments with spaces and metacharacters pass through unmodified.
- [ ] Hook template extracted to a file and covered by tests.
- [ ] Generated hooks use the shared resolver.
