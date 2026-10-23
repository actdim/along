---
protocol: along
protocol_version: "4.5.3"
slug: autonomous-container-build-and-firewall
type: bug
status: open
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: claude-code
tags: [docker, firewall, security, autonomous]
blocked_by: []
related: [feat--isolated-environment-docker]
---

# Autonomous container image does not build and its firewall fails open

## Problem

Review of commit ab51db5 (`feat--isolated-environment-docker`): `docker/`, `scripts/alongkit/environment.py`,
`scripts/alongkit/commands/env.py`.

- `docker/Dockerfile` runs `groupadd -g 1000 along` on `ubuntu:24.04`, which already ships user
  and group `ubuntu` with UID/GID 1000: the build aborts. No test builds the image.
  `docker/Dockerfile` and `docker/Dockerfile.autonomous` are byte-identical.
- The firewall fails open: `init-firewall.sh` exits 0 without NET_ADMIN, `entrypoint.sh` adds
  `|| true`, and a mid-script error leaves partial rules while the agent starts unrestricted.
- `ALONG_EXTRA_EGRESS` never reaches the firewall: the script runs through `sudo`, whose
  `env_reset` strips it.
- `iptables -t nat -F/-X` flushes the rules Docker's embedded DNS (127.0.0.11) needs on a
  user-defined compose network, so name resolution and all egress likely fail.
- DNS on port 53 is open to any destination (tunnelling); there are no `ip6tables` rules.
- Allowlisted hosts are resolved once at startup; CDN-backed registries rotate addresses.
- `environment.py` interpolates `name`, `repo`, `branch` and hosts into `env.yaml` and
  `compose.yaml` without escaping (key injection such as `privileged: true`); the env name is not
  validated (`../x`); a bad `env.yaml` is silently replaced with defaults.
- `env up`, `env down`, `env update` report success when docker fails; `--build` does nothing.
- `GITHUB_TOKEN` is embedded in the clone URL and persists in `/workspace/.git/config`.
- `tests/test_along_env.py::test_cli_up_status_and_down_lifecycle` runs real `docker compose up`
  when Docker is present (not hermetic).

## Requirements
- REQ-1: The image MUST build on `ubuntu:24.04` (reuse or rename the UID 1000 user); one Dockerfile.
- REQ-2: The container MUST refuse to start the agent when the firewall cannot be applied in full (fail closed), unless an explicit `ALONG_FIREWALL=off` is set.
- REQ-3: The extra egress allowlist MUST reach the firewall (pass it as an argument or a root-owned file, not through `sudo` env).
- REQ-4: The firewall MUST preserve Docker's DNS NAT rules and allow DNS only to the configured resolver.
- REQ-5: IPv6 egress MUST be blocked or filtered with the same allowlist.
- REQ-6: Generated YAML MUST be produced with ruamel (or escaped), and env names MUST be validated.
- REQ-7: `env up/down/update` MUST exit non-zero when the docker command fails.
- REQ-8: Git credentials MUST NOT persist in the repository config.
- REQ-9: Tests MUST be hermetic: no real docker invocation in the default suite.

## Acceptance Criteria
- [ ] `docker build` succeeds (CI job or documented manual check with output recorded).
- [ ] Without NET_ADMIN the container exits with a clear firewall error.
- [ ] A host in `egress_allowlist` is reachable; a host outside it and any IPv6 address are not.
- [ ] A `--repo` value with `"` or a newline yields valid YAML with no extra keys.
- [ ] Regression tests cover each criterion and fail on the old code; `python .along/scripts/test.py` is green.
