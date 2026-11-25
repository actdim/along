---
protocol: along
slug: multi-runtime-orchestration
title: Multi-Runtime Orchestration, Named Profiles & OpenObserve Observability
type: architecture
created: 2026-11-14
updated: 2026-11-25
tags: [orchestration, profiles, opencode, antigravity, claude, codex, deepseek, caching, openobserve, telemetry, worktree]
sources:
  - path: scripts/alongkit/orchestrator.py
  - path: scripts/alongkit/orchestration_profiles.py
  - path: scripts/alongkit/runner/base.py
  - path: scripts/alongkit/runner/claude.py
  - path: scripts/alongkit/runner/codex.py
  - path: scripts/alongkit/runner/deepseek.py
  - path: scripts/alongkit/runner/opencode.py
  - path: scripts/alongkit/runner/antigravity.py
  - path: scripts/alongkit/telemetry/otlp.py
---

# Multi-Runtime Orchestration, Named Profiles & OpenObserve Observability

## 1. Overview and Problem Statement

Engineering tasks vary widely in complexity. A single-file bugfix or typo correction does not warrant multi-agent decomposition, while complex refactorings benefit from specialized models (such as an advanced model for architecture and planning, a cost-efficient or local code model for step implementation, and an independent model for code review).

To prevent operational overhead and excessive token consumption, Along separates task execution into configurable **Orchestration Profiles**. These profiles govern which agent runtime harnesses (Claude Code, OpenAI Codex, OpenCode, Google Antigravity) execute each phase, while streaming real-time OpenTelemetry (OTel) traces to an analytical backend such as **OpenObserve**.

---

## 2. Core Components & Engine Implementation

Along provides a decoupled engine architecture for multi-runtime task execution:

### 2.1 Orchestration Modes

Along supports three distinct operational modes:

1. **`direct` (Single-Agent Fast-Path)**:
   - A single agent runtime handles the entire task in one continuous session.
   - Skips dedicated Scout and Reviewer subagent phases.
   - Ideal for S-size tasks (1-2 files), documentation updates, and straightforward fixes.

2. **`team-native` (In-Harness Sequential Roles)**:
   - Execution is divided into deterministic roles (`scout`, `architect`, `implementer`, `reviewer`).
   - All roles run within a single provider harness (for example, native Antigravity subagents or Claude Code `Task` tools, falling back to a single-agent Ralph loop when subagents are unavailable).
   - Suitable for M-size tasks requiring structured planning and review without cross-runtime switching.

3. **`cross-runtime` (Heterogeneous Multi-CLI Orchestration)**:
   - Supervised by `CrossRuntimeOrchestrator`.
   - Each role is dispatched to a dedicated CLI process and model configuration (for example, Claude Code for planning, OpenCode for coding, Codex or Antigravity for review).
   - Artifacts and state are synchronized via the repository session blackboard (`.along/.session/<slug>/`).
   - Designed for L/XL tasks and specialized enterprise or air-gapped environments.

### 2.2 Named Profiles Configuration & Schema

Profiles are defined as declarative YAML documents stored in `.along/orchestration/<name>.yaml`. Shorthand configs can also reside directly in `along.yaml` or `.along/config.yaml`.

```yaml
name: "cross-tiered"
description: "Tiered multi-agent execution with Claude planner and OpenCode worker"
mode: "cross-runtime" # direct | team-native | cross-runtime
workspace: "inherit"  # inherit | worktree
timeout: 1800         # global timeout in seconds

roles:
  scout:
    runtime: "claude-code"
    model: "claude-3-7-sonnet"
    timeout: 600
    args: ["--permission-mode", "headless"]
    env:
      ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"

  architect:
    runtime: "claude-code"
    model: "claude-3-7-sonnet"
    timeout: 900

  implementer:
    runtime: "opencode"
    model: "qwen2.5-coder:32b"
    timeout: 1800
    args: ["--variant", "code"]
    env:
      OPENAI_BASE_URL: "http://localhost:11434/v1"
      OPENAI_API_KEY: "ollama"

  reviewer:
    runtime: "codex"
    model: "o3-mini"
    timeout: 600
```

For a simple single-agent profile (`.along/orchestration/direct.yaml`):

```yaml
name: "direct"
description: "Default single-agent fast path"
mode: "direct"
workspace: "inherit"
runner:
  runtime: "claude-code"
  model: "claude-3-7-sonnet"
  timeout: 1200
```

---

## 3. Data Flow & Execution Workflows

### 3.1 Parameter Resolution Cascade

Orchestration parameters resolve in strict order of precedence:

1. **CLI Overrides (Highest Precedence)**:
   Flags passed directly to `along orchestrate <slug>`:
   ```bash
   along orchestrate <slug> --profile cross-tiered --model "claude-3-7-sonnet" --timeout 2400
   ```
2. **Issue Front-Matter**:
   Specified in `.along/ISSUES/<slug>.md`:
   ```yaml
   ---
   slug: core-compiler-refactor
   orchestration: cross-tiered
   ---
   ```
3. **Repository Profiles Directory**:
   Matching `.along/orchestration/<name>.yaml` file.
4. **Repository Default Configuration**:
   Default profile specified in `along.yaml` or `.along/config.yaml`:
   ```yaml
   orchestration: "direct"
   ```
5. **Built-in Fallback (Lowest Precedence)**:
   In-memory `direct` mode using the currently active agent runtime.

### 3.2 Phased Execution Lifecycle

The execution lifecycle coordinates across isolated subprocesses:

1. **Phase 1: Scout (Research)**: Generates `research.md` containing symbols, dependencies, and blast radius.
2. **Phase 2: Architect (Living Plan)**: Creates `plan.md` with numbered steps (`Step 1`, `Step 2`). Requires human or automated plan approval before mutating code.
3. **Phase 3 & 4: Step Implementation & Review Loop**:
   - `Implementer` executes Step N, updates code, and records touched files.
   - `Reviewer` audits git diff, executes automated tests, and issues a verdict (`PASS` / `FAIL`).
   - On `PASS`, advances to Step N+1. On `FAIL`, increments retry counter and feeds defects back into the prompt.
4. **Phase 5: Wrap & Closeout**: Reconciles history, synchronizes knowledge base projections, and creates release commit.

### 3.3 OpenAI-Compatible Proxy Prompt Caching & Headless Prompt Delivery

Custom OpenAI-compatible endpoints and headless CLI wrappers introduce two common operational failure modes: silent prompt-cache misses across proxies and process hangs from stdin vs positional argument mismatches.

#### OpenAI-Compatible Proxy Caching Compatibility
When configuring runtimes such as OpenCode with `@ai-sdk/openai-compatible` or routing requests through a custom OpenAI-compatible proxy, sessions can exhibit 0% prompt cache hits (`cache_read_tokens = 0`) even when native upstream providers achieve high prefix cache reuse:
- **Response schema mismatch (`prompt_cache_hit_tokens` vs `cached_tokens`)**: DeepSeek-style endpoints report prefix cache hits in `usage.prompt_cache_hit_tokens` (and cache misses in `usage.prompt_cache_miss_tokens`), whereas `@ai-sdk/openai-compatible` and standard OpenAI chat completions expect `usage.prompt_tokens_details.cached_tokens`. Proxies that pass responses through without translating `prompt_cache_hit_tokens` into `prompt_tokens_details.cached_tokens` report zero cached reads downstream.
- **Upstream prefix affinity**: Intermediate load balancers or stateless proxies that rotate backend workers or strip session/routing affinity break prefix caching on the upstream inference engine.
- **Prefix stability**: Injecting dynamic timestamps, changing system prompt headers, or reordering tool definitions between turns invalidates the cached prompt prefix.

Recommendations for cache-compatible operation:
1. Prefer native provider adapters or OpenAI-compatible proxies verified to preserve upstream prefix affinity and translate `prompt_cache_hit_tokens` into `prompt_tokens_details.cached_tokens`.
2. Keep system prompts, tool schemas, and static instruction prefixes deterministic across turns.
3. Monitor `cache_hit_ratio_pct` via `format_usage_summary` output surfaced by `along run`, `along wrap`, and `along doctor` (computed as `round(cache_read_tokens / (input_tokens + cache_read_tokens) * 100, 1)`). `DeepSeekHarnessRunner` (`scripts/alongkit/runner/deepseek.py`) and `OpenCodeRunner` (`scripts/alongkit/runner/opencode.py`) normalize `cache_read_tokens`, `prompt_cache_hit_tokens`, and `step_finish.part.tokens.cache.read` automatically.

#### Headless Prompt Delivery (`brief_via_stdin`) & Timeout Safety Net
- **Stdin vs positional CLI delivery**: `BaseRunner`, `ClaudeCodeRunner`, `CodexRunner`, and `DeepSeekHarnessRunner` default to `brief_via_stdin = True` (passing `"-"` and streaming the prompt over `stdin`) to stay below OS command-line limits such as Windows `cmd.exe` 8191-character limits. `OpenCodeRunner` defaults to `brief_via_stdin = False` because OpenCode 2.3.2+ expects the prompt as a positional CLI argument (`opencode run --format json ... <prompt>`). When wrapping custom DSH-compatible binaries that expect a positional argument rather than stdin, instantiate `DeepSeekHarnessRunner(..., brief_via_stdin=False)`.
- **Timeout safety net**: If a headless CLI expects positional arguments while receiving stdin (or stalls against an unresponsive endpoint), an unbounded `communicate()` call hangs indefinitely. `DeepSeekHarnessRunner` enforces a positive timeout safety net (`DEFAULT_TIMEOUT_SECONDS = 600`, overridable via `timeout` or `timeout_seconds`), terminating the full child process tree via `proc.kill_process_tree` on `subprocess.TimeoutExpired` and returning a structured `outcome: "timeout"`, `exit_code: 124` run record.

---

## 4. Invariants, Security Boundaries & Failure Modes

1. **Fail-Open Telemetry Invariant**:
   Network failures, timeouts, or unreachable OpenObserve instances MUST NOT halt or crash orchestrator execution. Failed span batches are safely appended to local disk WAL files (`.along/.session/<slug>/telemetry/spool.wal`).
2. **Single-Run Concurrency Claim**:
   Only one supervisor run may hold an active lock on an issue at any given time. Process claims are recorded in `state.json` with bounded TTL margins (`CLAIM_TTL_MARGIN_SECONDS = 300`).
3. **Plan Approval Guard**:
   Source code mutation is strictly locked until a living plan is verified and approved (`[gate: require-plan-approval]`).
4. **Workspace Isolation**:
   When configured with `workspace: worktree`, work is executed in an isolated git worktree branch linked with directory junctions for `node_modules` and `.venv`, protecting the parent working tree.


---

## 5. OpenObserve Telemetry Integration

During orchestration, `CrossRuntimeOrchestrator` instruments every execution phase with standard OpenTelemetry traces sent over OTLP/HTTP to OpenObserve.

### 5.1 Telemetry Configuration

Telemetry settings can be set in `along.yaml`, `.along/config.yaml`, or via standard OpenTelemetry environment variables:

```yaml
telemetry:
  endpoint: "http://localhost:5080/api/default/v1/traces"
  headers:
    Authorization: "Basic YWRtaW5AZXhhbXBsZS5jb206UGFzc3dvcmQxMjM="
  service_name: "actdim-along"
  timeout: 3.0
```

Environment variables supported:
- `OTEL_EXPORTER_OTLP_ENDPOINT`: Full traces endpoint URL (e.g. `http://localhost:5080/api/default/v1/traces`).
- `OTEL_EXPORTER_OTLP_HEADERS`: Comma-separated or key-value headers (e.g. `Authorization=Basic YWRtaW46cGFzc3dvcmQ=`).
- `OTEL_SERVICE_NAME`: Logical service identifier (defaults to `actdim-along`).

### 5.2 Span Hierarchy and Semantic Conventions

Every orchestration run generates a structured trace hierarchy:

- **Root Span**: `along.orchestrator.run`
  - Attributes:
    - `along.issue.slug`: Target issue slug.
    - `along.orchestration.profile`: Profile name (e.g. `cross-tiered`).
    - `along.orchestration.mode`: Execution mode (`direct`, `team-native`, `cross-runtime`).
    - `along.run.id`: Unique orchestrator execution identifier.
    - `along.workspace.mode`: `inherit` or `worktree`.

- **Phase Spans (Child Spans)**:
  - `phase.scout`: Execution of the research/scout role.
  - `phase.architect`: Generation and validation of `plan.md`.
  - `phase.step.<N>`: Implementation of step N by the designated worker.
    - Attributes: `runner.runtime`, `runner.model`, `step.number`, `process.exit_code`.
  - `phase.reviewer.<N>`: Audit of step N against reviewer rubrics.
    - Attributes: `reviewer.verdict` (`PASS` | `FAIL`), `reviewer.retries`.

### 5.3 Fail-Open Disk Spooling

Telemetry is strictly non-blocking and fail-open:
- If the OpenObserve server is offline, returns an HTTP error, or times out, spans are spooled to local disk in `.along/.session/<slug>/telemetry/spool.wal`.
- Telemetry network failures never cause orchestrator execution or test suites to fail.

---

## 6. Strategic Positioning: Quality Governance vs Process Multiplexers

When evaluating AI multi-agent orchestration for production engineering, it is crucial to distinguish between two fundamentally different layers of the software stack: **Infrastructure Process Multiplexers** and **Engineering Governance Protocols**.

### 6.1 The Limits of Pure Process Multiplexing (T3 Code, Herdr, BB IDE)

Recent desktop applications such as T3 Code, Herdr, and BB IDE function primarily as **Host Runtime Multiplexers and Terminal Switchboards**:
- **What they solve:** They manage OS-level processes, PTY sessions, WebSockets, desktop tabs, and git worktree directories, allowing a developer to run multiple terminal CLI sessions (Claude Code, Codex, Cursor) side-by-side.
- **Where they stop:** To a process multiplexer, the AI coding agent is an uninspected black box. The runner captures `stdout`, detects whether the process is idle or busy, and waits for exit code 0. It has no understanding of repository architectural invariants, test regressions, negative constraints, or whether the agent fabricated its verification claims.
- **The failure mode in real projects:** Running 5 uncoordinated agents in separate terminal windows without an engineering protocol rapidly produces merge conflicts, architectural drift, instruction decay, and unverified commits.

### 6.2 The Along Protocol Advantage: Deterministic Engineering Control

Along operates at the **Repository, Protocol, and Living Memory Layer**:
- **Living State Machine:** Tasks progress through deterministic, auditable roles: Supervisor -> Scout (read-only research) -> Architect (living plan) -> Implementer (step execution) -> Reviewer (rubric verification) -> Reassess (retry control) -> Wrap.
- **Quality Gates:** Code edits unlock only after explicit plan approval (`[gate: require-plan-approval]`); commits are strictly bound to issue slugs (`[gate: commit-issue-binding]`); and sessions cannot close without passing tests (`[gate: test_before_stop]`).
- **Unified Observability via OpenObserve:** Rather than parsing raw terminal streams, Along streams structured OpenTelemetry and OpenInference traces directly into OpenObserve, exposing exact step durations, token costs, runner exit codes, and failure events across all heterogeneous CLIs.
- **Git-Committed Memory:** State is not trapped in ephemeral application databases or local caches. Architectural decisions (ADRs), issue history, session logs, and living plans are committed directly to Git, surviving machine migrations and team handoffs.

### 6.3 Layered Symbiosis

Along does not compete with process multiplexers; it complements them:

```text
+-------------------------------------------------------------+
| User Interface & Terminal Layer (T3 Code, Herdr, Ghostty)   |
| (Manages PTYs, windows, notifications, remote access)       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
| Along Engineering Protocol Layer (along-team, alongkit)     |
| (Living Plan, Quality Gates, ADRs, Blast Radius, Blackboard)|
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
| Heterogeneous Agent Runtimes (Claude, Codex, OpenCode, AGY) |
| (Code generation, reasoning, tool execution)                |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
| Observability Layer (OpenObserve / OTLP)                    |
| (Real-time traces, span metrics, error events, audit logs)  |
+-------------------------------------------------------------+
```

An agent running inside Herdr, T3 Code, or a cloud VPS runner that adopts the Along protocol transforms from an unconstrained terminal process into a disciplined senior engineer that plans before modifying code, verifies every step against automated rubrics, and emits transparent telemetry.

### 6.4 Comparative Evaluation Matrix

| Capability / Invariant | Host Process Multiplexers (T3 Code, Herdr, BB IDE) | ActDim Along Protocol |
| :--- | :--- | :--- |
| **Primary Scope** | OS-level PTY/terminal multiplexing, process supervisor, and desktop GUI | Repository-level engineering protocol, living memory, and quality gates |
| **Verification & Review** | None (relies on model self-reporting and exit code 0) | Independent Reviewer role with deterministic pass/fail rubrics and retry limits |
| **Living Plan & Approval** | None (unstructured conversational chat) | Formal `plan.md` state machine with mandatory human/supervisor approval gate |
| **Observability Standard** | Ephemeral terminal logs and UI websocket events | Standard OpenTelemetry (OTel) traces streamed to OpenObserve |
| **Project Memory Persistence** | Local SQLite, app-specific thread caches, or lost on exit | Versioned repository artifacts (`.along/ISSUES/`, `DECISIONS/`, `HISTORY.md`) |
| **Multi-Model Heterogeneity** | Can launch multiple CLI tools concurrently | Can orchestrate specific roles across different CLIs with shared blackboard |
| **CI/CD & Headless Portability**| Requires desktop GUI or running Node/Electron daemon | Zero daemon requirement; runs in pure CLI, CI/CD, or containers |

