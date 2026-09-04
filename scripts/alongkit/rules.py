from __future__ import annotations

if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along rules attach   (or: python scripts/along_exec.py rules attach)"
    )

import json
import os
import re
import shutil
from typing import Set

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

def attach_rules(repo_root: str):
    required = detect_required_rules(repo_root)
    global_rules_dir = get_global_rules_dir()
    if not global_rules_dir:
        print("   [WARN] Could not find global rules source directory.")
        return

    local_rules_dir = os.path.join(repo_root, ".along", "rules")
    
    installed_files = set()
    
    # 1. Copy required rules
    if required:
        os.makedirs(local_rules_dir, exist_ok=True)
        for rule in required:
            src = os.path.join(global_rules_dir, rule)
            dst = os.path.join(local_rules_dir, rule)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                installed_files.add(os.path.normcase(os.path.normpath(dst)))
                
    # 2. Prune obsolete rules
    if os.path.exists(local_rules_dir):
        for root, dirs, files in os.walk(local_rules_dir):
            for f in files:
                p = os.path.normcase(os.path.normpath(os.path.join(root, f)))
                if p not in installed_files:
                    os.remove(p)
                    print(f"   [INFO] Pruned obsolete rule: {os.path.relpath(p, repo_root)}")
                    
        # Remove empty directories
        for root, dirs, files in os.walk(local_rules_dir, topdown=False):
            for d in dirs:
                p = os.path.join(root, d)
                if not os.listdir(p):
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
            ref_lines.append(f"- `[{r}](file://.along/rules/{r})`")

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
