#!/usr/bin/env python3
"""
alongkit.version - The single protocol and toolchain version constant.

The version string used to be declared independently in `migrate_protocol.py`,
`along_kb_sync.py`, `along_update.py`, and `along_feedback.py`. Three of them were
kept in step by regex rewrites in `along_version_bump.py`; the fourth was missed and
had drifted to 2.1.6, so every bug report submitted through `along-feedback` carried
a version that had not existed for three releases.

`along_version_bump.py` rewrites the constant below. Nothing else declares it.
"""


from __future__ import annotations
if __name__ == "__main__":
    raise SystemExit(
        f"{__name__} is a library module, not a command.\n"
        "Run: along kb-sync   (or: python scripts/along_exec.py kb-sync)"
    )


CURRENT_PROTOCOL_VERSION = "2.2.14"

#: Alias for readers that care about the toolchain rather than the protocol. They move
#: together: the engines and the protocol ship as one artifact.
CURRENT_VERSION = CURRENT_PROTOCOL_VERSION


def protocol_version() -> str:
    """The protocol version this toolchain implements."""
    return CURRENT_PROTOCOL_VERSION
