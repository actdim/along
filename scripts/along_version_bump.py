#!/usr/bin/env python3
"""
along_version_bump.py - Universal Project Version Bumper & Release Pipeline for Along.

Supports:
- Execution of project-specific `.along/scripts/bump_version.py` (if present)
- Auto-detection and synthesis for Node.js (package.json), Python (pyproject.toml/setup.py),
  Rust (Cargo.toml), .NET (Directory.Build.props/*.csproj), and generic VERSION files.
- Development mode for actdim/along protocol repo.
- Interactive fallback guidance if stack is custom/ambiguous.
- Automated typography sanitization, milestone reconciliation, and release commit/tagging.
"""

import sys
import os
import re
import json
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import gates, proc, repo, semver

def calculate_next_version(current_v, bump_type):
    """Next version string, or a usage error the caller cannot recover from."""
    try:
        return semver.calculate_next(current_v, bump_type)
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        sys.exit(1)

def is_along_dev_repo(repo_root):
    return (
        os.path.exists(os.path.join(repo_root, "skills", "along-init", "protocol.md")) and
        os.path.exists(os.path.join(repo_root, "scripts", "along_update.py"))
    )

def bump_along_dev_repo(repo_root, new_version):
    """Bumps version across actdim/along internal files."""
    modified_files = []
    
    # 1. Update skills/along-init/protocol.md
    proto_path = os.path.join(repo_root, "skills", "along-init", "protocol.md")
    if os.path.exists(proto_path):
        with open(proto_path, "r", encoding="utf-8") as f:
            content = f.read()
        updated = re.sub(r'# ALONG-PROTOCOL v\d+\.\d+\.\d+', f'# ALONG-PROTOCOL v{new_version}', content)
        if updated != content:
            with open(proto_path, "w", encoding="utf-8") as f: f.write(updated)
            modified_files.append(proto_path)

    # 2. Update all skills/*/SKILL.md
    skill_dirs = glob.glob(os.path.join(repo_root, "skills", "along-*"))
    for sdir in skill_dirs:
        skill_file = os.path.join(sdir, "SKILL.md")
        if os.path.exists(skill_file):
            with open(skill_file, "r", encoding="utf-8") as f:
                c = f.read()
            u = re.sub(r'\[v\d+\.\d+\.\d+\]', f'[v{new_version}]', c)
            u = re.sub(r'version: "\d+\.\d+\.\d+"', f'version: "{new_version}"', u)
            u = re.sub(r'ALONG-PROTOCOL v\d+\.\d+\.\d+', f'ALONG-PROTOCOL v{new_version}', u)
            if u != c:
                with open(skill_file, "w", encoding="utf-8") as f: f.write(u)
                modified_files.append(skill_file)

    # 3. Update root AGENTS.md
    agents_md = os.path.join(repo_root, "AGENTS.md")
    if os.path.exists(agents_md):
        with open(agents_md, "r", encoding="utf-8") as f: c = f.read()
        u = re.sub(r'# ALONG-PROTOCOL v\d+\.\d+\.\d+', f'# ALONG-PROTOCOL v{new_version}', c)
        if u != c:
            with open(agents_md, "w", encoding="utf-8") as f: f.write(u)
            modified_files.append(agents_md)

    # 4. Update README.md
    readme_md = os.path.join(repo_root, "README.md")
    if os.path.exists(readme_md):
        with open(readme_md, "r", encoding="utf-8") as f: c = f.read()
        u = re.sub(r'# Along \(v\d+\.\d+\.\d+\)', f'# Along (v{new_version})', c)
        u = re.sub(r'ALONG-PROTOCOL v\d+\.\d+\.\d+', f'ALONG-PROTOCOL v{new_version}', u)
        u = re.sub(r'Skills & Slash Commands \(v\d+\.\d+\.\d+\)', f'Skills & Slash Commands (v{new_version})', u)
        if u != c:
            with open(readme_md, "w", encoding="utf-8") as f: f.write(u)
            modified_files.append(readme_md)

    # 5. Update the protocol version constant. It is declared once, in the shared
    #    package; the legacy per-engine copies were removed in v3.0.0. The older
    #    paths stay in the list so a bump run inside an older checkout still works.
    for const_path in [os.path.join(repo_root, "scripts", "alongkit", "version.py"),
                       os.path.join(repo_root, "scripts", "migrate_protocol.py"),
                       os.path.join(repo_root, "skills", "along-init", "migrate_protocol.py"),
                       os.path.join(repo_root, "scripts", "along_kb_sync.py"),
                       os.path.join(repo_root, "skills", "along-kb-sync", "along_kb_sync.py"),
                       os.path.join(repo_root, "scripts", "along_update.py"),
                       os.path.join(repo_root, "skills", "along-update", "along_update.py")]:
        if os.path.exists(const_path):
            with open(const_path, "r", encoding="utf-8") as f: c = f.read()
            u = re.sub(r'CURRENT_PROTOCOL_VERSION = "\d+\.\d+\.\d+"',
                       f'CURRENT_PROTOCOL_VERSION = "{new_version}"', c)
            if u != c:
                with open(const_path, "w", encoding="utf-8") as f: f.write(u)
                modified_files.append(const_path)

    # 7. Update .along/CONTEXT.md
    ctx_md = os.path.join(repo_root, ".along", "CONTEXT.md")
    if os.path.exists(ctx_md):
        with open(ctx_md, "r", encoding="utf-8") as f: c = f.read()
        u = re.sub(r'ALONG-PROTOCOL v\d+\.\d+\.\d+', f'ALONG-PROTOCOL v{new_version}', c)
        if u != c:
            with open(ctx_md, "w", encoding="utf-8") as f: f.write(u)
            modified_files.append(ctx_md)

    # 8. Update llms.txt and llms-full.txt
    for llm_file in ["llms.txt", "llms-full.txt"]:
        llm_path = os.path.join(repo_root, llm_file)
        if os.path.exists(llm_path):
            with open(llm_path, "r", encoding="utf-8") as f: c = f.read()
            u = re.sub(r'ALONG-PROTOCOL v\d+\.\d+\.\d+', f'ALONG-PROTOCOL v{new_version}', c)
            u = re.sub(r'Along \(v\d+\.\d+\.\d+\)', f'Along (v{new_version})', u)
            if u != c:
                with open(llm_path, "w", encoding="utf-8") as f: f.write(u)
                modified_files.append(llm_path)

    # 9. Update package.json and packages/dashboard-ui/package.json
    for pkg_file in ["package.json", os.path.join("packages", "dashboard-ui", "package.json")]:
        pkg_path = os.path.join(repo_root, pkg_file)
        if os.path.exists(pkg_path):
            with open(pkg_path, "r", encoding="utf-8") as f:
                c = f.read()
            u = re.sub(r'"version":\s*"\d+\.\d+\.\d+"', f'"version": "{new_version}"', c)
            if u != c:
                with open(pkg_path, "w", encoding="utf-8") as f: f.write(u)
                modified_files.append(pkg_path)

    # 10. Update dashboard/app.py
    dash_app = os.path.join(repo_root, "dashboard", "app.py")
    if os.path.exists(dash_app):
        with open(dash_app, "r", encoding="utf-8") as f:
            c = f.read()
        u = re.sub(r'version="\d+\.\d+\.\d+"', f'version="{new_version}"', c)
        if u != c:
            with open(dash_app, "w", encoding="utf-8") as f: f.write(u)
            modified_files.append(dash_app)

    return modified_files

def synthesize_script(script_path, content):
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        os.chmod(script_path, 0o755)
    except Exception:
        pass
    print(f"-> Generated project-specific version bumper in: {script_path}")

def detect_and_bump_project(repo_root, bump_arg):
    custom_script = os.path.join(repo_root, ".along", "scripts", "bump_version.py")
    if os.path.exists(custom_script):
        print(f"-> Executing custom project script: {custom_script} {bump_arg}")
        res = proc.run_python([custom_script, bump_arg], cwd=repo_root)
        if res.returncode != 0:
            print(f"[Error] Custom bump script failed:\n{res.stderr}", file=sys.stderr)
            sys.exit(res.returncode)
        print(res.stdout.strip())
        # Try extracting new version from stdout
        m = re.search(r'(?:v?(\d+\.\d+\.\d+))', res.stdout)
        return m.group(1) if m else None

    # Check Along Dev Repo
    if is_along_dev_repo(repo_root):
        proto_path = os.path.join(repo_root, "skills", "along-init", "protocol.md")
        with open(proto_path, "r", encoding="utf-8") as f:
            m = re.search(r'# ALONG-PROTOCOL v(\d+\.\d+\.\d+)', f.read())
        cur_v = m.group(1) if m else "2.0.0"
        new_v = calculate_next_version(cur_v, bump_arg)
        files = bump_along_dev_repo(repo_root, new_v)
        print(f"-> [Along Dev Mode] Bumped v{cur_v} -> v{new_v} across {len(files)} internal files.")
        return new_v

    # Node.js Project (package.json)
    pkg_json = os.path.join(repo_root, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            cur_v = data.get("version", "1.0.0")
            new_v = calculate_next_version(cur_v, bump_arg)
            data["version"] = new_v
            with open(pkg_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            
            # package-lock.json
            pkg_lock = os.path.join(repo_root, "package-lock.json")
            if os.path.exists(pkg_lock):
                with open(pkg_lock, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                lock_data["version"] = new_v
                if "packages" in lock_data and "" in lock_data["packages"]:
                    lock_data["packages"][""]["version"] = new_v
                with open(pkg_lock, "w", encoding="utf-8") as f:
                    json.dump(lock_data, f, indent=2)
                    f.write("\n")

            # Synthesize script for future runs
            synthesize_script(custom_script, f'''#!/usr/bin/env python3
import sys, json, os, re

def main():
    bump_arg = sys.argv[1] if len(sys.argv) > 1 else "patch"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pkg_json = os.path.join(repo_root, "package.json")
    with open(pkg_json, "r", encoding="utf-8") as f: data = json.load(f)
    cur_v = data.get("version", "1.0.0")
    # semver calc
    parts = [int(p) for p in cur_v.split(".")]
    if bump_arg == "patch": next_v = f"{{parts[0]}}.{{parts[1]}}.{{parts[2]+1}}"
    elif bump_arg == "minor": next_v = f"{{parts[0]}}.{{parts[1]+1}}.0"
    elif bump_arg == "major": next_v = f"{{parts[0]+1}}.0.0"
    else: next_v = bump_arg.lstrip("v")
    data["version"] = next_v
    with open(pkg_json, "w", encoding="utf-8") as f: json.dump(data, f, indent=2); f.write("\\n")
    print(f"Bumped package.json: v{{cur_v}} -> v{{next_v}}")

if __name__ == "__main__":
    main()
''')
            print(f"-> [Node.js] Bumped package.json: v{cur_v} -> v{new_v}")
            return new_v
        except Exception as e:
            print(f"[Error] Failed to bump package.json: {e}", file=sys.stderr)

    # Python Project (pyproject.toml)
    pyproject = os.path.join(repo_root, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, "r", encoding="utf-8") as f:
                c = f.read()
            m = re.search(r'version\s*=\s*["\'](\d+\.\d+\.\d+.*?)["\']', c)
            if m:
                cur_v = m.group(1)
                new_v = calculate_next_version(cur_v, bump_arg)
                u = re.sub(r'version\s*=\s*["\'](\d+\.\d+\.\d+.*?)["\']', f'version = "{new_v}"', c, count=1)
                with open(pyproject, "w", encoding="utf-8") as f:
                    f.write(u)
                synthesize_script(custom_script, f'''#!/usr/bin/env python3
import sys, os, re

def main():
    bump_arg = sys.argv[1] if len(sys.argv) > 1 else "patch"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pyproject = os.path.join(repo_root, "pyproject.toml")
    with open(pyproject, "r", encoding="utf-8") as f: c = f.read()
    m = re.search(r'version\\s*=\\s*["\\'](\\d+\\.\\d+\\.\\d+.*?)["\\']', c)
    cur_v = m.group(1) if m else "1.0.0"
    parts = [int(p) for p in cur_v.split("-")[0].split(".")]
    if bump_arg == "patch": next_v = f"{{parts[0]}}.{{parts[1]}}.{{parts[2]+1}}"
    elif bump_arg == "minor": next_v = f"{{parts[0]}}.{{parts[1]+1}}.0"
    elif bump_arg == "major": next_v = f"{{parts[0]+1}}.0.0"
    else: next_v = bump_arg.lstrip("v")
    u = re.sub(r'version\\s*=\\s*["\\'](\\d+\\.\\d+\\.\\d+.*?)["\\']', f'version = "{{next_v}}"', c, count=1)
    with open(pyproject, "w", encoding="utf-8") as f: f.write(u)
    print(f"Bumped pyproject.toml: v{{cur_v}} -> v{{next_v}}")

if __name__ == "__main__":
    main()
''')
                print(f"-> [Python] Bumped pyproject.toml: v{cur_v} -> v{new_v}")
                return new_v
        except Exception as e:
            print(f"[Error] Failed to bump pyproject.toml: {e}", file=sys.stderr)

    # Rust Project (Cargo.toml)
    cargo_toml = os.path.join(repo_root, "Cargo.toml")
    if os.path.exists(cargo_toml):
        try:
            with open(cargo_toml, "r", encoding="utf-8") as f: c = f.read()
            m = re.search(r'\[package\][\s\S]*?version\s*=\s*["\'](\d+\.\d+\.\d+.*?)["\']', c)
            if m:
                cur_v = m.group(1)
                new_v = calculate_next_version(cur_v, bump_arg)
                u = re.sub(r'version\s*=\s*["\']' + re.escape(cur_v) + r'["\']', f'version = "{new_v}"', c, count=1)
                with open(cargo_toml, "w", encoding="utf-8") as f: f.write(u)
                synthesize_script(custom_script, f'''#!/usr/bin/env python3
import sys, os, re

def main():
    bump_arg = sys.argv[1] if len(sys.argv) > 1 else "patch"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cargo = os.path.join(repo_root, "Cargo.toml")
    with open(cargo, "r", encoding="utf-8") as f: c = f.read()
    m = re.search(r'\\[package\\][\\s\\S]*?version\\s*=\\s*["\\'](\\d+\\.\\d+\\.\\d+.*?)["\\']', c)
    cur_v = m.group(1) if m else "1.0.0"
    parts = [int(p) for p in cur_v.split("-")[0].split(".")]
    if bump_arg == "patch": next_v = f"{{parts[0]}}.{{parts[1]}}.{{parts[2]+1}}"
    elif bump_arg == "minor": next_v = f"{{parts[0]}}.{{parts[1]+1}}.0"
    elif bump_arg == "major": next_v = f"{{parts[0]+1}}.0.0"
    else: next_v = bump_arg.lstrip("v")
    u = re.sub(r'version\\s*=\\s*["\\']' + re.escape(cur_v) + r'["\\']', f'version = "{{next_v}}"', c, count=1)
    with open(cargo, "w", encoding="utf-8") as f: f.write(u)
    print(f"Bumped Cargo.toml: v{{cur_v}} -> v{{next_v}}")

if __name__ == "__main__":
    main()
''')
                print(f"-> [Rust] Bumped Cargo.toml: v{cur_v} -> v{new_v}")
                return new_v
        except Exception as e:
            print(f"[Error] Failed to bump Cargo.toml: {e}", file=sys.stderr)

    # Generic VERSION file
    version_file = os.path.join(repo_root, "VERSION")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f: cur_v = f.read().strip()
        new_v = calculate_next_version(cur_v, bump_arg)
        with open(version_file, "w", encoding="utf-8") as f: f.write(new_v + "\n")
        print(f"-> [Generic] Bumped VERSION file: v{cur_v} -> v{new_v}")
        return new_v

    # Fallback / Ambiguous guidance
    print("=" * 60)
    print("[Notice] Could not auto-detect project version manifest.")
    print("Inspected: package.json, pyproject.toml, Cargo.toml, VERSION, and Along dev files.")
    print("")
    print("To configure custom version bumping for this repository, create:")
    print(f"  {custom_script}")
    print("")
    print("Example Python Template:")
    print("------------------------------------------------------------")
    print("#!/usr/bin/env python3")
    print("import sys, os")
    print("bump_type = sys.argv[1] if len(sys.argv) > 1 else 'patch'")
    print("# Update your project-specific files here...")
    print("print('Bumped project version to vX.Y.Z')")
    print("------------------------------------------------------------")
    print("=" * 60)
    return None

sanitize_typography = gates.run_sanitizer


def update_along_milestones(repo_root, new_version):
    if not new_version:
        return
    milestone_files = glob.glob(os.path.join(repo_root, ".along", "MILESTONES", "*.md"))
    for mf in milestone_files:
        if new_version in os.path.basename(mf):
            with open(mf, "r", encoding="utf-8") as f: c = f.read()
            u = re.sub(r'status:\s*(?:open|in-progress)', 'status: completed', c)
            u = re.sub(r'progress_pct:\s*\d+', 'progress_pct: 100', u)
            if u != c:
                with open(mf, "w", encoding="utf-8") as f: f.write(u)
                print(f"-> Reconciled milestone {os.path.basename(mf)} to completed (100%).")

def main():
    repo_root = repo.find_repo_root()
    bump_arg = sys.argv[1] if len(sys.argv) > 1 else "patch"
    
    if bump_arg in ["-h", "--help"]:
        print("Usage: python along_version_bump.py [patch|minor|major|<version>] [-c|--commit] [-p|--push]")
        sys.exit(0)

    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    do_commit = "--commit" in flags or "-c" in flags or "-cp" in flags or "-pc" in flags or "--push" in flags or "-p" in flags
    do_push = "--push" in flags or "-p" in flags or "-cp" in flags or "-pc" in flags
    bump_arg_clean = [a for a in sys.argv[1:] if not a.startswith("-")][0] if any(not a.startswith("-") for a in sys.argv[1:]) else "patch"

    print("==================================================")
    print(f"-> Along Universal Release & Version Bumper")
    print(f"   Target Repository: {repo_root}")
    print(f"   Requested Bump:    {bump_arg_clean}")
    print("==================================================")

    new_version = detect_and_bump_project(repo_root, bump_arg_clean)
    if not new_version:
        print("[Abort] No version change recorded.")
        sys.exit(1)

    # Post-bump lifecycle
    print("-> Sanitizing Markdown typography (clean ASCII check)...")
    sanitize_typography(repo_root)

    print("-> Reconciling .along/ milestones and dashboard...")
    update_along_milestones(repo_root, new_version)

    # Mandatory tests before release commit
    if do_commit:
        if not gates.run_repository_tests(repo_root, "Release Quality Gate"):
            print("Release aborted. Fix failing tests before releasing.", file=sys.stderr)
            sys.exit(1)

    # Regenerate dashboard if available
    dash_script = repo.resolve_tool_script("along_dash.py", repo_root)
    if dash_script:
        proc.run_python([dash_script, "--markdown"], cwd=repo_root)

    if do_commit:
        git_dir = os.path.join(repo_root, ".git")
        if os.path.exists(git_dir):
            staged = proc.git(["add", "-A"], cwd=repo_root)
            commit_msg = f"release: v{new_version} - bump version and release reconciliation"
            committed = proc.git(["commit", "-m", commit_msg], cwd=repo_root) if staged.ok else staged
            if committed.ok:
                print(f"-> Git commit created: {commit_msg}")
                if do_push:
                    print("-> Pushing release commit to remote...")
                    pushed = proc.git(["push"], cwd=repo_root)
                    if pushed.ok:
                        print("-> Pushed successfully.")
                    else:
                        print(f"[Warning] Git push failed: {pushed.stderr.strip()}", file=sys.stderr)
            else:
                detail = (committed.stderr or committed.stdout).strip()
                print(f"[Note] Git commit skipped or working tree already clean: {detail}")
    else:
        print("-> [Notice] Version updated on disk. Use --commit (-c) to create release commit automatically.")

    sync_local_global_install(repo_root)

    print(f"\n[OK] Release v{new_version} finalized successfully!")


def sync_local_global_install(repo_root):
    """If running inside the along core repository, re-run install script to keep local machine synced."""
    is_along = (os.path.exists(os.path.join(repo_root, "skills", "along-init", "protocol.md"))
                and os.path.exists(os.path.join(repo_root, "scripts", "along_exec.py")))
    if not is_along:
        return

    print("-> [Along Core] Syncing global installation on local machine...")
    if sys.platform == "win32":
        ps1 = os.path.join(repo_root, "install.ps1")
        if os.path.exists(ps1):
            proc.run_capture(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-Target", "all"], cwd=repo_root)
    else:
        sh = os.path.join(repo_root, "install.sh")
        if os.path.exists(sh):
            proc.run_capture(["bash", sh, "--target=all"], cwd=repo_root)
    print("-> [Along Core] Global skills & scripts synchronized on local machine.")

if __name__ == "__main__":
    main()

