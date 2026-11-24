# Plan: Complete DSH Integration Fixes, Skills Support, and Test Verification

Execution Mode: Direct

## Scope
Finish the remaining items in `bug--dsh-tool-name-map-and-ask-capability`:
1. Fix global `install_dsh_hooks(..., is_global=True)` in `scripts/alongkit/hooks/config.py`:
   - Pass `is_global=is_global` to `_write_dsh_hooks_file(hooks_file, is_global=is_global, dry_run=dry_run)`.
   - Set `configPath` in `expected_patch` to the actual `hooks_file` path (normalized with forward slashes) when `is_global=True`, keeping `./.dsh/along-hooks.json` for local installs.
   - Update `test_install_global_dsh_hooks` in `tests/test_hooks_dsh.py` to assert `is_global` commands in `along-hooks.json` and the global `configPath` in `cordis.patch.yml`.
2. Remove the stale `ASK_CAPABLE_RUNTIMES` tuple in `scripts/alongkit/hooks/engine.py` (no other callers exist).
3. Add `~/.dsh/skills` to `along_update.py` (`purge_legacy_global_skills` and global `protocol.md` fallback paths), and add/verify test coverage for DSH skill installation planning (`planned_files` for `dsh` -> `~/.dsh/skills/along-*`).
4. Update `bug--dsh-tool-name-map-and-ask-capability.md` with verified findings (e.g. `dsh-tool-bash` uses `command`, `dsh-tool-fs` has no `ls` tool) and test results.
5. Run `tests/test_hooks_dsh.py`, `tests/test_hooks_tool_coverage.py`, `tests/test_installers.py`, and the full test suite (`python .along/scripts/test.py -q`), and report any pre-existing failures outside this issue's scope.

## Verify Policy
- `scoped`: run `tests/test_hooks_dsh.py`, `tests/test_hooks_tool_coverage.py`, `tests/test_installers.py`, plus full suite check.
