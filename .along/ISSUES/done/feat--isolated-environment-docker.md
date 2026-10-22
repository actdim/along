---
protocol: along
protocol_version: "4.4.16"
slug: isolated-environment-docker
type: feat
status: done
completed: 2026-10-23
priority: high
created: 2026-10-17
updated: 2026-10-23
agent: claude-code
tags: [vps, docker, isolation, environment, mvp]
milestone: v5.0.0-agent-run-protocol-and-observability
parent: feat--autonomous-multi-runtime-mvp
blocked_by: [spike--headless-runtimes-on-linux]
related: [feat--vps-runner-daemon, feat--byoc-kubernetes-operator-and-private-sandboxes]
---

# along env up: one-command isolated Docker environment for autonomous runs

## Goal

On a fresh Ubuntu VPS with Docker installed, one command creates an isolated environment for a
repository and starts autonomous work in it. Decision: ADR-2026-10-17--docker-isolation-now-gvisor-later.

```bash
along env up myproj --repo git@github.com:actdim/along.git
```

## Model

- One environment = one folder on the host + one container.
- Host folder `/srv/along/envs/<name>/`:
  - `env.yaml` (about 10 lines): repository URL, branch, runtimes, Telegram chat id, egress allowlist additions.
  - `secrets.env`: model API keys, repo-scoped git token, Telegram bot token. Never committed.
  - generated `compose.yaml`.
- Volumes: repository clone, runtime auth homes (`~/.claude`, `~/.claude.json`, `~/.opencode`, `~/.codex`), package caches.
- Image: Ubuntu 24.04 base, Python with Along, Node 20 LTS, git, and the CLI runtimes selected by
  `spike--headless-runtimes-on-linux` (Claude Code `@anthropic-ai/claude-code`, OpenCode `opencode`,
  and optional fallback `gemini-cli`/`codex`). Google Antigravity is ruled out and excluded.
  Published image plus a Dockerfile for local builds.
- Container runs as a non-root user; the repository volume is the only writable project path.
- Egress allowlist by default: model APIs, GitHub, PyPI, npm registry, `api.telegram.org`
  (firewall init script in the style of the Claude Code reference devcontainer `init-firewall.sh`).
- The daemon (`feat--vps-runner-daemon`) is the container entrypoint; `restart: unless-stopped`
  replaces a systemd unit.
- gVisor: `runtime: runsc` switch in `env.yaml`, off by default, not part of the MVP.

## Commands

`along env up | down | status | logs [-f] | shell | update <name>`

## Secrets (accepted risks)

- Agents can read the model API keys they need: use per-VPS keys with spend limits.
- Git push uses a fine-grained token scoped to the repository; preferably only the orchestrator pushes.
- MVP keeps the Telegram token in the same container. Later: a control container (daemon, Telegram,
  push) and worker containers without those secrets.

## Acceptance Criteria
- [x] `along env up` on a fresh Ubuntu VPS with Docker produces a running environment in one command.
- [x] Writes outside the mounted volumes fail inside the container (verified by a test task).
- [x] Egress outside the allowlist fails; allowlisted hosts work.
- [x] Runtime login state survives `along env down` and `up`.
- [x] `env.yaml` stays under 20 lines for the default case.
- [x] Documented in `docs/topic--autonomous-environment.md` (guide).
