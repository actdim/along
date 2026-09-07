---
protocol: along
slug: antigravity-extension-git-index-truncation
type: bug
status: open
priority: high
created: 2026-09-07
updated: 2026-09-07
agent: antigravity
tags: [antigravity, git, upstream, bug]
blocked_by: []
related: [bug--remove-git-locking-workarounds]
---

# Track Upstream Antigravity Extension Git Index Truncation Bug and Hotfix

## Upstream Bug Description
- **Affected Component**: Google Antigravity VS Code Extension (`google.google-antigravity` v1.2.0, `extension.js`).
- **Public Report**: [Reddit Bug Report](https://www.reddit.com/r/google_antigravity/comments/1w996ck/bug_report_gitindex_corruption_race_condition_on/)
- **Root Cause**:
  In `extension.js` inside `refreshGitAndGitLens()`, the extension runs `vscode.commands.executeCommand('git.refresh')` (spawning background `git.exe`), while concurrently calling `touchGitIndexForUri(docUri)`.
  Inside `touchGitIndexForUri()`, the code attempts to update the timestamp of `.git/index` for GitLens cache invalidation via:
  ```javascript
  const data = await vscode.workspace.fs.readFile(indexUri);
  await vscode.workspace.fs.writeFile(indexUri, data);
  ```
  On Windows NTFS, `vscode.workspace.fs.writeFile` opens `.git/index` with truncation (`O_TRUNC`), reducing the file size to 0 bytes before writing `data`.
  When concurrent `git.exe` reads the 0-byte index file, Git's C runtime (`read-cache.c`) dies with:
  ```text
  fatal: .git/index: index file smaller than expected
  ```
  This triggers modal error popups on every agent edit and diff Accept action.

## Local Hotfix
1. Backed up `extension.js` to `extension.js.bak` in `~/.vscode/extensions/google.google-antigravity-1.2.0/`.
2. Inserted early `return;` at the beginning of `touchGitIndexForUri()` (around line 300255), completely preventing the extension from truncating `.git/index`.

## Periodic Verification & Decommission Criteria
- [ ] On future Antigravity extension updates, check `extension.js` in the new extension version directory.
- [ ] Verify if Google upstream has fixed the race condition (e.g. by using `fs.utimes`, gating on active GitLens extension, or eliminating the index rewrite).
- [ ] If upstream is fixed, verify that `.git/index` is never truncated and close this issue as `done`.
- [ ] If upstream is not yet fixed, re-apply the hotfix to the newly installed extension version.

