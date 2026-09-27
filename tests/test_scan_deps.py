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

    def test_07_internal_monorepo_dag_and_subproject_scoped_kb(self):
        """Test internal monorepo DAG resolution, invariant extraction, and subproject-scoped KB."""
        # 1. Root package.json
        with open(os.path.join(self.test_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "actdim-monorepo", "private": True}, f)

        # 2. Internal package: packages/dynstruct
        dyn_dir = os.path.join(self.test_dir, "packages", "dynstruct")
        os.makedirs(dyn_dir, exist_ok=True)
        with open(os.path.join(dyn_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "@actdim/dynstruct", "version": "1.0.0"}, f)
        with open(os.path.join(dyn_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# Dynstruct Rules\n<!-- EXPORT-INVARIANTS: strict-component-model, no-react-hooks -->\nUse MobX models.")
        with open(os.path.join(dyn_dir, "llms.txt"), "w", encoding="utf-8") as f:
            f.write("# Dynstruct llms summary")

        # 3. Consuming subproject: apps/webapp (initialized Along subproject)
        app_dir = os.path.join(self.test_dir, "apps", "webapp")
        os.makedirs(os.path.join(app_dir, ".along"), exist_ok=True)
        os.makedirs(os.path.join(app_dir, "docs"), exist_ok=True)
        with open(os.path.join(app_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({
                "name": "webapp",
                "dependencies": {
                    "@actdim/dynstruct": "^1.0.0",
                    "zod": "^3.22.0"
                }
            }, f)

        # Mock external zod in apps/webapp/node_modules/zod
        zod_dir = os.path.join(app_dir, "node_modules", "zod")
        os.makedirs(zod_dir, exist_ok=True)
        with open(os.path.join(zod_dir, "llms.txt"), "w", encoding="utf-8") as f:
            f.write("# Zod llms instructions")

        # Run scanner
        res = along_scan_deps.run_scanner(self.test_dir, dry_run=False)

        # Check internal dependencies detected
        internal_deps = res.get("internal_dependencies", [])
        self.assertEqual(len(internal_deps), 1)
        self.assertEqual(internal_deps[0]["package"], "@actdim/dynstruct")
        self.assertEqual(internal_deps[0]["target_project"], "@actdim/dynstruct")
        self.assertIn("strict-component-model", internal_deps[0]["invariants"])
        self.assertIn("no-react-hooks", internal_deps[0]["invariants"])

        # Check root docs/topic--dependencies.md
        root_kb = os.path.join(self.test_dir, "docs", "topic--dependencies.md")
        self.assertTrue(os.path.isfile(root_kb))
        with open(root_kb, "r", encoding="utf-8") as f:
            root_content = f.read()
        self.assertIn("## Internal Monorepo Dependency Graph", root_content)
        self.assertIn("@actdim/dynstruct", root_content)
        self.assertIn("apps/webapp", root_content)
        self.assertIn("## Transitive Dependency Guidelines & Invariants", root_content)
        self.assertIn("strict-component-model", root_content)

        # Check subproject docs/topic--dependencies.md
        sub_kb = os.path.join(app_dir, "docs", "topic--dependencies.md")
        self.assertTrue(os.path.isfile(sub_kb), "Subproject topic--dependencies.md must be generated")
        with open(sub_kb, "r", encoding="utf-8") as f:
            sub_content = f.read()

        self.assertIn("# Dependencies & AI Documentation for `webapp`", sub_content)
        self.assertIn("## Internal Workspace Dependencies", sub_content)
        self.assertIn("@actdim/dynstruct", sub_content)
        # Relative link from apps/webapp/docs/ to packages/dynstruct/llms.txt
        self.assertIn("../../packages/dynstruct/llms.txt", sub_content)
        self.assertIn("../../packages/dynstruct/AGENTS.md", sub_content)
        # External dependency zod included in subproject docs
        self.assertIn("zod", sub_content)
        # Invariants section in subproject docs
        self.assertIn("## Transitive Dependency Guidelines & Invariants", sub_content)
        self.assertIn("strict-component-model", sub_content)
        self.assertIn("no-react-hooks", sub_content)

    def test_08_subproject_linking_flag(self):
        """Test --link flag updates managed block in subproject AGENTS.md."""
        # Setup monorepo
        with open(os.path.join(self.test_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "root-repo", "private": True}, f)

        lib_dir = os.path.join(self.test_dir, "packages", "core-lib")
        os.makedirs(lib_dir, exist_ok=True)
        with open(os.path.join(lib_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "@monorepo/core", "version": "1.0.0"}, f)
        with open(os.path.join(lib_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# Core Guidelines\nAlways use pure functions.")

        app_dir = os.path.join(self.test_dir, "apps", "client")
        os.makedirs(os.path.join(app_dir, ".along"), exist_ok=True)
        with open(os.path.join(app_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "client-app", "dependencies": {"@monorepo/core": "workspace:*"}}, f)

        agents_path = os.path.join(app_dir, "AGENTS.md")
        with open(agents_path, "w", encoding="utf-8") as f:
            f.write("# Client App Instructions\nDo not break UI.\n")

        # 1. Run without --link: AGENTS.md must NOT be modified
        along_scan_deps.run_scanner(self.test_dir, dry_run=False, link=False)
        with open(agents_path, "r", encoding="utf-8") as f:
            content_no_link = f.read()
        self.assertNotIn("<!-- BEGIN ALONG-DEPS", content_no_link)

        # 2. Run with --link: managed block must be injected
        along_scan_deps.run_scanner(self.test_dir, dry_run=False, link=True)
        with open(agents_path, "r", encoding="utf-8") as f:
            content_with_link = f.read()

        self.assertIn("<!-- BEGIN ALONG-DEPS (managed by along dep-scan - do not edit) -->", content_with_link)
        self.assertIn("@monorepo/core", content_with_link)
        self.assertIn("[AGENTS.md](../../packages/core-lib/AGENTS.md)", content_with_link)
        self.assertIn("<!-- END ALONG-DEPS -->", content_with_link)
        self.assertIn("Do not break UI.", content_with_link)

        # 3. Idempotent re-run: block is updated cleanly without duplication
        along_scan_deps.run_scanner(self.test_dir, dry_run=False, link=True)
        with open(agents_path, "r", encoding="utf-8") as f:
            content_rerun = f.read()
        self.assertEqual(content_rerun.count("BEGIN ALONG-DEPS"), 1)

    def test_09_subproject_boundary_preservation(self):
        """Test uninitialized subprojects do not get spurious docs directories unless requested."""
        with open(os.path.join(self.test_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "mono-root", "private": True}, f)

        # Subproject without .along and without docs
        uninit_dir = os.path.join(self.test_dir, "packages", "uninit-pkg")
        os.makedirs(uninit_dir, exist_ok=True)
        with open(os.path.join(uninit_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "@mono/uninit", "version": "1.0.0"}, f)

        # Default run: uninit-pkg/docs must NOT exist
        along_scan_deps.run_scanner(self.test_dir, dry_run=False, all_subprojects=False)
        self.assertFalse(os.path.exists(os.path.join(uninit_dir, "docs")))

        # With all_subprojects=True: uninit-pkg/docs IS created
        along_scan_deps.run_scanner(self.test_dir, dry_run=False, all_subprojects=True)
        self.assertTrue(os.path.isfile(os.path.join(uninit_dir, "docs", "topic--dependencies.md")))

    def test_10_multiline_exported_invariants(self):
        """Test parsing multi-line block exported invariants."""
        pkg_dir = os.path.join(self.test_dir, "some-pkg")
        os.makedirs(pkg_dir, exist_ok=True)
        with open(os.path.join(pkg_dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("""# Some Pkg
<!-- BEGIN-EXPORT-INVARIANTS -->
- Use deterministic UUIDs only
- Never import react-dom directly
<!-- END-EXPORT-INVARIANTS -->
""")
        invariants = along_scan_deps.extract_exported_invariants(pkg_dir)
        self.assertIn("Use deterministic UUIDs only", invariants)
        self.assertIn("Never import react-dom directly", invariants)


if __name__ == "__main__":
    unittest.main()
