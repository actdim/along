# Living Plan: autonomous-container-build-and-firewall

## Revision 1 (2026-10-29T12:14:23Z, plan approve --plan-file)

# Living Plan: bug--autonomous-container-build-and-firewall

Execution Mode: Role-Based (spans more than 3 files and crosses subsystems: docker assets, the `alongkit.environment` engine, the CLI router, tests, CI and docs)

## Context

Commit ab51db5 shipped an image that does not build, an egress firewall that fails open, drops the extra
allowlist, breaks Docker DNS and leaves IPv6 open, a CLI that writes YAML by string interpolation, and
docker failures reported as success. This plan makes the image build, makes the firewall fail closed,
makes generated config safe, and adds an opt-in real Docker verification path.

Facts the steps rely on (verified 2026-10-29):

- `docker/Dockerfile` and `docker/Dockerfile.autonomous` are byte-identical; only `tests/test_along_env.py`
  and `docs/topic--autonomous-environment.md` (section 4) reference them.
- `docker/Dockerfile:46` runs `groupadd -g 1000 along` on `ubuntu:24.04`, which already has user and group
  `ubuntu` 1000:1000. `:48` grants sudoers `NOPASSWD: /usr/local/bin/init-firewall.sh` with any arguments;
  `:64` is `USER along`. No `ipset` package.
- `docker/init-firewall.sh`: `:33-41` `exit 0` when `iptables` is missing or `iptables -L` fails; `:46-47`
  `iptables -t nat -F || true` and `-X`; `:63-64` port 53 open to any destination; `:68` `getent ahosts`
  once, IPv4 only; no `ip6tables`; `ALONG_EXTRA_EGRESS` read from env at `:18`.
- `docker/entrypoint.sh:8,10`: `init-firewall.sh || true`, skipped silently when `sudo -n` fails; `:21`
  builds `https://x-access-token:${GITHUB_TOKEN}@...`, so the token lands in `.git/config`.
- `scripts/alongkit/environment.py`: `save_env_config` (:124-160) and `generate_compose_yaml` (:177-236) build
  YAML from f-strings; `resolve_env_dir` (:77) only rejects an empty name; `load_env_config` (:95-101) swallows
  only `OSError` / `ValueError` (ruamel `YAMLError` and non-mapping documents unhandled); `env_down` (:400)
  ignores the `docker stop` return code; `env_update` (:557) ignores `pull`, and `--build` (:555) is a no-op
  (compose has no `build:`); `env_shell` (:525, :530) execs without `-u`; `DEFAULT_EGRESS_ALLOWLIST` (:32-41)
  duplicates the shell list and includes `api.telegram.org`.
- `scripts/alongkit/commands/env.py`: `up` (:115), `down` (:136), `update` (:251) always `sys.exit(0)` and print
  errors as "Notice"; `require_entity_name` (`commands/common.py:19`) only rejects a leading `-`.
- `tests/test_along_env.py:264` `test_cli_up_status_and_down_lifecycle` runs the real CLI, which calls
  `docker compose up` when Docker exists; `:309` asserts `useradd -u 1000 -g along`.
- ruamel is used via `bootstrap.require("ruamel.yaml")` (environment.py:96, frontmatter.py:143 `typ="rt"`).
- `feat--agent-execution-gate-telegram` section 7: long polling needs only outbound HTTPS to
  `api.telegram.org`, which must stay allowlisted.
- `.gitattributes` forces `*.sh` to LF. Git Bash exists at `/usr/bin/bash`, but `shutil.which("bash")` may hit
  the WSL launcher in `System32`.
- Docker 29.6.2 is installed but the daemon was not running at planning time; CI `.github/workflows/tests.yml`
  has an ubuntu-latest job where Docker is available.

## Steps

- [x] Step 1: One Dockerfile that builds; root entrypoint that drops privileges (REQ-1, REQ-3)
  - `git rm docker/Dockerfile.autonomous`; keep `docker/Dockerfile`.
  - User block: `if id ubuntu >/dev/null 2>&1; then userdel --remove ubuntu; fi`, then
    `groupadd -g 1000 along && useradd -u 1000 -g along -m -s /bin/bash along`.
  - Drop `sudo` from apt and delete the sudoers file (the agent must not rerun the firewall with chosen args).
  - Add `ipset` to apt (`iptables` already provides `ip6tables`).
  - Remove `USER along` (the entrypoint runs as root); keep `ENV HOME=/home/along`.
  - COPY the new `docker/git-credential-along` to `/usr/local/bin/` (Step 5).
  - Tests (`tests/test_along_env.py::TestDockerAssetsIntegrity`, rewrite `test_dockerfiles_exist_and_configured`):
    `Dockerfile.autonomous` does not exist; the Dockerfile contains `userdel --remove ubuntu`, no `sudoers`,
    no `groupadd -g 1000 along` before the `userdel`, and `ipset`; keep the runtimes, `actdim-along` and
    `VOLUME` asserts.

- [x] Step 2: Fail-closed entrypoint (REQ-2, REQ-3)
  - `docker/entrypoint.sh`: `FIREWALL_SCRIPT=/usr/local/bin/init-firewall.sh` on its own line (the test harness
    substitutes it).
  - Not root: exit 1 with `[Error] firewall: entrypoint must run as root`, unless `ALONG_FIREWALL=off`.
  - `ALONG_FIREWALL=off`: print `[Warning] firewall disabled by ALONG_FIREWALL=off` to stderr and skip it.
  - Otherwise write the validated `ALONG_EXTRA_EGRESS` to `/run/along/egress.list` (root-owned, 0644), run
    `"$FIREWALL_SCRIPT" --allow-file /run/along/egress.list`, and on a non-zero exit print
    `[Error] firewall could not be applied; refusing to start (set ALONG_FIREWALL=off to override)` and
    `exit 1`. No `|| true` anywhere.
  - Start the root refresher: `( while sleep "${ALONG_FIREWALL_REFRESH:-300}"; do "$FIREWALL_SCRIPT" --refresh
    --allow-file /run/along/egress.list || echo "[Warning] firewall refresh failed" >&2; done ) &`.
  - Run the clone and the final command as the agent user with
    `setpriv --reuid=1000 --regid=1000 --init-groups --no-new-privs`; the final command is
    `exec setpriv ... -- "$@"` (default `bash`).
  - Tests (new `tests/test_docker_scripts.py`):
    - Structural, always run: no `|| true` on a firewall line; `ALONG_FIREWALL` and `setpriv` present; no `sudo`.
    - Harness, `skipUnless(_real_bash())` (`_real_bash()` rejects paths under `System32` and checks
      `bash -c 'echo ok'`): copy the script to a tmp dir, rewrite the `FIREWALL_SCRIPT=` line to a stub, put
      fake `id` (prints 0), `setpriv` (execs the args after `--`) and `ipset` on PATH. (a) stub exits 3: the
      entrypoint exits non-zero, stderr contains "firewall", the final command did not run (marker absent);
      (b) `ALONG_FIREWALL=off`: the command runs; (c) `ALONG_EXTRA_EGRESS="a.example, b.example"`: the stub
      receives an allow-file holding both hosts.

- [x] Step 3: Firewall rewrite (REQ-2, REQ-4, REQ-5; also IP refresh)
  - `docker/init-firewall.sh`: `set -euo pipefail` and `trap 'lockdown; exit 1' ERR`; `lockdown` sets
    OUTPUT/INPUT/FORWARD policy DROP for v4 and v6 and flushes only the filter ACCEPTs.
  - Missing `iptables`, `ip6tables` or `ipset`, or a failing capability probe
    (`iptables -N ALONG_PROBE && iptables -X ALONG_PROBE`), is a fatal `exit 1` with a "firewall" message.
  - Never touch the nat table, so Docker's `DOCKER_OUTPUT` / `DOCKER_POSTROUTING` DNAT for 127.0.0.11 stays
    intact. Add a comment naming the alternative used by Anthropic's devcontainer script if a nat flush is
    ever needed: save `iptables-save -t nat | grep 127.0.0.11`, flush, recreate the two chains, replay.
  - Filter v4: flush filter OUTPUT/INPUT; allow `lo` and ESTABLISHED,RELATED; DNS udp/tcp 53 only to each
    `nameserver` in the resolv.conf (path from `ALONG_RESOLV_CONF`, default `/etc/resolv.conf`; 127.0.0.11 is
    covered by `lo`); allowlist via ipset `along-allow` (hash:net) with
    `-m set --match-set along-allow dst -p tcp -m multiport --dports 80,443 -j ACCEPT`; port 22 for github.com
    IPs via ipset `along-allow-ssh`; default policy DROP; end OUTPUT with
    `-j REJECT --reject-with icmp-admin-prohibited` for fast failure.
  - Hosts: defaults (identical to `DEFAULT_EGRESS_ALLOWLIST`, including `api.telegram.org`) plus `--allow-file`
    lines. Each entry must match `^[A-Za-z0-9.-]+$` or an IPv4 CIDR, anything else is fatal. Resolve with
    `getent ahostsv4`; an unresolved host is a warning, zero resolved IPs overall is fatal.
  - IPv6: `ip6tables -P INPUT/FORWARD/OUTPUT DROP`, allowing only `lo` and ESTABLISHED. If `ip6tables` fails
    because IPv6 is absent (`/proc/net/if_inet6` missing or `disable_ipv6=1`), treat it as blocked; otherwise
    the failure is fatal.
  - `--refresh`: build `along-allow-tmp`, `ipset swap`, destroy the old set; rules untouched; on failure the old
    set stays.
  - Self-check at the end: `curl --max-time 5 https://example.com` must fail, else exit 1.
  - Tests (`tests/test_docker_scripts.py`):
    - Structural: no `-t nat -F` / `-X`; `ip6tables -P OUTPUT DROP` present; no `--dport 53 -j ACCEPT`
      without `-d`; `--refresh` and `ipset swap` present; no `exit 0` before the rules.
    - Parity: parse the bash `DEFAULT_ALLOWLIST=( ... )` array; it equals
      `environment.DEFAULT_EGRESS_ALLOWLIST` and contains `api.telegram.org`.
    - Harness (real bash; fake `iptables` / `ip6tables` / `ipset` / `getent` / `curl` logging argv):
      (a) probe fails: exit != 0 and no `-P OUTPUT ACCEPT` left; (b) a rule failing mid-script triggers
      lockdown: the log ends with `-P OUTPUT DROP`, exit non-zero; (c) allow-file entry `bad;host` is
      rejected; (d) the fixture resolv.conf nameserver appears as `-d <ns>` on the port 53 rules.

- [x] Step 4: Safe YAML and name validation (REQ-6)
  - `environment.py`: `ENV_NAME_RE = ^[a-z0-9][a-z0-9_-]{0,62}$` (compose project and container-name safe;
    rejects `..`, `/` and uppercase) and `validate_env_name(name) -> str` raising `ValueError`; call it in
    `resolve_env_dir`, `env_up`, `env_down`, `env_status` (named), `env_logs`, `env_shell`, `env_update`.
  - `validate_egress_host(h)` with the shell's regex; `runtimes` must be a list of `[a-z0-9-]+`; `repo` and
    `branch` must not contain newlines or NUL.
  - `save_env_config`: build a dict and dump with ruamel `YAML(typ="rt")`,
    `indent(mapping=2, sequence=4, offset=2)`, `default_flow_style=False`, current key order.
  - `generate_compose_yaml`: build a dict and dump through a shared `_dump_yaml(data) -> str`; prepend the
    header comment as text; `environment` becomes a mapping (`ALONG_REPO_URL: <str>`) so the dumper quotes
    values. Add `init: true`, `security_opt: [no-new-privileges:true]`,
    `sysctls: {net.ipv6.conf.all.disable_ipv6: 1}` (defence in depth; the firewall still drops v6).
  - `load_env_config`: catch the ruamel `YAMLError`; raise a new `EnvConfigError(ValueError)` naming the file
    when the document is not a mapping or a field has the wrong type; never fall back to defaults.
  - `commands/env.py`: wrap each subcommand; `ValueError` (name) -> exit 2, `EnvConfigError` -> exit 1, both
    with `[Error]` on stderr.
  - Tests (`tests/test_along_env.py`, new class `TestEnvYamlSafety`): `repo='x"\nprivileged: true'` ->
    the parsed compose `services.runner` has no `privileged` key and `environment["ALONG_REPO_URL"]` equals
    the input (same round trip for `save_env_config` / `load_env_config`); a branch with `"`;
    `resolve_env_dir("../x")`, `"a/b"`, `"A"` raise `ValueError` and CLI `up ../x` exits 2; malformed
    `env.yaml` (`"a: [\n"`) or a list document raises `EnvConfigError`; egress host
    `"evil.com\n  privileged: true"` is rejected. Update `test_generate_compose_yaml_deterministic` to parse the
    YAML and assert values (`cap_add == ["NET_ADMIN"]`, volume keys, `runtime == "runsc"` with gVisor).

- [x] Step 5: Git credentials do not persist (REQ-8)
  - New `docker/git-credential-along` (bash): on `get`, read stdin; for `host=github.com` with `GITHUB_TOKEN`
    set, print `username=x-access-token` and `password=$GITHUB_TOKEN`; ignore `store` / `erase`.
  - Dockerfile: `git config --system credential.https://github.com.helper /usr/local/bin/git-credential-along`.
  - `entrypoint.sh`: clone `$ALONG_REPO_URL` unchanged (no token in the URL).
  - Tests: structural (`entrypoint.sh` has no `x-access-token:` or `${GITHUB_TOKEN}@`; the Dockerfile has the
    helper line); harness: `printf 'protocol=https\nhost=github.com\n\n' | GITHUB_TOKEN=t bash
    git-credential-along get` prints `password=t`; for `host=evil.com` the output is empty.

- [x] Step 6: Docker failures exit non-zero (REQ-7)
  - `env_down`: check the `docker stop` return code and set `error`.
  - `env_update`: run `pull` and check it (on failure set `error`, skip `up`); `up` is
    `["-f", f, "up", "-d"]` (drop `--build`).
  - `env_shell`: compose `exec -u along runner /bin/bash`; fallback `docker exec -it -u along`.
  - `commands/env.py`: when `res["error"]` is set for `up` (only when compose ran), `down` or `update`, print
    `[Error] <msg>` to stderr and `sys.exit(1)`; `--help` / usage stay exit 0.
  - Tests (in process: `handle_env_command` under `assertRaises(SystemExit)` with
    `environment.get_docker_compose_cmd` patched to `["docker", "compose"]` and `environment.subprocess.run`
    returning `returncode=1, stderr="boom"`): `up`, `down`, `update` exit 1 with `boom` on stderr; `update`
    argv has no `--build`; the `down` fallback with a failing `docker stop` exits 1; return code 0 exits 0.

- [x] Step 7: Hermetic default suite (REQ-9)
  - Rewrite `test_cli_up_status_and_down_lifecycle` in process with the Step 6 mocks plus
    `environment.shutil.which` patched to None for status; same outputs and exit codes.
  - `TestEnvCliCommands.setUp`: `self.env["PATH"] = os.path.dirname(sys.executable)` so no subprocess test can
    find docker; add `test_cli_up_without_docker_exits_1` (files created, exit 1, stderr names docker).
  - Proof: one test puts a fake `docker` (a `.cmd` or sh shim per OS) first on PATH that writes a marker file,
    runs the env CLI tests' commands, and asserts the marker does not appear.

- [x] Step 8: Opt-in real Docker verification and a CI job (acceptance criteria 1-3)
  - New `tests/test_docker_image_integration.py`,
    `skipUnless(os.environ.get("ALONG_DOCKER_TESTS") == "1" and shutil.which("docker"))`.
  - `setUpClass`: `docker build -f docker/Dockerfile -t along-autonomous:test .` (timeout 1800 s; assert rc 0,
    keep the output tail in the failure message); create a user-defined network `along-fw-<uuid8>` (exercises
    the embedded DNS); `docker run -d --cap-add NET_ADMIN --network N -e ALONG_EXTRA_EGRESS=example.org
    along-autonomous:test sleep infinity`; wait for the firewall ready line in the logs; `tearDownClass`
    removes the container and the network.
  - Assertions via `docker exec` (default user unless noted): `id -u` is 1000; `getent hosts github.com`
    succeeds; `curl -sS -o /dev/null --max-time 15 https://api.anthropic.com` rc 0; the same for
    `https://example.org` (extra allowlist); `https://example.com` rc != 0 (use a second container without
    extras, since example.com and example.org may share IPs); `dig @1.1.1.1 +time=2 +tries=1 example.com`
    fails; `docker exec -u 0 C ip6tables -S OUTPUT` contains `-P OUTPUT DROP` and
    `curl -6 --max-time 5 https://[2606:4700:4700::1111]` fails; `sudo -n true` fails;
    `git config --system --get credential.https://github.com.helper` is set.
  - Fail closed: `docker run --rm along-autonomous:test true` without NET_ADMIN gives rc != 0 and output
    containing "firewall"; with `-e ALONG_FIREWALL=off` rc 0.
  - `.github/workflows/tests.yml`: new job `docker` on ubuntu-latest with `ALONG_DOCKER_TESTS: '1'` running
    `python .along/scripts/test.py tests/test_docker_image_integration.py`.
  - Locally (Docker Desktop running): `ALONG_DOCKER_TESTS=1 python .along/scripts/test.py
    tests/test_docker_image_integration.py`; record the output in the session log (acceptance criterion 1).

- [x] Step 9: Docs, full suite, regression proof, commit, wrap
  - `docs/topic--autonomous-environment.md`: section 4 (one `docker/Dockerfile`; the `ubuntu` user replaced; no
    sudo; root entrypoint plus `setpriv`); section 5 (fail closed and `ALONG_FIREWALL=off`; DNS limited to the
    resolver; nat untouched; IPv6 drop; ipset refresh every `ALONG_FIREWALL_REFRESH` s; `api.telegram.org` for
    long polling); sections 3.1 / 3.3 (YAML shape, name rules, `init` / `security_opt` / `sysctls`); section 6
    (non-zero exits; `update` = pull + up); section 7 (DNS tunnelling through the embedded resolver as an
    accepted risk; the credential helper replaces the token in the URL); bump `updated:`.
  - `python .along/scripts/test.py` green; `along sanitize`.
  - Regression proof: `git stash push -- docker scripts/alongkit/environment.py scripts/alongkit/commands/env.py`,
    run the new test files, confirm every new test fails or errors (except the opt-in ones), `git stash pop`.
  - `git diff --stat`; commit via `/along-commit`; `along wrap autonomous-container-build-and-firewall
    --summary "..." --no-decisions`.

## Out of scope

- GitHub meta IP-range aggregation (DNS resolution plus periodic refresh is enough here).
- Filtering DNS tunnelling through Docker's embedded resolver (documented as an accepted risk).
- Installing Along into the image from the local checkout instead of PyPI; gVisor changes;
  `docker/along-runner.service` (a host unit, unaffected); separating orchestrator and worker containers.

## Rules for the executing agent

- Deviations within the ticket: `along plan revise autonomous-container-build-and-firewall --plan-file <path>
  --reason "..."`.
- A requirement that cannot be met (for example, the IPv6 drop is impossible under Docker Desktop):
  `along plan rework autonomous-container-build-and-firewall --reason "..."`, stop, ask the user.
- File content only through file tools (no heredocs, no `python -c`); ASCII only; `.sh` files LF.
- Tests only through `python .along/scripts/test.py [file]`; the default suite never invokes real docker.
- Never weaken a regression test to make it pass; every new test must fail on the stashed old code.
