# Plan: Fix Dual Browser Window, Ctrl+C Traceback, and CMD Step Parsing

## Root Cause Analysis

1. **Dual Browser Window / Tab on Launch**:
   - `session.create_browser_session()` launches Chrome for Testing (`launch_cft`) which opens an initial default tab (`New Tab`).
   - `connect_playwright()` connects via CDP to that browser instance.
   - Calling `b_inst.new_page()` immediately creates a second blank window/tab (`about:blank`).
   - **Fix**: Check `b_inst.contexts[0].pages` and reuse the existing page if present, calling `new_page()` only if no pages exist.

2. **Command Does Not Finish & Ugly Ctrl+C Traceback**:
   - Running `along webdev session _worker --headed` runs the interactive HTTP server in the foreground, designed to wait for steps until stopped.
   - When the user presses Ctrl+C, `subprocess.run(command, env=env)` in `bootstrap._reexec()` raises an unhandled `KeyboardInterrupt`, dumping a 15-line stack trace to the console.
   - **Fix**: In `bootstrap._reexec()`, wrap `subprocess.run()` in `try / except KeyboardInterrupt: sys.exit(130)`. Also add `KeyboardInterrupt` handling to `along_webdev.py:main` and `daemon.py:run_daemon_worker` with clean exit.
   - Clarify in CLI help and output that `session start` is the background daemon command, while `session _worker` is internal foreground runner.

3. **Second Command Fails in cmd.exe (`session step`)**:
   - In Windows Command Prompt (`cmd.exe`), single quotes `'` are not treated as string delimiters.
   - Running `along webdev session step --step '{"goto": "https://www.google.com"}'` causes `cmd.exe` to split on spaces, passing `'{"goto":'` and `https://www.google.com}'` as separate arguments. `argparse` treats the latter as an unrecognized positional argument.
   - **Fix**:
     - Change `--step` and `--batch` to `nargs="+"` in `along_webdev.py`.
     - Implement `normalize_step_payload()` to join space-split arguments, strip outer quotes, support `@file.json` references, and parse JSON / YAML / key-value shorthand.
     - Add direct convenience flags to `along webdev session step`: `--goto <URL>`, `--click <SELECTOR>`, `--fill <LOCATOR> <TEXT>`, `--screenshot [PATH]`.

---

## Proposed Changes

### 1. `scripts/alongkit/webdev/session.py`
- In `create_browser_session`:
  ```python
  contexts = b_inst.contexts
  if contexts and contexts[0].pages:
      page = contexts[0].pages[0]
  else:
      page = b_inst.new_page()
  ```

### 2. `scripts/alongkit/bootstrap.py`
- In `_reexec()`:
  Catch `KeyboardInterrupt` and exit with code 130 without printing an exception traceback.

### 3. `scripts/along_webdev.py`
- Wrap `main()` with `except KeyboardInterrupt: sys.exit(130)`.
- Update `p_session`:
  - `p_session.add_argument("--step", nargs="+", default=None, ...)`
  - `p_session.add_argument("--batch", nargs="+", default=None, ...)`
  - Add convenience flags: `--goto`, `--click`, `--fill`, `--screenshot`.

### 4. `scripts/alongkit/webdev/daemon.py`
- In `run_daemon_worker()`: Print clean exit message `Session worker terminated.` on `KeyboardInterrupt` or `SystemExit`.
- Implement `normalize_step_payload(raw)` and `normalize_batch_payload(raw)`:
  - Supports space-split tokens from `nargs="+"`.
  - Strips leading/trailing single quotes if `cmd.exe` preserved them.
  - Supports `@file.json` and local file paths.
  - Supports `goto=https://...` or key=value shorthand.
- In `handle_session_cli()`:
  - If `--goto`, `--click`, `--fill`, or `--screenshot` is provided, synthesize the step payload.
  - Fall back to `--step` processed via `normalize_step_payload`.

### 5. `tests/test_webdev_interactive.py`
- Update unit tests to verify:
  - Page reuse when pages are already open in `b_inst.contexts[0].pages`.
  - Normalization of single-quoted / space-split JSON strings in step execution.
  - Direct convenience shortcut flags (`--goto`, `--click`, `--fill`, `--screenshot`).

---

## Verification Plan
1. Run `python .along/scripts/test.py tests/test_webdev_interactive.py`.
2. Run `along webdev session step` simulation with:
   - Space-split single-quoted argument: `['\'{"goto":', 'https://www.google.com}\'']`.
   - Direct `--goto https://www.google.com`.
3. Check `along sanitize` for strict ASCII typography compliance.
