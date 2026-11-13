# Living Plan: feedback-github-pr-transport

## Revision 1 (2026-11-13T14:31:01Z, plan approve --plan-file)

# Living Plan: feat--feedback-github-pr-transport

Execution Mode: Role-Based (6 files: one new `alongkit` module, the feedback engine, its tests, the skill and two docs; one subsystem, but more than 3 files)

## Context

Goal (see the ticket): a user in any repo with Along installed tells the agent "create feedback for Along about X"; the result is a PR in `actdim/along` that adds exactly one Markdown file under `.along/inbox/`. With `gh` the flow is fully automatic; without `gh` the agent says so and opens the pre-filled GitHub web page instead. No local clone, no own service. Telegram / email are out of scope (`feat--feedback-maintainer-telegram-email-channels`).

Facts the steps rely on (verified 2026-11-13):

- `scripts/along_feedback.py`: transports `TelegramTransport`, `WebhookTransport`, `FileTransport` (static `send(report_text, incidents, config)` -> `(ok, msg)`); `dispatch_feedback(channel, incident_id, note, dry_run, repo_root)` returns early with "No unresolved diagnostic incidents" when there are no incidents, so free-text feedback is impossible today; `--channel` choices are `all|telegram|webhook|file`; `all` = file + enabled telegram/webhook; on any success incidents are marked resolved.
- Routing: `scripts/along_exec.py` maps `feedback` / `diagnostics` to `along_feedback.py`.
- `alongkit.diagnostics`: `ConfigManager.load_config(repo_root)`, `Redactor.sanitize_text`, `DiagnosticsStore`, `EXPORT_DIR`; `alongkit.version.CURRENT_VERSION`.
- `alongkit.proc.run_capture(cmd, ...)` -> `Result` (subprocess wrapper used by tests); `alongkit.typography.clean(text) -> (text, changed)` does the ASCII typography normalization.
- Existing `gh` detection precedent: `scripts/along_version_bump.py` uses `shutil.which("gh")`.
- `tests/test_feedback.py`: `TestAlongFeedbackEngine` test_01..test_06, temp diagnostics dirs, `unittest.mock`; test_06 runs the CLI through `proc.run_capture`.
- `tests/test_alongkit.py::TestNoDuplicateHelpers`: helpers live only in `scripts/alongkit/`; engines and tests must not redefine a module-level name defined elsewhere.
- Docs: `docs/topic--cli-reference.md` section "`along feedback`" documents non-existent `--export` / `--send` flags (fix while editing that section); `docs/topic--skills-reference.md` section "`along-feedback`".
- Windows command-line length limit (~32K chars): the file content must go to `gh api` via `--input <json file>`, not as a `-f content=` argument.
- A non-collaborator cannot create a branch in `actdim/along`; a server-side fork is unavoidable (`gh repo fork --clone=false`; the web editor forks automatically). Labels can only be set by users with triage rights, so no `--label` on the PR.

Defaults chosen (change at approval if needed):
- D1: Inbox path `.along/inbox/feedback--<YYYY-MM-DD>-<slug>.md` (tracked, not compiled into `ISSUES.md` until triaged).
- D2: PR base `main`. The orphan `feedback-inbox` base branch from the ticket's notes is NOT implemented here.
- D3: Target repo `actdim/along`, overridable by config `transports.github.repo` or env `ALONG_FEEDBACK_GITHUB_REPO` (for forks and tests).
- D4: `github` is never part of `--channel all`; it is explicit only.
- D5: Consent is enforced by the CLI: without `--yes` the github channel only prints the full file content and the planned actions, prints "NOT SENT", exits 0.

## Steps

- [x] Step 1: Free-text feedback payload in `alongkit` (REQ-5, REQ-6)
  - New module `scripts/alongkit/feedback_github.py`.
  - `build_inbox_note(title, body, incidents) -> (rel_path, text)`: slug from title (ASCII, lowercase, `-`, max 50 chars), path per D1; front-matter `title`, `date`, `along_version`, `os` (`platform.system()` + release), `python`, `source: along-feedback`, `tags: [feedback]`; body = user text, then an "Incidents" section only if incidents are given (id, component, first 200 chars of error).
  - Everything passes `Redactor.sanitize_text`, then `typography.clean`.
  - Done when: unit tests show redacted paths/tokens and pure ASCII output.

- [x] Step 2: `GitHubTransport` with `gh` path (REQ-1, REQ-2, REQ-4)
  - In `feedback_github.py`; dependencies injected for tests: `which` (default `shutil.which`), `run` (default `proc.run_capture`), `open_url` (default `webbrowser.open`).
  - Preconditions: `which("gh")` and `gh auth status` exit 0; otherwise go to Step 3.
  - Sequence: `gh api user --jq .login`; `gh api repos/<repo> --jq .permissions.push`; if not `true`: `gh repo fork <repo> --clone=false --default-branch-only`, resolve the fork (`gh api repos/<login>/<name> --jq .parent.full_name` must equal `<repo>`, else clear error), `gh api -X POST repos/<fork>/merge-upstream -f branch=main`; base sha `gh api repos/<repo>/git/ref/heads/main --jq .object.sha`; `POST repos/<target>/git/refs` for `refs/heads/feedback/<date>-<slug>` (on 422 "already exists" append `-2`, `-3`); `PUT repos/<target>/contents/<rel_path>` with `--input` JSON temp file (`message`, base64 `content`, `branch`); `gh pr create --repo <repo> --base main --head <owner>:<branch> --title "feedback: <title>" --body <short body with Along version>`.
  - Return `(True, "<PR URL>")` parsed from `gh pr create` stdout.
  - Any failing `gh` call: report its stderr verbatim, then fall back to Step 3 (browser) and say that the automatic path failed.
  - Done when: faked-`run` tests cover collaborator and fork paths and assert no `git clone` is ever called.

- [x] Step 3: Web fallback (REQ-3, REQ-4)
  - Message first: "GitHub CLI (gh) not found / not authenticated: with gh this would be fully automatic. Install it and run `gh auth login` to skip the browser next time. Opening the GitHub page instead."
  - URL `https://github.com/<repo>/new/main?filename=<rel_path>&value=<urlencoded text>`; if the URL exceeds 7000 chars, truncate the body, save the full note to `EXPORT_DIR` and tell the user to paste/attach it (print the path with the home directory redacted).
  - `open_url(url)`; print the URL and "click 'Propose changes', then 'Create pull request'; the PR link appears there".
  - Done when: tests for gh missing, gh unauthenticated and over-long body pass.

- [x] Step 4: Wire into `along_feedback.py` (REQ-1..REQ-5)
  - `send` gains `--channel github`, `--title`, `--body-file`, `--yes`; `--title` and `--body-file` required for `github` (argparse error exit 2 otherwise).
  - `dispatch_feedback` no longer returns early for the `github` channel when there are no incidents; incidents (if any) are attached and marked resolved only after success, as today.
  - Without `--yes` or with `--dry-run`: print note path, full note text and the planned actions (gh path or browser), print "NOT SENT", no subprocess and no browser call (D5).
  - Update the module docstring usage line.
  - Done when: CLI test via `proc.run_capture` shows the preview and "NOT SENT".

- [x] Step 5: Tests in `tests/test_feedback.py` (all REQs)
  - New test methods (test_07..): note building and redaction; preview without `--yes`; gh missing -> browser URL contains `filename=.along/inbox/` and the encoded title; gh unauthenticated -> browser; collaborator path call sequence (no fork); non-collaborator path (fork + merge-upstream); branch-exists retry; gh failure mid-way -> stderr reported + browser fallback; long body truncation; `all` does not include github.
  - Fakes only: no network, no real `gh`, no real browser; temp dirs as in existing tests; no name clashes with `alongkit` (TestNoDuplicateHelpers).

- [x] Step 6: Skill and docs
  - `skills/along-feedback/SKILL.md`: section "Send feedback to the Along maintainers": trigger phrases ("create/send feedback for Along"), flow = draft text -> write to a temp file -> run with `--dry-run`, show the output to the user -> after an explicit yes re-run with `--yes` -> give the user the PR URL (or the page instructions).
  - `docs/topic--cli-reference.md` `along feedback` section: real subcommands and the new flags (drop the non-existent `--export` / `--send`).
  - `docs/topic--skills-reference.md` `along-feedback` section: add the GitHub PR channel.

- [x] Step 7: Verify and close
  - `/along-test` (`python .along/scripts/test.py`) green; `along sanitize` and `along lint` clean on changed files; `git diff --stat` matches the 6 files.
  - Manual smoke (only on the user's explicit yes, it creates a real PR): `along feedback send --channel github --title "smoke test" --body-file <f> --yes` from another repo.
  - Record an ADR for D1 (inbox location) and D2 via `/along-decision-sync`; `along wrap feedback-github-pr-transport --summary "..." --decisions <ADR>`.

## Out of scope
- Telegram default channel and email (`feat--feedback-maintainer-telegram-email-channels`).
- GitHub Action that turns issues into inbox PRs; orphan `feedback-inbox` base branch.
- Triage tooling for `.along/inbox/` (promote an inbox note to an issue).
