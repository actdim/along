# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastapi>=0.110.0",
#     "uvicorn>=0.28.0",
#     "pydantic>=2.0.0",
#     "pyyaml>=6.0.0",
#     "rich>=13.0.0",
# ]
# ///

"""
Along Development Runner (.along/scripts/dev.py).
Launches the full dev environment with Vite HMR frontend (port 5173) and live FastAPI backend (port 8765).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Auto-bootstrap with `uv run` if dependencies are not available in current interpreter
if "--no-uv-reentry" not in sys.argv:
    try:
        import fastapi
        import uvicorn
        import pydantic
    except ImportError:
        uv_bin = shutil.which("uv")
        if uv_bin:
            cmd = [uv_bin, "run", str(Path(__file__).resolve())] + sys.argv[1:] + ["--no-uv-reentry"]
            try:
                sys.exit(subprocess.call(cmd))
            except KeyboardInterrupt:
                sys.exit(0)
        else:
            print(
                "[Error] Missing dependencies (fastapi, uvicorn, pydantic).\n"
                "Run with uv (recommended):\n"
                "    uv run .along/scripts/dev.py\n"
                "Or install the required packages:\n"
                "    python -m pip install fastapi uvicorn pydantic pyyaml rich",
                file=sys.stderr,
            )
            sys.exit(2)

if "--no-uv-reentry" in sys.argv:
    sys.argv.remove("--no-uv-reentry")

# Add repo root and scripts/ to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

scripts_dir = repo_root / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from alongkit import bootstrap
bootstrap.ensure_deps()

from dashboard.app import main

if __name__ == "__main__":
    # Default to dev mode if no explicit mode arguments passed
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] not in ("-w", "--web", "-c", "--cli", "--export")):
        sys.argv.append("--dev")
    main()

