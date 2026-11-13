---
protocol: along
protocol_version: "4.8.1"
slug: feedback-github-pr-transport
type: feat
status: done
completed: 2026-11-13
priority: medium
created: 2026-11-11
updated: 2026-11-13
agent: claude-code
tags: [feedback, github]
blocked_by: []
related: [feat--feedback-maintainer-telegram-email-channels]
plan_status: approved
---

# Feedback GitHub PR transport (gh API or web fallback)

## Problem

A user working in any repo with Along installed tells the agent "create feedback for Along about X". The feedback must land in the Along repository as a Markdown file in Git (a PR with one inbox file), not as a GitHub Issue that the maintainer later has to harvest through the API. No own microservice: only GitHub infrastructure and the user's own GitHub identity.

Today `along feedback send` supports only `file`, `telegram` and `webhook` (`scripts/along_feedback.py`); none of them puts anything into the Along repo.

## Flow

1. The agent (skill `along-feedback`) drafts the feedback text, runs it through the existing PII/secret redaction, shows the final text to the user and waits for an explicit yes.
2. `along feedback send --channel github --title "..." --body-file <path>` dispatches it.
3. The command prints the PR URL (or the URL of the opened web page) so the user can open and review it.

### Path A: `gh` is installed and authenticated (fully automatic)

All via the GitHub API, nothing is cloned locally:
- `gh api user` -> login; check push permission on `actdim/along`.
- Maintainer / collaborator: create branch `feedback/<date>-<slug>` directly in `actdim/along`.
- Everyone else: server-side fork (`gh repo fork actdim/along --clone=false --default-branch-only`, sync if stale), branch in the fork.
- One `PUT /repos/<owner>/along/contents/.along/inbox/feedback--<date>-<slug>.md` = one commit with the single file.
- `gh pr create --repo actdim/along --head <login>:<branch> --label feedback`; print the PR URL.

### Path B: no `gh` (or not authenticated)

- Tell the user plainly: "this would be automatic with the GitHub CLI (`gh`); install it and run `gh auth login` to skip the browser next time".
- Open the GitHub web "new file" page pre-filled: `https://github.com/actdim/along/new/<base>?filename=.along/inbox/feedback--<date>-<slug>.md&value=<urlencoded body>`. For users without write access GitHub forks automatically and offers "Propose changes" -> PR. The user clicks two buttons; the result is the same PR with one inbox file.
- URL length is limited (about 8 KB): truncate the body, save the full redacted report via the `file` transport and say where it is.
- Print the opened URL and tell the user that the PR link appears after "Propose changes".

## Design notes / open questions

- Inbox location: `.along/inbox/` (tracked, not compiled into `ISSUES.md` until triaged) vs. directly `.along/ISSUES/` with a low status. Default: `.along/inbox/`.
- Minimal branch content: the PR diff contains only the inbox file regardless of base. Option to evaluate: a long-lived orphan base branch `feedback-inbox` holding only `.along/inbox/`, with feedback PRs targeting it, merged into `main` by the maintainer in batches. GitHub refuses PRs between branches with no common history, so feedback branches must be created from that base branch's tip, never as standalone orphans.
- The fork in Path A/B is server-side only (no local download). Delete the feedback branch after merge.
- PRs from first-time contributors need maintainer approval to run CI (standard GitHub behaviour; irrelevant for a `.md` file).
- No new runtime dependency: shell out to `gh`; no token handling in Along itself.

## Requirements
- REQ-1: `along feedback send --channel github` MUST create a PR in `actdim/along` adding exactly one file under `.along/inbox/` when `gh` is installed and authenticated.
- REQ-2: The command MUST NOT clone the Along repository locally.
- REQ-3: When `gh` is missing or not authenticated, the command MUST say that the flow would be automatic with `gh` and MUST open the pre-filled GitHub web "new file" page instead.
- REQ-4: The command MUST print the resulting PR URL (Path A) or the opened page URL (Path B).
- REQ-5: The payload MUST pass the existing redaction, and the skill MUST show it to the user and get an explicit yes before dispatch; `--dry-run` MUST print the payload and the planned API calls without any network access.
- REQ-6: The written file MUST pass `along sanitize` (ASCII typography) and carry front-matter (title, date, along version, OS, source tag `feedback`).

## Acceptance Criteria
- [x] `--channel github` implemented in `scripts/along_feedback.py` (Path A and Path B)
- [x] `skills/along-feedback/SKILL.md` teaches the agent the "create feedback for Along" flow, including the consent step
- [x] Hermetic tests with a faked `gh` and faked browser opener (no network)
- [x] Inbox location decided and documented
- [x] Automated tests passing
