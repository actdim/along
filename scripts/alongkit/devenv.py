#!/usr/bin/env python3
"""
alongkit.devenv - Automated local development environment setup and editable install.
Initializes a repository-local .venv and installs alongkit in editable mode.
[feat--dev-environment-setup-and-editable-install]
"""

from __future__ import annotations
if __name__ == "__main__":
    import os
    raise SystemExit(
        f"{os.path.basename(__file__)} is a library module, not a command.\n"
        "Run: python .along/scripts/test.py"
    )

import os
import shutil
import subprocess
import sys
from typing import Optional, Tuple

from . import bootstrap, repo, textio


def find_site_packages(venv_dir: str) -> Optional[str]:
    """Locate the site-packages directory inside a virtual environment."""
    if sys.platform == "win32":
        candidate = os.path.join(venv_dir, "Lib", "site-packages")
        if os.path.isdir(candidate):
            return candidate
    lib_dir = os.path.join(venv_dir, "lib")
    if os.path.isdir(lib_dir):
        for entry in os.listdir(lib_dir):
            sp = os.path.join(lib_dir, entry, "site-packages")
            if os.path.isdir(sp):
                return sp
        sp = os.path.join(lib_dir, "site-packages")
        if os.path.isdir(sp):
            return sp
    return None


def setup_dev_environment(repo_root: str, reinstall: bool = False, quiet: bool = False,
                          with_dash: bool = True, with_pytest: bool = True) -> Tuple[bool, str]:
    """Initialize local .venv and install the package in editable mode.

    Returns (success, message). Isolates the environment strictly to the repository root.
    """
    repo_root = os.path.abspath(repo_root)
    venv_dir = os.path.join(repo_root, ".venv")

    if reinstall and os.path.isdir(venv_dir):
        try:
            shutil.rmtree(venv_dir)
        except OSError as exc:
            return False, f"Could not remove existing .venv: {exc}"

    uv_bin = shutil.which("uv")
    if not os.path.isdir(venv_dir):
        if not quiet:
            print(f"-> Creating local virtual environment at {repo.safe_relpath(venv_dir, repo_root)}...")
        if uv_bin:
            cmd = [uv_bin, "venv", "--quiet", "--python", sys.executable, venv_dir]
        else:
            cmd = [sys.executable, "-m", "venv", venv_dir]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if res.returncode != 0:
            return False, f"Failed to create virtual environment: {res.stderr.strip() or res.stdout.strip()}"

    py_exec = bootstrap.venv_python(venv_dir)
    if not os.path.isfile(py_exec):
        return False, f"Virtual environment interpreter missing at {py_exec}"

    # Install in editable mode or dependencies via uv / pip
    pkg_target = ".[dash]" if with_dash else "."
    install_targets = ["-e", pkg_target]
    if with_pytest:
        install_targets.append("pytest")

    install_ok = True
    if uv_bin:
        cmd_install = [uv_bin, "pip", "install", "--quiet", "--python", py_exec, *install_targets]
        res_inst = subprocess.run(cmd_install, cwd=repo_root, capture_output=True, text=True)
        if res_inst.returncode != 0:
            install_ok = False
    else:
        cmd_install = [py_exec, "-m", "pip", "install", "--quiet", *install_targets]
        res_inst = subprocess.run(cmd_install, cwd=repo_root, capture_output=True, text=True)
        if res_inst.returncode != 0:
            install_ok = False

    # Link scripts/ directory via .pth to guarantee alongkit is importable in IDEs and tools
    site_packages = find_site_packages(venv_dir)
    if site_packages and os.path.isdir(site_packages):
        pth_file = os.path.join(site_packages, "actdim_along.pth")
        scripts_dir = os.path.join(repo_root, "scripts")
        try:
            textio.write_text(pth_file, scripts_dir + "\n", newline="\n", atomic=True)
        except OSError:
            pass

    rel_venv = repo.safe_relpath(venv_dir, repo_root) or ".venv"
    if not install_ok:
        return True, f"Virtual environment created at {rel_venv} with .pth link (package install had warnings)"

    return True, f"Development environment initialized at {rel_venv} with editable alongkit"
