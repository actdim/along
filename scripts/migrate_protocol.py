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
    python scripts/migrate_protocol.py [TARGET_REPO_ROOT]
"""

import os
import re
import sys
import glob
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap

# This engine reads entity front-matter, so it needs ruamel.yaml. Resolve it before
# anything imports it: an engine invoked as `python <path>/<engine>.py` may start
# under an interpreter that has no dependencies prepared, which is exactly how the
# installers and the documented skill commands invoke it.
bootstrap.ensure_deps()

from alongkit import frontmatter, proc, repo, sanitizer, textio
from alongkit.version import CURRENT_PROTOCOL_VERSION


def parse_yaml_frontmatter(content, path=None):
    """Front-matter of a file this engine is about to rewrite.

    Tolerant on purpose: a migration must not abort a whole repository because one
    file is malformed. The caller must skip any file this reports on, never rewrite
    it from a partial parse, which is how the earlier hand-rolled parser destroyed
    block sequences.
    """
    fields, body, error = frontmatter.try_parse(content, path=path)
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
    agents_md = os.path.join(repo_root, "AGENTS.md")
    if os.path.exists(agents_md):
        with open(agents_md, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        m = re.search(r"(?:ALONG-PROTOCOL|ACTDIM-AGENTS-PROTOCOL) v(\d+\.\d+\.\d+)", content)
        if m:
            return m.group(1)
    return "1.0.0"

# ----------------------------------------------------------------------
# Step 1: v1.0.0 -> v1.1.0 (Tasks -> Issues)
# ----------------------------------------------------------------------
def step_migrate_v1_1_tasks_to_issues(working_dir):
    updated = False
    tasks_md = os.path.join(working_dir, "TASKS.md")
    issues_md = os.path.join(working_dir, "ISSUES.md")
    if os.path.exists(tasks_md) and not os.path.exists(issues_md):
        with open(tasks_md, "r", encoding="utf-8") as f:
            c = f.read()
        c = re.sub(r"# Tasks", "# Issues", c)
        c = re.sub(r"TASKS", "ISSUES", c)
        with open(issues_md, "w", encoding="utf-8") as f:
            f.write(c)
        os.remove(tasks_md)
        updated = True

    tasks_dir = os.path.join(working_dir, "TASKS")
    issues_dir = os.path.join(working_dir, "ISSUES")
    if os.path.exists(tasks_dir) and not os.path.exists(issues_dir):
        os.rename(tasks_dir, issues_dir)
        updated = True
    return updated

# ----------------------------------------------------------------------
# Step 2: v1.1.0 -> v1.3.0 (KB & Code Review Graph Scaffolding)
# ----------------------------------------------------------------------
def step_migrate_v1_3_kb_scaffolding(repo_root, working_dir):
    # .code-review-graph-ignore
    crg_ignore = os.path.join(repo_root, ".code-review-graph-ignore")
    created = 0
    if not os.path.exists(crg_ignore):
        with open(crg_ignore, "w", encoding="utf-8") as f:
            f.write("# Code Review Graph Exclusions\nnode_modules/\ndist/\nbuild/\nout/\n.git/\n.along/SESSIONS/\n.agents/SESSIONS/\n*.min.js\n*.bundle.js\n*.pyc\n__pycache__/\n")
        created += 1
    return created

# ----------------------------------------------------------------------
# Step 3: v1.3.3 -> v1.5.0 (Entity Ecosystem, Retro-Synthesis & Checklists)
# ----------------------------------------------------------------------
def step_migrate_v1_5_entity_ecosystem(repo_root, working_dir):
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
        os.makedirs(d, exist_ok=True)
        gitkeep = os.path.join(d, ".gitkeep")
        if not os.path.exists(gitkeep) and len(os.listdir(d)) == 0:
            open(gitkeep, "a").close()

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
            with open(cpath, "w", encoding="utf-8") as f:
                f.write(dump_yaml_frontmatter(fm, data["body"]))

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
            with open(past_m, "w", encoding="utf-8") as f:
                f.write(dump_yaml_frontmatter(fm_past, body_past))

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
        with open(current_m, "w", encoding="utf-8") as f:
            f.write(dump_yaml_frontmatter(fm_curr, body_curr))

    # 4. Enrich all ISSUES front-matter (with milestone linkage and protocol: along)
    all_issue_files = done_issues + active_issues
    for filepath in all_issue_files:
        is_done = "done" in os.path.dirname(filepath).replace("\\", "/").split("/")
        filename = os.path.basename(filepath)
        raw_slug = filename.replace(".md", "")
        clean_slug = raw_slug.split("--", 1)[1] if "--" in raw_slug else raw_slug
        issue_type = filename.split("--", 1)[0] if "--" in filename else "feat"

        content = textio.read_text(filepath)
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
            if new_content != content:
                textio.write_text(filepath, new_content)

    # 5. Enrich SESSIONS front-matter
    session_files = glob.glob(os.path.join(working_dir, "SESSIONS", "**", "*.md"), recursive=True)
    for filepath in session_files:
        content = textio.read_text(filepath)
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
            if new_content != content:
                textio.write_text(filepath, new_content)

    return True

# ----------------------------------------------------------------------
# Step 4: v1.5.7 -> v2.0.0 (Transition to Along & .along/ Directory)
# ----------------------------------------------------------------------
def step_migrate_v2_0_along_directory(repo_root):
    agents_dir = os.path.join(repo_root, ".agents")
    along_dir = os.path.join(repo_root, ".along")

    # Purge deprecated CONTEXT.md files
    for c_file in [os.path.join(along_dir, "CONTEXT.md"), os.path.join(agents_dir, "CONTEXT.md")]:
        if os.path.exists(c_file):
            try:
                os.remove(c_file)
            except Exception:
                pass
    
    recognized_files = [
        "ISSUES.md", "DECISIONS.md", "HISTORY.md",
        "GLOSSARY.md", "VISION.md", "DASHBOARD.md", "dashboard.html", "TASKS.md"
    ]
    recognized_dirs = [
        "ISSUES", "MILESTONES", "RISKS", "SPIKES", "CHECKLISTS", "SESSIONS", "KB", "TASKS"
    ]

    moved_count = 0
    if os.path.exists(agents_dir):
        os.makedirs(along_dir, exist_ok=True)
        
        # 1. Move recognised top-level files
        for fname in recognized_files:
            src = os.path.join(agents_dir, fname)
            dst = os.path.join(along_dir, fname)
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                shutil.move(src, dst)
                moved_count += 1

        # 2. Move recognised subdirectories
        for dname in recognized_dirs:
            src = os.path.join(agents_dir, dname)
            dst = os.path.join(along_dir, dname)
            if os.path.exists(src):
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                else:
                    # Merge files if destination already exists
                    for root, _, files in os.walk(src):
                        rel = os.path.relpath(root, src)
                        target_dir = os.path.join(dst, rel) if rel != "." else dst
                        os.makedirs(target_dir, exist_ok=True)
                        for f in files:
                            s_file = os.path.join(root, f)
                            d_file = os.path.join(target_dir, f)
                            if os.path.exists(d_file):
                                os.remove(d_file)
                            shutil.move(s_file, d_file)
                    shutil.rmtree(src, ignore_errors=True)
                moved_count += 1

        # 3. Clean up .agents/ if only empty directories or no files left
        remaining_files = []
        for root, _, files in os.walk(agents_dir):
            for f in files:
                remaining_files.append(os.path.join(root, f))

        if not remaining_files:
            shutil.rmtree(agents_dir, ignore_errors=True)
            print("   Removed empty legacy .agents/ directory.")
        else:
            print(f"   Preserved non-Along files in .agents/ ({len(remaining_files)} files remaining).")

    # 4. Inject protocol: along across all markdown files in .along/
    if os.path.exists(along_dir):
        for root, _, files in os.walk(along_dir):
            for f in files:
                if f.endswith(".md"):
                    fpath = os.path.join(root, f)
                    try:
                        content = textio.read_text(fpath)
                    except UnicodeDecodeError as exc:
                        print(f"   [WARN] {fpath} is not valid UTF-8 ({exc.reason}); skipped.",
                              file=sys.stderr)
                        continue
                    fields, _ = parse_yaml_frontmatter(content, path=fpath)
                    if fields and fields.get('protocol') != 'along':
                        updated = frontmatter.update(content, {'protocol': 'along'}, path=fpath)
                        if updated != content:
                            textio.write_text(fpath, updated)

    # 5. Update AGENTS.md references & markers
    agents_md_files = glob.glob(os.path.join(repo_root, "**", "AGENTS.md"), recursive=True)
    for amd in agents_md_files:
        try:
            content = textio.read_text(amd)
        except UnicodeDecodeError as exc:
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
        content = re.sub(r"(?:<!-- BEGIN ALONG-PROTOCOL (.*?) -->\s*)+", r"<!-- BEGIN ALONG-PROTOCOL \1 -->\n", content)
        content = re.sub(r"(?:<!-- END ALONG-PROTOCOL -->\s*)+", r"<!-- END ALONG-PROTOCOL -->\n", content)
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
            textio.write_text(amd, content)

    # 6. Update .code-review-graph-ignore
    crg_ignore = os.path.join(repo_root, ".code-review-graph-ignore")
    if os.path.exists(crg_ignore):
        with open(crg_ignore, "r", encoding="utf-8", errors="ignore") as f:
            c = f.read()
        if ".agents/" in c and ".along/" not in c:
            c = c.replace(".agents/", ".along/")
            with open(crg_ignore, "w", encoding="utf-8") as f:
                f.write(c)

    # 7. Migrate user home configuration / cache directories
    user_home = os.path.expanduser("~")
    old_cfg = os.path.join(user_home, ".config", "opencode", "actdim-agents")
    new_cfg = os.path.join(user_home, ".config", "opencode", "actdim-along")
    if os.path.exists(old_cfg) and not os.path.exists(new_cfg):
        try:
            shutil.move(old_cfg, new_cfg)
            print(f"   Migrated config: {old_cfg} -> {new_cfg}")
        except Exception:
            pass

    old_cache = os.path.join(user_home, ".cache", "actdim-agents")
    new_cache = os.path.join(user_home, ".cache", "actdim-along")
    if os.path.exists(old_cache) and not os.path.exists(new_cache):
        try:
            shutil.move(old_cache, new_cache)
            print(f"   Migrated cache: {old_cache} -> {new_cache}")
        except Exception:
            pass

    return moved_count

def sanitize_markdown_typography(target_dir):
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
    report = sanitizer.run(target_dir, mode=sanitizer.Mode.WRITE)
    for skipped in report.skipped:
        print(f"   [Warning] typography: skipped {skipped.path} ({skipped.reason})")
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
# Step 7: v2.0 -> v2.1 (Knowledge Base -> docs/ & .archive/)
# ----------------------------------------------------------------------
def step_migrate_v2_1_docs_wiki_and_archive(repo_root, interactive=True):
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

    if kb_script:
        res = proc.run_python([kb_script, repo_root])
        if res.ok:
            print("   [OK] Knowledge Base migrated to docs/ and .archive/.")
        else:
            print(f"   [WARN] along_kb_sync returned code {res.returncode}: {res.stderr.strip()}")
    else:
        # Fallback: import if in sys.path
        try:
            import along_kb_sync
            along_kb_sync.sync_kb(repo_root, check_only=False)
            print("   [OK] Knowledge Base migrated to docs/ and .archive/ via import.")
        except Exception as e:
            print(f"   [WARN] Step 7 Knowledge Base migration fallback error: {e}")

    # Final cleanup: purge legacy .along/KB, .agents/KB, and .along/CONTEXT.md
    for old_kb in [os.path.join(repo_root, ".along", "KB"), os.path.join(repo_root, ".agents", "KB")]:
        if os.path.exists(old_kb):
            shutil.rmtree(old_kb, ignore_errors=True)
    
    ctx_md = os.path.join(repo_root, ".along", "CONTEXT.md")
    if os.path.exists(ctx_md):
        try:
            os.remove(ctx_md)
        except Exception:
            pass

# Main Migration Controller
# ----------------------------------------------------------------------
def run_migrations(repo_root):
    along_dir = os.path.join(repo_root, ".along")
    agents_dir = os.path.join(repo_root, ".agents")
    
    if not os.path.exists(along_dir) and not os.path.exists(agents_dir):
        print(f"No .along/ or .agents/ directory found in {repo_root}. Run /along-init first.")
        return

    detected_version = detect_protocol_version(repo_root)
    print("==================================================")
    print("-> ALONG Migration Engine")
    print(f"   Target: {repo_root}")
    print(f"   Detected Protocol Version: v{detected_version}")
    print(f"   Target Protocol Version:   v{CURRENT_PROTOCOL_VERSION}")
    print("==================================================")

    # Initial target directory for legacy steps
    target_working_dir = along_dir if os.path.exists(along_dir) else agents_dir

    # Step 1
    print("-> Step 1 [v1.0 -> v1.1]: Verifying ISSUES directory structure...")
    step_migrate_v1_1_tasks_to_issues(target_working_dir)

    # Step 2
    print("-> Step 2 [v1.1 -> v1.3]: Scaffolding Knowledge Base (KB) & Code Graph ignore...")
    step_migrate_v1_3_kb_scaffolding(repo_root, target_working_dir)

    # Step 3
    print("-> Step 3 [v1.3 -> v1.5]: Upgrading Entity Ecosystem, Milestones & Relationships...")
    step_migrate_v1_5_entity_ecosystem(repo_root, target_working_dir)

    # Step 4: Along v2.0.0 Migration
    print("-> Step 4 [v1.5 -> v2.0]: Migrating to .along/ directory & injecting protocol: along metadata...")
    step_migrate_v2_0_along_directory(repo_root)

    active_along_dir = os.path.join(repo_root, ".along")

    # Step 5: Typography sanitation
    print("-> Step 5: Sanitizing Markdown typography (replacing em-dashes with ASCII hyphens)...")
    sanitized_count = sanitize_markdown_typography(active_along_dir) if os.path.exists(active_along_dir) else 0
    if sanitized_count > 0:
        print(f"   Sanitized typography in {sanitized_count} Markdown files.")

    # Step 6: Validate entity graph
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
    print("-> Step 7 [v2.0 -> v2.1]: Migrating Knowledge Base to docs/ and .archive/...")
    step_migrate_v2_1_docs_wiki_and_archive(repo_root)

    # Step 8: v2.2.x -> v2.2.6 Inbound Link Rewriting & Integrity Verification
    print("-> Step 8 [v2.2.x -> v2.2.6]: Retroactively repairing broken README links & verifying integrity...")
    step_migrate_v2_2_5_link_rewriting_and_integrity(repo_root, detected_version)

    print(f"-> [OK] All Along v{CURRENT_PROTOCOL_VERSION} migrations & validations completed successfully!")

def step_migrate_v2_2_5_link_rewriting_and_integrity(repo_root, detected_version="1.0.0"):
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
        rewritten_files, total_rewrites = along_kb_sync.rewrite_inbound_links(repo_root, dry_run=False)
        broken_links, total_checked = along_kb_sync.validate_repo_link_integrity(repo_root)
        if total_rewrites > 0:
            print(f"   [OK] Retroactively repaired {total_rewrites} broken link(s) across {rewritten_files} file(s).")
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
                res = proc.run_python([c, repo_root])
                if res.ok:
                    print("   [OK] Inbound links repaired via along_kb_sync.py.")
                else:
                    print(f"   [WARN] along_kb_sync returned code {res.returncode}: {res.stderr.strip()}")
                break

if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    run_migrations(root)

