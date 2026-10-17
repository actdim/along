#!/usr/bin/env python3
"""
alongkit.entities.mutation - Mutating, rewriting, superseding, and renaming entities.
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
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .projections import sync_issues_board
from .query import (
    _PROJECTION_FILES,
    find_issue_by_slug,
    resolve_milestone_by_query,
    scan_issues,
    scan_milestones,
)
from .vocabulary import (
    ISSUE_TYPES,
    MILESTONE_REFERENCE_FIELDS,
    REFERENCE_FIELDS,
    SESSION_REFERENCE_FIELDS,
    canonical_key,
    is_valid_slug,
    issue_filename,
    parse_key,
    today_iso,
)

_REFERENCING_DIRS: Tuple[str, ...] = ("ISSUES", "RISKS", "SPIKES", "CHECKLISTS", "DECISIONS")
_DANGLING_MILESTONE = "dangling milestone reference: "
_DELETE_LIST_FIELDS: Tuple[str, ...] = ("related", "blocked_by", "target_issues")
_DELETE_BLOCKING_FIELDS: Tuple[str, ...] = ("parent", "superseded_by", "duplicate_of")


def update_issue_frontmatter(repo_root: str, slug: str, updates: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Update issue frontmatter fields preserving comments, order, and structure."""
    from .. import frontmatter, textio

    issue = find_issue_by_slug(repo_root, slug)
    if not issue:
        raise ValueError(f"Issue with slug '{slug}' not found.")

    fpath = issue["file_path"]
    content = textio.read_text(fpath)
    updated_content = frontmatter.update(content, updates, path=fpath)
    textio.write_text(fpath, updated_content, newline="\n")

    new_fm, _, _ = frontmatter.try_parse(updated_content, path=fpath)
    return fpath, new_fm


def sync_milestones(repo_root: str, target_slug: Optional[str] = None) -> List[Dict[str, Any]]:
    """Synchronize milestone files: target_issues, progress_pct, and status."""
    from .. import frontmatter, textio

    all_milestones = scan_milestones(repo_root)
    if not all_milestones:
        return []

    target_m = None
    if target_slug:
        target_m = resolve_milestone_by_query(repo_root, target_slug)
        if not target_m:
            raise ValueError(f"Milestone '{target_slug}' not found.")

    milestones_to_sync = [target_m] if target_m else [
        m for m in all_milestones if m["status"] != "completed"]
    all_issues = scan_issues(repo_root, include_done=True)
    by_ref: Dict[str, Dict[str, Any]] = {}
    for iss in all_issues:
        by_ref[canonical_key(iss["type"], iss["slug"])] = iss
        by_ref.setdefault(iss["slug"], iss)

    results = []
    for m in milestones_to_sync:
        m_slug = m["slug"]
        m_stem = os.path.basename(m["file_path"])[:-3]

        assigned_issues = []
        for iss in all_issues:
            iss_m = iss["frontmatter"].get("milestone")
            if not iss_m:
                continue
            iss_m_str = str(iss_m).strip()
            if iss_m_str in (m_slug, m_stem):
                assigned_issues.append(iss)
        explicit = m["frontmatter"].get("target_issues") or []
        for ref in ([explicit] if isinstance(explicit, str) else explicit):
            iss = by_ref.get(str(ref).strip()) or by_ref.get(parse_key(str(ref).strip())[1])
            if not iss or iss in assigned_issues:
                continue
            other = str(iss["frontmatter"].get("milestone") or "").strip()
            if not other or other in (m_slug, m_stem):
                assigned_issues.append(iss)

        assigned_keys = sorted(list({
            canonical_key(iss["type"], iss["slug"]) for iss in assigned_issues
        }))

        total = len(assigned_issues)
        done_count = len([iss for iss in assigned_issues if iss["done"]])
        in_prog_count = len([iss for iss in assigned_issues if iss["status"] == "in-progress"])

        if total > 0:
            pct = round(100 * done_count / total)
            if done_count == total:
                new_status = "completed"
            elif in_prog_count > 0 or done_count > 0:
                new_status = "in-progress"
            else:
                new_status = "open"
        else:
            pct = 100 if m["status"] == "completed" else 0
            new_status = m["status"]

        fpath = m["file_path"]
        content = textio.read_text(fpath)
        cur_target = m["frontmatter"].get("target_issues", [])
        cur_pct = m["frontmatter"].get("progress_pct")
        cur_status = m["frontmatter"].get("status")

        if cur_target != assigned_keys or cur_pct != pct or cur_status != new_status:
            updates = {
                "target_issues": assigned_keys,
                "progress_pct": pct,
                "status": new_status,
            }
            updated_content = frontmatter.update(content, updates, path=fpath)
            textio.write_text(fpath, updated_content, newline="\n")

        results.append({
            "slug": m_slug,
            "title": m["title"],
            "file_path": fpath,
            "status": new_status,
            "progress_pct": pct,
            "total_issues": total,
            "done_issues": done_count,
            "target_issues": assigned_keys,
        })

    return results


def drop_dangling_milestones(repo_root: str, dry_run: bool = False) -> List[str]:
    """Remove milestone fields that resolve to no milestone."""
    from .. import frontmatter, repo, textio
    from .validation import validate_entities

    report = validate_entities(repo_root)
    targets = sorted({rel for rel, msg in report["errors"] + report["warnings"]
                      if msg.startswith(_DANGLING_MILESTONE)})
    changed: List[str] = []
    for rel in targets:
        path = os.path.join(repo_root, rel)
        content = textio.read_text(path)
        updated = frontmatter.update(content, {}, remove=["milestone"], path=path)
        if updated == content:
            continue
        if not dry_run:
            textio.write_text(path, updated, newline="\n")
        changed.append(repo.normalize_posix(rel))
    return changed


def _rewrite_ref(ref: Any, old_key: str, old_slug: str, new_key: str) -> Optional[str]:
    if not ref:
        return None
    raw = str(ref).strip()
    bracketed = raw.startswith("[") and raw.endswith("]")
    core = raw.strip("[]")
    prefix = ""
    if ":" in core:
        prefix, core = core.split(":", 1)
        prefix += ":"
    if core not in (old_key, old_slug):
        return None
    out = prefix + new_key
    return f"[{out}]" if bracketed else out


def _rewrite_fields(fm: Dict[str, Any], fields: Sequence[str], old_key: str, old_slug: str,
                    new_key: Union[str, Sequence[str]]) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    is_multi = isinstance(new_key, (list, tuple))
    for field_name in fields:
        value = fm.get(field_name)
        if isinstance(value, list):
            changed = False
            rewritten = []
            for item in value:
                if is_multi:
                    item_matches = _rewrite_ref(item, old_key, old_slug, old_key) is not None
                    if item_matches:
                        changed = True
                        for k in new_key:
                            rewritten_k = _rewrite_ref(item, old_key, old_slug, k)
                            if rewritten_k is not None and rewritten_k not in rewritten:
                                rewritten.append(rewritten_k)
                    else:
                        rewritten.append(item)
                else:
                    new = _rewrite_ref(item, old_key, old_slug, new_key)
                    changed = changed or new is not None
                    if new is None:
                        rewritten.append(item)
                    elif new not in rewritten:
                        rewritten.append(new)
            if changed:
                updates[field_name] = rewritten
        else:
            target_k = new_key[0] if is_multi and new_key else new_key
            new = _rewrite_ref(value, old_key, old_slug, target_k)
            if new is not None:
                updates[field_name] = new
    return updates


def _entity_files(sdir: str, dirname: str) -> List[str]:
    import glob

    return sorted(p for p in glob.glob(os.path.join(sdir, dirname, "**", "*.md"), recursive=True)
                  if os.path.basename(p) not in _PROJECTION_FILES)


def rewrite_inbound_references(repo_root: str, old_key: str, new_key: Union[str, Sequence[str]],
                                skip: Sequence[str] = (), history: bool = True) -> List[str]:
    """Point every reference to old_key at new_key; return the rewritten files."""
    from .. import frontmatter, repo, textio

    _, old_slug = parse_key(old_key)
    sdir = repo.state_dir(repo_root)
    skipped = {os.path.normcase(os.path.abspath(p)) for p in skip}
    plan: List[Tuple[str, Sequence[str]]] = []
    for dirname in _REFERENCING_DIRS:
        plan += [(p, REFERENCE_FIELDS) for p in _entity_files(sdir, dirname)]
    plan += [(p, MILESTONE_REFERENCE_FIELDS) for p in _entity_files(sdir, "MILESTONES")]
    if history:
        plan += [(p, SESSION_REFERENCE_FIELDS) for p in _entity_files(sdir, "SESSIONS")]

    changed: List[str] = []
    for fpath, fields in plan:
        if os.path.normcase(os.path.abspath(fpath)) in skipped:
            continue
        try:
            content = textio.read_text(fpath)
        except OSError:
            continue
        fm, _, _ = frontmatter.try_parse(content, path=fpath)
        if not fm:
            continue
        updates = _rewrite_fields(fm, fields, old_key, old_slug, new_key)
        if updates:
            textio.write_text(fpath, frontmatter.update(content, updates, path=fpath), newline="\n")
            changed.append(fpath)
    return changed


def _require_issue(repo_root: str, key: str) -> Dict[str, Any]:
    issue = find_issue_by_slug(repo_root, key)
    if not issue:
        raise ValueError(f"Issue '{key}' not found in .along/ISSUES/.")
    return issue


def rename_issue(repo_root: str, old: str, new: str) -> Dict[str, Any]:
    """Rename issue old to key new and rewrite every inbound reference."""
    from .. import frontmatter, textio

    issue = _require_issue(repo_root, old)
    new_type, new_slug = parse_key(new)
    new_type = new_type or issue["type"]
    if new_type not in ISSUE_TYPES:
        raise ValueError(f"Invalid issue type '{new_type}'. Allowed: {', '.join(ISSUE_TYPES)}")
    if not is_valid_slug(new_slug):
        raise ValueError(f"Invalid issue slug '{new_slug}': 2-5 lowercase kebab-case words.")
    old_key = canonical_key(issue["type"], issue["slug"])
    new_key = canonical_key(new_type, new_slug)
    if new_key == old_key:
        raise ValueError(f"'{new_key}' is already the key of this issue.")
    clash = find_issue_by_slug(repo_root, new_slug)
    if clash and os.path.abspath(clash["file_path"]) != os.path.abspath(issue["file_path"]):
        raise ValueError(f"An issue with slug '{new_slug}' already exists.")

    src = issue["file_path"]
    dest = os.path.join(os.path.dirname(src), issue_filename(new_type, new_slug))
    content = textio.read_text(src)
    updated = frontmatter.update(content, {"slug": new_slug, "type": new_type, "updated": today_iso()},
                                 path=src)
    textio.write_text(dest, updated, newline="\n", atomic=True)
    os.remove(src)

    changed = rewrite_inbound_references(repo_root, old_key, new_key, skip=[dest])
    sync_milestones(repo_root)
    sync_issues_board(repo_root)
    return {"old_key": old_key, "new_key": new_key, "file_path": dest, "rewritten": changed}


def supersede_issue(repo_root: str, old: str, by: Union[str, Sequence[str]]) -> Dict[str, Any]:
    """Close old as superseded by by and move live references over to by."""
    from .. import frontmatter, repo, textio

    if isinstance(by, str):
        successors_raw = [s.strip().lower() for s in by.split(",") if s.strip()]
    elif isinstance(by, (list, tuple)):
        successors_raw = [str(s).strip().lower() for s in by if str(s).strip()]
    else:
        raise ValueError(f"Invalid 'by' parameter for supersede: {by}")

    if not successors_raw:
        raise ValueError("At least one successor issue must be specified via '--by'.")

    issue = _require_issue(repo_root, old)
    old_key = canonical_key(issue["type"], issue["slug"])

    successors = [_require_issue(repo_root, s) for s in successors_raw]
    successors_keys = [canonical_key(s["type"], s["slug"]) for s in successors]

    if old_key in successors_keys:
        raise ValueError("An issue cannot supersede itself.")

    unique_keys = []
    for k in successors_keys:
        if k not in unique_keys:
            unique_keys.append(k)
    successors_keys = unique_keys

    superseded_by_val: Union[str, List[str]] = (
        successors_keys[0] if len(successors_keys) == 1 else successors_keys
    )

    skip_paths = [issue["file_path"]] + [s["file_path"] for s in successors]
    changed = rewrite_inbound_references(
        repo_root, old_key,
        successors_keys if len(successors_keys) > 1 else successors_keys[0],
        skip=skip_paths, history=False)

    src = issue["file_path"]
    done_dir = os.path.join(repo.state_dir(repo_root), "ISSUES", "done")
    dest = os.path.join(done_dir, os.path.basename(src))
    today = today_iso()
    content = textio.read_text(src)
    updated = frontmatter.update(
        content,
        {"status": "superseded", "superseded_by": superseded_by_val, "updated": today, "completed": today},
        place_after={"completed": "status", "superseded_by": "completed"},
        path=src)
    os.makedirs(done_dir, exist_ok=True)
    textio.write_text(dest, updated, newline="\n", atomic=True)
    if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dest)):
        os.remove(src)

    sync_milestones(repo_root)
    sync_issues_board(repo_root)
    return {"old_key": old_key, "new_key": superseded_by_val, "file_path": dest, "rewritten": changed}


def delete_issue(repo_root: str, key: str) -> Dict[str, Any]:
    """Delete an issue created by mistake, with every list reference to it."""
    from .. import frontmatter, proc, repo, textio

    issue = _require_issue(repo_root, key)
    old_key = canonical_key(issue["type"], issue["slug"])
    old_slug = issue["slug"]
    sdir = repo.state_dir(repo_root)

    def points_at(ref: Any) -> bool:
        return _rewrite_ref(ref, old_key, old_slug, old_key) is not None

    def refs(fm: Dict[str, Any], field_name: str) -> List[Any]:
        value = fm.get(field_name)
        return value if isinstance(value, list) else [value]

    holders: List[str] = []
    edits: List[Tuple[str, str, Dict[str, Any]]] = []
    files = [p for d in _REFERENCING_DIRS + ("MILESTONES",) for p in _entity_files(sdir, d)]
    for fpath in files + _entity_files(sdir, "SESSIONS"):
        if os.path.normcase(os.path.abspath(fpath)) == os.path.normcase(os.path.abspath(issue["file_path"])):
            continue
        try:
            content = textio.read_text(fpath)
        except OSError:
            continue
        fm, _, _ = frontmatter.try_parse(content, path=fpath)
        if not fm:
            continue
        rel = repo.canonical_relpath(fpath, repo_root)
        blocking = SESSION_REFERENCE_FIELDS + _DELETE_BLOCKING_FIELDS
        if any(points_at(r) for f in blocking for r in refs(fm, f)):
            holders.append(rel)
            continue
        updates = {f: [r for r in fm[f] if not points_at(r)] for f in _DELETE_LIST_FIELDS
                   if isinstance(fm.get(f), list) and any(points_at(r) for r in fm[f])}
        if updates:
            edits.append((fpath, content, updates))
    if holders:
        raise ValueError(f"'{old_key}' is referenced by {', '.join(holders)}: cancel it "
                         f"('along issue cancel {old_slug}') or supersede it instead.")
    log = proc.run_capture(["git", "log", "--all", "-F", f"--grep={old_slug}", "-n", "1", "--format=%h"],
                           cwd=repo_root, check=False)
    if log.ok and log.stdout.strip():
        raise ValueError(f"Commit {log.stdout.strip()} mentions '{old_slug}': cancel it "
                         f"('along issue cancel {old_slug}') instead of deleting it.")

    for fpath, content, updates in edits:
        textio.write_text(fpath, frontmatter.update(content, updates, path=fpath), newline="\n")
    os.remove(issue["file_path"])
    sync_milestones(repo_root)
    sync_issues_board(repo_root)
    return {"key": old_key, "file_path": issue["file_path"], "rewritten": [e[0] for e in edits]}
