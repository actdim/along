from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along rules attach   (or: python scripts/along_exec.py rules attach)"
    )

import difflib
import hashlib
import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

from . import textio

RULE_SIGNATURES = {
    "Directory.Packages.props": ["platforms/monorepo.md"],
    "pnpm-workspace.yaml": ["platforms/monorepo.md"],
    "tsconfig.json": ["languages/typescript.md"],
    "pyproject.toml": ["languages/python.md"],
    "requirements.txt": ["languages/python.md"],
    "setup.py": ["languages/python.md"],
    "Directory.Build.props": ["languages/csharp.md"],
    "Cargo.toml": ["languages/rust.md"],
    "vite.config.ts": ["platforms/web.md"],
    "vite.config.js": ["platforms/web.md"],
    "next.config.js": ["platforms/web.md"],
    "next.config.mjs": ["platforms/web.md"],
    "tauri.conf.json": ["platforms/desktop.md"],
    "pubspec.yaml": ["platforms/mobile.md"],
    "docker-compose.yml": ["platforms/backend.md"],
    "nest-cli.json": ["platforms/backend.md"],
}

HEADER_PREFIX = "<!-- managed by along: do not edit."
HEADER_RE = re.compile(
    r"^<!-- managed by along: do not edit[^\n]*-->\r?\n<!-- template:\s*(\S+)\s+sha256:([0-9a-fA-F]{64})\s*-->\r?\n*",
    re.MULTILINE
)


def compute_rule_hash(text: str) -> str:
    """Computes normalized SHA-256 hash of text ignoring trailing whitespace and CRLF."""
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def format_rule_header(rule: str, tmpl_hash: str) -> str:
    """Generates standard 2-line Along managed header comment."""
    return (
        "<!-- managed by along: do not edit. Project guidelines belong in docs/ and AGENTS.md -->\n"
        f"<!-- template: {rule} sha256:{tmpl_hash} -->\n\n"
    )


def parse_rule_header(content: str) -> Tuple[Optional[str], Optional[str], str]:
    """Extracts (template_name, sha256_hash, body) from rule pack content."""
    m = HEADER_RE.match(content)
    if m:
        return m.group(1), m.group(2), content[m.end():]
    return None, None, content


def _is_locally_modified(content: str, global_rules_dir: str, rule: str) -> bool:
    """True when a rule pack differs from what Along installed.

    With a managed header the body is compared to the header hash. A headerless (legacy)
    file is pristine only when it matches the current Along template; without a template
    to compare against it counts as modified, so it is never deleted unseen.
    """
    _, f_hash, f_body = parse_rule_header(content)
    if f_hash:
        return compute_rule_hash(f_body) != f_hash
    src = os.path.join(global_rules_dir, rule) if global_rules_dir else ""
    if not src or not os.path.isfile(src):
        return True
    return compute_rule_hash(content) != compute_rule_hash(textio.read_text(src))


def detect_required_rules(repo_root: str) -> Set[str]:
    required = set()
    ignored_dirs = {'.git', 'node_modules', 'dist', 'build', '.venv', 'venv', 'bin', 'obj', 'vendor', '.along', '.agents'}
    
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for f in files:
            if f in RULE_SIGNATURES:
                for rule in RULE_SIGNATURES[f]:
                    required.add(rule)
            
            if f.endswith(".ts") or f.endswith(".tsx"):
                required.add("languages/typescript.md")
            elif f.endswith(".csproj") or f.endswith(".sln"):
                required.add("languages/csharp.md")
            elif f.endswith(".rs"):
                required.add("languages/rust.md")
            
            if f == "package.json":
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as pj:
                        content = pj.read()
                        if '"react-dom"' in content or '"msw"' in content:
                            required.add("platforms/web.md")
                        if '"react-native"' in content or '"expo"' in content:
                            required.add("platforms/mobile.md")
                        if '"express"' in content or '"fastapi"' in content:
                            required.add("platforms/backend.md")
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    pass
    return required


def get_global_rules_dir() -> str:
    # Use ~/.along/rules as the definitive source of rule packs
    user_home = os.path.expanduser("~")
    along_home = os.path.join(user_home, ".along", "rules")
    if os.path.exists(along_home):
        return along_home
    # Fallback for dev mode
    dev_rules = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "rules"))
    if os.path.exists(dev_rules):
        return dev_rules
    return ""


def attach_rules(repo_root: str, on_conflict: str = "preserve"):
    on_conflict = (on_conflict or "preserve").lower()
    required = detect_required_rules(repo_root)
    global_rules_dir = get_global_rules_dir()
    if not global_rules_dir:
        print("   [WARN] Could not find global rules source directory.")
        return

    local_rules_dir = os.path.join(repo_root, ".along", "rules")
    
    installed_files = set()
    
    # 1. Copy required rules with header and hash verification
    if required:
        os.makedirs(local_rules_dir, exist_ok=True)
        for rule in required:
            src = os.path.join(global_rules_dir, rule)
            dst = os.path.join(local_rules_dir, rule)
            if not os.path.exists(src):
                continue
                
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmpl_content = textio.read_text(src)
            tmpl_hash = compute_rule_hash(tmpl_content)
            managed_header = format_rule_header(rule, tmpl_hash)
            full_managed_content = managed_header + tmpl_content.lstrip()
            
            norm_dst = os.path.normcase(os.path.normpath(dst))
            
            if not os.path.exists(dst):
                textio.write_text(dst, full_managed_content)
                installed_files.add(norm_dst)
                continue
                
            dst_content = textio.read_text(dst)
            dst_tmpl, dst_hash, dst_body = parse_rule_header(dst_content)
            
            is_dirty = False
            if dst_hash is not None:
                cur_body_hash = compute_rule_hash(dst_body)
                if cur_body_hash == dst_hash:
                    # Pristine file: safe to update if template changed
                    if cur_body_hash != tmpl_hash or dst_tmpl != rule:
                        textio.write_text(dst, full_managed_content)
                        print(f"   [INFO] Updated rule template: {rule}")
                    installed_files.add(norm_dst)
                else:
                    is_dirty = True
            else:
                # File without header (legacy or manual)
                legacy_hash = compute_rule_hash(dst_content)
                if legacy_hash == tmpl_hash:
                    # Legacy pristine file without header: upgrade cleanly
                    textio.write_text(dst, full_managed_content)
                    print(f"   [INFO] Injected managed header into rule pack: {rule}")
                    installed_files.add(norm_dst)
                else:
                    is_dirty = True

            if is_dirty:
                rel_dst = os.path.relpath(dst, repo_root).replace("\\", "/")
                if on_conflict == "overwrite":
                    import datetime
                    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
                    backup_base = os.path.join(repo_root, ".along", ".migration-backup", ts)
                    backup_file = os.path.join(backup_base, "rules", rule)
                    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                    shutil.copy2(dst, backup_file)
                    textio.write_text(dst, full_managed_content)
                    print(f"   [OK] Overwrote modified rule pack with Along template: {rule} (backup saved at .along/.migration-backup/{ts}/rules/{rule})")
                elif on_conflict == "diff":
                    tmpl_lines = tmpl_content.splitlines(keepends=True)
                    dst_lines = dst_body.splitlines(keepends=True)
                    d = "".join(difflib.unified_diff(
                        tmpl_lines, dst_lines,
                        fromfile=f"template:{rule}", tofile=f"local:{rule}"
                    ))
                    if d:
                        print(f"   [DIFF] Local modifications in '{rule}':\n{d}")
                    print(f"   [WARN] Rule pack '{rule}' was modified locally ({rel_dst}). Preserving modifications; skipping overwrite.")
                else:
                    # default "preserve"
                    print(f"   [WARN] Rule pack '{rule}' was modified locally ({rel_dst}). Preserving modifications; skipping overwrite. Project guidelines belong in docs/ and AGENTS.md.")
                installed_files.add(norm_dst)
                
    # 2. Prune obsolete rules
    if os.path.exists(local_rules_dir):
        for root, dirs, files in os.walk(local_rules_dir):
            for f in files:
                p = os.path.normcase(os.path.normpath(os.path.join(root, f)))
                
                # Protect gates configuration and gitkeep
                if f in ("gates.yaml", "gates.yml", ".gitkeep"):
                    continue
                
                if p not in installed_files:
                    rel_rule = os.path.relpath(p, local_rules_dir).replace("\\", "/")
                    try:
                        is_modified = _is_locally_modified(textio.read_text(p), global_rules_dir, rel_rule)
                    except (OSError, UnicodeDecodeError, ValueError):
                        # Unreadable: keep it rather than delete what we cannot inspect.
                        is_modified = True

                    if is_modified:
                        print(f"   [WARN] Retaining modified unlisted rule: {os.path.relpath(p, repo_root)}")
                        continue
                        
                    os.remove(p)
                    print(f"   [INFO] Pruned obsolete rule: {os.path.relpath(p, repo_root)}")
                    
        # Remove empty directories
        for root, dirs, files in os.walk(local_rules_dir, topdown=False):
            for d in dirs:
                p = os.path.join(root, d)
                if os.path.exists(p) and not os.listdir(p):
                    os.rmdir(p)

    # 3. Update AGENTS.md
    agents_md = os.path.join(repo_root, "AGENTS.md")
    if not os.path.exists(agents_md):
        return

    content = textio.read_text(agents_md, strict=False)
    original_content = content

    marker_start = "<!-- BEGIN ALONG-RULES -->"
    marker_end = "<!-- END ALONG-RULES -->"

    if required:
        ref_lines = ["See the following engineering guidelines:"]
        for r in sorted(required):
            ref_lines.append(f"- `[{r}](.along/rules/{r})`")

        block_content = "\n".join(ref_lines)
        block = f"{marker_start}\n{block_content}\n{marker_end}"

        if marker_start in content and marker_end in content:
            pattern = re.compile(f"{re.escape(marker_start)}.*?{re.escape(marker_end)}", re.DOTALL)
            content = pattern.sub(lambda _: block, content)
        else:
            if "## Project specifics" in content:
                content = content.replace("## Project specifics", f"## Project specifics\n\n{block}")
            else:
                content = content.rstrip() + f"\n\n## Project specifics\n\n{block}\n"
    else:
        # If no rules required, remove the marker block if present
        if marker_start in content and marker_end in content:
            pattern = re.compile(f"{re.escape(marker_start)}.*?{re.escape(marker_end)}\\n?", re.DOTALL)
            content = pattern.sub("", content)

    if content != original_content:
        textio.write_text(agents_md, content)
    
    if required:
        print(f"   [OK] Attached {len(required)} rule packs to AGENTS.md.")


def audit_rules(repo_root: str) -> List[Dict[str, Any]]:
    """Audits repository rule packs against Along global templates."""
    required = detect_required_rules(repo_root)
    global_rules_dir = get_global_rules_dir()
    local_rules_dir = os.path.join(repo_root, ".along", "rules")
    
    results: List[Dict[str, Any]] = []
    seen_rules: Set[str] = set()
    
    # Check all required rules
    for rule in sorted(required):
        seen_rules.add(rule)
        dst = os.path.join(local_rules_dir, rule)
        src = os.path.join(global_rules_dir, rule) if global_rules_dir else ""
        
        if not os.path.exists(dst):
            results.append({
                "rule": rule,
                "status": "missing",
                "path": dst,
                "detail": "Required by project stack but not installed"
            })
            continue
            
        dst_content = textio.read_text(dst)
        dst_tmpl, dst_hash, dst_body = parse_rule_header(dst_content)
        
        tmpl_content = textio.read_text(src) if (src and os.path.exists(src)) else ""
        tmpl_hash = compute_rule_hash(tmpl_content) if tmpl_content else ""
        
        if dst_hash is not None:
            cur_body_hash = compute_rule_hash(dst_body)
            if cur_body_hash == dst_hash:
                results.append({
                    "rule": rule,
                    "status": "pristine",
                    "path": dst,
                    "detail": "Matches Along template"
                })
            else:
                results.append({
                    "rule": rule,
                    "status": "modified",
                    "path": dst,
                    "detail": "Locally modified from template"
                })
        else:
            cur_hash = compute_rule_hash(dst_content)
            if cur_hash == tmpl_hash:
                results.append({
                    "rule": rule,
                    "status": "pristine",
                    "path": dst,
                    "detail": "Matches Along template (unversioned header)"
                })
            else:
                results.append({
                    "rule": rule,
                    "status": "modified",
                    "path": dst,
                    "detail": "Locally modified (no managed header)"
                })
                
    # Check for unrequired / obsolete files in .along/rules/
    if os.path.exists(local_rules_dir):
        for root, dirs, files in os.walk(local_rules_dir):
            for f in files:
                p = os.path.join(root, f)
                rel_rule = os.path.relpath(p, local_rules_dir).replace("\\", "/")
                if f in ("gates.yaml", "gates.yml", ".gitkeep"):
                    results.append({
                        "rule": rel_rule,
                        "status": "protected",
                        "path": p,
                        "detail": "Repository gate configuration"
                    })
                    continue
                if rel_rule not in seen_rules:
                    is_modified = _is_locally_modified(textio.read_text(p), global_rules_dir, rel_rule)
                    results.append({
                        "rule": rel_rule,
                        "status": "modified_obsolete" if is_modified else "obsolete",
                        "path": p,
                        "detail": "Obsolete (not required by stack)"
                    })
                    
    return results


def diff_rule(repo_root: str, rule: str) -> Optional[str]:
    """Generates unified diff between local modified rule body and Along template."""
    global_rules_dir = get_global_rules_dir()
    local_rules_dir = os.path.join(repo_root, ".along", "rules")
    
    src = os.path.join(global_rules_dir, rule)
    dst = os.path.join(local_rules_dir, rule)
    
    if not os.path.exists(dst):
        return f"Error: Local rule '{rule}' not found at {dst}"
    if not os.path.exists(src):
        return f"Error: Global template '{rule}' not found at {src}"
        
    tmpl_content = textio.read_text(src)
    dst_content = textio.read_text(dst)
    _, _, dst_body = parse_rule_header(dst_content)
    
    tmpl_lines = tmpl_content.splitlines(keepends=True)
    dst_lines = dst_body.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(
        tmpl_lines,
        dst_lines,
        fromfile=f"template:{rule}",
        tofile=f"local:{rule}",
    ))
    if not diff:
        return ""
    return "".join(diff)


def restore_rule(repo_root: str, rule: Optional[str] = None, force: bool = False) -> List[str]:
    """Restores pristine Along template for the specified rule (or all modified rules if None)."""
    global_rules_dir = get_global_rules_dir()
    if not global_rules_dir:
        print("   [WARN] Could not find global rules source directory.")
        return []
        
    audits = audit_rules(repo_root)
    targets = []
    for entry in audits:
        if rule:
            if entry["rule"] == rule or entry["rule"].endswith(rule):
                targets.append(entry)
        else:
            if "modified" in entry["status"]:
                targets.append(entry)
                
    if not targets:
        return []
        
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup_base = os.path.join(repo_root, ".along", ".migration-backup", timestamp)
    
    restored: List[str] = []
    for item in targets:
        r = item["rule"]
        dst = item["path"]
        src = os.path.join(global_rules_dir, r)
        if not os.path.exists(src):
            continue
            
        # Backup before restore
        backup_file = os.path.join(backup_base, "rules", r)
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        shutil.copy2(dst, backup_file)
        
        tmpl_content = textio.read_text(src)
        tmpl_hash = compute_rule_hash(tmpl_content)
        managed_header = format_rule_header(r, tmpl_hash)
        full_managed_content = managed_header + tmpl_content.lstrip()
        
        textio.write_text(dst, full_managed_content)
        restored.append(r)
        print(f"   [OK] Restored pristine rule template: {r} (backup at .along/.migration-backup/{timestamp}/rules/{r})")
        
    return restored
