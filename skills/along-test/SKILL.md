---
name: along-test
description: Run repository automated tests with quiet flags using .along/scripts/test.py or auto-detected test runner (pytest -q, npm test, cargo test -q, dotnet test -v q).
---

# Along Test (`/along-test`) [v2.2.25]

Execute project automated tests with quiet flags via `.along/scripts/test.py` or auto-detected test runner.

---

## Usage

```bash
python .along/scripts/test.py
along test
```
*(Or `/along-test`, or stack fallback: `npm test`, `pytest -q`, `python -m unittest discover tests -q`, `cargo test -q`, `dotnet test -v q`)*
*(Or fallback: `python ~/.along/bin/along_exec.py test` or `/along-test`; executes `.along/scripts/test.py` or auto-detects and synthesizes it for pytest, unittest, npm, cargo, dotnet)*

