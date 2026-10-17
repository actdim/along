#!/usr/bin/env python3
"""
alongkit.commands.doctor - Diagnostic validation of repository structure, runtime and entities.
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
import shutil
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .. import entities, frontmatter, lifecycle, proc, repo, session, textio


def _doctor_runtime_checks(repo_root: str, errors: int, warnings: int) -> Tuple[int, int]:
    """Runtime section of along doctor: who runs, what is enforced, environment hazards."""
    from alongkit import runtime

    agent = entities.detect_agent()
    report = runtime.runtime_report(repo_root, agent)
    print(f"\n--- Runtime: {agent} ---")
    tag = "[OK]" if report["enforcement"] == runtime.MECHANICAL else "[WARN]"
    print(f"{tag} Gate enforcement: {report['enforcement']}. {report['explanation']}")
    if report["enforcement"] != runtime.MECHANICAL:
        warnings += 1
    else:
        beat = runtime.last_heartbeat(repo_root, agent)
        if beat:
            print(f"[OK] Last {agent} hook run in this repository: {beat}.")
        else:
            print(f"[WARN] No {agent} hook run recorded in this repository yet "
                  "(.along/diagnostics/hook_heartbeat.json). If this session already used tools, "
                  "the runtime is not loading the hooks; restart it or check its hook settings.")
            warnings += 1

    if report["python_supported"]:
        print(f"[OK] Python {report['python']} is supported (>= 3.10).")
    else:
        print(f"[FAIL] Python {report['python']} is below the supported minimum 3.10.")
        errors += 1

    if report["stale_index_lock"]:
        print("[WARN] .git/index.lock exists: git writes will fail. If no git process is running, the "
              "folder likely forbids deletes (Claude Cowork without delete permission): grant delete "
              "permission for the folder, then remove the lock.")
        warnings += 1

    symlinks = proc.git(["config", "--get", "core.symlinks"], cwd=repo_root)
    core_symlinks = symlinks.stdout.strip() if symlinks.ok else None
    if runtime.is_cross_os_mount(repo_root, fs_type=report["fs_type"], core_symlinks=core_symlinks):
        fs = report["fs_type"] or "unknown fs"
        print(f"[WARN] Repository is on a cross-OS or VM-mounted filesystem ({fs}, core.symlinks="
              f"{core_symlinks or 'unset'}): do not run 'along worktree' from this environment.")
        warnings += 1
    return errors, warnings


def _doctor_zombie_docs_checks(repo_root: str, warnings: int) -> Tuple[int, List[dict]]:
    """Scan docs/ directories for abandoned zombie stubs."""
    zombies = []
    today = datetime.now().date()
    ignored = set(repo.IGNORED_DIRS) | set(repo.PROVIDER_DIRS)

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignored]
        if os.path.basename(root) != "docs":
            continue
        for f in files:
            if not f.endswith(".md") or f.lower() in ("index.md", "readme.md"):
                continue
            fpath = os.path.join(root, f)
            try:
                content = textio.read_text(fpath, strict=False)
                fm, body, _ = frontmatter.try_parse(content)
                if not fm or fm.get("protocol") != "along":
                    continue
                created_str = str(fm.get("created", ""))
                age_days = None
                if created_str:
                    try:
                        c_date = datetime.strptime(created_str[:10], "%Y-%m-%d").date()
                        age_days = (today - c_date).days
                    except ValueError:
                        pass
                body_lines = [
                    line.strip()
                    for line in (body or "").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                is_placeholder = (
                    "Document system components and engineering guidelines here" in (body or "")
                    or len(body_lines) < 3
                )
                if is_placeholder and (age_days is None or age_days >= 7):
                    rel = repo.safe_relpath(fpath, repo_root).replace("\\", "/")
                    zombies.append({
                        "path": rel,
                        "lines": len(body_lines),
                        "created": created_str or "unknown",
                        "age_days": age_days,
                    })
            except (OSError, UnicodeDecodeError, ValueError, KeyError, AttributeError):
                continue

    if zombies:
        print(f"\n[WARN: zombie-stub] Detected {len(zombies)} abandoned zombie stub(s) in documentation:")
        for z in zombies:
            age_disp = f"{z['age_days']}d old" if z['age_days'] is not None else "unknown age"
            print(f"  - {z['path']}: {z['lines']} content line(s), created {z['created']} ({age_disp}). Populate with real content or prune.")
        warnings += len(zombies)
    else:
        print("[OK] Knowledge Base articles clean: no abandoned zombie stubs detected.")

    return warnings, zombies


def _doctor_stub_issues_checks(repo_root: str, warnings: int) -> Tuple[int, List[dict]]:
    """Scan .along/ISSUES/ for stubs, boilerplate placeholders, or uncompleted criteria."""
    findings = entities.audit_stub_issues(repo_root)
    if findings:
        print(f"\n[WARN: stub-issues] Detected {len(findings)} stub or incomplete issue(s) across .along/ISSUES/:")
        for f in findings:
            reasons_str = "; ".join(f["reasons"])
            print(f"  - {f['path']} ({f['status']}): {reasons_str}")
        print("Remediation advice:")
        print("  - To reopen and populate with real context: along issue reopen <slug>")
        print("  - To cancel unneeded stubs: along issue done <slug> --status cancelled")
        warnings += len(findings)
    else:
        print("[OK] Issue entity quality clean: zero scaffold stubs or incomplete criteria detected.")
    return warnings, findings


def handle_doctor_command(repo_root: str, args: List[str]):
    if args and args[0] in ("-h", "--help", "help"):
        print("Usage: along doctor [entities|docs|issues|--entities|--docs|--issues] [--fix]")
        print("  (no args)            Report protocol, hooks, runtime, bindings, doc quality, issue stubs and blackboard health")
        print("  entities [--fix]     Validate entity schemas and references; --fix drops dangling milestone fields")
        print("  docs                 Validate documentation quality and detect abandoned zombie stubs")
        print("  issues               Validate issue quality and detect empty scaffold stubs or incomplete criteria")
        sys.exit(0)
    check_entities = "--entities" in args or (bool(args) and args[0].lower() == "entities")
    if check_entities:
        print("=== Along Entity Graph Validation (Doctor) ===")
        if "--fix" in args:
            fixed = entities.drop_dangling_milestones(repo_root)
            if fixed:
                print(f"-> Removed {len(fixed)} dangling milestone field(s):")
                for rel in fixed:
                    print(f"  - {rel}")
            else:
                print("-> No dangling milestone fields to remove.")
        report = entities.validate_entities(repo_root)
        print(f"Scanned {report['scanned']} entities across .along/.")
        errs = report["errors"]
        warns = report["warnings"]
        if errs:
            print(f"\n[FAIL] Found {len(errs)} entity schema error(s):")
            for path, msg in errs:
                print(f"  - {path}: {msg}")
        else:
            print("\n[OK] All entity schemas, enums, mandatory fields, and graph references valid.")

        if warns:
            print(f"\n[WARN] Found {len(warns)} entity warning(s):")
            for path, msg in warns:
                print(f"  - {path}: {msg}")

        print(f"\nEntity Doctor Summary: {len(errs)} errors, {len(warns)} warnings.")
        sys.exit(1 if len(errs) > 0 else 0)

    check_docs = "--docs" in args or (bool(args) and args[0].lower() == "docs")
    if check_docs:
        print("=== Along Knowledge Base Quality Validation (Doctor) ===")
        warns, zombies = _doctor_zombie_docs_checks(repo_root, 0)
        print(f"\nDocs Doctor Summary: 0 errors, {len(zombies)} warning(s).")
        sys.exit(0)

    check_issues = "--issues" in args or (bool(args) and args[0].lower() == "issues")
    if check_issues:
        print("=== Along Issue Quality & Stub Validation (Doctor) ===")
        warns, findings = _doctor_stub_issues_checks(repo_root, 0)
        print(f"\nIssues Doctor Summary: 0 errors, {len(findings)} warning(s).")
        sys.exit(0)

    print("=== Along Protocol Diagnostics (Doctor) ===")
    errors = 0
    warnings = 0

    along_dir = os.path.join(repo_root, ".along")
    if not os.path.exists(along_dir):
        print("[FAIL] Missing .along/ directory.")
        errors += 1
    else:
        print("[OK] .along/ directory exists.")

    # Check .gitattributes
    gitattributes_file = os.path.join(repo_root, ".gitattributes")
    if not os.path.exists(gitattributes_file):
        print("[WARN] Missing .gitattributes (recommended for merge=union on HISTORY.md/DECISIONS.md).")
        warnings += 1
    else:
        ga_content = textio.read_text(gitattributes_file, strict=False)
        if "merge=union" in ga_content:
            print("[OK] .gitattributes configured with merge=union.")
        else:
            print("[WARN] .gitattributes exists but lacks merge=union for .along/ files.")
            warnings += 1

    # Check Along merge drivers (along git setup)
    from alongkit import merge as along_merge
    driver_info = along_merge.status(repo_root)
    if driver_info["git"]:
        if along_merge.is_configured(driver_info):
            print("[OK] Along merge drivers registered (projection, frontmatter).")
        else:
            print("[WARN] Along merge drivers not fully registered. Run `along git setup`.")
            warnings += 1
        if driver_info["pending_resync"]:
            print("[WARN] Projections kept as 'ours' in a merge; run `along git sync`: "
                  + ", ".join(driver_info["pending_resync"]))
            warnings += 1

        # Check Git release tag push configuration and release tag integrity
        follow_tags = proc.git(["config", "--local", "--get", "push.followTags"], cwd=repo_root)
        if not follow_tags.ok or follow_tags.stdout.strip().lower() != "true":
            print("[WARN] Git push.followTags is not configured (release tags will not be pushed by default). "
                  "Run `along git setup` (or `git config push.followTags true`).")
            warnings += 1
        else:
            print("[OK] Git push.followTags is configured.")

        remote_origin = proc.git(["remote", "get-url", "origin"], cwd=repo_root)
        if remote_origin.ok:
            remote_tags_res = proc.git(["ls-remote", "--tags", "origin"], cwd=repo_root, check=False)
            if remote_tags_res.ok:
                remote_tag_lines = remote_tags_res.stdout.splitlines()
                remote_tags = set()
                for rline in remote_tag_lines:
                    rparts = rline.split()
                    if len(rparts) >= 2 and rparts[1].startswith("refs/tags/"):
                        rtag = rparts[1][len("refs/tags/"):].split("^{}")[0]
                        remote_tags.add(rtag)

                local_tags_res = proc.git(
                    ["for-each-ref", "--format=%(refname:short) %(objecttype)", "refs/tags/v*"],
                    cwd=repo_root,
                    check=False,
                )
                if local_tags_res.ok:
                    local_release_tags = [
                        tline.split()[0]
                        for tline in local_tags_res.stdout.splitlines()
                        if tline.strip() and tline.split()[-1] == "tag"
                    ]
                    unpushed_tags = [t for t in local_release_tags if t not in remote_tags]
                    if unpushed_tags:
                        print(f"[WARN] Local release tag(s) not present on origin: {', '.join(unpushed_tags)}. "
                              "Push with: git push origin --tags")
                        warnings += 1

        release_commits = proc.git(["log", "--grep=^release: v", "--format=%H %s"], cwd=repo_root, check=False)
        if release_commits.ok:
            for rline in release_commits.stdout.splitlines():
                if not rline.strip():
                    continue
                rparts = rline.split(maxsplit=1)
                if len(rparts) < 2:
                    continue
                sha, subject = rparts
                m = re.match(r"^release:\s+(v\d+\.\d+\.\d+)\b", subject)
                if m:
                    expected_tag = m.group(1)
                    tag_check = proc.git(
                        ["tag", "-l", "--format=%(refname:short) %(objecttype)", expected_tag],
                        cwd=repo_root,
                        check=False,
                    )
                    has_tag = tag_check.ok and tag_check.stdout.strip().startswith(expected_tag)
                    if not has_tag:
                        print(f"[WARN] Release commit {sha[:7]} ({subject}) has no matching annotated tag '{expected_tag}'. "
                              f"Create with: git tag -a {expected_tag} -m \"release: {expected_tag}\" {sha[:7]}")
                        warnings += 1

    # Check per-machine diagnostics committed before the directory ignored itself
    from alongkit import gitgates
    tracked_diag = gitgates.tracked_diagnostics(repo_root)
    if tracked_diag:
        print(f"[WARN] {len(tracked_diag)} per-machine diagnostics file(s) tracked in git "
              f"({', '.join(tracked_diag[:3])}{', ...' if len(tracked_diag) > 3 else ''}). "
              "Run `along migrate --apply` (or `git rm --cached` them) and commit.")
        warnings += 1

    # Orphan blackboards
    orphans = lifecycle.orphan_blackboards(repo_root)
    if orphans:
        print(f"[WARN] {len(orphans)} orphan blackboard(s) in .along/.session/: "
              + ", ".join(f"{slug} ({why})" for slug, why in orphans)
              + ". Run `along scratch purge <slug>`: it archives the record into the session log first.")
        warnings += 1
    else:
        print("[OK] No orphan blackboards.")

    # Stale bindings and in-progress issues nobody is bound to
    stale = session.gc_bindings(repo_root, dry_run=True)
    if stale:
        print(f"[WARN] {len(stale)} stale session binding(s) (older than {session.BINDING_MAX_AGE_HOURS} h "
              f"or without a blackboard): {', '.join(stale)}. Run `along session gc`.")
        warnings += 1
    bound = {str(b.get("slug")) for b in session.list_bindings(repo_root) if b.get("slug")}
    unbound = [i["slug"] for i in entities.scan_issues(repo_root) if i.get("status") == "in-progress"
               and i["slug"] not in bound]
    if unbound:
        print(f"[WARN] {len(unbound)} issue(s) in progress with no session bound: {', '.join(unbound)}. "
              "Resume with `along start <slug>`, close them out (`along session list`), or set them back "
              "to open (`along issue update <slug> --status open`).")
        warnings += 1

    # Check uncommitted changes belonging to wrapped issues
    from alongkit import closeout
    c_status = closeout.closeout_status(repo_root)
    wrapped_work = c_status["repository"].get("wrapped", {})
    if wrapped_work:
        total_wrapped_files = sum(len(files) for files in wrapped_work.values())
        print(f"[WARN] {total_wrapped_files} uncommitted file(s) belong to wrapped issue(s):")
        for wkey, wfiles in sorted(wrapped_work.items()):
            wslug = entities.parse_key(wkey)[1]
            print(f"  - {wkey} ({len(wfiles)} file(s)):")
            for wf in wfiles:
                print(f"      {wf}")
            paths_arg = " ".join(wfiles)
            print(f"    Commit with: along commit -i {wslug} --paths {paths_arg}")
            print(f"    Or close out: along session close {wslug}")
        warnings += 1

    # Check DECISIONS
    dec_dir = os.path.join(along_dir, "DECISIONS")
    dec_file = os.path.join(along_dir, "DECISIONS.md")
    if os.path.isdir(dec_dir):
        adr_count = len([f for f in os.listdir(dec_dir) if f.endswith(".md")])
        print(f"[OK] .along/DECISIONS/ modular ADR directory exists ({adr_count} records).")
    elif os.path.exists(dec_file):
        dec_content = textio.read_text(dec_file, strict=False)
        if "## ADR-" in dec_content:
            print("[OK] .along/DECISIONS.md uses decentralized ADR-YYYY-MM-DD--<slug> format.")
        else:
            print("[WARN] .along/DECISIONS.md uses legacy sequential numbering.")
            warnings += 1

    # Check obsolete CONTEXT.md
    context_file = os.path.join(along_dir, "CONTEXT.md")
    if os.path.exists(context_file):
        print("[WARN] .along/CONTEXT.md detected (deprecated in v2.2.0, recommend removal).")
        warnings += 1

    # Check AGENTS.md
    agents_file = os.path.join(repo_root, "AGENTS.md")
    if os.path.exists(agents_file):
        print("[OK] AGENTS.md exists.")
    else:
        print("[FAIL] Missing AGENTS.md at repository root.")
        errors += 1

    # Nested contexts outside any nested git repository
    nested = repo.find_unmarked_nested_contexts(repo_root)
    if nested:
        shown = ", ".join(repo.normalize_posix(repo.safe_relpath(p, repo_root)) for p in nested[:10])
        more = f" (+{len(nested) - 10} more)" if len(nested) > 10 else ""
        print(f"[WARN] {len(nested)} nested .along/ without .git found (possibly created by older Along "
              f"versions): {shown}{more}. Consolidate them into the root by hand, or mark an intentional "
              "one with '\"subproject\": {\"intentional\": true}' in its .along/config.json.")
        warnings += 1

    # Check VISION
    from alongkit import scaffold
    if scaffold.find_root_file(repo_root, scaffold.VISION_FILENAME) and os.path.isdir(along_dir):
        print("[WARN] Root VISION.md coexists with .along/. Run `along migrate --apply` to reconcile.")
        warnings += 1
    if scaffold.find_imported_vision_markers(repo_root):
        print("[WARN] .along/VISION.md has an unresolved 'along:imported-vision needs-restructure' "
              "section. Decompose it (scope/non-goals/roadmap stay; architecture -> docs/; "
              "backlog -> ISSUES/MILESTONES) and remove the markers.")
        warnings += 1
    for note in scaffold.find_root_notes(repo_root):
        print(f"[WARN] Root note {os.path.basename(note)} duplicates the Knowledge Base; route it "
              "into docs/topic--*.md, .along/VISION.md or entities (see /along-init).")
        warnings += 1

    # Check along CLI availability on PATH
    along_cmd = shutil.which("along") or (shutil.which("along.cmd") if sys.platform == "win32" else None)
    if along_cmd:
        print(f"[OK] 'along' CLI executable found on PATH: {along_cmd}")
    else:
        user_along_bin = os.path.join(os.path.expanduser("~"), ".along", "bin")
        print("[WARN] 'along' CLI is not found on PATH.")
        if sys.platform == "win32":
            print(f"       To fix: re-run install.ps1, or add '{user_along_bin}' to your User PATH.")
        else:
            print(f"       To fix: add 'export PATH=\"{user_along_bin}:$PATH\"' to your shell profile (~/.bashrc or ~/.zshrc).")
        warnings += 1

    # Check code-review-graph MCP server
    try:
        from along_graph_check import run_graph_check
        gc = run_graph_check(repo_root)
        if gc["status"] == "healthy":
            print(f"[OK] code-review-graph MCP server ready ({gc['package']}).")
        elif gc["status"] == "degraded":
            print(f"[WARN] code-review-graph MCP server: {gc['summary']}")
            warnings += 1
        else:
            print(f"[FAIL] code-review-graph MCP server: {gc['summary']}")
            errors += 1
    except (OSError, ValueError, AttributeError, RuntimeError) as exc:
        print(f"[WARN] Could not run MCP health check: {exc}")
        warnings += 1

    # Check global user pack repository (~/.along/user-pack/)
    user_pack_dir = os.path.expanduser("~/.along/user-pack")
    if os.path.isdir(user_pack_dir):
        if os.path.isdir(os.path.join(user_pack_dir, ".git")):
            remote_check = proc.git(["remote", "get-url", "origin"], cwd=user_pack_dir, check=False)
            if not remote_check.ok or not remote_check.stdout.strip():
                print("[WARN] Global user pack (~/.along/user-pack) has no git remote configured.")
                warnings += 1
            st_check = proc.git(["status", "--porcelain"], cwd=user_pack_dir, check=False)
            if st_check.ok and st_check.stdout.strip():
                print("[WARN] Global user pack (~/.along/user-pack) has uncommitted changes.")
                warnings += 1
            else:
                print("[OK] Global user pack (~/.along/user-pack) repository clean.")
        else:
            print("[WARN] Global user pack (~/.along/user-pack) is not a git repository.")
            warnings += 1

    # Declared test policy
    from alongkit import verify
    policy = verify.load_policy(repo_root)
    problems = verify.policy_problems(repo_root, policy)
    if problems:
        print("[FAIL] Verify policy invalid: " + "; ".join(problems))
        errors += 1
    elif policy.tests == verify.TESTS_NONE:
        print(f"[WARN] Verify: {policy.describe()}")
        warnings += 1
    else:
        print(f"[OK] Verify: {policy.describe()}")

    # Gate friction
    from alongkit import gatestats
    from alongkit.hooks import config as hook_config
    shadowed = hook_config.load_config(repo_root).overridden_gates()
    if shadowed:
        print(f"[WARN] Gates set to shadow by config: {', '.join(shadowed)}")
        warnings += 1
    for row in gatestats.most_bypassed(gatestats.collect(repo_root)):
        print(f"[WARN] Gate '{row.gate}' bypassed {row.bypassed}x vs blocked {row.blocked}x "
              f"({row.bypass_ratio * 100:.0f}%): review whether it is wrong or too strict ('along gates stats').")
        warnings += 1

    # Gate strictness profiles
    from alongkit import profiles
    active_prof, prof_source = profiles.resolve_active_profile_with_source(repo_root)
    h_config = hook_config.load_config(repo_root)
    gate_table = hook_config.load_gate_profiles_table(repo_root)
    counts = {"block": 0, "warn": 0, "off": 0}
    matrix_rows = []
    width = max((len(gid) for gid in gate_table), default=20)
    for gid in sorted(gate_table.keys()):
        mode = h_config.get_gate_mode(gid)
        sev = "block" if mode == hook_config.HookMode.ENFORCE else ("off" if mode == hook_config.HookMode.OFF else "warn")
        counts[sev] += 1
        matrix_rows.append((gid, sev))
    print(f"\n--- Gate Strictness Profile: {active_prof} (source: {prof_source}) ---")
    print(f"[OK] Gate strictness profile: {active_prof} (source: {prof_source}) - "
          f"{counts['block']} block, {counts['warn']} warn, {counts['off']} off.")
    print(f"Gate strictness matrix ({len(matrix_rows)} gates):")
    for gid, sev in matrix_rows:
        print(f"  {gid.ljust(width)}  [{sev.upper()}]")

    # Documentation Routing Tree Compliance
    from alongkit import repochecks
    doc_candidates = []
    for d_root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in repo.IGNORED_DIRS and not d.startswith(".")]
        for f in files:
            if f.lower() in ("readme.md", "agents.md"):
                doc_candidates.append(repo.canonical_relpath(os.path.join(d_root, f), repo_root))
    doc_findings = repochecks.check_doc_routing_compliance(
        doc_candidates,
        lambda p: textio.read_text(os.path.join(repo_root, p), strict=False),
        {},
    )
    if doc_findings:
        print(f"[WARN] Documentation Routing Tree: {len(doc_findings)} issue(s) detected [gate: doc-routing-compliance]:")
        for loc, msg in doc_findings:
            print(f"       - {loc}: {msg}")
        warnings += 1
    else:
        print("[OK] Documentation Routing Tree: README.md overview boundaries and AGENTS.md references clean.")

    warnings, _ = _doctor_zombie_docs_checks(repo_root, warnings)
    warnings, _ = _doctor_stub_issues_checks(repo_root, warnings)

    errors, warnings = _doctor_runtime_checks(repo_root, errors, warnings)

    print(f"\nDoctor Summary: {errors} errors, {warnings} warnings.")
    sys.exit(1 if errors > 0 else 0)
