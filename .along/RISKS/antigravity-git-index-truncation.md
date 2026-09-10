---
protocol: along
protocol_version: "2.6.0"
slug: antigravity-git-index-truncation
title: "Upstream Antigravity VS Code Extension Git Index Truncation"
severity: high
status: resolved
owner: user
mitigation: "Resolved upstream in v1.3.0 via fs.promises.utimes and isGitLensActive gate."
created: 2026-09-07
updated: 2026-09-10
---

# Upstream Antigravity Extension Git Index Truncation Bug and Mitigation

## Upstream Defect Description
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

## Resolution
Fixed upstream in Google Antigravity VS Code Extension v1.3.0 (`extension.js`):
1. `touchGitIndexForUri()` is now gated on `isGitLensActive()`, returning early if GitLens is not installed or not active.
2. File timestamp updates now use `safeTouchFile()`, which invokes `fs.promises.utimes(uri.fsPath, now, now)` instead of `vscode.workspace.fs.writeFile()`. This touches file timestamps without truncating or rewriting file content, eliminating the index corruption race condition with concurrent `git.exe`.
3. Verified on 2026-09-10 with extension version `google.google-antigravity-1.3.0`.

## Historic Mitigation (v1.2.0)
1. Backed up `extension.js` to `extension.js.bak` in `~/.vscode/extensions/google.google-antigravity-1.2.0/`.
2. Inserted early `return;` at the beginning of `touchGitIndexForUri()`.

## Periodic Verification & Decommission Criteria
- [x] Check `extension.js` in the new extension version directory.
- [x] Verify if Google upstream has fixed the race condition: confirmed fixed in v1.3.0 using `fs.promises.utimes` and `isGitLensActive`.
- [x] Risk marked as `status: resolved`.
