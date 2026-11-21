# Plan: Self-Contained Offline NL-to-WebDev Step Compiler and Runner

## Goal
Implement a self-contained, offline natural-language-to-WebDev step compiler and runner (`along webdev nl`) that converts conversational user test instructions into executable, schema-validated `along-webdev` Playwright scenarios without external cloud dependencies.

## Architecture & Subsystems

### 1. Local Inference Client (`scripts/alongkit/webdev/local_llm.py`)
- Define class `LocalInferenceClient`:
  - Strategy 1: OpenAI-compatible HTTP daemon auto-discovery:
    - Probes `http://127.0.0.1:11434/v1` (Ollama) or `http://127.0.0.1:8080/v1` (llama-server / vLLM / LM Studio).
    - Lightweight HTTP request using Python standard library `urllib.request` (zero external dependencies).
  - Strategy 2: Deterministic rule-based template compiler:
    - Provides instant offline fallback when no local LLM server daemon is active.
    - Pattern-matches standard browser instructions:
      - Navigation: "открой / перейди / open / visit <url>" -> `navigate: <url>`
      - Typing: "введи / заполни / type / fill <value> в <field>" -> `fill: <selector>, <value>`
      - Clicks: "кликни / нажми / click / press <button>" -> `click: <selector>`
      - Assertions: "проверь / убедись / assert / verify <text>" -> `assert_visible: <selector>`
      - Screenshots: "сделай скриншот / screenshot / capture" -> `screenshot: <path>`

### 2. Natural Language Scenario Compiler (`scripts/alongkit/webdev/compiler.py`)
- Define class `NLScenarioCompiler`:
  - Structured prompt engineering:
    - Concise JSON-schema / YAML specification with few-shot examples.
    - Strict instruction to produce only valid `along-webdev` scenario steps.
  - Security & Origin Validation:
    - Whitelist validation: ensures navigation targets adhere to allowed local origins (e.g. `localhost`, `127.0.0.1`) unless explicitly configured.
    - Redaction: strips potential sensitive secrets before emitting scenario.
    - Structural validator: asserts all generated steps have valid actions (`navigate`, `click`, `fill`, `assert_visible`, `screenshot`, `wait_for`).

### 3. CLI Subcommand Integration (`scripts/along_webdev.py`)
- Add subcommand parser: `along webdev nl "<instruction>"`:
  - `--url <base_url>`: Optional base URL prefix for relative navigation paths.
  - `--backend {auto,local-http,template}`: Inference backend selection (default: `auto`).
  - `--dry-run`: Output generated YAML scenario to stdout without launching browser.
  - `--run`: Execute compiled scenario via `AlongWebDevRunner` and emit `run-result.json`.

### 4. Tests & Verification
- `tests/test_webdev_local_llm.py`:
  - Unit tests for template compiler patterns (Russian and English prompts).
  - Unit tests for local HTTP inference client with mocked server responses.
  - Unit tests for origin whitelist enforcement and invalid syntax rejection.
  - End-to-end dry-run verification.
- Verification gates:
  - Run `python .along/scripts/test.py -k test_webdev_local_llm`.
  - Run `along sanitize`.
  - Run `python scripts/along_kb_sync.py --check`.

### 5. Documentation
- Document `along webdev nl` in `docs/topic--cli-reference.md` and `docs/topic--setup-and-workflow.md`.
- Synchronize knowledge base via `along kb-sync`.
