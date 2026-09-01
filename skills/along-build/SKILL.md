---
name: along-build
description: Build the target repository using .along/scripts/build.py or auto-detected build tool (npm, cargo, dotnet, python).
---

# Along Build (`/along-build`) [v2.2.13]

Execute project build lifecycle hook via `.along/scripts/build.py` or auto-detected build runner.

---

## Usage

```bash
python .along/scripts/build.py
```
*(Or `/along-build`, or stack fallback: `npm run build`, `cargo build`, `dotnet build -v q`, `python -m build`)*

