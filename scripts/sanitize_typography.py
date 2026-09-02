#!/usr/bin/env python3
"""
sanitize_typography.py - Report, and on request repair, non-ASCII typographic and
invisible characters across repository text.

The policy, the file walking, the strict reads, and the report all live in
`alongkit.sanitizer`; this file is the command line over them. It defaults to
`--check`: the tool reports and exits non-zero, and rewrites nothing unless asked.
That default is deliberate and is the point of
`[bug--typography-sanitizer-destroys-non-utf8-files]` - the previous version
rewrote the whole repository unattended before every commit and every release,
read candidate files with `errors="ignore"`, and forced LF onto files that
`.gitattributes` declares CRLF.

Stream contract (rules/platforms/cli.md): the JSON summary is the data and goes to
stdout; progress and findings are logs and go to stderr. Exit 0 clean, 1 findings in
check mode, 2 usage error.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()


from alongkit import repo, sanitizer

USAGE = """Usage: python sanitize_typography.py [ROOT] [options]

Modes (default --check):
  --check              report findings and exit 1; never writes
  --dry-run            report findings and exit 0; never writes
  --write, --fix       apply the ASCII replacements

Scope:
  --include-data       also scan .json, .yaml, .yml, .toml (off by default)
  --include EXT        scan an additional suffix as well (repeatable)
  --exclude GLOB       skip paths matching GLOB (repeatable)
  --no-ignore-file     ignore .alongsanitizeignore

Output:
  --json               machine-readable summary on stdout
  -q, --quiet          summary only, no per-file detail
  -h, --help           this message

Localized resource directories (locales/, i18n/, translations/, ...) are never
scanned. Files that are not valid UTF-8 are skipped and reported, never rewritten.
"""


def main():
    argv = sys.argv[1:]
    mode = sanitizer.Mode.CHECK
    include_data = False
    extra_suffixes = []
    excludes = []
    use_ignore_file = True
    as_json = False
    verbose = True
    root = None

    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("-h", "--help"):
            print(USAGE)
            return 0
        elif arg == "--check":
            mode = sanitizer.Mode.CHECK
        elif arg == "--dry-run":
            mode = sanitizer.Mode.DRY_RUN
        elif arg in ("--write", "--fix"):
            mode = sanitizer.Mode.WRITE
        elif arg == "--include-data":
            include_data = True
        elif arg == "--no-ignore-file":
            use_ignore_file = False
        elif arg == "--json":
            as_json = True
        elif arg in ("-q", "--quiet"):
            verbose = False
        elif arg in ("--include", "--exclude"):
            index += 1
            if index >= len(argv):
                print(f"[Error] {arg} requires a value.\n\n{USAGE}", file=sys.stderr)
                return 2
            (extra_suffixes if arg == "--include" else excludes).append(argv[index])
        elif arg.startswith("--include=") or arg.startswith("--exclude="):
            flag, _, value = arg.partition("=")
            (extra_suffixes if flag == "--include" else excludes).append(value)
        elif arg.startswith("-"):
            print(f"[Error] unknown option: {arg}\n\n{USAGE}", file=sys.stderr)
            return 2
        elif root is None:
            root = arg
        else:
            print(f"[Error] unexpected argument: {arg}\n\n{USAGE}", file=sys.stderr)
            return 2
        index += 1

    target = os.path.abspath(root) if root else repo.find_repo_root()
    if not os.path.isdir(target):
        print(f"[Error] not a directory: {target}", file=sys.stderr)
        return 2

    report = sanitizer.run(target, mode=mode, include_data=include_data,
                           extra_suffixes=extra_suffixes, excludes=excludes,
                           use_ignore_file=use_ignore_file)

    if as_json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
        if verbose and not report.clean:
            print(sanitizer.format_report(report, verbose=False), file=sys.stderr)
    else:
        print(sanitizer.format_report(report, verbose=verbose), file=sys.stderr)
        if mode == sanitizer.Mode.CHECK and not report.clean:
            print("Run with --write to apply these replacements.", file=sys.stderr)

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
