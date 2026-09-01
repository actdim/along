---
name: along-decision-sync
description: Record architectural/design decisions into the nearest .along/DECISIONS.md as append-only ADR entries with decentralized slug headers, and mark superseded ones. Use when a non-trivial technical choice was made, or invokes /along-decision-sync.
---

# Along Decision Sync (`/along-decision-sync`) [v2.2.13]

Maintains append-only Architectural Decision Records (ADRs) in the nearest `.along/DECISIONS.md` using decentralized slug headers to prevent git merge conflicts across parallel branches.

## Scope & Placement
- Always record ADRs in the **NEAREST** `.along/DECISIONS.md` for the subproject, module, or submodule being architected.
- Root `.along/DECISIONS.md` is reserved for system-wide or cross-package architectural decisions.

## ADR Format (Protocol v2.2.0)
```markdown
## ADR-YYYY-MM-DD--<slug> - <Title>
- Date: YYYY-MM-DD
- Status: accepted (or: superseded by ADR-YYYY-MM-DD--<slug>)
- Context: <why this came up>
- Decision: <what was decided>
- Consequences: <trade-offs / follow-ups>
```

## CLI Helper
```bash
python scripts/along_exec.py decision create <slug> --title "Title" --context "Why" --decision "What" --consequences "Tradeoffs"
```

