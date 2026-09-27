---
protocol: along
protocol_version: "4.1.0"
slug: golang-ecosystem-support
type: feat
status: open
priority: high
created: 2026-09-27
updated: 2026-09-27
agent: antigravity
tags: [go, golang, rules, dep-scan, lifecycle, cloud-native]
milestone: v5.1.0-language-ecosystem-expansion
blocked_by: []
related: []
---

# Go (Golang) Ecosystem Support (Rules, Dep-Scan & Lifecycle)

## Goal
Implement end-to-end Along protocol support for the Go (Golang) ecosystem, including idiomatic engineering rules, Go modules dependency scanning, and automated lifecycle hook detection.

## Problem Statement
Go is a foundational language for cloud-native infrastructure, CLI utilities, and microservices. While `along_dep_scan.py` notes `go.mod` as an ecosystem marker, it does not scan dependencies or locate AI guidelines in the Go module cache. Furthermore, Along lacks a dedicated `rules/languages/go.md` rule pack and does not auto-detect `go test` or `go build` lifecycle commands.

## Technical Specifications

### 1. Language Rule Pack
- Create `rules/languages/go.md`:
  - Idiomatic error handling (explicit wrapping with `%w`, avoiding panics).
  - Concurrency safety (goroutine lifecycle, cancellation via `context.Context`, avoiding channel leaks).
  - Interface design (small, consumer-defined interfaces).
  - Standard testing (`testing.T`, table-driven tests, subtests).
- Register signatures in `alongkit.rules.RULE_SIGNATURES`:
  - `go.mod` -> `languages/go.md`
  - `go.work` -> `languages/go.md`
  - `*.go` -> `languages/go.md`

### 2. Dependency & Module Scanner (`along_dep_scan.py`)
- Implement `scan_go_project_deps(project, repo_root, internal_map)`:
  - Parse `go.mod` `require (...)` and single-line `require` statements.
  - Inspect `vendor/` directory if present.
  - Locate module cache: `$GOPATH/pkg/mod/` or `~/go/pkg/mod/` (handling case-encoded module paths like `!github.com`).
  - Scan for AI documentation (`AGENTS.md`, `llms.txt`, `docs/`) and exported invariants in cached modules.
  - Support `go.work` multi-module workspace internal DAG linking.

### 3. Lifecycle Runner (`alongkit/lifecycle.py`)
- Add auto-detection for Go projects (`go.mod`):
  - `build`: `go build ./...`
  - `test`: `go test -v=false ./...`
  - `dev`: `go run .` (or `main.go` / `cmd/server/main.go` detection)

## Acceptance Criteria
- [ ] `along rules attach` auto-attaches `go.md` when project carries Go files.
- [ ] `along dep-scan` discovers Go module dependencies and records them in `topic--dependencies.md`.
- [ ] `along test` and `along build` auto-synthesize verified Go hooks.
- [ ] Unit and hermetic tests verify Go manifest parsing and cache resolution.
