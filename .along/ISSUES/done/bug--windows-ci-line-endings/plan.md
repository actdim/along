# Living Plan: windows-ci-line-endings

## Revision 1 (2026-11-15T12:46:59Z, plan approve --plan-file)

# Implementation Plan: Fix Windows CI Line Endings and Gitattributes Defaults

Execution Mode: Direct

## Summary
Prevent line ending divergence across Windows runners and local environments by establishing a repository-wide `* text=auto eol=lf` default in `.gitattributes`, explicitly pinning script and frontend text files to `eol=lf`, and making hook installation checks resilient to CRLF line endings.

## Files to Change
- `.gitattributes`: Add `* text=auto eol=lf`, `*.js text eol=lf`, `*.ts text eol=lf`, `*.tsx text eol=lf`, `*.css text eol=lf`, `*.html text eol=lf`, `*.svg text eol=lf`. Ensure `*.ps1` and `*.bat` retain `eol=crlf`.
- `scripts/alongkit/hooks/config.py`: In `install_opencode_hooks`, normalize line endings (`replace("\r\n", "\n")`) before comparing `existing` with `plugin_content`.
- `tests/test_opencode_runtime.py`: Add test case verifying that `install_opencode_hooks` correctly reports `present` even if template or disk file contains CRLF.

## Verification
- Run `python .along/scripts/test.py tests/test_opencode_runtime.py`
- Run full test suite: `python .along/scripts/test.py -q`
- Verify gates: `python scripts/along_exec.py gates check --ci --no-links`
