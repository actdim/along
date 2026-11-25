# Plan: Audit OpenCode custom OpenAI-compatible provider caching efficiency and runner prompt delivery resilience

## Execution Mode
Direct

## Context and Scope
Diagnostics during an OpenCode session revealed critical performance and resilience gaps in the OpenCode / DeepSeek integration:
1. Zero prompt cache hits: A custom OpenAI-compatible OpenCode provider processed 222k input tokens with 0 cache hits, whereas the default OpenCode free provider achieved 38.3M cache read tokens.
2. DSH headless runner prompt delivery: `DeepSeekHarnessRunner` defaults to stdin piping (`-`), which can hang headless runners if CLI arguments are expected.
3. Telemetry: Cache hit ratios and breakdown metrics are not currently summarized in Along tooling.

Target Issue: `task--opencode-deepseek-cache-configuration-audit`
Milestone: `v5.0.0-agent-run-protocol-and-observability`

## Step-by-Step Implementation Plan

### Step 1: OpenCode Custom Provider Configuration Audit
- Document findings from `~/.config/opencode/opencode.jsonc`:
  - The custom OpenAI-compatible provider uses `@ai-sdk/openai-compatible` pointing to an external proxy endpoint.
  - The proxy does not map DeepSeek `prompt_cache_hit_tokens` into OpenAI `prompt_tokens_details.cached_tokens`, or the proxy upstream does not maintain prompt prefix caches.
  - Document recommendations for cache-compatible configuration.

### Step 2: Headless Runner Prompt Delivery Configuration
- In `scripts/alongkit/runner/deepseek.py`:
  - Allow `brief_via_stdin` to be passed to `__init__` and configured per runner instance.
  - When `brief_via_stdin = False`, append `prompt` as a CLI argument instead of `"-"`.
  - Compute `cache_hit_ratio_pct` when parsing usage.
  - Add `format_usage_summary(usage)` helper.

### Step 3: Observability & Doctor Telemetry
- Expose cache hit ratio and token usage formatting across runners and diagnostics.

### Step 4: Unit Tests
- In `tests/test_runtime_adapters.py`:
  - Test `brief_via_stdin=False` command construction.
  - Test `cache_hit_ratio_pct` computation and `format_usage_summary`.

### Step 5: Verification
- Run `python .along/scripts/test.py tests/test_runtime_adapters.py`.
- Run full test suite and verify clean typography.
