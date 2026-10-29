#!/usr/bin/env python3
"""
tests/test_docker_scripts.py - Tests for Docker entrypoint, firewall, and credential helper.
[bug--autonomous-container-build-and-firewall]
"""

from __future__ import annotations

import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from typing import Optional

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import environment


def _real_bash() -> Optional[str]:
    """Find a functional bash executable, rejecting broken WSL launchers in System32."""
    candidates = []
    which_bash = shutil.which("bash")
    if which_bash and "system32" not in which_bash.lower():
        candidates.append(which_bash)
    if sys.platform == "win32":
        for prefix in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LocalAppData", "") + r"\Programs",
        ):
            if prefix:
                candidates.append(os.path.join(prefix, "Git", "bin", "bash.exe"))
                candidates.append(os.path.join(prefix, "Git", "usr", "bin", "bash.exe"))
    for cand in candidates:
        if cand and os.path.isfile(cand):
            try:
                res = subprocess.run([cand, "-c", "echo ok"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip() == "ok":
                    return cand
            except (OSError, subprocess.SubprocessError):
                pass
    return None


def _to_posix(path: str) -> str:
    """Convert path to POSIX format for bash compatibility on Windows."""
    if not isinstance(path, str):
        return path
    if not (os.path.isabs(path) or (len(path) >= 2 and path[1] == ':') or os.path.exists(path)):
        return path
    norm = os.path.normpath(os.path.abspath(path))
    if len(norm) >= 2 and norm[1] == ':':
        return f"/{norm[0].lower()}{norm[2:].replace(os.sep, '/')}"
    return norm.replace(os.sep, '/')


class TestDockerScriptsStructural(unittest.TestCase):
    """Structural assertions on shell scripts without requiring bash execution."""

    def test_entrypoint_structural(self):
        """entrypoint.sh has no || true, contains setpriv, no sudo, and no persisted tokens."""
        path = os.path.join(REPO_ROOT, "docker", "entrypoint.sh")
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        content = "".join(lines)
        self.assertIn("FIREWALL_SCRIPT=/usr/local/bin/init-firewall.sh\n", content)
        self.assertIn("ALONG_FIREWALL", content)
        self.assertIn("setpriv", content)
        self.assertNotIn("sudo", content)
        self.assertNotIn("x-access-token:", content)
        self.assertNotIn("${GITHUB_TOKEN}@", content)

        # Ensure no line contains || true
        for line in lines:
            self.assertNotIn("|| true", line)

    def test_init_firewall_structural(self):
        """init-firewall.sh touches no nat table, drops IPv6, restricts port 53, and refreshes."""
        path = os.path.join(REPO_ROOT, "docker", "init-firewall.sh")
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("-t nat -F", content)
        self.assertNotIn("-t nat -X", content)
        self.assertIn("ip6tables -P OUTPUT DROP", content)
        self.assertIn("--refresh", content)
        self.assertIn("ipset swap", content)

        # No port 53 rule without -d destination
        for line in content.splitlines():
            if "--dport 53" in line and not line.strip().startswith("#"):
                self.assertIn("-d", line, f"Port 53 rule missing destination IP: {line}")

        # Check there is no early exit 0 before rules are set
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "exit 0":
                # Only allowable inside --refresh branch or at the end
                self.assertTrue(
                    "REFRESH_MODE" in content[:content.find(line)] or idx > len(lines) - 5,
                    f"Unexpected early exit 0 at line {idx + 1}"
                )

    def test_allowlist_parity_with_python_ssot(self):
        """DEFAULT_ALLOWLIST in init-firewall.sh matches alongkit.environment."""
        path = os.path.join(REPO_ROOT, "docker", "init-firewall.sh")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"DEFAULT_ALLOWLIST=\(\s*([\s\S]*?)\)", content)
        self.assertIsNotNone(match, "Could not find DEFAULT_ALLOWLIST array in init-firewall.sh")
        raw_items = match.group(1).splitlines()
        shell_hosts = []
        for line in raw_items:
            clean = line.strip().strip('"').strip("'")
            if clean:
                shell_hosts.append(clean)

        self.assertEqual(shell_hosts, environment.DEFAULT_EGRESS_ALLOWLIST)
        self.assertIn("api.telegram.org", shell_hosts)

    def test_git_credential_along_structural(self):
        """git-credential-along exists and is configured in Dockerfile."""
        cred_path = os.path.join(REPO_ROOT, "docker", "git-credential-along")
        self.assertTrue(os.path.isfile(cred_path))

        dockerfile_path = os.path.join(REPO_ROOT, "docker", "Dockerfile")
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            df_content = f.read()
        self.assertIn("credential.https://github.com.helper /usr/local/bin/git-credential-along", df_content)


@unittest.skipUnless(_real_bash(), "A functional bash shell is required for harness tests")
class TestDockerScriptsHarness(unittest.TestCase):
    """Execution tests for shell scripts using real bash and mock binaries."""

    def setUp(self):
        self.bash = _real_bash()
        self.tmp_dir = tempfile.mkdtemp(prefix="along-test-fw-harness-")
        self.bin_dir = os.path.join(self.tmp_dir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.env = dict(os.environ)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_mock_script(self, name: str, body: str) -> str:
        """Create an executable bash script in mock bin directory."""
        path = os.path.join(self.bin_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("#!/usr/bin/env bash\n" + body + "\n")
        try:
            st = os.stat(path)
            os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass
        return path

    def _run_in_bash(self, script_path: str, *args: str, env: Optional[dict] = None, input: Optional[str] = None):
        """Execute script in bash with mock bin directory placed first on PATH."""
        posix_bin = _to_posix(self.bin_dir)
        posix_script = _to_posix(script_path)
        quoted_args = " ".join(f'"{_to_posix(a)}"' for a in args)
        bash_cmd = f'export PATH="{posix_bin}:$PATH"; "{posix_script}" {quoted_args}'
        return subprocess.run([self.bash, "-c", bash_cmd], env=env or self.env, input=input, capture_output=True, text=True)

    def test_entrypoint_fail_closed_and_bypass(self):
        """Entrypoint refuses to start when firewall fails, but allows ALONG_FIREWALL=off."""
        orig_entry = os.path.join(REPO_ROOT, "docker", "entrypoint.sh")
        entry_copy = os.path.join(self.tmp_dir, "entrypoint.sh")
        shutil.copy2(orig_entry, entry_copy)

        stub_firewall = os.path.join(self.tmp_dir, "stub-firewall.sh")
        stub_args_file = os.path.join(self.tmp_dir, "stub-args.txt")
        stub_body_file = os.path.join(self.tmp_dir, "stub-body.txt")

        # Mock binaries: id returns 0, setpriv runs args after --, touch creates file
        self._make_mock_script("id", "echo 0")
        self._make_mock_script("touch", 'echo touched > "$1"')
        self._make_mock_script("setpriv", """
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--" ]; then
        shift
        exec "$@"
    fi
    shift
done
exec "$@"
""")

        # Stub firewall recording arguments and exiting 3 (failure)
        with open(stub_firewall, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"""#!/usr/bin/env bash
echo "$@" > "{_to_posix(stub_args_file)}"
if [ -n "$2" ] && [ -f "$2" ]; then
    cat "$2" > "{_to_posix(stub_body_file)}"
fi
exit 3
""")
        os.chmod(stub_firewall, 0o755)

        # Rewrite FIREWALL_SCRIPT line in entrypoint
        with open(entry_copy, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(entry_copy, "w", encoding="utf-8", newline="\n") as f:
            for line in lines:
                if line.startswith("FIREWALL_SCRIPT="):
                    f.write(f"FIREWALL_SCRIPT=\"{_to_posix(stub_firewall)}\"\n")
                else:
                    f.write(line)

        marker = os.path.join(self.tmp_dir, "marker.txt")

        # 1. Firewall failure causes entrypoint to exit non-zero and refuse to execute command
        res = self._run_in_bash(entry_copy, "touch", marker)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("firewall", res.stderr.lower())
        self.assertFalse(os.path.exists(marker), "Command must not run when firewall fails")

        # 2. ALONG_FIREWALL=off bypasses firewall and executes command
        env_off = dict(self.env)
        env_off["ALONG_FIREWALL"] = "off"
        res_off = self._run_in_bash(entry_copy, "touch", marker, env=env_off)
        self.assertEqual(res_off.returncode, 0, f"entrypoint failed with ALONG_FIREWALL=off: {res_off.stderr}")
        self.assertTrue(os.path.exists(marker), "Command must run when ALONG_FIREWALL=off")
        self.assertIn("firewall disabled", res_off.stderr)

        # 3. ALONG_EXTRA_EGRESS passes allow-file with all items
        env_extra = dict(self.env)
        env_extra["ALONG_EXTRA_EGRESS"] = "a.example, b.example"
        self._run_in_bash(entry_copy, "touch", marker, env=env_extra)
        with open(stub_body_file, "r", encoding="utf-8") as f:
            body = f.read()
        self.assertIn("a.example", body)
        self.assertIn("b.example", body)

    def test_init_firewall_rules_and_lockdown(self):
        """init-firewall triggers lockdown on failure, validates hosts, and targets nameservers."""
        fw_script = os.path.join(REPO_ROOT, "docker", "init-firewall.sh")
        fw_copy = os.path.join(self.tmp_dir, "init-firewall.sh")
        shutil.copy2(fw_script, fw_copy)

        log_file = os.path.join(self.tmp_dir, "calls.log")
        posix_log = _to_posix(log_file)

        # Mock logger helper
        logger_body = f'echo "$0 $@" >> "{posix_log}"\n'

        self._make_mock_script("iptables", f"""
{logger_body}
if [ "$1" = "-N" ] && [ "$2" = "ALONG_PROBE" ]; then
    exit "${{FAIL_PROBE:-0}}"
fi
if [ "${{FAIL_RULE:-0}}" = "1" ] && [ "$1" = "-A" ]; then
    exit 1
fi
exit 0
""")

        self._make_mock_script("ip6tables", f"""
{logger_body}
exit 0
""")

        self._make_mock_script("ipset", f"""
{logger_body}
exit 0
""")

        self._make_mock_script("getent", """
if [ "$1" = "ahostsv4" ]; then
    echo "93.184.216.34 RAW"
    exit 0
fi
exit 1
""")

        self._make_mock_script("curl", """
# Self check expects curl to fail for blocked destinations
exit 1
""")

        resolv_path = os.path.join(self.tmp_dir, "resolv.conf")
        with open(resolv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("nameserver 192.0.2.53\n")

        # 1. Probe failure
        env_probe = dict(self.env)
        env_probe["FAIL_PROBE"] = "1"
        res_probe = self._run_in_bash(fw_copy, env=env_probe)
        self.assertNotEqual(res_probe.returncode, 0)
        with open(log_file, "r", encoding="utf-8") as f:
            probe_logs = f.read()
        self.assertNotIn("-P OUTPUT ACCEPT", probe_logs)

        # 2. Rule failure triggers lockdown
        os.remove(log_file)
        env_rule = dict(self.env)
        env_rule["FAIL_RULE"] = "1"
        env_rule["ALONG_RESOLV_CONF"] = _to_posix(resolv_path)
        res_rule = self._run_in_bash(fw_copy, env=env_rule)
        self.assertNotEqual(res_rule.returncode, 0)
        with open(log_file, "r", encoding="utf-8") as f:
            rule_logs = f.read().strip().splitlines()
        self.assertTrue(rule_logs[-1].endswith("-P OUTPUT DROP"), f"Log did not end with DROP: {rule_logs[-1]}")

        # 3. Allow-file entry bad;host is rejected
        os.remove(log_file)
        bad_allow = os.path.join(self.tmp_dir, "bad-allow.txt")
        with open(bad_allow, "w", encoding="utf-8", newline="\n") as f:
            f.write("bad;host\n")
        res_bad = self._run_in_bash(fw_copy, "--allow-file", bad_allow)
        self.assertNotEqual(res_bad.returncode, 0)

        # 4. Nameserver appears on port 53 rules
        os.remove(log_file)
        env_ok = dict(self.env)
        env_ok["ALONG_RESOLV_CONF"] = _to_posix(resolv_path)
        res_ok = self._run_in_bash(fw_copy, env=env_ok)
        self.assertEqual(res_ok.returncode, 0, f"firewall script failed: {res_ok.stderr}")
        with open(log_file, "r", encoding="utf-8") as f:
            ok_logs = f.read()
        self.assertIn("-d 192.0.2.53 --dport 53", ok_logs)

    def test_git_credential_along_harness(self):
        """git-credential-along supplies password for github.com and stays silent for others."""
        cred_script = os.path.join(REPO_ROOT, "docker", "git-credential-along")

        # 1. Valid GitHub request
        input_gh = "protocol=https\nhost=github.com\n\n"
        env_gh = dict(self.env)
        env_gh["GITHUB_TOKEN"] = "secret-token-xyz"
        res_gh = self._run_in_bash(cred_script, "get", env=env_gh, input=input_gh)
        self.assertEqual(res_gh.returncode, 0)
        self.assertIn("username=x-access-token", res_gh.stdout)
        self.assertIn("password=secret-token-xyz", res_gh.stdout)

        # 2. Non-GitHub host request
        input_evil = "protocol=https\nhost=evil.com\n\n"
        res_evil = self._run_in_bash(cred_script, "get", env=env_gh, input=input_evil)
        self.assertEqual(res_evil.returncode, 0)
        self.assertEqual(res_evil.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
