# Living Plan: docs--count-claim-and-plan-approval-drift

Title: Documentation counts, phase and rubric claims, snippet unit and plan approval drift

## Execution Mode

Direct

## Steps

- [x] Step 1: Fix all six documentation drift items, `.along/VISION.md` stale counts/extras, `README.md` and `skills/along-kb-search/SKILL.md` snippet unit wording, and `docs/topic--llm-wiki-architecture.md` `all 18` reference
  - `docs/topic--runtime-hooks-and-gates.md`: update `33` -> `35` canonical/catalogue gates, `11` -> `12` git/CI-only checks (including `provenance drift`), and clarify separation from runtime gates (`require_plan_approval`, `destructive_command`, `worktree_env_readiness`, `workspace_containment`).
  - `docs/topic--declarative-gates-and-traceability.md`: update `33 gates` -> `35 gates` and include `session_record_append_only` and `provenance_drift` in the commit-time check summary.
  - `docs/topic--architecture.md`: update `eighteen skills` -> `22 skills`; make phase diagram contiguous (`Phase 0` through `Phase 6: Wrap-up (/along-wrap)`) matching `7-Phase State Machine (Phases 0-6)`; update `6-Point Verification Rubric` -> `7-Point Verification Rubric`.
  - `docs/topic--system-comparisons.md` (`write_policy: manual`), `docs/topic--skills-reference.md`, `README.md`, `skills/along-kb-search/SKILL.md`: replace `< 150 tokens` snippet-window phrasing with `<= 150 words` matching `scripts/along_kb_search.py` (`max_words: int = 150`); add `WEBDEV["along-webdev"]` to `topic--skills-reference.md` Phase 3 diagram; update `docs/topic--llm-wiki-architecture.md` `all 18 automation skills` -> `all 22 automation skills`.
  - `docs/topic--setup-and-workflow.md`: update `along start` atomic initialization to document `phase: planning`, `plan_approved: false` by default, explicit user plan approval (`ExitPlanMode` or `along plan approve`), pre-approved plans on the current machine, and `--approved` for scripted runs (binding alone does not unlock source edits).
  - `.along/VISION.md`: update `32 protocol invariants` -> `35 protocol invariants`, `21-Skill Automation Suite` -> `22-Skill Automation Suite` with `along-webdev`, and add `actdim-along[webdev]` to Modular Extras and Installation Matrix.

- [x] Step 2: Reconcile all 5 `[DRIFT]` provenance entries, run `along kb-sync`, and remove untracked stale `.opencode/plugins/along-gates.js`
  - Update `docs/topic--llm-wiki-architecture.md` to document `session.settle_projection_denials(repo_root)` in `scripts/along_kb_sync.py`.
  - Update `docs/topic--migrations.md` to document Step 17 (`step_relocate_protocol_reference`) from `scripts/migrate_protocol.py`.
  - Accept drift across all 5 tracked topic-source pairs (`docs/topic--llm-wiki-architecture.md`, `docs/topic--architecture.md`, `docs/topic--domain-model.md`, `docs/topic--migrations.md`, `docs/topic--setup-and-workflow.md`) with `--reviewed` / `--no-doc-impact` as appropriate, then run `along kb-sync` to refresh `docs/INDEX.md`, `llms.txt`, and `llms-full.txt`.
  - Verify `.opencode/` is untracked via `git ls-files .opencode/` and remove stale `.opencode/plugins/along-gates.js` and empty `.opencode/`.

- [x] Step 3: Add automated count, unit, diagram, rubric, and `along start` drift checks in `tests/test_docs.py` and `tests/test_system_comparisons.py`
  - Verify gate count claims in living docs match `default_gates.yaml` (35 total, 12 `[git, ci]`).
  - Verify skill count claims in living docs match `skills/along-*` (22).
  - Verify snippet-window wording uses words (not `150 tokens`) matching `scripts/along_kb_search.py`.
  - Verify phase diagram contiguity, rubric heading vs numbered items, and `along start` explicit approval description.

- [x] Step 4: Verify full test suite and all quality gates, then wrap, commit, and push
  - Run targeted tests and full `.along\scripts\test.py -q`.
  - Run `along sanitize`, `along hook verify --strict`, `along kb-sync --check --strict`, `along context-budget --check`, and `along gates check --ci --range d4302b8..HEAD`.
  - Tick Acceptance Criteria in `.along/ISSUES/docs--count-claim-and-plan-approval-drift.md`, wrap, commit with `along commit`, and push.
