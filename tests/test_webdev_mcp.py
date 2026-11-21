#!/usr/bin/env python3
"""tests.test_webdev_mcp - Tests for along-webdev stdio MCP server (REQ-13)."""

import json
import os
import shutil
import tempfile
import unittest

from alongkit.webdev import mcp_server


class TestWebdevMcpServer(unittest.TestCase):
    """MCP server protocol and tool dispatch tests (REQ-13)."""

    def setUp(self):
        self.temp_repo = tempfile.mkdtemp()
        self.sdir = os.path.join(self.temp_repo, ".along")
        os.makedirs(self.sdir, exist_ok=True)
        os.environ["ALONG_WEBDEV_HERMETIC"] = "1"

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)
        os.environ.pop("ALONG_WEBDEV_HERMETIC", None)

    def test_initialize_handshake(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        resp = mcp_server.handle_jsonrpc_request(self.temp_repo, req)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 1)
        res = resp["result"]
        self.assertEqual(res["serverInfo"]["name"], "along-webdev")
        self.assertEqual(res["protocolVersion"], "2024-11-05")
        self.assertIn("tools", res["capabilities"])

    def test_tools_list_manifest(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        resp = mcp_server.handle_jsonrpc_request(self.temp_repo, req)
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        expected = {
            "serve_up",
            "serve_status",
            "serve_down",
            "session_start",
            "session_step",
            "session_batch",
            "session_save",
            "session_status",
            "session_stop",
            "run",
            "checklist_compile",
            "screenshot",
            "eval",
        }
        self.assertTrue(expected.issubset(tool_names))

    def test_tools_call_session_lifecycle(self):
        # 1. Start session
        req_start = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "session_start",
                "arguments": {"issue": "mcp-test"},
            },
        }
        resp_start = mcp_server.handle_jsonrpc_request(self.temp_repo, req_start)
        self.assertFalse(resp_start["result"].get("isError", False))

        # 2. Check status
        req_stat = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "session_status",
                "arguments": {},
            },
        }
        resp_stat = mcp_server.handle_jsonrpc_request(self.temp_repo, req_stat)
        self.assertFalse(resp_stat["result"].get("isError", False))

        # 3. Stop session
        req_stop = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "session_stop",
                "arguments": {},
            },
        }
        resp_stop = mcp_server.handle_jsonrpc_request(self.temp_repo, req_stop)
        self.assertFalse(resp_stop["result"].get("isError", False))

    def test_tools_call_unknown_tool(self):
        req = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {},
            },
        }
        resp = mcp_server.handle_jsonrpc_request(self.temp_repo, req)
        self.assertTrue(resp["result"].get("isError", False))


if __name__ == "__main__":
    unittest.main()
