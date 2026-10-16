#!/usr/bin/env python3
"""
alongkit.entities.query - Querying, scanning, resolving, and context traversal for entities.
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
from typing import Any, Dict, List, Optional, Tuple

from .vocabulary import (
    CLOSED_ISSUE_STATUSES,
    DELIVERED_ISSUE_STATUSES,
    ROOT_QUALIFIER,
    canonical_key,
    parse_key,
)

_ANCESTOR_ENTITY_DIRS = ("ISSUES", "RISKS", "SPIKES", "MILESTONES", "DECISIONS")
_PROJECTION_FILES = ("ISSUES.md", "README.md", "CONSTRAINTS.md", "DECISIONS.md")


def scan_issues(repo_root: str, include_done: bool = False) -> List[Dict[str, Any]]:
    """List issues from the SSOT entity files (.along/ISSUES/*.md)."""
    from .. import frontmatter, repo, textio

    sdir = repo.state_dir(repo_root)
    issues_dir = os.path.join(sdir, "ISSUES")
    if not os.path.isdir(issues_dir):
        return []

    dirs_to_scan = [(issues_dir, False)]
    if include_done:
        done_dir = os.path.join(issues_dir, "done")
        if os.path.isdir(done_dir):
            dirs_to_scan.append((done_dir, True))

    issues = []
    for directory, is_done in dirs_to_scan:
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(directory, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                content = textio.read_text(fpath)
            except OSError:
                continue
            fm, _, _ = frontmatter.try_parse(content, path=fpath)
            ftype, fslug = parse_key(fname[:-3])
            itype = fm.get("type") or ftype or "task"
            islug = fm.get("slug") or fslug
            status = fm.get("status") or ("done" if is_done else "open")

            issues.append({
                "slug": islug,
                "type": itype,
                "status": status,
                "priority": fm.get("priority", "medium"),
                "file_path": fpath,
                "done": is_done or status in CLOSED_ISSUE_STATUSES,
                "delivered": status in DELIVERED_ISSUE_STATUSES,
                "frontmatter": fm,
            })
    return issues


def find_issue_by_slug(repo_root: str, slug: str) -> Optional[Dict[str, Any]]:
    """Search .along/ISSUES/ and .along/ISSUES/done/ for an issue matching slug."""
    clean_type, clean_slug = parse_key(slug)
    all_issues = scan_issues(repo_root, include_done=True)
    for iss in all_issues:
        if iss["slug"] == clean_slug or iss["slug"] == slug:
            if clean_type and iss["type"] != clean_type:
                continue
            return iss
        if canonical_key(iss["type"], iss["slug"]) == slug:
            return iss
    return None


def resolve_active_issue(repo_root: str,
                         explicit_slug: Optional[str] = None,
                         branch_name: Optional[str] = None,
                         strict: bool = False) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Infer or validate the active issue for a commit deterministically."""
    from .. import proc

    warnings: List[str] = []

    # 1. Explicit slug
    if explicit_slug:
        found = find_issue_by_slug(repo_root, explicit_slug)
        if not found:
            msg = f"Unknown issue slug: '{explicit_slug}' does not exist in .along/ISSUES/."
            if strict:
                raise ValueError(msg)
            warnings.append(msg)
            return None, warnings
        return found, warnings

    active_issues = scan_issues(repo_root, include_done=False)
    in_progress = [iss for iss in active_issues if iss["status"] == "in-progress"]

    # 2. Branch name check
    branch = branch_name
    if branch is None:
        res = proc.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
        if res.ok:
            branch = res.stdout.strip()

    if branch and branch not in ("HEAD", "main", "master"):
        branch_lower = branch.lower()
        branch_matches = []
        for iss in in_progress:
            islug = iss["slug"].lower()
            if (islug == branch_lower or
                    f"/{islug}" in branch_lower or
                    f"--{islug}" in branch_lower or
                    branch_lower.endswith(islug)):
                branch_matches.append(iss)
        if len(branch_matches) == 1:
            return branch_matches[0], warnings

    # 3. Single in-progress issue
    if len(in_progress) == 1:
        return in_progress[0], warnings

    # 4. Refuse to guess
    if len(in_progress) == 0:
        msg = "No in-progress issue found in .along/ISSUES/. Commit will have no issue binding."
        if strict:
            raise ValueError("Strict mode: no in-progress issue found in .along/ISSUES/.")
        warnings.append(msg)
        return None, warnings
    else:
        slugs = [iss["slug"] for iss in in_progress]
        msg = (
            f"Multiple in-progress issues found ({', '.join(slugs)}). "
            "Cannot determine active issue unambiguously without --issue <slug>."
        )
        if strict:
            raise ValueError(f"Strict mode: multiple in-progress issues found ({', '.join(slugs)}).")
        warnings.append(msg)
        return None, warnings


def scan_milestones(repo_root: str) -> List[Dict[str, Any]]:
    """List milestones from .along/MILESTONES/*.md."""
    from .. import frontmatter, repo, textio

    sdir = repo.state_dir(repo_root)
    m_dir = os.path.join(sdir, "MILESTONES")
    if not os.path.isdir(m_dir):
        return []

    milestones = []
    for fname in sorted(os.listdir(m_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(m_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            content = textio.read_text(fpath)
        except OSError:
            continue
        fm, _, _ = frontmatter.try_parse(content, path=fpath)
        fslug = fname[:-3]
        mslug = fm.get("slug") or fslug
        status = fm.get("status") or "open"
        milestones.append({
            "slug": mslug,
            "title": fm.get("title", mslug),
            "status": status,
            "target_issues": fm.get("target_issues", []),
            "file_path": fpath,
            "frontmatter": fm,
        })
    return milestones


def resolve_in_progress_milestone(repo_root: str) -> Optional[str]:
    """Return the milestone slug if exactly one milestone has status: in-progress."""
    milestones = scan_milestones(repo_root)
    in_progress = [m for m in milestones if m["status"] == "in-progress"]
    if len(in_progress) == 1:
        return in_progress[0]["slug"]
    return None


def resolve_milestone_by_query(repo_root: str, query: str) -> Optional[Dict[str, Any]]:
    """Fuzzy resolve milestone by exact slug, filename, version prefix, or substring."""
    if not query or not isinstance(query, str):
        return None
    raw = query.strip()
    if raw.endswith(".md"):
        raw = raw[:-3]
    lowered = raw.lower()

    milestones = scan_milestones(repo_root)
    if not milestones:
        return None

    for m in milestones:
        stem = os.path.basename(m["file_path"])[:-3].lower()
        if m["slug"].lower() == lowered or stem == lowered:
            return m

    clean_v = lowered.lstrip("v")
    v_candidates = []
    for m in milestones:
        m_slug_clean = m["slug"].lower().lstrip("v")
        m_stem_clean = os.path.basename(m["file_path"])[:-3].lower().lstrip("v")
        if (m_slug_clean.startswith(clean_v + ".") or
                m_slug_clean.startswith(clean_v + "-") or
                m_slug_clean == clean_v or
                m_stem_clean.startswith(clean_v + ".") or
                m_stem_clean.startswith(clean_v + "-") or
                m_stem_clean == clean_v):
            v_candidates.append(m)

    if len(v_candidates) == 1:
        return v_candidates[0]
    elif len(v_candidates) > 1:
        exact_v = [m for m in v_candidates if m["slug"].lower().startswith(f"v{clean_v}") or m["slug"].lower().startswith(clean_v)]
        if len(exact_v) == 1:
            return exact_v[0]
        return None

    sub_candidates = [
        m for m in milestones
        if lowered in m["slug"].lower() or lowered in m.get("title", "").lower()
    ]
    if len(sub_candidates) == 1:
        return sub_candidates[0]
    return None


def check_milestone_version_collision(
    repo_root: str,
    new_slug: str,
    exclude_slug: Optional[str] = None
) -> Optional[str]:
    """Check if new_slug collides with any existing milestone SemVer version."""
    from .. import semver

    new_ver = semver.parse(new_slug)
    if new_ver == (0, 0, 0):
        return None

    milestones = scan_milestones(repo_root)
    for m in milestones:
        mslug = m["slug"]
        if exclude_slug and mslug == exclude_slug:
            continue
        m_ver = semver.parse(mslug)
        if m_ver == (0, 0, 0):
            continue

        m_status = m["status"]
        if new_ver == m_ver:
            if m_status != "completed":
                return (
                    f"Milestone exact SemVer collision ({semver.to_str(new_ver)}) with "
                    f"existing milestone '{mslug}'. Milestones cannot share the same release version."
                )

        if (new_ver[0], new_ver[1]) == (m_ver[0], m_ver[1]):
            if m_status != "completed":
                return (
                    f"Milestone minor version collision ({new_ver[0]}.{new_ver[1]}) with "
                    f"existing active milestone '{mslug}'. Active milestones must target distinct minor releases."
                )

    return None


def get_issue_summary(repo_root: str, slug: str) -> Optional[Dict[str, Any]]:
    """Retrieve structured summary of an issue including frontmatter and body."""
    from .. import frontmatter, repo, textio

    iss = find_issue_by_slug(repo_root, slug)
    if not iss:
        return None

    fpath = iss["file_path"]
    try:
        content = textio.read_text(fpath)
        fm, body, _ = frontmatter.try_parse(content, path=fpath)
    except OSError:
        fm, body = iss["frontmatter"], ""

    return {
        "slug": iss["slug"],
        "type": iss["type"],
        "status": iss["status"],
        "priority": iss["priority"],
        "title": fm.get("title", iss["slug"].replace("-", " ").capitalize()),
        "milestone": fm.get("milestone"),
        "agent": fm.get("agent"),
        "tags": fm.get("tags", []),
        "created": fm.get("created"),
        "updated": fm.get("updated"),
        "completed": fm.get("completed"),
        "blocked_by": fm.get("blocked_by", []),
        "related": fm.get("related", []),
        "requires": fm.get("requires"),
        "file_path": repo.safe_relpath(fpath, repo_root),
        "body": body.strip(),
    }


def milestone_open_issues(repo_root: str, milestone: Dict[str, Any]) -> Tuple[List[str], int]:
    """(open issue keys, total) over a milestone's issues."""
    names = {milestone["slug"], os.path.basename(milestone["file_path"])[:-3]}
    listed = milestone.get("frontmatter", {}).get("target_issues") or []
    keys: Dict[str, bool] = {}
    for iss in scan_issues(repo_root, include_done=True):
        key = canonical_key(iss["type"], iss["slug"])
        in_field = str(iss["frontmatter"].get("milestone") or "").strip() in names
        in_list = key in listed or iss["slug"] in listed
        if in_field or in_list:
            keys[key] = iss["status"] in CLOSED_ISSUE_STATUSES
    return sorted(k for k, closed in keys.items() if not closed), len(keys)


def _context_entity_keys(along_dir: str, keys: set) -> None:
    """Add the entity keys of one .along/ directory to keys."""
    import glob

    for dirname in _ANCESTOR_ENTITY_DIRS:
        pattern = os.path.join(along_dir, dirname, "**", "*.md")
        for fpath in glob.glob(pattern, recursive=True):
            fname = os.path.basename(fpath)
            if fname in _PROJECTION_FILES:
                continue
            stem = fname[:-3]
            keys.add(stem)
            if "--" in stem:
                bare = stem.split("--", 1)[1]
                keys.add(bare)
                keys.add(f"decision--{bare}")


def ancestor_contexts(repo_root: str) -> List[Tuple[str, str]]:
    """(owner, state dir) of every enclosing context above repo_root, nearest first."""
    from .. import repo

    root = os.path.normcase(os.path.abspath(repo_root))
    return [(owner, sdir) for owner, sdir in repo.context_chain(repo_root)
            if os.path.normcase(os.path.abspath(owner)) != root]


def ancestor_entity_keys(repo_root: str) -> set:
    """Entity keys of every enclosing .along/ context."""
    keys: set = set()
    for _owner, sdir in ancestor_contexts(repo_root):
        _context_entity_keys(sdir, keys)
    return keys


def _ref_key(ref: Any) -> Tuple[str, str]:
    """(qualifier, key) of a reference: root:task--x -> ('root', 'task--x')."""
    clean = str(ref).strip().strip("[]")
    if ":" in clean:
        qualifier, clean = clean.split(":", 1)
        return qualifier.strip().lower(), clean.strip()
    return "", clean


def _resolve_ref(ref: Any, known: set, root_keys: Optional[set] = None) -> bool:
    """True when ref names a key in known (a root: ref in root_keys, when given)."""
    if not ref:
        return False
    qualifier, clean = _ref_key(ref)
    if qualifier == ROOT_QUALIFIER and root_keys is not None:
        known = root_keys
    if clean in known:
        return True
    _, slug = parse_key(clean)
    return slug in known


def _is_self_ref(ref: Any, own_type: str, own_slug: str) -> bool:
    qualifier, clean = _ref_key(ref)
    if qualifier == ROOT_QUALIFIER:
        return False
    return clean in (own_slug, canonical_key(own_type, own_slug))


def cross_context_parents(repo_root: str) -> List[Tuple[str, str, str]]:
    """(issue key, parent, owner dir) for each local issue whose parent lives in an enclosing context."""
    found: List[Tuple[str, str, str]] = []
    outer = ancestor_contexts(repo_root)
    if not outer:
        return found
    issues = scan_issues(repo_root, include_done=True)
    local = {canonical_key(i["type"], i["slug"]) for i in issues} | {i["slug"] for i in issues}
    for iss in issues:
        parent = (iss.get("frontmatter") or {}).get("parent")
        if not parent or not str(parent).strip():
            continue
        own_key = canonical_key(iss["type"], iss["slug"])
        if _resolve_ref(parent, local) and not _is_self_ref(parent, iss["type"], iss["slug"]):
            continue
        for owner, sdir in outer:
            keys: set = set()
            _context_entity_keys(sdir, keys)
            if _resolve_ref(parent, keys):
                found.append((own_key, str(parent), owner))
                break
    return found


def reference_context(repo_root: str, ref: Any) -> Optional[str]:
    """Owner directory of the context a reference resolves in, nearest first, or None."""
    from .. import repo

    _qualifier, clean = _ref_key(ref)
    for owner, sdir in repo.context_chain(repo_root):
        keys: set = set()
        _context_entity_keys(sdir, keys)
        if _resolve_ref(clean, keys):
            return owner
    return None


def _nested_context_keys(start: str, skip: Optional[str] = None) -> set:
    """Entity keys of every .along/ context strictly below start."""
    from .. import repo

    keys: set = set()
    root = os.path.abspath(start)
    skip_norm = os.path.normcase(os.path.abspath(skip)) if skip else None
    ignored = set(repo.IGNORED_DIRS) | set(repo.PROVIDER_DIRS)
    for current, dirs, _files in os.walk(root):
        if current != root:
            if skip_norm and os.path.normcase(os.path.abspath(current)) == skip_norm:
                dirs[:] = []
                continue
            if os.path.exists(os.path.join(current, ".git")):
                dirs[:] = []
                continue
            candidate = os.path.join(current, ".along")
            if os.path.isdir(candidate):
                _context_entity_keys(candidate, keys)
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
    return keys


def descendant_entity_keys(repo_root: str) -> set:
    """Entity keys of every nested .along/ context below repo_root."""
    return _nested_context_keys(repo_root)


def sibling_entity_keys(repo_root: str) -> set:
    """Entity keys of the other .along/ contexts of the same git repository."""
    root = os.path.abspath(repo_root)
    if os.path.exists(os.path.join(root, ".git")):
        return set()
    current = os.path.dirname(root)
    while current and current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, ".git")):
            return _nested_context_keys(current, skip=root)
        current = os.path.dirname(current)
    return set()
