#!/usr/bin/env python3
"""
along_dep_scan.py - Hierarchical Multi-Project & Submodule AI Dependencies Discovery engine for Along.

Features:
- Recursive subproject, monorepo package, git submodule, and symlink discovery.
- Cycle protection using realpath tracking and strict skip lists (node_modules, .git, .venv, bin, obj, etc.).
- Multi-ecosystem support:
  * Node.js (npm/pnpm/yarn/bun: package.json)
  * Python (pip/poetry/uv: pyproject.toml, requirements*.txt, setup.py)
  * .NET (C#/F# NuGet: *.csproj, *.fsproj, Directory.Packages.props, packages.config)
  * Rust (Cargo: Cargo.toml)
  * Go (go.mod)
- Adaptive custom project hook (.along/scripts/dep_scan.py).
- Knowledge Base Integration (docs/topic--dependencies.md & docs/INDEX.md):
  * Internal Subprojects / Submodules AI & Wiki links registry.
  * Declared External Dependencies with AI instructions scoped by project.
"""

import os
import sys
import json
import re
import argparse
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Any, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import entities, proc, repo
from alongkit.version import CURRENT_PROTOCOL_VERSION

TARGET_AI_FILES = [
    "AGENTS.md",
    "agents.md",
    "CLAUDE.md",
    "claude.md",
    "llms.txt",
    "llms-full.txt",
    "LLMS.txt",
    "LLMS.md",
]

TARGET_AI_LOWER = {f.lower() for f in TARGET_AI_FILES}

# One definition, shared with every other engine and gate.
IGNORE_TRAVERSAL_DIRS = set(repo.IGNORED_DIRS) | {'.gemini'}


find_repo_root = repo.find_repo_root
normalize_posix = repo.normalize_posix
safe_relpath = repo.safe_relpath
get_today_iso = entities.today_iso


def find_ai_files_in_dir(dir_path: str, repo_root: str) -> List[Dict[str, str]]:
    """Scan directory for AI instruction files without case duplication."""
    found = []
    if not os.path.isdir(dir_path):
        return found
    try:
        entries = os.listdir(dir_path)
    except Exception:
        return found

    seen_real = set()
    for entry in sorted(entries):
        if entry.lower() in TARGET_AI_LOWER:
            full = os.path.join(dir_path, entry)
            if os.path.isfile(full):
                r_canon = os.path.realpath(full)
                if r_canon not in seen_real:
                    seen_real.add(r_canon)
                    rel = normalize_posix(safe_relpath(full, repo_root))
                    found.append({"filename": entry, "path": rel})
    return found


# ---------------------------------------------------------------------------
# Project Discovery & Traversal
# ---------------------------------------------------------------------------

class ProjectScope:
    def __init__(self, name: str, rel_path: str, full_path: str, is_root: bool = False):
        self.name = name
        self.rel_path = normalize_posix(rel_path)
        self.full_path = full_path
        self.is_root = is_root
        self.ecosystems: List[str] = []
        self.ai_files: List[Dict[str, str]] = []
        self.has_along_dir: bool = False
        self.has_docs_dir: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "rel_path": self.rel_path,
            "is_root": self.is_root,
            "ecosystems": sorted(list(set(self.ecosystems))),
            "ai_files": self.ai_files,
            "has_along_dir": self.has_along_dir,
            "has_docs_dir": self.has_docs_dir,
        }


def discover_submodules(repo_root: str) -> List[str]:
    """Parse .gitmodules if present to extract explicit submodule paths."""
    gitmodules_path = os.path.join(repo_root, ".gitmodules")
    submodule_paths = []
    if not os.path.isfile(gitmodules_path):
        return submodule_paths

    try:
        with open(gitmodules_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for m in re.finditer(r"path\s*=\s*(.+)", content):
            sub_path = m.group(1).strip().strip('"').strip("'")
            if sub_path:
                submodule_paths.append(sub_path)
    except Exception:
        pass
    return submodule_paths


def is_project_directory(dir_path: str) -> Tuple[bool, List[str]]:
    """Determine if a directory represents a project root and list its ecosystems."""
    ecosystems = []
    try:
        entries = set(os.listdir(dir_path))
    except Exception:
        return False, []

    if "package.json" in entries:
        ecosystems.append("npm")
    if "pyproject.toml" in entries or "requirements.txt" in entries or "setup.py" in entries:
        ecosystems.append("python")
    if "Cargo.toml" in entries:
        ecosystems.append("cargo")
    if "go.mod" in entries:
        ecosystems.append("go")

    for f in entries:
        if f.endswith(".csproj") or f.endswith(".fsproj") or f == "Directory.Packages.props" or f == "packages.config":
            ecosystems.append("nuget")
            break

    is_proj = bool(ecosystems) or (".along" in entries) or ("AGENTS.md" in entries) or ("docs" in entries)
    return is_proj, ecosystems


def inspect_internal_ai_context(proj_dir: str, repo_root: str) -> Tuple[List[Dict[str, str]], bool, bool]:
    """Discover internal project AI context files, docs, and .along folder."""
    found_files = find_ai_files_in_dir(proj_dir, repo_root)
    has_along = os.path.isdir(os.path.join(proj_dir, ".along"))
    has_docs = os.path.isdir(os.path.join(proj_dir, "docs"))

    if has_along:
        rel_along = normalize_posix(os.path.relpath(os.path.join(proj_dir, ".along"), repo_root))
        found_files.append({"filename": ".along/", "path": rel_along})

    if has_docs:
        rel_docs = normalize_posix(os.path.relpath(os.path.join(proj_dir, "docs"), repo_root))
        found_files.append({"filename": "docs/", "path": rel_docs})

    return found_files, has_along, has_docs


def discover_all_projects(repo_root: str) -> List[ProjectScope]:
    """Recursively discover all project roots, subprojects, submodules, and symlinks."""
    projects: List[ProjectScope] = []
    visited_realpaths: Set[str] = set()

    root_canon = os.path.realpath(repo_root)
    visited_realpaths.add(root_canon)

    # 1. Main repo root
    _, root_ecos = is_project_directory(repo_root)
    root_ai, root_along, root_docs = inspect_internal_ai_context(repo_root, repo_root)
    root_proj = ProjectScope(name="[root]", rel_path=".", full_path=repo_root, is_root=True)
    root_proj.ecosystems = root_ecos
    root_proj.ai_files = root_ai
    root_proj.has_along_dir = root_along
    root_proj.has_docs_dir = root_docs
    projects.append(root_proj)

    # 2. Check explicit submodules
    for sub_rel in discover_submodules(repo_root):
        sub_full = os.path.join(repo_root, sub_rel)
        if os.path.isdir(sub_full):
            sub_canon = os.path.realpath(sub_full)
            visited_realpaths.add(sub_canon)
            _, sub_ecos = is_project_directory(sub_full)
            sub_ai, sub_along, sub_docs = inspect_internal_ai_context(sub_full, repo_root)
            p = ProjectScope(name=sub_rel, rel_path=sub_rel, full_path=sub_full)
            p.ecosystems = sub_ecos
            p.ai_files = sub_ai
            p.has_along_dir = sub_along
            p.has_docs_dir = sub_docs
            projects.append(p)

    # 3. Recursive directory traversal
    for root, dirs, files in os.walk(repo_root, followlinks=True):
        canon_dir = os.path.realpath(root)
        if canon_dir != root_canon and canon_dir in visited_realpaths:
            dirs.clear()
            continue
        visited_realpaths.add(canon_dir)

        # Filter out ignored directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_TRAVERSAL_DIRS
            and not d.startswith(".")
            and os.path.realpath(os.path.join(root, d)) not in visited_realpaths
        ]

        if root == repo_root:
            continue

        rel_dir = normalize_posix(os.path.relpath(root, repo_root))
        if any(p.rel_path == rel_dir for p in projects):
            continue

        is_proj, ecos = is_project_directory(root)
        if is_proj:
            ai_files, has_along, has_docs = inspect_internal_ai_context(root, repo_root)
            proj_name = rel_dir
            pkg_json = os.path.join(root, "package.json")
            if os.path.isfile(pkg_json):
                try:
                    with open(pkg_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("name"):
                            proj_name = data["name"]
                except Exception:
                    pass

            p = ProjectScope(name=proj_name, rel_path=rel_dir, full_path=root)
            p.ecosystems = ecos
            p.ai_files = ai_files
            p.has_along_dir = has_along
            p.has_docs_dir = has_docs
            projects.append(p)

    return projects


# ---------------------------------------------------------------------------
# Node.js (npm / pnpm / yarn / bun) Scanner
# ---------------------------------------------------------------------------

def scan_node_project_deps(project: ProjectScope, repo_root: str) -> List[Dict[str, Any]]:
    pkg_json_path = os.path.join(project.full_path, "package.json")
    if not os.path.isfile(pkg_json_path):
        return []

    try:
        with open(pkg_json_path, "r", encoding="utf-8") as f:
            pkg_data = json.load(f)
    except Exception:
        return []

    deps = {}
    for section in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
        if isinstance(pkg_data.get(section), dict):
            deps.update(pkg_data[section])

    discovered = []
    scope_label = "[root]" if project.is_root else project.rel_path

    lookup_node_modules = [
        os.path.join(project.full_path, "node_modules"),
        os.path.join(repo_root, "node_modules"),
    ]

    for pkg_name in sorted(deps.keys()):
        pkg_full_dir = None
        for nm_dir in lookup_node_modules:
            candidate = os.path.join(nm_dir, *pkg_name.split("/"))
            if os.path.isdir(candidate):
                pkg_full_dir = candidate
                break

        if not pkg_full_dir:
            continue

        found_files = find_ai_files_in_dir(pkg_full_dir, repo_root)

        # Check for .along or docs in package
        along_dir = os.path.join(pkg_full_dir, ".along")
        if os.path.isdir(along_dir):
            rel_along = normalize_posix(os.path.relpath(along_dir, repo_root))
            found_files.append({"filename": ".along/", "path": rel_along})

        docs_dir = os.path.join(pkg_full_dir, "docs")
        if os.path.isdir(docs_dir):
            rel_docs = normalize_posix(os.path.relpath(docs_dir, repo_root))
            found_files.append({"filename": "docs/", "path": rel_docs})

        # Check inner package.json for metadata
        inner_pkg_path = os.path.join(pkg_full_dir, "package.json")
        ai_metadata = None
        version = str(deps[pkg_name])
        if os.path.isfile(inner_pkg_path):
            try:
                with open(inner_pkg_path, "r", encoding="utf-8") as pf:
                    inner_data = json.load(pf)
                    if "version" in inner_data:
                        version = inner_data["version"]
                    for ai_key in ["ai", "llms", "agents", "along"]:
                        if ai_key in inner_data:
                            ai_metadata = {ai_key: inner_data[ai_key]}
                            break
            except Exception:
                pass

        if found_files or ai_metadata:
            discovered.append({
                "package": pkg_name,
                "scope": scope_label,
                "ecosystem": "npm",
                "version": version,
                "files": found_files,
                "metadata": ai_metadata,
            })

    return discovered


# ---------------------------------------------------------------------------
# Python (pip / poetry / uv) Scanner
# ---------------------------------------------------------------------------

def parse_pyproject_deps(pyproject_path: str) -> List[str]:
    deps = []
    if not os.path.isfile(pyproject_path):
        return deps

    try:
        with open(pyproject_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        proj_deps_match = re.search(r'\[project\][\s\S]*?dependencies\s*=\s*\[(.*?)\]', content)
        if proj_deps_match:
            raw_items = proj_deps_match.group(1)
            for item in re.findall(r'["\']([a-zA-Z0-9_\-\.]+)(?:[<>=!~].*)?["\']', raw_items):
                deps.append(item)

        poetry_match = re.search(r'\[tool\.poetry\.dependencies\]([\s\S]*?)(?:\n\[|$)', content)
        if poetry_match:
            for line in poetry_match.group(1).splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    m = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*=', line)
                    if m and m.group(1).lower() != "python":
                        deps.append(m.group(1))
    except Exception:
        pass
    return list(set(deps))


def parse_requirements_deps(req_path: str) -> List[str]:
    deps = []
    if not os.path.isfile(req_path):
        return deps

    try:
        with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                m = re.match(r'^([a-zA-Z0-9_\-\.]+)', line)
                if m:
                    deps.append(m.group(1))
    except Exception:
        pass
    return list(set(deps))


def scan_python_project_deps(project: ProjectScope, repo_root: str) -> List[Dict[str, Any]]:
    declared_pkgs = set()
    declared_pkgs.update(parse_pyproject_deps(os.path.join(project.full_path, "pyproject.toml")))
    declared_pkgs.update(parse_requirements_deps(os.path.join(project.full_path, "requirements.txt")))
    declared_pkgs.update(parse_requirements_deps(os.path.join(project.full_path, "requirements-dev.txt")))

    if not declared_pkgs:
        return []

    scope_label = "[root]" if project.is_root else project.rel_path
    candidate_venvs = [
        os.path.join(project.full_path, ".venv"),
        os.path.join(project.full_path, "venv"),
        os.path.join(repo_root, ".venv"),
        os.path.join(repo_root, "venv"),
    ]
    site_packages_dirs = []
    for venv in candidate_venvs:
        if os.path.isdir(venv):
            win_site = os.path.join(venv, "Lib", "site-packages")
            if os.path.isdir(win_site):
                site_packages_dirs.append(win_site)
            lib_dir = os.path.join(venv, "lib")
            if os.path.isdir(lib_dir):
                for child in os.listdir(lib_dir):
                    sub = os.path.join(lib_dir, child, "site-packages")
                    if os.path.isdir(sub):
                        site_packages_dirs.append(sub)

    if not site_packages_dirs and hasattr(sys, "prefix"):
        win_site = os.path.join(sys.prefix, "Lib", "site-packages")
        if os.path.isdir(win_site):
            site_packages_dirs.append(win_site)

    discovered = []

    for pkg_name in sorted(declared_pkgs):
        norm_name = pkg_name.lower().replace("-", "_")
        found_pkg_dir = None
        version = None

        for site_pkg in site_packages_dirs:
            for variant in [norm_name, pkg_name, pkg_name.replace("_", "-")]:
                p = os.path.join(site_pkg, variant)
                if os.path.isdir(p):
                    found_pkg_dir = p
                    break
            if found_pkg_dir:
                for entry in os.listdir(site_pkg):
                    if (entry.lower().startswith(f"{norm_name}-") or entry.lower().startswith(f"{pkg_name.lower()}-")) and entry.endswith(".dist-info"):
                        meta_file = os.path.join(site_pkg, entry, "METADATA")
                        if os.path.isfile(meta_file):
                            try:
                                with open(meta_file, "r", encoding="utf-8", errors="ignore") as mf:
                                    for mline in mf:
                                        if mline.startswith("Version:"):
                                            version = mline.split(":", 1)[1].strip()
                                            break
                            except Exception:
                                pass
                        break
                break

        if not found_pkg_dir:
            continue

        found_files = find_ai_files_in_dir(found_pkg_dir, repo_root)

        if found_files:
            discovered.append({
                "package": pkg_name,
                "scope": scope_label,
                "ecosystem": "pypi",
                "version": version or "installed",
                "files": found_files,
                "metadata": None,
            })

    return discovered


# ---------------------------------------------------------------------------
# .NET (C# / F# / NuGet) Scanner
# ---------------------------------------------------------------------------

def parse_nuget_references(xml_path: str) -> Dict[str, str]:
    pkgs = {}
    if not os.path.isfile(xml_path):
        return pkgs

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ["PackageReference", "PackageVersion"]:
                name = elem.attrib.get("Include") or elem.attrib.get("Update")
                version = elem.attrib.get("Version") or "*"
                if not version or version == "*":
                    ver_elem = elem.find("Version")
                    if ver_elem is not None and ver_elem.text:
                        version = ver_elem.text.strip()
                if name:
                    pkgs[name] = version
            elif tag == "package":  # packages.config
                name = elem.attrib.get("id")
                version = elem.attrib.get("version") or "*"
                if name:
                    pkgs[name] = version
    except Exception:
        pass
    return pkgs


def get_nuget_cache_dirs(repo_root: str) -> List[str]:
    cache_dirs = []
    env_nuget = os.environ.get("NUGET_PACKAGES")
    if env_nuget and os.path.isdir(env_nuget):
        cache_dirs.append(env_nuget)

    home = os.path.expanduser("~")
    std_cache = os.path.join(home, ".nuget", "packages")
    if os.path.isdir(std_cache):
        cache_dirs.append(std_cache)

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        win_cache = os.path.join(user_profile, ".nuget", "packages")
        if os.path.isdir(win_cache) and win_cache not in cache_dirs:
            cache_dirs.append(win_cache)

    local_pkg = os.path.join(repo_root, "packages")
    if os.path.isdir(local_pkg):
        cache_dirs.append(local_pkg)

    return cache_dirs


def scan_nuget_project_deps(project: ProjectScope, repo_root: str) -> List[Dict[str, Any]]:
    declared_pkgs = {}
    try:
        entries = os.listdir(project.full_path)
    except Exception:
        return []

    for f in entries:
        if f.endswith(".csproj") or f.endswith(".fsproj") or f in ["Directory.Packages.props", "packages.config"]:
            xml_p = os.path.join(project.full_path, f)
            declared_pkgs.update(parse_nuget_references(xml_p))

    if not declared_pkgs:
        return []

    scope_label = "[root]" if project.is_root else project.rel_path
    nuget_caches = get_nuget_cache_dirs(repo_root)
    discovered = []

    for pkg_name, ver in sorted(declared_pkgs.items()):
        pkg_lower = pkg_name.lower()
        found_pkg_dir = None
        actual_ver = ver

        for cache in nuget_caches:
            pkg_root_in_cache = os.path.join(cache, pkg_lower)
            if not os.path.isdir(pkg_root_in_cache):
                pkg_root_in_cache = os.path.join(cache, pkg_name)

            if os.path.isdir(pkg_root_in_cache):
                versions = [v for v in os.listdir(pkg_root_in_cache) if os.path.isdir(os.path.join(pkg_root_in_cache, v))]
                if versions:
                    matched_v = ver if ver in versions else sorted(versions)[-1]
                    found_pkg_dir = os.path.join(pkg_root_in_cache, matched_v)
                    actual_ver = matched_v
                    break

        if not found_pkg_dir:
            continue

        found_files = find_ai_files_in_dir(found_pkg_dir, repo_root)

        docs_dir = os.path.join(found_pkg_dir, "docs")
        if os.path.isdir(docs_dir):
            rel_docs = normalize_posix(safe_relpath(docs_dir, repo_root))
            found_files.append({"filename": "docs/", "path": rel_docs})

        if found_files:
            discovered.append({
                "package": pkg_name,
                "scope": scope_label,
                "ecosystem": "nuget",
                "version": actual_ver,
                "files": found_files,
                "metadata": None,
            })

    return discovered


# ---------------------------------------------------------------------------
# Rust (Cargo) Scanner
# ---------------------------------------------------------------------------

def scan_rust_project_deps(project: ProjectScope, repo_root: str) -> List[Dict[str, Any]]:
    cargo_path = os.path.join(project.full_path, "Cargo.toml")
    if not os.path.isfile(cargo_path):
        return []

    declared_deps = {}
    try:
        with open(cargo_path, "r", encoding="utf-8") as f:
            content = f.read()
        for section in ["dependencies", "dev-dependencies", "build-dependencies"]:
            sec_match = re.search(r'\[' + re.escape(section) + r'\]([\s\S]*?)(?:\n\[|$)', content)
            if sec_match:
                for line in sec_match.group(1).splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        m = re.match(r'^([a-zA-Z0-9_\-]+)\s*=\s*(?:["\'](.*?)["\']|\{.*version\s*=\s*["\'](.*?)["\'])', line)
                        if m:
                            pkg_name = m.group(1)
                            ver = m.group(2) or m.group(3) or "*"
                            declared_deps[pkg_name] = ver
    except Exception:
        return []

    discovered = []
    scope_label = "[root]" if project.is_root else project.rel_path

    vendor_dirs = [
        os.path.join(project.full_path, "vendor"),
        os.path.join(repo_root, "vendor"),
    ]
    cargo_home = os.environ.get("CARGO_HOME", os.path.expanduser("~/.cargo"))
    registry_src = os.path.join(cargo_home, "registry", "src")

    for pkg_name, ver in sorted(declared_deps.items()):
        pkg_dirs = []
        for vd in vendor_dirs:
            if os.path.isdir(vd):
                v_pkg = os.path.join(vd, pkg_name)
                if os.path.isdir(v_pkg):
                    pkg_dirs.append(v_pkg)

        if os.path.isdir(registry_src):
            for reg_idx in os.listdir(registry_src):
                reg_full = os.path.join(registry_src, reg_idx)
                if os.path.isdir(reg_full):
                    for folder in os.listdir(reg_full):
                        if folder.startswith(f"{pkg_name}-"):
                            pkg_dirs.append(os.path.join(reg_full, folder))

        for p_dir in pkg_dirs:
            found_files = find_ai_files_in_dir(p_dir, repo_root)

            if found_files:
                discovered.append({
                    "package": pkg_name,
                    "scope": scope_label,
                    "ecosystem": "cargo",
                    "version": ver,
                    "files": found_files,
                    "metadata": None,
                })
                break

    return discovered


# ---------------------------------------------------------------------------
# Adaptive Custom Script Hook (.along/scripts/dep_scan.py)
# ---------------------------------------------------------------------------

def run_custom_dep_scan_hook(project_dir: str, repo_root: str) -> List[Dict[str, Any]]:
    """Execute project-level or subproject-level .along/scripts/dep_scan.py if available."""
    custom_scripts = [
        os.path.join(project_dir, ".along", "scripts", "dep_scan.py"),
        os.path.join(project_dir, ".along", "scripts", "scan_deps.py"),
    ]
    for script_path in custom_scripts:
        if os.path.isfile(script_path):
            res = proc.run_python([script_path, "--json"], cwd=project_dir, timeout=30)
            if res.ok and res.out:
                try:
                    data = json.loads(res.out)
                except ValueError as exc:
                    print(f"[Warning] {script_path} did not emit valid JSON: {exc}",
                          file=sys.stderr)
                    continue
                if isinstance(data, list):
                    return data
    return []


def synthesize_dep_scan_hook_template(script_path: str):
    """Generate a template for project-specific custom dependency scanner."""
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    content = '''#!/usr/bin/env python3
"""
.along/scripts/dep_scan.py - Custom Project Dependency Scanner Hook.
Outputs JSON list of discovered dependencies with AI instructions.
"""
import sys
import json

def main():
    # Return list of dicts: [{"package": "...", "ecosystem": "...", "version": "...", "files": [{"filename": "...", "path": "..."}]}]
    results = []
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
'''
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Knowledge Base (Wiki) Markdown Generator
# ---------------------------------------------------------------------------

def generate_dependencies_kb_content(projects: List[ProjectScope], external_deps: List[Dict[str, Any]]) -> str:
    today = get_today_iso()
    lines = [
        "---",
        "protocol: along",
        f'protocol_version: "{CURRENT_PROTOCOL_VERSION}"',
        "slug: topic--dependencies",
        "title: Dependencies & Submodules AI Documentation and Rules",
        "type: topic",
        f"created: {today}",
        f"updated: {today}",
        "tags: [dependencies, ai-context, submodules, vendor, rules]",
        "---",
        "",
        "# Dependencies & Submodules AI Documentation and Rules",
        "",
        "> [!NOTE]",
        "> This document maintains a unified registry of internal subprojects, submodules, and external dependencies.",
        "> Consult linked guidelines when developing, refactoring, or integrating components across the repository.",
        "",
    ]

    # Section 1: Internal Subprojects & Modules
    internal_subprojects = [p for p in projects if not p.is_root]
    lines.append("## Internal Subprojects, Modules & Submodules")
    lines.append("")
    if not internal_subprojects:
        lines.append("Single-root project structure. No nested subprojects or Git submodules detected.")
        lines.append("")
    else:
        lines.append("| Subproject / Module | Path | Ecosystems | AI Documentation & Context |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for sub in internal_subprojects:
            ecos_str = ", ".join(f"`{e}`" for e in sub.ecosystems) if sub.ecosystems else "`general`"
            links = []
            for f in sub.ai_files:
                fn = f["filename"]
                fp = f["path"]
                rel_from_docs = f"../{fp}"
                links.append(f"[{fn}]({rel_from_docs})")
            links_str = " <br> ".join(links) if links else "-"
            lines.append(f"| **`{sub.name}`** | `{sub.rel_path}` | {ecos_str} | {links_str} |")
        lines.append("")

    # Section 2: Declared External Dependencies with AI Context
    lines.append("## Declared External Dependencies with AI Guidelines")
    lines.append("")
    if not external_deps:
        lines.append("No active external dependencies with AI instructions (`AGENTS.md`, `llms.txt`, or package metadata) were detected.")
        lines.append("")
    else:
        lines.append("| Package | Scope / Project | Ecosystem | Version | AI Guidelines / Instructions |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for dep in external_deps:
            pkg = dep["package"]
            scope = dep.get("scope", "[root]")
            eco = dep["ecosystem"]
            ver = dep.get("version") or "unspecified"
            file_links = []
            for f in dep.get("files", []):
                fn = f["filename"]
                fp = f["path"]
                rel_from_docs = f"../{fp}"
                file_links.append(f"[{fn}]({rel_from_docs})")
            if dep.get("metadata"):
                meta_str = ", ".join(f"`{k}`" for k in dep["metadata"].keys())
                file_links.append(f"manifest metadata ({meta_str})")

            links_str = " <br> ".join(file_links) if file_links else "-"
            lines.append(f"| **`{pkg}`** | `{scope}` | `{eco}` | `{ver}` | {links_str} |")
        lines.append("")

    lines.append("## Usage in Agent Sessions")
    lines.append("When working on features involving any of the modules or external libraries above:")
    lines.append("1. **Internal Submodules**: Follow conventions in the nearest `AGENTS.md` or subproject `docs/`.")
    lines.append("2. **Third-Party Libraries**: Read the linked instruction files directly for framework-specific patterns and best practices.")
    lines.append("")
    return "\n".join(lines)


def update_kb_index(repo_root: str):
    kb_dir = os.path.join(repo_root, "docs")
    index_file = os.path.join(kb_dir, "INDEX.md")
    if not os.path.isfile(index_file):
        return

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()

        dep_link = "[topic--dependencies.md](./topic--dependencies.md)"
        if "topic--dependencies.md" not in content:
            if "## Articles" in content:
                content = content.replace(
                    "## Articles",
                    "## Articles\n- " + dep_link + ": Dependencies & Submodules AI Documentation and Rules",
                    1
                )
            else:
                content += f"\n- {dep_link}: Dependencies & Submodules AI Documentation and Rules\n"

            with open(index_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Runner Orchestration
# ---------------------------------------------------------------------------

def run_scanner(repo_root: str, dry_run: bool = False) -> Dict[str, Any]:
    repo_root = os.path.abspath(repo_root)
    projects = discover_all_projects(repo_root)
    all_external_deps: List[Dict[str, Any]] = []

    seen_dep_keys = set()

    for proj in projects:
        proj_deps: List[Dict[str, Any]] = []
        proj_deps.extend(scan_node_project_deps(proj, repo_root))
        proj_deps.extend(scan_python_project_deps(proj, repo_root))
        proj_deps.extend(scan_nuget_project_deps(proj, repo_root))
        proj_deps.extend(scan_rust_project_deps(proj, repo_root))
        proj_deps.extend(run_custom_dep_scan_hook(proj.full_path, repo_root))

        for item in proj_deps:
            key = (item["package"], item["ecosystem"], item.get("scope", proj.rel_path))
            if key not in seen_dep_keys:
                seen_dep_keys.add(key)
                all_external_deps.append(item)

    if not dry_run:
        kb_dir = os.path.join(repo_root, "docs")
        os.makedirs(kb_dir, exist_ok=True)
        dep_kb_path = os.path.join(kb_dir, "topic--dependencies.md")
        content = generate_dependencies_kb_content(projects, all_external_deps)
        with open(dep_kb_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

        update_kb_index(repo_root)

    return {
        "projects": [p.to_dict() for p in projects],
        "dependencies": all_external_deps,
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Hierarchical Multi-Project & Submodule AI Dependencies Discovery engine for Along.")
    parser.add_argument("--root", type=str, default=None, help="Root repository directory (auto-detected by default)")
    parser.add_argument("--json", action="store_true", help="Output discovered dependencies and projects in JSON format")
    parser.add_argument("--check", action="store_true", help="Dry run scan without modifying KB files")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet output")

    args = parser.parse_args()
    repo_root = find_repo_root(args.root)

    results = run_scanner(repo_root, dry_run=args.check)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    projects = results["projects"]
    deps = results["dependencies"]

    if not args.quiet:
        print(f"-> [Along Hierarchical Dependencies Discovery] Scanned root: {repo_root}")
        print(f"-> Discovered {len(projects)} project scopes / subprojects:")
        for p in projects:
            ecos = ", ".join(p["ecosystems"]) if p["ecosystems"] else "general"
            ai_count = len(p["ai_files"])
            print(f"   * {p['name']} ({p['rel_path']}) [{ecos}] - {ai_count} AI context file(s)")

        if deps:
            print(f"\n-> Discovered {len(deps)} external dependencies with AI instructions:")
            for d in deps:
                files_str = ", ".join(f["filename"] for f in d.get("files", []))
                if d.get("metadata"):
                    files_str += f" (metadata: {list(d['metadata'].keys())})"
                print(f"   - {d['package']} [{d.get('scope', 'root')}] ({d['ecosystem']} {d.get('version', '')}): {files_str}")
            if not args.check:
                print(f"\n-> Updated Knowledge Base registry: docs/topic--dependencies.md")
        else:
            print("\n-> No external dependencies with AI instructions detected.")


if __name__ == "__main__":
    main()
