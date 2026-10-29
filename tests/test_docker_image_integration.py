#!/usr/bin/env python3
"""
tests/test_docker_image_integration.py - Real Docker integration tests for autonomous container image and firewall.
[bug--autonomous-container-build-and-firewall]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(
    os.environ.get("ALONG_DOCKER_TESTS") == "1" and shutil.which("docker"),
    "Opt-in integration test suite requiring ALONG_DOCKER_TESTS=1 and docker on PATH"
)
class TestDockerImageIntegration(unittest.TestCase):
    """End-to-end integration tests using real Docker daemon."""

    image_tag = "along-autonomous:test"
    container_id: str = ""
    network_name: str = ""

    @classmethod
    def setUpClass(cls):
        # 1. Build Docker image
        build_cmd = ["docker", "build", "-f", "docker/Dockerfile", "-t", cls.image_tag, "."]
        res = subprocess.run(build_cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=1800)
        if res.returncode != 0:
            tail = "\n".join(res.stderr.splitlines()[-20:])
            raise RuntimeError(f"docker build failed with exit code {res.returncode}:\n{tail}")

        # 2. Create user-defined network for embedded DNS testing (127.0.0.11)
        cls.network_name = f"along-fw-{uuid.uuid4().hex[:8]}"
        subprocess.run(["docker", "network", "create", cls.network_name], check=True, capture_output=True)

        # 3. Start running test container with extra allowlist
        run_cmd = [
            "docker", "run", "-d",
            "--cap-add", "NET_ADMIN",
            "--network", cls.network_name,
            "-e", "ALONG_EXTRA_EGRESS=example.org",
            cls.image_tag,
            "sleep", "infinity"
        ]
        res_run = subprocess.run(run_cmd, capture_output=True, text=True, check=True)
        cls.container_id = res_run.stdout.strip()

        # 4. Wait for firewall initialization to complete
        ready = False
        deadline = time.time() + 30
        while time.time() < deadline:
            logs = subprocess.run(["docker", "logs", cls.container_id], capture_output=True, text=True).stdout
            if "Egress firewall successfully configured" in logs or "All unauthorized outbound traffic dropped" in logs:
                ready = True
                break
            time.sleep(1)

        if not ready:
            logs = subprocess.run(["docker", "logs", cls.container_id], capture_output=True, text=True).stdout
            raise TimeoutError(f"Container firewall did not become ready within 30s. Logs:\n{logs}")

    @classmethod
    def tearDownClass(cls):
        if cls.container_id:
            subprocess.run(["docker", "rm", "-f", cls.container_id], capture_output=True)
        if cls.network_name:
            subprocess.run(["docker", "network", "rm", cls.network_name], capture_output=True)

    def test_user_is_non_root_along(self):
        """Container agent executes with non-root along user (UID 1000)."""
        # 1. Entrypoint drops privileges to along (UID 1000) for agent commands
        res_run = subprocess.run(
            ["docker", "run", "--rm", "--cap-add", "NET_ADMIN", self.image_tag, "id", "-u"],
            capture_output=True, text=True
        )
        self.assertEqual(res_run.returncode, 0)
        self.assertEqual(res_run.stdout.strip().splitlines()[-1], "1000")

        # 2. In running container, the agent command (PID 1) executes under UID 1000
        res_top = subprocess.run(
            ["docker", "exec", self.container_id, "ps", "-o", "uid,comm", "-p", "1"],
            capture_output=True, text=True
        )
        self.assertEqual(res_top.returncode, 0)
        self.assertIn("1000", res_top.stdout)

        # 3. Interactive shell exec as user along
        res_exec = subprocess.run(
            ["docker", "exec", "-u", "along", self.container_id, "id", "-u"],
            capture_output=True, text=True
        )
        self.assertEqual(res_exec.returncode, 0)
        self.assertEqual(res_exec.stdout.strip(), "1000")

    def test_dns_resolution_and_default_allowlist(self):
        """DNS resolution works through Docker embedded resolver and allowlisted endpoints succeed."""
        res_dns = subprocess.run(["docker", "exec", self.container_id, "getent", "hosts", "github.com"], capture_output=True, text=True)
        self.assertEqual(res_dns.returncode, 0, f"DNS resolution failed: {res_dns.stderr}")

        res_curl = subprocess.run(
            ["docker", "exec", self.container_id, "curl", "-sS", "-o", "/dev/null", "--max-time", "15", "https://api.anthropic.com"],
            capture_output=True, text=True
        )
        self.assertEqual(res_curl.returncode, 0, f"Curl to api.anthropic.com failed: {res_curl.stderr}")

    def test_extra_egress_allowlist_reachable(self):
        """Extra allowlist endpoint example.org configured via ALONG_EXTRA_EGRESS is reachable."""
        res = subprocess.run(
            ["docker", "exec", self.container_id, "curl", "-sS", "-o", "/dev/null", "--max-time", "15", "https://example.org"],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0, f"Curl to extra allowlist example.org failed: {res.stderr}")

    def test_unauthorized_egress_blocked(self):
        """Endpoint outside allowlist is blocked in container without extra egress."""
        # Use a second container without extra allowlist on the network
        run_cmd = [
            "docker", "run", "--rm",
            "--cap-add", "NET_ADMIN",
            "--network", self.network_name,
            self.image_tag,
            "curl", "-sS", "-o", "/dev/null", "--max-time", "5", "https://example.com"
        ]
        res = subprocess.run(run_cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0, "Unauthorized host example.com should be blocked by firewall")

    def test_direct_external_dns_tunnelling_fails(self):
        """Direct queries to external DNS servers bypassing configured resolver fail."""
        res = subprocess.run(
            ["docker", "exec", self.container_id, "dig", "@1.1.1.1", "+time=2", "+tries=1", "example.com"],
            capture_output=True, text=True
        )
        self.assertNotEqual(res.returncode, 0, "Direct external DNS query to 1.1.1.1 must fail")

    def test_ipv6_filtering_and_blocking(self):
        """IPv6 traffic is blocked and OUTPUT policy is DROP."""
        res_rules = subprocess.run(["docker", "exec", "-u", "0", self.container_id, "ip6tables", "-S", "OUTPUT"], capture_output=True, text=True)
        if res_rules.returncode == 0:
            self.assertIn("-P OUTPUT DROP", res_rules.stdout)

        res_curl = subprocess.run(
            ["docker", "exec", self.container_id, "curl", "-6", "--max-time", "5", "https://[2606:4700:4700::1111]"],
            capture_output=True, text=True
        )
        self.assertNotEqual(res_curl.returncode, 0, "Outbound IPv6 connection must fail")

    def test_sudo_is_absent(self):
        """Agent user has no sudo privileges."""
        res = subprocess.run(["docker", "exec", self.container_id, "sudo", "-n", "true"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)

    def test_git_credential_helper_configured(self):
        """Git credential helper is configured system-wide."""
        res = subprocess.run(
            ["docker", "exec", self.container_id, "git", "config", "--system", "--get", "credential.https://github.com.helper"],
            capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "/usr/local/bin/git-credential-along")

    def test_fail_closed_without_net_admin(self):
        """Without NET_ADMIN capability, container refuses to start unless ALONG_FIREWALL=off."""
        res_fail = subprocess.run(["docker", "run", "--rm", self.image_tag, "true"], capture_output=True, text=True)
        self.assertNotEqual(res_fail.returncode, 0)
        output = res_fail.stdout + res_fail.stderr
        self.assertIn("firewall", output.lower())

        res_bypass = subprocess.run(["docker", "run", "--rm", "-e", "ALONG_FIREWALL=off", self.image_tag, "true"], capture_output=True, text=True)
        self.assertEqual(res_bypass.returncode, 0)


if __name__ == "__main__":
    unittest.main()
