#!/usr/bin/env python3
"""tests/test_plan_scope.py - Approved plan grants write scope.

[feat--plan-grants-write-scope]
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from alongkit import bootstrap
bootstrap.ensure_deps()

import along_exec
from alongkit import frontmatter, planscope, session, textio
from alongkit.hooks import HookEvent, HookEventType
from alongkit.hooks import predicates

CLEAN_ENV = {
    k: v for k, v in os.environ.items()
    if k not in session.SESSION_ENV_VARS and k not in ("ALONG_PROFILE", "ALONG_AUTONOMOUS")
}
SID = "sess-planscope"
KEY = session.session_key("claude", SID)


class TestPlanPaths(unittest.TestCase):
    def test_plan_paths_extracts_and_cleans_paths(self):
        plan = """# Implementation Plan

## Background
Some notes mentioning `ignore_me.py` before the section.

## Files to change
- `scripts/foo.py:12`
- `../other/x.ts:10-25`
- `src/main.rs`
- `isolated.py`
- `command_name`
- `echo`

## Next Steps
- `also_ignore.py`
"""
        paths = planscope.plan_paths(plan)
        self.assertEqual(
            paths,
            ["scripts/foo.py", "../other/x.ts", "src/main.rs", "isolated.py"],
        )

    def test_heading_variants(self):
        for heading in (
            "## Files to modify",
            "### File to edit",
            "## Critical files",
            "# Files to change (scope)",
        ):
            close = "#" * len(heading.split()[0]) + " Out of scope"
            plan = f"{heading}\n- `pkg/app.py`\n\n{close}\n- `other.py`\n"
            paths = planscope.plan_paths(plan)
            self.assertEqual(paths, ["pkg/app.py"], f"Failed for heading: {heading}")

    def test_no_matching_section_returns_empty(self):
        plan = "# Plan\n\n## Steps\n1. Do something with `file.py`.\n"
        self.assertEqual(planscope.plan_paths(plan), [])

    def test_dedup_preserves_order(self):
        plan = """## Files to change
- `scripts/foo.py:10`
- `scripts/bar.py`
- `scripts/foo.py:50`
"""
        self.assertEqual(planscope.plan_paths(plan), ["scripts/foo.py", "scripts/bar.py"])


class TestSplitGrantable(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="along-ws-")
        self.sub = os.path.join(self.ws, "packages", "sub")
        self.other = os.path.join(self.ws, "packages", "other")
        os.makedirs(self.sub, exist_ok=True)
        os.makedirs(self.other, exist_ok=True)
        self.ext = tempfile.mkdtemp(prefix="along-ext-")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)
        shutil.rmtree(self.ext, ignore_errors=True)

    def test_split_grantable_classification(self):
        paths = [
            "src/local.ts",
            "../other/x.ts",
            os.path.join(self.ext, "ext.txt"),
            "/nonexistent/outside/system/file.txt" if sys.platform != "win32" else "C:\\outside\\file.txt",
        ]
        grant, rejected = planscope.split_grantable(
            paths,
            ctx=self.sub,
            workspace_root=self.ws,
            allowed_roots=[self.ext],
        )
        self.assertIn("../other/x.ts", grant)
        ext_rel = os.path.relpath(os.path.join(self.ext, "ext.txt"), self.sub).replace("\\", "/")
        self.assertIn(ext_rel, grant)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0], paths[3])


class TestEndToEndPlanGrantsWriteScope(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        self.env.start()
        self.ws = tempfile.mkdtemp(prefix="along-e2e-ws-")
        self.sub = os.path.join(self.ws, "packages", "sub")
        self.other = os.path.join(self.ws, "packages", "other")
        for ctx in (self.ws, self.sub, self.other):
            os.makedirs(os.path.join(ctx, ".along", "ISSUES"), exist_ok=True)
            os.makedirs(os.path.join(ctx, ".along", ".session"), exist_ok=True)
        os.makedirs(os.path.join(self.ws, ".git"), exist_ok=True)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.ws, ignore_errors=True)

    def test_subproject_plan_approval_grants_write_scope(self):
        slug = "sub-feature"
        issue_file = os.path.join(self.sub, ".along", "ISSUES", f"feat--{slug}.md")
        textio.write_text(
            issue_file,
            f"---\nprotocol: along\nprotocol_version: \"4.8.0\"\nslug: {slug}\n"
            f"type: feat\nstatus: in-progress\npriority: medium\n---\n# {slug}\n\n## Acceptance Criteria\n- [ ] Done\n",
        )

        plan_content = """# Plan

## Files to change
- `src/local.ts`
- `../other/x.ts`
- `C:/forbidden/outside.txt` if win32 else `/forbidden/outside.txt`
"""
        plan_path = os.path.join(self.sub, "draft-plan.md")
        textio.write_text(plan_path, plan_content)

        session.init_session(self.sub, slug)
        session.bind_session(self.sub, slug, key=KEY)

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"ALONG_SESSION_ID": SID, "ALONG_SESSION_RUNTIME": "claude"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = along_exec.handle_plan_command(self.sub, ["approve", slug, "--plan-file", plan_path])

        self.assertEqual(code, 0, out.getvalue() + err.getvalue())
        self.assertIn("-> Plan grants write scope: ../other/x.ts", out.getvalue())
        self.assertIn("[Notice] Not granted (outside workspace)", out.getvalue())

        fm, _body, _err = frontmatter.try_parse(textio.read_text(issue_file))
        self.assertIn("../other/x.ts", fm.get("write_scope", []))

        # Check write scope check in predicates
        covers = predicates._bound_scope_covers(self.ws, KEY, "packages/other/x.ts")
        self.assertTrue(covers, "Target packages/other/x.ts must be covered by bound write_scope")

        event = HookEvent(
            event_type=HookEventType.PRE_TOOL_USE,
            tool_name="write_to_file",
            tool_args={"TargetFile": os.path.join(self.other, "x.ts"), "CodeContent": "console.log(1);\n"},
            workspace_root=self.ws,
            runtime="claude",
            conversation_id=SID,
        )
        self.assertIsNone(predicates.check_active_issue(event, self.ws))
