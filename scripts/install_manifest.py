#!/usr/bin/env python3
"""
install_manifest.py - record what an install wrote, prune what it no longer ships,
and uninstall exactly that and nothing else.

Called by `install.ps1` and `install.sh` after they finish copying, and directly by a
user who wants to see or undo an install. The installers copy; this engine keeps the
books. `[bug--installer-parity-and-destructive-rules-overwrite]` REQ-2, REQ-6, REQ-7.

Why a manifest at all: the installer used to keep its destinations clean by deleting
them first (`Remove-Item -Recurse -Force ~/.claude/rules`), which destroyed whatever the
user had written there - on every run, including the runs the release engine started
without being asked. Knowing which files Along itself wrote makes the delete unnecessary
and makes a real uninstall possible.

Stream contract (rules/platforms/cli.md): the report is the data. Without `--json` it is
the readable report on stdout; with `--json` the JSON takes stdout and the readable form
moves to stderr. Failures and usage errors always go to stderr. Exit 0 on success, 1 when
a planned file never landed or a removal failed, 2 on a usage error.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import install, repo, version

USAGE = """Usage: python install_manifest.py <command> [options]

Commands:
  sync        record the current install and remove files Along no longer ships
  show        print the recorded manifest
  uninstall   remove every file the manifest records (and nothing else)

Options:
  --source DIR           the Along checkout that was installed (sync; default: cwd repo)
  --target NAME          claude | codex | opencode | antigravity (repeatable, sync)
  --version V            version to record (default: the protocol version)
  --no-prune             record only; leave superseded files on disk
  --dry-run              report what would change, change nothing
  --json                 machine-readable report on stdout
  -h, --help             this message

Homes (each defaults to the standard location under the user home):
  --user-home DIR        --along-home DIR         --claude-home DIR
  --codex-home DIR       --opencode-home DIR      --antigravity-home DIR
"""


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        sys.stderr.write(USAGE)
        return 0 if argv else 2
    command = argv[0]
    if command not in ("sync", "show", "uninstall"):
        sys.stderr.write(f"unknown command: {command}\n{USAGE}")
        return 2

    source = None
    targets = []
    version_string = None
    prune = True
    dry_run = False
    as_json = False
    homes = {}
    home_flags = {
        "--user-home": "user", "--along-home": "along", "--claude-home": "claude",
        "--codex-home": "codex", "--opencode-home": "opencode",
        "--antigravity-home": "antigravity",
    }

    index = 1
    while index < len(argv):
        arg = argv[index]
        value = None
        if arg.startswith("--") and "=" in arg:
            arg, value = arg.split("=", 1)

        def take(flag):
            """The value of `flag`, whether it was joined by `=` or given separately."""
            nonlocal index
            if value is not None:
                return value
            index += 1
            if index >= len(argv):
                sys.stderr.write(f"{flag} needs a value\n")
                return None
            return argv[index]

        if arg in ("-h", "--help"):
            sys.stderr.write(USAGE)
            return 0
        elif arg == "--source":
            source = take(arg)
            if source is None:
                return 2
        elif arg == "--target":
            name = take(arg)
            if name is None:
                return 2
            if name == "all":
                targets = list(install.PROVIDERS)
            elif name == "both":
                targets = ["claude", "codex"]
            elif name in install.PROVIDERS:
                targets.append(name)
            else:
                sys.stderr.write(f"unknown target: {name}\n")
                return 2
        elif arg == "--version":
            version_string = take(arg)
            if version_string is None:
                return 2
        elif arg == "--no-prune":
            prune = False
        elif arg == "--dry-run":
            dry_run = True
        elif arg == "--json":
            as_json = True
        elif arg in home_flags:
            resolved = take(arg)
            if resolved is None:
                return 2
            homes[home_flags[arg]] = resolved
        else:
            sys.stderr.write(f"unknown option: {arg}\n{USAGE}")
            return 2
        index += 1

    user_home = homes.pop("user", None)
    resolved_homes = install.Homes.defaults(user_home, **homes)
    log = sys.stderr if as_json else sys.stdout

    if command == "show":
        manifest = install.read_manifest(resolved_homes.along)
        if as_json:
            sys.stdout.write(json.dumps(manifest, indent=2) + "\n")
        if not manifest:
            log.write(f"   no install manifest at "
                      f"{install.manifest_path(resolved_homes.along)}\n")
            return 0
        log.write(f"   Along {manifest.get('version', '?')} installed "
                  f"{manifest.get('updated', '?')} for "
                  f"{', '.join(manifest.get('providers') or [])}\n")
        log.write(f"   {len(manifest.get('files') or {})} files, recorded in "
                  f"{install.manifest_path(resolved_homes.along)}\n")
        return 0

    if command == "uninstall":
        report = install.uninstall(resolved_homes.along, dry_run=dry_run)
        verb = "would remove" if dry_run else "removed"
        log.write(f"   {verb} {len(report['removed'])} of {report['recorded']} "
                  f"recorded files\n")
        for key in report["failed"]:
            sys.stderr.write(f"   could not remove {key}\n")
        if not report["recorded"]:
            log.write(f"   nothing recorded in {report['manifest']}\n")
        if as_json:
            sys.stdout.write(json.dumps(report, indent=2) + "\n")
        return 1 if report["failed"] else 0

    source_root = os.path.abspath(source) if source else repo.find_repo_root(os.getcwd())
    if not os.path.isdir(os.path.join(source_root, "skills")):
        sys.stderr.write(f"   not an Along checkout: {source_root}\n")
        return 2

    report = install.sync_manifest(
        source_root, resolved_homes, targets or list(install.PROVIDERS),
        version_string or version.CURRENT_VERSION, prune=prune, dry_run=dry_run)

    log.write(f"-> Install manifest: {report['installed']} files "
              f"({report['added']} new, {report['changed']} updated, "
              f"{report['unchanged']} unchanged) -> {report['manifest']}\n")
    for key in report["removed"]:
        log.write(f"   removed superseded {key}\n")
    for key in report["missing"]:
        sys.stderr.write(f"   MISSING (the install did not produce it): {key}\n")
    if as_json:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 1 if report["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
