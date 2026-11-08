import os
import sys

# Pytest runner bridge:
# If pytest is already imported (e.g. during pytest collection), satisfy ALONG_TEST_RUNNER.
# Trade-off note: Any process that has already imported pytest passes this guard; raw
# `python -m unittest` or unconfigured direct execution remains strictly blocked.
if not os.environ.get("ALONG_TEST_RUNNER"):
    if "pytest" in sys.modules or "_pytest" in sys.modules:
        os.environ["ALONG_TEST_RUNNER"] = "pytest"
    else:
        raise SystemExit(
            "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
            "To run tests with automatically resolved dependencies, use the official project entry point:\n"
            "    python .along/scripts/test.py"
        )
