#!/usr/bin/env python3
"""
alongkit.worktree - Git worktree workspace isolation and environment readiness engine.

Provides full lifecycle management for isolated development workspaces:
- Evaluates host runtime capability and environment readiness (fail-fast gate)
- Provisions isolated Git worktrees under `.along/worktrees/<slug>`
- Links dependency directories (node_modules, .venv) via NTFS junctions on Windows
  or symbolic links on POSIX without duplicating packages
- Propagates untracked configuration (.env, .env.local) to worktree
- Preserves session blackboard (.along/.session/<slug>) across worktree teardown
- Resilient teardown with junction pre-unlinking, exponential backoff, and
  deferred garbage collection to mitigate Windows NTFS file handle locks
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: along worktree --help   (or: python scripts/along_exec.py worktree --help)"
    )

import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import proc, repo, textio
from .install import is_link

MANIFEST_FILENAME: str = ".along-worktree.json"
PENDING_TRASH_FILENAME: str = ".pending_worktrees.json"


def _utc_now_iso() -> str:
    """ISO 8601 formatted UTC timestamp with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class WorktreeInfo:
    """Metadata describing an active isolated Along worktree."""
    slug: str
    path: str
    branch: str
    created_at: str
    linked_dirs: List[str] = field(default_factory=list)
    copied_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_worktree_path(repo_root: str, slug: str) -> str:
    """Return the canonical filesystem path for a worktree given its slug."""
    clean_slug = slug.strip().replace(" ", "-")
    return os.path.join(repo.state_dir(repo_root), "worktrees", clean_slug)


def is_worktree(path: str) -> bool:
    """Check if the given path is a Git worktree (carries a .git file rather than directory)."""
    git_file = os.path.join(path, ".git")
    if not os.path.isfile(git_file):
        return False
    try:
        content = textio.read_text(git_file).strip()
        return content.startswith("gitdir:")
    except (OSError, UnicodeDecodeError):
        return False


def link_directory(target_path: str, link_path: str) -> bool:
    """Create a directory link: NTFS junction on Windows, symlink on POSIX.

    Target must be an absolute path to an existing directory.
    Link must not exist prior to creation.
    """
    target_abs = os.path.abspath(target_path)
    link_abs = os.path.abspath(link_path)
    if not os.path.isdir(target_abs):
        return False
    if os.path.exists(link_abs) or is_link(link_abs):
        return False

    os.makedirs(os.path.dirname(link_abs), exist_ok=True)
    if os.name == "nt":
        # On Windows, try os.symlink first, then fall back to directory junction (mklink /J)
        try:
            os.symlink(target_abs, link_abs, target_is_directory=True)
            return True
        except OSError:
            pass
        res = proc.run_capture(["cmd.exe", "/c", "mklink", "/J", link_abs, target_abs])
        return res.ok and (os.path.exists(link_abs) or is_link(link_abs))
    else:
        try:
            os.symlink(target_abs, link_abs, target_is_directory=True)
            return True
        except OSError:
            return False


def unlink_directory(link_path: str) -> bool:
    """Safely unlink a directory link or junction without touching target contents.

    Uses os.rmdir or os.unlink. NEVER uses shutil.rmtree.
    """
    link_abs = os.path.abspath(link_path)
    if not (os.path.exists(link_abs) or is_link(link_abs)):
        return True

    # For directory junctions or directory symlinks
    if is_link(link_abs):
        try:
            os.rmdir(link_abs)
            return True
        except OSError:
            pass
        try:
            os.unlink(link_abs)
            return True
        except OSError:
            pass
    elif os.path.islink(link_abs):
        try:
            os.unlink(link_abs)
            return True
        except OSError:
            pass

    # Empty directory fallback
    try:
        os.rmdir(link_abs)
        return True
    except OSError:
        return False


def is_worktree_supported(repo_root: str) -> Tuple[bool, str]:
    """Verify if the host repository and filesystem support worktree isolation with environment readiness."""
    repo_root_abs = os.path.abspath(repo_root)

    # 1. Verify Git is available and inside a Git work tree
    res = proc.git(["rev-parse", "--is-inside-work-tree"], cwd=repo_root_abs)
    if not res.ok:
        return False, "Not inside a valid Git repository"

    # 2. Verify repository has at least one commit (HEAD resolves)
    res = proc.git(["rev-parse", "--verify", "HEAD"], cwd=repo_root_abs)
    if not res.ok:
        return False, "Git repository has no initial commit (HEAD cannot be resolved)"

    # 3. Test filesystem linking capability (NTFS junction or symlink)
    state_directory = repo.state_dir(repo_root_abs)
    test_dir = os.path.join(state_directory, ".link_test_src")
    test_link = os.path.join(state_directory, ".link_test_dst")
    try:
        os.makedirs(test_dir, exist_ok=True)
        if os.path.exists(test_link) or is_link(test_link):
            unlink_directory(test_link)
        ok = link_directory(test_dir, test_link)
        if not ok:
            return False, "Filesystem does not support NTFS junctions or symbolic links"
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return False, f"Filesystem link test encountered error: {exc}"
    finally:
        if os.path.exists(test_link) or is_link(test_link):
            unlink_directory(test_link)
        if os.path.isdir(test_dir):
            try:
                os.rmdir(test_dir)
            except OSError:
                pass

    return True, "Worktree isolation and environment readiness supported"


def link_environment(repo_root: str, worktree_path: str, slug: str) -> Tuple[List[str], List[str]]:
    """Link dependencies, propagate configurations, and link session blackboard into worktree."""
    repo_root_abs = os.path.abspath(repo_root)
    worktree_abs = os.path.abspath(worktree_path)
    linked_dirs: List[str] = []
    copied_files: List[str] = []

    # 1. Root dependency folders
    for dep_name in ("node_modules", ".venv", "venv", "env"):
        dep_src = os.path.join(repo_root_abs, dep_name)
        if os.path.isdir(dep_src) and not is_link(dep_src):
            dep_dst = os.path.join(worktree_abs, dep_name)
            if not os.path.exists(dep_dst) and not is_link(dep_dst):
                if link_directory(dep_src, dep_dst):
                    linked_dirs.append(dep_name)

    # 2. Subproject dependency folders (e.g. packages/*/node_modules)
    packages_dir = os.path.join(repo_root_abs, "packages")
    if os.path.isdir(packages_dir):
        for pkg in os.listdir(packages_dir):
            pkg_dep = os.path.join(packages_dir, pkg, "node_modules")
            if os.path.isdir(pkg_dep) and not is_link(pkg_dep):
                rel_dep = os.path.relpath(pkg_dep, repo_root_abs).replace("\\", "/")
                target_link = os.path.join(worktree_abs, rel_dep)
                if not os.path.exists(target_link) and not is_link(target_link):
                    if link_directory(pkg_dep, target_link):
                        linked_dirs.append(rel_dep)

    # 3. Propagate untracked local environment and configuration files
    for config_name in (".env", ".env.local", ".env.development", ".env.test", "local.settings.json"):
        cfg_src = os.path.join(repo_root_abs, config_name)
        if os.path.isfile(cfg_src) and not is_link(cfg_src):
            cfg_dst = os.path.join(worktree_abs, config_name)
            if not os.path.exists(cfg_dst):
                try:
                    shutil.copy2(cfg_src, cfg_dst)
                    copied_files.append(config_name)
                except OSError:
                    pass

    # 4. State preservation: link ephemeral session blackboard
    primary_session = os.path.join(repo.state_dir(repo_root_abs), ".session", slug)
    os.makedirs(primary_session, exist_ok=True)

    worktree_state = repo.state_dir(worktree_abs)
    worktree_session = os.path.join(worktree_state, ".session", slug)
    if not os.path.exists(worktree_session) and not is_link(worktree_session):
        os.makedirs(os.path.dirname(worktree_session), exist_ok=True)
        if link_directory(primary_session, worktree_session):
            rel_sess = os.path.relpath(worktree_session, worktree_abs).replace("\\", "/")
            linked_dirs.append(rel_sess)

    return linked_dirs, copied_files


def unlink_environment(worktree_path: str) -> None:
    """Read worktree manifest and safely unlink all linked directories."""
    worktree_abs = os.path.abspath(worktree_path)
    manifest_file = os.path.join(worktree_abs, MANIFEST_FILENAME)
    linked_dirs: List[str] = []

    if os.path.isfile(manifest_file):
        try:
            data = json.loads(textio.read_text(manifest_file))
            linked_dirs = data.get("linked_dirs", [])
        except (OSError, json.JSONDecodeError):
            pass

    # Unlink explicit entries from manifest
    for rel_path in linked_dirs:
        target = os.path.join(worktree_abs, rel_path)
        unlink_directory(target)

    # Fallback scan for common junction locations in worktree root
    for dep_name in ("node_modules", ".venv", "venv", "env"):
        target = os.path.join(worktree_abs, dep_name)
        if is_link(target):
            unlink_directory(target)


def _flush_session_state(repo_root: str, worktree_path: str, slug: str) -> None:
    """Ensure any session logs, reviews, or blackboard states are synchronized to the primary repo."""
    primary_session = os.path.join(repo.state_dir(repo_root), ".session", slug)
    worktree_session = os.path.join(repo.state_dir(worktree_path), ".session", slug)

    if not os.path.exists(worktree_session) or is_link(worktree_session):
        return

    # If worktree_session is an unlinked regular directory, copy all files back
    os.makedirs(primary_session, exist_ok=True)
    for root, _, files in os.walk(worktree_session):
        for f in files:
            src_file = os.path.join(root, f)
            rel_path = os.path.relpath(src_file, worktree_session)
            dst_file = os.path.join(primary_session, rel_path)
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            try:
                shutil.copy2(src_file, dst_file)
            except OSError:
                pass


def _register_pending_trash(repo_root: str, trash_path: str) -> None:
    """Record a locked directory in .along/.pending_worktrees.json for deferred cleanup."""
    pending_file = os.path.join(repo.state_dir(repo_root), PENDING_TRASH_FILENAME)
    trash_abs = os.path.abspath(trash_path)
    paths: List[str] = []
    if os.path.isfile(pending_file):
        try:
            data = json.loads(textio.read_text(pending_file))
            paths = data.get("trash_paths", [])
        except (OSError, json.JSONDecodeError):
            paths = []
    if trash_abs not in paths:
        paths.append(trash_abs)
    try:
        textio.write_text(pending_file, json.dumps({"trash_paths": paths}, indent=2) + "\n")
    except OSError:
        pass


def _ensure_git_exclude(repo_root: str) -> None:
    """Ensure .along/worktrees/ is excluded from Git status in .git/info/exclude."""
    git_dir = proc._find_git_dir(repo_root)
    if not git_dir:
        return
    info_dir = os.path.join(git_dir, "info")
    os.makedirs(info_dir, exist_ok=True)
    exclude_file = os.path.join(info_dir, "exclude")
    try:
        content = textio.read_text(exclude_file) if os.path.isfile(exclude_file) else ""
        lines_to_add = [entry for entry in (".along/worktrees/", ".along/.pending_worktrees.json") if entry not in content]
        if lines_to_add:
            new_content = (content.rstrip() + "\n" + "\n".join(lines_to_add) + "\n").lstrip()
            textio.write_text(exclude_file, new_content)
    except (OSError, UnicodeDecodeError):
        pass


def create_worktree(
    repo_root: str,
    slug: str,
    branch: Optional[str] = None,
    base_ref: Optional[str] = None,
) -> WorktreeInfo:
    """Provision an isolated Git worktree, link environment, and write manifest."""
    repo_root_abs = os.path.abspath(repo_root)
    _ensure_git_exclude(repo_root_abs)
    supported, reason = is_worktree_supported(repo_root_abs)
    if not supported:
        raise RuntimeError(f"Worktree creation aborted by fail-fast check: {reason}")

    clean_slug = slug.strip().replace(" ", "-")
    target_branch = branch or f"along/{clean_slug}"
    worktree_path = get_worktree_path(repo_root_abs, clean_slug)

    if os.path.exists(worktree_path):
        manifest_path = os.path.join(worktree_path, MANIFEST_FILENAME)
        if os.path.isfile(manifest_path):
            try:
                data = json.loads(textio.read_text(manifest_path))
                return WorktreeInfo(
                    slug=clean_slug,
                    path=worktree_path,
                    branch=data.get("branch", target_branch),
                    created_at=data.get("created_at", _utc_now_iso()),
                    linked_dirs=data.get("linked_dirs", []),
                    copied_files=data.get("copied_files", []),
                )
            except (OSError, json.JSONDecodeError):
                pass
        raise RuntimeError(f"Target worktree path already exists: {worktree_path}")

    # Check if branch exists
    chk = proc.git(["rev-parse", "--verify", f"refs/heads/{target_branch}"], cwd=repo_root_abs)
    if chk.ok:
        res = proc.git(["worktree", "add", worktree_path, target_branch], cwd=repo_root_abs)
    else:
        start_point = base_ref or "HEAD"
        res = proc.git(["worktree", "add", "-b", target_branch, worktree_path, start_point], cwd=repo_root_abs)

    if not res.ok:
        raise RuntimeError(f"git worktree add failed: {res.stderr or res.stdout}")

    # Link environment and dependencies
    linked_dirs, copied_files = link_environment(repo_root_abs, worktree_path, clean_slug)

    info = WorktreeInfo(
        slug=clean_slug,
        path=worktree_path,
        branch=target_branch,
        created_at=_utc_now_iso(),
        linked_dirs=linked_dirs,
        copied_files=copied_files,
    )

    # Save manifest
    manifest_file = os.path.join(worktree_path, MANIFEST_FILENAME)
    try:
        textio.write_text(manifest_file, json.dumps(info.to_dict(), indent=2) + "\n")
    except OSError:
        pass

    return info


def remove_worktree(
    repo_root: str,
    slug: str,
    force: bool = True,
    delete_branch: bool = True,
) -> bool:
    """Safely tear down a worktree with junction pre-unlinking, backoff, and trash quarantine."""
    repo_root_abs = os.path.abspath(repo_root)
    clean_slug = slug.strip().replace(" ", "-")
    worktree_path = get_worktree_path(repo_root_abs, clean_slug)

    # 1. Reset CWD if current process is inside worktree
    try:
        cwd = os.getcwd()
        if os.path.abspath(cwd).startswith(os.path.abspath(worktree_path)):
            os.chdir(repo_root_abs)
    except OSError:
        try:
            os.chdir(repo_root_abs)
        except OSError:
            pass

    if not os.path.exists(worktree_path):
        proc.git(["worktree", "prune"], cwd=repo_root_abs)
        if delete_branch:
            proc.git(["branch", "-D", f"along/{clean_slug}"], cwd=repo_root_abs)
        return True

    # 2. Flush session blackboard back to primary repository
    _flush_session_state(repo_root_abs, worktree_path, clean_slug)

    # 3. Unlink all junctions/symlinks
    unlink_environment(worktree_path)

    # 4. Remove worktree via Git with backoff retry loop
    removed = False
    remove_cmd = ["worktree", "remove", "--force", worktree_path] if force else ["worktree", "remove", worktree_path]
    for _ in range(4):
        res = proc.git(remove_cmd, cwd=repo_root_abs)
        if res.ok or not os.path.exists(worktree_path):
            removed = True
            break
        time.sleep(0.5)

    # 5. Handle directory leftovers or persistent Windows file handle locks
    if os.path.exists(worktree_path):
        try:
            shutil.rmtree(worktree_path)
            removed = True
        except OSError:
            # Unlock Git worktree tracking and quarantine directory
            proc.git(["worktree", "prune"], cwd=repo_root_abs)
            trash_name = f".trash_{clean_slug}_{int(time.time())}"
            trash_path = os.path.join(os.path.dirname(worktree_path), trash_name)
            try:
                os.rename(worktree_path, trash_path)
                _register_pending_trash(repo_root_abs, trash_path)
            except OSError:
                _register_pending_trash(repo_root_abs, worktree_path)

    # 6. Delete branch if requested
    if delete_branch:
        proc.git(["branch", "-D", f"along/{clean_slug}"], cwd=repo_root_abs)

    return removed


def merge_worktree(repo_root: str, slug: str, strategy: str = "squash") -> proc.Result:
    """Merge an isolated worktree branch into the primary working branch."""
    repo_root_abs = os.path.abspath(repo_root)
    clean_slug = slug.strip().replace(" ", "-")
    branch = f"along/{clean_slug}"

    chk = proc.git(["rev-parse", "--verify", f"refs/heads/{branch}"], cwd=repo_root_abs)
    if not chk.ok:
        return chk

    if strategy == "squash":
        return proc.git(["merge", "--squash", branch], cwd=repo_root_abs)
    return proc.git(["merge", "--ff-only", branch], cwd=repo_root_abs)


def list_worktrees(repo_root: str) -> List[Dict[str, Any]]:
    """List active Along worktrees and their environment readiness states."""
    repo_root_abs = os.path.abspath(repo_root)
    worktrees_dir = os.path.join(repo.state_dir(repo_root_abs), "worktrees")
    results: List[Dict[str, Any]] = []
    if not os.path.isdir(worktrees_dir):
        return results

    gw_res = proc.git(["worktree", "list", "--porcelain"], cwd=repo_root_abs)
    git_worktrees: Dict[str, Dict[str, str]] = {}
    current_entry: Dict[str, str] = {}
    for line in gw_res.lines():
        if line.startswith("worktree "):
            current_entry = {"path": line.split(" ", 1)[1].strip()}
        elif line.startswith("branch "):
            current_entry["branch"] = line.split(" ", 1)[1].strip()
            git_worktrees[os.path.normcase(os.path.abspath(current_entry["path"]))] = current_entry
        elif not line:
            if "path" in current_entry:
                git_worktrees[os.path.normcase(os.path.abspath(current_entry["path"]))] = current_entry
            current_entry = {}
    if "path" in current_entry:
        git_worktrees[os.path.normcase(os.path.abspath(current_entry["path"]))] = current_entry

    for item in sorted(os.listdir(worktrees_dir)):
        if item.startswith(".") or item.startswith("_"):
            continue
        wpath = os.path.join(worktrees_dir, item)
        if not os.path.isdir(wpath):
            continue

        manifest_file = os.path.join(wpath, MANIFEST_FILENAME)
        manifest: Dict[str, Any] = {}
        if os.path.isfile(manifest_file):
            try:
                manifest = json.loads(textio.read_text(manifest_file))
            except (OSError, json.JSONDecodeError):
                pass

        norm_key = os.path.normcase(os.path.abspath(wpath))
        git_info = git_worktrees.get(norm_key, {})
        branch = manifest.get("branch") or git_info.get("branch", f"along/{item}")
        if branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]

        results.append({
            "slug": item,
            "path": wpath,
            "branch": branch,
            "created_at": manifest.get("created_at"),
            "linked_dirs": manifest.get("linked_dirs", []),
            "copied_files": manifest.get("copied_files", []),
            "is_git_registered": norm_key in git_worktrees,
        })

    return results


def gc_worktrees(repo_root: str) -> int:
    """Prune orphaned Git worktrees and clean deferred trash directories."""
    repo_root_abs = os.path.abspath(repo_root)
    proc.git(["worktree", "prune"], cwd=repo_root_abs)
    cleaned = 0

    pending_file = os.path.join(repo.state_dir(repo_root_abs), PENDING_TRASH_FILENAME)
    if os.path.isfile(pending_file):
        try:
            data = json.loads(textio.read_text(pending_file))
            remaining = []
            for path in data.get("trash_paths", []):
                if os.path.exists(path):
                    try:
                        shutil.rmtree(path)
                        cleaned += 1
                    except OSError:
                        remaining.append(path)
                else:
                    cleaned += 1
            if remaining:
                textio.write_text(pending_file, json.dumps({"trash_paths": remaining}, indent=2) + "\n")
            else:
                os.remove(pending_file)
        except (OSError, json.JSONDecodeError):
            pass

    worktrees_dir = os.path.join(repo.state_dir(repo_root_abs), "worktrees")
    if os.path.isdir(worktrees_dir):
        for item in os.listdir(worktrees_dir):
            if item.startswith(".trash_"):
                target = os.path.join(worktrees_dir, item)
                try:
                    shutil.rmtree(target)
                    cleaned += 1
                except OSError:
                    pass

    return cleaned


class WorktreeManager:
    """High-level object-oriented interface for Git worktree management."""

    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)

    def is_supported(self) -> Tuple[bool, str]:
        return is_worktree_supported(self.repo_root)

    def create(self, slug: str, branch: Optional[str] = None, base_ref: Optional[str] = None) -> WorktreeInfo:
        return create_worktree(self.repo_root, slug, branch=branch, base_ref=base_ref)

    def remove(self, slug: str, force: bool = True, delete_branch: bool = True) -> bool:
        return remove_worktree(self.repo_root, slug, force=force, delete_branch=delete_branch)

    def merge(self, slug: str, strategy: str = "squash") -> proc.Result:
        return merge_worktree(self.repo_root, slug, strategy=strategy)

    def list(self) -> List[Dict[str, Any]]:
        return list_worktrees(self.repo_root)

    def gc(self) -> int:
        return gc_worktrees(self.repo_root)
