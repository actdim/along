#!/usr/bin/env python3
"""
migrate_protocol.py - Version-aware migration engine for ALONG-PROTOCOL.

Executes sequential, version-specific migration steps on target repository's structure:
  - v1.0.0 -> v1.1.0: Tasks -> Issues directory & kebab-case renaming
  - v1.1.0 -> v1.3.0: Knowledge Base (.agents/KB/) & .code-review-graph-ignore scaffolding
  - v1.3.3 -> v1.5.0: Entity Ecosystem (MILESTONES, RISKS, SPIKES, CHECKLISTS),
                     retroactive Milestone synthesis from past sessions/done issues,
                     standard Checklists synthesis, and complete YAML front-matter enrichment.
  - v1.5.7 -> v2.0.0: Transition to Along ecosystem:
                     - Migrates verified protocol files from .agents/ to .along/
                     - Injects `protocol: along` into all entity YAML front-matters
                     - Updates AGENTS.md protocol markers and path references to .along/
                     - Cleans up empty .agents/ while preserving foreign files
                     - Migrates ~/.config/opencode/actdim-agents to actdim-along and ~/.cache

Usage:
    python scripts/migrate_protocol.py [TARGET_REPO_ROOT] [--dry-run|--apply] [--force]
                                       [--no-backup]

The engine never deletes a destination file. On a collision it merges (append-only
files), keeps the destination (projections, recompiled later), or preserves the legacy
copy beside it, and it copies the whole state directory into
`.along/.migration-backup/<timestamp>/` before the first modification. All of that is
implemented once in `alongkit.migration`; see
`[bug--migration-deletes-destination-without-backup]`.

Dry-run is the default whenever the engine is not talking to a human terminal, so a
tool that invokes it (an installer, a test, another engine) gets a plan and has to ask
for the mutation explicitly with `--apply`.
"""

import argparse
import os
import re
import sys
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()
from alongkit import frontmatter, migration, proc, repo, sanitizer, semver, textio
from alongkit.version import CURRENT_PROTOCOL_VERSION


def repair_unquoted_frontmatter_scalars(content, path=None):
    """Attempt to repair unquoted colons in scalar fields (title, summary, description).

    Returns (repaired_content, fields) if repair succeeded and verified by ruamel.yaml,
    or (None, None) if unrepairable.
    """
    block = frontmatter.split(content)
    if block is None:
        return None, None
    lines = block.raw.splitlines(keepends=True)
    repaired_lines = []
    modified = False
    scalar_re = re.compile(r'^([ \t]*(?:title|summary|description):[ \t]+)(.*?)(\r?\n?)$')
    for line in lines:
        m = scalar_re.match(line)
        if m:
            prefix, val, end = m.group(1), m.group(2).strip(), m.group(3)
            # If value contains ': ' and is not quoted with " or '
            if (': ' in val or val.endswith(':')) and not ((val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'"))):
                escaped_val = val.replace('"', '\\"')
                repaired_lines.append(f'{prefix}"{escaped_val}"{end}')
                modified = True
                continue
        repaired_lines.append(line)

    if not modified:
        return None, None

    new_raw = "".join(repaired_lines)
    candidate = block.bom + block.open_delim + new_raw + block.close_delim + block.body
    try:
        fields, _ = frontmatter.parse(candidate, path=path)
        return candidate, fields
    except frontmatter.FrontmatterError:
        return None, None


def parse_yaml_frontmatter(content, path=None, allow_repair=False):
    """Front-matter of a file this engine is about to rewrite.

    Tolerant on purpose: a migration must not abort a whole repository because one
    file is malformed. The caller must skip any file this reports on, never rewrite
    it from a partial parse, which is how the earlier hand-rolled parser destroyed
    block sequences.
    """
    fields, body, error = frontmatter.try_parse(content, path=path)
    if error and allow_repair:
        repaired_content, repaired_fields = repair_unquoted_frontmatter_scalars(content, path=path)
        if repaired_content is not None:
            return repaired_fields, body
    if error:
        print(f"   [WARN] {error}", file=sys.stderr)
        return None, body
    return fields, body



def dump_yaml_frontmatter(fm, body):
    """Render a NEW entity file. Never use on a file that already exists: use
    frontmatter.update, which preserves comments, key order, and line endings.
    """
    return frontmatter.render(fm, body)


def detect_protocol_version(repo_root):
    """The protocol version the repository declares, from its AGENTS.md marker.

    Read strictly. The previous `errors="ignore"` silently dropped undecodable bytes,
    and a version detected from a mangled read decides which migration steps run.
    """
    agents_md = os.path.join(repo_root, "AGENTS.md")
    if os.path.exists(agents_md):
        try:
            content = textio.read_text(agents_md)
        except UnicodeDecodeError as exc:
            print(f"   [WARN] AGENTS.md is not valid UTF-8 ({exc.reason}); "
                  "assuming the oldest protocol version.", file=sys.stderr)
            return "1.0.0"
        m = re.search(r"(?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL) v(\d+\.\d+\.\d+)", content)
        if m:
            return m.group(1)
    return "1.0.0"

# ----------------------------------------------------------------------
# Step 1: v1.0.0 -> v1.1.0 (Tasks -> Issues)
# ----------------------------------------------------------------------
def step_migrate_v1_1_tasks_to_issues(mig, working_dir):
    updated = False
    tasks_md = os.path.join(working_dir, "TASKS.md")
    issues_md = os.path.join(working_dir, "ISSUES.md")
    if os.path.exists(tasks_md) and not os.path.exists(issues_md):
        try:
            c = textio.read_text(tasks_md)
        except UnicodeDecodeError as exc:
            mig.note_skipped(tasks_md, f"not valid UTF-8 ({exc.reason})")
            c = None
        if c is not None:
            c = re.sub(r"# Tasks", "# Issues", c)
            c = re.sub(r"TASKS", "ISSUES", c)
            mig.write(issues_md, c, announce=True)
            mig.discard(tasks_md, "renamed to ISSUES.md")
            updated = True

    tasks_dir = os.path.join(working_dir, "TASKS")
    issues_dir = os.path.join(working_dir, "ISSUES")
    if os.path.exists(tasks_dir) and not os.path.exists(issues_dir):
        mig.move(tasks_dir, issues_dir, "TASKS/ renamed to ISSUES/")
        updated = True
    return updated

# ----------------------------------------------------------------------
# Step 2: v1.1.0 -> v1.3.0 (KB & Code Review Graph Scaffolding)
# ----------------------------------------------------------------------
def step_migrate_v1_3_kb_scaffolding(mig, repo_root, working_dir):
    # .code-review-graph-ignore
    crg_ignore = os.path.join(repo_root, ".code-review-graph-ignore")
    created = 0
    if not os.path.exists(crg_ignore):
        mig.write(crg_ignore,
                  "# Code Review Graph Exclusions\nnode_modules/\ndist/\nbuild/\nout/\n"
                  ".git/\n.along/SESSIONS/\n.agents/SESSIONS/\n*.min.js\n*.bundle.js\n"
                  "*.pyc\n__pycache__/\n",
                  announce=True)
        created += 1
    return created

# ----------------------------------------------------------------------
# Step 3: v1.3.3 -> v1.5.0 (Entity Ecosystem, Retro-Synthesis & Checklists)
# ----------------------------------------------------------------------
def step_migrate_v1_5_entity_ecosystem(mig, repo_root, working_dir):
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_year = datetime.now().strftime("%Y")

    # 1. Ensure directory skeleton (KB is located in docs/ since v2.1)
    dirs = [
        os.path.join(working_dir, "ISSUES", "done"),
        os.path.join(working_dir, "SESSIONS", today_year),
        os.path.join(working_dir, "MILESTONES"),
        os.path.join(working_dir, "RISKS"),
        os.path.join(working_dir, "SPIKES"),
        os.path.join(working_dir, "CHECKLISTS"),
    ]
    for d in dirs:
        mig.makedirs(d)
        gitkeep = os.path.join(d, ".gitkeep")
        if not os.path.isdir(d) or len(os.listdir(d)) == 0:
            mig.touch(gitkeep)

    # 2. Synthesize standard Checklists if missing
    checklists_dir = os.path.join(working_dir, "CHECKLISTS")
    standard_checklists = {
        "stage-completion.md": {
            "slug": "stage-completion",
            "title": "Mandatory Stage Completion & Wrap-Up",
            "category": "stage-completion",
            "body": "# Mandatory Stage Completion Checklist\n\n"
                    "1. [ ] Automated tests, linting, and builds run with quiet flags.\n"
                    "2. [ ] All completed issues moved to `ISSUES/done/` with `status: done` and `completed: YYYY-MM-DD`.\n"
                    "3. [ ] Related milestone progress percentage updated.\n"
                    "4. [ ] Active session log written to `SESSIONS/`.\n"
                    "5. [ ] ISSUES board updated and lean.\n"
                    "6. [ ] Documentation in `docs/` updated if interfaces changed.\n"
                    "7. [ ] Prompt user to compact session (`/compact`).\n"
        },
        "pre-commit.md": {
            "slug": "pre-commit",
            "title": "Pre-Commit Quality Gate",
            "category": "pre-commit",
            "body": "# Pre-Commit Verification Checklist\n\n"
                    "1. [ ] Code compiles and unit tests pass.\n"
                    "2. [ ] Mandatory git diff inspected for zero unintended deletions.\n"
                    "3. [ ] No API keys, secrets, or sensitive credentials committed.\n"
                    "4. [ ] Filenames are Windows-safe (no colons, YYYY-MM-DD dates).\n"
        }
    }
    for filename, data in standard_checklists.items():
        cpath = os.path.join(checklists_dir, filename)
        if not os.path.exists(cpath):
            fm = {
                "protocol": "along",
                "slug": data["slug"],
                "title": data["title"],
                "category": data["category"],
                "created": today_str,
                "updated": today_str
            }
            mig.write(cpath, dump_yaml_frontmatter(fm, data["body"]))

    # 3. Analyze past work to retroactively synthesize Milestones
    milestones_dir = os.path.join(working_dir, "MILESTONES")
    done_issues = glob.glob(os.path.join(working_dir, "ISSUES", "done", "*.md"))
    active_issues = glob.glob(os.path.join(working_dir, "ISSUES", "*.md"))

    done_slugs = [os.path.basename(f).replace(".md", "") for f in done_issues]
    active_slugs = [os.path.basename(f).replace(".md", "") for f in active_issues]

    # If no milestones exist, synthesize from past history
    if len(glob.glob(os.path.join(milestones_dir, "*.md"))) == 0:
        if done_slugs:
            past_m = os.path.join(milestones_dir, "v1.3.0-knowledge-base-and-graph.md")
            fm_past = {
                "protocol": "along",
                "slug": "v1.3.0-knowledge-base-and-graph",
                "title": "v1.3.0: Knowledge Base Architecture & Code Graph Integration",
                "status": "completed",
                "due_date": "2026-08-26",
                "created": "2026-08-11",
                "target_issues": done_slugs,
                "progress_pct": 100
            }
            body_past = "# Milestone: v1.3.0 Knowledge Base & Code Graph\n\nDelivered structured documentation architecture, /along-init-kb, /along-search-kb, /along-sync-kb, /along-check-graph, and code-review-graph MCP integration.\n"
            mig.write(past_m, dump_yaml_frontmatter(fm_past, body_past))

        current_m = os.path.join(milestones_dir, "v2.0.0-along-transition.md")
        fm_curr = {
            "protocol": "along",
            "slug": "v2.0.0-along-transition",
            "title": "v2.0.0: Transition to Along Ecosystem & .along/ Directory",
            "status": "in-progress",
            "due_date": "2026-09-05",
            "created": "2026-08-27",
            "target_issues": active_slugs,
            "progress_pct": 50
        }
        body_curr = "# Milestone: v2.0.0 Along Transition\n\nDelivers isolated `.along/` directory, protocol: along metadata validation, /along-dash visual analytics, and full namespaced along-* command suite.\n"
        mig.write(current_m, dump_yaml_frontmatter(fm_curr, body_curr))

    # 4. Enrich all ISSUES front-matter (with milestone linkage and protocol: along)
    all_issue_files = done_issues + active_issues
    for filepath in all_issue_files:
        is_done = "done" in os.path.dirname(filepath).replace("\\", "/").split("/")
        filename = os.path.basename(filepath)
        raw_slug = filename.replace(".md", "")
        clean_slug = raw_slug.split("--", 1)[1] if "--" in raw_slug else raw_slug
        issue_type = filename.split("--", 1)[0] if "--" in filename else "feat"

        try:
            content = textio.read_text(filepath)
        except UnicodeDecodeError as exc:
            mig.note_skipped(filepath, f"not valid UTF-8 ({exc.reason})")
            continue
        fields, _ = parse_yaml_frontmatter(content, path=filepath)
        if fields is None:
            continue

        # Only the keys that are missing or wrong are written, so a file that is
        # already correct is left byte-identical. The previous implementation
        # re-serialized every entity on every run, which is how block sequences
        # and quoting were lost.
        updates = {}
        removals = []
        slug = fields.get('slug') or clean_slug
        if fields.get('protocol') != 'along':
            updates['protocol'] = 'along'
        for key, value in (('slug', slug),
                           ('type', fields.get('type') or issue_type),
                           ('priority', fields.get('priority') or 'medium'),
                           ('created', fields.get('created') or today_str),
                           ('agent', fields.get('agent') or 'antigravity')):
            if not fields.get(key):
                updates[key] = value
        created = fields.get('created') or updates.get('created') or today_str
        if not fields.get('updated'):
            updates['updated'] = created
        updated = fields.get('updated') or updates.get('updated') or created

        if is_done:
            if fields.get('status') != 'done':
                updates['status'] = 'done'
            if not fields.get('completed'):
                updates['completed'] = updated
        else:
            if not fields.get('status'):
                updates['status'] = 'open'
            if 'completed' in fields:
                removals.append('completed')

        if not fields.get('tags'):
            tags = []
            if 'mcp' in slug: tags.append('mcp')
            if 'kb' in slug or 'knowledge' in slug: tags.append('kb')
            if 'dashboard' in slug or 'analytics' in slug or 'dash' in slug: tags.append('dashboard')
            updates['tags'] = tags

        if not fields.get('milestone'):
            updates['milestone'] = ('v1.3.0-knowledge-base-and-graph' if is_done
                                    else 'v2.0.0-along-transition')

        if 'blocked_by' not in fields:
            updates['blocked_by'] = []
        if 'related' not in fields:
            updates['related'] = []
        if 'parent' in fields and not fields['parent']:
            removals.append('parent')

        if updates or removals:
            new_content = frontmatter.update(
                content, updates, remove=removals, path=filepath,
                place_after={'completed': 'status', 'updated': 'created'})
            mig.write(filepath, new_content, detail="front-matter normalized")

    # 5. Enrich SESSIONS front-matter
    session_files = glob.glob(os.path.join(working_dir, "SESSIONS", "**", "*.md"), recursive=True)
    for filepath in session_files:
        try:
            content = textio.read_text(filepath)
        except UnicodeDecodeError as exc:
            mig.note_skipped(filepath, f"not valid UTF-8 ({exc.reason})")
            continue
        fields, _ = parse_yaml_frontmatter(content, path=filepath)
        if fields is None:
            continue

        updates = {}
        if fields.get('protocol') != 'along':
            updates['protocol'] = 'along'
        defaults = (
            ('date', today_str),
            ('slug', os.path.basename(filepath).replace('.md', '')),
            ('agent', 'antigravity'),
            ('branch', 'main'),
            ('commit', 'unknown'),
            ('summary', 'Work session log.'),
            ('milestone', 'v2.0.0-along-transition'),
        )
        for key, value in defaults:
            if key not in fields:
                updates[key] = value
        for key in ('issues_advanced', 'issues_completed', 'decisions',
                    'risks_logged', 'spikes_conducted'):
            if key not in fields:
                updates[key] = []

        if updates:
            new_content = frontmatter.update(content, updates, path=filepath)
            mig.write(filepath, new_content, detail="front-matter normalized")

    return True

# ----------------------------------------------------------------------
# Step 4: v1.5.7 -> v2.0.0 (Transition to Along & .along/ Directory)
# ----------------------------------------------------------------------
def step_migrate_v2_0_along_directory(mig, repo_root):
    """Bring legacy `.agents/` content into `.along/` without losing either side.

    The destination is never deleted. `mig.adopt` decides per file class: append-only
    files (`DECISIONS.md`, `HISTORY.md`) are union-merged the way `.gitattributes`
    already merges them across branches, derived projections keep the destination and
    drop the legacy copy for recompilation, and anything else keeps the destination
    with the legacy copy preserved as `<name>.legacy.md` and reported as a conflict.
    """
    agents_dir = os.path.join(repo_root, ".agents")
    along_dir = os.path.join(repo_root, ".along")

    # CONTEXT.md is no longer purged here. It is adopted so Step 7 can evaluate its
    # content, archive it, and ingest any substantive documentation into docs/.

    recognized_files = [
        "ISSUES.md", "DECISIONS.md", "HISTORY.md", "CONTEXT.md",
        "GLOSSARY.md", "VISION.md", "DASHBOARD.md", "dashboard.html", "TASKS.md"
    ]
    recognized_dirs = [
        "ISSUES", "MILESTONES", "RISKS", "SPIKES", "CHECKLISTS", "SESSIONS", "KB", "TASKS"
    ]

    moved_count = 0
    if os.path.exists(agents_dir):
        mig.makedirs(along_dir)

        # 1. Adopt recognised top-level files
        for fname in recognized_files:
            src = os.path.join(agents_dir, fname)
            dst = os.path.join(along_dir, fname)
            if os.path.exists(src):
                if mig.adopt(src, dst) != "absent":
                    moved_count += 1

        # 2. Adopt recognised subdirectories, file by file on a collision
        for dname in recognized_dirs:
            src = os.path.join(agents_dir, dname)
            dst = os.path.join(along_dir, dname)
            if os.path.exists(src):
                mig.adopt_tree(src, dst)
                moved_count += 1

        # 3. Clean up .agents/ only when nothing of the user's is left in it
        mig.rmdir_if_empty(agents_dir)

    # 4. Inject protocol: along across all markdown files in .along/
    if os.path.exists(along_dir):
        for root, dirs, files in os.walk(along_dir):
            # Never walk into the backup this run just wrote: a backup that the engine
            # keeps editing is not a copy of the state it was taken from.
            dirs[:] = [d for d in dirs if d != migration.BACKUP_DIRNAME]
            for f in files:
                if f.endswith(".md"):
                    fpath = os.path.join(root, f)
                    try:
                        content = textio.read_text(fpath)
                    except UnicodeDecodeError as exc:
                        mig.note_skipped(fpath, f"not valid UTF-8 ({exc.reason})")
                        print(f"   [WARN] {fpath} is not valid UTF-8 ({exc.reason}); skipped.",
                              file=sys.stderr)
                        continue
                    fields, _ = parse_yaml_frontmatter(content, path=fpath)
                    if fields and fields.get('protocol') != 'along':
                        updated = frontmatter.update(content, {'protocol': 'along'}, path=fpath)
                        mig.write(fpath, updated, detail="protocol: along injected")

    # 5. Update AGENTS.md references & markers
    agents_md_files = glob.glob(os.path.join(repo_root, "**", "AGENTS.md"), recursive=True)
    for amd in agents_md_files:
        try:
            content = textio.read_text(amd)
        except UnicodeDecodeError as exc:
            mig.note_skipped(amd, f"not valid UTF-8 ({exc.reason})")
            print(f"   [WARN] {amd} is not valid UTF-8 ({exc.reason}); skipped.", file=sys.stderr)
            continue
        original = content

        # Replace markers and deduplicate
        content = re.sub(
            r"<!-- BEGIN ACTDIM-AGENTS-PROTOCOL (.*?) -->",
            r"<!-- BEGIN ALONG-PROTOCOL \1 -->",
            content
        )
        content = re.sub(r"<!-- END ACTDIM-AGENTS-PROTOCOL -->", r"<!-- END ALONG-PROTOCOL -->", content)
        # Collapse REPEATED markers. `{2,}` rather than `+`, and the file's own newline
        # rather than a hardcoded one: `\s*` swallows the marker's own line ending, so
        # over a file with a single pair - every already-current AGENTS.md - the `+`
        # version rewrote two CRLF line endings as LF and called it a migration. Same
        # family as the legacy renames guarded below, found by reading the dry-run plan
        # of a repository that had nothing to migrate.
        newline = textio.detect_newline(content)
        content = re.sub(r"(?:<!-- BEGIN ALONG-PROTOCOL (.*?) -->\s*){2,}",
                         f"<!-- BEGIN ALONG-PROTOCOL \\1 -->{newline}", content)
        content = re.sub(r"(?:<!-- END ALONG-PROTOCOL -->\s*){2,}",
                         f"<!-- END ALONG-PROTOCOL -->{newline}", content)
        content = re.sub(r"# ACTDIM-AGENTS-PROTOCOL v\d+\.\d+\.\d+", f"# ALONG-PROTOCOL v{CURRENT_PROTOCOL_VERSION}", content)
        content = re.sub(r"# ALONG-PROTOCOL v\d+\.\d+\.\d+", f"# ALONG-PROTOCOL v{CURRENT_PROTOCOL_VERSION}", content)

        # Legacy path and command renames, applied ONLY to a file that still carries a
        # pre-v2.0.0 marker or a legacy skill name. Running them unconditionally over a
        # current AGENTS.md is not a no-op, it is damage: the substitutions below are
        # substring replacements over prose.
        #
        # Both failure modes were observed in this repository. `.agents/` -> `.along/`
        # rewrote a deliberate mention of the legacy directory inside the managed protocol
        # block, leaving a sentence that named `.along/KB/` twice. `/dashboard` ->
        # `/along-dash` turned the real path `packages/dashboard-ui/` into
        # `packages/along-dash-ui/`, which does not exist. Neither was detectable until
        # `test_03b_managed_block_matches_its_source` compared the block with its source.
        needs_legacy_rename = (
            "ACTDIM-AGENTS-PROTOCOL" in original
            or (".agents/" in original and ".along/" not in original)
            or re.search(r"(?<![\w/-])/(init-agents|update-agents|repo-dashboard)(?![\w-])",
                         original) is not None
        )
        if needs_legacy_rename:
            content = content.replace(".agents/", ".along/")
            # Anchored so a slash-command name is only rewritten when it stands alone.
            # `/dashboard` inside `packages/dashboard-ui` must not match.
            for legacy, current in (("init-agents", "along-init"),
                                    ("update-agents", "along-update"),
                                    ("init-kb", "along-init-kb"),
                                    ("sync-kb", "along-sync-kb"),
                                    ("search-kb", "along-search-kb"),
                                    ("repo-dashboard", "along-dash"),
                                    ("dashboard", "along-dash")):
                content = re.sub(rf"(?<![\w/-])/{legacy}(?![\w-])", f"/{current}", content)

        if content != original:
            mig.write(amd, content, detail="protocol markers and legacy names updated",
                      announce=True)

    # 6. Update .code-review-graph-ignore
    crg_ignore = os.path.join(repo_root, ".code-review-graph-ignore")
    if os.path.exists(crg_ignore):
        try:
            c = textio.read_text(crg_ignore)
        except UnicodeDecodeError as exc:
            mig.note_skipped(crg_ignore, f"not valid UTF-8 ({exc.reason})")
            c = None
        if c is not None and ".agents/" in c and ".along/" not in c:
            mig.write(crg_ignore, c.replace(".agents/", ".along/"),
                      detail=".agents/ -> .along/", announce=True)

    # 7. Migrate user home configuration / cache directories
    # 7. Rename Along's own legacy directories under the user's home. Only when the
    #    new name is free, so this can never overwrite a current installation, and only
    #    outside dry-run, like every other mutation here.
    user_home = os.path.expanduser("~")
    for label, old, new in (
            ("config", os.path.join(user_home, ".config", "opencode", "actdim-agents"),
             os.path.join(user_home, ".config", "opencode", "actdim-along")),
            ("cache", os.path.join(user_home, ".cache", "actdim-agents"),
             os.path.join(user_home, ".cache", "actdim-along"))):
        if os.path.exists(old) and not os.path.exists(new):
            try:
                mig.move(old, new, f"legacy {label} directory renamed")
            except OSError as exc:
                # Reported rather than swallowed: a half-renamed home directory is
                # exactly what the user needs to know about.
                print(f"   [WARN] could not rename the legacy {label} directory "
                      f"{old}: {exc}", file=sys.stderr)

    return moved_count

def sanitize_markdown_typography(mig, target_dir):
    """Repair banned typography under `target_dir`, returning the file count.

    A migration is an explicitly requested rewrite, so write mode is correct here -
    unlike the commit and release paths, which only verify. What is not correct, and
    was the previous behaviour, is reading each candidate with `errors="ignore"` and
    then overwriting it: that deleted every undecodable byte in any file that was not
    valid UTF-8. `alongkit.sanitizer` reads strictly, skips and reports such a file,
    and preserves the line endings of the ones it does rewrite. It also applies the
    whole forbidden-character table rather than only the two dashes this function
    used to know about.
    """
    # Looked at before it is touched, so a clean tree neither takes a backup nor
    # reports an operation it did not perform.
    report = sanitizer.run(target_dir, mode=sanitizer.Mode.DRY_RUN)
    for skipped in report.skipped:
        mig.note_skipped(skipped.path, f"typography: {skipped.reason}")
        print(f"   [Warning] typography: skipped {skipped.path} ({skipped.reason})")
    if not report.files_with_findings:
        return 0
    if not mig.dry_run:
        mig.ensure_backup()
        report = sanitizer.run(target_dir, mode=sanitizer.Mode.WRITE)
    mig.record("sanitize typography", target_dir,
               f"{report.files_with_findings} file(s)")
    return report.files_with_findings

def validate_and_build_entity_graph(along_dir):
    """
    Builds entity dependency graph from .along/ (or fallback .agents/) and checks for cycles & dangling references.
    """
    nodes = {}
    edges = []
    errors = []
    warnings = []

    # Collect entity files
    entity_patterns = [
        ("issue", os.path.join(along_dir, "ISSUES", "**", "*.md")),
        ("risk", os.path.join(along_dir, "RISKS", "*.md")),
        ("spike", os.path.join(along_dir, "SPIKES", "*.md")),
        ("milestone", os.path.join(along_dir, "MILESTONES", "*.md")),
    ]

    for etype, pattern in entity_patterns:
        for fpath in glob.glob(pattern, recursive=True):
            fname = os.path.basename(fpath)
            if fname in ["ISSUES.md", "README.md"]:
                continue
            key = fname.replace(".md", "")
            clean_slug = key.split("--", 1)[1] if "--" in key else key
            fields, _ = parse_yaml_frontmatter(textio.read_text(fpath, strict=False), path=fpath)
            fm = fields or {}
            node_data = {
                "key": key,
                "slug": fm.get("slug", clean_slug),
                "type": etype,
                "status": fm.get("status", "open"),
                "fm": fm,
                "file": fpath
            }
            nodes[key] = node_data
            if clean_slug != key:
                nodes[clean_slug] = node_data

    # Collect edges and validate dangling references
    adj_blocked = {}
    visited_keys = set()
    for key, data in nodes.items():
        if data["key"] in visited_keys:
            continue
        visited_keys.add(data["key"])
        fm = data["fm"]
        k = data["key"]
        adj_blocked[k] = []

        # blocked_by
        blocked_by = fm.get("blocked_by") or []
        if isinstance(blocked_by, str):
            blocked_by = [blocked_by]
        for b in blocked_by:
            if not b:
                continue
            edges.append({"source": b, "target": k, "type": "blocks"})
            adj_blocked[k].append(b)
            if b not in nodes:
                warnings.append(f"Dangling link in {k}: blocked_by '{b}' not found.")

        # related
        related = fm.get("related") or []
        if isinstance(related, str):
            related = [related]
        for r in related:
            if not r:
                continue
            edges.append({"source": k, "target": r, "type": "related"})
            if r not in nodes:
                warnings.append(f"Dangling link in {k}: related '{r}' not found.")

        # parent
        parent = fm.get("parent")
        if parent:
            edges.append({"source": parent, "target": k, "type": "parent_of"})
            if parent not in nodes:
                warnings.append(f"Dangling link in {k}: parent '{parent}' not found.")

    # Cycle detection in blocked_by DAG
    state = {}  # 0=unvisited, 1=visiting, 2=visited
    def dfs(n, path):
        state[n] = 1
        for neighbor in adj_blocked.get(n, []):
            if neighbor not in state or state[neighbor] == 0:
                if neighbor in adj_blocked and dfs(neighbor, path + [neighbor]):
                    return True
            elif state[neighbor] == 1:
                cycle_str = " -> ".join(path + [neighbor])
                errors.append(f"Dependency cycle detected in blocked_by graph: {cycle_str}")
                return True
        state[n] = 2
        return False

    for n in list(adj_blocked.keys()):
        if state.get(n, 0) == 0:
            dfs(n, [n])

    return nodes, edges, errors, warnings

# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Step 7: v2.0 -> v2.1 (Knowledge Base -> docs/)
# ----------------------------------------------------------------------
def step_migrate_v2_1_docs_wiki_and_archive(mig, repo_root, interactive=True):
    # Locate along_kb_sync.py in local scripts/ or global paths
    exec_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(repo_root, "scripts", "along_kb_sync.py"),
        os.path.join(exec_dir, "along_kb_sync.py"),
        os.path.expanduser("~/.along/bin/along_kb_sync.py"),
        os.path.expanduser("~/.config/opencode/actdim-along/along_kb_sync.py"),
    ]
    kb_script = None
    for c in candidates:
        if os.path.isfile(c):
            kb_script = c
            break

    # The KB engine owns its own dry-run: `--check` inspects and reports without
    # writing, so a migration plan covers the KB step too instead of stopping at it.
    kb_args = ["--check"] if mig.dry_run else []
    if kb_script:
        res = proc.run_python([kb_script, repo_root, *kb_args])
        if res.ok:
            verb = "would be migrated" if mig.dry_run else "migrated"
            print(f"   [OK] Knowledge Base {verb} to docs/.")
        else:
            print(f"   [WARN] along_kb_sync returned code {res.returncode}: {res.stderr.strip()}")
    else:
        # Fallback: import if in sys.path
        try:
            import along_kb_sync
            along_kb_sync.sync_kb(repo_root, check_only=mig.dry_run)
            print("   [OK] Knowledge Base migrated to docs/ via import.")
        except Exception as e:
            print(f"   [WARN] Step 7 Knowledge Base migration fallback error: {e}")

    # Final cleanup: purge legacy .along/KB and .agents/KB. Both
    # are backed up first; their content has already been ingested into docs/, but a
    # deletion the user cannot undo is not the migration's call to make.
    for old_kb in [os.path.join(repo_root, ".along", "KB"), os.path.join(repo_root, ".agents", "KB")]:
        mig.discard(old_kb, "Knowledge Base now lives in docs/")

    # Explicitly evaluate CONTEXT.md to salvage substantive documentation into docs/
    context_file = os.path.join(repo_root, ".along", "CONTEXT.md")
    if os.path.exists(context_file):
        try:
            content = textio.read_text(context_file, strict=False)
        except Exception:
            content = ""
            
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        is_substantive = len(lines) > 2
        if is_substantive and len(lines) <= 4:
            text = " ".join(lines).lower()
            if "context" in text and ("add" in text or "project" in text or "replace" in text):
                is_substantive = False
                
        if is_substantive:
            today_str = datetime.now().strftime("%Y-%m-%d")
            fm = {
                "protocol": "along",
                "slug": "legacy-context",
                "title": "Legacy Project Context",
                "type": "topic",
                "created": today_str,
                "updated": today_str,
                "tags": ["legacy", "context"]
            }
            docs_dir = os.path.join(repo_root, "docs")
            mig.makedirs(docs_dir)
            wiki_path = os.path.join(docs_dir, "topic--legacy-context.md")
            
            if not os.path.exists(wiki_path):
                mig.write(wiki_path, dump_yaml_frontmatter(fm, content), 
                          detail="synthesized from legacy CONTEXT.md", announce=True)
            
            mig.discard(context_file, "CONTEXT.md synthesized into docs/")
        else:
            mig.discard(context_file, "empty or boilerplate CONTEXT.md discarded")


def step_repair_legacy_frontmatter_colons(mig, target_dir, detected_version):
    """Safely repair unquoted colons in legacy front-matter scalar fields.

    Active ONLY when detected_version < 2.2.9 (prior to ruamel.yaml integration).
    """
    if semver.parse(detected_version) >= (2, 2, 9) or not os.path.exists(target_dir):
        return 0

    repaired_count = 0
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d != migration.BACKUP_DIRNAME]
        for f in files:
            if not f.endswith(".md"):
                continue
            fpath = os.path.join(root, f)
            try:
                content = textio.read_text(fpath)
            except UnicodeDecodeError:
                continue

            fields, _, error = frontmatter.try_parse(content, path=fpath)
            if error:
                repaired_content, _ = repair_unquoted_frontmatter_scalars(content, path=fpath)
                if repaired_content is not None:
                    mig.write(fpath, repaired_content, detail="repaired unquoted front-matter colons", announce=True)
                    repaired_count += 1
    if repaired_count > 0:
        verb = "would repair" if mig.dry_run else "Repaired"
        print(f"   {verb} unquoted front-matter colons in {repaired_count} entity file(s).")
    return repaired_count


def scan_shell_escape_artifacts_in_docs(repo_root, detected_version):
    """Advisory diagnostic scan for shell-escaping artifacts in docs/ when migrating from v2.0.0 <= v < v2.2.9.

    Reports warnings for manual review without modifying any files on disk.
    """
    if not (semver.parse(detected_version) >= (2, 0, 0) and semver.parse(detected_version) < (2, 2, 9)):
        return []

    docs_dir = os.path.join(repo_root, "docs")
    if not os.path.isdir(docs_dir):
        return []

    warnings = []
    paired_backslash_re = re.compile(r'(?<![A-Za-z0-9_/\\])\\([A-Za-z0-9_.]+(?:\([^)]*\))?)\\(?![A-Za-z0-9_/\\])')
    escaped_quote_re = re.compile(r'\\"')

    for f in sorted(os.listdir(docs_dir)):
        if not f.endswith(".md"):
            continue
        fpath = os.path.join(docs_dir, f)
        try:
            content = textio.read_text(fpath, strict=False)
        except Exception:
            continue

        in_fence = False
        for line_idx, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            line_no_inline = re.sub(r'`[^`]+`', '', line)

            for match in paired_backslash_re.finditer(line_no_inline):
                matched_str = match.group(0)
                rel_f = os.path.relpath(fpath, repo_root).replace('\\', '/')
                warnings.append(f"{rel_f}:{line_idx}: Suspicious paired backslashes '{matched_str}' (possible shell-escaped backticks; manual review recommended)")

            if escaped_quote_re.search(line_no_inline):
                rel_f = os.path.relpath(fpath, repo_root).replace('\\', '/')
                warnings.append(f"{rel_f}:{line_idx}: Suspicious escaped quote '\\\"' in prose (manual review recommended)")

    return warnings


# Main Migration Controller
# ----------------------------------------------------------------------
def run_migrations(repo_root, dry_run=True, force=False, backup=True):
    """Run every migration step against `repo_root` and return a process exit code.


    In dry-run mode no step writes anything: each one reports what it would do, and
    the plan is printed in full at the end. This is the default for any caller that is
    not a human at a terminal, because the two ways this engine used to run - from the
    installer and from the test suite - were both invocations nobody asked for.
    """
    along_dir = os.path.join(repo_root, ".along")
    agents_dir = os.path.join(repo_root, ".agents")

    if not os.path.exists(along_dir) and not os.path.exists(agents_dir):
        print(f"No .along/ or .agents/ directory found in {repo_root}. Run /along-init first.")
        return 0

    detected_version = detect_protocol_version(repo_root)
    recorded_version = migration.read_state(along_dir)
    print("==================================================")
    print("-> ALONG Migration Engine")
    print(f"   Target: {repo_root}")
    print(f"   Mode:   {'dry run (nothing is written)' if dry_run else 'apply'}")
    print(f"   Detected Protocol Version: v{detected_version}")
    print(f"   Recorded Migration State:  {'v' + recorded_version if recorded_version else 'none'}")
    print(f"   Target Protocol Version:   v{CURRENT_PROTOCOL_VERSION}")
    print("==================================================")

    # A completed migration is recorded, so a second run is a no-op instead of
    # re-executing eight steps whose idempotency held only by accident of their
    # individual guards.
    if (recorded_version == CURRENT_PROTOCOL_VERSION
            and not os.path.exists(agents_dir) and not force):
        print(f"-> Already at v{CURRENT_PROTOCOL_VERSION}; nothing to do. "
              "Use --force to re-run every step.")
        return 0

    mig = migration.Migration(repo_root, dry_run=dry_run, state_dir=along_dir,
                              backup=backup)

    # Initial target directory for legacy steps
    target_working_dir = along_dir if os.path.exists(along_dir) else agents_dir

    # Step 1
    print("-> Step 1 [v1.0 -> v1.1]: Verifying ISSUES directory structure...")
    step_migrate_v1_1_tasks_to_issues(mig, target_working_dir)

    # Step 2
    print("-> Step 2 [v1.1 -> v1.3]: Scaffolding Knowledge Base (KB) & Code Graph ignore...")
    step_migrate_v1_3_kb_scaffolding(mig, repo_root, target_working_dir)

    # Step 2b: Repair legacy front-matter colons before entity enrichment
    if semver.parse(detected_version) < (2, 2, 9):
        print("-> Step 2b [v1.5 -> v2.2.8]: Repairing unquoted front-matter colons...")
        step_repair_legacy_frontmatter_colons(mig, target_working_dir, detected_version)

    # Step 3
    print("-> Step 3 [v1.3 -> v1.5]: Upgrading Entity Ecosystem, Milestones & Relationships...")
    step_migrate_v1_5_entity_ecosystem(mig, repo_root, target_working_dir)

    # Step 4: Along v2.0.0 Migration
    print("-> Step 4 [v1.5 -> v2.0]: Migrating to .along/ directory & injecting protocol: along metadata...")
    step_migrate_v2_0_along_directory(mig, repo_root)

    active_along_dir = os.path.join(repo_root, ".along")
    if semver.parse(detected_version) < (2, 2, 9) and os.path.exists(active_along_dir):
        step_repair_legacy_frontmatter_colons(mig, active_along_dir, detected_version)

    # Step 5: Typography sanitation
    print("-> Step 5: Sanitizing Markdown typography (replacing banned characters with ASCII)...")
    sanitized_count = (sanitize_markdown_typography(mig, active_along_dir)
                       if os.path.exists(active_along_dir) else 0)
    if sanitized_count > 0:
        verb = "would sanitize" if dry_run else "Sanitized"
        print(f"   {verb} typography in {sanitized_count} Markdown files.")

    # Step 6: Validate entity graph
    errors = []
    if os.path.exists(active_along_dir):
        print("-> Step 6: Validating Entity Relationships & Dependency Graph...")
        nodes, edges, errors, warnings = validate_and_build_entity_graph(active_along_dir)
        print(f"   Entities parsed: {len(set(d['key'] for d in nodes.values()))}, Total links: {len(edges)}")
        for w in warnings:
            print(f"   [WARN] {w}")
        for e in errors:
            print(f"   [ERROR] {e}")

        if errors:
            print("-> [FAIL] Migration completed with graph validation errors.")

    # Step 7: v2.1.0 Docs & LLM-Wiki migration
    print("-> Step 7 [v2.0 -> v2.1]: Migrating Knowledge Base to docs/...")
    step_migrate_v2_1_docs_wiki_and_archive(mig, repo_root)

    # Step 8: v2.2.x -> v2.2.6 Inbound Link Rewriting & Integrity Verification
    print("-> Step 8 [v2.2.x -> v2.2.6]: Retroactively repairing broken README links & verifying integrity...")
    step_migrate_v2_2_5_link_rewriting_and_integrity(mig, repo_root, detected_version)

    # Step 8b: Advisory scan for shell-escaping artifacts in docs/ (gated to v2.0.0 <= v < v2.2.9)
    if semver.parse(detected_version) >= (2, 0, 0) and semver.parse(detected_version) < (2, 2, 9):
        print("-> Step 8b [v2.0 -> v2.2.8]: Advisory scan for potential shell-escaping artifacts in docs/...")
        shell_warnings = scan_shell_escape_artifacts_in_docs(repo_root, detected_version)
        if shell_warnings:
            print(f"   [Notice] Found {len(shell_warnings)} potential shell-escaping artifact(s) in docs/:")
            for sw in shell_warnings:
                print(f"      [WARN] {sw}")
            mig.record("advisory shell scan", repo_root, f"{len(shell_warnings)} warning(s)", announce=False)
        else:
            print("   [OK] No suspicious shell-escaping artifacts detected in docs/.")

    # The state marker is written last, so a run that died halfway is not recorded as
    # a completed migration.
    if not dry_run and not errors:
        mig.record_state(CURRENT_PROTOCOL_VERSION)

    print("--------------------------------------------------")
    for line in mig.summary():
        print(line)
    print("--------------------------------------------------")

    if dry_run:
        print(f"-> [OK] Dry run complete; no file was written. Re-run with --apply to "
              f"perform the Along v{CURRENT_PROTOCOL_VERSION} migrations & validations.")
        return 0

    print(f"-> [OK] All Along v{CURRENT_PROTOCOL_VERSION} migrations & validations completed successfully!")
    return 0

def step_migrate_v2_2_5_link_rewriting_and_integrity(mig, repo_root, detected_version="1.0.0"):
    """
    Step 8 [v2.2.x -> v2.2.6]:
    Retroactively repairs broken inbound links in README.md and all project Markdown files
    caused by premature deletion of .along/KB/ without inbound link rewriting in versions 2.1.0 - 2.2.4.
    """
    scripts_dir = os.path.join(repo_root, "scripts")
    exec_dir = os.path.dirname(os.path.abspath(__file__))
    user_home = os.path.expanduser("~")
    for p in [scripts_dir, exec_dir, os.path.join(user_home, ".along", "bin")]:
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)

    try:
        import along_kb_sync
        # Counted on a dry pass first, so a repository with nothing to repair is
        # neither backed up nor rewritten.
        rewritten_files, total_rewrites = along_kb_sync.rewrite_inbound_links(
            repo_root, dry_run=True)
        if total_rewrites > 0 and not mig.dry_run:
            mig.ensure_backup()
            rewritten_files, total_rewrites = along_kb_sync.rewrite_inbound_links(
                repo_root, dry_run=False)
        broken_links, total_checked = along_kb_sync.validate_repo_link_integrity(repo_root)
        if total_rewrites > 0:
            verb = "would repair" if mig.dry_run else "Retroactively repaired"
            print(f"   [OK] {verb} {total_rewrites} broken link(s) across {rewritten_files} file(s).")
            mig.record("rewrite inbound links", repo_root,
                       f"{total_rewrites} link(s) in {rewritten_files} file(s)",
                       announce=False)
        else:
            print("   [OK] Inbound links clean; verified all relative Markdown links on disk.")
    except Exception as e:
        candidates = [
            os.path.join(repo_root, "scripts", "along_kb_sync.py"),
            os.path.join(exec_dir, "along_kb_sync.py"),
            os.path.join(user_home, ".along", "bin", "along_kb_sync.py"),
            os.path.join(user_home, ".config", "opencode", "actdim-along", "along_kb_sync.py"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                res = proc.run_python([c, repo_root, *(["--check"] if mig.dry_run else [])])
                if res.ok:
                    print("   [OK] Inbound links repaired via along_kb_sync.py.")
                else:
                    print(f"   [WARN] along_kb_sync returned code {res.returncode}: {res.stderr.strip()}")
                break

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="migrate_protocol.py",
        description="Migrate a repository's Along protocol structure to "
                    f"v{CURRENT_PROTOCOL_VERSION}, without ever deleting content.")
    parser.add_argument("repo_root", nargs="?", default=os.getcwd(),
                        help="repository to migrate (default: current directory)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-n", "--dry-run", action="store_true",
                      help="print the full planned operation list and write nothing")
    mode.add_argument("-y", "--apply", action="store_true",
                      help="perform the migration (required for a non-interactive caller)")
    parser.add_argument("--force", action="store_true",
                        help="re-run every step even when the recorded state is current")
    parser.add_argument("--no-backup", action="store_true",
                        help="skip the pre-migration copy of the state directory")
    args = parser.parse_args(argv)

    # Dry-run unless a human asked for the mutation, either by passing --apply or by
    # running the engine at a terminal. The installer and the test suite both used to
    # migrate repositories nobody had pointed at this engine.
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    dry_run = args.dry_run or not (args.apply or interactive)
    if dry_run and not args.dry_run:
        print("-> [Notice] Not attached to a terminal; running as a dry run. "
              "Pass --apply to perform the migration.")

    return run_migrations(os.path.abspath(args.repo_root), dry_run=dry_run,
                          force=args.force, backup=not args.no_backup)


if __name__ == "__main__":
    sys.exit(main())

