#!/usr/bin/env bash
# install.sh - install the ALONG skills into Claude Code, Codex, OpenCode and/or Antigravity.
# For Linux / macOS (and Git Bash on Windows).
#
# Claude, Codex & Antigravity use the same ~/.<tool>/skills/<name>/SKILL.md format -> the skill folders are copied verbatim.
# OpenCode uses flat ~/.config/opencode/commands/<name>.md commands -> generated from the same SKILL.md bodies;
#   along-init's helper files (protocol.md, along_update.py, migrate_protocol.py) are placed in ~/.config/opencode/actdim-along/.
# The ALONG-PROTOCOL itself is picked up by all four natively via each repo's AGENTS.md.
#
# Usage:
#   ./install.sh                        # all (default), copy
#   ./install.sh --target=claude        # claude | codex | opencode | antigravity | both (claude+codex) | all
#   ./install.sh --symlink              # symlink skill folders (claude/codex/antigravity); opencode commands are always generated
#   ./install.sh --migrate              # also migrate this repository's .along/ structure
#   ./install.sh --claude-home=DIR --codex-home=DIR --opencode-home=DIR --antigravity-home=DIR
set -euo pipefail

TARGET=all
SYMLINK=0
INSTALL_DEPS=0
MIGRATE=0
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
OPENCODE_HOME="${OPENCODE_HOME:-$HOME/.config/opencode}"
ANTIGRAVITY_HOME="${ANTIGRAVITY_HOME:-$HOME/.gemini/config}"

# Un-namespaced OpenCode commands from before the /along-* prefix. Kept at parity with
# $shortAliases in install.ps1; tests/test_skills_and_scripts.py compares the two.
SHORT_ALIASES=(
  "build" "commit" "context-sync" "dash" "decision-sync" "dep-scan" "dev"
  "graph-check" "history-sync" "init" "issue-sync" "kb-search" "kb-sync"
  "test" "update" "version-bump" "wrap"
)

LEGACY_SKILLS=(
  "init-agents" "update-agents" "dashboard" "repo-dashboard"
  "bump-version" "check-graph" "wrap-session" "wrap-stage"
  "sync-context" "sync-issues" "sync-tasks" "sync-decisions"
  "sync-history" "init-kb" "sync-kb" "sync-wiki" "search-kb" "search-wiki"
  "along-wrap-session" "along-wrap-stage"
  "along-sync-issues" "along-sync-context" "along-sync-decisions" "along-sync-history"
  "along-check-graph" "along-scan-deps" "along-bump-version"
  "along-init-kb" "along-sync-kb" "along-search-kb" "along-context-sync"
)

for arg in "$@"; do
  case "$arg" in
    --target=*)           TARGET="${arg#*=}" ;;
    --symlink)            SYMLINK=1 ;;
    --install-deps)       INSTALL_DEPS=1 ;;
    --migrate)            MIGRATE=1 ;;
    --claude-home=*)      CLAUDE_HOME="${arg#*=}" ;;
    --codex-home=*)       CODEX_HOME="${arg#*=}" ;;
    --opencode-home=*)    OPENCODE_HOME="${arg#*=}" ;;
    --antigravity-home=*) ANTIGRAVITY_HOME="${arg#*=}" ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  if [ "$INSTALL_DEPS" -eq 1 ]; then
    echo "-> Installing 'uv' package & Python version manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
  else
    echo "-> [Note] 'uv' is recommended for automatic Python/MCP tool management."
    echo "   Install uv:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   Or run with: ./install.sh --install-deps"
    echo "   Or use mise: mise install"
  fi
else
  echo "-> 'uv' detected: $(command -v uv)"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
src="$SCRIPT_DIR/skills"
[ -d "$src" ] || { echo "Source skills folder not found: $src" >&2; exit 1; }

do_claude=0; do_codex=0; do_opencode=0; do_antigravity=0
case "$TARGET" in
  claude)      do_claude=1 ;;
  codex)       do_codex=1 ;;
  opencode)    do_opencode=1 ;;
  antigravity) do_antigravity=1 ;;
  both)        do_claude=1; do_codex=1 ;;
  all)         do_claude=1; do_codex=1; do_opencode=1; do_antigravity=1 ;;
  *) echo "invalid --target: $TARGET (claude|codex|opencode|antigravity|both|all)" >&2; exit 1 ;;
esac

purge_legacy_skills() {
  local dst="$1/skills"
  if [ -d "$dst" ]; then
    for leg in "${LEGACY_SKILLS[@]}"; do
      rm -rf "$dst/$leg"
    done
  fi
}

install_skillfolders() {  # $1 = tool home dir; installs SKILL.md folders verbatim
  local dst="$1/skills"
  mkdir -p "$dst"
  purge_legacy_skills "$1"
  echo "-> $dst"
  local d name target
  for d in "$src"/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"; target="$dst/$name"; rm -rf "$target"
    if [ "$SYMLINK" -eq 1 ]; then
      ln -s "$(cd "$d" && pwd)" "$target"; echo "   linked  $name"
    else
      cp -r "${d%/}" "$target"; echo "   copied  $name"
    fi
  done
}

install_rulefolders() {  # $1 = tool home dir; installs the language & platform rule packs
  local rules_src="$SCRIPT_DIR/rules"
  [ -d "$rules_src" ] || return 0
  local dst="$1/rules"
  mkdir -p "$dst"
  # Copied over, not replaced: a tool home may hold rule files the user wrote, and
  # deleting the destination first would take them with it.
  cp -r "$rules_src"/. "$dst/"
  echo "   rules copied -> $dst"
}

install_along_scripts() {
  local along_home="$HOME/.along"
  local along_bin="$along_home/bin"
  mkdir -p "$along_bin"
  local scripts_src="$SCRIPT_DIR/scripts"
  if [ -d "$scripts_src" ]; then
    cp -r "$scripts_src"/*.py "$along_bin/" 2>/dev/null || true
    # The shared package must travel with the engines: they import `alongkit`, and
    # Python resolves it from the running script's own directory. A copy of *.py alone
    # produces a global install where every engine fails on ModuleNotFoundError.
    rm -rf "$along_bin/alongkit"
    cp -r "$scripts_src/alongkit" "$along_bin/alongkit" 2>/dev/null || true
    find "$along_bin/alongkit" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
    echo "-> Along tools installed -> $along_bin"
  fi
  local cfg_file="$along_home/config.json"
  local example_cfg="$SCRIPT_DIR/config/along-config.example.json"
  if [ ! -f "$cfg_file" ] && [ -f "$example_cfg" ]; then
    cp "$example_cfg" "$cfg_file"
    echo "-> Initialized default Along configuration: $cfg_file"
  fi
}

install_opencode() {  # generate flat commands + place along-init helper
  local cmddir="$OPENCODE_HOME/commands"
  local helper="$OPENCODE_HOME/actdim-along"
  local old_helper="$OPENCODE_HOME/actdim-agents"
  mkdir -p "$cmddir" "$helper"
  rm -rf "$old_helper"

  # Clean legacy commands and the un-namespaced short aliases
  for leg in "${LEGACY_SKILLS[@]}"; do
    rm -f "$cmddir/$leg.md"
  done
  for short in "${SHORT_ALIASES[@]}"; do
    rm -f "$cmddir/$short.md"
  done

  local scripts_src="$SCRIPT_DIR/scripts"
  if [ -d "$scripts_src" ]; then
    cp -r "$scripts_src"/*.py "$helper/" 2>/dev/null || true
    # The shared package must travel with the engines: they import `alongkit`, and
    # Python resolves it from the running script's own directory. A copy of *.py alone
    # produces a global install where every engine fails on ModuleNotFoundError.
    rm -rf "$helper/alongkit"
    cp -r "$scripts_src/alongkit" "$helper/alongkit" 2>/dev/null || true
    find "$helper/alongkit" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
  fi
  [ -f "$src/along-init/protocol.md" ] && cp -f "$src/along-init/protocol.md" "$helper/protocol.md"

  local d name sk desc out
  for d in "$src"/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"; sk="$d/SKILL.md"; out="$cmddir/$name.md"
    desc="$(awk 'NR==1&&/^---/{f=1;next} f&&/^---/{exit} f&&/^description:/{sub(/^description:[ ]*/,"");print;exit}' "$sk")"
    {
      echo '---'
      printf 'description: "%s"\n' "$desc"
      echo '---'
      echo
      if [ "$name" = "along-init" ]; then
        echo "> OpenCode: helper files live at \`$helper\`. Where the steps below say \"this skill's folder\", use \`$helper\`."
        echo
      fi
      awk 'c>=2{print} /^---[[:space:]]*$/{c++}' "$sk"
    } > "$out"
    echo "   command $name.md"

  done
}

configure_mcp_server() {  # $1 = target file path
  local file="$1"
  local dir="$(dirname "$file")"
  mkdir -p "$dir"
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "
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
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f'   registered code-review-graph MCP in {path}')
    except Exception as e:
        print(f'   (note: could not write {path}: {e})')
else:
    print(f'   code-review-graph MCP already configured in {path}')
" "$file" 2>/dev/null || true
  fi
}

install_along_scripts

if [ "$do_claude" -eq 1 ]; then
  install_skillfolders "$CLAUDE_HOME"
  install_rulefolders "$CLAUDE_HOME"
  configure_mcp_server "$(dirname "$CLAUDE_HOME")/.claude.json"
  configure_mcp_server "$CLAUDE_HOME/mcp_config.json"
fi
if [ "$do_codex" -eq 1 ]; then
  install_skillfolders "$CODEX_HOME"
  install_rulefolders "$CODEX_HOME"
  configure_mcp_server "$CODEX_HOME/mcp_config.json"
fi
if [ "$do_opencode" -eq 1 ]; then
  install_opencode
  configure_mcp_server "$OPENCODE_HOME/mcp_config.json"
fi
if [ "$do_antigravity" -eq 1 ]; then
  install_skillfolders "$ANTIGRAVITY_HOME"
  install_rulefolders "$ANTIGRAVITY_HOME"
  configure_mcp_server "$ANTIGRAVITY_HOME/mcp_config.json"
fi

# Migrate this repository's protocol structure, only when asked (--migrate). Installing
# used to migrate whatever repository the installer happened to sit in, and the migration
# engine rewrites front-matter, moves entities and deletes legacy directories. See
# [bug--migration-deletes-destination-without-backup].
if [ -d "$SCRIPT_DIR/.along" ] || [ -d "$SCRIPT_DIR/.agents" ]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "-> [Note] python3 not found; skipping the protocol migration."
  elif [ "$MIGRATE" -eq 1 ]; then
    echo "-> Running the Along protocol migration for this repository..."
    python3 "$SCRIPT_DIR/scripts/migrate_protocol.py" "$SCRIPT_DIR" --apply
  else
    echo "-> [Note] This repository carries Along state. Installing does not migrate it."
    echo "   Preview:  python3 scripts/migrate_protocol.py . --dry-run"
    echo "   Apply:    python3 scripts/migrate_protocol.py . --apply   (or re-run the installer with --migrate)"
  fi
fi

echo "Done. Claude/Codex/Antigravity skills register next session as /along-* (/along-init, /along-update, /along-dash, etc.); OpenCode picks up /commands, code-review-graph MCP is configured, and all read AGENTS.md natively."
