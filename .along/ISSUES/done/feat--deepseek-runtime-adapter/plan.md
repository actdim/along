# Plan: DeepSeek Runtime Adapter for Headless CLI Orchestration

## Goal
Implement `DeepSeekHarnessRunner` (`runtime = "deepseek"`, alias `"dsh"`) in `scripts/alongkit/runner/deepseek.py` to enable headless execution via `dsh --profile headless --json` and seamless multi-agent integration in `along run deepseek` and `along orchestrate [--scout|--architect|--implementer|--reviewer] deepseek`.

## Architecture & Subsystems

### 1. Runner Implementation (`scripts/alongkit/runner/deepseek.py`)
- Define class `DeepSeekHarnessRunner(BaseRunner)`.
- Runtime identifiers:
  - `runtime: str = "deepseek"`
  - `runtime_label: str = "DeepSeek Harness"`
  - `default_binary: str = "dsh"`
  - `cli_version: str = "0.2.0"`
  - `brief_via_stdin: bool = True`
- Binary resolution (`resolve_binary`):
  - Check `self.binary_path`.
  - Search `shutil.which("dsh")`.
  - Fallback on Windows: `%LOCALAPPDATA%\Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd`.
- Command construction (`build_command`):
  - Base command: `[binary, "--profile", "headless", "--json", "-"]`.
  - Support model selection via `--model` (e.g. `deepseek-chat`, `deepseek-reasoner`).
  - Merge optional role args and extra args safely via `merge_args`.
- Environment isolation (`build_env`):
  - Sets `DSH_PERMISSION_MODE = "danger-full-access"` to prevent interactive blocking in headless runs.
  - Allowlist: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DSH_HOME`, `DSH_PERMISSION_MODE`.
  - Strictly filter out unrelated API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, telegram tokens).
- Output parsing (`parse_output`):
  - Stream parser for NDJSON events emitted by `dsh --profile headless --json`.
  - Extract text chunks, tool calls, file mutations, and step finish token counts.
  - Formulate structured output: `{"outcome": outcome, "usage": usage, "changed_files": [...], "handoff_note": ..., "text": ...}`.

### 2. Registry & Multi-Agent Orchestrator Integration
- `scripts/alongkit/runner/__init__.py`:
  - Register `RUNNER_MAP["deepseek"] = DeepSeekHarnessRunner`.
  - Register `RUNNER_MAP["dsh"] = DeepSeekHarnessRunner`.
  - Export `DeepSeekHarnessRunner`.
- `scripts/alongkit/orchestration_profiles.py`:
  - Add `"deepseek"` and `"dsh"` to `VALID_RUNTIMES`.
- `scripts/alongkit/orchestrator.py`:
  - Add `"deepseek"` and `"dsh"` to `ORCHESTRATOR_RUNTIMES`.

### 3. Tests & Verification
- `tests/test_runtime_adapters.py`:
  - Add test class `TestDeepSeekHarnessRunner`:
    - `test_deepseek_command_line_and_flags`: verify command line generation with `--profile headless --json -`.
    - `test_deepseek_environment_isolation`: verify `DEEPSEEK_API_KEY` pass-through, `DSH_PERMISSION_MODE` default, and filtering of third-party keys.
    - `test_deepseek_output_parsing`: verify extraction of tokens, message content, and tool file changes from mock NDJSON stream.
    - `test_deepseek_binary_fallback_resolution`: verify resolution logic when binary is at custom/fallback path.
- Verification gates:
  - Run `python .along/scripts/test.py -k test_runtime_adapters`.
  - Run `along sanitize`.
  - Run `python scripts/along_kb_sync.py --check`.

### 4. Documentation
- Update `docs/topic--cli-reference.md` to document `along run deepseek` and `along orchestrate ... deepseek`.
- Sync knowledge base via `along kb-sync`.
