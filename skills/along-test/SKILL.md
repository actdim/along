---
name: along-test
description: Run repository automated tests with quiet flags using .along/scripts/test.py or auto-detected test runner (pytest -q, npm test, cargo test -q, dotnet test -v q).
---

# Along Test (`/along-test`) [v2.2.18]

Execute project automated tests with quiet flags via `.along/scripts/test.py` or auto-detected test runner.

---

## Usage

```bash
python .along/scripts/test.py
```
*(Or `/along-test`, or stack fallback: `npm test`, `pytest -q`, `python -m unittest discover tests -q`, `cargo test -q`, `dotnet test -v q`)*

