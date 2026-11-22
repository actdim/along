---
protocol: along
protocol_version: "4.9.1"
slug: local-llm-substrate-env-config
type: feat
status: open
priority: high
created: 2026-11-22
updated: 2026-11-22
agent: antigravity
tags: [llm, local, substrate, env, config, harness]
blocked_by: []
related: [feat--runtime-integration-tests-local-llm, feat--local-llm-micro-orchestrator, feat--webdev-nl-local-runner]
parent: feat--local-llm-runtime-harness
---

# Local LLM Substrate: .env Configuration & Directory Contract

## Problem

Along currently lacks a standardized, environment-driven configuration layer to discover, bind, and manage local LLM inference engines (such as llama-server, Ollama, or vLLM) on Windows and Linux hosts. 

Machine-specific absolute paths (such as `d:\Tools\LlamaCPP`) and custom ports cannot be committed to Git. Without a standardized contract:
1. Developers cannot configure their local inference substrate via a single `.env` file with `ALONG_*` environment variables.
2. The Along agent and tooling have no canonical documentation or contract defining what an external local tools directory is expected to provide (e.g. `start-server.ps1`, `stop-server.ps1`, `run/` runtime state, `/health` endpoint, model aliasing for `local`).
3. Automated integration tests and local runners cannot automatically probe or manage the lifecycle of the local server process.

## Requirements

### 1. Environment Variable & .env Support (REQ-1)
- Along MUST support loading configuration from `.env` files (or active environment variables) with the following standardized variables:
  - `ALONG_LOCAL_LLM_ENDPOINT`: Base URL of the OpenAI/Anthropic compatible local server (default: `http://127.0.0.1:8080/v1` or `http://127.0.0.1:8080`).
  - `ALONG_LLAMA_TOOLS_DIR`: Absolute or relative path to the external tools directory (e.g. `d:\Tools\LlamaCPP`).
  - `ALONG_LLAMA_PROFILE`: Target model profile name to run for tests and agents (default: `qwen25coder7`).
  - `ALONG_LLAMA_AUTO_START`: Boolean flag (`1`/`0`, `true`/`false`) indicating whether Along should attempt to auto-start the server when `/health` is unreachable.
  - `ALONG_LLAMA_AUTO_STOP`: Boolean flag (`1`/`0`, `true`/`false`) indicating whether Along should stop the server upon test completion.
- Along MUST provide a versioned `.env.example` in the repository root documenting all variables.
- The `.env` file MUST be included in `.gitignore`.

### 2. Tools Directory Contract (REQ-2)
- Along MUST specify and document the canonical contract for external tools directories in `docs/topic--local-llm-substrate.md`:
  - **Server lifecycle**:
    - `start-server.ps1 [profile]`: Powershell script accepting a profile argument and starting `llama-server.exe` in background or headless mode.
    - `stop-server.ps1`: Powershell script cleanly terminating the server and freeing VRAM.
  - **State files**:
    - `run/llama-server.pid`: Contains the PID of the active server process.
    - `run/llama-server.log`: Captures stdout and stderr for error diagnostics.
    - `run/active-profile.txt`: Names the currently loaded profile.
  - **Health probe**:
    - `GET /health`: Returns JSON with `{"status": "ok"}` when the model is fully loaded and ready for inference.
  - **Model alias contract**:
    - The server MUST expose the loaded model under both its specific alias (e.g. `qwen2.5-coder-7b-instruct`) and the canonical alias `local` so that all agent runtimes can target model `local` without config churn.

### 3. Core Substrate Helper Module (REQ-3)
- Along MUST provide a dedicated Python helper module `alongkit.local_llm`:
  - `load_config() -> LocalSubstrateConfig`: Resolves configuration from `.env` and `os.environ`.
  - `is_server_ready(endpoint: str) -> bool`: Probes the `/health` endpoint with timeout.
  - `ensure_server(config: LocalSubstrateConfig) -> bool`: Verifies server status, invoking `start-server.ps1` via powershell when needed and waiting for `/health` readiness.

## Implementation Plan

1. **Configuration & .env loader**:
   - Update `alongkit.environment` or introduce `alongkit.local_llm` to parse `.env` files using pure Python (no third-party dependencies).
   - Add `.env.example` to repository root with `ALONG_LOCAL_LLM_*` and `ALONG_LLAMA_*` definitions.
2. **Directory Contract Documentation**:
   - Write `docs/topic--local-llm-substrate.md` detailing the contract, expected folder layout, scripts, endpoints, and troubleshooting.
   - Register the article in `docs/INDEX.md`.
3. **Substrate Lifecycle Engine**:
   - Implement `alongkit/local_llm/substrate.py` with health checking, auto-start, and auto-stop capabilities.
4. **Unit Verification**:
   - Add unit tests in `tests/test_local_llm_config.py` verifying `.env` parsing, default fallback values, and mock lifecycle commands.

## Acceptance Criteria

- [ ] `.env.example` exists and documents all `ALONG_LOCAL_LLM_*` and `ALONG_LLAMA_*` variables.
- [ ] `.env` is confirmed in `.gitignore` and never committed.
- [ ] `docs/topic--local-llm-substrate.md` fully documents the directory contract and lifecycle scripts.
- [ ] `alongkit.local_llm` provides clean health checking and auto-start logic for Windows hosts.
- [ ] All unit tests pass in `python .along/scripts/test.py -k test_local_llm_config`.
