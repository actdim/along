# Living Plan: Harden test_zz_hermetic_suite against flaky Windows Git stat-cache

## Execution Mode
Direct (1 test file).

## Revision note (2026-11-08 review)
The previous revision dropped the `vanished` category from the failure report. That removes the
most valuable thing the gate catches: a test that reverts, stashes or deletes a developer's
uncommitted file makes that file vanish from `git status` exactly like a stat-cache flip does.
Status alone cannot tell the two apart; file content can.

The previous revision also relied on `git update-index -q --refresh`. `git status` already
refreshes the stat cache (and writes the index opportunistically), which is what the existing
double `git status` call exploits. `update-index --refresh` adds an index write and an
`index.lock` acquisition for little gain, so it is demoted to optional.

The existing gate also has a blind spot the old plan did not mention: a file dirty in the
baseline (`M`) that the suite modifies further stays `M`, so `changed` never sees it.

Issue REQ-1, REQ-2 and REQ-3 were amended (2026-11-08) to: "classify baseline-dirty entries by content
hash; vanished or status-changed entries with unchanged content are benign; content changes fail".

## 1. Root cause still to confirm
No failing run is attached to the issue. Step 0 captures one so the fix is measured, not guessed.

## 2. Design
Snapshot = `{path: (status, digest)}` where `digest` is the SHA-256 of the working-tree file
(or `None` when the path does not exist or is a directory).

- Hash only entries reported by `git status --porcelain -u` (the dirty set is small), so the
  cost stays negligible.
- Decision table, per path in `BASELINE` union `after`:

| Baseline | After | Content digest | Verdict |
| :--- | :--- | :--- | :--- |
| absent | present | n/a | `appeared` -> fail |
| present | absent | equal to baseline | stat-cache flip -> ignore |
| present | absent | different / file gone | `reverted or deleted` -> fail |
| present | present, status differs | equal | stat-cache flip -> ignore |
| present | present, status differs | different | `status changed` -> fail |
| present | present, same status | different | `content changed` -> fail (new coverage) |
| present | present, same status | equal | ok |

- Keep the double `git status` call; optionally run `git update-index -q --refresh` first, with
  its result ignored, only if Step 0 shows the flip survives the double call.
- Document in the docstring that a developer editing files while the suite runs will trip the
  gate; that is accepted and the message says so.

## 3. Steps
0. Reproduce: run the full suite on Windows until `test_01` fails; record the reported paths and
   whether their content differed (`git diff --stat` on those paths). Note the result in the issue.
1. Add `_digest(repo_root, path) -> str | None` and extend `porcelain_snapshot()` to return
   `{path: (status, digest)}`. Keep the `None` return when git cannot answer.
2. Rewrite the comparison in `test_01_working_tree_is_unchanged_by_the_suite` per the table, with
   report labels `appeared`, `status changed`, `content changed`, `reverted or deleted`.
3. Leave `test_02` and `test_03` untouched.
4. Add focused unit tests (same file or `tests/test_hermetic_snapshot.py`) for the classifier as a
   pure function over two snapshots: flip ignored, revert detected, content change on an
   already-dirty file detected, new file detected.

## 4. Verification
- `python .along/scripts/test.py test_zz_hermetic_suite.py` on a clean tree and on a dirty tree.
- Full `python .along/scripts/test.py` run on Windows: no false positive across 3 consecutive runs.
- Manual negative check: temporarily add a test that overwrites a dirty tracked file in a scratch
  copy of the logic (classifier unit test), confirm it fails.
- `along sanitize` clean.

## 5. Sequencing
Land before `task--optimize-test-suite-execution-time`, which changes how `test_zz` is scheduled.
