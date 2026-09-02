# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "fastapi>=0.110.0",
#     "uvicorn>=0.28.0",
#     "pydantic>=2.0.0",
#     "ruamel.yaml>=0.18",
#     "rich>=13.0.0",
# ]
# ///

"""
Along Dashboard & Knowledge Base Engine Runner.

Runs the dynamic Along Dashboard, OpenAPI service, and Knowledge Base search engine:
- Terminal CLI Mode: Rich executive summary tables and active issues.
- Web Mode: FastAPI + Uvicorn service with OpenAPI Swagger docs and live UI.
- Static Export Mode: Standalone single-file snapshot only when explicitly requested via --export.
"""

import sys
import shutil
import subprocess
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

if "--no-uv-reentry" in sys.argv:
    sys.argv.remove("--no-uv-reentry")

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from alongkit import bootstrap
bootstrap.ensure_deps()


from dashboard.app import main

if __name__ == "__main__":
    main()
