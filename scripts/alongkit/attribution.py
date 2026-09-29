#!/usr/bin/env python3
"""
alongkit.attribution - Keep AI co-author trailers out of commits.

Agent runtimes append `Co-Authored-By:` trailers to the commits they create
(Claude Code: `Claude ... <noreply@anthropic.com>`, Antigravity:
`Antigravity (Gemini) <noreply@google.com>`). GitHub resolves the trailer email to
an account and lists the vendor as a repository contributor; the only way to undo
it afterwards is a history rewrite and a force-push. See
`[feat--suppress-ai-coauthor-attribution]`.

Three layers share this module:
- `apply_claude_attribution` / `apply_cursor_attribution` - written into the runtime
  config by `along hook install`, so the runtime never adds the trailer. Codex and
  Antigravity document no such key; for them the gate below is the only layer.
- `find_ai_coauthor` - the runtime-agnostic `commit_no_ai_coauthor` gate.
- `strip_ai_coauthor_trailers` - `/along-commit` cleans its own message.

Human co-authors are left alone. Opt-out for a repository:
`.along/config.json` -> `{"commits": {"allow_ai_coauthor": true}}`.
"""


from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )


import json
import os
import re
from typing import Any, Dict, Optional

from . import repo, textio


#: Names and addresses that identify an AI agent rather than a person.
AI_IDENTITY_RE = re.compile(
    r"(?i)anthropic|claude|openai|codex|chatgpt|gemini|antigravity|copilot|"
    r"cursor(?:agent)?|devin|aider|windsurf|codeium|noreply@google\.com"
)

#: A trailer inside free text (a shell command line). Stops at a newline or quote.
_TRAILER_IN_TEXT_RE = re.compile(r"(?i)Co-Authored-By:[^\n\"']*")

#: A trailer as its own line of a commit message.
_TRAILER_LINE_RE = re.compile(r"(?i)^[ \t]*Co-Authored-By:")

#: Claude Code settings that suppress the commit trailer. `attribution.commit` is the
#: current key (an empty string hides the trailer); `includeCoAuthoredBy` is the legacy
#: one, read only when `attribution` is absent, kept for older versions.
CLAUDE_COMMIT_ATTRIBUTION = ""
CLAUDE_LEGACY_KEY = "includeCoAuthoredBy"


def is_ai_coauthor_line(line: str) -> bool:
    """True if `line` is a `Co-Authored-By:` trailer naming an AI agent."""
    return bool(_TRAILER_LINE_RE.match(line) and AI_IDENTITY_RE.search(line))


def find_ai_coauthor(text: str) -> Optional[str]:
    """First AI co-author trailer found anywhere in `text`, or None."""
    for match in _TRAILER_IN_TEXT_RE.finditer(text or ""):
        trailer = match.group(0).strip()
        if AI_IDENTITY_RE.search(trailer):
            return trailer
    return None


def strip_ai_coauthor_trailers(message: str) -> str:
    """Remove AI co-author trailer lines, keeping human ones and the message body."""
    lines = message.splitlines()
    kept = [line for line in lines if not is_ai_coauthor_line(line)]
    if len(kept) == len(lines):
        return message
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept) + ("\n" if message.endswith("\n") else "")


def allow_ai_coauthor(repo_root: Optional[str]) -> bool:
    """Repository opt-out: `.along/config.json` `commits.allow_ai_coauthor`."""
    if not repo_root:
        return False
    config_path = os.path.join(repo.state_dir(repo_root), "config.json")
    if not os.path.isfile(config_path):
        return False
    try:
        data = json.loads(textio.read_text(config_path, strict=False))
    except (OSError, ValueError):
        return False
    commits = data.get("commits") if isinstance(data, dict) else None
    return isinstance(commits, dict) and commits.get("allow_ai_coauthor") is True


def apply_claude_attribution(settings: Dict[str, Any]) -> bool:
    """Set Claude Code commit attribution off in `settings`; True if anything changed.

    Only the commit side is touched: `attribution.pr` and every other key are kept.
    """
    changed = False
    attribution = settings.get("attribution")
    if not isinstance(attribution, dict):
        attribution = {}
        settings["attribution"] = attribution
        changed = True
    if attribution.get("commit") != CLAUDE_COMMIT_ATTRIBUTION:
        attribution["commit"] = CLAUDE_COMMIT_ATTRIBUTION
        changed = True
    if settings.get(CLAUDE_LEGACY_KEY) is not False:
        settings[CLAUDE_LEGACY_KEY] = False
        changed = True
    return changed


def apply_cursor_attribution(cli_config: Dict[str, Any]) -> bool:
    """Set `attribution.attributeCommitsToAgent = false` in Cursor `cli-config.json`."""
    changed = False
    attribution = cli_config.get("attribution")
    if not isinstance(attribution, dict):
        attribution = {}
        cli_config["attribution"] = attribution
        changed = True
    if attribution.get("attributeCommitsToAgent") is not False:
        attribution["attributeCommitsToAgent"] = False
        changed = True
    return changed
