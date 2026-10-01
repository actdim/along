---
protocol: along
slug: agent-run-protocol
title: Agent Run Protocol (ARP/AEP) & OpenTelemetry Engine
type: architecture
created: 2026-09-25
updated: 2026-09-25
tags: [telemetry, opentelemetry, openinference, tracing, arp, aep, redactor, offloader, spool]
sources:
  - path: scripts/alongkit/telemetry/models.py
  - path: scripts/alongkit/telemetry/conventions.py
  - path: scripts/alongkit/telemetry/redactor.py
  - path: scripts/alongkit/telemetry/offloader.py
  - path: scripts/alongkit/telemetry/spool.py
  - path: scripts/alongkit/telemetry/otlp.py
  - path: scripts/alongkit/telemetry/tracer.py
  - path: scripts/alongkit/runner/stream.py
  - path: scripts/alongkit/runner/antigravity.py
  - path: scripts/alongkit/proc.py
  - path: scripts/along_exec.py
---

# Agent Run Protocol (ARP/AEP) & OpenTelemetry Engine

## 1. System Topology & Architecture Overview

The Along Agent Run Protocol (ARP), also referred to as the Agent Execution Protocol (AEP), defines a standardized observability, telemetry, and execution tracking engine for autonomous agent workflows. Modern AI agent operations execute non-deterministic cycles of LLM inference, multi-step chain reasoning, external tool usage, and subprocess execution. Without rigorous runtime tracing, debugging multi-agent swarms, identifying token bottlenecks, and investigating protocol violations becomes intractable.

The ARP engine bridges semantic OpenInference standards and OpenTelemetry (OTel) GenAI semantic conventions into Along. It provides real-time, vendor-neutral telemetry with local disk buffering and offline survivability.

```text
+-----------------------------------------------------------------------------------+
|                            Along Agent Runtime (Harness)                          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                        Root Span: SpanKind.AGENT                            |  |
|  |    along.run.id, along.issue.slug, along.agent.name, along.observability    |  |
|  +-----------------------------------------------------------------------------+  |
|          |                                              |                         |
|          v                                              v                         |
|  +-----------------------------+              +--------------------------------+  |
|  |    SpanKind.CHAIN (Step)    |              |     SpanKind.TOOL (Execution)  |  |
|  |   turn_seq, phase, retries  |              |    tool.name, process.cmd      |  |
|  +-----------------------------+              +--------------------------------+  |
|          |                                              |                         |
|          v                                              v                         |
|  +-----------------------------+              +--------------------------------+  |
|  |     SpanKind.LLM (Model)    |              |    Subprocess: run_capture     |  |
|  |   gen_ai.usage, prompt/resp |              |   pid, exit_code, stdout/err   |  |
|  +-----------------------------+              +--------------------------------+  |
+-----------------------------------------------------------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
        +-----------------------------+     +-----------------------------+
        |     Sensitive Data Scrub    |     |      Payload Offloading     |
        |        class Redactor       |     |   class ArtifactOffloader   |
        |  API keys, tokens, paths    |     |   >10 KB or >50 lines to    |
        +-----------------------------+     |  .along/artifacts/<run_id>/ |
                       |                    +-----------------------------+
                       +-----------------+-----------------+
                                         |
                                         v
                         +-------------------------------+
                         |     Export & Failover Engine  |
                         |      class OTLPExporter       |
                         +-------------------------------+
                                         |
                    +--------------------+--------------------+
                    | (HTTP 2xx Success)                      | (Connection Error / Timeout)
                    v                                         v
     +-----------------------------+          +-----------------------------------+
     |   OTel / OTLP Collector     |          |  Local Write-Ahead Log (WAL)      |
     |   http://localhost:4318     |          |  class Spooler                    |
     |   /v1/traces                |          |  .along/telemetry/spool/<run>.wal |
     +-----------------------------+          +-----------------------------------+
                                                              |
                                                              | along telemetry flush
                                                              v
                                              +-----------------------------------+
                                              | Flushed to Collector on Reconnect |
                                              +-----------------------------------+
```

Telemetry is instrumented non-intrusively across the core Along architecture:
- Session Blackboards and Agent Lifecycle: Tracks execution turns, plan revisions, and autonomous task completions.
- Subprocess Execution via `run_capture`: Captures terminal process invocations, exit codes, process IDs, and outputs.
- Declarative Gate Enforcements: Hooks report gate validations and circuit breaker trip events directly into active spans.
- Offline-First Durability: Telemetry never disrupts agent runs if the network is absent or the OTel collector is offline.

---

## 2. Core Components & Span Hierarchy

The telemetry architecture centers on six core modules under `scripts/alongkit/telemetry/`:

### 2.1 Span Taxonomy & Semantic Hierarchy (`SpanKind`)
The engine categorizes execution scopes into four distinct `SpanKind` classifications:
1. `SpanKind.AGENT`: The root span representing the end-to-end agent run. Carries run metadata including `along.run.id`, `along.issue.slug`, `along.agent.name`, and `along.observability.level`.
2. `SpanKind.CHAIN`: Represents sequential reasoning chains, workflow steps, or multi-turn loops. Carries turn sequences (`along.turn.seq`), step titles (`along.turn.title`), phases (`along.turn.phase`), and retry counters (`along.turn.retries`).
3. `SpanKind.TOOL`: Encompasses external tool executions, file system operations, and shell executions. Carries `tool.name`, `tool.parameters`, and process execution details.
4. `SpanKind.LLM`: Encapsulates prompt evaluations, model inference calls, and token generation. Carries OpenInference model metadata (`llm.model_name`), standard OTel GenAI system identifiers (`gen_ai.system`), and token usage counters (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`).

### 2.2 Trace Coordinator (`Tracer`)
`Tracer` coordinates trace context across nested execution scopes. It manages:
- 128-bit W3C-compliant Trace IDs (`trace_id` as a 32-character hexadecimal string) and 64-bit Span IDs (`span_id` as a 16-character hexadecimal string).
- Stack-based active span scoping via `start_span(...)`, context managers, and `end_span(...)`.
- Automatic linkage of child spans to their `parent_span_id`.
- Global ambient registration via `Tracer.set_active(tracer)` and `Tracer.get_active()`, allowing detached subroutines such as subprocess execution to attach telemetry to active turns without manual dependency plumbing.

### 2.3 Secret Redactor (`Redactor`)
Prior to buffering or exporting any span attributes, span events, or payload text, `Redactor` scrubs confidential credentials:
- Private Cryptographic Keys: Scans for PEM blocks (`-----BEGIN RSA/EC/OPENSSH/DSA PRIVATE KEY-----`) and replaces them with `[REDACTED_PRIVATE_KEY]`.
- Anthropic API Keys: Detects `sk-ant-(api03-)?...` keys and replaces them with `sk-ant-[REDACTED]`.
- OpenAI API Keys: Detects `sk-...` and `sk-proj-...` keys and replaces them with `sk-[REDACTED]`.
- GitHub Access Tokens: Detects `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, and fine-grained `github_pat_` tokens, replacing them with `[REDACTED_GITHUB_TOKEN]`.
- AWS Access Keys: Detects `AKIA...` and `ASIA...` 20-character keys, replacing them with `[REDACTED_AWS_KEY]`.
- Bearer Authorization Headers: Detects `Bearer <token>` HTTP headers and masks values.
- Generic Password & Secret Assignments: Matches `api_key = "..."`, `password: "..."`, and `client_secret: "..."`, masking the literal values.
- Home Directory Paths: Normalizes absolute user directory paths across Windows (`C:\Users\<user>`), macOS (`/Users/<user>`), and Linux (`/home/<user>`) to prevent leaking local developer usernames.

### 2.4 Artifact Offloader (`ArtifactOffloader`)
Large terminal outputs, build logs, and multi-megabyte tool payloads degrade OTel collector performance and exceed message limits. The `ArtifactOffloader` applies deterministic size threshold rules:
- Offload Trigger: Any text payload exceeding 10 KB (10,240 bytes) OR exceeding 50 lines of text.
- Storage Location: Persisted atomically under `.along/artifacts/<run_id>/<sha256>.<ext>`.
- Truncated Inline Preview: The span attribute retains a 20-line, 1,000-character preview ending with an explicit reference marker: `... [Output offloaded to .along/artifacts/<run_id>/<sha256>.<ext> (<bytes> bytes, <lines> lines)]`.
- Metadata Annotation: Generates an `ArtifactRef` data structure recording the file path, SHA-256 digest, exact byte count, line count, and MIME type.
- Distilled Observations: When a command runs through `proc.run_capture(distill=True)`, `Tracer.record_command_result(observation=...)` sets the span output to the distilled observation (`alongkit.distill`, at most 50 lines / 2 KB) and force-offloads the raw stdout and stderr to the artifact whatever their size (`maybe_offload(force=True)`). The active execution span stays small, and the raw text remains reachable through `along.artifact.ref`.

### 2.5 Fail-Open Write-Ahead Log Spooler (`Spooler`)
If network export fails or the OTel collector endpoint is unreachable, the engine never crashes or interrupts agent workflows:
- Disk WAL Spool: Records spans immediately as newline-delimited JSON (JSON lines) into `.along/telemetry/spool/<run_id>.wal`.
- Durability: Flushes and executes `os.fsync` after writing each span line.
- Re-read & Clearance: Supports atomic extraction (`read_spool()`) and safe deletion (`clear()`) once exported.

### 2.6 OTLP Exporter (`OTLPExporter`)
`OTLPExporter` formats spans into the official OpenTelemetry `v1/traces` JSON schema via `build_otlp_payload(...)` and transmits batches via HTTP POST:
- Default Endpoint: `http://localhost:4318/v1/traces`.
- Fallback & Spooling: If an HTTP connection error or timeout occurs, `OTLPExporter` automatically offloads the failed batch to the local `Spooler`.
- Deferred Flushing: Provides `flush_spool(...)` to replay stored WAL records once connectivity resumes.

---

## 3. Data Flow & Telemetry Execution Workflows

Telemetry generation flows hierarchically throughout an agent session:

```text
Agent Harness           Tracer / Stack             Redactor / Offloader         OTLP / Spooler
     |                         |                            |                          |
     |--- start_run() -------->|                            |                          |
     |                         |-- create AGENT span ------>|                          |
     |                         |<-- sanitized root span ----|                          |
     |                         |                                                       |
     |--- step / turn -------->|                                                       |
     |                         |-- create CHAIN span ------>|                          |
     |                         |<-- sanitized turn span ----|                          |
     |                         |                                                       |
     |--- run_capture(cmd) --->|                                                       |
     |        |                |-- create TOOL span ------->|                          |
     |        v                |                            |-- maybe_offload() ------>| (if >10KB / >50 lines)
     |    subprocess.Popen     |                            |   write to .along/art..  |
     |    proc.communicate()   |                            |<-- preview + ArtifactRef |
     |        |                |-- record_command_result -->|                          |
     |        |                |                            |-- sanitize_text() ------>|
     |        |<---------------|                            |<-- clean stdout/stderr --|
     |                         |                                                       |
     |--- end_span() --------->|                                                       |
     |                         |-- buffer span -------------+                          |
     |                         |                            |                          |
     |--- end_run() ---------->|                            |                          |
     |                         |-- flush_buffered_spans --->+------------------------->|
     |                         |                                                       |-- HTTP POST to OTLP
     |                         |                                                       |   (on fail: write WAL)
```

### 3.1 Subprocess Telemetry Integration (`proc.run_capture`)
All text-capturing subprocess calls in Along execute via `alongkit.proc.run_capture`. Telemetry is linked automatically:
1. Active Tracer Discovery: When `run_capture` is invoked, it queries `Tracer.get_active()`. If an active tracer and span exist, subprocess execution attaches directly to that span context.
2. Anomaly & Circuit Interception: If a prohibited command violates runtime gates (e.g. global package manager execution), `run_capture` intercepts execution, trips the circuit breaker, and logs a command failure span event with exit code 126 before any process spawns.
3. Execution Metrics: On process completion, `run_capture` captures process ID (`process.pid`), complete command line (`process.command_line`), and process return code (`process.exit.code`).
4. Output Scrubbing & Offloading: The command stdout and stderr are scrubbed through `Redactor.sanitize_text(...)`. If the output exceeds 10 KB or 50 lines, `ArtifactOffloader` saves the raw stream to `.along/artifacts/<run_id>/` and returns a truncated preview with the artifact digest.

---

## 4. Invariants, Failure Modes & Redaction Guarantees

The telemetry subsystem adheres to four non-negotiable architectural guarantees:

### 4.1 Fail-Open Telemetry Invariance
Telemetry is strictly auxiliary. An agent run MUST NEVER fail due to telemetry network failures, collector downtime, disk serialization errors, or OTel schema changes:
- Network Outages: When HTTP requests to the collector fail or time out, spans are routed to `.along/telemetry/spool/<run_id>.wal`.
- Spool Failures: If disk write permissions fail, exceptions are suppressed, and the primary agent execution proceeds unaffected.
- Zero Execution Blocking: Telemetry calls utilize non-blocking routines or strict timeouts (default exporter timeout: 3.0s, connectivity probe timeout: 1.5s).

### 4.2 Credential Redaction Invariance
Under no circumstances may plaintext API tokens or developer credentials appear in exported OTel payloads, local WAL logs, or offloaded artifacts. Redaction rules are evaluated in deterministic precedence (e.g. `sk-ant-` evaluated before generic `sk-` tokens) to ensure complete masking.

### 4.3 Clean ASCII Storage Standard
All emitted JSON files, WAL records, artifacts, and documentation follow strict Clean ASCII encoding:
- Prohibited Characters: Unicode em-dashes, typographic curly quotes, unicode ellipses, non-breaking spaces, and BOM markers are strictly barred.
- Deterministic Serialization: `json.dumps(..., ensure_ascii=True)` guarantees transport compatibility across heterogeneous platforms and terminals.

### 4.4 Idempotent Spool Flushes
Flushing buffered WAL logs is atomic:
- Span payloads are transmitted to the OTLP collector.
- Upon receiving HTTP 2xx confirmation from the endpoint, the corresponding `.wal` files are cleared.
- If export fails, the WAL files remain intact on disk, allowing subsequent retry via `along telemetry flush`.

---

## 5. CLI Reference & Telemetry Administration

Along provides dedicated administrative CLI subcommands under `along telemetry`:

### 5.1 Telemetry Status (`along telemetry status`)
Inspects the local telemetry buffer, pending WAL spool files, and collector connectivity:

```bash
along telemetry status [--json] [--endpoint <url>]
```

Parameters and behavior:
- `--json`: Emits structured machine-readable JSON containing `wal_count`, `total_bytes`, `endpoint`, `connected`, `endpoint_status`, and `wal_files`.
- `--endpoint <url>`: Overrides the target OTLP endpoint to test (defaults to `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `ALONG_TELEMETRY_ENDPOINT`, `OTEL_EXPORTER_OTLP_ENDPOINT`, or `http://localhost:4318/v1/traces`).
- Connectivity Probe: Sends an empty OTLP test payload with a fast 1.5s timeout. Reports connection status without blocking.

Terminal output example:
```text
Along Telemetry Status:
  Endpoint:      http://localhost:4318/v1/traces [unreachable (timed out)]
  Spool Dir:     /path/to/repo/.along/telemetry/spool
  Pending WALs:  2 file(s)
  Spooled Size:  4820 bytes
  WAL Files:
    - 372d529afe5e4c5392e396b08d799b5a.wal (2410 bytes)
    - 8a91b2c3d4e5f60718293a4b5c6d7e8f.wal (2410 bytes)
```

JSON output example:
```json
{
  "wal_count": 2,
  "total_bytes": 4820,
  "endpoint": "http://localhost:4318/v1/traces",
  "connected": false,
  "endpoint_status": "timed out",
  "spool_dir": "/path/to/repo/.along/telemetry/spool",
  "wal_files": [
    {
      "name": "372d529afe5e4c5392e396b08d799b5a.wal",
      "size_bytes": 2410
    },
    {
      "name": "8a91b2c3d4e5f60718293a4b5c6d7e8f.wal",
      "size_bytes": 2410
    }
  ]
}
```

### 5.2 Telemetry Flush (`along telemetry flush`)
Replays and exports all spooled spans to the active OTLP collector:

```bash
along telemetry flush [--endpoint <url>]
```

Parameters and behavior:
- `--endpoint <url>`: Overrides the target endpoint.
- Reads all `.wal` files under `.along/telemetry/spool/`.
- Transmits spans via `OTLPExporter(endpoint=...)`.
- On HTTP 2xx success: Clears the flushed `.wal` files and prints the total number of flushed spans.
- On network failure: Retains the WAL files on disk, reports the error to `stderr`, and exits with code 1.

## 6. Agent Runtime Runners & Antigravity Supervisor

Along provides supervised process launchers for native AI agent environments under `alongkit.runner`.

### 6.1 Antigravity Runtime Runner (`along run antigravity`)

The Antigravity runner (`alongkit.runner.antigravity.AntigravityRunner`) supervises Google Antigravity processes, enforcing workspace containment, active issue binding, and dual-channel telemetry.

```bash
along run antigravity [--dry-run] [-i|--issue <slug>] [--run-id <id>] [-e|--endpoint <url>] [-b|--binary <path>] [-- <agent-args...>]
along run agy [--dry-run] [-i|--issue <slug>] [--run-id <id>] [-e|--endpoint <url>] [-b|--binary <path>] [-- <agent-args...>]
```

#### Dual-Channel Observability Model
1. **Hook Channel (`antigravity_hook`)**: The lifecycle gate hook (`along_hook.py --runtime antigravity`) intercepts `PreToolUse` and `PostToolUse` events from the Antigravity IDE, recording structured tool spans with parameter verification, execution duration, and exit codes.
2. **Stream Channel (`stdout_stream`)**: The `ChunkedStreamSupervisor` captures child process stdout and stderr in binary mode, chunking output at 200 ms or 64 KB boundaries into `SpanEvent` records, while simultaneously teeing to the console and persisting logs to `.along/artifacts/<run_id>/stdout.log` and `stderr.log`.

#### Environment Variable Contract
When spawning the Antigravity runtime, the supervisor injects the following context variables:
- `ALONG_RUN_ID`: Unique hexadecimal run ID (32 chars) linking all spans and artifacts.
- `ALONG_ISSUE_SLUG`: Active issue key bound to the session (enforces `require-active-issue` gate).
- `ALONG_REPO_ROOT`: Absolute path to repository root, enforcing workspace containment.
- `ALONG_OBSERVABILITY_LEVEL`: Set to `complete` for full dual-channel tracing.
- `ALONG_OBSERVABILITY_SOURCES`: Set to `antigravity_hook,stdout_stream`.
- `ALONG_OTEL_ENDPOINT`: Optional OTLP trace collector endpoint.
- `PYTHONIOENCODING`: Forced to `utf-8`.
- `PYTHONUTF8`: Forced to `1`.

