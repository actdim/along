---
protocol: along
protocol_version: "4.9.0"
slug: windows-ci-line-endings
type: bug
status: done
completed: 2026-11-15
priority: high
created: 2026-11-15
updated: 2026-11-15
agent: antigravity
tags: [ci, gitattributes, line-endings, windows]
blocked_by: []
related: []
plan_status: approved
---

# Fix Windows CI line ending normalization and gitattributes defaults

On Windows CI runners (windows-latest) where Git defaults to core.autocrlf=true, files not explicitly declared with eol=lf in .gitattributes (such as *.js, *.ts, and generic text files) are checked out with CRLF (\r\n) line endings. This caused test_install_and_registration in test_opencode_runtime.py to fail across all Python versions on windows-latest because install_opencode_hooks compares raw file content against normalized LF output without newline normalization.

## Requirements
- REQ-1: .gitattributes MUST declare basic text default `* text=auto eol=lf` along with explicit rules for JS/TS files (`*.js text eol=lf`, `*.ts text eol=lf`, `*.tsx text eol=lf`, `*.json text eol=lf`, `*.css text eol=lf`, `*.html text eol=lf`) while preserving CRLF for `*.ps1` and `*.bat`.
- REQ-2: `install_opencode_hooks` in `scripts/alongkit/hooks/config.py` MUST normalize line endings before checking if the target file is already up to date.
- REQ-3: Unit tests in `tests/test_opencode_runtime.py` MUST verify idempotency when source template content contains CRLF line endings.

## Acceptance Criteria
- [x] .gitattributes updated with basic text default and explicit frontend/script extensions.
- [x] install_opencode_hooks compares content with normalized newlines.
- [x] Unit test explicitly testing CRLF idempotency passes.
- [x] Full unit test suite passes cleanly.
