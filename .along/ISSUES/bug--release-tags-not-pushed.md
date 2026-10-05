---
protocol: along
protocol_version: "4.4.5"
slug: release-tags-not-pushed
type: bug
status: open
priority: high
created: 2026-10-05
updated: 2026-10-05
agent: claude-code
tags: [release, version-bump, git]
blocked_by: []
related: []
milestone: v4.5.0-multi-user-merge-automation
---

# Release tags stay local and are not pushed (v4.4.5 reached origin only by hand)

Release tags are regularly created locally but never reach the remote. On 2026-10-05 the
annotated tag `v4.4.5` (on release commit `e2f3172`) existed locally while `origin` had tags
only up to `v4.4.4`, although `main` itself was already in sync with `origin/main`. The tag
was pushed by hand (`git push origin v4.4.5`).

## Facts
- Likely path: `along bump` ran without `-p/--push`, then the commits went out with a plain
  `git push`, which does not send tags; `push.followTags` is not set in this repository.
- `scripts/along_version_bump.py` `create_release_commit()` runs `git tag -a v<version>` after
  the commit and pushes only with `-p/--push` (`git push --follow-tags`).
- A failed `git tag` only prints `[Error]` and returns `complete = False`; the release commit
  stays. Nothing later reports a release commit without its tag.
- Without `--push` the tag (if created) stays local, and a later plain `git push` does not send
  annotated tags unless `push.followTags` is set.
- Checking this needed `git ls-remote`, which the plan gate held in the inquiry phase, see
  [bug--plan-gate-blocks-readonly-git].

## Open questions (decide before fixing)
- Confirm how earlier releases were pushed (tags `v4.4.0`..`v4.4.4` did reach the remote).
- Should the protocol make the tag part of the release contract (bump fails/rolls back
  without the tag, `push.followTags` set by `along git setup`, push of the tag as a completion
  step, `along doctor` / wrap check for untagged `release:` commits)?

## Acceptance Criteria
- [ ] Root cause of the unpushed release tags confirmed
- [x] `v4.4.5` pushed to `origin` (2026-10-05)
- [ ] Protocol/tooling change so an untagged or unpushed release is detected or impossible
- [ ] Automated tests passing
