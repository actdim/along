# Plan: Gate traceability does not scan .along/PROTOCOL.md and ignores undocumented gates

Execution Mode: Direct
Issue: `bug--traceability-blind-to-protocol-md-and-unbadged-gates`
Verify Policy: `required`

## Root Cause & Findings

1. **Hole 1 (`.along/*.md` omitted from scan set)**:
   `scan_prose_anchors` (`scripts/alongkit/hooks/traceability.py`) scans `AGENTS.md`, `CLAUDE.md`, `README.md`, and recursively walks `skills/`, `docs/`, and `.along/rules/`. It never scans top-level `.along/*.md` files, leaving the 22 `[gate: ...]` badges in `.along/PROTOCOL.md` invisible to `audit_traceability`.
2. **Hole 2 (undocumented gates do not fail default check)**:
   `TraceabilityReport.is_clean` checks only `not self.dangling_references and not self.schema_errors`, ignoring `self.undocumented_gates`. `scripts/along_hook.py verify` exits non-zero on undocumented gates only when `--strict` is explicitly passed, and `.github/workflows/tests.yml` does not run `along hook verify --strict` in its `gates` job.
3. **Unbadged catalogue gates and mismatched `typography` error badge**:
   - In `scripts/alongkit/hooks/default_gates.yaml`, `typography` emits `[gate: clean-ascii-typography]` instead of `[gate: typography]`.
   - Running `along hook verify` on the current tree reports **10** undocumented `[git, ci]` gates: the 5 named in the ticket (`typography`, `provenance_drift`, `session_record_append_only`, `windows_safe_filenames`, `no_tracked_secrets`) plus 5 other commit-time gates whose badges were stripped from `skills/along-init/protocol.md` in `debt--gate-simplification` (`anti_stub_injection`, `code_fence_language`, `commit_no_ai_coauthor`, `portable_links`, `stable_entry_point`).
   - `skills/along-init/protocol.md` has a hard 6144 B ceiling (currently 6097 B), whereas `skills/along-init/protocol-reference.md` (which renders to `.along/PROTOCOL.md` via `along update`) carries the detailed rule descriptions and already holds `[gate: ...]` badges.

## Changes

1. **Scanner & Verdict (`scripts/alongkit/hooks/traceability.py`)**:
   - Update `scan_prose_anchors` to also collect top-level `*.md` files inside `repo.state_dir(repo_root)` (covering `.along/PROTOCOL.md`, `.along/VISION.md`, `.along/CONSTRAINTS.md`, `.along/GLOSSARY.md`, etc. without descending into `ISSUES/`, `SESSIONS/`, or `DECISIONS/`).
   - Update `TraceabilityReport.is_clean` to also require `not self.undocumented_gates` so missing badges fail `audit_traceability` and `format_traceability_report` (`Verdict: FAILED`) by default.
   - Update module docstring to accurately list scanned locations.
2. **CLI Default & CI Enforcement (`scripts/along_hook.py`, `.github/workflows/tests.yml`)**:
   - In `scripts/along_hook.py`, flip `--strict` on `along hook verify` to `default=True` (keeping `--strict` accepted for backwards compatibility). Since `report.is_clean` checks `undocumented_gates`, both `along hook verify` and `along hook verify --strict` exit `1` on any missing badge.
   - In `.github/workflows/tests.yml`, add a step in the `gates` job running `python scripts/along_exec.py hook verify --strict`.
3. **Gate Error Badge & Prose Badges (`scripts/alongkit/hooks/default_gates.yaml`, `skills/along-init/protocol-reference.md`, `.along/PROTOCOL.md`)**:
   - Fix `default_gates.yaml` for `typography` (`[gate: clean-ascii-typography]` -> `[gate: typography]`).
   - Add the 10 missing `[gate: ...]` badges to `skills/along-init/protocol-reference.md` on their corresponding rules (preserving all `test_scaffold_profiles.py` `PRE_SLIMMING_RULES` strings and profile markers), then regenerate `.along/PROTOCOL.md` via `along update --local-only --no-hooks` (verifying `test_03b2_protocol_reference_matches_its_source` passes).
4. **Documentation Parity (`docs/topic--declarative-gates-and-traceability.md`, `docs/topic--runtime-hooks-and-gates.md`, `docs/topic--cli-reference.md`)**:
   - Update `docs/topic--declarative-gates-and-traceability.md` to document `.along/*.md` in `scan_prose_anchors`, default failure on undocumented gates, and `typography` id.
   - Update `docs/topic--runtime-hooks-and-gates.md` (Section 4a prose note) to clarify that commit-time checks lack tags in the slim `AGENTS.md` core while carrying their `[gate: ...]` badges in `.along/PROTOCOL.md`.
   - Update `docs/topic--cli-reference.md` to reflect `along hook verify` failing on undocumented gates by default (`--strict` retained).
   - Run `along kb-sync` / settle provenance hashes as needed.
5. **Tests (`tests/test_gates_traceability.py`)**:
   - Assert distinct badges found in `.along/PROTOCOL.md` > 0 (REQ-4).
   - Assert every `[gate: ...]` badge in `default_gates.yaml` error messages resolves to its own gate `id` (REQ-3).
   - Hermetic tests proving:
     - `.along/*.md` (`PROTOCOL.md`, `VISION.md`, `CONSTRAINTS.md`, `GLOSSARY.md`) is scanned by `scan_prose_anchors`, and a dangling badge in `.along/*.md` or dropping `.along/*.md` fails verification (REQ-1, AC-5).
     - `TraceabilityReport.is_clean` is `False` and `along hook verify` exits non-zero without `--strict` when any gate lacks a prose badge (REQ-2).

## Verification

1. After applying scanner + CLI fix (before adding prose badges), run `along hook verify` to confirm `.along/PROTOCOL.md` badges are counted and missing-badge gates cause exit code `1`.
2. After fixing `default_gates.yaml` and regenerating `.along/PROTOCOL.md`, run `along hook verify` (without `--strict`) and `along hook verify --strict` and confirm exit `0` with `35 / 35` anchored.
3. Run `C:\Users\Admin\.along\venv\Scripts\python.exe .along\scripts\test.py tests/test_gates_traceability.py -q`, `tests/test_scaffold_profiles.py`, `tests/test_context_budget.py`, `tests/test_diagnostics_profiles.py`, `tests/test_git_gate_enforcement.py`, `tests/test_skills_and_scripts.py`, and then the full suite with `$env:ALONGKIT_PROJECT_ENV="1"`.
4. Run `along sanitize`, `along gates check --ci --no-links` (or pre-commit check), and `along kb-sync --check --strict`.
