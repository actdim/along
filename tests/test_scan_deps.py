#!/usr/bin/env python3
"""
tests/test_scan_deps.py - Unit tests for along_dep_scan.py Hierarchical AI Dependencies Discovery engine.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import along_dep_scan as along_scan_deps


class TestAlongScanDeps(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="along_test_deps_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_01_node_dependencies_discovery(self):
        """Test scanning Node.js project with npm/pnpm dependencies containing AGENTS.md and llms.txt."""
        pkg_json = {
            "name": "test-node-app",
            "dependencies": {
                "mock-lib-a": "^1.0.0",
                "@scoped/mock-lib-b": "^2.1.0",
                "regular-lib-c": "^3.0.0"
            }
        }
        with open(os.path.join(self.test_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump(pkg_json, f)

        # Create mock node_modules
        lib_a_dir = os.path.join(self.test_dir, "node_modules", "mock-lib-a")
        os.makedirs(lib_a_dir, exist_ok=True)
        with open(os.path.join(lib_a_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# Mock Lib A Rules\nAlways use function X.")
        with open(os.path.join(lib_a_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "mock-lib-a", "version": "1.0.0", "ai": {"rules": "AGENTS.md"}}, f)

        lib_b_dir = os.path.join(self.test_dir, "node_modules", "@scoped", "mock-lib-b")
        os.makedirs(lib_b_dir, exist_ok=True)
        with open(os.path.join(lib_b_dir, "llms.txt"), "w", encoding="utf-8") as f:
            f.write("# Scoped Lib B LLMS Context")

        # regular-lib-c has no AI files
        lib_c_dir = os.path.join(self.test_dir, "node_modules", "regular-lib-c")
        os.makedirs(lib_c_dir, exist_ok=True)
        with open(os.path.join(lib_c_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "regular-lib-c", "version": "3.0.0"}, f)

        scope = along_scan_deps.ProjectScope(name="[root]", rel_path=".", full_path=self.test_dir, is_root=True)
        results = along_scan_deps.scan_node_project_deps(scope, self.test_dir)
        self.assertEqual(len(results), 2, "Should discover 2 packages with AI context")

        pkg_names = [r["package"] for r in results]
        self.assertIn("mock-lib-a", pkg_names)
        self.assertIn("@scoped/mock-lib-b", pkg_names)
        self.assertNotIn("regular-lib-c", pkg_names)

    def test_02_python_dependencies_discovery(self):
        """Test scanning Python project with requirements.txt and .venv site-packages."""
        with open(os.path.join(self.test_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write("mock-ai-tool>=1.0.0\nstandard-pkg==2.0\n")

        # Mock virtual environment
        site_pkgs = os.path.join(self.test_dir, ".venv", "Lib", "site-packages")
        os.makedirs(site_pkgs, exist_ok=True)

        tool_dir = os.path.join(site_pkgs, "mock_ai_tool")
        os.makedirs(tool_dir, exist_ok=True)
        with open(os.path.join(tool_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# Mock AI Tool Instructions")

        # dist-info metadata
        dist_info = os.path.join(site_pkgs, "mock_ai_tool-1.2.0.dist-info")
        os.makedirs(dist_info, exist_ok=True)
        with open(os.path.join(dist_info, "METADATA"), "w", encoding="utf-8") as f:
            f.write("Metadata-Version: 2.1\nName: mock-ai-tool\nVersion: 1.2.0\n")

        scope = along_scan_deps.ProjectScope(name="[root]", rel_path=".", full_path=self.test_dir, is_root=True)
        results = along_scan_deps.scan_python_project_deps(scope, self.test_dir)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["package"], "mock-ai-tool")
        self.assertEqual(results[0]["version"], "1.2.0")
        self.assertEqual(results[0]["ecosystem"], "pypi")

    def test_03_rust_dependencies_discovery(self):
        """Test scanning Rust project with Cargo.toml and vendored dependencies."""
        cargo_content = """
        [package]
        name = "test-rust-app"
        version = "0.1.0"

        [dependencies]
        mock-crate-a = "0.5.0"
        mock-crate-b = "1.0"
        """
        with open(os.path.join(self.test_dir, "Cargo.toml"), "w", encoding="utf-8") as f:
            f.write(cargo_content)

        # Mock vendored crate
        v_crate_a = os.path.join(self.test_dir, "vendor", "mock-crate-a")
        os.makedirs(v_crate_a, exist_ok=True)
        with open(os.path.join(v_crate_a, "llms.txt"), "w", encoding="utf-8") as f:
            f.write("# Mock Crate A LLMs instructions")

        scope = along_scan_deps.ProjectScope(name="[root]", rel_path=".", full_path=self.test_dir, is_root=True)
        results = along_scan_deps.scan_rust_project_deps(scope, self.test_dir)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["package"], "mock-crate-a")
        self.assertEqual(results[0]["ecosystem"], "cargo")

    def test_04_nuget_dependencies_discovery(self):
        """Test scanning .NET project with .csproj and local packages folder."""
        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Actdim.MsgMesh" Version="2.0.0" />
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
  </ItemGroup>
</Project>"""
        with open(os.path.join(self.test_dir, "App.csproj"), "w", encoding="utf-8") as f:
            f.write(csproj_content)

        # Mock packages cache in test_dir/packages
        pkg_dir = os.path.join(self.test_dir, "packages", "actdim.msgmesh", "2.0.0")
        os.makedirs(pkg_dir, exist_ok=True)
        with open(os.path.join(pkg_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# MsgMesh .NET Guidelines")

        scope = along_scan_deps.ProjectScope(name="[root]", rel_path=".", full_path=self.test_dir, is_root=True)
        results = along_scan_deps.scan_nuget_project_deps(scope, self.test_dir)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["package"], "Actdim.MsgMesh")
        self.assertEqual(results[0]["ecosystem"], "nuget")

    def test_04b_nuget_semver_sorting_discovery(self):
        """Test scanning .NET project picks highest semver (10.0.0 > 9.0.0)."""
        csproj_content = """<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Actdim.BigLib" />
  </ItemGroup>
</Project>"""
        with open(os.path.join(self.test_dir, "App2.csproj"), "w", encoding="utf-8") as f:
            f.write(csproj_content)

        # Mock packages cache with multiple versions where ASCII order differs from semver
        pkg_base = os.path.join(self.test_dir, "packages", "actdim.biglib")
        for v in ("2.0.0", "9.0.0", "10.0.0"):
            v_dir = os.path.join(pkg_base, v)
            os.makedirs(v_dir, exist_ok=True)
            with open(os.path.join(v_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
                f.write(f"# BigLib v{v} Guidelines")

        scope = along_scan_deps.ProjectScope(name="[root]", rel_path=".", full_path=self.test_dir, is_root=True)
        results = along_scan_deps.scan_nuget_project_deps(scope, self.test_dir)
        matched = [r for r in results if r["package"] == "Actdim.BigLib"]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["version"], "10.0.0")

    def test_05_hierarchical_monorepo_subprojects_and_kb_generation(self):
        """Test recursive discovery of nested packages and submodules with Wiki generation."""
        # Root package.json (no deps)
        with open(os.path.join(self.test_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "monorepo-root", "private": True}, f)

        # Subproject 1: packages/ui-app
        ui_dir = os.path.join(self.test_dir, "packages", "ui-app")
        os.makedirs(ui_dir, exist_ok=True)
        with open(os.path.join(ui_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "@monorepo/ui", "dependencies": {"fast-sdk": "^1.0.0"}}, f)
        with open(os.path.join(ui_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# UI App Guidelines")

        # Subproject 1 node_modules
        sdk_dir = os.path.join(ui_dir, "node_modules", "fast-sdk")
        os.makedirs(sdk_dir, exist_ok=True)
        with open(os.path.join(sdk_dir, "llms.txt"), "w", encoding="utf-8") as f:
            f.write("# Fast SDK instructions")

        # Subproject 2: modules/backend (.NET)
        be_dir = os.path.join(self.test_dir, "modules", "backend")
        os.makedirs(be_dir, exist_ok=True)
        with open(os.path.join(be_dir, "Backend.csproj"), "w", encoding="utf-8") as f:
            f.write('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><PackageReference Include="Micro.Lib" Version="1.0" /></ItemGroup></Project>')

        # Run scanner
        scan_output = along_scan_deps.run_scanner(self.test_dir, dry_run=False)
        self.assertGreaterEqual(len(scan_output["projects"]), 3, "Should discover root, packages/ui-app, and modules/backend")

        dep_kb = os.path.join(self.test_dir, "docs", "topic--dependencies.md")
        self.assertTrue(os.path.isfile(dep_kb), "docs/topic--dependencies.md must be generated")

        with open(dep_kb, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("## Internal Subprojects, Modules & Submodules", content)
        self.assertIn("@monorepo/ui", content)
        self.assertIn("modules/backend", content)
        self.assertIn("fast-sdk", content)
        self.assertIn("packages/ui-app", content)
        self.assertIn("protocol: along", content)

    def test_06_custom_adaptive_hook(self):
        """Test execution of .along/scripts/dep_scan.py custom hook."""
        along_scripts = os.path.join(self.test_dir, ".along", "scripts")
        os.makedirs(along_scripts, exist_ok=True)
        hook_file = os.path.join(along_scripts, "dep_scan.py")

        hook_code = """#!/usr/bin/env python3
import json
print(json.dumps([{
    "package": "custom-elixir-dep",
    "ecosystem": "hex",
    "version": "0.9.0",
    "files": [{"filename": "AGENTS.md", "path": "custom/AGENTS.md"}]
}]))
"""
        with open(hook_file, "w", encoding="utf-8") as f:
            f.write(hook_code)

        results = along_scan_deps.run_custom_dep_scan_hook(self.test_dir, self.test_dir)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["package"], "custom-elixir-dep")
        self.assertEqual(results[0]["ecosystem"], "hex")


if __name__ == "__main__":
    unittest.main()
