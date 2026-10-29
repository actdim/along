# Runtime CLI Fixtures

Captured on: 2026-10-29

## Claude Code (2.1.228)

- Version: `claude --version` -> `2.1.228 (Claude Code)`
- Help: `claude --help`
- Prompt via stdin: Supported via `-p` mode (`claude -p`).
- Commands:
  - OK sample: `claude -p --output-format json --no-session-persistence`
  - Write sample: `claude -p --output-format json --no-session-persistence --dangerously-skip-permissions`
- Schema notes:
  - Output is a single top-level JSON object.
  - Keys: `type`, `subtype`, `is_error`, `result`, `total_cost_usd`, `usage` (`input_tokens`, `output_tokens`), `session_id`.
  - Does not emit `tool_calls` or `cost` directly.

## OpenAI Codex (0.158.0)

- Version: `codex --version` -> `codex-cli 0.158.0`
- Help: `codex exec --help`
- Prompt via stdin: Supported using `-` as the prompt argument (`codex exec ... -`).
- Commands:
  - OK sample: `codex exec --json --sandbox workspace-write --ephemeral --color never -C <scratch> -`
  - Write sample: `codex exec --json --sandbox workspace-write --ephemeral --color never -C <scratch> -`
- Schema notes:
  - Output is JSONL events stream.
  - Events include `thread.started`, `turn.started`, `item.started`, `item.completed`, `turn.completed`.
  - Usage is recorded in `turn.completed.usage` (`input_tokens`, `output_tokens`).
  - Text is in `item.completed` with `item.type == "agent_message"`.
  - File changes appear under `item.completed` with `item.type == "file_change"`.

## OpenCode (1.18.32)

- Version: `opencode --version` -> `1.18.32`
- Help: `opencode run --help`
- Prompt via stdin: Supported via piped stdin (`opencode run ...`).
- Commands:
  - OK sample: `opencode run --format json --dir <scratch>`
  - Write sample: `opencode run --format json --dir <scratch> --auto`
- Schema notes:
  - Output is JSONL events stream.
  - Events include `step_start`, `text`, `tool_use`, `step_finish`.
  - Usage and cost are recorded in `step_finish.part.tokens` and `step_finish.part.cost`.
  - Text parts have `type: "text"` and `part.text`.
  - Tool invocations have `type: "tool_use"`, with `part.tool` and `part.state.input.filePath`.
