#!/usr/bin/env python3
"""
configure_mcp.py - register the `code-review-graph` MCP server with a provider.

This file exists because the installers used to carry a 24-line Python program inside a
PowerShell here-string and a Bash double-quoted string, passed to `python -c`. The
protocol both installers ship forbids exactly that: content that crosses a shell, a
string literal and a source parser in sequence loses a backslash or a quote sooner or
later, and the failure is silent. `[bug--installer-parity-and-destructive-rules-overwrite]`
REQ-3.

It also stops the installers claiming a success they never had. Registration is written
only where the provider's configuration contract is verified; every other provider is
reported with its path and the snippet to add by hand. `alongkit.install` holds the
contracts and does the writing.

Stream contract (rules/platforms/cli.md): the report is the data. Without `--json` it is
the readable report on stdout; with `--json` the JSON takes stdout and the readable form
moves to stderr. Usage errors always go to stderr. Exit 0 when nothing failed, 1 when a
target could not be configured, 2 on a usage error.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()


from alongkit import install

USAGE = """Usage: python configure_mcp.py [options]

Targets (default: every provider):
  --provider NAME        claude | codex | opencode | antigravity (repeatable)

Behaviour:
  --include-unverified   also write providers whose config contract is unconfirmed
  --dry-run              report what would be written, write nothing
  --json                 machine-readable report on stdout
  -h, --help             this message

Homes (each defaults to the standard location under the user home):
  --user-home DIR        --claude-home DIR        --codex-home DIR
  --opencode-home DIR    --antigravity-home DIR
"""


def main():
    argv = sys.argv[1:]
    providers = []
    include_unverified = False
    dry_run = False
    as_json = False
    homes = {}
    home_flags = {
        "--user-home": "user", "--claude-home": "claude", "--codex-home": "codex",
        "--opencode-home": "opencode", "--antigravity-home": "antigravity",
    }

    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("-h", "--help"):
            sys.stderr.write(USAGE)
            return 0
        elif arg == "--provider":
            index += 1
            if index >= len(argv):
                sys.stderr.write("--provider needs a name\n")
                return 2
            if argv[index] not in install.PROVIDERS:
                sys.stderr.write(f"unknown provider: {argv[index]}\n")
                return 2
            providers.append(argv[index])
        elif arg == "--include-unverified":
            include_unverified = True
        elif arg == "--dry-run":
            dry_run = True
        elif arg == "--json":
            as_json = True
        elif arg in home_flags:
            index += 1
            if index >= len(argv):
                sys.stderr.write(f"{arg} needs a directory\n")
                return 2
            homes[home_flags[arg]] = argv[index]
        elif arg.startswith("--") and "=" in arg:
            flag, value = arg.split("=", 1)
            if flag not in home_flags:
                sys.stderr.write(f"unknown option: {flag}\n{USAGE}")
                return 2
            homes[home_flags[flag]] = value
        else:
            sys.stderr.write(f"unknown option: {arg}\n{USAGE}")
            return 2
        index += 1

    user_home = homes.pop("user", None)
    resolved = install.Homes.defaults(user_home, **homes)
    report = install.configure_mcp(providers or list(install.PROVIDERS), resolved,
                                   include_unverified=include_unverified,
                                   dry_run=dry_run)

    log = sys.stderr if as_json else sys.stdout
    for entry in report:
        log.write(f"   {entry['message']}\n")
    failed = [entry for entry in report if entry["status"] == "failed"]
    if as_json:
        sys.stdout.write(json.dumps({"targets": report,
                                     "failed": len(failed)}, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
