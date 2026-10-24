#!/usr/bin/env python3
"""tests/test_daemon.py - Unit tests for VPS runner daemon and Telegram ingress loop."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

if not os.environ.get("ALONG_TEST_RUNNER"):
    raise SystemExit(
        "[Error] Tests must not be run directly or via standard test commands (unittest/pytest).\n"
        "To run tests with automatically resolved dependencies, use the official project entry point:\n"
        "    python .along/scripts/test.py"
    )

import hermetic
from alongkit import daemon, handoff, session, textio, worktree
from alongkit.commands.daemon import build_parser, format_status_text, handle_daemon_command


class MockTelegramClient(daemon.TelegramClient):
    """Hermetic mock for Telegram Bot API client."""

    def __init__(self, updates: list | None = None) -> None:
        super().__init__(bot_token="mock_token_12345")
        self.updates_queue = list(updates or [])
        self.sent_messages: list[dict] = []

    def get_updates(
        self,
        offset: int | None = None,
        limit: int = 100,
        timeout: int = 20,
    ) -> list[dict]:
        res = list(self.updates_queue)
        self.updates_queue.clear()
        return res

    def send_message(self, chat_id: int | str, text: str) -> bool:
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        return True


class TestDaemonLifecycle(unittest.TestCase):
    """Test PID management, state transitions, status reporting, and stop lifecycle."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-daemon-lifecycle-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_pid_file_management(self) -> None:
        self.assertIsNone(daemon.read_pid(self.repo))

        daemon.write_pid(self.repo, 98765)
        self.assertEqual(daemon.read_pid(self.repo), 98765)
        self.assertTrue(os.path.isfile(daemon.get_pid_file(self.repo)))

        daemon.remove_pid(self.repo)
        self.assertIsNone(daemon.read_pid(self.repo))

        # Test corrupt PID file
        pid_file = daemon.get_pid_file(self.repo)
        textio.write_text(pid_file, "not-a-number\n")
        self.assertIsNone(daemon.read_pid(self.repo))

    def test_daemon_status_reporting(self) -> None:
        # 1. Stopped status
        st_stopped = daemon.get_daemon_status(self.repo)
        self.assertFalse(st_stopped["running"])
        self.assertEqual(st_stopped["status"], "stopped")
        self.assertIsNone(st_stopped["pid"])

        # 2. Running status: alive and the recorded identity matches
        daemon.write_pid(self.repo, 54321, token="start-54321")
        daemon.save_daemon_state(self.repo, {
            "pid": 54321,
            "status": "idle",
            "started_at": "2026-10-23T10:00:00Z",
            "current_task": None,
            "worktree": True,
            "poll_interval": 3.0,
        })

        with patch("alongkit.daemon.is_pid_alive", return_value=True), \
             patch("alongkit.daemon.process_identity", return_value="start-54321"):
            st_running = daemon.get_daemon_status(self.repo)
            self.assertTrue(st_running["running"])
            self.assertEqual(st_running["pid"], 54321)
            self.assertEqual(st_running["status"], "idle")
            self.assertTrue(st_running["worktree"])
            self.assertEqual(st_running["poll_interval"], 3.0)
            self.assertIsNotNone(st_running["uptime_seconds"])

        # 3. Stale PID file (process died)
        with patch("alongkit.daemon.is_pid_alive", return_value=False):
            st_stale = daemon.get_daemon_status(self.repo)
            self.assertFalse(st_stale["running"])
            self.assertTrue(st_stale.get("stale"))
            self.assertEqual(st_stale["status"], "stale-pid")

    def test_stop_daemon_lifecycle(self) -> None:
        # When stopped, stop_daemon succeeds idempotently
        ok, msg = daemon.stop_daemon(self.repo)
        self.assertTrue(ok)
        self.assertIn("not running", msg)

        # When stale PID, stop_daemon cleans up
        daemon.write_pid(self.repo, 11223)
        with patch("alongkit.daemon.is_pid_alive", return_value=False):
            ok, msg = daemon.stop_daemon(self.repo)
            self.assertTrue(ok)
            self.assertIn("Cleaned up stale daemon PID", msg)
            self.assertIsNone(daemon.read_pid(self.repo))

        # When running process (identity verified)
        daemon.write_pid(self.repo, 99999, token="start-99999")
        with patch("alongkit.daemon.is_pid_alive", return_value=True), \
             patch("alongkit.daemon.process_identity", return_value="start-99999"), \
             patch("alongkit.daemon.terminate_pid", return_value=True):
            ok, msg = daemon.stop_daemon(self.repo)
            self.assertTrue(ok)
            self.assertIn("stopped successfully", msg)
            self.assertIsNone(daemon.read_pid(self.repo))

    def test_daemon_logs_appending_and_tailing(self) -> None:
        daemon.append_daemon_log(self.repo, "First test entry", level="INFO")
        daemon.append_daemon_log(self.repo, "Second test entry", level="WARNING")

        captured: list[str] = []
        daemon.tail_daemon_logs(self.repo, lines=10, follow=False, output_fn=captured.append)
        self.assertEqual(len(captured), 2)
        self.assertIn("First test entry", captured[0])
        self.assertIn("[INFO]", captured[0])
        self.assertIn("Second test entry", captured[1])
        self.assertIn("[WARNING]", captured[1])


class TestTelegramIngress(unittest.TestCase):
    """Test command parsing, authorization enforcement, and orchestrator dispatch."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-daemon-telegram-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_parse_telegram_command(self) -> None:
        self.assertEqual(daemon.parse_telegram_command("/task feat--auth"), ("task", "feat--auth"))
        self.assertEqual(daemon.parse_telegram_command("/run bug--fix-1"), ("run", "bug--fix-1"))
        self.assertEqual(daemon.parse_telegram_command("/task@along_bot my-task"), ("task", "my-task"))
        self.assertEqual(daemon.parse_telegram_command("/status"), ("status", None))
        self.assertEqual(daemon.parse_telegram_command("/help"), ("help", None))
        self.assertEqual(daemon.parse_telegram_command("Just regular message"), (None, None))
        self.assertEqual(daemon.parse_telegram_command(""), (None, None))

    def test_is_sender_authorized(self) -> None:
        allowed = ["12345", "67890"]

        # Valid chat_id or user_id
        self.assertTrue(daemon.is_sender_authorized(allowed, chat_id=12345, user_id=99999))
        self.assertTrue(daemon.is_sender_authorized(allowed, chat_id=88888, user_id=67890))
        self.assertTrue(daemon.is_sender_authorized(allowed, chat_id="12345", user_id=None))

        # Unauthorized
        self.assertFalse(daemon.is_sender_authorized(allowed, chat_id=11111, user_id=22222))
        self.assertFalse(daemon.is_sender_authorized([], chat_id=12345, user_id=12345))
        self.assertFalse(daemon.is_sender_authorized(None, chat_id=12345, user_id=12345))

    def test_unauthorized_update_rejected(self) -> None:
        mock_client = MockTelegramClient()
        mock_orch = MagicMock()

        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_client=mock_client,
            orchestrator_fn=mock_orch,
            log_to_stdout=False,
        )

        # Update from unauthorized chat 999
        unauth_update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 999},
                "from": {"id": 999},
                "text": "/task unauthorized-task",
            },
        }

        d.process_update(unauth_update)
        mock_orch.assert_not_called()
        self.assertEqual(len(mock_client.sent_messages), 1)
        self.assertIn("Access denied", mock_client.sent_messages[0]["text"])

    def test_authorized_command_dispatches_to_orchestrator(self) -> None:
        mock_client = MockTelegramClient()
        mock_orch = MagicMock(return_value={"status": "completed"})

        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_client=mock_client,
            orchestrator_fn=mock_orch,
            log_to_stdout=False,
        )

        auth_update = {
            "update_id": 2,
            "message": {
                "chat": {"id": 100},
                "from": {"id": 100},
                "text": "/task task--fixture-sample-task",
            },
        }

        d.process_update(auth_update)
        mock_orch.assert_called_once()
        call_kwargs = mock_orch.call_args[1]
        self.assertEqual(call_kwargs["slug"], "task--fixture-sample-task")

        # Check notification sent back to chat 100
        sent_texts = [m["text"] for m in mock_client.sent_messages]
        self.assertTrue(any("Starting execution" in t for t in sent_texts))
        self.assertTrue(any("completed successfully" in t for t in sent_texts))
        self.assertIsNone(d.current_task)

    def test_status_command_handling(self) -> None:
        mock_client = MockTelegramClient()
        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_client=mock_client,
            log_to_stdout=False,
        )

        status_update = {
            "update_id": 3,
            "message": {
                "chat": {"id": 100},
                "from": {"id": 100},
                "text": "/status",
            },
        }

        d.process_update(status_update)
        self.assertEqual(len(mock_client.sent_messages), 1)
        self.assertIn("[Along Runner Status]", mock_client.sent_messages[0]["text"])


class TestConcurrencyAndClaims(unittest.TestCase):
    """Test single concurrency enforcement and state.json claim integration."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-daemon-claims-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_single_concurrency_busy_rejection(self) -> None:
        mock_client = MockTelegramClient()
        mock_orch = MagicMock()

        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_client=mock_client,
            orchestrator_fn=mock_orch,
            log_to_stdout=False,
        )
        d.current_task = "existing-active-task"

        d.handle_task_command(chat_id=100, slug="new-task")
        mock_orch.assert_not_called()
        self.assertEqual(len(mock_client.sent_messages), 1)
        self.assertIn("Runner busy", mock_client.sent_messages[0]["text"])
        self.assertIn("existing-active-task", mock_client.sent_messages[0]["text"])

    def test_active_claim_rejection_from_state_json(self) -> None:
        mock_client = MockTelegramClient()
        mock_orch = MagicMock()

        slug = "task--fixture-sample-task"
        # Initialize session state first
        session.init_session(self.repo, slug)
        # Acquire claim by another runner
        claimed = handoff.acquire_claim(
            self.repo,
            slug=slug,
            run_id="external-runner-999",
            runtime="supervisor",
            ttl_seconds=3600,
        )
        self.assertTrue(claimed)

        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_client=mock_client,
            orchestrator_fn=mock_orch,
            dry_run=False,
            log_to_stdout=False,
        )

        d.handle_task_command(chat_id=100, slug=slug)
        mock_orch.assert_not_called()
        self.assertEqual(len(mock_client.sent_messages), 1)
        self.assertIn("currently claimed in state.json", mock_client.sent_messages[0]["text"])
        self.assertIn("external-runner-999", mock_client.sent_messages[0]["text"])

    def test_error_handling_resets_busy_state(self) -> None:
        mock_client = MockTelegramClient()
        mock_orch = MagicMock(side_effect=RuntimeError("Simulated orchestration boom"))

        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_client=mock_client,
            orchestrator_fn=mock_orch,
            log_to_stdout=False,
        )

        slug = "task--fixture-sample-task"
        d.handle_task_command(chat_id=100, slug=slug)
        self.assertIsNone(d.current_task)
        st = daemon.load_daemon_state(self.repo)
        self.assertEqual(st.get("status"), "idle")
        self.assertIsNone(st.get("current_task"))

        # Error notification delivered to chat
        sent_texts = [m["text"] for m in mock_client.sent_messages]
        self.assertTrue(any("Error during execution" in t for t in sent_texts))


class TestDaemonCli(unittest.TestCase):
    """Test CLI argument parsing, status text formatting, and routing."""

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-daemon-cli-")

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_parser_construction_and_subcommands(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["start", "--poll-interval", "2.5", "--worktree", "--dry-run", "--foreground"])
        self.assertEqual(args.subcmd, "start")
        self.assertEqual(args.poll_interval, 2.5)
        self.assertTrue(args.worktree)
        self.assertTrue(args.dry_run)
        self.assertTrue(args.foreground)

        args_status = parser.parse_args(["status", "--json"])
        self.assertEqual(args_status.subcmd, "status")
        self.assertTrue(args_status.json)

        args_logs = parser.parse_args(["logs", "-f", "--tail", "100"])
        self.assertEqual(args_logs.subcmd, "logs")
        self.assertTrue(args_logs.follow)
        self.assertEqual(args_logs.tail, 100)

    def test_format_status_text(self) -> None:
        sample_status = {
            "running": True,
            "pid": 4321,
            "status": "busy",
            "uptime_seconds": 3665,
            "current_task": "feat--auth-v2",
            "worktree": True,
            "poll_interval": 5.0,
            "last_poll_at": "2026-10-23T11:00:00Z",
        }
        text = format_status_text(sample_status)
        self.assertIn("Running:             Yes", text)
        self.assertIn("PID:                 4321", text)
        self.assertIn("Process State:       busy", text)
        self.assertIn("1h 1m 5s", text)
        self.assertIn("feat--auth-v2", text)
        self.assertIn("Worktree Isolation:  Enabled", text)

    def test_handle_daemon_command_help_and_status(self) -> None:
        # Help returns 0
        self.assertEqual(handle_daemon_command(self.repo, ["--help"]), 0)
        self.assertEqual(handle_daemon_command(self.repo, []), 0)

        # Status returns 1 when daemon is stopped
        ret = handle_daemon_command(self.repo, ["status", "--json"])
        self.assertEqual(ret, 1)


class SequencedTelegramClient(MockTelegramClient):
    """Hands out one queued item per poll: a list of updates, an exception to raise, or a callable."""

    def __init__(self, batches: list, idle=None) -> None:
        super().__init__()
        self.batches = list(batches)
        self.idle = idle
        self.offsets: list = []

    def get_updates(self, offset=None, limit=100, timeout=20):
        self.offsets.append(offset)
        if self.batches:
            item = self.batches.pop(0)
            if isinstance(item, BaseException):
                raise item
            if callable(item):
                item()
                return []
            return item
        if self.idle:
            self.idle()
        time.sleep(0.01)
        return []


def _update(update_id: int, text: str, chat: int = 100, date=None) -> dict:
    msg = {"chat": {"id": chat}, "from": {"id": chat}, "text": text}
    if date is not None:
        msg["date"] = date
    return {"update_id": update_id, "message": msg}


class TestDaemonLifecycleSafety(unittest.TestCase):
    """[bug--runner-daemon-lifecycle-safety]: no lost work, no replays, no foreign kills."""

    SLUG = "task--fixture-sample-task"

    def setUp(self) -> None:
        self.repo = hermetic.make_repo_fixture(prefix="along-test-daemon-safety-")

    def tearDown(self) -> None:
        daemon.remove_pid(self.repo)
        shutil.rmtree(self.repo, ignore_errors=True)

    def _daemon(self, client, orch=None, **kwargs) -> daemon.RunnerDaemon:
        d = daemon.RunnerDaemon(
            repo_root=self.repo,
            allowed_chats=["100"],
            telegram_token="test-token",
            telegram_client=client,
            orchestrator_fn=orch or MagicMock(return_value={"status": "completed"}),
            log_to_stdout=False,
            **kwargs,
        )
        d._setup_signals = lambda: None  # keep the test process's own handlers
        return d

    def _texts(self, client) -> list:
        return [m["text"] for m in client.sent_messages]

    def test_worktree_run_keeps_the_branch_and_names_it(self) -> None:
        wt = worktree.WorktreeInfo(slug=self.SLUG, path=self.repo, branch=f"along/{self.SLUG}", created_at="now")
        client = MockTelegramClient()
        d = self._daemon(client, use_worktree=True)
        with patch.object(daemon.worktree, "create_worktree", return_value=wt), \
             patch.object(daemon.worktree, "remove_worktree") as remove, \
             patch.object(daemon.proc, "git", return_value=MagicMock(ok=True, stdout="")):
            d.handle_task_command(100, self.SLUG)
        remove.assert_called_once()
        self.assertFalse(remove.call_args.kwargs.get("delete_branch", True),
                         "Teardown must keep the branch that holds the run's commits")
        self.assertTrue(any(f"along/{self.SLUG}" in t for t in self._texts(client)))

    def test_dirty_worktree_is_kept(self) -> None:
        wt = worktree.WorktreeInfo(slug=self.SLUG, path=self.repo, branch=f"along/{self.SLUG}", created_at="now")
        client = MockTelegramClient()
        d = self._daemon(client, use_worktree=True)
        with patch.object(daemon.worktree, "create_worktree", return_value=wt), \
             patch.object(daemon.worktree, "remove_worktree") as remove, \
             patch.object(daemon.proc, "git", return_value=MagicMock(ok=True, stdout=" M src/app.py\n")):
            d.handle_task_command(100, self.SLUG)
        remove.assert_not_called()
        self.assertTrue(any("kept" in t and self.repo in t for t in self._texts(client)))

    def test_offset_is_persisted_and_used_after_restart(self) -> None:
        first = SequencedTelegramClient([[_update(5, f"/task {self.SLUG}")]])
        d = self._daemon(first)
        first.idle = d.request_stop
        self.assertEqual(d.run(), 0)
        self.assertEqual(daemon.load_daemon_state(self.repo).get("telegram_offset"), 5)

        second = SequencedTelegramClient([])
        d2 = self._daemon(second)
        second.idle = d2.request_stop
        d2.run()
        self.assertEqual(second.offsets[0], 6, "A restarted daemon must not be handed update 5 again")

    def test_stale_command_is_ignored(self) -> None:
        client = MockTelegramClient()
        orch = MagicMock(return_value={"status": "completed"})
        d = self._daemon(client, orch)
        d.process_update(_update(7, f"/task {self.SLUG}", date=int(time.time()) - 3600))
        orch.assert_not_called()
        self.assertTrue(any("Ignored" in t for t in self._texts(client)))

    def test_stop_never_signals_an_unverified_pid(self) -> None:
        # This test process is alive, so its PID stands in for a reused one.
        for content in (f"{os.getpid()}\n", f"{os.getpid()}\nnot-the-recorded-start\n"):
            with self.subTest(content=content):
                textio.write_text(daemon.get_pid_file(self.repo), content)
                self.assertEqual(daemon.get_daemon_status(self.repo)["status"], "stale-pid")
                with patch("alongkit.daemon.terminate_pid") as term:
                    ok, msg = daemon.stop_daemon(self.repo)
                term.assert_not_called()
                self.assertTrue(ok)
                self.assertIsNone(daemon.read_pid(self.repo))

    def test_pid_file_is_exclusive(self) -> None:
        self.assertTrue(daemon.acquire_pid_file(self.repo))
        self.assertFalse(daemon.acquire_pid_file(self.repo), "A live daemon's PID file must not be replaced")
        self.assertEqual(daemon.read_pid(self.repo), os.getpid())
        daemon.remove_pid(self.repo)
        daemon.write_pid(self.repo, 999999, token="gone")
        with patch("alongkit.daemon.is_pid_alive", return_value=False):
            self.assertTrue(daemon.acquire_pid_file(self.repo), "A stale PID file is taken over")
        self.assertEqual(daemon.read_pid(self.repo), os.getpid())

    def test_status_is_answered_while_a_task_runs(self) -> None:
        status_sent = threading.Event()
        order = []

        class Client(SequencedTelegramClient):
            def send_message(self, chat_id, text):
                super().send_message(chat_id, text)
                if "[Along Runner Status]" in text:
                    status_sent.set()
                return True

        def orch(**kwargs):
            order.append(("task-finished", status_sent.wait(3)))
            return {"status": "completed"}

        client = Client([[_update(1, f"/task {self.SLUG}")], [_update(2, "/status")]])
        d = self._daemon(client, orch)
        client.idle = lambda: d.request_stop() if d.current_task is None and order else None
        d.run()
        self.assertEqual(order, [("task-finished", True)], "/status must be answered during the task")

    def test_poll_errors_back_off_and_a_bad_token_exits_78(self) -> None:
        sleeps = []
        client = SequencedTelegramClient([RuntimeError("boom")] * 3)
        d = self._daemon(client, poll_interval=5)
        client.idle = d.request_stop
        d._sleep = sleeps.append
        with patch("alongkit.daemon.time.sleep", side_effect=sleeps.append):
            d.run()
        self.assertEqual(sleeps[:3], [5, 10, 20])

        auth = SequencedTelegramClient([daemon.TelegramAuthError("HTTP 401")])
        d2 = self._daemon(auth)
        self.assertEqual(d2.run(), daemon.EXIT_CONFIG)

    def test_background_start_uses_the_engine_script_and_reports_a_failed_spawn(self) -> None:
        import itertools
        fake = os.path.join(self.repo, "scripts", "along_daemon.py")
        textio.write_text(fake, "raise SystemExit(0)\n")
        child = MagicMock(pid=4242)
        child.poll.return_value = 2
        with patch("alongkit.daemon.subprocess.Popen", return_value=child) as popen, \
             patch("alongkit.daemon.get_daemon_status", return_value={"running": False}), \
             patch("alongkit.daemon.time.time", side_effect=itertools.count(0, 10)), \
             patch("alongkit.daemon.time.sleep"):
            rc = daemon.start_daemon(self.repo)
        self.assertEqual(rc, 1, "A child that exits during startup is a failed start")
        cmd = popen.call_args[0][0]
        self.assertNotEqual(os.path.normcase(cmd[1]), os.path.normcase(fake))

    def test_log_rotates_above_the_size_limit(self) -> None:
        with patch("alongkit.daemon.LOG_MAX_BYTES", 100):
            daemon.append_daemon_log(self.repo, "x" * 200)
            daemon.append_daemon_log(self.repo, "after rotation")
        self.assertTrue(os.path.isfile(daemon.get_log_file(self.repo) + ".1"))
        self.assertIn("after rotation", textio.read_text(daemon.get_log_file(self.repo)))


if __name__ == "__main__":
    unittest.main()
