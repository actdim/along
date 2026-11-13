---
name: along-test
description: Run repository automated tests with quiet flags using .along/scripts/test.py or auto-detected test runner (pytest -q, npm test, cargo test -q, dotnet test -v q).
---

# Along Test (`/along-test`)
Execute project automated tests with quiet flags via `.along/scripts/test.py` or auto-detected test runner.

---

## Usage

```bash
along test
along test --full
along test --affected
along test --scope <name>
python .along/scripts/test.py
```
*(Or `/along-test`, or stack fallback: `npm test`, `pytest -q`, `python -m unittest discover tests -q`, `cargo test -q`, `dotnet test -v q`)*
*(Or fallback: `python ~/.along/bin/along_exec.py test` or `/along-test`; executes `.along/scripts/test.py` or auto-detects and synthesizes it for pytest, unittest, npm, cargo, dotnet)*

## Effective Policy and Scoping Flags

By default, `along test` runs under the **effective verify policy** of the bound issue (approved plan snapshot > repository `.along/config.json`).
Override flags:
- `--full`: Force running the full test suite.
- `--affected`: Run tests for files modified in the active session or working tree.
- `--scope <name>`: Run a named test scope declared in `.along/config.json` under `verify.scopes`.

## Runner Contract

The test runner passes execution context to `.along/scripts/test.py` via environment variables:
- `ALONG_TEST_MODE`: `full | affected | scoped`
- `ALONG_TEST_SCOPE`: named scope (e.g. `api`, `web`, `unit`)
- `ALONG_ATTRIBUTED_FILES`: path to file listing repo-relative paths of modified files (one per line)

Example mapping inside `.along/scripts/test.py`:
```python
mode = os.environ.get("ALONG_TEST_MODE", "full")
scope = os.environ.get("ALONG_TEST_SCOPE", "")
files_path = os.environ.get("ALONG_ATTRIBUTED_FILES", "")

if mode == "scoped" and scope == "api":
    cmd = ["pytest", "-q", "tests/api"]
elif mode == "affected" and files_path:
    with open(files_path, "r", encoding="utf-8") as f:
        targets = [line.strip() for line in f if line.strip()]
    cmd = ["pytest", "-q"] + targets
else:
    cmd = ["pytest", "-q"]
```

