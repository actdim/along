# install.ps1 - install the ALONG skills into Claude Code, Codex, OpenCode and/or Antigravity.
#
# Claude, Codex & Antigravity use the same ~/.<tool>/skills/<name>/SKILL.md format -> the skill folders are copied verbatim.
# OpenCode uses flat ~/.config/opencode/commands/<name>.md commands -> generated from the same SKILL.md bodies;
#   along-init's helper files (protocol.md, along_update.py, migrate_protocol.py) go to ~/.config/opencode/actdim-along/.
# The ALONG-PROTOCOL itself is picked up by all four natively via each repo's AGENTS.md.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1                  # all (default), copy
#   powershell ... -File install.ps1 -Target claude    # claude | codex | opencode | antigravity | both | all
#   powershell ... -File install.ps1 -Symlink          # symlink skill folders (claude/codex/antigravity)
#   powershell ... -File install.ps1 -Migrate          # also migrate this repository's .along/ structure
#   powershell ... -File install.ps1 -Uninstall        # remove exactly what the install manifest records

param(
    [ValidateSet('claude', 'codex', 'opencode', 'antigravity', 'both', 'all')][string]$Target = 'all',
    [switch]$Symlink,
    [switch]$InstallDeps,
    [switch]$Migrate,
    [switch]$Uninstall,
    [switch]$IncludeUnverifiedMcp,
    [string]$AlongHome       = (Join-Path $env:USERPROFILE '.along'),
    [string]$ClaudeHome      = (Join-Path $env:USERPROFILE '.claude'),
    [string]$CodexHome       = (Join-Path $env:USERPROFILE '.codex'),
    [string]$OpencodeHome    = (Join-Path $env:USERPROFILE '.config\opencode'),
    [string]$AntigravityHome = (Join-Path $env:USERPROFILE '.gemini\config')
)

$ErrorActionPreference = 'Stop'

# The engines this installer delegates to. Everything that has to decide something -
# which MCP configuration file a provider really reads, what a previous install put on
# disk - lives in scripts/, not in a here-string passed to `python -c`. See
# [bug--installer-parity-and-destructive-rules-overwrite].
function Get-PythonExe {
    # Presence on PATH is not enough: Windows ships a Microsoft Store stub named
    # python3.exe that is not Python and exits with an advertisement. A candidate has
    # to answer `-V` before it counts as an interpreter.
    foreach ($name in @('python', 'python3', 'py')) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        try {
            $null = & $found.Source -V 2>&1
            if ($LASTEXITCODE -eq 0) { return $found.Source }
        }
        catch { }
    }
    return $null
}

function Get-AlongTool([string]$scriptName) {
    # Returns the engine path only when it can actually be run, so every call site is
    # `if ($tool) { & $python $tool ... }` and the child's output reaches the console
    # instead of being swallowed by a function return value.
    if (-not (Get-PythonExe)) { return $null }
    $toolPath = Join-Path $PSScriptRoot (Join-Path 'scripts' $scriptName)
    if (-not (Test-Path $toolPath)) { return $null }
    return $toolPath
}

# Passed to both engines so a run never has to guess where a provider was installed,
# and so a test can point the whole installer at a throwaway directory.
$HomeArgs = @(
    '--user-home', (Split-Path -Parent $ClaudeHome),
    '--along-home', $AlongHome,
    '--claude-home', $ClaudeHome,
    '--codex-home', $CodexHome,
    '--opencode-home', $OpencodeHome,
    '--antigravity-home', $AntigravityHome
)

if ($Uninstall) {
    Write-Host "-> Uninstalling Along: removing exactly the files the install manifest records."
    $tool = Get-AlongTool 'install_manifest.py'
    if (-not $tool) {
        Write-Host "-> [Error] python not found; cannot read the install manifest."
        exit 1
    }
    & (Get-PythonExe) $tool @(@('uninstall') + $HomeArgs)
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Done. Your own files in the provider homes were left untouched."
    exit 0
}

$LegacySkills = @(
    'init-agents', 'update-agents', 'dashboard', 'repo-dashboard',
    'bump-version', 'check-graph', 'wrap-session', 'wrap-stage',
    'sync-context', 'sync-issues', 'sync-tasks', 'sync-decisions',
    'sync-history', 'init-kb', 'sync-kb', 'sync-wiki', 'search-kb', 'search-wiki',
    'along-wrap-session', 'along-wrap-stage',
    'along-sync-issues', 'along-sync-context', 'along-sync-decisions', 'along-sync-history',
    'along-check-graph', 'along-scan-deps', 'along-bump-version',
    'along-init-kb', 'along-sync-kb', 'along-search-kb', 'along-context-sync'
)

function Check-Dependencies {
    $uv = Get-Command 'uv' -ErrorAction SilentlyContinue
    if (-not $uv) {
        if ($InstallDeps) {
            Write-Host "-> Installing 'uv' package & Python version manager..."
            powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        }
        else {
            Write-Host "-> [Note] 'uv' is recommended for automatic Python/MCP tool management."
            Write-Host "   Install uv:  powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
            Write-Host "   Or run with: powershell ... -File install.ps1 -InstallDeps"
            Write-Host "   Or use mise: mise install"
        }
    }
    else {
        Write-Host "-> 'uv' detected: $($uv.Source)"
    }
}

Check-Dependencies

$src = Join-Path $PSScriptRoot 'skills'
if (-not (Test-Path $src)) { throw "Source skills folder not found: $src" }

function Write-Utf8NoBom([string]$path, [string]$text) {
    [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

function Purge-LegacySkillFolders([string]$homeDir) {
    $dst = Join-Path $homeDir 'skills'
    if (Test-Path $dst) {
        foreach ($legacy in $LegacySkills) {
            $legacyPath = Join-Path $dst $legacy
            if (Test-Path $legacyPath) {
                Remove-Item -Recurse -Force $legacyPath -ErrorAction SilentlyContinue
                Write-Host "   purged legacy skill: $legacy"
            }
        }
    }
}

function Install-SkillFolders([string]$homeDir) {
    $dst = Join-Path $homeDir 'skills'
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Purge-LegacySkillFolders $homeDir
    Write-Host "-> $dst"
    foreach ($d in Get-ChildItem -Directory $src) {
        $target = Join-Path $dst $d.Name
        if (Test-Path $target) { Remove-Item -Recurse -Force $target }
        if ($Symlink) {
            try {
                New-Item -ItemType SymbolicLink -Path $target -Target $d.FullName -ErrorAction Stop | Out-Null
                Write-Host "   linked  $($d.Name)"
            }
            catch {
                # One level of quoting, not two. `cmd /c mklink /J "`"$target`""` expands
                # to ""C:\path"" , which cmd reads as an empty argument followed by a bare
                # path: it happens to work while no path contains a space, and fails on
                # exactly the paths this fallback exists for. PowerShell already quotes an
                # argument that contains spaces when it builds the child command line.
                $null = cmd /c mklink /J $target $d.FullName 2>&1
                if (Test-Path $target) {
                    Write-Host "   linked (junction)  $($d.Name)"
                }
                else {
                    Copy-Item -Recurse $d.FullName $target
                    Write-Host "   copied (fallback)  $($d.Name)"
                }
            }
        }
        else {
            Copy-Item -Recurse $d.FullName $target
            Write-Host "   copied  $($d.Name)"
        }
    }
}

function Install-RuleFolders([string]$homeDir) {
    $rulesSrc = Join-Path $PSScriptRoot 'rules'
    if (Test-Path $rulesSrc) {
        $dst = Join-Path $homeDir 'rules'
        # Copied over, never replaced. This used to be `Remove-Item -Recurse -Force $dst`
        # followed by a fresh copy, so every install - including the ones the release
        # engine triggered unasked - destroyed whatever the user had written under
        # ~/.claude/rules/. Files Along shipped and no longer ships are removed by name
        # afterwards, from the install manifest. See
        # [bug--installer-parity-and-destructive-rules-overwrite].
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Copy-Item -Path "$rulesSrc\*" -Destination $dst -Recurse -Force
        Write-Host "   rules copied -> $dst"
    }
}

function Install-AlongScripts {
    $alongHome = $AlongHome
    $alongBin = Join-Path $alongHome 'bin'
    New-Item -ItemType Directory -Force -Path $alongBin | Out-Null
    $scriptsSrc = Join-Path $PSScriptRoot 'scripts'
    if (Test-Path $scriptsSrc) {
        Copy-Item -Path "$scriptsSrc\*" -Destination $alongBin -Recurse -Force
        # The shared `alongkit` package travels with the engines, which import it from
        # their own directory. Compiled caches must not: they are interpreter-specific.
        Get-ChildItem -Path $alongBin -Directory -Recurse -Filter '__pycache__' |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "-> Along tools installed -> $alongBin"
    }
    $cfgFile = Join-Path $alongHome 'config.json'
    $exampleCfg = Join-Path $PSScriptRoot 'config\along-config.example.json'
    if (-not (Test-Path $cfgFile) -and (Test-Path $exampleCfg)) {
        Copy-Item -Path $exampleCfg -Destination $cfgFile -Force
        Write-Host "-> Initialized default Along configuration: $cfgFile"
    }
}

function Install-OpenCode {
    $cmddir = Join-Path $OpencodeHome 'commands'
    $helper = Join-Path $OpencodeHome 'actdim-along'
    $oldHelper = Join-Path $OpencodeHome 'actdim-agents'

    New-Item -ItemType Directory -Force -Path $cmddir | Out-Null
    New-Item -ItemType Directory -Force -Path $helper | Out-Null

    # Clean legacy OpenCode files & unnamespaced aliases
    if (Test-Path $oldHelper) {
        Remove-Item -Recurse -Force $oldHelper -ErrorAction SilentlyContinue
    }
    foreach ($legacy in $LegacySkills) {
        $legacyCmd = Join-Path $cmddir "$legacy.md"
        if (Test-Path $legacyCmd) {
            Remove-Item -Force $legacyCmd -ErrorAction SilentlyContinue
        }
    }
    $shortAliases = @('build', 'commit', 'context-sync', 'dash', 'decision-sync', 'dep-scan', 'dev', 'graph-check', 'history-sync', 'init', 'issue-sync', 'kb-search', 'kb-sync', 'test', 'update', 'version-bump', 'wrap')
    foreach ($short in $shortAliases) {
        $shortCmd = Join-Path $cmddir "$short.md"
        if (Test-Path $shortCmd) {
            Remove-Item -Force $shortCmd -ErrorAction SilentlyContinue
        }
    }

    $scriptsSrc = Join-Path $PSScriptRoot 'scripts'
    if (Test-Path $scriptsSrc) {
        Copy-Item -Path "$scriptsSrc\*" -Destination $helper -Recurse -Force
        # The shared `alongkit` package travels with the engines, which import it from
        # their own directory. Compiled caches must not: they are interpreter-specific.
        Get-ChildItem -Path $helper -Directory -Recurse -Filter '__pycache__' |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path (Join-Path $src 'along-init\protocol.md')) {
        Copy-Item -Force (Join-Path $src 'along-init\protocol.md') (Join-Path $helper 'protocol.md')
    }

    foreach ($d in Get-ChildItem -Directory $src) {
        $raw = (Get-Content -Raw -Encoding UTF8 (Join-Path $d.FullName 'SKILL.md')) -replace "`r`n", "`n"
        $desc = ''
        $body = $raw
        if ($raw -match '(?s)^---\n(.*?)\n---\n(.*)$') {
            $fm = $matches[1]; $body = $matches[2]
            foreach ($line in ($fm -split "`n")) {
                if ($line -match '^description:\s*(.*)$') { $desc = $matches[1]; break }
            }
        }
        $note = ''
        if ($d.Name -eq 'along-init') {
            $note = '> OpenCode: helper files live at `' + $helper + '`. Where the steps below say "this skill''s folder", use `' + $helper + '`.' + "`n`n"
        }
        $content = "---`n" + 'description: "' + $desc + '"' + "`n---`n`n" + $note + $body
        Write-Utf8NoBom (Join-Path $cmddir ($d.Name + '.md')) $content
        Write-Host "   command $($d.Name).md"

    }
}


$targets = switch ($Target) {
    'claude'      { @('claude') }
    'codex'       { @('codex') }
    'opencode'    { @('opencode') }
    'antigravity' { @('antigravity') }
    'both'        { @('claude', 'codex') }
    'all'         { @('claude', 'codex', 'opencode', 'antigravity') }
}

Install-AlongScripts

foreach ($t in $targets) {
    switch ($t) {
        'claude' {
            Install-SkillFolders $ClaudeHome
            Install-RuleFolders $ClaudeHome
        }
        'codex' {
            Install-SkillFolders $CodexHome
            Install-RuleFolders $CodexHome
        }
        'opencode' {
            Install-OpenCode
        }
        'antigravity' {
            Install-SkillFolders $AntigravityHome
            Install-RuleFolders $AntigravityHome
        }
    }
}

# --- MCP registration, once, for the providers actually installed ---
# The installer used to write `code-review-graph` into five files and print a success
# line for each: only ~/.claude.json is read by anything. scripts/configure_mcp.py holds
# the per-provider contract, writes where it is verified, and reports the rest with the
# snippet to add by hand.
$mcpArgs = @()
foreach ($t in $targets) { $mcpArgs += @('--provider', $t) }
if ($IncludeUnverifiedMcp) { $mcpArgs += '--include-unverified' }
$mcpArgs += @('--user-home', (Split-Path -Parent $ClaudeHome),
              '--claude-home', $ClaudeHome, '--codex-home', $CodexHome,
              '--opencode-home', $OpencodeHome, '--antigravity-home', $AntigravityHome)
Write-Host "-> code-review-graph MCP:"
$mcpTool = Get-AlongTool 'configure_mcp.py'
if ($mcpTool) {
    & (Get-PythonExe) $mcpTool @mcpArgs
}
else {
    Write-Host "   (skipped: python not found, so no provider configuration was touched)"
}

# --- Install manifest: what was written, and what a previous install left behind ---
# Nothing here deletes a directory. The manifest names the files Along itself wrote, so
# a superseded one can be removed by name and a file the user wrote is never a candidate.
# It is also what `-Uninstall` reads.
$manifestArgs = @('sync', '--source', $PSScriptRoot) + $HomeArgs
foreach ($t in $targets) { $manifestArgs += @('--target', $t) }
$manifestTool = Get-AlongTool 'install_manifest.py'
if ($manifestTool) {
    & (Get-PythonExe) $manifestTool @manifestArgs
}
else {
    Write-Host "-> [Note] python not found; no install manifest was written."
    Write-Host "   Run later:  python scripts\install_manifest.py sync --source ."
}

# --- Migrate this repository's protocol structure, only when asked (-Migrate) ---
# Installing used to migrate whatever repository the installer happened to sit in. The
# migration engine rewrites front-matter, moves entities and deletes legacy directories,
# so an install could silently change a working tree nobody had pointed it at. See
# [bug--migration-deletes-destination-without-backup].
$hasState = (Test-Path (Join-Path $PSScriptRoot '.along')) -or (Test-Path (Join-Path $PSScriptRoot '.agents'))
if ($hasState) {
    $py = Get-PythonExe
    if (-not $py) {
        Write-Host "-> [Note] python not found; skipping the protocol migration."
    } elseif ($Migrate) {
        Write-Host "-> Running the Along protocol migration for this repository..."
        & $py (Join-Path $PSScriptRoot 'scripts\migrate_protocol.py') $PSScriptRoot --apply
    } else {
        Write-Host "-> [Note] This repository carries Along state. Installing does not migrate it."
        Write-Host "   Preview:  python scripts\migrate_protocol.py . --dry-run"
        Write-Host "   Apply:    python scripts\migrate_protocol.py . --apply   (or re-run the installer with -Migrate)"
    }
}

Write-Host "Done. Claude/Codex/Antigravity skills register next session as /along-* (/along-init, /along-update, /along-dash, etc.); OpenCode picks up /commands, and all read AGENTS.md natively."
Write-Host "     MCP registration is reported per provider above: only a verified configuration contract is written to."
Write-Host "     To remove Along again: install.ps1 -Uninstall  (removes only what the manifest records)."
