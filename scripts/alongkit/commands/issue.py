#!/usr/bin/env python3
"""
alongkit.commands.issue - Modular CLI command router for along issue.
[debt--along-exec-argparse-migration]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import argparse
from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List

from alongkit import entities, frontmatter, gates, lifecycle, repo, session, textio, transaction
from alongkit.version import CURRENT_PROTOCOL_VERSION
from .common import check_unknown_args, require_entity_name

RECENT_DONE_LIMIT = entities.RECENT_DONE_LIMIT


def _report_rewritten(repo_root: str, paths: List[str]):
    if not paths:
        print("-> No inbound references to rewrite.")
        return
    print(f"-> Rewrote inbound references in {len(paths)} file(s):")
    for path in paths:
        print(f"   - {repo.normalize_posix(repo.safe_relpath(path, repo_root))}")


def _issue_create(repo_root: str, args: List[str], issues_dir: str, today: str):
    if len(args) < 3:
        print("[Error] Usage: along_exec.py issue create <type> <slug> --title \"Title\" [--priority high|medium|low] [--tags \"tag1,tag2\"] [--agent <name>] [--milestone <name>]", file=sys.stderr)
        sys.exit(1)
    itype = args[1].lower()
    if itype not in entities.ISSUE_TYPES:
        print(f"[Error] Invalid issue type '{itype}'. Allowed types: {', '.join(entities.ISSUE_TYPES)}", file=sys.stderr)
        sys.exit(1)

    require_entity_name(args[2].lower(), "along issue create <type> <slug> --title \"Title\"")

    parser = argparse.ArgumentParser(prog="along issue create", allow_abbrev=False)
    parser.add_argument("type")
    parser.add_argument("slug")
    parser.add_argument("--title", "-t", default=None)
    parser.add_argument("--priority", "-p", default="medium")
    parser.add_argument("--tags", default=None)
    parser.add_argument("--agent", "-a", default=None)
    parser.add_argument("--milestone", "-m", default=None)
    parser.add_argument("--no-milestone", action="store_true")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue create")

    islug = parsed.slug.lower()
    if not entities.is_valid_slug(islug):
        print(f"[Error] Invalid issue slug '{islug}'. Slug must be 2-5 lowercase kebab-case words (e.g. my-feature-name).", file=sys.stderr)
        sys.exit(1)

    existing_issue = entities.find_issue_by_slug(repo_root, islug)
    if existing_issue:
        rel_existing = repo.safe_relpath(existing_issue["file_path"], repo_root)
        print(f"[Error] An issue with slug '{islug}' already exists: {rel_existing}", file=sys.stderr)
        sys.exit(1)

    title = parsed.title or islug.replace("-", " ").capitalize()
    priority = parsed.priority.lower()
    if priority not in entities.PRIORITIES:
        print(f"[Error] Invalid priority '{priority}'. Allowed priorities: {', '.join(entities.PRIORITIES)}", file=sys.stderr)
        sys.exit(1)

    tags = [t.strip() for t in parsed.tags.split(",") if t.strip()] if parsed.tags else []
    agent = entities.detect_agent(parsed.agent)

    milestone = None
    if parsed.no_milestone:
        milestone = None
    elif parsed.milestone:
        if parsed.milestone.lower() in ("none", "null", "~", ""):
            milestone = None
        else:
            clean_m = parsed.milestone[:-3] if parsed.milestone.endswith(".md") else parsed.milestone
            m_path = os.path.join(repo_root, ".along", "MILESTONES", f"{clean_m}.md")
            if not os.path.exists(m_path):
                print(f"[Error] Milestone '{parsed.milestone}' does not exist in .along/MILESTONES/.", file=sys.stderr)
                sys.exit(1)
            milestone = clean_m
    else:
        milestone = entities.resolve_in_progress_milestone(repo_root)

    inferred = entities.infer_issue_type(f"{islug} {title}")
    if itype == "feat" and inferred in ("bug", "debt"):
        print(f"-> [Notice] Title/slug matches {inferred} keywords. Consider using type '{inferred}' instead of 'feat'.")

    milestone_line = f"milestone: {milestone}\n" if milestone else ""
    target_file = os.path.join(issues_dir, f"{itype}--{islug}.md")
    tags_str = f"[{', '.join(tags)}]" if tags else "[]"
    content = f"""---
protocol: along
protocol_version: "{CURRENT_PROTOCOL_VERSION}"
slug: {islug}
type: {itype}
status: open
priority: {priority}
created: {today}
updated: {today}
agent: {agent}
tags: {tags_str}
{milestone_line}blocked_by: []
related: []
---

# {title}

Describe the feature, requirements, and background context here.

## Acceptance Criteria
- [ ] Task requirement 1
- [ ] Automated tests passing
"""
    textio.write_text(target_file, content, newline="\n", atomic=True)
    print(f"-> Created issue: {target_file}")

    if milestone:
        try:
            entities.sync_milestones(repo_root, milestone)
            print(f"-> Synchronized milestone {milestone}.")
        except ValueError:
            pass

    issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
    if os.path.exists(issues_board):
        entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
        print("-> Updated .along/ISSUES.md")
    sys.exit(0)


def _issue_done(repo_root: str, args: List[str], issues_dir: str, done_dir: str, today: str):
    if len(args) < 2:
        print("[Error] Usage: along_exec.py issue done <slug> [--status done|superseded|cancelled|duplicate] [--superseded-by <key>] [--duplicate-of <key>]", file=sys.stderr)
        sys.exit(1)
    require_entity_name(args[1].lower(), "along issue done|cancel <slug> [--status ...]")

    parser = argparse.ArgumentParser(prog="along issue done", allow_abbrev=False)
    parser.add_argument("slug")
    parser.add_argument("--status", "-s", default="done")
    parser.add_argument("--superseded-by", default=None)
    parser.add_argument("--duplicate-of", default=None)
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue done")

    islug = parsed.slug.lower()
    target_status = parsed.status.lower()
    superseded_by = parsed.superseded_by.strip() if parsed.superseded_by else None
    duplicate_of = parsed.duplicate_of.strip() if parsed.duplicate_of else None

    if target_status not in entities.CLOSED_ISSUE_STATUSES:
        print(f"[Error] Invalid closing status '{target_status}'. Allowed statuses: {', '.join(entities.CLOSED_ISSUE_STATUSES)}", file=sys.stderr)
        sys.exit(1)

    found_file = None
    for f in os.listdir(issues_dir):
        if f.endswith(f"--{islug}.md") and os.path.isfile(os.path.join(issues_dir, f)):
            found_file = os.path.join(issues_dir, f)
            break

    if not found_file:
        print(f"[Error] Issue '{islug}' not found in {issues_dir}", file=sys.stderr)
        sys.exit(1)

    filename = os.path.basename(found_file)
    dest_file = os.path.join(done_dir, filename)
    content = textio.read_text(found_file)

    if not frontmatter.has_frontmatter(content):
        print(
            f"[Error] {filename} has no parseable YAML front-matter. "
            "Refusing to close it silently: fix the entity header, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)

    if content.startswith("\ufeff"):
        content = content.lstrip("\ufeff")
        print(
            f"-> [Notice] Normalized a UTF-8 BOM in {filename}. "
            "The protocol requires BOM-free UTF-8. To avoid producing one: PowerShell 7+ "
            "has -Encoding utf8NoBOM; Windows PowerShell 5.1 has no such value, so use "
            "[IO.File]::WriteAllText(path, text, (New-Object System.Text.UTF8Encoding($false)))."
        )

    if target_status in entities.DELIVERED_ISSUE_STATUSES:
        comp_ok, comp_reasons = entities.validate_issue_completion(content, target_status)
        if not comp_ok:
            print(
                f"[Error] Cannot close issue '{islug}' as {target_status}:\n"
                + "\n".join(f"  - {r}" for r in comp_reasons)
                + f"\n  Update '{repo.safe_relpath(found_file, repo_root)}' before marking it done, "
                + "or cancel with '--status cancelled'.",
                file=sys.stderr,
            )
            sys.exit(2)

    updates = {"status": target_status, "updated": today, "completed": today}
    if superseded_by:
        updates["superseded_by"] = superseded_by
    if duplicate_of:
        updates["duplicate_of"] = duplicate_of

    content = frontmatter.update(
        content,
        updates,
        place_after={"completed": "status"},
    )

    block = frontmatter.split(content)
    if block:
        sibling_link_re = re.compile(
            r'(\[[^\]]+\]\()(?:\./)?(?<!\.\./)((?:feat|bug|debt|task|docs)--[a-z0-9-]+\.md\b)'
        )
        body_lines = block.body.splitlines(keepends=True)
        adjusted_body_lines = []
        in_fence = False
        for line in body_lines:
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                adjusted_body_lines.append(line)
                continue
            if in_fence:
                adjusted_body_lines.append(line)
                continue
            adjusted_body_lines.append(sibling_link_re.sub(r'\1../\2', line))
        content = block.open_delim + block.raw + block.close_delim + "".join(adjusted_body_lines)

    _itype, bare_slug = entities.parse_key(filename[:-3])
    has_blackboard = session.load_state(repo_root, bare_slug) is not None
    if has_blackboard:
        unrecorded = session.unrecorded_files(repo_root, bare_slug)
        if unrecorded:
            print(f"[Error] issue done failed: blackboard '{bare_slug}' contains unknown non-scaffold file(s):", file=sys.stderr)
            for f in unrecorded:
                print(f"  - {f}", file=sys.stderr)
            sys.exit(2)
    tx = transaction.FileTransaction(repo_root, label=f"issue-done-{bare_slug}")
    try:
        tx.protect(found_file)
        tx.protect(dest_file)
        textio.write_text(dest_file, content, newline="\n", atomic=True)
        os.remove(found_file)
        print(f"-> Moved issue to done: {dest_file}")

        if has_blackboard:
            session.append_trace(repo_root, bare_slug, "archived by issue done")
        if has_blackboard or target_status == "done":
            log_path = lifecycle.write_session_record(
                repo_root, tx, bare_slug, today=today, completed=(target_status == "done"))
            print(f"-> Recorded in session log: {repo.safe_relpath(log_path, repo_root)}")

        issues_board = os.path.join(repo_root, ".along", "ISSUES.md")
        if os.path.exists(issues_board):
            tx.protect(issues_board)
            entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
            print("-> Updated .along/ISSUES.md")
        tx.commit()
    except (OSError, ValueError, frontmatter.FrontmatterError) as exc:
        print(f"[Error] issue done failed: {exc}", file=sys.stderr)
        tx.rollback()
        sys.exit(1)
    if has_blackboard and lifecycle.purge_archived(repo_root, bare_slug, complete=True):
        print(f"-> Purged session blackboard: .along/.session/{bare_slug}")
    sys.exit(0)


def _issue_reopen(repo_root: str, args: List[str], issues_dir: str, done_dir: str, today: str):
    if len(args) < 2 or args[1].startswith("-"):
        print("[Error] Usage: along issue reopen <slug>", file=sys.stderr)
        sys.exit(1)
    parser = argparse.ArgumentParser(prog="along issue reopen", allow_abbrev=False)
    parser.add_argument("slug")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue reopen")

    _itype, islug = entities.parse_key(parsed.slug.lower())
    if any(f.endswith(f"--{islug}.md") for f in os.listdir(issues_dir) if os.path.isfile(os.path.join(issues_dir, f))):
        print(f"[Error] Issue '{islug}' is already open in {issues_dir}.", file=sys.stderr)
        sys.exit(1)
    found = next((os.path.join(done_dir, f) for f in sorted(os.listdir(done_dir))
                  if f.endswith(f"--{islug}.md")), None) if os.path.isdir(done_dir) else None
    if not found:
        print(f"[Error] Issue '{islug}' not found in {done_dir}", file=sys.stderr)
        sys.exit(1)
    dest = os.path.join(issues_dir, os.path.basename(found))
    content = textio.read_text(found)
    if not frontmatter.has_frontmatter(content):
        print(f"[Error] {os.path.basename(found)} has no parseable YAML front-matter.", file=sys.stderr)
        sys.exit(1)
    content = frontmatter.update(content, {"status": "open", "updated": today},
                                 remove=("completed", "superseded_by", "duplicate_of"))
    block = frontmatter.split(content)
    if block:
        back = re.compile(r'(\[[^\]]+\]\()\.\./((?:feat|bug|debt|task|docs)--[a-z0-9-]+\.md\b)')
        body, in_fence = [], False
        for line in block.body.splitlines(keepends=True):
            if line.strip().startswith(("```", "~~~")):
                in_fence = not in_fence
            body.append(line if in_fence else back.sub(r"\1\2", line))
        content = block.bom + block.open_delim + block.raw + block.close_delim + "".join(body)
    tx = transaction.FileTransaction(repo_root, label=f"issue-reopen-{islug}")
    try:
        tx.protect(found)
        tx.protect(dest)
        textio.write_text(dest, content, newline="\n", atomic=True)
        os.remove(found)
        board = os.path.join(repo.state_dir(repo_root), "ISSUES.md")
        if os.path.exists(board):
            tx.protect(board)
            entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
        tx.commit()
    except (OSError, ValueError, frontmatter.FrontmatterError) as exc:
        print(f"[Error] issue reopen failed: {exc}", file=sys.stderr)
        tx.rollback()
        sys.exit(1)
    print(f"-> Reopened {repo.safe_relpath(dest, repo_root)} (status: open). Resume with 'along start {islug}'.")
    sys.exit(0)


def _issue_sync(repo_root: str, args: List[str]):
    parser = argparse.ArgumentParser(prog="along issue sync", allow_abbrev=False)
    _parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue sync")

    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
    print(f"-> Recompiled .along/ISSUES.md projection (capped to {RECENT_DONE_LIMIT} recent completed issues).")
    for key, parent, owner in entities.cross_context_parents(repo_root):
        print(f"   {key}: parent {parent} (found in {repo.safe_relpath(owner, repo_root) or owner})")
    if not gates.entity_integrity_gate(repo_root, "Issue Sync"):
        sys.exit(1)
    sys.exit(0)


def _issue_rename(repo_root: str, args: List[str]):
    if len(args) < 3:
        print("[Error] Usage: along issue rename <old-key> <new-key>", file=sys.stderr)
        sys.exit(1)
    for name in args[1:3]:
        require_entity_name(name, "along issue rename <old-key> <new-key>")
    parser = argparse.ArgumentParser(prog="along issue rename", allow_abbrev=False)
    parser.add_argument("old_key")
    parser.add_argument("new_key")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue rename")

    try:
        result = entities.rename_issue(repo_root, parsed.old_key.lower(), parsed.new_key.lower())
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"-> Renamed {result['old_key']} -> {result['new_key']}: "
          f"{repo.normalize_posix(repo.safe_relpath(result['file_path'], repo_root))}")
    _report_rewritten(repo_root, result["rewritten"])
    sys.exit(0)


def _issue_supersede(repo_root: str, args: List[str]):
    if len(args) < 2 or args[1].startswith("-"):
        print("[Error] Usage: along issue supersede <old-key> --by <new-key>[,<new-key>...]", file=sys.stderr)
        sys.exit(1)
    require_entity_name(args[1].lower(), "along issue supersede <old-key> --by <new-key>[,<new-key>...]")

    parser = argparse.ArgumentParser(prog="along issue supersede", allow_abbrev=False)
    parser.add_argument("old_key")
    parser.add_argument("--by", default=None)
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue supersede")

    if not parsed.by:
        print("[Error] Usage: along issue supersede <old-key> --by <new-key>[,<new-key>...]", file=sys.stderr)
        sys.exit(1)

    try:
        by_keys = [k.strip() for k in parsed.by.lower().split(",") if k.strip()]
        result = entities.supersede_issue(repo_root, parsed.old_key.lower(), by_keys if len(by_keys) > 1 else parsed.by.lower())
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)
    by_display = ", ".join(result["new_key"]) if isinstance(result["new_key"], list) else result["new_key"]
    print(f"-> Superseded {result['old_key']} by {by_display}: "
          f"{repo.normalize_posix(repo.safe_relpath(result['file_path'], repo_root))}")
    _report_rewritten(repo_root, result["rewritten"])
    sys.exit(0)


def _issue_delete(repo_root: str, args: List[str]):
    if len(args) < 2:
        print("[Error] Usage: along issue delete <slug>", file=sys.stderr)
        sys.exit(1)
    slug = require_entity_name(args[1].lower(), "along issue delete <slug>")
    parser = argparse.ArgumentParser(prog="along issue delete", allow_abbrev=False)
    parser.add_argument("slug")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue delete")

    try:
        result = entities.delete_issue(repo_root, parsed.slug.lower())
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"-> Deleted {result['key']}: {repo.normalize_posix(repo.safe_relpath(result['file_path'], repo_root))}")
    _report_rewritten(repo_root, result["rewritten"])
    sys.exit(0)


def _issue_list(repo_root: str, issues_dir: str, args: List[str]):
    parser = argparse.ArgumentParser(prog="along issue list", allow_abbrev=False)
    parser.add_argument("--compact", "-c", action="store_true")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue list")

    if parsed.compact:
        issues = sorted(entities.scan_issues(repo_root), key=lambda x: (x.get("status") != "in-progress", x["slug"]))
        print(f"=== Active Backlog Digest ({len(issues)} open/in-progress issues) ===")
        for iss in issues:
            key = entities.canonical_key(iss["type"], iss["slug"])
            status = iss.get("status", "open")
            prio = iss.get("priority", "medium")
            title = (iss.get("frontmatter") or {}).get("title") or iss["slug"].replace("-", " ").capitalize()
            print(f"- {key} [{status}|{prio}] {title}")
        sys.exit(0)
    print(f"-> Active issues in {issues_dir}:")
    count = 0
    for f in os.listdir(issues_dir):
        if f.endswith(".md") and os.path.isfile(os.path.join(issues_dir, f)):
            print(f"   - {f}")
            count += 1
    print(f"Total active issues: {count}")
    sys.exit(0)


def _issue_update(repo_root: str, args: List[str], today: str):
    if len(args) < 2:
        print("[Error] Usage: along issue update <slug> [--milestone <name>] [--priority <high|medium|low>] [--status <status>] [--tags <t1,t2>] [--title <title>]", file=sys.stderr)
    require_entity_name(args[1].lower(), "along issue update <slug> [--milestone <name>] [--priority <high|medium|low>] [--status <status>] [--tags <t1,t2>] [--title <title>]")

    parser = argparse.ArgumentParser(prog="along issue update", allow_abbrev=False)
    parser.add_argument("slug")
    parser.add_argument("--milestone", "-m", default=None)
    parser.add_argument("--priority", "-p", default=None)
    parser.add_argument("--status", "-s", default=None)
    parser.add_argument("--tags", default=None)
    parser.add_argument("--title", "-t", default=None)
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue update")

    raw_slug = parsed.slug.lower()
    issue = entities.find_issue_by_slug(repo_root, raw_slug)
    if not issue:
        print(f"[Error] Issue '{raw_slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

    updates: Dict[str, Any] = {"updated": today}
    milestone_updated = False
    target_milestone_slug = None

    if parsed.milestone is not None:
        val = parsed.milestone
        if val in ("~", "none", "null", ""):
            updates["milestone"] = None
        else:
            m_resolved = entities.resolve_milestone_by_query(repo_root, val)
            if not m_resolved:
                print(f"[Error] Milestone '{val}' not found or ambiguous in .along/MILESTONES/.", file=sys.stderr)
                sys.exit(1)
            updates["milestone"] = m_resolved["slug"]
            target_milestone_slug = m_resolved["slug"]
        milestone_updated = True

    if parsed.priority is not None:
        pval = parsed.priority.lower()
        if pval not in entities.PRIORITIES:
            print(f"[Error] Invalid priority '{pval}'. Allowed: {', '.join(entities.PRIORITIES)}", file=sys.stderr)
            sys.exit(1)
        updates["priority"] = pval

    if parsed.status is not None:
        sval = parsed.status.lower()
        if sval not in entities.ISSUE_STATUSES:
            print(f"[Error] Invalid status '{sval}'. Allowed: {', '.join(entities.ISSUE_STATUSES)}", file=sys.stderr)
            sys.exit(1)
        updates["status"] = sval

    if parsed.tags is not None:
        updates["tags"] = [t.strip() for t in parsed.tags.split(",") if t.strip()]

    if parsed.title is not None:
        updates["title"] = parsed.title

    fpath, new_fm = entities.update_issue_frontmatter(repo_root, issue["slug"], updates)
    rel_path = repo.normalize_posix(repo.safe_relpath(fpath, repo_root))
    print(f"-> Updated issue {issue['slug']}: {rel_path}")
    for k, v in updates.items():
        if k != "updated":
            print(f"   {k}: {v}")

    if milestone_updated:
        old_m = issue["frontmatter"].get("milestone")
        if old_m and old_m != target_milestone_slug:
            try:
                entities.sync_milestones(repo_root, old_m)
            except ValueError:
                pass
        if target_milestone_slug:
            try:
                entities.sync_milestones(repo_root, target_milestone_slug)
            except ValueError:
                pass
        print("-> Synchronized affected milestone(s).")

    entities.sync_issues_board(repo_root, recent_done_limit=RECENT_DONE_LIMIT)
    sys.exit(0)


def _issue_show(repo_root: str, args: List[str]):
    if len(args) < 2:
        print("[Error] Usage: along issue show <slug> [--json]", file=sys.stderr)
        sys.exit(1)
    parser = argparse.ArgumentParser(prog="along issue show", allow_abbrev=False)
    parser.add_argument("slug")
    parser.add_argument("--json", action="store_true")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue show")

    raw_slug = parsed.slug.lower()
    summary = entities.get_issue_summary(repo_root, raw_slug)
    if not summary:
        print(f"[Error] Issue '{raw_slug}' not found in .along/ISSUES/.", file=sys.stderr)
        sys.exit(1)

    if parsed.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"=== Issue: {summary['slug']} ({summary['type']}) ===")
        print(f"Title:     {summary['title']}")
        print(f"Status:    {summary['status']}")
        print(f"Priority:  {summary['priority']}")
        print(f"Milestone: {summary.get('milestone') or 'none'}")
        print(f"Agent:     {summary.get('agent') or 'unknown'}")
        print(f"Tags:      {', '.join(summary.get('tags') or [])}")
        requires = summary.get("requires")
        if requires:
            if isinstance(requires, dict):
                req_parts = []
                for d in requires.get("decisions", []) or []:
                    req_parts.append(f"ADR:{d}")
                for doc in requires.get("docs", []) or []:
                    req_parts.append(f"docs:{doc}")
                print(f"Requires:  {', '.join(req_parts)}")
            else:
                print(f"Requires:  {requires}")
        print(f"Path:      {summary['file_path']}")
        if summary.get("body"):
            print("\n--- Summary / Body ---")
            lines = summary["body"].splitlines()
            preview = lines[:25]
            print("\n".join(preview))
            if len(lines) > 25:
                print(f"... ({len(lines) - 25} more lines)")
    sys.exit(0)


def _issue_lint(repo_root: str, args: List[str]):
    parser = argparse.ArgumentParser(prog="along issue lint", allow_abbrev=False)
    parser.add_argument("--strict", action="store_true")
    parsed, extra = parser.parse_known_args(args[1:])
    check_unknown_args(extra, "along issue lint")

    strict = parsed.strict
    report = entities.lint_issues(repo_root, strict=strict)
    print(f"=== Along Issue Structural Section Lint ({report['scanned']} issues scanned) ===")
    if report["clean"]:
        print("[OK] All active issues satisfy structural section contracts (Problem, Requirements/Architecture, Acceptance Criteria).")
        sys.exit(0)
    print(f"[WARN] Found {len(report['findings'])} issue(s) with missing mandatory sections:")
    for item in report["findings"]:
        print(f"  - {item['path']}: missing {', '.join(item['missing'])}")
    sys.exit(1 if strict else 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="along issue",
        description="Issue lifecycle management.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="subcmd")

    p_create = sub.add_parser("create", help="Create a new issue")
    p_create.add_argument("type", choices=list(entities.ISSUE_TYPES), help="Issue type")
    p_create.add_argument("slug", help="Issue slug (kebab-case)")
    p_create.add_argument("--title", "-t", default=None, help="Issue title")
    p_create.add_argument("--priority", "-p", default="medium", choices=list(entities.PRIORITIES), help="Issue priority")
    p_create.add_argument("--tags", default=None, help="Comma-separated tags")
    p_create.add_argument("--agent", "-a", default=None, help="Assigned agent")
    p_create.add_argument("--milestone", "-m", default=None, help="Assigned milestone")
    p_create.add_argument("--no-milestone", action="store_true", help="Explicitly assign no milestone")

    for name in ("done", "close"):
        p_done = sub.add_parser(name, help="Close an issue")
        p_done.add_argument("slug", help="Issue slug")
        p_done.add_argument("--status", "-s", default="done", choices=list(entities.CLOSED_ISSUE_STATUSES))
        p_done.add_argument("--superseded-by", default=None)
        p_done.add_argument("--duplicate-of", default=None)

    p_cancel = sub.add_parser("cancel", help="Cancel an issue")
    p_cancel.add_argument("slug", help="Issue slug")
    p_cancel.add_argument("--superseded-by", default=None)
    p_cancel.add_argument("--duplicate-of", default=None)

    p_del = sub.add_parser("delete", help="Delete an issue created by mistake")
    p_del.add_argument("slug", help="Issue slug")

    p_reopen = sub.add_parser("reopen", help="Reopen a closed issue")
    p_reopen.add_argument("slug", help="Issue slug")

    sub.add_parser("sync", help="Recompile .along/ISSUES.md projection board")

    for name in ("list", "export"):
        p_list = sub.add_parser(name, help="List active issues")
        p_list.add_argument("--compact", "-c", action="store_true", help="Compact digest")

    for name in ("update", "edit"):
        p_up = sub.add_parser(name, help="Update an issue")
        p_up.add_argument("slug", help="Issue slug")
        p_up.add_argument("--milestone", "-m", default=None)
        p_up.add_argument("--priority", "-p", default=None)
        p_up.add_argument("--status", "-s", default=None)
        p_up.add_argument("--tags", default=None)
        p_up.add_argument("--title", "-t", default=None)

    for name in ("show", "get"):
        p_sh = sub.add_parser(name, help="Show issue details")
        p_sh.add_argument("slug", help="Issue slug")
        p_sh.add_argument("--json", action="store_true", help="Format as JSON")

    p_lint = sub.add_parser("lint", help="Audit issue section contracts")
    p_lint.add_argument("--strict", action="store_true")

    p_ren = sub.add_parser("rename", help="Rename an issue key")
    p_ren.add_argument("old_key", help="Old canonical key")
    p_ren.add_argument("new_key", help="New canonical key")

    p_sup = sub.add_parser("supersede", help="Supersede an issue key")
    p_sup.add_argument("old_key", help="Old canonical key")
    p_sup.add_argument("--by", required=True, help="New canonical key(s)")

    return parser


def handle_issue_command(repo_root: str, args: List[str]):
    if not args or args[0] in ("-h", "--help", "help"):
        print("Usage: along_exec.py issue [create|update|done|cancel|delete|reopen|sync|list|show|rename|supersede|lint] [args...]")
        print("  create <type> <slug> --title \"Title\" [--priority high|medium|low] [--tags \"t1,t2\"] [--agent <name>] [--milestone <name>|--no-milestone]")
        print("  update <slug> [--milestone <name>] [--priority <high|medium|low>] [--status <status>] [--tags <t1,t2>] [--title <title>]")
        print("  done   <slug> [--status done|superseded|cancelled|duplicate] [--superseded-by <key>] [--duplicate-of <key>]")
        print("  cancel <slug>             Close as cancelled (moved to done/)")
        print("  delete <slug>             Remove an issue created by mistake (refused once sessions, commits")
        print("                            or parent/superseded_by/duplicate_of references name it)")
        print("  reopen <slug>")
        print("  sync                      Recompile the .along/ISSUES.md board")
        print("  list   [--compact]        List active issues (or compact backlog digest)")
        print("  show   <slug> [--json]")
        print("  lint   [--strict]         Audit active issues against mandatory section contracts")
        print("  rename <old-key> <new-key>")
        print("  supersede <old-key> --by <new-key>")
        sys.exit(0)

    subcmd = args[0].lower()
    issues_dir = os.path.join(repo_root, ".along", "ISSUES")
    done_dir = os.path.join(issues_dir, "done")
    os.makedirs(issues_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    dispatch = {
        "create": lambda: _issue_create(repo_root, args, issues_dir, today),
        "done": lambda: _issue_done(repo_root, args, issues_dir, done_dir, today),
        "close": lambda: _issue_done(repo_root, args, issues_dir, done_dir, today),
        "cancel": lambda: _issue_done(repo_root, args[:2] + ["--status", "cancelled"] + args[2:],
                                      issues_dir, done_dir, today),
        "delete": lambda: _issue_delete(repo_root, args),
        "reopen": lambda: _issue_reopen(repo_root, args, issues_dir, done_dir, today),
        "sync": lambda: _issue_sync(repo_root, args),
        "list": lambda: _issue_list(repo_root, issues_dir, args),
        "export": lambda: _issue_list(repo_root, issues_dir, args),
        "lint": lambda: _issue_lint(repo_root, args),
        "update": lambda: _issue_update(repo_root, args, today),
        "edit": lambda: _issue_update(repo_root, args, today),
        "show": lambda: _issue_show(repo_root, args),
        "get": lambda: _issue_show(repo_root, args),
        "rename": lambda: _issue_rename(repo_root, args),
        "supersede": lambda: _issue_supersede(repo_root, args),
    }

    handler = dispatch.get(subcmd)
    if not handler:
        print(f"[Error] Unknown issue subcommand '{subcmd}'. Run 'along issue --help'.", file=sys.stderr)
        sys.exit(1)
    handler()
