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

param(
    [ValidateSet('claude', 'codex', 'opencode', 'antigravity', 'both', 'all')][string]$Target = 'all',
    [switch]$Symlink,
    [switch]$InstallDeps,
    [switch]$Migrate,
    [string]$ClaudeHome      = (Join-Path $env:USERPROFILE '.claude'),
    [string]$CodexHome       = (Join-Path $env:USERPROFILE '.codex'),
    [string]$OpencodeHome    = (Join-Path $env:USERPROFILE '.config\opencode'),
    [string]$AntigravityHome = (Join-Path $env:USERPROFILE '.gemini\config')
)

$ErrorActionPreference = 'Stop'

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
                $null = cmd /c mklink /J "`"$target`"" "`"$($d.FullName)`"" 2>&1
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
        if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Copy-Item -Path "$rulesSrc\*" -Destination $dst -Recurse -Force
        Write-Host "   rules copied -> $dst"
    }
}

function Install-AlongScripts {
    $alongHome = Join-Path $env:USERPROFILE '.along'
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

function Set-McpConfigJson([string]$filePath) {
    try {
        $parent = Split-Path -Parent $filePath
        if ($parent -and -not (Test-Path $parent)) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        
        $py = Get-Command 'python' -ErrorAction SilentlyContinue
        if ($py) {
            $script = @"
import json, os, sys
path = sys.argv[1]
data = {}
if os.path.exists(path) and os.path.getsize(path) > 0:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
if not isinstance(data, dict):
    data = {}
if 'mcpServers' not in data or not isinstance(data['mcpServers'], dict):
    data['mcpServers'] = {}
if 'code-review-graph' not in data['mcpServers']:
    data['mcpServers']['code-review-graph'] = {
        'command': 'uvx',
        'args': ['code-review-graph']
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'   registered code-review-graph MCP in {path}')
else:
    print(f'   code-review-graph MCP already configured in {path}')
"@
            & python -c $script $filePath
            return
        }

        $json = $null
        if (Test-Path $filePath) {
            $raw = Get-Content -Raw -Encoding UTF8 $filePath
            if ($raw -and $raw.Trim()) {
                $json = $raw | ConvertFrom-Json
            }
        }
        if (-not $json) {
            $json = [PSCustomObject]@{}
        }
        if (-not $json.PSObject.Properties['mcpServers']) {
            $json | Add-Member -MemberType NoteProperty -Name 'mcpServers' -Value ([PSCustomObject]@{}) -Force
        }
        if (-not $json.mcpServers.PSObject.Properties['code-review-graph']) {
            $crg = [PSCustomObject]@{
                command = 'uvx'
                args = @('code-review-graph')
            }
            $json.mcpServers | Add-Member -MemberType NoteProperty -Name 'code-review-graph' -Value $crg -Force
            $out = $json | ConvertTo-Json -Depth 10
            Write-Utf8NoBom $filePath $out
            Write-Host "   registered code-review-graph MCP in $filePath"
        }
        else {
            Write-Host "   code-review-graph MCP already configured in $filePath"
        }
    }
    catch {
        Write-Host "   (note: could not update $filePath - $_)"
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
            Set-McpConfigJson (Join-Path $env:USERPROFILE '.claude.json')
            Set-McpConfigJson (Join-Path $ClaudeHome 'mcp_config.json')
        }
        'codex' {
            Install-SkillFolders $CodexHome
            Install-RuleFolders $CodexHome
            Set-McpConfigJson (Join-Path $CodexHome 'mcp_config.json')
        }
        'opencode' {
            Install-OpenCode
            Set-McpConfigJson (Join-Path $OpencodeHome 'mcp_config.json')
        }
        'antigravity' {
            Install-SkillFolders $AntigravityHome
            Install-RuleFolders $AntigravityHome
            Set-McpConfigJson (Join-Path $AntigravityHome 'mcp_config.json')
        }
    }
}

# --- Migrate this repository's protocol structure, only when asked (-Migrate) ---
# Installing used to migrate whatever repository the installer happened to sit in. The
# migration engine rewrites front-matter, moves entities and deletes legacy directories,
# so an install could silently change a working tree nobody had pointed it at. See
# [bug--migration-deletes-destination-without-backup].
$hasState = (Test-Path (Join-Path $PSScriptRoot '.along')) -or (Test-Path (Join-Path $PSScriptRoot '.agents'))
if ($hasState) {
    $py = Get-Command 'python' -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Host "-> [Note] python not found; skipping the protocol migration."
    } elseif ($Migrate) {
        Write-Host "-> Running the Along protocol migration for this repository..."
        & python (Join-Path $PSScriptRoot 'scripts\migrate_protocol.py') $PSScriptRoot --apply
    } else {
        Write-Host "-> [Note] This repository carries Along state. Installing does not migrate it."
        Write-Host "   Preview:  python scripts\migrate_protocol.py . --dry-run"
        Write-Host "   Apply:    python scripts\migrate_protocol.py . --apply   (or re-run the installer with -Migrate)"
    }
}

Write-Host "Done. Claude/Codex/Antigravity skills register next session as /along-* (/along-init, /along-update, /along-dash, etc.); OpenCode picks up /commands, code-review-graph MCP is configured, and all read AGENTS.md natively."
