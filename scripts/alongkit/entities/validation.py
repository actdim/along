#!/usr/bin/env python3
"""
alongkit.entities.validation - Entity schemas, enums, mandatory fields, and graph references.
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

from .decisions import check_decision_conflicts
from .query import (
    _context_entity_keys,
    _is_self_ref,
    _resolve_ref,
    ancestor_contexts,
    descendant_entity_keys,
    scan_issues,
    scan_milestones,
    sibling_entity_keys,
)
from .vocabulary import (
    CLOSED_ISSUE_STATUSES,
    DECISION_STATUSES,
    ISSUE_STATUSES,
    ISSUE_TYPES,
    LEGACY_ENTITY_DIRS,
    MILESTONE_STATUSES,
    PRIORITIES,
    canonical_key,
    is_iso_date,
)

_ARCHIVED_SUFFIX = " (archived issue)"


def is_integrity_error(message: str) -> bool:
    """A validate_entities error the reference-integrity gate blocks on."""
    return message.startswith("dangling ") or message.startswith("invalid ")


def _archived_reporter(warnings: List[Tuple[str, str]]):
    """Append (rel, message) to warnings, marking the message as an archived issue's."""
    def report(finding: Tuple[str, str]) -> None:
        warnings.append((finding[0], finding[1] + _ARCHIVED_SUFFIX))
    return report


def validate_entities(repo_root: str, ancestors: bool = True,
                      descendants: bool = True, siblings: bool = True,
                      outer_keys: Optional[set] = None,
                      outer_root_keys: Optional[set] = None) -> Dict[str, Any]:
    """Validate entity schemas, enums, mandatory fields, and graph references."""
    from .. import frontmatter, repo, semver, textio

    sdir = repo.state_dir(repo_root)
    errors: List[Tuple[str, str]] = []
    warnings: List[Tuple[str, str]] = []
    scanned = 0
    external: set = set()
    ancestor_keys: set = set(outer_keys or ())
    root_keys: Optional[set] = set(outer_root_keys) if outer_root_keys is not None else None
    if ancestors:
        outer = ancestor_contexts(repo_root)
        for _owner, asdir in outer:
            _context_entity_keys(asdir, ancestor_keys)
        if outer and root_keys is None:
            root_keys = set()
            _context_entity_keys(outer[-1][1], root_keys)
    external |= ancestor_keys
    if descendants:
        external |= descendant_entity_keys(repo_root)
    if siblings:
        external |= sibling_entity_keys(repo_root)

    all_issues = scan_issues(repo_root, include_done=True)
    known_issue_slugs = {iss["slug"] for iss in all_issues}
    known_issue_keys = ({canonical_key(iss["type"], iss["slug"]) for iss in all_issues}
                        | known_issue_slugs | external)

    all_milestones = scan_milestones(repo_root)
    known_milestone_slugs = (
        {m["slug"] for m in all_milestones} |
        {os.path.basename(m["file_path"])[:-3] for m in all_milestones} |
        external
    )

    known_entity_keys = set(known_issue_keys)
    for m in all_milestones:
        known_entity_keys.add(m["slug"])
        known_entity_keys.add(f"milestone--{m['slug']}")

    # RISKS/SPIKES/CHECKLISTS are legacy folders a not yet migrated context may still hold.
    for kind, dirname in (("risk", "RISKS"), ("spike", "SPIKES"), ("checklist", "CHECKLISTS"), ("decision", "DECISIONS")):
        edir = os.path.join(sdir, dirname)
        if os.path.isdir(edir):
            for fname in os.listdir(edir):
                if fname.endswith(".md"):
                    slug = fname[:-3]
                    known_entity_keys.add(slug)
                    known_entity_keys.add(f"{kind}--{slug}")
                    if slug.startswith("ADR-") and "--" in slug:
                        bare = slug.split("--", 1)[1]
                        known_entity_keys.add(bare)
                        known_entity_keys.add(f"decision--{bare}")

    if root_keys is None:
        root_keys = known_entity_keys

    # 1. Validate Issues
    for iss in all_issues:
        scanned += 1
        fm = iss["frontmatter"]
        fpath = iss["file_path"]
        rel = repo.canonical_relpath(fpath, repo_root)
        schema = _archived_reporter(warnings) if iss["done"] else errors.append

        if not fm:
            schema((rel, "missing or unparseable YAML front-matter"))
            continue

        if fm.get("protocol") != "along":
            schema((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))

        islug = fm.get("slug")
        if not islug:
            schema((rel, "missing mandatory field: 'slug'"))
        else:
            fname = os.path.basename(fpath)
            expected_key = canonical_key(iss["type"], islug)
            if fname[:-3] != expected_key and fname[:-3] != islug and not fname.endswith(f"--{islug}.md"):
                schema((rel, f"slug '{islug}' does not match filename '{fname}'"))

        itype = fm.get("type")
        if not itype or itype not in ISSUE_TYPES:
            schema((rel, f"invalid type: '{itype}' (allowed: {', '.join(ISSUE_TYPES)})"))

        istatus = fm.get("status")
        if not istatus or istatus not in ISSUE_STATUSES:
            schema((rel, f"invalid status: '{istatus}' (allowed: {', '.join(ISSUE_STATUSES)})"))

        priority = fm.get("priority")
        if not priority or priority not in PRIORITIES:
            schema((rel, f"invalid priority: '{priority}' (allowed: {', '.join(PRIORITIES)})"))

        created = fm.get("created")
        if not created or not is_iso_date(created):
            schema((rel, f"missing or invalid created date: '{created}' (expected YYYY-MM-DD)"))

        updated = fm.get("updated")
        if not updated or not is_iso_date(updated):
            schema((rel, f"missing or invalid updated date: '{updated}' (expected YYYY-MM-DD)"))

        if iss["done"] or istatus in CLOSED_ISSUE_STATUSES:
            completed = fm.get("completed")
            if not completed or not is_iso_date(completed):
                schema((rel, f"missing or invalid completed date on closed issue: '{completed}' (expected YYYY-MM-DD)"))

        mslug = fm.get("milestone")
        if mslug and str(mslug).strip() and str(mslug).strip() not in known_milestone_slugs:
            schema((rel, f"dangling milestone reference: '{mslug}'"))

        parent = fm.get("parent")
        if parent and str(parent).strip():
            if islug and _is_self_ref(parent, iss["type"], str(islug)):
                if not _resolve_ref(parent, ancestor_keys):
                    errors.append((rel, f"invalid self-parent reference: '{parent}' "
                                        "(no enclosing context has an issue with this key)"))
            elif not _resolve_ref(parent, known_entity_keys, root_keys):
                errors.append((rel, f"dangling parent reference: '{parent}'"))

        blocked_by = fm.get("blocked_by")
        if isinstance(blocked_by, list):
            for b in blocked_by:
                if b and not _resolve_ref(b, known_entity_keys, root_keys):
                    errors.append((rel, f"dangling blocked_by reference: '{b}'"))

        related = fm.get("related")
        if isinstance(related, list):
            for r in related:
                if r and not _resolve_ref(r, known_entity_keys, root_keys):
                    errors.append((rel, f"dangling related reference: '{r}'"))

        superseded_by = fm.get("superseded_by")
        if isinstance(superseded_by, list):
            for s in superseded_by:
                if s and str(s).strip() and not _resolve_ref(s, known_entity_keys, root_keys):
                    errors.append((rel, f"dangling superseded_by reference: '{s}'"))
        elif superseded_by and str(superseded_by).strip():
            if not _resolve_ref(superseded_by, known_entity_keys, root_keys):
                errors.append((rel, f"dangling superseded_by reference: '{superseded_by}'"))

        duplicate_of = fm.get("duplicate_of")
        if duplicate_of and str(duplicate_of).strip():
            if not _resolve_ref(duplicate_of, known_entity_keys, root_keys):
                errors.append((rel, f"dangling duplicate_of reference: '{duplicate_of}'"))

        requires = fm.get("requires")
        if isinstance(requires, dict):
            for d in requires.get("decisions", []) or []:
                if d and not _resolve_ref(str(d), known_entity_keys, root_keys):
                    errors.append((rel, f"dangling requires.decisions reference: '{d}'"))
            for doc in requires.get("docs", []) or []:
                doc_name = str(doc).strip()
                doc_file = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
                doc_path = os.path.join(repo_root, "docs", doc_file)
                if not os.path.isfile(doc_path):
                    errors.append((rel, f"dangling requires.docs reference: '{doc}'"))

    # 2. Validate Milestones
    active_minor_versions: Dict[Tuple[int, int], str] = {}
    exact_versions: Dict[Tuple[int, int, int], List[Dict[str, Any]]] = {}

    for m in all_milestones:
        scanned += 1
        fm = m["frontmatter"]
        fpath = m["file_path"]
        rel = repo.canonical_relpath(fpath, repo_root)

        if not fm:
            errors.append((rel, "missing or unparseable YAML front-matter"))
            continue

        if fm.get("protocol") != "along":
            errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))

        mslug = fm.get("slug")
        if not mslug:
            errors.append((rel, "missing mandatory field: 'slug'"))

        if not fm.get("title"):
            errors.append((rel, "missing mandatory field: 'title'"))

        mstatus = fm.get("status")
        if not mstatus or mstatus not in MILESTONE_STATUSES:
            errors.append((rel, f"invalid status: '{mstatus}' (allowed: {', '.join(MILESTONE_STATUSES)})"))

        target_issues = fm.get("target_issues")
        if isinstance(target_issues, list):
            for t in target_issues:
                if t and not _resolve_ref(t, known_issue_keys):
                    errors.append((rel, f"dangling target_issues reference: '{t}'"))

        if mslug:
            ver = semver.parse(mslug)
            if ver != (0, 0, 0):
                exact_versions.setdefault(ver, []).append({"rel": rel, "slug": mslug, "status": mstatus})
                if mstatus != "completed":
                    minor_key = (ver[0], ver[1])
                    if minor_key in active_minor_versions:
                        existing_rel = active_minor_versions[minor_key]
                        errors.append((
                            rel,
                            f"milestone minor version collision ({ver[0]}.{ver[1]}) with '{existing_rel}'. "
                            "Active milestones must target distinct minor releases."
                        ))
                    else:
                        active_minor_versions[minor_key] = rel

    for ver, group in exact_versions.items():
        if len(group) > 1 and any(item["status"] != "completed" for item in group):
            colliding = ", ".join(f"'{item['rel']}'" for item in group)
            for item in group:
                if item["status"] != "completed":
                    errors.append((
                        item["rel"],
                        f"exact SemVer collision {ver[0]}.{ver[1]}.{ver[2]} with {colliding}. "
                        "Milestones cannot share the same release version."
                    ))

    # 3. Legacy entity folders (RISKS, SPIKES, CHECKLISTS) are converted by migration
    # Step 16 [debt--entity-model-slimming]; until then their keys stay resolvable (above)
    # and the folder is reported, not validated.
    for dirname in LEGACY_ENTITY_DIRS:
        ldir = os.path.join(sdir, dirname)
        if os.path.isdir(ldir) and any(f.endswith(".md") for f in os.listdir(ldir)):
            warnings.append((repo.canonical_relpath(ldir, repo_root),
                             "legacy entity folder; run `along update` (migration Step 16) to convert it"))

    # 4. Validate Sessions
    sessions_dir = os.path.join(sdir, "SESSIONS")
    if os.path.isdir(sessions_dir):
        for root, _, files in os.walk(sessions_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                scanned += 1
                fpath = os.path.join(root, fname)
                rel = repo.canonical_relpath(fpath, repo_root)
                try:
                    c = textio.read_text(fpath)
                    fm, _, _ = frontmatter.try_parse(c, path=fpath)
                except OSError:
                    continue
                if not fm:
                    errors.append((rel, "missing or unparseable YAML front-matter"))
                    continue
                if fm.get("protocol") != "along":
                    errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
                if not fm.get("slug"):
                    errors.append((rel, "missing mandatory field: 'slug'"))
                sdate = fm.get("date")
                if sdate and not is_iso_date(sdate):
                    errors.append((rel, f"invalid session date: '{sdate}' (expected YYYY-MM-DD)"))
                mslug = fm.get("milestone")
                if mslug and str(mslug).strip() and str(mslug).strip() not in known_milestone_slugs:
                    errors.append((rel, f"dangling milestone reference: '{mslug}'"))
                for key in ("issues_advanced", "issues_completed"):
                    items = fm.get(key)
                    if isinstance(items, list):
                        for item in items:
                            if item and not _resolve_ref(item, known_issue_keys):
                                errors.append((rel, f"dangling {key} reference: '{item}'"))

    # 5. Validate Decisions (.along/DECISIONS/*.md)
    dec_dir = os.path.join(sdir, "DECISIONS")
    if os.path.isdir(dec_dir):
        for fname in sorted(os.listdir(dec_dir)):
            if not fname.endswith(".md"):
                continue
            scanned += 1
            fpath = os.path.join(dec_dir, fname)
            rel = repo.canonical_relpath(fpath, repo_root)
            try:
                c = textio.read_text(fpath)
                fm, _, _ = frontmatter.try_parse(c, path=fpath)
            except OSError:
                continue
            if not fm:
                errors.append((rel, "missing or unparseable YAML front-matter"))
                continue
            if fm.get("protocol") != "along":
                errors.append((rel, f"missing or invalid protocol: '{fm.get('protocol')}' (expected 'along')"))
            dslug = fm.get("slug")
            if not dslug:
                errors.append((rel, "missing mandatory field: 'slug'"))
            if not fm.get("title"):
                errors.append((rel, "missing mandatory field: 'title'"))
            ddate = fm.get("date")
            if not ddate or not is_iso_date(ddate):
                errors.append((rel, f"missing or invalid date: '{ddate}' (expected YYYY-MM-DD)"))
            dstatus = fm.get("status")
            if not dstatus:
                errors.append((rel, "missing mandatory field: 'status'"))
            elif dstatus not in DECISION_STATUSES and not str(dstatus).startswith("superseded"):
                errors.append((rel, f"invalid status: '{dstatus}' (allowed: {', '.join(DECISION_STATUSES)})"))

            sup_by = fm.get("superseded_by")
            if isinstance(sup_by, list):
                for s in sup_by:
                    if s and str(s).strip() and not _resolve_ref(s, known_entity_keys):
                        errors.append((rel, f"dangling superseded_by reference: '{s}'"))
            elif sup_by and str(sup_by).strip():
                if not _resolve_ref(sup_by, known_entity_keys):
                    errors.append((rel, f"dangling superseded_by reference: '{sup_by}'"))

        conflicts = check_decision_conflicts(repo_root)
        for c in conflicts:
            errors.append((c.get("rel", "DECISIONS"), f"decision conflict: {c['message']}"))

    return {
        "clean": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "scanned": scanned,
    }
