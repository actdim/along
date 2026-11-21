---
name: along-webdev
description: Self-contained web development and browser execution substrate for Playwright verification, exploratory sessions, and visual proof.
---

# Along WebDev (`/along-webdev`)

Provider-agnostic browser execution substrate for web development verification, exploratory interactive sessions, and visual regression proof.

---

## Capabilities

- **Application Services Lifecycle**: `along webdev serve up|status|down|logs` manages declared dev services with readiness probes and log harvesting.
- **Exploratory Sessions**: `along webdev session start|step|batch|save|stop` runs a persistent browser behind a local daemon and records transcripts into reusable scenarios.
- **Declarative Scenarios**: `along webdev run <scenario.yaml>` executes checks across viewports and themes, producing deterministic evidence under `.along/artifacts/webdev/`.
- **Checklist Compilation**: `along webdev checklist compile <file|issue>` compiles natural language markdown checklists into scenario skeletons.
- **Visual Proof Screenshots**: `along webdev shot --url <url> --out <path>` captures fast route screenshots.
- **Declared Limits & Emulation**: `along webdev limits` inspects unverifiable surfaces and recommended emulation substitutes.

---

## Usage

```bash
# Bring up application services
along webdev serve up

# Start interactive exploratory browser session
along webdev session start --issue feat--chat-ui

# Execute exploratory step
along webdev session step --step '{"goto": "/chat"}'

# Save recorded transcript to scenario
along webdev session save --as scenario.yaml

# Run declarative verification scenario
along webdev run scenario.yaml --issue feat--chat-ui --file-failures

# Quick screenshot
along webdev shot --url http://localhost:5173 --out proof.png
```

---

## Safety Guidelines

- **Zero Real Passwords**: Never type or submit real passwords or production tokens. Use synthetic credentials or dev login bypass routes.
- **Self-Ignoring Artifacts**: Screenshots and harvested network logs are stored in `.along/artifacts/webdev/` which ignores itself from git tracking.
