#!/usr/bin/env python3
"""along_webdev_mcp.py - Dedicated stdio Model Context Protocol (MCP) server entrypoint for Along WebDev (REQ-13)."""

from __future__ import annotations

import os
import sys

# Ensure alongkit runtime and dependencies
from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit.webdev import mcp_server


def main() -> int:
    return mcp_server.run_stdio_server()


if __name__ == "__main__":
    sys.exit(main())
