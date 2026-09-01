---
protocol: along
protocol_version: 2.2.8
slug: installer-parity-and-destructive-rules-overwrite
type: bug
status: done
completed: 2026-09-01
priority: critical
created: 2026-09-01
updated: 2026-09-01
agent: claude-code
tags: [installer, cross-platform, mcp, data-loss, powershell]
milestone: v3.0.0-global-quality-revision
blocked_by: []
related: [release-engine-mutates-before-tests-and-reinstalls-globals, unpinned-mcp-and-ghost-wiki-query-tool]
parent: protocol-quality-audit-remediation
---

# Installers are not at parity, destroy user rule directories, and register MCP in unverified locations

## Problem 1: Linux and macOS users get no rule packs

`install.ps1:108-117` installs the rule packs:

```powershell
function Install-RuleFolders([string]$homeDir) {
    $rulesSrc = Join-Path $PSScriptRoot 'rules'
    ...
    Copy-Item -Path "$rulesSrc\*" -Destination $dst -Recurse -Force
}
```

`install.sh` contains zero occurrences of the string `rules`. Verified:

```text
Select-String -Path install.sh -Pattern 'rules' -SimpleMatch  ->  0 matches
```

So the six platform archetypes and five language rule packs, which `rules/INDEX.md`
presents as a core feature, are simply absent on Unix installs.

The existing parity test does not catch this because it only compares skill folder names:

```python
# tests/test_skills_and_scripts.py:205-211
def test_09_install_scripts_match_skills(self):
    skill_dirs = [os.path.basename(p) for p in glob.glob(...,"skills","along-*")]
```

## Problem 2: installation deletes the user's rules directory

```powershell
# install.ps1:110-114
$dst = Join-Path $homeDir 'rules'
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
```

Any user-authored file under `~/.claude/rules/` is destroyed on every install, and the
install is also triggered implicitly by `along_version_bump.py` (see
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`). Rules should be
merged or installed into a namespaced subdirectory (`~/.claude/rules/along/`), never by
wiping the parent.

## Problem 3: the installer violates the protocol rule it ships

`AGENTS.md` states: "Never execute fragile multi-line inline shell strings
(`python -c \"...\"`) containing escaped quotes on Windows / PowerShell."

`install.ps1:200-225` does exactly that: a 24-line here-string passed to `python -c` to
edit JSON. The same pattern is in `install.sh:160-191`. The protocol's own reference
implementation is the primary violator of its determinism rule.

## Problem 4: MCP registration targets unverified paths

The installers write `code-review-graph` into:

- `~/.claude.json` - correct for Claude Code.
- `~/.claude/mcp_config.json` - not a path Claude Code reads.
- `~/.codex/mcp_config.json` - Codex configuration is `~/.codex/config.toml`.
- `~/.config/opencode/mcp_config.json` - unverified.
- `~/.gemini/config/mcp_config.json` - unverified.

Three or four of the five writes are likely inert, yet the installer prints
"code-review-graph MCP is configured" for all of them. Either verify each provider's real
configuration contract or stop claiming success.

## Problem 5: fragile junction fallback quoting

```powershell
# install.ps1:91
$null = cmd /c mklink /J "`"$target`"" "`"$($d.FullName)`"" 2>&1
```

Double-wrapped quoting produces `""path""` for `cmd`. It happens to work for paths without
spaces and is fragile for paths with spaces, which is the case this fallback exists to
handle.

## Problem 6: no idempotency or version reporting

The installer neither reports the currently installed version nor skips unchanged skills.
Every run is a full delete-and-copy of every skill folder in every provider home.

## Requirements

- REQ-1: Bring `install.sh` to full parity: rule packs, and any other artifact `install.ps1`
  handles. Add a parity test that compares the artifact sets (skills, rules, scripts,
  configs), not just skill names.
- REQ-2: Never delete a user directory. Install rules into a namespaced subdirectory and
  remove only files Along itself previously wrote (tracked via a manifest).
- REQ-3: Replace both inline `python -c` blocks with a standalone script
  (`scripts/configure_mcp.py`) invoked with arguments.
- REQ-4: Verify each provider's actual MCP configuration path; write only where the contract
  is confirmed, and report skipped providers honestly.
- REQ-5: Fix the `mklink /J` quoting and add a test using a path containing a space.
- REQ-6: Write an install manifest (`~/.along/install-manifest.json`) with version, target
  homes, and installed files, enabling idempotent updates and clean uninstall.
- REQ-7: Add an `--uninstall` / `-Uninstall` path that removes only manifest-listed files.

## Acceptance Criteria

- [x] `install.sh` and `install.ps1` install identical artifact sets, enforced by test.
- [x] Pre-existing user files in `~/.claude/rules/` survive an install.
- [x] Zero inline `python -c` in installer scripts.
- [x] MCP configuration written only to verified paths; unverified providers reported.
- [x] Install manifest written; second run is a no-op for unchanged content.

## Implementation

| Requirement | Where it landed |
| :--- | :--- |
| REQ-1 parity by artifact | `alongkit.install.planned_files()` describes the installed layout once. `tests/test_installers.py::TestInstallerScriptsMatchThePlan` runs each real installer against a throwaway checkout (path containing a space) into throwaway homes and asserts disk equals the plan in both directions. Both produce the same 174 files for `all`. The probe list in `test_09_installer_artifact_parity` is kept as a cheap first line and gained manifest and uninstall probes. `install.sh` had already gained `rules/` in `[bug--tests-mutate-working-tree]`; this closes the mechanism that let it go missing. |
| REQ-2 no user directory is deleted | `Install-RuleFolders` no longer runs `Remove-Item -Recurse -Force $dst`; both installers copy over the destination. Superseded files are removed by name from the manifest, scoped to the providers of the run. Rules stay at `<home>/rules/` rather than moving to a namespaced subdirectory: the packs are loaded by path from `rules/INDEX.md` and relocating them would break every existing reference for no additional safety, since the manifest already makes the delete unnecessary. |
| REQ-3 no inline `python -c` | Both blocks replaced by `scripts/configure_mcp.py` over `alongkit.install`. `TestInstallerSourceHygiene::test_no_installer_runs_an_inline_python_program` fails if one returns (comment lines excluded, so the file can still explain what was removed). |
| REQ-4 verified MCP paths only | `install.mcp_target()` carries a per-provider contract and a `verified` flag. Written: Claude Code's `mcpServers` in `~/.claude.json`. Reported with path and snippet, written only under `--include-unverified-mcp`: Codex `~/.codex/config.toml` (`[mcp_servers.<name>]`, appended, never rewritten), OpenCode `opencode.json`, Antigravity the Gemini settings file. The four inert `mcp_config.json` writes and their success lines are gone. A configuration file that does not parse is now refused rather than replaced from `{}`. |
| REQ-5 junction quoting | `cmd /c mklink /J $target $d.FullName` - one level of quoting, PowerShell quotes the arguments. Exercised by `test_a_linked_install_records_links_and_uninstalls_without_touching_the_source` with a space in both the checkout and the home path. That test also covers a defect the fix uncovered: `os.path.islink` is False for a junction, so the manifest would have recorded the repository's own files and an uninstall would have deleted the checkout through the link. `install.is_link` tests the reparse-point attribute; removal uses `os.rmdir`. |
| REQ-6 install manifest | `~/.along/install-manifest.json`: schema, version, date, source, providers, homes, and every installed path with a content hash. `install_manifest.py sync` reports added / changed / unchanged and prunes; a second install reports every file unchanged and rewrites the same manifest. The copy step itself still rewrites identical bytes: making the shells hash-compare per file would duplicate the layout logic in three places, so "no-op" is guaranteed by content and by the report, not by skipped writes. |
| REQ-7 uninstall | `install.ps1 -Uninstall` / `./install.sh --uninstall` -> `install_manifest.py uninstall`, which removes exactly the recorded paths, cleans the directories that become empty, and leaves `~/.along/config.json`, user files, and provider configuration in place. |

Recorded as ADR-2026-09-01--installers-never-delete-what-they-did-not-write. Every install
root is overridable (`--along-home`, `--claude-home`, ...), which is what lets the tests run
the real installers without touching a developer's own home. Suite: 209 -> 226 tests.
