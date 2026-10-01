#!/usr/bin/env python3
"""
scripts/along_merge_driver.py - git merge driver entry point for Along files.

Registered in `.git/config` by `along git setup`; git invokes it as:

  python scripts/along_merge_driver.py projection  %O %A %B %P
  python scripts/along_merge_driver.py frontmatter %O %A %B %P

%O ancestor, %A ours (the result is written here), %B theirs, %P pathname.
Exit 0 means a clean merge; non-zero leaves conflict markers in %A for the user.
Logic lives in `alongkit.merge`.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from alongkit import bootstrap

USAGE = "usage: along_merge_driver.py {projection|frontmatter} %O %A %B [%P]"


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 4 or args[0] in ("-h", "--help"):
        sys.stderr.write(USAGE + "\n")
        return 0 if args[:1] in (["-h"], ["--help"]) else 2
    mode, base, ours, theirs = args[:4]
    pathname = args[4] if len(args) > 4 else ours

    bootstrap.ensure_deps()
    from alongkit import merge
    return merge.run_driver(mode, base, ours, theirs, pathname)


if __name__ == "__main__":
    sys.exit(main())
