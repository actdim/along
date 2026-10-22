#!/usr/bin/env python3
"""
tests/test_along_env.py - Tests for along env isolated Docker environment manager.
[feat--isolated-environment-docker]
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

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

from alongkit import environment, proc

ALONG_EXEC = os.path.join(SCRIPTS_DIR, "along_exec.py")
ALONG_ENV = os.path.join(SCRIPTS_DIR, "along_env.py")


class TestEnvConfigAndCompose(unittest.TestCase):
    """Test environment configuration loading, saving, and compose synthesis."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="along-test-env-")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_resolve_env_dir(self):
        """Path resolution properly handles base dir and specific env dir."""
        resolved = environment.resolve_env_dir("proj1", base_dir=self.tmp_dir)
        self.assertEqual(resolved, os.path.join(self.tmp_dir, "proj1"))

        # Passing env directory itself as base_dir
        specific = os.path.join(self.tmp_dir, "proj1")
        self.assertEqual(environment.resolve_env_dir("proj1", base_dir=specific), specific)

        # Empty name raises ValueError
        with self.assertRaises(ValueError):
            environment.resolve_env_dir("")

    def test_save_and_load_config_stays_under_20_lines(self):
        """env.yaml default configuration must stay under 20 lines."""
        env_dir = os.path.join(self.tmp_dir, "myproj")
        config = {
            "name": "myproj",
            "repo": "https://github.com/actdim/along.git",
            "branch": "develop",
            "runtimes": ["claude-code", "opencode"],
            "telegram_chat_id": "12345",
            "egress_allowlist": ["custom.api.io"],
            "image": "actdim/along-autonomous:latest",
            "gvisor": False,
        }
        env_file = environment.save_env_config(env_dir, config)
        self.assertTrue(os.path.exists(env_file))

        with open(env_file, "r", encoding="utf-8") as f:
            lines = [l for l in f.readlines() if l.strip()]
        self.assertLess(len(lines), 20, f"env.yaml must stay under 20 lines (got {len(lines)})")

        loaded = environment.load_env_config(env_dir)
        self.assertEqual(loaded["name"], "myproj")
        self.assertEqual(loaded["repo"], "https://github.com/actdim/along.git")
        self.assertEqual(loaded["branch"], "develop")
        self.assertEqual(loaded["runtimes"], ["claude-code", "opencode"])
        self.assertEqual(loaded["telegram_chat_id"], "12345")
        self.assertEqual(loaded["egress_allowlist"], ["custom.api.io"])

    def test_ensure_secrets_file_template(self):
        """secrets.env is created with required secret keys and not overwritten."""
        env_dir = os.path.join(self.tmp_dir, "secrets-test")
        secrets_file = environment.ensure_secrets_file(env_dir)
        self.assertTrue(os.path.exists(secrets_file))

        with open(secrets_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("ANTHROPIC_API_KEY=", content)
        self.assertIn("OPENAI_API_KEY=", content)
        self.assertIn("GEMINI_API_KEY=", content)
        self.assertIn("GITHUB_TOKEN=", content)
        self.assertIn("TELEGRAM_BOT_TOKEN=", content)
        self.assertIn("ALONG_AUTONOMOUS=1", content)

        # Calling again does not overwrite custom content
        with open(secrets_file, "a", encoding="utf-8") as f:
            f.write("\nCUSTOM_KEY=custom_value\n")
        environment.ensure_secrets_file(env_dir)
        with open(secrets_file, "r", encoding="utf-8") as f:
            self.assertIn("CUSTOM_KEY=custom_value", f.read())

    def test_generate_compose_yaml_deterministic(self):
        """compose.yaml contains all required volumes, restart policies, and security caps."""
        config = {
            "name": "alpha",
            "repo": "https://github.com/actdim/along.git",
            "branch": "main",
            "runtimes": ["claude-code", "opencode"],
            "telegram_chat_id": "-1001",
            "egress_allowlist": ["api.example.com"],
            "image": "actdim/along-autonomous:latest",
            "gvisor": False,
        }
        yaml1 = environment.generate_compose_yaml(config)
        yaml2 = environment.generate_compose_yaml(config)
        self.assertEqual(yaml1, yaml2, "compose.yaml synthesis must be deterministic")

        self.assertIn("container_name: along-alpha", yaml1)
        self.assertIn("restart: unless-stopped", yaml1)
        self.assertIn("- NET_ADMIN", yaml1)
        self.assertIn("- secrets.env", yaml1)
        self.assertIn("- repo:/workspace", yaml1)
        self.assertIn("- claude_auth:/home/along/.claude", yaml1)
        self.assertIn("- opencode_auth:/home/along/.opencode", yaml1)
        self.assertIn("- cache:/home/along/.cache", yaml1)
        self.assertIn("volumes:\n  repo:\n  claude_auth:\n  opencode_auth:\n  cache:", yaml1)
        self.assertNotIn("runtime: runsc", yaml1)

        # Test gVisor switch
        config["gvisor"] = True
        yaml_gvisor = environment.generate_compose_yaml(config)
        self.assertIn("runtime: runsc", yaml_gvisor)


class TestEnvLifecycle(unittest.TestCase):
    """Test environment lifecycle functions (up, down, status, update)."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="along-test-lifecycle-")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_env_up_creates_structure(self):
        """env_up provisions directory, env.yaml, secrets.env, and compose.yaml."""
        res = environment.env_up(
            name="testenv",
            repo_url="https://github.com/actdim/along.git",
            branch="main",
            base_dir=self.tmp_dir,
            run_compose=False,
        )
        self.assertEqual(res["name"], "testenv")
        env_dir = res["path"]
        self.assertTrue(os.path.isdir(env_dir))
        self.assertTrue(os.path.isfile(os.path.join(env_dir, "env.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(env_dir, "secrets.env")))
        self.assertTrue(os.path.isfile(os.path.join(env_dir, "compose.yaml")))

    def test_env_down_preserves_volumes_and_files(self):
        """env_down preserves persistent configuration files."""
        res_up = environment.env_up("down-test", base_dir=self.tmp_dir, run_compose=False)
        env_dir = res_up["path"]

        res_down = environment.env_down("down-test", base_dir=self.tmp_dir, run_compose=False)
        self.assertEqual(res_down["name"], "down-test")
        self.assertTrue(os.path.isfile(os.path.join(env_dir, "env.yaml")))
        self.assertTrue(os.path.isfile(os.path.join(env_dir, "secrets.env")))
        self.assertTrue(os.path.isfile(os.path.join(env_dir, "compose.yaml")))

    def test_env_down_nonexistent_raises(self):
        """env_down on missing environment raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            environment.env_down("nonexistent", base_dir=self.tmp_dir, run_compose=False)

    def test_env_status_single_and_listing(self):
        """env_status returns structured metadata for single and multiple environments."""
        environment.env_up("env-a", repo_url="https://repo-a.git", base_dir=self.tmp_dir, run_compose=False)
        environment.env_up("env-b", repo_url="https://repo-b.git", base_dir=self.tmp_dir, run_compose=False)

        status_a = environment.env_status("env-a", base_dir=self.tmp_dir)
        self.assertIsInstance(status_a, dict)
        self.assertEqual(status_a["name"], "env-a")
        self.assertEqual(status_a["repo"], "https://repo-a.git")
        self.assertTrue(status_a["has_secrets"])
        self.assertTrue(status_a["has_compose"])

        all_envs = environment.env_status(base_dir=self.tmp_dir)
        self.assertIsInstance(all_envs, list)
        self.assertEqual(len(all_envs), 2)
        names = [e["name"] for e in all_envs]
        self.assertIn("env-a", names)
        self.assertIn("env-b", names)

    def test_env_update_refreshes_compose(self):
        """env_update regenerates compose.yaml with any updated env.yaml settings."""
        res_up = environment.env_up("upd-env", base_dir=self.tmp_dir, run_compose=False)
        env_dir = res_up["path"]

        config = environment.load_env_config(env_dir)
        config["gvisor"] = True
        environment.save_env_config(env_dir, config)

        environment.env_update("upd-env", base_dir=self.tmp_dir, run_compose=False)
        with open(os.path.join(env_dir, "compose.yaml"), "r", encoding="utf-8") as f:
            self.assertIn("runtime: runsc", f.read())


class TestEnvCliCommands(unittest.TestCase):
    """Test CLI commands and argument parsing for along env."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="along-cli-env-")
        self.env = dict(os.environ)
        self.env["ALONG_ENVS_DIR"] = self.tmp_dir

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run(self, *args: str) -> proc.Result:
        return proc.run_capture([sys.executable, ALONG_EXEC, "env", *args], cwd=REPO_ROOT, env=self.env)

    def test_env_help(self):
        """along env --help and -h output usage with return code 0."""
        for flag in ("--help", "-h"):
            res = self._run(flag)
            self.assertEqual(res.returncode, 0)
            self.assertIn("Usage: along env", res.stdout)
            self.assertIn("up", res.stdout)
            self.assertIn("down", res.stdout)
            self.assertIn("status", res.stdout)

    def test_subcommand_help_options(self):
        """Subcommand --help displays specific usage and exits 0."""
        for sub in ("up", "down", "status", "logs", "shell", "update"):
            res = self._run(sub, "--help")
            self.assertEqual(res.returncode, 0)
            self.assertIn(f"along env {sub}", res.stdout)

    def test_unknown_subcommand_fails_with_code_2(self):
        """Unrecognized subcommand fails with exit code 2."""
        res = self._run("unknown-cmd")
        self.assertEqual(res.returncode, 2)
        self.assertIn("Unknown subcommand", res.stderr)

    def test_flag_like_names_fail_with_code_2(self):
        """Entity names starting with hyphen must fail with exit code 2."""
        for sub in ("up", "down", "logs", "shell", "update"):
            res = self._run(sub, "-bad-name")
            self.assertEqual(res.returncode, 2, f"Subcommand {sub} did not reject flag-like name")
            self.assertIn("cannot start with '-'", res.stderr)

    def test_unrecognized_arguments_fail_with_code_2(self):
        """Unrecognized flags fail loudly with exit code 2."""
        res = self._run("up", "testenv", "--invalid-flag")
        self.assertEqual(res.returncode, 2)
        self.assertIn("unrecognized arguments", res.stderr)

    def test_cli_up_status_and_down_lifecycle(self):
        """End-to-end CLI lifecycle for up, status (--json), and down."""
        # 1. UP
        res_up = self._run("up", "cli-proj", "--repo", "https://github.com/actdim/along.git", "--dir", self.tmp_dir)
        self.assertEqual(res_up.returncode, 0)
        self.assertIn("Created isolated environment: cli-proj", res_up.stdout)

        # 2. STATUS (single env, JSON)
        res_stat = self._run("status", "cli-proj", "--dir", self.tmp_dir, "--json")
        self.assertEqual(res_stat.returncode, 0)
        data = json.loads(res_stat.stdout)
        self.assertEqual(data["name"], "cli-proj")
        self.assertEqual(data["repo"], "https://github.com/actdim/along.git")
        self.assertTrue(data["has_secrets"])
        self.assertTrue(data["has_compose"])

        # 3. STATUS (table listing)
        res_list = self._run("status", "--dir", self.tmp_dir)
        self.assertEqual(res_list.returncode, 0)
        self.assertIn("cli-proj", res_list.stdout)

        # 4. DOWN
        res_down = self._run("down", "cli-proj", "--dir", self.tmp_dir)
        self.assertEqual(res_down.returncode, 0)
        self.assertIn("Stopped isolated environment: cli-proj", res_down.stdout)

    def test_standalone_along_env_script(self):
        """scripts/along_env.py direct execution works identically."""
        res = proc.run_capture([sys.executable, ALONG_ENV, "--help"], cwd=REPO_ROOT, env=self.env)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage: along env", res.stdout)


class TestDockerAssetsIntegrity(unittest.TestCase):
    """Test Docker assets specifications and firewall allowlist."""

    def test_dockerfiles_exist_and_configured(self):
        """Dockerfile.autonomous and Dockerfile exist and configure non-root user and runtimes."""
        for path in ("docker/Dockerfile.autonomous", "docker/Dockerfile"):
            full_path = os.path.join(REPO_ROOT, path)
            self.assertTrue(os.path.isfile(full_path), f"Missing {path}")
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("FROM ubuntu:24.04", content)
            self.assertIn("useradd -u 1000 -g along", content)
            self.assertIn("@anthropic-ai/claude-code", content)
            self.assertIn("opencode-ai", content)
            self.assertIn("actdim-along", content)
            self.assertIn("VOLUME [\"/workspace\"", content)

    def test_init_firewall_contains_mandatory_allowlist(self):
        """init-firewall.sh declares iptables egress rules for required endpoints."""
        fw_path = os.path.join(REPO_ROOT, "docker", "init-firewall.sh")
        self.assertTrue(os.path.isfile(fw_path))
        with open(fw_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_hosts = [
            "api.anthropic.com",
            "api.openai.com",
            "generativelanguage.googleapis.com",
            "github.com",
            "pypi.org",
            "registry.npmjs.org",
            "api.telegram.org",
        ]
        for host in required_hosts:
            self.assertIn(host, content, f"Missing required allowlisted host: {host}")

        self.assertIn("iptables -P OUTPUT DROP", content)
        self.assertIn("iptables -P INPUT DROP", content)

    def test_entrypoint_exists(self):
        """entrypoint.sh exists and configures initialization."""
        entry_path = os.path.join(REPO_ROOT, "docker", "entrypoint.sh")
        self.assertTrue(os.path.isfile(entry_path))
        with open(entry_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("init-firewall.sh", content)
        self.assertIn("exec", content)


if __name__ == "__main__":
    unittest.main()
