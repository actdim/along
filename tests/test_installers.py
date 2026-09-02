#!/usr/bin/env python3
"""
tests/test_installers.py - the installers install the same thing, destroy nothing, and
say only what is true.

The four guarantees, each tied to a way the previous installers were wrong
(`[bug--installer-parity-and-destructive-rules-overwrite]`):

1. **Parity by artifact, not by name.** Both installers are run against a throwaway
   checkout and their output on disk is compared to `alongkit.install.planned_files`,
   the single description of the installed layout. The previous parity test compared
   skill folder NAMES, which is why `install.sh` shipped without installing `rules/`
   at all and no test noticed for months.

2. **Nothing a user wrote is deleted.** `install.ps1` opened with
   `Remove-Item -Recurse -Force ~/.claude/rules` on every run, and the release engine
   ran the installer unasked. A user rule file is planted before each install and must
   still be there afterwards, and after an uninstall.

3. **A link install stays a link install.** The symlink fallback creates a Windows
   junction, which `os.path.islink` does not report. Recording the files behind it
   would make an uninstall delete the source checkout, so the test uninstalls a linked
   install and counts the checkout's files afterwards.

4. **No claimed success that never happened.** MCP registration is written only where
   the contract is verified, an unparseable configuration file is left alone rather
   than replaced, and everything else is reported as skipped.

Hermetic rule: every installer invocation targets `hermetic.make_installer_checkout()`
and homes under `tempfile`, never `REPO_ROOT` and never the developer's real
`~/.claude`. See `tests/test_zz_hermetic_suite.py`.
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
for _path in (REPO_ROOT, SCRIPTS_DIR, os.path.dirname(os.path.abspath(__file__))):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from alongkit import install, proc
import hermetic


class InstallerCase(unittest.TestCase):
    """Shared fixtures: one throwaway checkout, one throwaway user home per test."""

    @classmethod
    def setUpClass(cls):
        cls.checkout = hermetic.make_installer_checkout()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.checkout, ignore_errors=True)

    def make_home(self):
        """A user home with a space in its path, removed when the test ends."""
        home = tempfile.mkdtemp(prefix="along home ")
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        return home

    def homes_for(self, home):
        return install.Homes.defaults(
            home,
            along=os.path.join(home, ".along"),
            claude=os.path.join(home, ".claude"),
            codex=os.path.join(home, ".codex"),
            opencode=os.path.join(home, ".config", "opencode"),
            antigravity=os.path.join(home, ".gemini", "config"))

    def home_arguments(self, home, style):
        """The home overrides in the argument style of one installer."""
        pairs = [("along-home", os.path.join(home, ".along")),
                 ("claude-home", os.path.join(home, ".claude")),
                 ("codex-home", os.path.join(home, ".codex")),
                 ("opencode-home", os.path.join(home, ".config", "opencode")),
                 ("antigravity-home", os.path.join(home, ".gemini", "config"))]
        if style == "sh":
            return [f"--{name}={value}" for name, value in pairs]
        flags = {"along-home": "-AlongHome", "claude-home": "-ClaudeHome",
                 "codex-home": "-CodexHome", "opencode-home": "-OpencodeHome",
                 "antigravity-home": "-AntigravityHome"}
        arguments = []
        for name, value in pairs:
            arguments.extend([flags[name], value])
        return arguments

    def plant_user_rule(self, home):
        """A file the user wrote into a provider home, which an install must not touch."""
        path = os.path.join(home, ".along", "rules", "my-own-rule.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write("# My own rule\n\nWritten by the user, not by Along.\n")
        return path

    def installed_under(self, roots):
        """Every file (or link) actually on disk under the install's own roots."""
        found = set()
        for root in roots:
            if not os.path.isdir(root):
                continue
            for current, dirs, files in os.walk(root):
                if install.is_link(current):
                    found.add(install.path_key(current))
                    dirs[:] = []
                    continue
                keep = []
                for name in sorted(dirs):
                    path = os.path.join(current, name)
                    if install.is_link(path):
                        found.add(install.path_key(path))
                    else:
                        keep.append(name)
                dirs[:] = keep
                for name in files:
                    found.add(install.path_key(os.path.join(current, name)))
        return found

    def read_manifest(self, home):
        path = os.path.join(home, ".along", install.MANIFEST_NAME)
        self.assertTrue(os.path.isfile(path), f"no install manifest at {path}")
        with io.open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def bash(self):
        found = shutil.which("bash")
        if not found:
            self.skipTest("bash is unavailable")
        if sys.platform == "win32":
            # On Windows, bash.exe is usually WSL, which might be installed
            # but lack a default distro or have a non-standard one like docker-desktop.
            probe = proc.run_capture([found, "-c", "echo 1"])
            if not probe.ok:
                self.skipTest(f"bash is present but broken or WSL distro is unsupported: {probe.stderr.strip()}")
        return found

    def powershell(self):
        if sys.platform != "win32":
            self.skipTest("install.ps1 is only exercised on Windows")
        found = shutil.which("powershell") or shutil.which("pwsh")
        if not found:
            self.skipTest("powershell is unavailable")
        return found

    def run_sh(self, arguments):
        command = [self.bash(), os.path.join(self.checkout, "install.sh")] + arguments
        result = proc.run_capture(command, cwd=self.checkout, timeout=600)
        self.assertTrue(result.ok,
                        f"install.sh failed ({result.returncode})\n"
                        f"{result.stdout}\n{result.stderr}")
        return result

    def run_ps1(self, arguments):
        command = [self.powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-File", os.path.join(self.checkout, "install.ps1")] + arguments
        result = proc.run_capture(command, cwd=self.checkout, timeout=600)
        self.assertTrue(result.ok,
                        f"install.ps1 failed ({result.returncode})\n"
                        f"{result.stdout}\n{result.stderr}")
        return result


class TestInstalledLayoutPlan(InstallerCase):
    """`planned_files` is the specification both installers are measured against."""

    def test_rules_are_planned_for_along_home(self):
        homes = self.homes_for(self.make_home())
        plan = install.planned_files(self.checkout, homes)
        rules = os.path.join(homes.along, "rules", "INDEX.md")
        self.assertIn(rules, plan,
                      "along home must receive the rule packs")

    def test_engines_and_the_shared_package_land_in_along_bin(self):
        homes = self.homes_for(self.make_home())
        plan = install.planned_files(self.checkout, homes)
        self.assertIn(os.path.join(homes.bin, "along_exec.py"), plan)
        self.assertIn(os.path.join(homes.bin, "alongkit", "install.py"), plan)

    def test_opencode_gets_one_command_per_skill_and_the_helper_engines(self):
        homes = self.homes_for(self.make_home())
        plan = install.planned_files(self.checkout, homes, ["opencode"])
        commands = os.path.join(homes.opencode, "commands")
        for skill in install.source_skills(self.checkout):
            self.assertIn(os.path.join(commands, skill + ".md"), plan)
        helper = os.path.join(homes.opencode, "actdim-along")
        self.assertIn(os.path.join(helper, "protocol.md"), plan)
        self.assertIn(os.path.join(helper, "alongkit", "repo.py"), plan)

    def test_the_user_configuration_is_not_owned_by_the_install(self):
        """`~/.along/config.json` is seeded once and then belongs to the user."""
        homes = self.homes_for(self.make_home())
        plan = install.planned_files(self.checkout, homes)
        self.assertNotIn(os.path.join(homes.along, "config.json"), plan)


class TestInstallManifestLifecycle(InstallerCase):

    def _fake_install(self, homes, providers=install.PROVIDERS):
        """Put the planned files on disk without running a shell installer."""
        for dest, source in install.planned_files(self.checkout, homes, providers).items():
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(source, dest)

    def test_a_second_sync_reports_everything_unchanged(self):
        home = self.make_home()
        homes = self.homes_for(home)
        self._fake_install(homes)
        first = install.sync_manifest(self.checkout, homes, install.PROVIDERS, "9.9.9")
        second = install.sync_manifest(self.checkout, homes, install.PROVIDERS, "9.9.9")
        self.assertEqual(first["missing"], [])
        self.assertGreater(first["installed"], 0)
        self.assertEqual((second["added"], second["changed"]), (0, 0))
        self.assertEqual(second["unchanged"], second["installed"])

    def test_a_superseded_file_is_pruned_and_a_user_file_is_not(self):
        home = self.make_home()
        homes = self.homes_for(home)
        self._fake_install(homes)
        install.sync_manifest(self.checkout, homes, install.PROVIDERS, "9.9.9")

        user_file = self.plant_user_rule(home)
        superseded = os.path.join(homes.along, "rules", "languages", "retired.md")
        os.makedirs(os.path.dirname(superseded), exist_ok=True)
        with io.open(superseded, "w", encoding="utf-8") as handle:
            handle.write("# A rule pack Along used to ship\n")
        # Claim it in the manifest, exactly as a previous version of Along would have.
        path = install.manifest_path(homes.along)
        with io.open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["files"][install.path_key(superseded)] = "0" * 16
        with io.open(path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)

        report = install.sync_manifest(self.checkout, homes, install.PROVIDERS, "9.9.9")
        self.assertIn(install.path_key(superseded), report["removed"])
        self.assertFalse(os.path.exists(superseded))
        self.assertTrue(os.path.isfile(user_file),
                        "an install removed a file the user wrote; this is the whole bug")

    def test_pruning_is_scoped_to_the_providers_of_this_run(self):
        """Installing one provider must not uninstall another."""
        home = self.make_home()
        homes = self.homes_for(home)
        self._fake_install(homes)
        install.sync_manifest(self.checkout, homes, install.PROVIDERS, "9.9.9")
        codex_skill = os.path.join(homes.codex, "skills", "along-init", "SKILL.md")
        self.assertTrue(os.path.isfile(codex_skill))

        install.sync_manifest(self.checkout, homes, ["claude"], "9.9.9")
        self.assertTrue(os.path.isfile(codex_skill),
                        "a claude-only install pruned the codex install")
        manifest = self.read_manifest(home)
        self.assertIn(install.path_key(codex_skill), manifest["files"],
                      "the codex files must stay recorded, or uninstall would miss them")

    def test_uninstall_removes_only_recorded_files(self):
        home = self.make_home()
        homes = self.homes_for(home)
        self._fake_install(homes)
        user_file = self.plant_user_rule(home)
        install.sync_manifest(self.checkout, homes, install.PROVIDERS, "9.9.9")

        report = install.uninstall(homes.along)
        self.assertEqual(report["failed"], [])
        self.assertGreater(len(report["removed"]), 0)
        self.assertTrue(os.path.isfile(user_file))
        self.assertFalse(os.path.exists(
            os.path.join(homes.claude, "skills", "along-init", "SKILL.md")))
        self.assertFalse(os.path.isfile(install.manifest_path(homes.along)))


class TestMcpRegistrationContract(InstallerCase):

    def test_only_the_verified_target_is_written(self):
        home = self.make_home()
        homes = self.homes_for(home)
        report = {entry["provider"]: entry
                  for entry in install.configure_mcp(install.PROVIDERS, homes)}
        self.assertEqual(report["claude"]["status"], "registered")
        for provider in ("codex", "opencode", "antigravity"):
            self.assertEqual(report[provider]["status"], "skipped",
                             "an unverified provider must be reported, not written")
            self.assertFalse(os.path.exists(report[provider]["path"]),
                             "nothing may be created at an unverified path")

        with io.open(os.path.join(home, ".claude.json"), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["mcpServers"][install.MCP_SERVER_NAME],
                         install.MCP_SERVER_ENTRY)

    def test_an_existing_configuration_is_preserved_and_not_duplicated(self):
        home = self.make_home()
        homes = self.homes_for(home)
        path = os.path.join(home, ".claude.json")
        with io.open(path, "w", encoding="utf-8") as handle:
            json.dump({"numStartups": 7, "mcpServers": {"other": {"command": "x"}}},
                      handle)

        install.configure_mcp(["claude"], homes)
        with io.open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["numStartups"], 7, "unrelated settings must survive")
        self.assertIn("other", data["mcpServers"])

        again = install.configure_mcp(["claude"], homes)
        self.assertEqual(again[0]["status"], "present")

    def test_an_unparseable_configuration_is_left_alone(self):
        """The previous installer restarted from `{}` and overwrote the whole file."""
        home = self.make_home()
        homes = self.homes_for(home)
        path = os.path.join(home, ".claude.json")
        damaged = '{"mcpServers": {"other": {"command": "x"'
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(damaged)

        report = install.configure_mcp(["claude"], homes)
        self.assertEqual(report[0]["status"], "failed")
        with io.open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), damaged)

    def test_an_unverified_target_can_be_opted_into_and_is_idempotent(self):
        home = self.make_home()
        homes = self.homes_for(home)
        os.makedirs(homes.codex, exist_ok=True)
        config = os.path.join(homes.codex, "config.toml")
        with io.open(config, "w", encoding="utf-8") as handle:
            handle.write("model = \"o3\"\n")

        first = install.configure_mcp(["codex"], homes, include_unverified=True)
        self.assertEqual(first[0]["status"], "registered")
        with io.open(config, "r", encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("model = \"o3\"", body, "the existing configuration must survive")
        self.assertIn(f"[mcp_servers.{install.MCP_SERVER_NAME}]", body)

        second = install.configure_mcp(["codex"], homes, include_unverified=True)
        self.assertEqual(second[0]["status"], "present")
        with io.open(config, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), body, "a second run must change nothing")


class TestInstallerScriptsMatchThePlan(InstallerCase):
    """The end-to-end guarantee: run the real installers, compare disk to the plan."""

    def assert_matches_plan(self, home, providers, label, user_files=()):
        homes = self.homes_for(home)
        plan = install.planned_files(self.checkout, homes, providers)
        expected = {install.path_key(path) for path in plan}
        # A file the user wrote sits inside an owned root and is deliberately absent
        # from the plan: the install neither creates it nor is allowed to remove it.
        theirs = {install.path_key(path) for path in user_files}
        actual = self.installed_under(install.owned_roots(homes, providers)) - theirs
        self.assertEqual(
            sorted(expected - actual), [],
            f"{label} did not install everything the layout describes")
        self.assertEqual(
            sorted(actual - expected), [],
            f"{label} installed files the layout does not describe")
        manifest = self.read_manifest(home)
        self.assertEqual(set(manifest["files"]), expected,
                         f"{label} recorded a manifest that does not match the install")
        return expected

    def test_bash_installer_matches_the_plan_and_spares_user_files(self):
        home = self.make_home()
        user_file = self.plant_user_rule(home)
        self.run_sh(["--target=all"] + self.home_arguments(home, "sh"))
        expected = self.assert_matches_plan(home, install.PROVIDERS, "install.sh",
                                           user_files=[user_file])
        self.assertTrue(os.path.isfile(user_file),
                        "install.sh deleted a rule file the user wrote")

        self.run_sh(["--uninstall"] + self.home_arguments(home, "sh"))
        self.assertTrue(os.path.isfile(user_file), "--uninstall removed a user file")
        still_there = [path for path in expected if os.path.lexists(path)]
        self.assertEqual(still_there, [], "--uninstall left installed files behind")

    def test_powershell_installer_matches_the_same_plan(self):
        home = self.make_home()
        user_file = self.plant_user_rule(home)
        self.run_ps1(["-Target", "all"] + self.home_arguments(home, "ps1"))
        self.assert_matches_plan(home, install.PROVIDERS, "install.ps1",
                                 user_files=[user_file])
        self.assertTrue(os.path.isfile(user_file),
                        "install.ps1 deleted a rule file the user wrote; it used to "
                        "start with Remove-Item -Recurse -Force on this directory")

    def test_a_linked_install_records_links_and_uninstalls_without_touching_the_source(self):
        """REQ-5: the junction fallback, on a path with a space, and a safe uninstall."""
        home = self.make_home()
        arguments = self.home_arguments(home, "sh")
        if sys.platform == "win32":
            self.run_ps1(["-Target", "claude", "-Symlink"]
                         + self.home_arguments(home, "ps1"))
        else:
            self.run_sh(["--target=claude", "--symlink"] + arguments)

        homes = self.homes_for(home)
        linked = os.path.join(homes.claude, "skills", "along-init")
        self.assertTrue(install.is_link(linked),
                        "the skill folder should be a link, not a copy")
        manifest = self.read_manifest(home)
        self.assertEqual(manifest["files"][install.path_key(linked)], "symlink",
                         "a link must be recorded as one, or uninstall follows it")

        before = sum(len(files) for _, _, files
                     in os.walk(os.path.join(self.checkout, "skills")))
        if sys.platform == "win32":
            self.run_ps1(["-Uninstall"] + self.home_arguments(home, "ps1"))
        else:
            self.run_sh(["--uninstall"] + arguments)
        after = sum(len(files) for _, _, files
                    in os.walk(os.path.join(self.checkout, "skills")))
        self.assertEqual(before, after,
                         "uninstalling a linked install deleted the source checkout")
        self.assertFalse(os.path.lexists(linked))


class TestInstallerSourceHygiene(unittest.TestCase):
    """Two rules the installers themselves have to obey, checked in their source."""

    def sources(self):
        """Both installers as executable lines: comments are documentation, not code.

        The comments deliberately quote the patterns being banned, to say what the
        code used to do and why it no longer does it. A gate that reads them as
        violations would force the explanation out of the file.
        """
        found = {}
        for name in ("install.ps1", "install.sh"):
            with io.open(os.path.join(REPO_ROOT, name), "r", encoding="utf-8") as handle:
                lines = [line for line in handle.read().splitlines()
                         if not line.lstrip().startswith("#")]
            found[name] = lines
        return found

    def test_no_installer_runs_an_inline_python_program(self):
        """AGENTS.md forbids it, and both installers used to carry a 24-line one."""
        offenders = []
        for name, lines in self.sources().items():
            for number, line in enumerate(lines, start=1):
                if re.search(r"python3?(?:\.exe)?[\"']?\s+-c\b", line):
                    offenders.append(f"{name} (line {number} of the code): {line.strip()}")
        self.assertEqual(offenders, [],
                         "an installer passes a program to `python -c`; put it in "
                         "scripts/ and call it with arguments instead:\n"
                         + "\n".join(offenders))

    def test_no_installer_deletes_a_rules_directory(self):
        patterns = (r"Remove-Item[^\n]*\$dst", r"rm\s+-rf[^\n]*rules")
        offenders = []
        for name, lines in self.sources().items():
            for pattern in patterns:
                for match in re.finditer(pattern, "\n".join(lines)):
                    offenders.append(f"{name}: {match.group(0).strip()}")
        self.assertEqual(offenders, [],
                         "an installer deletes a destination directory it does not own; "
                         "superseded files are pruned by name from the install manifest")


if __name__ == "__main__":
    unittest.main()
