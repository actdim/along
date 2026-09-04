#!/usr/bin/env python3
"""
along_version_bump.py - Universal Project Version Bumper & Release Pipeline for Along.

Supports:
- Execution of project-specific `.along/scripts/bump_version.py` (if present)
- Auto-detection and synthesis for Node.js (package.json), Python (pyproject.toml/setup.py),
  Rust (Cargo.toml), .NET (Directory.Build.props/*.csproj), and generic VERSION files.
- Development mode for actdim/along protocol repo.
- Interactive fallback guidance if stack is custom/ambiguous.
- Milestone reconciliation, CHANGELOG entry, release commit, and annotated tag.

Order of operations, and why it is this order
--------------------------------------------
Every gate runs BEFORE the first byte is written: the tests, the typography check, and the
Markdown link check. The engine used to bump the version, rewrite the whole tree with the
sanitizer, flip milestone files to `completed`, regenerate the dashboard, and only then run
the tests - and only when `--commit` was passed, so a plain `patch` verified nothing at all.
A failing gate printed "Release aborted" and exited 1 over a tree that was already
half-released, with no way back. See
`[bug--release-engine-mutates-before-tests-and-reinstalls-globals]`.

The mutations that follow the gates go through `alongkit.transaction.FileTransaction`, so a
failure anywhere up to the git commit restores every file byte for byte and reports what it
put back. Once the commit exists there is nothing safe to undo, so the transaction closes.

A release no longer reinstalls the machine's global agent configuration. It used to run
`install.ps1 -Target all` at the end of every bump: that deletes and recreates
`~/.claude/rules` (destroying user-authored rules), recopies skill folders for four
providers, and edits MCP configuration - with the output captured and the exit code
ignored, so the success line printed even when the install failed. Installing globally is
`/along-update` or the installer, run by a human who meant it.

The typography step verifies and aborts; it does not rewrite the tree. Pass
`--fix-typography` to opt into the rewrite, which is then applied inside the transaction so
a later abort restores it. See `[bug--typography-sanitizer-destroys-non-utf8-files]`.
"""

import sys
import os
import re
import json
import glob
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alongkit import bootstrap
bootstrap.ensure_deps()


from alongkit import (frontmatter, gates, proc, repo, sanitizer, semver, textio,
                      transaction)

#: Label every gate and abort message carries, so the source of a failure is unambiguous.
GATE_LABEL = "Release Quality Gate"


class ReleaseAborted(RuntimeError):
    """A release step failed. `main` rolls the transaction back and exits non-zero.

    Nothing in this engine calls `sys.exit` past the argument parsing: an exit would
    skip the rollback and leave exactly the half-released tree this issue is about.
    """


def calculate_next_version(current_v, bump_type):
    """Next version string, or an abort the caller cannot recover from."""
    try:
        return semver.calculate_next(current_v, bump_type)
    except ValueError as exc:
        raise ReleaseAborted(str(exc)) from exc

def is_along_dev_repo(repo_root):
    return (
        os.path.exists(os.path.join(repo_root, "skills", "along-init", "protocol.md")) and
        os.path.exists(os.path.join(repo_root, "scripts", "along_update.py"))
    )


def rewrite_version_in_file(tx, path, substitutions):
    """Apply `(pattern, replacement)` pairs to `path` through the transaction.

    True when the file changed. The read is strict UTF-8 and the write adds no BOM and
    preserves the file's line endings, so a version bump never becomes an encoding
    change; a file that is not valid UTF-8 aborts the release instead of being rewritten
    lossily, which is the defect `[bug--typography-sanitizer-destroys-non-utf8-files]`
    documents for the sanitizer.
    """
    if not os.path.exists(path):
        return False
    try:
        original = textio.read_text(path, strict=True)
    except (OSError, UnicodeDecodeError) as exc:
        raise ReleaseAborted(f"cannot read {repo.safe_relpath(path, tx.root)}: {exc}") from exc

    updated = original
    for pattern, replacement in substitutions:
        updated = re.sub(pattern, replacement, updated)
    if updated == original:
        return False
    tx.write(path, updated)
    return True


def bump_along_dev_repo(repo_root, new_version, tx):
    """Bumps version across actdim/along internal files."""
    modified_files = []

    def apply(path, substitutions):
        if rewrite_version_in_file(tx, path, substitutions):
            modified_files.append(path)

    protocol_line = (r'# ALONG-PROTOCOL v\d+\.\d+\.\d+', f'# ALONG-PROTOCOL v{new_version}')
    protocol_mention = (r'ALONG-PROTOCOL v\d+\.\d+\.\d+', f'ALONG-PROTOCOL v{new_version}')

    # 1. Update skills/along-init/protocol.md
    apply(os.path.join(repo_root, "skills", "along-init", "protocol.md"), [protocol_line])

    # 2. Update all skills/*/SKILL.md
    for sdir in sorted(glob.glob(os.path.join(repo_root, "skills", "along-*"))):
        apply(os.path.join(sdir, "SKILL.md"), [
            (r'\[v\d+\.\d+\.\d+\]', f'[v{new_version}]'),
            (r'version: "\d+\.\d+\.\d+"', f'version: "{new_version}"'),
            protocol_mention,
        ])

    # 3. Update root AGENTS.md
    apply(os.path.join(repo_root, "AGENTS.md"), [protocol_line])

    # 4. Update README.md
    apply(os.path.join(repo_root, "README.md"), [
        (r'# Along \(v\d+\.\d+\.\d+\)', f'# Along (v{new_version})'),
        protocol_mention,
        (r'Skills & Slash Commands \(v\d+\.\d+\.\d+\)',
         f'Skills & Slash Commands (v{new_version})'),
    ])

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
        apply(const_path, [(r'CURRENT_PROTOCOL_VERSION = "\d+\.\d+\.\d+"',
                            f'CURRENT_PROTOCOL_VERSION = "{new_version}"')])



    # 8. Update llms.txt and llms-full.txt (both root and .well-known/)
    for llm_file in [
        "llms.txt", "llms-full.txt",
        os.path.join(".well-known", "llms.txt"),
        os.path.join(".well-known", "llms-full.txt"),
    ]:
        apply(os.path.join(repo_root, llm_file), [
            protocol_mention,
            (r'Along \(v\d+\.\d+\.\d+\)', f'Along (v{new_version})'),
        ])

    # 9. Update package.json and packages/dashboard-ui/package.json
    for pkg_file in ["package.json", os.path.join("packages", "dashboard-ui", "package.json")]:
        apply(os.path.join(repo_root, pkg_file),
              [(r'"version":\s*"\d+\.\d+\.\d+"', f'"version": "{new_version}"')])

    # 10. Update dashboard/app.py
    apply(os.path.join(repo_root, "dashboard", "app.py"),
          [(r'version="\d+\.\d+\.\d+"', f'version="{new_version}"')])

    return modified_files

def synthesize_script(script_path, content, tx=None):
    if tx is not None:
        tx.protect(script_path)
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    textio.write_text(script_path, content)
    try:
        os.chmod(script_path, 0o755)
    except OSError:
        pass
    print(f"-> Generated project-specific version bumper in: {script_path}")

def detect_and_bump_project(repo_root, bump_arg, tx):
    """Write the new version into this project's manifests. Returns the new version.

    Every write goes through `tx`, so a failure in a later release step restores the
    manifests. The one exception is a project's own `.along/scripts/bump_version.py`,
    whose writes this engine cannot see; that is recorded on the transaction and named in
    the rollback report rather than being quietly assumed to be undone.
    """
    custom_script = os.path.join(repo.state_dir(repo_root), "scripts", "bump_version.py")
    if os.path.exists(custom_script):
        print(f"-> Executing custom project script: {custom_script} {bump_arg}")
        tx.mark_unrestorable(
            f"{repo.safe_relpath(custom_script, repo_root)} wrote paths this engine "
            "cannot see; inspect `git status` and revert them by hand if needed")
        res = proc.run_python([custom_script, bump_arg], cwd=repo_root)
        if res.returncode != 0:
            raise ReleaseAborted(f"custom bump script failed:\n{res.stderr.strip()}")
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
        files = bump_along_dev_repo(repo_root, new_v, tx)
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
            tx.write(pkg_json, json.dumps(data, indent=2) + "\n")

            # package-lock.json
            pkg_lock = os.path.join(repo_root, "package-lock.json")
            if os.path.exists(pkg_lock):
                with open(pkg_lock, "r", encoding="utf-8") as f:
                    lock_data = json.load(f)
                lock_data["version"] = new_v
                if "packages" in lock_data and "" in lock_data["packages"]:
                    lock_data["packages"][""]["version"] = new_v
                tx.write(pkg_lock, json.dumps(lock_data, indent=2) + "\n")

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
''', tx)
            print(f"-> [Node.js] Bumped package.json: v{cur_v} -> v{new_v}")
            return new_v
        except (OSError, ValueError, KeyError) as exc:
            raise ReleaseAborted(f"failed to bump package.json: {exc}") from exc

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
                tx.write(pyproject, u)
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
''', tx)
                print(f"-> [Python] Bumped pyproject.toml: v{cur_v} -> v{new_v}")
                return new_v
        except (OSError, ValueError) as exc:
            raise ReleaseAborted(f"failed to bump pyproject.toml: {exc}") from exc

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
                tx.write(cargo_toml, u)
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
''', tx)
                print(f"-> [Rust] Bumped Cargo.toml: v{cur_v} -> v{new_v}")
                return new_v
        except (OSError, ValueError) as exc:
            raise ReleaseAborted(f"failed to bump Cargo.toml: {exc}") from exc

    # Generic VERSION file
    version_file = os.path.join(repo_root, "VERSION")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f: cur_v = f.read().strip()
        new_v = calculate_next_version(cur_v, bump_arg)
        tx.write(version_file, new_v + "\n")
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

typography_gate = gates.typography_gate


def release_preflight(repo_root, skip_verify=False, fix_typography=False):
    """Run every gate before the release writes anything.

    Returns the absolute paths the typography rule wants to rewrite, so the mutation
    stage can protect them before `--fix-typography` touches them. Raises ReleaseAborted
    on the first failing gate, at which point nothing has been written at all.

    Unconditional, not conditional on `--commit`: the previous version ran its tests only
    when it was also going to commit, so `along_version_bump.py patch` shipped a version
    number no gate had ever looked at.
    """
    if skip_verify:
        print("-> [Notice] --no-verify: tests, typography, and link gates skipped.")
        return []

    if not gates.run_repository_tests(repo_root, GATE_LABEL):
        raise ReleaseAborted("automated tests failed")

    report = gates.run_sanitizer(repo_root, verbose=False)
    for skipped in report.skipped:
        print(f"-> [{GATE_LABEL}] typography: skipped {skipped.path} ({skipped.reason})")
    if report.clean:
        print(f"-> [{GATE_LABEL}] Typography clean ({report.files_scanned} files scanned).")
        pending = []
    elif fix_typography:
        print(f"-> [{GATE_LABEL}] Typography findings to repair:\n"
              f"{sanitizer.format_report(report)}")
        pending = [os.path.join(repo_root, f.path) for f in report.findings]
    else:
        print(f"[Error] {GATE_LABEL}: banned typography found.\n"
              f"{sanitizer.format_report(report)}", file=sys.stderr)
        raise ReleaseAborted("banned typography found; re-run with --fix-typography "
                             "to apply these replacements, or fix them by hand")

    if not gates.link_integrity_gate(repo_root, GATE_LABEL):
        raise ReleaseAborted("broken relative Markdown links")

    return pending


def milestone_matches_version(slug, version):
    """True when `slug` names `version` as a whole component (`v3.0.0-...`, not `v3.0.01`).

    Matching used to be `new_version in os.path.basename(path)`, a substring test over the
    filename, so a bump to `1.5.0` also claimed any milestone whose name merely contained
    those characters.
    """
    if not slug:
        return False
    wanted = {version, f"v{version}"}
    return any(part in wanted for part in str(slug).split("-"))


def update_along_milestones(repo_root, new_version, tx):
    """Mark the milestone whose own slug carries `new_version` as completed.

    Front-matter only, through `frontmatter.update`. The previous implementation ran two
    unanchored `re.sub` calls over the whole file, so a `status: open` or `progress_pct: 40`
    appearing anywhere in the body - a target-issue table, a quoted example - was rewritten
    as well. Same defect class as `[bug--issue-done-corrupts-status-and-drops-completed]`,
    fixed there and left behind here.
    """
    if not new_version:
        return []

    updated = []
    pattern = os.path.join(repo.state_dir(repo_root), "MILESTONES", "*.md")
    for path in sorted(glob.glob(pattern)):
        name = os.path.basename(path)
        try:
            content = textio.read_text(path, strict=True)
            fields, _ = frontmatter.parse(content, path=path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(f"[Warning] cannot read milestone {name}: {exc}", file=sys.stderr)
            continue

        if not milestone_matches_version(fields.get("slug"), new_version):
            continue
        if content.startswith(frontmatter.BOM):
            print(f"-> Milestone {name}: dropping a UTF-8 BOM while updating front-matter.")

        rewritten = frontmatter.update(
            content, {"status": "completed", "progress_pct": 100}, path=path)
        if rewritten == content:
            continue
        tx.write(path, rewritten)
        updated.append(path)
        print(f"-> Reconciled milestone {name} to completed (100%).")

    if not updated:
        print(f"-> No milestone slug names v{new_version}; nothing to reconcile.")
    return updated


def release_log_entries(repo_root, limit=200):
    """Commit subjects since the most recent tag, newest first; empty when git cannot say."""
    if not os.path.exists(os.path.join(repo_root, ".git")):
        return []

    described = proc.git(["describe", "--tags", "--abbrev=0"], cwd=repo_root)
    span = f"{described.out}..HEAD" if described.ok and described.out else "HEAD"
    log = proc.git(["log", span, "--no-merges", f"--max-count={limit}",
                    "--pretty=format:%s"], cwd=repo_root)
    if not log.ok:
        print(f"[Warning] cannot read git log for the CHANGELOG: {log.stderr.strip()}",
              file=sys.stderr)
        return []
    return log.lines()


def update_changelog(repo_root, new_version, tx):
    """Prepend a `## v<version>` section to CHANGELOG.md, listing commits since the last tag.

    The skill describes itself as a release orchestrator and produced neither a changelog
    nor a tag. Entries are the subjects git actually recorded rather than a generated
    summary of them, so the section is verifiable against `git log`.
    """
    path = os.path.join(repo_root, "CHANGELOG.md")
    entries = release_log_entries(repo_root)
    section = [f"## v{new_version} - {datetime.now().strftime('%Y-%m-%d')}", ""]
    section += ([f"- {entry}" for entry in entries] if entries else
               ["- No commits recorded since the previous release tag."])
    section.append("")
    block = "\n".join(section)

    newline = "\n"
    if os.path.exists(path):
        try:
            existing = textio.read_text(path, strict=True)
        except (OSError, UnicodeDecodeError) as exc:
            raise ReleaseAborted(f"cannot read CHANGELOG.md: {exc}") from exc
        newline = textio.detect_newline(existing)
        flat = existing.replace("\r\n", "\n").replace("\r", "\n")
        if re.search(r'^## v' + re.escape(new_version) + r'\b', flat, re.MULTILINE):
            print(f"-> CHANGELOG.md already carries a v{new_version} section; left as is.")
            return False
        first_section = re.search(r'^## ', flat, re.MULTILINE)
        if first_section:
            head, tail = flat[:first_section.start()], flat[first_section.start():]
        else:
            head, tail = flat.rstrip("\n") + "\n\n", ""
        updated = head + block + "\n" + tail
    else:
        updated = ("# Changelog\n\nAll notable changes to this project, newest first.\n\n"
                   + block + "\n")

    tx.write(path, updated, newline=newline)
    print(f"-> CHANGELOG.md: added the v{new_version} section ({len(entries)} commit(s)).")
    return True


def create_release_commit(repo_root, new_version, paths, tx, do_push=False):
    """Stage exactly `paths`, commit, and create the annotated tag `v<version>`.

    Staging used to be `git add -A`, which swept the entire working tree into the release
    commit: every unrelated edit a developer happened to have open shipped inside it.
    `paths` is what this release actually wrote.

    Returns True when the release is complete. The transaction is closed the moment the
    commit exists, because after that a rollback would destroy committed work rather than
    repair anything.
    """
    if not os.path.exists(os.path.join(repo_root, ".git")):
        print("-> [Notice] Not a git work tree; skipping commit and tag.")
        return True
    if not paths:
        print("-> [Notice] The release wrote no files; nothing to commit.")
        return True

    staged = proc.git(["add", "--", *paths], cwd=repo_root)
    if not staged.ok:
        raise ReleaseAborted(f"git staging failed: {staged.stderr.strip()}")

    commit_msg = f"release: v{new_version} - bump version and release reconciliation"
    committed = proc.git(["commit", "-m", commit_msg], cwd=repo_root)
    if not committed.ok:
        detail = (committed.stderr or committed.stdout).strip()
        if "nothing to commit" in detail:
            print(f"-> [Notice] Nothing staged to commit: {detail}")
            return True
        raise ReleaseAborted(f"git commit failed: {detail}")

    tx.commit()
    print(f"-> Git commit created: {commit_msg}")

    complete = True
    tag = f"v{new_version}"
    tagged = proc.git(["tag", "-a", tag, "-m", f"release: {tag}"], cwd=repo_root)
    if tagged.ok:
        print(f"-> Annotated tag created: {tag}")
    else:
        print(f"[Error] Could not create the annotated tag {tag}: "
              f"{(tagged.stderr or tagged.stdout).strip()}", file=sys.stderr)
        complete = False

    if do_push:
        print("-> Pushing release commit and tags to remote...")
        pushed = proc.git(["push", "--follow-tags"], cwd=repo_root)
        if pushed.ok:
            print("-> Pushed successfully.")
        else:
            # Reported as an error, not a warning: the commit and the tag exist locally
            # and the remote does not have them, which is not a successful release.
            print(f"[Error] Git push failed: {(pushed.stderr or pushed.stdout).strip()}",
                  file=sys.stderr)
            complete = False

    return complete


def main():
    repo_root = repo.find_repo_root()
    bump_arg = sys.argv[1] if len(sys.argv) > 1 else "patch"

    if bump_arg in ["-h", "--help"]:
        print("Usage: python along_version_bump.py [patch|minor|major|<version>] "
              "[-c|--commit] [-p|--push] [--fix-typography] [-n|--no-verify]")
        sys.exit(0)

    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    fix_typography = "--fix-typography" in flags
    skip_verify = "--no-verify" in flags or "-n" in flags
    do_commit = "--commit" in flags or "-c" in flags or "-cp" in flags or "-pc" in flags or "--push" in flags or "-p" in flags
    do_push = "--push" in flags or "-p" in flags or "-cp" in flags or "-pc" in flags
    bump_arg_clean = [a for a in sys.argv[1:] if not a.startswith("-")][0] if any(not a.startswith("-") for a in sys.argv[1:]) else "patch"

    print("==================================================")
    print(f"-> Along Universal Release & Version Bumper")
    print(f"   Target Repository: {repo_root}")
    print(f"   Requested Bump:    {bump_arg_clean}")
    print("==================================================")

    tx = transaction.FileTransaction(repo_root, "release")
    try:
        # Gates first, on the untouched tree.
        pending_typography = release_preflight(repo_root, skip_verify=skip_verify,
                                               fix_typography=fix_typography)

        # Mutations, all of them recorded on the transaction.
        for path in pending_typography:
            tx.protect(path)
        if pending_typography and not typography_gate(repo_root, GATE_LABEL, allow_fix=True):
            raise ReleaseAborted("the typography findings could not be repaired")

        new_version = detect_and_bump_project(repo_root, bump_arg_clean, tx)
        if not new_version:
            raise ReleaseAborted("no version change recorded")

        print("-> Reconciling .along/ milestones...")
        update_along_milestones(repo_root, new_version, tx)
        update_changelog(repo_root, new_version, tx)

        written = [repo.normalize_posix(p) for p in tx.changed()]
        complete = True
        if do_commit:
            complete = create_release_commit(repo_root, new_version, written, tx,
                                             do_push=do_push)
        else:
            print(f"-> Version updated on disk across {len(written)} file(s):")
            for rel in written:
                print(f"   {rel}")
            print("-> [Notice] Use --commit (-c) to create the release commit and tag.")
            tx.commit()
    except ReleaseAborted as exc:
        report_rollback(tx, str(exc))
        sys.exit(1)
    except Exception as exc:
        # Not swallowed: the tree is restored first, then the traceback is re-raised so
        # the defect is visible instead of being reported as a tidy release failure.
        report_rollback(tx, f"unexpected error: {exc}")
        raise

    if not complete:
        print(f"\n[Error] Release v{new_version} is incomplete; see the errors above.",
              file=sys.stderr)
        sys.exit(1)
    print(f"\n[OK] Release v{new_version} finalized successfully!")


def report_rollback(tx, reason):
    """Undo the release's file mutations and say exactly what was put back."""
    restored = tx.rollback()
    print(f"\n[Abort] Release aborted: {reason}", file=sys.stderr)
    if restored:
        print(f"-> Rolled back {len(restored)} file(s):", file=sys.stderr)
        for rel in restored:
            print(f"   {repo.normalize_posix(rel)}", file=sys.stderr)
    else:
        print("-> Nothing was written; the working tree is untouched.", file=sys.stderr)
    for note in tx.unrestorable:
        print(f"[Warning] not rolled back: {note}", file=sys.stderr)


if __name__ == "__main__":
    main()
