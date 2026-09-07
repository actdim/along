---
name: along-dev
description: Run repository development or local debugging server using .along/scripts/dev.py or auto-detected dev runner (npm run dev, cargo run, dotnet run, python main.py).
---

# Along Dev (`/along-dev`) [v2.2.22]

Launch project development / debugging server via `.along/scripts/dev.py` or auto-detected runner.

---

## Usage

```bash
python .along/scripts/dev.py
along dev
```
*(Or `/along-dev`, or stack fallback: `npm run dev`, `cargo run`, `dotnet run`, `python main.py`)*
*(Or fallback: `python ~/.along/bin/along_exec.py dev` or `/along-dev`; executes `.along/scripts/dev.py` or auto-detects and synthesizes it for npm, cargo, dotnet, python)*

