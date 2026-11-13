# Living Plan: OpenCode Runtime V2 Plugin Hardening and Lifecycle Hook Completeness

Execution Mode: Role-Based (along-team)

## Steps

- [x] Step 1: OpenCode V2 Plugin Rewrite (`opencode_plugin.js`)
  - Export `{ id: "along-gates", async setup(ctx) }` as default, retain `AlongPlugin` named export.
  - Register `tool.execute.before`, `tool.execute.after`, `session.idle`, `session.stop`, `session.prompt`, `shell.env`, `shell.create.before`.
  - Maintain session ID cache from tool/prompt events to inject into shell even when `shell.env` lacks `sessionID`.
  - Implement robust process spawn: timeout (10s), Python interpreter resolution (`ALONG_PYTHON`, venv, `py -3`, `python3`, `python`), diagnostic logging to `~/.along/diagnostics/opencode-hook.log`, and Error throw on non-zero exit.

- [x] Step 2: Tool Argument Normalization in Adapters
  - Update `GenericCliAdapter` and `OpenCodeAdapter` to parse OpenCode camelCase fields (`newString`, `oldString`, `filePath`, and `execute`'s `{ code }`).
  - Map `newString` to `ReplacementContent`, `code` to `CommandLine`, `filePath` to `TargetFile`.

- [x] Step 3: Runtime Agent Detection Hardening
  - In `vocabulary.py`: ignore `AGENT` if value is `"1"`, `"0"`, `"true"`, or `"false"`.
  - Check `OPENCODE_SESSION_ID`, `OPENCODE_AGENT`, `OPENCODE_CLI` before generic fallback.

- [x] Step 4: Installers, Update Engine, and Repository Hygiene
  - Update `install.ps1` hook registration loop to include `opencode` with `$OpencodeHome`.
  - Update `install.sh` hook registration loop to include `opencode` with `$OPENCODE_HOME`.
  - In `config.py` (`install_opencode_hooks`), remove obsolete `along-opencode-plugin.js`.
  - Add `.opencode/` to `.gitignore`.

- [x] Step 5: Doctor Diagnostics Freshness & Honesty
  - In `runtime.py`: check for V2 structure (`along-gates`, `setup`) in `along-gates.js`.
  - In `doctor.py`: verify hook heartbeat freshness before asserting mechanical enforcement.

- [x] Step 6: Automated Verification & Session Wrap
  - Write Node integration test executing `node` to verify `opencode_plugin.js` loads, exports V2 structure, and registers hooks cleanly.
  - Run full test suite, verify clean typography with `along sanitize`.
  - Deploy plugin locally to `~/.config/opencode/plugins/along-gates.js` and verify with `opencode debug info`.
  - Wrap issue transactionally via `along wrap opencode-runtime-v2-hardening`.
