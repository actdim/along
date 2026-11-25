#!/usr/bin/env python3
"""
alongkit.version - Canonical protocol and toolchain version constants.

`CURRENT_VERSION` tracks the toolchain package SemVer (PyPI package, CLI, skills
distribution, and dashboard). `CURRENT_PROTOCOL_VERSION` tracks the repository
protocol specification SemVer (`ALONG-PROTOCOL vX.Y.Z`). They are decoupled so
toolchain releases do not churn protocol headers across the repository.

`along_version_bump.py` rewrites the constants below. Nothing else declares them.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along version-bump   (or: python scripts/along_version_bump.py)"
    )

from . import semver


#: Protocol specification SemVer (`ALONG-PROTOCOL vX.Y.Z`).
CURRENT_PROTOCOL_VERSION = "4.9.1"

#: Minimum protocol specification version supported by this toolchain.
MIN_SUPPORTED_PROTOCOL_VERSION = "4.8.0"

#: Toolchain package SemVer (`actdim-along` distribution, CLI, and engines).
CURRENT_VERSION = "4.9.3"
__version__ = CURRENT_VERSION


def protocol_version() -> str:
    """The protocol version this toolchain implements."""
    return CURRENT_PROTOCOL_VERSION


def is_protocol_supported(ver_str: str) -> bool:
    """Return True when `ver_str` is within [MIN_SUPPORTED_PROTOCOL_VERSION, CURRENT_PROTOCOL_VERSION]."""
    if not ver_str or not isinstance(ver_str, str):
        return False
    parsed = semver.parse(ver_str)
    if parsed == (0, 0, 0):
        return False
    return semver.parse(MIN_SUPPORTED_PROTOCOL_VERSION) <= parsed <= semver.parse(CURRENT_PROTOCOL_VERSION)


#: Milestone version threshold tuples for migrations and compatibility checks
V2_0_0: tuple = (2, 0, 0)
V2_2_9: tuple = (2, 2, 9)
V2_2_26: tuple = (2, 2, 26)
V3_0_0: tuple = (3, 0, 0)
V3_1_0: tuple = (3, 1, 0)
