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
#   ./install.sh --uninstall            # remove exactly what the install manifest records
#   ./install.sh --claude-home=DIR --codex-home=DIR --opencode-home=DIR --antigravity-home=DIR
set -euo pipefail

TARGET=all
SYMLINK=0
INSTALL_DEPS=0
MIGRATE=0
UNINSTALL=0
INCLUDE_UNVERIFIED_MCP=0
ALONG_HOME="${ALONG_HOME:-$HOME/.along}"
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
    --uninstall)          UNINSTALL=1 ;;
    --include-unverified-mcp) INCLUDE_UNVERIFIED_MCP=1 ;;
    --along-home=*)       ALONG_HOME="${arg#*=}" ;;
    --claude-home=*)      CLAUDE_HOME="${arg#*=}" ;;
    --codex-home=*)       CODEX_HOME="${arg#*=}" ;;
    --opencode-home=*)    OPENCODE_HOME="${arg#*=}" ;;
    --antigravity-home=*) ANTIGRAVITY_HOME="${arg#*=}" ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# The engines this installer delegates to. Everything that has to decide something -
# which MCP configuration file a provider really reads, what a previous install put on
# disk - lives in scripts/, not in a string passed to `python3 -c`. See
# [bug--installer-parity-and-destructive-rules-overwrite].
# `command -v` is not enough on Windows: Git Bash finds the Microsoft Store stub
# `python3.exe`, which is on PATH, is not Python, and exits 49 with an advertisement.
# The candidate has to answer `-V` before it counts as an interpreter.
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -V >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

# Passed to both engines so a run never has to guess where a provider was installed,
# and so a test can point the whole installer at a throwaway directory. A plain array,
# not `mapfile`: macOS still ships bash 3.2, which has no `mapfile`.
HOME_ARGS=(
  --user-home "$(dirname "$CLAUDE_HOME")"
  --along-home "$ALONG_HOME"
  --claude-home "$CLAUDE_HOME"
  --codex-home "$CODEX_HOME"
  --opencode-home "$OPENCODE_HOME"
  --antigravity-home "$ANTIGRAVITY_HOME"
)

if [ "$UNINSTALL" -eq 1 ]; then
  echo "-> Uninstalling Along: removing exactly the files the install manifest records."
  if [ -z "$PYTHON" ]; then
    echo "-> [Error] python3 not found; cannot read the install manifest." >&2
    exit 1
  fi
  "$PYTHON" "$SCRIPT_DIR/scripts/install_manifest.py" uninstall "${HOME_ARGS[@]}"
  echo "Done. Your own files in the provider homes were left untouched."
  exit 0
fi

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
  local along_home="$ALONG_HOME"
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

install_along_scripts

PROVIDER_ARGS=()
if [ "$do_claude" -eq 1 ]; then
  install_skillfolders "$CLAUDE_HOME"
  install_rulefolders "$CLAUDE_HOME"
  PROVIDER_ARGS+=(claude)
fi
if [ "$do_codex" -eq 1 ]; then
  install_skillfolders "$CODEX_HOME"
  install_rulefolders "$CODEX_HOME"
  PROVIDER_ARGS+=(codex)
fi
if [ "$do_opencode" -eq 1 ]; then
  install_opencode
  PROVIDER_ARGS+=(opencode)
fi
if [ "$do_antigravity" -eq 1 ]; then
  install_skillfolders "$ANTIGRAVITY_HOME"
  install_rulefolders "$ANTIGRAVITY_HOME"
  PROVIDER_ARGS+=(antigravity)
fi

# --- MCP registration, once, for the providers actually installed ---
# The installer used to write `code-review-graph` into five files and print a success
# line for each: only ~/.claude.json is read by anything. scripts/configure_mcp.py holds
# the per-provider contract, writes where it is verified, and reports the rest with the
# snippet to add by hand.
echo "-> code-review-graph MCP:"
if [ -n "$PYTHON" ]; then
  mcp_args=()
  for provider in "${PROVIDER_ARGS[@]}"; do mcp_args+=(--provider "$provider"); done
  if [ "$INCLUDE_UNVERIFIED_MCP" -eq 1 ]; then mcp_args+=(--include-unverified); fi
  "$PYTHON" "$SCRIPT_DIR/scripts/configure_mcp.py" "${mcp_args[@]}" \
    --user-home "$(dirname "$CLAUDE_HOME")" --claude-home "$CLAUDE_HOME" \
    --codex-home "$CODEX_HOME" --opencode-home "$OPENCODE_HOME" \
    --antigravity-home "$ANTIGRAVITY_HOME" || true
else
  echo "   (skipped: python3 not found, so no provider configuration was touched)"
fi

# --- Install manifest: what was written, and what a previous install left behind ---
# Nothing here deletes a directory. The manifest names the files Along itself wrote, so
# a superseded one can be removed by name and a file the user wrote is never a candidate.
# It is also what `--uninstall` reads.
if [ -n "$PYTHON" ]; then
  manifest_args=(sync --source "$SCRIPT_DIR")
  for provider in "${PROVIDER_ARGS[@]}"; do manifest_args+=(--target "$provider"); done
  "$PYTHON" "$SCRIPT_DIR/scripts/install_manifest.py" "${manifest_args[@]}" \
    "${HOME_ARGS[@]}" || true
else
  echo "-> [Note] python3 not found; no install manifest was written."
  echo "   Run later:  python3 scripts/install_manifest.py sync --source ."
fi

# Migrate this repository's protocol structure, only when asked (--migrate). Installing
# used to migrate whatever repository the installer happened to sit in, and the migration
# engine rewrites front-matter, moves entities and deletes legacy directories. See
# [bug--migration-deletes-destination-without-backup].
if [ -d "$SCRIPT_DIR/.along" ] || [ -d "$SCRIPT_DIR/.agents" ]; then
  if [ -z "$PYTHON" ]; then
    echo "-> [Note] python3 not found; skipping the protocol migration."
  elif [ "$MIGRATE" -eq 1 ]; then
    echo "-> Running the Along protocol migration for this repository..."
    "$PYTHON" "$SCRIPT_DIR/scripts/migrate_protocol.py" "$SCRIPT_DIR" --apply
  else
    echo "-> [Note] This repository carries Along state. Installing does not migrate it."
    echo "   Preview:  python3 scripts/migrate_protocol.py . --dry-run"
    echo "   Apply:    python3 scripts/migrate_protocol.py . --apply   (or re-run the installer with --migrate)"
  fi
fi

echo "Done. Claude/Codex/Antigravity skills register next session as /along-* (/along-init, /along-update, /along-dash, etc.); OpenCode picks up /commands, and all read AGENTS.md natively."
echo "     MCP registration is reported per provider above: only a verified configuration contract is written to."
echo "     To remove Along again: ./install.sh --uninstall  (removes only what the manifest records)."
