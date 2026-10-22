#!/usr/bin/env python3
"""
tests/test_handoff_entities.py - Unit tests for cross-runtime handoff entities and along brief.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import io
import json
import os
import shutil
import sys
import unittest

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import hermetic
from alongkit import frontmatter, handoff, proc, repo, session, textio
from alongkit.commands.brief import handle_brief_command


class TestRunRecords(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-handoff-runs-")
        self.slug = "sample-task"
        session.init_session(self.repo, self.slug, title="Sample Task", total_steps=3)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_create_and_load_run_record(self):
        run_id = "run-001"
        rec = handoff.create_run_record(
            self.repo,
            self.slug,
            run_id=run_id,
            role="implementer",
            runtime="claude-code",
            model="claude-3-7-sonnet",
            step=1,
        )
        self.assertEqual(rec["run_id"], run_id)
        self.assertEqual(rec["role"], "implementer")
        self.assertEqual(rec["runtime"], "claude-code")
        self.assertEqual(rec["outcome"], "in-progress")

        loaded = handoff.load_run_record(self.repo, self.slug, run_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["run_id"], run_id)
        self.assertEqual(loaded["model"], "claude-3-7-sonnet")
        self.assertEqual(loaded["step"], 1)

    def test_finish_run_record(self):
        run_id = "run-002"
        handoff.create_run_record(self.repo, self.slug, run_id, "reviewer", "antigravity", step=1)

        finished = handoff.finish_run_record(
            self.repo,
            self.slug,
            run_id=run_id,
            outcome="done",
            exit_code=0,
            changed_files=["scripts/alongkit/handoff.py"],
            usage={"input_tokens": 1000, "output_tokens": 200},
            handoff_note="handoff.md",
        )
        self.assertEqual(finished["outcome"], "done")
        self.assertEqual(finished["exit_code"], 0)
        self.assertEqual(finished["changed_files"], ["scripts/alongkit/handoff.py"])
        self.assertEqual(finished["usage"]["input_tokens"], 1000)
        self.assertIsNotNone(finished["end"])

        # Re-loading verifies persistence
        loaded = handoff.load_run_record(self.repo, self.slug, run_id)
        self.assertEqual(loaded["outcome"], "done")
        self.assertEqual(loaded["handoff_note"], "handoff.md")

    def test_list_run_records(self):
        handoff.create_run_record(self.repo, self.slug, "run-1", "architect", "codex", start="2026-10-23T01:00:00Z")
        handoff.create_run_record(self.repo, self.slug, "run-2", "implementer", "claude-code", start="2026-10-23T01:10:00Z")

        records = handoff.list_run_records(self.repo, self.slug)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["run_id"], "run-1")
        self.assertEqual(records[1]["run_id"], "run-2")

    def test_invalid_outcome_raises(self):
        run_id = "run-err"
        handoff.create_run_record(self.repo, self.slug, run_id, "implementer", "claude-code")
        with self.assertRaises(ValueError):
            handoff.finish_run_record(self.repo, self.slug, run_id, outcome="invalid-outcome")


class TestReviewVerdicts(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-handoff-reviews-")
        self.slug = "review-task"
        session.init_session(self.repo, self.slug, title="Review Task", total_steps=2)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_validate_review_verdict_rules(self):
        # Empty defects with pass verdict is valid
        valid, errs = handoff.validate_review_verdict("pass", [])
        self.assertTrue(valid)
        self.assertEqual(errs, [])

        # Nit defects with pass verdict is valid
        valid, errs = handoff.validate_review_verdict("pass", [{"severity": "nit", "description": "Minor typo"}])
        self.assertTrue(valid)

        # Blocking defect with pass verdict is invalid
        valid, errs = handoff.validate_review_verdict("pass", [{"severity": "blocking", "description": "Crash on empty input"}])
        self.assertFalse(valid)
        self.assertTrue(any("cannot be 'pass'" in e for e in errs))

        # Important defect with pass verdict is invalid
        valid, errs = handoff.validate_review_verdict("pass", [{"severity": "important", "description": "Missing test"}])
        self.assertFalse(valid)

        # Blocking defect with fail verdict is valid
        valid, errs = handoff.validate_review_verdict("fail", [{"severity": "blocking", "description": "Crash"}])
        self.assertTrue(valid)

        # Fail verdict with only nit defects is invalid
        valid, errs = handoff.validate_review_verdict("fail", [{"severity": "nit", "description": "Typo"}])
        self.assertFalse(valid)
        self.assertTrue(any("cannot be 'fail'" in e for e in errs))

        # Invalid verdict string
        valid, errs = handoff.validate_review_verdict("maybe", [])
        self.assertFalse(valid)

    def test_write_and_load_review_verdict(self):
        defects = [
            {"severity": "blocking", "description": "Unhandled exception in claim renewal", "file": "claim.py", "line": 42},
            {"severity": "nit", "description": "Add docstring example"},
        ]
        path = handoff.write_review_verdict(
            self.repo,
            self.slug,
            step=1,
            verdict="fail",
            defects=defects,
            body="Review details for Step 1 implementation.",
        )
        self.assertTrue(os.path.isfile(path))

        loaded = handoff.load_review_verdict(self.repo, self.slug, step=1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["step"], 1)
        self.assertEqual(loaded["verdict"], "fail")
        self.assertEqual(len(loaded["defects"]), 2)
        self.assertEqual(loaded["defects"][0]["severity"], "blocking")
        self.assertIn("Review details for Step 1", loaded["body"])

    def test_write_invalid_verdict_raises(self):
        with self.assertRaises(ValueError):
            handoff.write_review_verdict(
                self.repo,
                self.slug,
                step=1,
                verdict="pass",
                defects=[{"severity": "blocking", "description": "Broken"}],
            )


class TestQuestionLifecycle(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-handoff-questions-")
        self.slug = "question-task"
        session.init_session(self.repo, self.slug, title="Question Task", total_steps=2)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_question_lifecycle(self):
        self.assertFalse(handoff.has_open_questions(self.repo, self.slug))

        # 1. Create question
        q = handoff.create_question(
            self.repo,
            self.slug,
            question="Which database adapter should be used?",
            options=["sqlite", "postgres", "memory"],
            recommended="memory",
            body="Memory adapter is faster for tests.",
            qid="q-1",
        )
        self.assertEqual(q["id"], "q-1")
        self.assertEqual(q["status"], "open")
        self.assertEqual(q["recommended"], "memory")
        self.assertTrue(handoff.has_open_questions(self.repo, self.slug))

        # 2. Load question
        loaded = handoff.load_question(self.repo, self.slug, "q-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["question"], "Which database adapter should be used?")
        self.assertEqual(loaded["options"], ["sqlite", "postgres", "memory"])
        self.assertIn("Memory adapter is faster", loaded["body"])

        # 3. List questions (open only)
        open_list = handoff.list_questions(self.repo, self.slug, status="open")
        self.assertEqual(len(open_list), 1)

        # 4. Answer question
        answered = handoff.answer_question(
            self.repo,
            self.slug,
            qid="q-1",
            answer="memory",
            answered_by="operator-telegram",
        )
        self.assertEqual(answered["status"], "answered")
        self.assertEqual(answered["answer"], "memory")
        self.assertEqual(answered["answered_by"], "operator-telegram")
        self.assertIsNotNone(answered["answered_at"])

        # 5. Verify no open questions remain
        self.assertFalse(handoff.has_open_questions(self.repo, self.slug))
        answered_list = handoff.list_questions(self.repo, self.slug, status="answered")
        self.assertEqual(len(answered_list), 1)


class TestClaimManagement(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-handoff-claims-")
        self.slug = "claim-task"
        session.init_session(self.repo, self.slug, title="Claim Task", total_steps=2)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_acquire_and_release_claim(self):
        self.assertFalse(handoff.is_claim_active(self.repo, self.slug))

        # Acquire claim
        ok = handoff.acquire_claim(self.repo, self.slug, run_id="run-a", runtime="claude-code", ttl_seconds=600)
        self.assertTrue(ok)
        self.assertTrue(handoff.is_claim_active(self.repo, self.slug))

        claim = handoff.get_claim(self.repo, self.slug)
        self.assertIsNotNone(claim)
        self.assertEqual(claim["run_id"], "run-a")
        self.assertEqual(claim["runtime"], "claude-code")

        # Collision prevention: second run cannot acquire active claim
        ok_collision = handoff.acquire_claim(self.repo, self.slug, run_id="run-b", runtime="codex")
        self.assertFalse(ok_collision)

        # Same run can renew claim
        ok_renew = handoff.acquire_claim(self.repo, self.slug, run_id="run-a", runtime="claude-code", ttl_seconds=1200)
        self.assertTrue(ok_renew)

        # Release claim
        released = handoff.release_claim(self.repo, self.slug, run_id="run-a")
        self.assertTrue(released)
        self.assertFalse(handoff.is_claim_active(self.repo, self.slug))

    def test_expired_claim_takeover(self):
        # Acquire claim with expired timestamp
        handoff.acquire_claim(self.repo, self.slug, run_id="run-old", runtime="claude-code")

        # Manually backdate expiration in state.json
        st = session.load_state(self.repo, self.slug)
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st["claimed_by"]["expires_at"] = past_time
        session.save_state(self.repo, self.slug, st)

        # Claim is now expired
        self.assertFalse(handoff.is_claim_active(self.repo, self.slug))

        # New run can take over expired claim
        ok_takeover = handoff.acquire_claim(self.repo, self.slug, run_id="run-new", runtime="antigravity", ttl_seconds=600)
        self.assertTrue(ok_takeover)

        claim = handoff.get_claim(self.repo, self.slug)
        self.assertEqual(claim["run_id"], "run-new")
        self.assertEqual(claim["runtime"], "antigravity")

    def test_release_other_run_claim_requires_force(self):
        handoff.acquire_claim(self.repo, self.slug, run_id="run-holder", runtime="opencode", ttl_seconds=600)

        # Non-holder cannot release
        released = handoff.release_claim(self.repo, self.slug, run_id="run-intruder")
        self.assertFalse(released)
        self.assertTrue(handoff.is_claim_active(self.repo, self.slug))

        # Forced release succeeds
        released_force = handoff.release_claim(self.repo, self.slug, run_id="run-intruder", force=True)
        self.assertTrue(released_force)
        self.assertFalse(handoff.is_claim_active(self.repo, self.slug))


class TestHandoffNote(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-handoff-note-")
        self.slug = "note-task"
        session.init_session(self.repo, self.slug, title="Note Task", total_steps=2)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_write_and_read_handoff_note(self):
        self.assertIsNone(handoff.read_handoff_note(self.repo, self.slug))

        path = handoff.write_handoff_note(
            self.repo,
            self.slug,
            done="Implemented claim acquisition and verification tests.",
            remaining="Wire CLI brief generator and update documentation.",
            traps="Remember to use UTC timezone in timestamps.",
        )
        self.assertTrue(os.path.isfile(path))

        content = handoff.read_handoff_note(self.repo, self.slug)
        self.assertIsNotNone(content)
        self.assertIn("## What Was Done", content)
        self.assertIn("Implemented claim acquisition", content)
        self.assertIn("## What Is Left", content)
        self.assertIn("## Traps & Watch-outs", content)


class TestAlongBrief(unittest.TestCase):

    def setUp(self):
        self.repo = hermetic.make_repo_fixture(prefix="along-brief-test-")
        self.slug = "brief-task"

        # Create issue file with goal, REQ-N, and acceptance criteria
        issues_dir = os.path.join(repo.state_dir(self.repo), "ISSUES")
        os.makedirs(issues_dir, exist_ok=True)
        self.issue_file = os.path.join(issues_dir, f"feat--{self.slug}.md")
        issue_content = """---
protocol: along
protocol_version: "4.4.16"
slug: brief-task
type: feat
status: in-progress
priority: high
created: 2026-10-23
updated: 2026-10-23
agent: antigravity
tags: [handoff, test]
---

# Test Brief Task Title

## Problem
Multi-vendor runtimes require compact, deterministic context payloads to execute steps.

## Requirements
- REQ-1: The brief generator MUST extract the issue goal and acceptance criteria.
- REQ-2: The brief generator MUST extract open defects from recent review verdicts.

## Acceptance Criteria
- [ ] Implement deterministic handoff brief generation.
- [ ] Enforce size limits via --max-bytes.
"""
        textio.write_text(self.issue_file, issue_content, newline="\n")

        # Initialize session blackboard
        session.init_session(self.repo, self.slug, title="Test Brief Task Title", total_steps=2)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_brief_generation_roles(self):
        # Roles: scout, architect, implementer, reviewer
        for role in ("scout", "architect", "implementer", "reviewer"):
            payload = handoff.generate_brief(self.repo, self.slug, role=role)
            self.assertIn(f"# Handoff Brief: {role.capitalize()}", payload)
            self.assertIn("## Issue Goal", payload)
            self.assertIn("Multi-vendor runtimes require compact", payload)
            self.assertIn("## Requirements", payload)
            self.assertIn("REQ-1:", payload)
            self.assertIn("## Acceptance Criteria", payload)
            self.assertIn("- [ ] Implement deterministic handoff brief generation.", payload)
            self.assertIn("## Current Step", payload)

    def test_reviewer_role_includes_review_policy(self):
        payload_no_custom = handoff.generate_brief(self.repo, self.slug, role="reviewer")
        self.assertIn("## Review Policy", payload_no_custom)
        self.assertIn("Repository Review Policy:", payload_no_custom)

        # Create custom root REVIEW.md
        custom_review_path = os.path.join(self.repo, "REVIEW.md")
        textio.write_text(custom_review_path, "Custom repo review rules: flag any missing type annotations.\n")

        payload_custom = handoff.generate_brief(self.repo, self.slug, role="reviewer")
        self.assertIn("Custom repo review rules: flag any missing type annotations.", payload_custom)

        # Non-reviewer roles do not get Review Policy section
        payload_impl = handoff.generate_brief(self.repo, self.slug, role="implementer")
        self.assertNotIn("## Review Policy", payload_impl)

    def test_brief_includes_defects_and_questions(self):
        # Add open defects in review
        handoff.write_review_verdict(
            self.repo,
            self.slug,
            step=1,
            verdict="fail",
            defects=[{"severity": "blocking", "description": "Crash on empty string"}],
            body="Review notes.",
        )

        # Add answered question
        handoff.create_question(self.repo, self.slug, question="Use JSON format?", qid="q-1")
        handoff.answer_question(self.repo, self.slug, qid="q-1", answer="Yes, indent=2", answered_by="human")

        # Add handoff note
        handoff.write_handoff_note(self.repo, self.slug, done="Wrote parser", remaining="Add tests")

        payload = handoff.generate_brief(self.repo, self.slug, role="implementer")
        self.assertIn("Crash on empty string", payload)
        self.assertIn("Use JSON format?", payload)
        self.assertIn("Yes, indent=2", payload)
        self.assertIn("Wrote parser", payload)

    def test_brief_determinism(self):
        payload_1 = handoff.generate_brief(self.repo, self.slug, role="implementer")
        payload_2 = handoff.generate_brief(self.repo, self.slug, role="implementer")
        self.assertEqual(payload_1, payload_2)

    def test_brief_size_bounding(self):
        # Generate with very small max_bytes
        small_limit = 400
        payload = handoff.generate_brief(self.repo, self.slug, role="implementer", max_bytes=small_limit)
        byte_len = len(payload.encode("utf-8"))
        self.assertLessEqual(byte_len, small_limit)
        self.assertIn("Brief payload truncated to stay within context budget", payload)

    def test_handle_brief_command_cli(self):
        # Plain text output
        buf = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = buf
            ret = handle_brief_command(self.repo, [self.slug, "--role", "implementer"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        self.assertIn("Handoff Brief: Implementer", buf.getvalue())

        # JSON output
        buf_json = io.StringIO()
        try:
            sys.stdout = buf_json
            ret = handle_brief_command(self.repo, [self.slug, "--role", "reviewer", "--json"])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        data = json.loads(buf_json.getvalue())
        self.assertEqual(data["slug"], self.slug)
        self.assertEqual(data["role"], "reviewer")
        self.assertIn("Handoff Brief: Reviewer", data["payload"])


if __name__ == "__main__":
    unittest.main()
