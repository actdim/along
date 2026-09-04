#!/usr/bin/env python3
"""
tests/test_skills_and_scripts.py - Comprehensive Unit Tests for Along Protocol & Skills Suite.

Guarantees:
1. Syntax & Compilation: Every Python file in scripts/ and skills/ is valid Python.
2. Anti-Corruption: No Python script contains Markdown headers or text instead of code.
3. Skill Manifests: Every skills/along-* directory contains valid SKILL.md with name and description.
4. Protocol Version Consistency: Versions across manifests, protocol.md, README.md, and scripts match.
5. Typography Sanitization: Zero non-ASCII typographic characters (em-dash, curly quotes, NBSP, ZWSP).
6. Engine CLI Execution: along_dash, along_update, migrate_protocol, along_exec, and along_commit run without errors.
7. Installer Integrity: install.ps1 and install.sh install the same artifact set.

Hermetic rule: every engine invocation below targets a throwaway fixture from
`tests/hermetic.py`, never REPO_ROOT. Tests that need live repository content read it and
never run a writing engine over it. See `[bug--tests-mutate-working-tree]` and the
meta-test in `tests/test_zz_hermetic_suite.py`.
"""

import os
import sys
import glob
import re
import unittest
import subprocess
import tempfile
import shutil
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from alongkit import proc, typography
import hermetic


def run_engine(cmd, **kwargs):
    """Capture a child process with the encoding conventions fixed in one place.

    Named `run_engine` rather than `run`: `alongkit.sanitizer.run` now owns that name
    in the shared package, and `test_no_engine_redefines_a_shared_helper` fails when a
    module outside the package shadows one of its helpers.

    `subprocess.run(..., text=True)` without `encoding=` decodes with the host locale.
    On a cp1251 or cp936 Windows install a single non-ASCII byte raised
    UnicodeDecodeError inside the reader thread, `run` returned `stdout=None`, and the
    assertion below failed with a confusing `TypeError: argument of type 'NoneType'`
    instead of the real cause. See [bug--subprocess-encoding-breaks-on-non-utf8-locale].
    """
    return proc.run_capture(cmd, **kwargs)

class TestAlongSkillsAndScripts(unittest.TestCase):

    def test_00_zero_byte_files_forbidden(self):
        """Verify zero 0-byte (empty) files across repository source, config, and skills."""
        patterns = ['**/*.md', '**/*.py', '**/*.sh', '**/*.ps1', '**/*.json', '**/*.yaml', '**/*.yml']
        zero_byte_files = []

        for pat in patterns:
            for filepath in glob.glob(os.path.join(REPO_ROOT, pat), recursive=True):
                if any(x in filepath for x in [".git", "__pycache__", "node_modules", "dist", ".vite"]):
                    continue
                if os.path.basename(filepath) == ".gitkeep":
                    continue
                size = os.path.getsize(filepath)
                if size == 0:
                    rel = os.path.relpath(filepath, REPO_ROOT)
                    zero_byte_files.append(f"{rel} (0 bytes)")

        self.assertEqual(len(zero_byte_files), 0, f"Found empty 0-byte files in repository:\n" + "\n".join(zero_byte_files))

    def test_01_all_python_files_compile(self):
        """Verify that every .py file in scripts/ and skills/ compiles and has non-trivial size."""
        py_files = (
            glob.glob(os.path.join(REPO_ROOT, "scripts", "**", "*.py"), recursive=True) +
            glob.glob(os.path.join(REPO_ROOT, "skills", "**", "*.py"), recursive=True) +
            glob.glob(os.path.join(REPO_ROOT, ".along", "scripts", "**", "*.py"), recursive=True) +
            glob.glob(os.path.join(REPO_ROOT, "tests", "**", "*.py"), recursive=True)
        )
        self.assertGreater(len(py_files), 5, "Should find at least 5 Python scripts in repo")

        for py_path in py_files:
            rel = os.path.relpath(py_path, REPO_ROOT)
            size = os.path.getsize(py_path)
            self.assertGreater(size, 40, f"Python file {rel} is unexpectedly small ({size} bytes)")
            with open(py_path, "r", encoding="utf-8") as f:
                code = f.read()
            try:
                compile(code, py_path, "exec")
            except Exception as e:
                self.fail(f"Syntax/compilation error in {rel}: {e}")

    def test_02_no_markdown_in_python_scripts(self):
        """Guard against accidental overwrite of Python scripts with README/Markdown text."""
        py_files = (
            glob.glob(os.path.join(REPO_ROOT, "scripts", "**", "*.py"), recursive=True) +
            glob.glob(os.path.join(REPO_ROOT, "skills", "**", "*.py"), recursive=True)
        )
        forbidden_starters = ["# Along (v", "# ALONG-PROTOCOL v", "AI agents start every session blind"]
        
        for py_path in py_files:
            rel = os.path.relpath(py_path, REPO_ROOT)
            with open(py_path, "r", encoding="utf-8") as f:
                first_lines = [f.readline() for _ in range(15)]
            joined = "".join(first_lines)
            for marker in forbidden_starters:
                self.assertNotIn(marker, joined, f"Corrupted Python file detected in {rel}: contains Markdown text '{marker}'")

    def test_03_skill_manifests_validity(self):
        """Verify that every skills/along-* directory contains a valid SKILL.md with frontmatter."""
        skill_dirs = glob.glob(os.path.join(REPO_ROOT, "skills", "along-*"))
        self.assertGreaterEqual(len(skill_dirs), 10, "Should have at least 10 along-* skills")

        for sdir in skill_dirs:
            sname = os.path.basename(sdir)
            skill_md = os.path.join(sdir, "SKILL.md")
            self.assertTrue(os.path.exists(skill_md), f"Missing SKILL.md in {sname}")

            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertTrue(content.startswith("---"), f"{sname}/SKILL.md must start with YAML front-matter '---'")
            self.assertIn(f"name: {sname}", content, f"{sname}/SKILL.md front-matter must specify 'name: {sname}'")
            self.assertIn("description:", content, f"{sname}/SKILL.md front-matter must specify 'description:'")

    END_MARKER = "<!-- END ALONG-PROTOCOL -->"

    def test_03b_managed_block_matches_its_source(self):
        """
        The AGENTS.md managed block must equal skills/along-init/protocol.md exactly.

        `protocol.md` is the source; the block in `AGENTS.md` is a projection that
        `along-init` and `along-update` regenerate from it. Without this test the two
        drift silently: the link-rewriting engine had replaced `.agents/KB/` with
        `.along/KB/` inside ordinary prose in the projection only, producing a sentence
        that named the same directory twice and no longer mentioned the legacy one. That
        is the "unanchored regex over whole files" mechanism from
        `[debt--protocol-quality-audit-remediation]`, caught here in the projection it
        damaged.
        """
        with open(os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md"),
                  "r", encoding="utf-8") as f:
            source = f.read().replace("\r\n", "\n").strip()
        with open(os.path.join(REPO_ROOT, "AGENTS.md"), "r", encoding="utf-8") as f:
            agents = f.read().replace("\r\n", "\n")

        self.assertIn(self.END_MARKER, agents,
                      "AGENTS.md must delimit the managed block with an END marker")
        block = agents[: agents.index(self.END_MARKER) + len(self.END_MARKER)].strip()

        if block != source:
            import difflib

            diff = "\n".join(list(difflib.unified_diff(
                source.splitlines(), block.splitlines(),
                "skills/along-init/protocol.md", "AGENTS.md managed block",
                lineterm="", n=1))[:40])
            self.fail("the managed block has drifted from its source. Regenerate it with "
                      f"/along-init rather than editing AGENTS.md by hand:\n{diff}")

    def test_03c_protocol_pins_no_stale_version_examples(self):
        """
        Illustrative version numbers in the protocol text must not name a release.

        `protocol_version: "2.2.4"` sat in the front-matter schema and in the issue field
        list while the protocol was at 2.2.9. Nothing kept them in step:
        `along_version_bump.py` rewrites `ALONG-PROTOCOL vX.Y.Z` and
        `CURRENT_PROTOCOL_VERSION`, not prose examples. Naming no version is the fix.
        """
        for name in ("AGENTS.md", os.path.join("skills", "along-init", "protocol.md")):
            path = os.path.join(REPO_ROOT, name)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            body = text.split(self.END_MARKER)[0]
            # The only version the protocol text may name is the one in its own title,
            # written unquoted as `# ALONG-PROTOCOL vX.Y.Z` and kept in step by
            # along_version_bump.py. Any QUOTED version literal is an illustrative
            # example that nothing updates, so it is drift waiting to happen.
            quoted = re.findall(r'"(\d+\.\d+\.\d+)"', body)
            self.assertEqual(
                quoted, [],
                f"{name} quotes version literal(s) {quoted} in the protocol text. "
                "Describe the field instead of naming a release: nothing keeps prose "
                "examples in step with the version.")

    def test_04_protocol_version_consistency(self):
        """Verify that protocol version is identical across protocol.md, AGENTS.md, README.md, and scripts."""
        proto_file = os.path.join(REPO_ROOT, "skills", "along-init", "protocol.md")
        with open(proto_file, "r", encoding="utf-8") as f:
            proto_text = f.read()
        
        m = re.search(r'# ALONG-PROTOCOL v(\d+\.\d+\.\d+)', proto_text)
        self.assertIsNotNone(m, "protocol.md must declare '# ALONG-PROTOCOL vX.Y.Z'")
        version = m.group(1)

        # Check AGENTS.md
        agents_md = os.path.join(REPO_ROOT, "AGENTS.md")
        with open(agents_md, "r", encoding="utf-8") as f:
            self.assertIn(f"# ALONG-PROTOCOL v{version}", f.read(), "AGENTS.md must match protocol.md version")

        # Check README.md
        readme_md = os.path.join(REPO_ROOT, "README.md")
        with open(readme_md, "r", encoding="utf-8") as f:
            readme_text = f.read()
            self.assertIn(f"# Along (v{version})", readme_text, "README.md header must match protocol version")
            self.assertIn(f"ALONG-PROTOCOL v{version}", readme_text, "README.md text must match protocol version")

        # Check the single protocol version constant. It used to be declared
        # independently in four engines; three were kept in step by regex rewrites and
        # the fourth (along_feedback.py) had drifted to 2.1.6.
        version_module = os.path.join(REPO_ROOT, "scripts", "alongkit", "version.py")
        with open(version_module, "r", encoding="utf-8") as f:
            self.assertIn(f'CURRENT_PROTOCOL_VERSION = "{version}"', f.read(),
                          f"alongkit/version.py must match {version}")

        # No engine may declare its own copy.
        offenders = []
        for name in sorted(os.listdir(os.path.join(REPO_ROOT, "scripts"))):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(REPO_ROOT, "scripts", name), "r", encoding="utf-8") as f:
                if re.search(r'^CURRENT_(PROTOCOL_)?VERSION\s*=\s*"', f.read(), re.MULTILINE):
                    offenders.append(name)
        self.assertEqual(offenders, [],
                         f"engines must import the version, not declare it: {offenders}")

    def test_05_clean_typography(self):
        """Verify zero non-ASCII typographic characters across repository text files."""
        # The table lives in alongkit.typography, shared with the sanitizer. Two copies
        # meant a character could be banned by this gate and unknown to the tool that
        # is supposed to fix it.
        forbidden_chars = {char: typography.name_of(char)
                           for char in typography.REPLACEMENTS}
        
        patterns = ['**/*.md', '**/*.py', '**/*.sh', '**/*.ps1', '**/*.json', '**/*.yaml', '**/*.yml']
        violations = []

        for pat in patterns:
            for filepath in glob.glob(os.path.join(REPO_ROOT, pat), recursive=True):
                # Skip .git, caches, tests, node_modules, dist, and typography sanitizer itself
                if any(x in filepath for x in [".git", "__pycache__", "scratch", "tests", "node_modules", "dist", ".vite", "sanitize_typography.py"]):
                    continue
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue

                for ch, desc in forbidden_chars.items():
                    if ch in content:
                        rel = os.path.relpath(filepath, REPO_ROOT)
                        violations.append(f"{rel}: contains {desc} (U+{ord(ch):04X})")

        self.assertEqual(len(violations), 0, f"Typography violations found:\n" + "\n".join(violations[:15]))

    LEGACY_AGENTS_MD = (
        "<!-- BEGIN ACTDIM-AGENTS-PROTOCOL root -->\n"
        "# ACTDIM-AGENTS-PROTOCOL v1.5.0\n\n"
        "Entities live in `.agents/ISSUES/`. Run /init-agents then /update-agents.\n"
        "Open the board with /repo-dashboard or /dashboard. Sync with /sync-kb.\n"
        "<!-- END ACTDIM-AGENTS-PROTOCOL -->\n"
    )

    CURRENT_AGENTS_MD = (
        "<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->\n"
        "# ALONG-PROTOCOL v2.2.9\n\n"
        "Direct linking into internal service folders (`.along/KB/`, `.agents/KB/`) is forbidden.\n"
        "<!-- END ALONG-PROTOCOL -->\n\n"
        "## Project specifics\n\n"
        "- Frontend lives in `packages/dashboard-ui/` and is served by /along-dash.\n"
    )

    def _migrate_temp_repo(self, agents_md):
        """Run the migration over a throwaway repository and return the resulting AGENTS.md."""
        mig_script = os.path.join(REPO_ROOT, "scripts", "migrate_protocol.py")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, ".along", "ISSUES"))
            target = os.path.join(tmp, "AGENTS.md")
            with open(target, "w", encoding="utf-8", newline="") as f:
                f.write(agents_md)
            # `--apply` is explicit because the engine dry-runs for any caller that is
            # not a human at a terminal, which is what stopped installs and test runs
            # from migrating repositories nobody pointed them at
            # (`[bug--migration-deletes-destination-without-backup]`).
            run_engine([sys.executable, mig_script, tmp, "--apply"])
            with open(target, "r", encoding="utf-8") as f:
                return f.read()

    def test_07b_migration_renames_a_legacy_agents_md(self):
        """A pre-v2.0.0 AGENTS.md must be migrated to the Along names."""
        after = self._migrate_temp_repo(self.LEGACY_AGENTS_MD)
        self.assertNotIn("ACTDIM-AGENTS-PROTOCOL", after)
        self.assertNotIn(".agents/ISSUES/", after)
        self.assertIn("/along-init", after)
        self.assertNotIn("/init-agents", after)
        self.assertNotIn("/dashboard", after, "the legacy /dashboard command must be renamed")

    def test_07c_migration_leaves_a_current_agents_md_alone(self):
        """
        The migration must not rewrite prose in an already-current AGENTS.md.

        Both substitutions it applies are substring replacements, and both damaged this
        repository: `.agents/` -> `.along/` rewrote a deliberate mention of the legacy
        directory inside the managed protocol block, and `/dashboard` -> `/along-dash`
        turned the real path `packages/dashboard-ui/` into `packages/along-dash-ui/`,
        which does not exist. The renames now apply only to a file that still carries a
        legacy marker.
        """
        after = self._migrate_temp_repo(self.CURRENT_AGENTS_MD)
        self.assertIn(".agents/KB/", after,
                      "a deliberate mention of the legacy directory must survive")
        self.assertIn("packages/dashboard-ui/", after,
                      "a real path containing /dashboard must survive")
        self.assertNotIn("along-dash-ui", after)

    def _run_dash(self, target, *extra):
        """Run along_dash.py against `target`, falling back to uv for the dash extra.

        Returns the Result, or skips the test when neither the dashboard dependencies
        nor `uv` are available.
        """
        dash_script = os.path.join(REPO_ROOT, "scripts", "along_dash.py")
        self.assertTrue(os.path.exists(dash_script), "scripts/along_dash.py must exist")

        res = run_engine([sys.executable, dash_script, target] + list(extra))
        if res.returncode != 0 and "No module named 'fastapi'" in res.stderr:
            # Fallback to uv when the dashboard stack is managed there. `httpx2` was a
            # typo for `httpx`, so this path had never worked, and `uv` was invoked
            # unconditionally, raising FileNotFoundError instead of skipping.
            if not shutil.which("uv"):
                self.skipTest("dashboard dependencies are absent and uv is not installed")
            res = run_engine(["uv", "run",
                       "--with", "fastapi", "--with", "uvicorn", "--with", "httpx",
                       "--with", "ruamel.yaml", "--with", "rich",
                       dash_script, target] + list(extra))
        return res

    def test_06_along_dash_cli_execution(self):
        """Verify that along_dash.py renders the CLI summary and exports HTML on request.

        The old version pointed the engine at REPO_ROOT and then asserted that
        `.along/DASHBOARD.md` and `.along/dashboard.html` existed there. Both assertions
        were vacuous: `--cli` writes nothing, so they only proved that two committed
        artifacts were still checked in. The export path is what writes, so that is what
        is tested, into a fixture.
        """
        with hermetic.repo_fixture(prefix="along-dash-") as fixture:
            res = self._run_dash(fixture, "--cli")
            self.assertEqual(res.returncode, 0, f"along_dash.py --cli failed:\n{res.stderr}")
            self.assertIn("Along Executive Dashboard", res.stdout)
            self.assertIn("Project Metrics Summary", res.stdout)

            exported = self._run_dash(fixture, "--export")
            self.assertEqual(exported.returncode, 0,
                             f"along_dash.py --export failed:\n{exported.stderr}")
            html = os.path.join(fixture, ".along", "dashboard.html")
            self.assertTrue(os.path.exists(html),
                            f"--export must write {html}; stdout:\n{exported.stdout}")
            self.assertGreater(os.path.getsize(html), 0, "exported dashboard must not be empty")

    def test_07_migrate_protocol_execution(self):
        """Verify that migrate_protocol.py executes cleanly over an already-current repository.

        This ran against REPO_ROOT, which is how the suite came to rewrite project
        memory: the engine normalizes front-matter, sanitizes typography, and rewrites
        Markdown links across the whole tree, with no --dry-run to hold it back
        (`[bug--migration-deletes-destination-without-backup]`).
        """
        mig_script = os.path.join(REPO_ROOT, "scripts", "migrate_protocol.py")
        self.assertTrue(os.path.exists(mig_script), "scripts/migrate_protocol.py must exist")

        with hermetic.repo_fixture(prefix="along-migrate-") as fixture:
            res = run_engine([sys.executable, mig_script, fixture, "--apply"])
            self.assertEqual(res.returncode, 0, f"migrate_protocol.py failed:\n{res.stderr}")
            self.assertIn("migrations & validations completed successfully", res.stdout)
            self.assertNotIn("[ERROR]", res.stdout,
                             "a current repository must migrate without graph errors")

            # The fixture is already current, so the engine must leave its entity alone.
            issue = os.path.join(fixture, ".along", "ISSUES", "task--fixture-sample-task.md")
            with open(issue, "r", encoding="utf-8") as f:
                self.assertIn('protocol_version: "', f.read(),
                              "migration must not unquote front-matter of a current entity")

    def test_08_along_update_check_only(self):
        """Verify that along_update.py runs in check-only mode cleanly."""
        update_script = os.path.join(REPO_ROOT, "scripts", "along_update.py")
        self.assertTrue(os.path.exists(update_script), "scripts/along_update.py must exist")

        with hermetic.repo_fixture(prefix="along-update-check-") as fixture:
            res = run_engine([sys.executable, update_script, fixture, "--check-only", "--local-only"])
            self.assertEqual(res.returncode, 0,
                             f"along_update.py --check-only failed:\n{res.stderr}")
            self.assertIn("Check-Only Mode", res.stdout)

    #: What an installer must put on disk, with the probe that proves each side does it.
    #: The previous test compared skill folder NAMES only, which is why install.sh could
    #: ship without installing `rules/` at all and nothing noticed
    #: (`[bug--installer-parity-and-destructive-rules-overwrite]`). Artifacts, not names.
    INSTALLER_ARTIFACTS = (
        ("enumerate the skill folders in skills/ dynamically",
         r"Get-ChildItem -Directory \$src", r'for d in "\$src"/\*/'),
        ("purge legacy skill folders",
         r"Purge-LegacySkillFolders", r"purge_legacy_skills"),
        ("install the rule packs from rules/",
         r"Join-Path \$PSScriptRoot 'rules'", r"\$SCRIPT_DIR/rules"),
        ("install the engines into ~/.along/bin",
         r"Join-Path \$alongHome 'bin'", r"\$along_home/bin"),
        ("strip interpreter-specific __pycache__ from the installed engines",
         r"__pycache__", r"__pycache__"),
        ("seed the default configuration from config/along-config.example.json",
         r"along-config\.example\.json", r"along-config\.example\.json"),
        ("generate the flat OpenCode commands",
         r"Join-Path \$OpencodeHome 'commands'", r"\$OPENCODE_HOME/commands"),
        ("place protocol.md in the OpenCode helper directory",
         r"along-init.protocol\.md", r"along-init/protocol\.md"),
        ("remove the un-namespaced OpenCode command aliases",
         r"shortAliases", r"SHORT_ALIASES"),
        ("register the code-review-graph MCP server",
         r"configure_mcp\.py", r"configure_mcp\.py"),
        ("record what was installed in the install manifest",
         r"install_manifest\.py", r"install_manifest\.py"),
        ("offer an uninstall that reads the manifest",
         r"\$Uninstall", r"UNINSTALL"),
        ("migrate the current repository at the end",
         r"migrate_protocol\.py", r"migrate_protocol\.py"),
    )

    #: Tool homes both installers must be able to target.
    INSTALLER_TARGETS = ("claude", "codex", "opencode", "antigravity")

    def _installer_sources(self):
        sources = {}
        for name in ("install.ps1", "install.sh"):
            with open(os.path.join(REPO_ROOT, name), "r", encoding="utf-8") as f:
                sources[name] = f.read()
        return sources

    def test_09_installer_artifact_parity(self):
        """install.ps1 and install.sh must install the same set of artifacts."""
        sources = self._installer_sources()
        missing = []
        for label, ps1_probe, sh_probe in self.INSTALLER_ARTIFACTS:
            for name, probe in (("install.ps1", ps1_probe), ("install.sh", sh_probe)):
                if not re.search(probe, sources[name]):
                    missing.append(f"{name} does not appear to {label} (probe: {probe})")
        self.assertEqual(
            missing, [],
            "the two installers must stay at parity; one of them is missing an artifact:\n"
            + "\n".join(missing))

        for name, text in sources.items():
            for target in self.INSTALLER_TARGETS:
                self.assertIn(target, text, f"{name} must support the {target} target")

    def test_09b_installer_legacy_purge_lists_are_identical(self):
        """
        Both installers delete the same obsolete skills, or one leaves ghosts behind.

        A name dropped from one list only means the corresponding platform keeps serving a
        renamed skill from a previous protocol version, which then shadows the current one.
        """
        sources = self._installer_sources()
        ps1_block = re.search(r"\$LegacySkills\s*=\s*@\((.*?)\n\)", sources["install.ps1"],
                              re.DOTALL)
        sh_block = re.search(r"LEGACY_SKILLS=\((.*?)\n\)", sources["install.sh"], re.DOTALL)
        self.assertIsNotNone(ps1_block, "install.ps1 must declare $LegacySkills = @(...)")
        self.assertIsNotNone(sh_block, "install.sh must declare LEGACY_SKILLS=(...)")

        def names(block):
            return set(re.findall(r"""["']([a-z0-9][a-z0-9-]*)["']""", block))

        ps1_names, sh_names = names(ps1_block.group(1)), names(sh_block.group(1))
        self.assertEqual(
            ps1_names, sh_names,
            "legacy purge lists diverge.\n"
            f"  only in install.ps1: {sorted(ps1_names - sh_names)}\n"
            f"  only in install.sh:  {sorted(sh_names - ps1_names)}")

        current = {os.path.basename(p)
                   for p in glob.glob(os.path.join(REPO_ROOT, "skills", "along-*"))}
        self.assertEqual(
            current & ps1_names, set(),
            "the purge list names a skill that currently ships; installing would delete it")

    def test_10_skills_pure_declarative(self):
        """Verify that skills/ directory contains only clean Markdown manifests and zero .py or __pycache__ files."""
        py_in_skills = glob.glob(os.path.join(REPO_ROOT, "skills", "**", "*.py"), recursive=True)
        pyc_in_skills = glob.glob(os.path.join(REPO_ROOT, "skills", "**", "*.pyc"), recursive=True)
        pycache_dirs = [d for d in glob.glob(os.path.join(REPO_ROOT, "skills", "**"), recursive=True) if "__pycache__" in d]

        self.assertEqual(len(py_in_skills), 0, f"skills/ directory must not contain .py files: {py_in_skills}")
        self.assertEqual(len(pyc_in_skills), 0, f"skills/ directory must not contain .pyc files: {pyc_in_skills}")
        self.assertEqual(len(pycache_dirs), 0, f"skills/ directory must not contain __pycache__: {pycache_dirs}")

    def test_11_along_exec_router_dispatch(self):
        """Verify that along_exec.py command router responds to --help and dispatches known commands."""
        exec_script = os.path.join(REPO_ROOT, "scripts", "along_exec.py")
        self.assertTrue(os.path.exists(exec_script), "scripts/along_exec.py must exist")

        res = run_engine([sys.executable, exec_script, "--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Along Command Router", res.stdout)
        self.assertIn("kb-sync", res.stdout)
        self.assertIn("dep-scan", res.stdout)

    def test_12_along_exec_entity_management(self):
        """Verify that along_exec.py manages issues and scratchpads cleanly without inline shell scripts.

        `along_exec` resolves its target from the working directory, so the fixture is
        passed as `cwd`. It used to create and purge `.along/.session/unit-test-task/`
        inside this repository.
        """
        exec_script = os.path.join(REPO_ROOT, "scripts", "along_exec.py")

        with hermetic.repo_fixture(prefix="along-exec-") as fixture:
            # 1. Scratchpad lifecycle
            init_res = run_engine([sys.executable, exec_script, "scratch", "init", "unit-test-task"],
                           cwd=fixture)
            self.assertEqual(init_res.returncode, 0, init_res.stderr)
            scratch_dir = os.path.join(fixture, ".along", ".session", "unit-test-task")
            self.assertTrue(os.path.exists(scratch_dir), "Scratchpad directory should exist")
            self.assertTrue(os.path.exists(os.path.join(scratch_dir, "plan.md")), "plan.md should exist")

            purge_res = run_engine([sys.executable, exec_script, "scratch", "purge", "unit-test-task"],
                            cwd=fixture)
            self.assertEqual(purge_res.returncode, 0, purge_res.stderr)
            self.assertFalse(os.path.exists(scratch_dir), "Scratchpad directory should be purged")

            # 2. Issue list command
            list_res = run_engine([sys.executable, exec_script, "issue", "list"], cwd=fixture)
            self.assertEqual(list_res.returncode, 0, list_res.stderr)
            self.assertIn("Active issues in", list_res.stdout)
            self.assertIn("fixture-sample-task", list_res.stdout,
                          "the fixture entity must be listed, proving the fixture was the target")

    def test_13_dashboard_graph_builder_with_kb_and_adr(self):
        """Verify that dashboard graph builder creates valid nodes and edges for KB articles and ADRs.

        Read-only against the live `.along/`, which is the only permitted use of it:
        `EntityCollector` and `build_entity_dag_graph` parse and never write. The graph is
        worth building from real project memory, because a fixture cannot drift.
        """
        from dashboard.core.collector import EntityCollector
        from dashboard.core.graph import build_entity_dag_graph

        agents_dir = os.path.join(REPO_ROOT, ".along")
        collector = EntityCollector(Path(agents_dir) if "Path" in globals() else Path(agents_dir))
        collector.collect_all()

        graph = build_entity_dag_graph(collector)
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertIsInstance(graph["nodes"], list)
        self.assertIsInstance(graph["edges"], list)

        node_types = {n.get("type") for n in graph["nodes"]}
        self.assertIn("issue", node_types)
        if collector.kb_articles:
            self.assertIn("kb", node_types)
        if collector.decisions:
            self.assertIn("decision", node_types)

        node_ids = {n["id"] for n in graph["nodes"]}
        for edge in graph["edges"]:
            self.assertIn(edge["source"], node_ids)
            self.assertIn(edge["target"], node_ids)
            self.assertIn("type", edge)
            self.assertIn("label", edge)

    def test_14_legacy_kb_and_context_migration(self):
        """Verify that legacy .along/KB/ and CONTEXT.md are automatically migrated to docs/ and .archive/."""
        temp_dir = tempfile.mkdtemp(prefix="along_mig_test_")
        try:
            # 1. Setup mock legacy v2.0 repository
            agents_md = os.path.join(temp_dir, "AGENTS.md")
            with open(agents_md, "w", encoding="utf-8") as f:
                f.write("<!-- BEGIN ALONG-PROTOCOL root -->\n# ALONG-PROTOCOL v2.0.0\n<!-- END ALONG-PROTOCOL -->\n\n## Project specifics\n")

            along_dir = os.path.join(temp_dir, ".along")
            kb_dir = os.path.join(along_dir, "KB")
            os.makedirs(kb_dir, exist_ok=True)

            # Legacy CONTEXT.md
            ctx_path = os.path.join(along_dir, "CONTEXT.md")
            with open(ctx_path, "w", encoding="utf-8") as f:
                f.write("# Temporary Session Context\nLegacy snapshot.\n")

            # Legacy 01-architecture.md
            arch_path = os.path.join(kb_dir, "01-architecture.md")
            with open(arch_path, "w", encoding="utf-8") as f:
                f.write("---\nprotocol: along\nslug: 01-architecture\ntitle: Architecture\ntype: architecture\n---\n# Architecture Spec\nCore flow.\n")

            # Legacy raw note
            raw_path = os.path.join(kb_dir, "unstructured-notes.md")
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write("# Unstructured Notes\nRaw brainstorm text.\n")

            # 2. Run migration script
            mig_script = os.path.join(REPO_ROOT, "scripts", "migrate_protocol.py")
            res = run_engine([sys.executable, mig_script, temp_dir, "--apply"])
            self.assertEqual(res.returncode, 0, f"migrate_protocol failed in test:\n{res.stderr}")

            # 3. Assertions
            docs_dir = os.path.join(temp_dir, "docs")
            archive_dir = os.path.join(temp_dir, ".archive")

            self.assertTrue(os.path.exists(docs_dir), "docs/ directory must exist after migration")
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "topic--architecture.md")), "01-architecture.md must migrate to docs/topic--architecture.md")
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "topic--unstructured-notes.md")), "raw note must synthesize to docs/topic--unstructured-notes.md")
            self.assertTrue(os.path.exists(os.path.join(docs_dir, "INDEX.md")), "docs/INDEX.md must be compiled")

            self.assertFalse(os.path.exists(archive_dir), ".archive/ directory must NOT exist after migration")
            note_content = open(os.path.join(docs_dir, "topic--unstructured-notes.md"), encoding="utf-8").read()
            self.assertIn("sources:", note_content)
            self.assertIn("unstructured-notes.md", note_content)

            self.assertFalse(os.path.exists(kb_dir), ".along/KB/ directory must be purged")
            self.assertFalse(os.path.exists(ctx_path), ".along/CONTEXT.md must be purged")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_15_along_update_multi_context_and_uninit_subprojects(self):
        """Verify that along_update.py updates all sub-contexts and detects uninitialized subprojects."""
        temp_dir = tempfile.mkdtemp(prefix="along_multi_ctx_")
        try:
            # Root context
            with open(os.path.join(temp_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write("<!-- BEGIN ALONG-PROTOCOL root -->\n# ALONG-PROTOCOL v2.0.0\n<!-- END ALONG-PROTOCOL -->\n\n## Project specifics\n")
            os.makedirs(os.path.join(temp_dir, ".along", "KB"), exist_ok=True)
            with open(os.path.join(temp_dir, ".along", "KB", "01-architecture.md"), "w", encoding="utf-8") as f:
                f.write("# Root Architecture\nRoot spec.\n")

            # Subproject context with its own .along/ and legacy KB
            sub_dir = os.path.join(temp_dir, "packages", "sub-app")
            os.makedirs(os.path.join(sub_dir, ".along", "KB"), exist_ok=True)
            with open(os.path.join(sub_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write("<!-- BEGIN ALONG-PROTOCOL ref=../../AGENTS.md -->\n<!-- END ALONG-PROTOCOL -->\n")
            with open(os.path.join(sub_dir, ".along", "KB", "02-domain-model.md"), "w", encoding="utf-8") as f:
                f.write("# Subapp Domain\nDomain spec.\n")

            # Uninitialized subproject with package.json
            uninit_dir = os.path.join(temp_dir, "packages", "uninit-lib")
            os.makedirs(uninit_dir, exist_ok=True)
            with open(os.path.join(uninit_dir, "package.json"), "w", encoding="utf-8") as f:
                f.write('{"name": "uninit-lib", "version": "1.0.0"}')

            # Run along_update.py with --all-sync
            update_script = os.path.join(REPO_ROOT, "scripts", "along_update.py")
            res = run_engine([sys.executable, update_script, temp_dir, "--all-sync", "--local-only"])
            self.assertEqual(res.returncode, 0, f"along_update failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

            # Assertions
            # Root docs
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "docs", "topic--architecture.md")), "Root 01-architecture must migrate to docs/topic--architecture.md")
            self.assertFalse(os.path.exists(os.path.join(temp_dir, ".along", "KB")), "Root .along/KB must be purged")

            # Subproject docs
            self.assertTrue(os.path.exists(os.path.join(sub_dir, "docs", "topic--domain-model.md")), "Subproject 02-domain-model must migrate to sub-app/docs/topic--domain-model.md")
            self.assertFalse(os.path.exists(os.path.join(sub_dir, ".along", "KB")), "Subproject .along/KB must be purged")

            # Uninitialized package detected
            self.assertIn("uninit-lib", res.stdout, "along_update stdout should mention uninitialized subproject")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_16_inbound_link_rewriter(self):
        """Verify that along_kb_sync rewrites legacy KB links across monorepo packages to canonical docs/ paths."""
        temp_dir = tempfile.mkdtemp(prefix="along_link_rewrite_")
        try:
            # Root context
            docs_dir = os.path.join(temp_dir, "docs")
            along_dir = os.path.join(temp_dir, ".along")
            kb_dir = os.path.join(along_dir, "KB")
            os.makedirs(kb_dir, exist_ok=True)
            os.makedirs(docs_dir, exist_ok=True)

            with open(os.path.join(temp_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write("<!-- BEGIN ALONG-PROTOCOL root -->\n# ALONG-PROTOCOL v2.2.4\n<!-- END ALONG-PROTOCOL -->\n")

            with open(os.path.join(kb_dir, "03-setup-and-workflow.md"), "w", encoding="utf-8") as f:
                f.write("# Setup & Workflows\nGuide.\n")

            with open(os.path.join(kb_dir, "01-architecture.md"), "w", encoding="utf-8") as f:
                f.write("# Architecture\nArch.\n")

            # Root README referencing legacy paths
            root_readme = os.path.join(temp_dir, "README.md")
            with open(root_readme, "w", encoding="utf-8") as f:
                f.write("# Root Project\n\nSee [Setup](./.along/KB/03-setup-and-workflow.md) and [Arch](.along/KB/01-architecture.md).\n")

            # Monorepo subproject README referencing legacy paths with relative navigation
            sub_pkg_dir = os.path.join(temp_dir, "packages", "sub-lib")
            os.makedirs(sub_pkg_dir, exist_ok=True)
            sub_readme = os.path.join(sub_pkg_dir, "README.md")
            with open(sub_readme, "w", encoding="utf-8") as f:
                f.write("# Sub Library\n\nRefer to [Setup Guide](../../.along/KB/03-setup-and-workflow.md#cli-setup) for instructions.\n")

            # Run along_kb_sync
            kb_script = os.path.join(REPO_ROOT, "scripts", "along_kb_sync.py")
            res = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res.returncode, 0, f"along_kb_sync failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

            # Verify root README was rewritten
            with open(root_readme, "r", encoding="utf-8") as f:
                root_c = f.read()
            self.assertIn("./docs/topic--setup-and-workflow.md", root_c, "Root README should have rewritten setup link")
            self.assertIn("./docs/topic--architecture.md", root_c, "Root README should have rewritten arch link")
            self.assertNotIn(".along/KB/", root_c, "Root README should not contain legacy .along/KB/ paths")

            # Verify subproject README was rewritten with proper relative path and anchor
            with open(sub_readme, "r", encoding="utf-8") as f:
                sub_c = f.read()
            self.assertIn("../../docs/topic--setup-and-workflow.md#cli-setup", sub_c, "Subproject README should rewrite relative link to ../../docs/ preserving anchor")
            self.assertNotIn(".along/KB/", sub_c, "Subproject README should not contain legacy .along/KB/ paths")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_17_link_integrity_gate(self):
        """Verify that validate_repo_link_integrity detects broken links and passes valid relative links."""
        scripts_dir = os.path.join(REPO_ROOT, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import along_kb_sync

        temp_dir = tempfile.mkdtemp(prefix="along_link_integrity_")
        try:
            os.makedirs(os.path.join(temp_dir, "docs"), exist_ok=True)
            with open(os.path.join(temp_dir, "docs", "topic--test.md"), "w", encoding="utf-8") as f:
                f.write("# Test Topic\nContent.\n")

            test_md = os.path.join(temp_dir, "README.md")
            with open(test_md, "w", encoding="utf-8") as f:
                f.write("# Overview\n\nValid: [Test](./docs/topic--test.md#anchor)\nInvalid: [Missing](./docs/topic--missing.md)\n")

            broken_links, total_checked = along_kb_sync.validate_repo_link_integrity(temp_dir)
            self.assertEqual(total_checked, 2, "Should check exactly 2 links")
            self.assertEqual(len(broken_links), 1, "Should find exactly 1 broken link")
            self.assertEqual(broken_links[0]["target"], "./docs/topic--missing.md")
            self.assertEqual(broken_links[0]["line"], 4)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_18_header_deduplication(self):
        """Verify that along_update.py collapses duplicate BEGIN/END protocol comment markers in AGENTS.md."""
        temp_dir = tempfile.mkdtemp(prefix="along_header_dedup_")
        try:
            agents_md = os.path.join(temp_dir, "AGENTS.md")
            # Create AGENTS.md with duplicate comment headers
            with open(agents_md, "w", encoding="utf-8") as f:
                f.write(
                    "<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->\n"
                    "<!-- BEGIN ALONG-PROTOCOL root (managed by along-init - do not edit by hand) -->\n"
                    "# ALONG-PROTOCOL v2.0.0\n"
                    "<!-- END ALONG-PROTOCOL -->\n"
                    "<!-- END ALONG-PROTOCOL -->\n\n"
                    "## Project specifics\n\n- Custom rule\n"
                )

            update_script = os.path.join(REPO_ROOT, "scripts", "along_update.py")
            res = run_engine([sys.executable, update_script, temp_dir, "--local-only"])
            self.assertEqual(res.returncode, 0, f"along_update failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()

            begin_count = content.count("<!-- BEGIN ALONG-PROTOCOL")
            end_count = content.count("<!-- END ALONG-PROTOCOL -->")
            self.assertEqual(begin_count, 1, f"AGENTS.md should have exactly 1 BEGIN marker, found {begin_count}")
            self.assertEqual(end_count, 1, f"AGENTS.md should have exactly 1 END marker, found {end_count}")
            self.assertIn("## Project specifics", content, "Custom project specifics must be preserved")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_19_retroactive_link_rewriting_without_kb_dir(self):
        """Verify that along_update retroactively rewrites legacy KB links even when .along/KB was already deleted."""
        temp_dir = tempfile.mkdtemp(prefix="along_retroactive_links_")
        try:
            # Context already migrated to docs/, .along/KB is gone
            docs_dir = os.path.join(temp_dir, "docs")
            os.makedirs(docs_dir, exist_ok=True)
            with open(os.path.join(docs_dir, "topic--architecture.md"), "w", encoding="utf-8") as f:
                f.write("---\nprotocol: along\nslug: topic--architecture\n---\n# Arch\n")
            with open(os.path.join(docs_dir, "topic--domain-model.md"), "w", encoding="utf-8") as f:
                f.write("---\nprotocol: along\nslug: topic--domain-model\n---\n# Domain\n")
            with open(os.path.join(docs_dir, "INDEX.md"), "w", encoding="utf-8") as f:
                f.write("# Index\n")

            with open(os.path.join(temp_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write("<!-- BEGIN ALONG-PROTOCOL root -->\n# ALONG-PROTOCOL v2.1.0\n<!-- END ALONG-PROTOCOL -->\n")

            # README with broken links from old versions
            readme_path = os.path.join(temp_dir, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Project Title\n\n"
                    "- [Architecture](.along/KB/01-architecture.md)\n"
                    "- [Domain](docs/02-domain-model.md)\n"
                    "- [Custom Section](.along/KB/05-custom-guide.md)\n"
                    "- [Catalog](.along/KB/)\n"
                )

            update_script = os.path.join(REPO_ROOT, "scripts", "along_update.py")
            res = run_engine([sys.executable, update_script, temp_dir, "--local-only"])
            self.assertEqual(res.returncode, 0, f"along_update failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

            with open(readme_path, "r", encoding="utf-8") as f:
                updated_readme = f.read()

            self.assertIn("./docs/topic--architecture.md", updated_readme)
            self.assertIn("./docs/topic--domain-model.md", updated_readme)
            self.assertIn("./docs/topic--custom-guide.md", updated_readme)
            self.assertIn("./docs/INDEX.md", updated_readme)
            self.assertNotIn(".along/KB", updated_readme)
            self.assertNotIn("01-architecture", updated_readme)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_20_candidate_scripts_resolution(self):
        """Verify that along_update resolves helper scripts in ~/.along/bin/ and scripts/."""
        scripts_dir = os.path.join(REPO_ROOT, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import along_update

        resolved_kb = along_update.locate_skill_script(REPO_ROOT, "along-kb-sync", "along_kb_sync.py")
        self.assertIsNotNone(resolved_kb, "Should resolve along_kb_sync.py in repository scripts/")
        self.assertTrue(os.path.exists(resolved_kb))

    def test_21_docs_articles_not_empty_placeholders(self):
        """Verify that knowledge base articles in docs/ are rich, substantive, and not empty placeholder stubs."""
        docs_dir = os.path.join(REPO_ROOT, "docs")
        self.assertTrue(os.path.exists(docs_dir), "docs/ directory must exist")

        topic_files = glob.glob(os.path.join(docs_dir, "topic--*.md"))
        self.assertGreaterEqual(len(topic_files), 4, "Must contain at least 4 core topic articles")

        for topic_path in topic_files:
            rel = os.path.relpath(topic_path, REPO_ROOT)
            size = os.path.getsize(topic_path)
            with open(topic_path, "r", encoding="utf-8") as f:
                lines = [line for line in f.readlines() if line.strip()]

            # Substantive content assertion (must be > 1000 bytes and >= 20 non-empty lines)
            self.assertGreater(size, 1000, f"{rel} is too small ({size} bytes). Documentation must not be an empty placeholder stub.")
            self.assertGreaterEqual(len(lines), 20, f"{rel} has only {len(lines)} lines. Expected rich documentation.")

    def test_22_sources_provenance_and_drift_detection(self):
        """Verify that along_kb_sync detects source drift and missing sources via front-matter hashes."""
        with hermetic.repo_fixture(prefix="along-drift-") as temp_dir:
            kb_script = os.path.join(REPO_ROOT, "scripts", "along_kb_sync.py")
            src_file = os.path.join(temp_dir, "README.md")
            with open(src_file, "r", encoding="utf-8") as f:
                src_content = f.read()

            import along_kb_sync
            src_hash = along_kb_sync.compute_content_hash(src_content)

            doc_path = os.path.join(temp_dir, "docs", "topic--architecture.md")
            with open(doc_path, "r", encoding="utf-8") as f:
                doc_content = f.read()

            # Inject sources into front-matter
            doc_with_sources = doc_content.replace(
                "tags: [architecture]\n",
                f"tags: [architecture]\nsources:\n  - path: README.md\n    hash: \"{src_hash}\"\n"
            )
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(doc_with_sources)

            # 1. Run sync when source is clean -> no drift
            res = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res.returncode, 0)
            self.assertNotIn("[DRIFT]", res.stdout)
            self.assertNotIn("[ORPHANED SOURCE]", res.stdout)

            # 2. Mutate source file -> verify [DRIFT] is reported
            with open(src_file, "a", encoding="utf-8") as f:
                f.write("\n## Extra Heading\nAdditional content.\n")

            res_drift = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res_drift.returncode, 0)
            self.assertIn("[DRIFT]", res_drift.stdout)
            self.assertIn("Source 'README.md' has changed", res_drift.stdout)

            # 3. Reference a non-existent source file -> verify [ORPHANED SOURCE] is reported
            doc_with_orphan = doc_with_sources.replace("path: README.md", "path: missing-spec.md")
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(doc_with_orphan)

            res_orphan = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res_orphan.returncode, 0)
            self.assertIn("[ORPHANED SOURCE]", res_orphan.stdout)
            self.assertIn("missing-spec.md", res_orphan.stdout)

    def test_23_content_reduction_intent_gate(self):
        """Verify that along_kb_sync halts with exit code 2 on content reduction unless --prune-intent is provided."""
        temp_dir = tempfile.mkdtemp(prefix="along-shrink-")
        try:
            # Initialize a git repository in temp_dir
            run_engine(["git", "init"], cwd=temp_dir)
            run_engine(["git", "config", "user.email", "test@example.com"], cwd=temp_dir)
            run_engine(["git", "config", "user.name", "Test Runner"], cwd=temp_dir)

            docs_dir = os.path.join(temp_dir, "docs")
            os.makedirs(docs_dir, exist_ok=True)
            doc_path = os.path.join(docs_dir, "topic--architecture.md")

            # Create an article with 35 lines
            initial_lines = [
                "---",
                "protocol: along",
                'protocol_version: "2.2.18"',
                "slug: architecture",
                "title: Architecture",
                "type: architecture",
                "created: 2026-09-01",
                "tags: [architecture]",
                "---",
                "",
                "# Architecture",
                "",
                "Detailed architecture content follows.",
            ] + [f"Line {i} describing system components in detail." for i in range(1, 25)]
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write("\n".join(initial_lines) + "\n")

            # Commit to git HEAD
            run_engine(["git", "add", "."], cwd=temp_dir)
            run_engine(["git", "commit", "-m", "Initial commit"], cwd=temp_dir)

            # Shrink the document drastically (from ~37 lines down to 14 lines, delta >= 10, >25%)
            shrunk_lines = [
                "---",
                "protocol: along",
                'protocol_version: "2.2.18"',
                "slug: architecture",
                "title: Architecture",
                "type: architecture",
                "created: 2026-09-01",
                "tags: [architecture]",
                "---",
                "",
                "# Architecture",
                "",
                "Only small stub left.",
            ]
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write("\n".join(shrunk_lines) + "\n")

            kb_script = os.path.join(REPO_ROOT, "scripts", "along_kb_sync.py")

            # 1. Run without --prune-intent -> MUST fail with exit code 2
            res_blocked = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res_blocked.returncode, 2)
            self.assertIn("Detected significant content reduction", res_blocked.stdout)
            self.assertIn("--prune-intent", res_blocked.stdout)

            # 2. Run with --prune-intent [REASON] -> MUST succeed with exit code 0
            res_allowed = run_engine([sys.executable, kb_script, temp_dir, "--prune-intent", "Refactoring component spec"])
            self.assertEqual(res_allowed.returncode, 0)
            self.assertIn("[PRUNE-INTENT] Acknowledged content reduction: Refactoring component spec", res_allowed.stdout)

            # 3. Run with --allow-shrink -> MUST succeed with exit code 0
            res_alias = run_engine([sys.executable, kb_script, temp_dir, "--allow-shrink"])
            self.assertEqual(res_alias.returncode, 0)
            self.assertIn("[PRUNE-INTENT] Acknowledged content reduction: Allow shrink", res_alias.stdout)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_24_smart_llms_txt_sync(self):
        """Verify that along_kb_sync preserves custom sections in llms.txt while updating documentation links."""
        with hermetic.repo_fixture(prefix="along-llmstxt-") as temp_dir:
            llms_path = os.path.join(temp_dir, "llms.txt")
            custom_content = (
                "# Custom Project Title\n\n"
                "> Custom description of the project.\n\n"
                "## Custom Section\n"
                "- Custom feature bullet\n\n"
                "## Documentation Links\n"
                "- [Legacy Doc](./docs/topic--legacy.md)\n"
                "- [External Guide](https://example.com/guide)\n\n"
                "## External Resources\n"
                "- https://actdim.com\n"
            )
            with open(llms_path, "w", encoding="utf-8") as f:
                f.write(custom_content)

            kb_script = os.path.join(REPO_ROOT, "scripts", "along_kb_sync.py")
            res = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res.returncode, 0)

            with open(llms_path, "r", encoding="utf-8") as f:
                updated_content = f.read()

            # Custom sections preserved
            self.assertIn("# Custom Project Title", updated_content)
            self.assertIn("> Custom description of the project.", updated_content)
            self.assertIn("## Custom Section", updated_content)
            self.assertIn("- Custom feature bullet", updated_content)
            self.assertIn("## External Resources", updated_content)
            self.assertIn("- https://actdim.com", updated_content)

            # External link inside Documentation Links preserved
            self.assertIn("- [External Guide](https://example.com/guide)", updated_content)

            # Documentation links synchronized with active docs
            self.assertIn("- [docs/topic--architecture.md](docs/topic--architecture.md): Architecture.", updated_content)
            self.assertNotIn("./docs/topic--legacy.md", updated_content)

    def test_25_well_known_llms_txt_and_full_txt_sync(self):
        """Verify .well-known resolution, deterministic llms-full.txt compilation, and cascading subprojects."""
        with hermetic.repo_fixture(prefix="along-wk-llms-") as temp_dir:
            # 1. Setup .well-known directory with an existing llms.txt
            wk_dir = os.path.join(temp_dir, ".well-known")
            os.makedirs(wk_dir, exist_ok=True)
            wk_llms = os.path.join(wk_dir, "llms.txt")
            with open(wk_llms, "w", encoding="utf-8") as f:
                f.write("# Well-Known Title\n\n> Well-known description.\n\n## Custom\n- value\n")

            # Also create a nested subproject with its own .along/ and docs/
            sub_dir = os.path.join(temp_dir, "src", "services", "sub-service")
            os.makedirs(os.path.join(sub_dir, ".along"), exist_ok=True)
            os.makedirs(os.path.join(sub_dir, "docs"), exist_ok=True)
            with open(os.path.join(sub_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write("# Sub Service\n\n> Microservice for data processing.\n")
            with open(os.path.join(sub_dir, "docs", "topic--sub.md"), "w", encoding="utf-8") as f:
                f.write("---\nprotocol: along\nprotocol_version: \"2.2.18\"\nslug: sub\ntitle: Sub Service Docs\ntype: topic\n---\n# Sub Service Docs\nDetailed topic body.\n")

            kb_script = os.path.join(REPO_ROOT, "scripts", "along_kb_sync.py")
            res = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res.returncode, 0, f"along_kb_sync failed:\n{res.stderr}\n{res.stdout}")

            # Verify root .well-known/llms.txt was updated
            with open(wk_llms, "r", encoding="utf-8") as f:
                wk_updated = f.read()
            self.assertIn("# Well-Known Title", wk_updated)
            self.assertIn("## Custom", wk_updated)
            self.assertIn("- [docs/topic--architecture.md](docs/topic--architecture.md): Architecture.", wk_updated)

            # Verify root .well-known/llms-full.txt was deterministically compiled
            wk_full = os.path.join(wk_dir, "llms-full.txt")
            self.assertTrue(os.path.isfile(wk_full), ".well-known/llms-full.txt must be compiled")
            with open(wk_full, "r", encoding="utf-8") as f:
                full_body = f.read()
            self.assertIn("Full Documentation Context", full_body)
            self.assertIn("## Document: docs/topic--architecture.md (Architecture)", full_body)
            self.assertIn("The fixture Knowledge Base article.", full_body)

            # Verify cascading subproject sync created llms.txt and llms-full.txt for sub-service
            sub_llms = os.path.join(sub_dir, "llms.txt")
            sub_full = os.path.join(sub_dir, "llms-full.txt")
            self.assertTrue(os.path.isfile(sub_llms), "Subproject llms.txt must be synchronized")
            self.assertTrue(os.path.isfile(sub_full), "Subproject llms-full.txt must be compiled")
            with open(sub_llms, "r", encoding="utf-8") as f:
                sub_llms_content = f.read()
            self.assertIn("Sub Service", sub_llms_content)
            self.assertIn("docs/topic--sub.md", sub_llms_content)

            # Now test dual-target synchronization: create root llms.txt alongside .well-known/llms.txt
            root_llms = os.path.join(temp_dir, "llms.txt")
            with open(root_llms, "w", encoding="utf-8") as f:
                f.write("# Root Copy\n\n> Stale copy.\n")

            res2 = run_engine([sys.executable, kb_script, temp_dir])
            self.assertEqual(res2.returncode, 0)

            # Both root and .well-known targets must be updated to prevent drift
            with open(root_llms, "r", encoding="utf-8") as f:
                root_updated = f.read()
            with open(wk_llms, "r", encoding="utf-8") as f:
                wk_updated2 = f.read()
            self.assertIn("- [docs/topic--architecture.md](docs/topic--architecture.md): Architecture.", root_updated)
            self.assertIn("- [docs/topic--architecture.md](docs/topic--architecture.md): Architecture.", wk_updated2)

    def test_26_canonical_context_and_manifest_discovery(self):
        """Verify alongkit.repo downward discovery functions and llm target resolution."""
        from alongkit import repo

        temp_dir = tempfile.mkdtemp(prefix="along-repo-discovery-")
        try:
            # 1. Root context
            os.makedirs(os.path.join(temp_dir, ".along"), exist_ok=True)

            # 2. Subproject 1: .NET-style nested folder with AGENTS.md and .csproj
            net_proj = os.path.join(temp_dir, "src", "Services", "Billing")
            os.makedirs(net_proj, exist_ok=True)
            with open(os.path.join(net_proj, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write("# Sub Agents\n")
            with open(os.path.join(net_proj, "Billing.csproj"), "w", encoding="utf-8") as f:
                f.write("<Project />")

            # 3. Subproject 2: Rust package with Cargo.toml (uninitialized context)
            rust_proj = os.path.join(temp_dir, "crates", "parser")
            os.makedirs(rust_proj, exist_ok=True)
            with open(os.path.join(rust_proj, "Cargo.toml"), "w", encoding="utf-8") as f:
                f.write("[package]\nname = \"parser\"\n")

            # 4. Ignored directories: node_modules and .git
            ignored_proj = os.path.join(temp_dir, "node_modules", "some-dep")
            os.makedirs(ignored_proj, exist_ok=True)
            with open(os.path.join(ignored_proj, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write("# Ignored\n")

            # Test find_agent_contexts
            contexts = repo.find_agent_contexts(temp_dir)
            abs_root = os.path.abspath(temp_dir)
            abs_net = os.path.abspath(net_proj)
            abs_ignored = os.path.abspath(ignored_proj)

            self.assertIn(abs_root, contexts)
            self.assertIn(abs_net, contexts)
            self.assertNotIn(abs_ignored, contexts, "Ignored directories must not be discovered as contexts")

            # Test find_manifest_projects
            manifest_projs = repo.find_manifest_projects(temp_dir)
            abs_rust = os.path.abspath(rust_proj)
            self.assertIn(abs_net, manifest_projs)
            self.assertIn(abs_rust, manifest_projs)
            self.assertNotIn(abs_ignored, manifest_projs)

            # Test resolve_llm_targets
            # Case 1: Neither exists and no .well-known dir -> default root
            targets1 = repo.resolve_llm_targets(rust_proj, "llms.txt")
            self.assertEqual(targets1, [os.path.join(abs_rust, "llms.txt")])

            # Case 2: .well-known dir exists -> default .well-known
            wk_dir = os.path.join(rust_proj, ".well-known")
            os.makedirs(wk_dir, exist_ok=True)
            targets2 = repo.resolve_llm_targets(rust_proj, "llms.txt")
            self.assertEqual(targets2, [os.path.join(wk_dir, "llms.txt")])

            # Case 3: File exists in .well-known -> returns .well-known
            with open(os.path.join(wk_dir, "llms.txt"), "w", encoding="utf-8") as f:
                f.write("content")
            targets3 = repo.resolve_llm_targets(rust_proj, "llms.txt")
            self.assertEqual(targets3, [os.path.join(wk_dir, "llms.txt")])

            # Case 4: Both exist -> returns both
            with open(os.path.join(rust_proj, "llms.txt"), "w", encoding="utf-8") as f:
                f.write("root content")
            targets4 = repo.resolve_llm_targets(rust_proj, "llms.txt")
            self.assertEqual(len(targets4), 2)
            self.assertIn(os.path.join(wk_dir, "llms.txt"), targets4)
            self.assertIn(os.path.join(rust_proj, "llms.txt"), targets4)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)




