#!/usr/bin/env python3
"""
alongkit.entities.vocabulary - Vocabulary, constants, slug/key rules, and agent detection.
[debt--split-along-exec-and-entities]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import os
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

#: `spike` is a timeboxed experiment with an `## Outcome` section; it replaced the separate
#: SPIKES/ entity [debt--entity-model-slimming].
ISSUE_TYPES: tuple = ("feat", "bug", "debt", "task", "docs", "spike")
#: Regex alternation of the issue types, for patterns matching `<type>--<slug>` names.
ISSUE_TYPE_ALTERNATION: str = "(?:" + "|".join(ISSUE_TYPES) + ")"
ISSUE_STATUSES: tuple = (
    "open",
    "in-progress",
    "blocked",
    "done",
    "superseded",
    "cancelled",
    "duplicate",
)
CLOSED_ISSUE_STATUSES: tuple = ("done", "superseded", "cancelled", "duplicate")
DELIVERED_ISSUE_STATUSES: tuple = ("done",)
PRIORITIES: tuple = ("critical", "high", "medium", "low")

MILESTONE_STATUSES: tuple = ("open", "in-progress", "completed")
DECISION_STATUSES: tuple = ("accepted", "superseded", "retired", "proposed", "rejected", "deprecated", "active")
ACTIVE_DECISION_STATUSES: tuple = ("accepted", "active")

DONE_REQUIRED_FIELDS: tuple = ("status", "completed")

ENTITY_DIRS: Dict[str, str] = {
    "issue": "ISSUES",
    "session": "SESSIONS",
    "milestone": "MILESTONES",
    "decision": "DECISIONS",
}

#: Entity folders of the protocol before [debt--entity-model-slimming]. Migration Step 16
#: converts their records; nothing else reads them.
LEGACY_ENTITY_DIRS: Tuple[str, ...] = ("RISKS", "SPIKES", "CHECKLISTS")

REFERENCE_FIELDS: Tuple[str, ...] = ("related", "blocked_by", "parent", "superseded_by", "duplicate_of")
MILESTONE_REFERENCE_FIELDS: Tuple[str, ...] = ("target_issues",)
SESSION_REFERENCE_FIELDS: Tuple[str, ...] = ("issues_advanced", "issues_completed")

RECENT_DONE_LIMIT: int = 5
ROOT_QUALIFIER: str = "root"

BUG_KEYWORDS: tuple = (
    "fix", "bug", "issue", "leak", "crash", "error", "fail", "failure",
    "broken", "regression", "hang", "deadlock", "race", "flaky",
)
DEBT_KEYWORDS: tuple = (
    "debt", "refactor", "cleanup", "clean", "audit", "tidy", "deprecate",
    "prune", "dedup", "unify", "reorganize", "sanitize", "migrate", "parity",
)
DOCS_KEYWORDS: tuple = (
    "doc", "docs", "readme", "guide", "manual", "documentation",
)


def today_iso() -> str:
    """Today as YYYY-MM-DD. Windows-safe in filenames, sortable, and unambiguous."""
    return date.today().strftime("%Y-%m-%d")


def is_iso_date(value: str) -> bool:
    """True when value is a YYYY-MM-DD calendar date."""
    try:
        datetime.strptime(str(value).strip(), "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def slugify(text: str, max_words: int = 5) -> str:
    """Lowercase kebab-case slug, as the protocol requires for every entity."""
    lowered = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if not lowered:
        return "untitled"
    words = [word for word in lowered.split("-") if word]
    return "-".join(words[:max_words]) if max_words else "-".join(words)


def is_valid_slug(slug: str, min_words: int = 2, max_words: int = 5) -> bool:
    """True when slug is lowercase kebab-case within word count bounds [min_words, max_words]."""
    if not isinstance(slug, str) or not slug:
        return False
    slug = slug.strip()
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", slug):
        return False
    words = slug.split("-")
    if min_words is not None and len(words) < min_words:
        return False
    if max_words is not None and len(words) > max_words:
        return False
    return True


def canonical_key(entity_type: Optional[str], slug: str) -> str:
    """<type>--<slug> when a type is known, otherwise the bare slug."""
    slug = slug.strip()
    if not entity_type:
        return slug
    prefix = f"{entity_type}--"
    return slug if slug.startswith(prefix) else prefix + slug


def parse_key(key: str) -> Tuple[Optional[str], str]:
    """Split a canonical key into (type, slug); type is None for a bare slug."""
    cleaned = key.strip().strip("[]")
    if "--" in cleaned:
        head, tail = cleaned.split("--", 1)
        if head in ISSUE_TYPES:
            return head, tail
    return None, cleaned


def issue_filename(entity_type: str, slug: str) -> str:
    """File name of an issue entity: <type>--<slug>.md."""
    return f"{canonical_key(entity_type, slug)}.md"


def session_filename(day: str, slug: str) -> str:
    """File name of a session log: date first, so a directory listing sorts by time."""
    return f"{day}--{slug}.md"


def infer_issue_type(text: str) -> str:
    """Infer the most appropriate issue type from title, slug, or description."""
    words = set(re.findall(r"[a-z0-9]+", str(text).lower()))
    if any(k in words for k in BUG_KEYWORDS):
        return "bug"
    if any(k in words for k in DEBT_KEYWORDS):
        return "debt"
    if any(k in words for k in DOCS_KEYWORDS):
        return "docs"
    return "feat"


def detect_agent(explicit: Optional[str] = None) -> str:
    """Infer the executing agent tool/model name at runtime."""
    if explicit:
        return explicit.strip()

    env = os.environ
    if env.get("ALONG_AGENT"):
        return env["ALONG_AGENT"].strip()
    if env.get("AGENT"):
        val = env["AGENT"].strip()
        if val:
            return val

    from .. import runtime
    if runtime.is_cowork_env(env):
        return "cowork"

    if any(k in env for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                              "CLAUDE_CODE", "CLAUDE_PROJECT_DIR", "CLAUDE_CONVERSATION_ID", "ANTHROPIC_CLI")):
        return "claude-code"

    if any(k in env for k in ("ANTIGRAVITY_AGENT", "ANTIGRAVITY_CONVERSATION_ID", "ANTIGRAVITY_PROJECT_ID")):
        return "antigravity"

    if any(k in env for k in ("CODEX_CLI", "OPENAI_CODEX")):
        return "codex"

    if any(k in env for k in ("OPENCODE_CLI", "OPENCODE_AGENT")):
        return "opencode"

    return "unknown"
