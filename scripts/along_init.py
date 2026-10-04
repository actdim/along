#!/usr/bin/env python3
"""
along_init.py - Deterministic scaffolder behind /along-init.

Does every mechanical part of initialization in one idempotent run, so an agent
cannot skip a step:
- AGENTS.md managed block: FULL at an architecture root, a short REF inside a nested
  folder of the same git working tree; a hand-written file keeps its text below the
  block under `## Project specifics`.
- CLAUDE.md import line, .gitattributes merge lines.
- `.along/` skeleton (create-only, existing state is never overwritten).
- Root VISION.md reconciled into `.along/VISION.md` (moved, deduplicated, or merged
  under a `needs-restructure` marker); links to it repointed.
- Pipeline: `along rules attach`, `along git setup`, `along hook install --runtime all`,
  `along migrate --apply` (each can be skipped).

Judgment work stays with the agent (see skills/along-init/SKILL.md): decomposing an
imported VISION section, routing root notes, filling Project specifics, and the
re-run questions printed at the end.

Usage:
  along init [TARGET_DIR] [--dry-run] [--json] [--no-rules] [--no-git] [--no-hooks] [--no-migrate]
  python scripts/along_init.py [TARGET_DIR] [options]
"""

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()

from alongkit import migration, proc, repo, scaffold, textio
from along_update import get_global_skill_paths, get_source_protocol_paths

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

GITATTRIBUTES_LINES = (
    "*.md text eol=lf",
    ".along/HISTORY.md merge=union",
    ".along/DECISIONS.md merge=union",
)

ISSUES_BOARD = "# Active Issues\n\n## Active\n\n## Backlog\n\n## Done (recent)\n"
GLOSSARY = ("# Glossary\n\n_Domain terms. Add a term when you introduce or clarify it._\n\n"
            "<!-- - **Term** - definition. -->\n")
HISTORY = ("# History\n\n_Index of sessions (newest last). One line per session:_\n"
           "_`<YYYY-MM-DD> - <slug> - <agent> - <summary> - <relative link>`_\n")

RERUN_QUESTIONS = (
    "Rebuild the code graph from scratch (`along graph-sync --full`)?",
    "Refresh the Knowledge Base from README.md and docs/ (`/along-kb-sync`)?",
    "Review `.code-review-graph-ignore` exclusions (`along graph-check`)?",
)


def resolve_init_target(explicit):
    """Explicit directory > git top-level of the cwd > cwd."""
    if explicit:
        return os.path.abspath(explicit)
    res = proc.git(["rev-parse", "--show-toplevel"], cwd=os.getcwd())
    top = (res.stdout or "").strip() if res.ok else ""
    return os.path.abspath(top) if top else os.path.abspath(os.getcwd())


def load_protocol_text(root):
    candidates = [os.path.join(root, "skills", "along-init", "protocol.md")]
    candidates += get_source_protocol_paths() + get_global_skill_paths()
    for path in candidates:
        if os.path.isfile(path):
            return textio.read_text(path, strict=False).strip()
    return None


def _note(report, key, path, root):
    report[key].append(repo.normalize_posix(repo.safe_relpath(path, root)))


def write_if_missing(mig, path, text, report, root):
    if os.path.exists(path):
        _note(report, "untouched", path, root)
        return
    mig.makedirs(os.path.dirname(path))
    mig.write(path, text)
    _note(report, "created", path, root)


def scaffold_agents_md(mig, root, protocol_text, report):
    path = os.path.join(root, "AGENTS.md")
    info = scaffold.protocol_block_for(root, protocol_text)
    report["protocol_variant"] = info["variant"]
    report["protocol_ref"] = info["ref"]
    if not os.path.isfile(path):
        mig.write(path, scaffold.new_agents_md(info["block"]))
        _note(report, "created", path, root)
        return
    existing = textio.read_text(path)
    had_markers = bool(scaffold.MANAGED_BLOCK_RE.search(existing))
    updated = scaffold.merge_protocol_block(existing, info["block"])
    if updated == existing:
        _note(report, "untouched", path, root)
        return
    mig.write(path, updated)
    _note(report, "updated", path, root)
    if not had_markers:
        report["adopted_handwritten_agents_md"] = True


def scaffold_claude_md(mig, root, report):
    path = os.path.join(root, "CLAUDE.md")
    existing = textio.read_text(path) if os.path.isfile(path) else None
    updated = scaffold.ensure_claude_import(existing)
    if existing == updated:
        _note(report, "untouched", path, root)
        return
    mig.write(path, updated)
    _note(report, "updated" if existing is not None else "created", path, root)


def scaffold_gitattributes(mig, root, report):
    path = os.path.join(root, ".gitattributes")
    existing = textio.read_text(path) if os.path.isfile(path) else ""
    present = {line.strip() for line in existing.splitlines()}
    missing = [line for line in GITATTRIBUTES_LINES if line not in present]
    if not missing:
        _note(report, "untouched", path, root)
        return
    prefix = existing if not existing or existing.endswith("\n") else existing + "\n"
    mig.write(path, prefix + "\n".join(missing) + "\n")
    _note(report, "updated" if existing else "created", path, root)


def scaffold_state_dir(mig, root, report):
    along_dir = os.path.join(root, repo.STATE_DIR)
    year = str(date.today().year)
    mig.makedirs(along_dir)
    for sub in (os.path.join("ISSUES", "done"), "DECISIONS", os.path.join("SESSIONS", year)):
        directory = os.path.join(along_dir, sub)
        if not os.path.isdir(directory):
            mig.makedirs(directory)
            mig.touch(os.path.join(directory, ".gitkeep"))
            _note(report, "created", directory, root)
    write_if_missing(mig, os.path.join(along_dir, "ISSUES.md"), ISSUES_BOARD, report, root)
    write_if_missing(mig, os.path.join(along_dir, "GLOSSARY.md"), GLOSSARY, report, root)
    write_if_missing(mig, os.path.join(along_dir, "HISTORY.md"), HISTORY, report, root)


def scaffold_vision(mig, root, report):
    along_vision = os.path.join(root, repo.STATE_DIR, scaffold.VISION_FILENAME)
    root_vision = scaffold.find_root_file(root, scaffold.VISION_FILENAME)
    if root_vision and not os.path.isdir(os.path.dirname(along_vision)):
        # Only reachable in a dry run on a fresh repository: `.along/` is not on disk yet.
        report["vision"] = {"action": "moved", "source": repo.normalize_posix(
            repo.safe_relpath(root_vision, root)), "links": []}
        return
    if root_vision:
        result = scaffold.reconcile_root_vision(root, mig)
        report["vision"] = {
            "action": result["action"],
            "source": repo.normalize_posix(repo.safe_relpath(str(result["source"]), root)),
            "links": [repo.normalize_posix(repo.safe_relpath(p, root)) for p in result["links"]],
        }
        return
    write_if_missing(mig, along_vision, scaffold.vision_template(), report, root)


def run_pipeline(root, args, report):
    """The CLI steps an agent used to forget. Each one is idempotent."""
    along_exec = os.path.join(SCRIPTS_DIR, "along_exec.py")
    steps = []
    if not args.no_rules:
        steps.append(("rules attach", [sys.executable, along_exec, "rules", "attach"]))
    if not args.no_git and scaffold.is_git_boundary(root):
        steps.append(("git setup", [sys.executable, along_exec, "git", "setup"]))
    if not args.no_hooks:
        steps.append(("hook install", [sys.executable, along_exec, "hook", "install", "--runtime", "all"]))
    if not args.no_migrate:
        steps.append(("migrate", [sys.executable, os.path.join(SCRIPTS_DIR, "migrate_protocol.py"),
                                  root, "--apply"]))
    for name, cmd in steps:
        if args.dry_run:
            report["pipeline"].append({"step": name, "status": "would run"})
            continue
        if not args.json:
            print(f"-> {name}...")
        if args.json:
            res = proc.run_capture(cmd, cwd=root)
            code = res.returncode
        else:
            code = proc.run_passthrough(cmd, cwd=root)
        report["pipeline"].append({"step": name, "status": "ok" if code == 0 else f"exit {code}"})


def print_report(report):
    print("==================================================")
    print(f"-> Along init: {report['root']}" + ("  (dry run, nothing written)" if report["dry_run"] else ""))
    variant = report["protocol_variant"]
    print(f"   Protocol block: {variant}" + (f" -> {report['protocol_ref']}" if report["protocol_ref"] else ""))
    if report.get("adopted_handwritten_agents_md"):
        print("   AGENTS.md had no markers: protocol placed on top, original text kept under '## Project specifics'.")
    for key, label in (("created", "CREATED"), ("updated", "UPDATED"), ("untouched", "UNTOUCHED")):
        for item in report[key]:
            print(f"   {label:<10} {item}")
    vision = report.get("vision")
    if vision and vision["action"] not in ("none",):
        print(f"   VISION     {vision['source']} -> .along/VISION.md ({vision['action']}; source deleted)")
        for link in vision["links"]:
            print(f"   LINKS      repointed in {link}")
    for step in report["pipeline"]:
        print(f"   PIPELINE   {step['step']}: {step['status']}")
    todo = []
    if vision and vision["action"] == "merged-needs-restructure":
        todo.append("Decompose the 'along:imported-vision' section of .along/VISION.md (scope / non-goals / "
                    "roadmap stay; architecture -> docs/topic--architecture.md; backlog -> ISSUES / "
                    "MILESTONES), then remove its markers.")
    for note in report["root_notes"]:
        todo.append(f"Route root note {note} into docs/topic--*.md, .along/VISION.md or entities, then delete it.")
    if report.get("adopted_handwritten_agents_md"):
        todo.append("Review '## Project specifics' in AGENTS.md: keep conventions, move protocol duplicates out.")
    if todo:
        print("-> AGENT ACTIONS (complete before reporting init as done):")
        for item in todo:
            print(f"   - {item}")
    if report["rerun"]:
        print("-> RE-RUN QUESTIONS (ask the user, then act on each answer):")
        for question in RERUN_QUESTIONS:
            print(f"   - {question}")
    print("==================================================")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Along deterministic repository initialization.")
    parser.add_argument("target", nargs="?", default=None,
                        help="Directory to initialize (default: git top-level, else cwd)")
    parser.add_argument("--dry-run", action="store_true", help="Report the plan without writing")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--no-rules", action="store_true", help="Skip `along rules attach`")
    parser.add_argument("--no-git", action="store_true", help="Skip `along git setup`")
    parser.add_argument("--no-hooks", action="store_true", help="Skip `along hook install`")
    parser.add_argument("--no-migrate", action="store_true", help="Skip `along migrate --apply`")
    args = parser.parse_args(argv)

    root = resolve_init_target(args.target)
    if not os.path.isdir(root):
        print(f"[Error] Not a directory: {root}", file=sys.stderr)
        return 2
    protocol_text = load_protocol_text(root)
    if not protocol_text:
        print("[Error] Could not locate skills/along-init/protocol.md (local, ALONG_PROTOCOL_SOURCE, "
              "or global skills).", file=sys.stderr)
        return 1

    report = {"root": root, "dry_run": args.dry_run,
              "rerun": os.path.isdir(os.path.join(root, repo.STATE_DIR)),
              "created": [], "updated": [], "untouched": [], "pipeline": [],
              "protocol_variant": "", "protocol_ref": "", "vision": None, "root_notes": []}
    quiet = (lambda _msg: None) if args.json else print
    mig = migration.Migration(root, dry_run=args.dry_run,
                              state_dir=os.path.join(root, repo.STATE_DIR), printer=quiet)

    scaffold_agents_md(mig, root, protocol_text, report)
    scaffold_claude_md(mig, root, report)
    scaffold_gitattributes(mig, root, report)
    scaffold_state_dir(mig, root, report)
    scaffold_vision(mig, root, report)
    write_if_missing(mig, os.path.join(root, "docs", "INDEX.md"),
                     scaffold.minimal_docs_index(date.today().isoformat()), report, root)
    report["root_notes"] = [os.path.basename(p) for p in scaffold.find_root_notes(root)]

    if mig.errors:
        report["errors"] = list(mig.errors)
    else:
        run_pipeline(root, args, report)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    failed = bool(mig.errors) or any(s["status"] not in ("ok", "would run") for s in report["pipeline"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
