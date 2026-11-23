# Plan: docs--reconcile-protocol-counts-and-extras

Execution Mode: Direct (4 targeted files, documentation and metadata sync)

## Context
During repository quality analysis, several factual drift issues and out-of-sync counts were identified:
- `README.md`: states "32 protocol invariants" (actually 35 in `default_gates.yaml`), omits `actdim-along[webdev]`, and incorrectly defines `[all]` as alias for `[dash]` only.
- `docs/topic--skills-reference.md`: states "21 singular automation skills" instead of 22 (reflecting `along-webdev`).
- `scripts/alongkit/cli.py`: retains an obsolete comment referencing "nineteen SKILL.md files".
- `.along/VISION.md`: specifies frontmatter `protocol_version: "4.4.11"` while repository protocol version is `4.9.1`.

## Planned Modifications
1. `README.md`:
   - Update runtime gate description from "32 protocol invariants" to "35 protocol invariants".
   - Under Python Package Installation (Core vs. Extras), add `pip install actdim-along[webdev]`.
   - Update Modular Extras Architecture section to list `actdim-along[webdev]` (WebDev browser verification) and clarify that `actdim-along[all]` bundles both `[dash]` and `[webdev]`.
2. `docs/topic--skills-reference.md`:
   - Update introductory count from 21 to 22 singular automation skills.
3. `scripts/alongkit/cli.py`:
   - Remove obsolete comment referring to "nineteen SKILL.md files".
4. `.along/VISION.md`:
   - Update frontmatter `protocol_version` from `"4.4.11"` to `"4.9.1"`.
5. Knowledge Base & Gates Verification:
   - Run `python scripts/along_kb_sync.py --strict` to verify link integrity and synchronize topic provenance hashes.
   - Run `python scripts/alongkit/cli.py hook verify` to verify 35 gate invariants.
   - Run `python .along/scripts/test.py` to ensure all 1997 tests remain green.

## Verification Policy
- Automated checks: `along hook verify`, `along kb-sync --strict`, `python .along/scripts/test.py`.
