# Living Plan: provenance-drift-gate

## Revision 1 (2026-11-13T17:56:02Z, ExitPlanMode)

# Plan: feat--provenance-drift-gate

Execution Mode: Role-Based (`along-team`). The work spans more than 3 files and two subsystems: the kb-sync engine and the commit/CI gates.

## Context
`docs/topic--*.md` articles record `sources: [{path, hash}]`. `along kb-sync` only prints `[DRIFT]` warnings. No commit, wrap or CI gate checks them, and no command writes a new hash, so hashes are hand-edited and go stale (11 drift warnings across 6 topics on 2026-11-13). Goal: settle drift in the same change that edits a tracked source, through a CLI command, without letting old drift block unrelated work. Issue: `feat--provenance-drift-gate` (REQ-1..REQ-8).

## Design

### 1. Shared helpers: new `scripts/alongkit/provenance.py`
- Move `compute_content_hash` out of `scripts/along_kb_sync.py:28` (LF-normalized SHA-256); `along_kb_sync.py` imports it, and its old name stays importable from there (used in `tests/test_skills_and_scripts.py:1462`).
- `topic_sources(repo_root, read)`: parses each `docs/topic--*.md` with `alongkit.frontmatter.parse`. Returns `{source_path: [(topic_path, recorded_hash)]}`. Dict entries with a `hash` are tracked; plain-string entries and entries without a hash are untracked, matching the existing check at `along_kb_sync.py:1041-1067`. Paths are resolved against the context root that owns that `docs/` (nested subprojects supported, like the kb-sync cascade).
- `drift_for(paths, read)`: for the given changed paths, returns `(topic, source, recorded, actual)` for every tracked pair whose content hash differs. A deleted source counts as drift with `actual=None`.
- `accept(topic_path, sources, decision)`: rewrites only the `hash` values through `alongkit.frontmatter.update` (round-trip, keeps every other key and the body).

### 2. CLI in `scripts/along_kb_sync.py`
- `--accept-drift TOPIC [SOURCE ...]`: requires exactly one of `--reviewed` or `--no-doc-impact REASON` (exit 2 otherwise). With no SOURCE, it accepts all drifted sources of the topic. Prints `Doc-Provenance: <topic>; <source>; reviewed|no-doc-impact: <reason>` lines to quote in the commit message. On a `write_policy: manual` topic it also notes that content edits still need a `docs--` issue.
- `--drift-diff TOPIC`: for each drifted source, finds the last commit whose topic file contains the recorded hash (`git log -1 -S <hash> -- <topic>`) and prints `git diff <commit> -- <source>`. Otherwise prints "no commit recorded this hash".
- The existing `[DRIFT]` warning gains a hint: `along kb-sync --drift-diff <topic>`, then `--accept-drift`.

### 3. Gate `provenance_drift` in `scripts/alongkit/gitgates.py`
- `check_provenance(repo_root, changed, layer, read)`, following the `check_session_records` / `check_doc_routing` pattern:
  - pre-commit reads the index (`_index_reader`), so a staged topic hash counts;
  - CI reads the tree (`_tree_reader`) for paths changed in the range.
- Considers only tracked sources among `changed` (REQ-5), so pre-existing drift elsewhere never fires.
- Violation: `provenance_drift`, location `<topic>`, message names the source and the fix command.
- Wired into `check_pre_commit` (`gitgates.py:747`), `check_ci` (`gitgates.py:869`) and `scripts/along_commit.py` next to step 6 (`along_commit.py:275-282`), skipped with `-n` like the other steps. The bypass is the existing `-n --reason` flow with its `Along-Bypass:` trailer (`alongkit/bypass.py`).
- Declared in `scripts/alongkit/hooks/default_gates.yaml` like `session_record_append_only` (`default_gates.yaml:433`): `enforcement: [git, ci]`, profiles `strict: block`, `standard: block`, `light: warn`, `rule.type: predicate`, `handler: alongkit.gitgates.check_provenance`.

### 4. Docs (REQ-8)
- `docs/topic--llm-wiki-architecture.md` section 6 (drift gate): the new flags and the commit-time gate.
- `docs/topic--cli-reference.md` (kb-sync flags), `docs/topic--runtime-hooks-and-gates.md` (gate list), `skills/along-kb-sync/SKILL.md`.
- Refresh the provenance hashes of these topics with the new command, which is itself a dogfooding check.

## Tests (new `tests/test_provenance.py`, temp git repos as in `tests/test_session_records.py`)
- `accept` round-trip: other keys and the body stay byte-identical; only the named hashes change.
- `--accept-drift` without `--reviewed` / `--no-doc-impact` exits 2.
- Gate: a staged source edit without a hash update gives a `provenance_drift` violation; after accept and staging the topic, it passes.
- Gate: a commit touching an untracked file passes while another topic carries old drift.
- Gate: deleting a tracked source gives a violation.
- CI layer: range check flags only sources changed in the range.
- `--drift-diff` prints the source diff from the recording commit.
- `tests/test_alongkit.py` still passes (helpers live in `alongkit/`).

## Verification
- `python .along/scripts/test.py` (full suite).
- Manual: edit a tracked source in this repo, then `along gates check` fails; `along kb-sync --accept-drift ... --reviewed` makes it pass.
- `along kb-sync --strict`, `along sanitize docs --check`, `along graph-impact` on the changed engines.
- Wrap with `--no-decisions`, unless the gate profile choice deserves an ADR (decide at wrap).

## Out of scope
- Section- or symbol-level source hashing (separate `feat--` issue).
- Reviewing the 11 existing drift warnings (separate `docs--` issue; easier once this lands).
