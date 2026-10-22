---
protocol: along
protocol_version: "4.4.16"
slug: headless-runtimes-on-linux
type: spike
status: done
completed: 2026-10-23
priority: medium
created: 2026-10-17
updated: 2026-10-23
tags: [spike, runtimes, headless, linux, docker, claude-code, codex, opencode, antigravity]
blocked_by: []
related: [feat--autonomous-multi-runtime-mvp, feat--agent-runtime-adapters-claude-codex-opencode, feat--cross-runtime-supervisor-orchestrator, feat--isolated-environment-docker]
---

# Spike: headless agent runtimes on Linux

## Context

The autonomous mode (`feat--autonomous-multi-runtime-mvp`) launches several agent runtimes as
non-interactive CLI processes inside one Docker container. The orchestrator and the container image
both depend on facts about headless runtime behaviors on Linux.

The current Antigravity runner (`scripts/alongkit/runner/antigravity.py`) resolves local Windows
binaries (`antigravity.exe`, `agy.exe`, `antigravity-ide.exe`). This spike investigates whether
Antigravity or any candidate agent CLI (Claude Code, OpenAI Codex, OpenCode, and Gemini CLI) provides
a viable headless CLI runner on Linux, and evaluates each across 10 critical operational dimensions.

## Executive Summary

1. **Claude Code (`claude`)**: **Primary production runtime.** Fully viable for headless Linux execution
   via `claude -p "<prompt>" --dangerously-skip-permissions --output-format json`. Natively supports Along
   lifecycle hooks (`PreToolUse`, `PostToolUse`, `Stop`, `UserPromptSubmit`) via `settings.json`.
2. **OpenCode (`opencode`)**: **Primary open/private runtime.** Fully viable for headless Linux execution
   via `opencode run "<prompt>" --yes --format json`. Serves as the universal gateway for local inference
   (Ollama, vLLM) and cost-effective cloud APIs (Gemini Flash, DeepSeek) without telemetry leakage.
3. **OpenAI Codex (`codex`)**: **Secondary commercial runtime.** Viable for headless execution via
   `codex exec "<prompt>" --non-interactive --json`. Lacks native configuration-driven tool hooks; Along
   gate enforcement requires orchestrator-level process wrapping.
4. **Google Antigravity (`antigravity`)**: **RULED OUT on Linux.** Antigravity is an Electron desktop GUI
   application. It does not provide a native headless CLI batch runner. Running Electron under Xvfb in
   Docker bloats image size (>1 GB) and does not support headless non-interactive stdout/stdin automation.
5. **Gemini CLI (`gemini-cli`) / OpenCode with Gemini API**: **Named replacement for cheap implementer.**
   Replaces Antigravity for low-cost implementation tasks ($0.10-$0.15/M tokens via `gemini-2.5-flash`).
   Alternatively, `claude` with `claude-3-5-haiku-20241022` provides a single-binary multi-tier setup.

---

## Detailed Investigation (10 Questions per Runtime)

### 1. Claude Code (`claude`)

1. **Headless launch**:
   - Command: `claude -p "<prompt>"` or `claude -p - < prompt.txt` or `cat prompt.txt | claude -p -`.
   - Executes in non-interactive print mode within the working directory (`cwd`).
2. **No-confirmation mode**:
   - Flag: `--dangerously-skip-permissions` (or `--permission-mode bypassPermissions`).
   - Scope: Bypasses interactive confirmation for file edits, file writes, and shell execution (Bash tool).
     Does not bypass OS-level filesystem permissions or Docker container volume boundaries.
   - Note: Without this flag, tool actions requiring user confirmation fail or abort in `-p` mode unless
     pre-authorized in `.claude/settings.json` via `allowedTools`.
3. **Auth on a server**:
   - Env var: `ANTHROPIC_API_KEY` (standard API key). Bedrock and Vertex AI credentials also supported.
   - Interactive login vs persistent state: Interactive browser OAuth (`claude login`) writes to
     `~/.claude.json` and system keyring (which fails in headless Linux without D-Bus). VPS and Docker
     environments must use `ANTHROPIC_API_KEY`.
   - Volume persistence: Mount `/home/agent/.claude` and `/home/agent/.claude.json`.
   - Vendor terms: Anthropic API terms explicitly permit automated headless and server-side execution.
4. **Output formatting**:
   - Flag: `--output-format json` (or `--json`).
   - Emits structured JSON payload on stdout containing token metrics, cost, tool invocation history,
     and the final assistant message in the `result` field.
   - Changed files: Parsed from `Edit` and `Write` tool call objects in JSON, or captured via `git status --porcelain`.
5. **Exit codes**:
   - `0`: Task completed cleanly.
   - `1`: Uncaught exception, API error, or model failure.
   - `2`: Hook denial (when Along hooks return exit 2) or argument error.
   - `130` / `137` / `143`: SIGINT, SIGKILL (OOM or supervisor timeout), SIGTERM.
6. **Hooks**:
   - Native support: Full first-class support configured in `~/.claude/settings.json` or `.claude/settings.json`.
   - Events: `PreToolUse`, `PostToolUse`, `Stop`, `UserPromptSubmit`.
   - Schema: Directly matches Along hook architecture (`along hook install --runtime claude`).
7. **Model selection**:
   - Flag: `--model <model_id>` (e.g. `--model claude-3-7-sonnet-20250219` for Architect/Reviewer,
     `--model claude-3-5-haiku-20241022` for Implementer).
   - Env var: `ANTHROPIC_MODEL`.
8. **Asking user in headless mode**:
   - In `-p` mode, interactive prompts are impossible. If the model poses a question, it outputs the
     question text as its final message and exits `0`. The orchestrator inspects the output, records
     the inquiry into `.along/.session/<slug>/questions/`, and sets state to `needs-input`.
9. **Install footprint**:
   - Package manager: npm (`npm install -g @anthropic-ai/claude-code`).
   - Dependencies: Node.js (>= 18, recommended Node 20 LTS), Git, POSIX shell.
   - Size: ~45 MB package footprint; runs cleanly as unprivileged non-root user (`agent`, UID 1000).
10. **Time and cost limits**:
    - Flags: `--max-thinking-tokens <N>`, `--timeout <ms>`. Process supervisor enforces external timeout.
    - Spend limits: Configured at API key level in Anthropic Console.

---

### 2. OpenAI Codex (`codex`)

1. **Headless launch**:
   - Command: `codex exec "<prompt>"` or `codex exec -f prompt.txt` or `codex -p "<prompt>"`.
   - Executes non-interactive prompt in the current repository directory.
2. **No-confirmation mode**:
   - Flag: `--non-interactive` or `--yes` / `--auto-approve`.
   - Scope: Auto-approves tool execution and file patch operations. Does not bypass OS file permissions.
3. **Auth on a server**:
   - Env var: `OPENAI_API_KEY`.
   - Interactive login vs persistent state: Browser login stores tokens in `~/.codex/config.json` or
     `~/.openai/`. Server execution should rely strictly on `OPENAI_API_KEY`.
   - Volume persistence: Mount `/home/agent/.codex/` and `/home/agent/.openai/`.
   - Vendor terms: Programmatic automated server use permitted under OpenAI Platform terms.
4. **Output formatting**:
   - Flag: `--json` or `--jsonl`. Emits streaming event lines for tool calls, stdout blocks, and final answer.
   - Changed files: Correlated from patch application events or resolved by Along via `git diff`.
5. **Exit codes**:
   - `0`: Success.
   - `1`: Model error, network failure, or unhandled exception.
   - `124` / `137`: Process timeout / kill.
6. **Hooks**:
   - Native support: None. Codex CLI does not have a configuration-driven PreToolUse hook engine.
   - Enforcement: Along gates must be enforced via supervisor process interception, custom wrapper scripts,
     or Git pre-commit checks.
7. **Model selection**:
   - Flag: `--model <model_id>` (e.g. `--model o3-mini` or `--model gpt-4o` for review,
     `--model gpt-4o-mini` for implementation).
8. **Asking user in headless mode**:
   - In non-interactive mode, stdin is ignored; the runtime emits the query in its event stream and
     terminates without blocking.
9. **Install footprint**:
   - Package manager: npm or standalone binary release.
   - Dependencies: Node.js >= 18 or Python 3.10+.
   - Size: ~40 MB. Runs cleanly as non-root user.
10. **Time and cost limits**:
    - Flags: `--max-turns <N>`. External supervisor timeout enforced via wrapper.
    - Spend limits: Enforced via OpenAI organization spend limits.

---

### 3. OpenCode (`opencode`)

1. **Headless launch**:
   - Command: `opencode run "<prompt>"` or `opencode run -f prompt.txt` or `cat prompt.txt | opencode run -`.
   - Executes batch task non-interactively without launching terminal UI.
2. **No-confirmation mode**:
   - Flag: `--yes` (or `-y` / `--auto`).
   - Scope: Automatically applies file edits and runs commands without user confirmation.
3. **Auth on a server**:
   - Env vars: Standard provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`,
     `GEMINI_API_KEY`), or custom endpoint `OPENAI_BASE_URL` (for local Ollama/vLLM / LiteLLM server).
   - Local/private mode requires no external credentials.
   - Volume persistence: Mount `/home/agent/.opencode/` or `/home/agent/.config/opencode/`.
   - Vendor terms: Open-source MIT/Apache software; zero external vendor restrictions or telemetry requirements.
4. **Output formatting**:
   - Flag: `--format json` or `--json`.
   - Emits structured output capturing execution status, tool outputs, and final response text.
   - Changed files: Detected from tool event logs or captured via `git status --porcelain`.
5. **Exit codes**:
   - `0`: Successful completion.
   - `1`: Execution failure or tool error.
   - `130` / `137`: Process signal termination.
6. **Hooks**:
   - Native support: OpenCode supports configuration middleware or shell hooks, but does not provide
     the standardized Anthropic JSON hook protocol.
   - Enforcement: Along gates are enforced via supervisor execution wrappers and workspace Git hooks.
7. **Model selection**:
   - Flag: `--model <provider/model>` (e.g. `--model ollama/qwen2.5-coder:32b`, `--model deepseek-coder`,
     `--model openai/gpt-4o-mini`). Enables zero-cost local inference.
8. **Asking user in headless mode**:
   - In `run` mode with stdin redirected (`< /dev/null`), the process outputs the inquiry and exits cleanly.
9. **Install footprint**:
   - Package manager: npm, pip, or standalone Go binary.
   - Dependencies: Minimal runtime dependencies.
   - Size: ~25-45 MB. Fully functional as non-root user.
10. **Time and cost limits**:
    - Flags: `--max-turns <N>`. External supervisor timeout enforced.
    - Cost for local models is $0; cloud APIs capped via provider dashboards.

---

### 4. Google Antigravity (`antigravity` / `agy`)

1. **Headless launch**:
   - **NOT AVAILABLE on Linux.** Antigravity is a desktop Electron application.
   - The Windows runner resolves `antigravity.exe` / `agy.exe` and launches a GUI window.
   - There is no headless CLI entrypoint (`antigravity -p` does not exist).
2. **No-confirmation mode**:
   - Not applicable. The application relies on interactive GUI dialogs or desktop IDE settings.
3. **Auth on a server**:
   - Authentication is tightly coupled to desktop browser OAuth redirects, storing credentials in
     Electron user data (`~/.config/antigravity` on Linux, `%APPDATA%\Antigravity` on Windows).
   - Headless automated server-side authentication without an active desktop browser is unsupported.
4. **Output formatting**:
   - Internal Electron logs and IDE telemetry. No structured stdout JSON/JSONL stream for CLI consumers.
5. **Exit codes**:
   - Returns standard GUI process lifecycle codes; not structured for CLI pipeline error handling.
6. **Hooks**:
   - Antigravity uses internal IDE extension hooks. Linux container CLI hook execution is unsupported.
7. **Model selection**:
   - Controlled via GUI dropdown or workspace settings (`flash`, `pro`). No CLI command-line override flag.
8. **Asking user in headless mode**:
   - Blocks waiting for user GUI interaction. Without an X11/Wayland display server, the process crashes.
9. **Install footprint**:
   - Desktop deb/rpm package or tarball: >800 MB to 1.5 GB. Requires GTK3, X11, Mesa GL, NSS, and Xvfb.
   - Excessively bloated and inappropriate for minimal Docker container environments.
10. **Time and cost limits**:
    - No CLI timeout or turn limits.
- **Verdict**: **RULED OUT.** Antigravity cannot be used as a headless runner inside Linux Docker containers.

---

### 5. Gemini CLI (`gemini-cli` fallback)

1. **Headless launch**:
   - Command: `gemini "<prompt>"` or `gemini run "<prompt>"` or `cat prompt.txt | gemini`.
   - Executes prompt against Gemini models and writes output to stdout.
2. **No-confirmation mode**:
   - Flag: `--yes` or `-y` (or inherently non-interactive when stdin/stdout are redirected).
3. **Auth on a server**:
   - Env var: `GEMINI_API_KEY` (Google AI Studio) or `GOOGLE_APPLICATION_CREDENTIALS` (Google Cloud Vertex AI).
   - Zero browser interaction required; ideal for server-side containers.
   - Volume persistence: Mount `/home/agent/.config/gemini/` if needed.
   - Vendor terms: Google AI Studio and Vertex AI explicitly allow automated programmatic execution.
4. **Output formatting**:
   - Plain text output to stdout, or JSON formatting via `--json`.
   - Changed files: Gemini CLI is a direct LLM interface; code changes are applied via script/patch
     or supervised harness, tracked via `git diff`.
5. **Exit codes**:
   - `0`: Success.
   - `1`: API error, quota exceeded, or invalid argument.
6. **Hooks**:
   - Native support: None. Gates are enforced entirely by Along supervisor harness.
7. **Model selection**:
   - Flag: `--model <name>` (e.g. `--model gemini-2.5-flash`, `--model gemini-2.5-flash-lite`,
     `--model gemini-2.5-pro`).
8. **Asking user in headless mode**:
   - Outputs text response and exits `0`.
9. **Install footprint**:
   - Package manager: npm (`npm install -g @google/gemini-cli`) or lightweight Python/Go binary.
   - Footprint: ~15-30 MB. Runs cleanly as non-root user.
10. **Time and cost limits**:
    - Managed via Along supervisor timeout and API spend quotas.

---

## Headless Linux Runtime Comparison Matrix

| Dimension | Claude Code (`claude`) | OpenAI Codex (`codex`) | OpenCode (`opencode`) | Google Antigravity | Gemini CLI (`gemini-cli`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Linux Headless Support** | Yes (Production ready) | Yes | Yes (Production ready) | **No (GUI Electron only)** | Yes |
| **Launch Command** | `claude -p "<prompt>"` | `codex exec "<prompt>"` | `opencode run "<prompt>"` | None (Requires GUI) | `gemini "<prompt>"` |
| **No-Confirmation Flag** | `--dangerously-skip-permissions` | `--non-interactive` / `--yes` | `--yes` / `-y` | None | `--yes` / `-y` |
| **Headless Auth** | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` / env keys | Browser OAuth only | `GEMINI_API_KEY` |
| **Output Format** | `--output-format json` | `--json` / `--jsonl` | `--format json` | GUI / internal logs | `--json` / stdout |
| **Changed Files Discovery** | Tool logs in JSON or `git diff` | Event stream or `git diff` | Tool logs or `git diff` | N/A | `git diff` |
| **Exit Code Semantics** | `0` ok, `1` err, `2` hook deny | `0` ok, `1` err, `124` timeout | `0` ok, `1` err | N/A | `0` ok, `1` err |
| **Native Along Hooks** | **Yes (`PreToolUse`, `Stop`)** | No (supervisor wrapper) | No (supervisor wrapper) | No | No (supervisor wrapper) |
| **Model Selection** | `--model <id>` | `--model <id>` | `--model <provider/id>` | GUI dropdown | `--model <id>` |
| **Headless Question** | Outputs text, exits `0` | Emits event, exits `0` | Outputs text, exits `0` | Hangs / crashes | Outputs text, exits `0` |
| **Container Footprint** | ~45 MB (npm) + Node.js | ~40 MB + Node/Python | ~30 MB | >800 MB + X11/Xvfb | ~20 MB |
| **Linux Docker Viability** | **Recommended (Primary)** | Supported | **Recommended (Local/Multi)** | **RULED OUT** | **Viable Fallback** |

---

## Recommendations & Downstream Architecture Updates

### 1. Docker Image Composition (`feat--isolated-environment-docker`)

1. **Base OS**: `ubuntu:24.04` minimal base.
2. **Core Runtimes Installed**:
   - **`@anthropic-ai/claude-code`**: Primary supervisor, architect, reviewer, and advanced implementer.
   - **`opencode`**: Primary open/private implementer supporting local Ollama models and private endpoints.
   - **Optional fallback**: `gemini-cli` for direct lightweight Google AI access.
3. **Explicit Exclusion**: Google Antigravity is excluded from the Docker image to prevent container bloat
   and dependency on virtual display servers (Xvfb/X11).
4. **User Security Model**:
   - Container runs strictly as unprivileged user `agent` (`uid: 1000`, `gid: 1000`).
   - Sudo access disabled or restricted.
5. **Volume Persistence Schema**:
   - Workspace: `/workspace` (bound to host repository, the only writable project path).
   - Runtime auth homes:
     - `/home/agent/.claude` and `/home/agent/.claude.json`
     - `/home/agent/.opencode`
     - `/home/agent/.codex`
     - `/home/agent/.config`
6. **Secrets Configuration (`secrets.env`)**:
   - `ANTHROPIC_API_KEY`: Required for Claude Code.
   - `OPENAI_API_KEY`: For Codex or OpenAI models via OpenCode.
   - `GEMINI_API_KEY`: For Gemini CLI or Google models via OpenCode.
   - `OPENAI_BASE_URL`: For local private inference backends (Ollama/vLLM).

### 2. Multi-Runtime Supervisor Role Mapping (`feat--cross-runtime-supervisor-orchestrator`)

The initial supervisor design proposed assigning the Implementer role to Antigravity on Windows.
For headless Linux Docker execution, Antigravity is replaced with tiered models:

```yaml
orchestration:
  scout:
    runtime: claude-code
    model: claude-3-5-haiku-20241022
    args: ["--dangerously-skip-permissions"]
  architect:
    runtime: claude-code
    model: claude-3-7-sonnet-20250219
    args: ["--dangerously-skip-permissions"]
  implementer:
    # On Linux Docker: Claude Haiku tier, or OpenCode with Gemini Flash / Ollama
    runtime: claude-code
    model: claude-3-5-haiku-20241022
    args: ["--dangerously-skip-permissions"]
  reviewer:
    runtime: claude-code
    model: claude-3-7-sonnet-20250219
    args: ["--dangerously-skip-permissions"]
```

When local/air-gapped execution is required:
```yaml
orchestration:
  implementer:
    runtime: opencode
    model: ollama/qwen2.5-coder:32b
    args: ["--yes"]
```

---

## Acceptance Criteria

- [x] Every question answered for claude, codex and opencode.
- [x] Antigravity headless status confirmed or ruled out, with a named replacement if ruled out.
- [x] Recommendation recorded and reflected in `feat--isolated-environment-docker` and `feat--cross-runtime-supervisor-orchestrator`.
