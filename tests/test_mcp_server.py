"""Test MCP server (JSON-RPC 2.0 stdio transport)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from humanarchive import mcp_server


class TestInitialize:
    def test_initialize(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        r = resp["result"]
        assert r["serverInfo"]["name"] == "humanarchive"
        assert "protocolVersion" in r
        assert "tools" in r["capabilities"]

    def test_unknown_method(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "does_not_exist", "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_notification_returns_none(self):
        """Notifications không cần response."""
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
        })
        assert resp is None


class TestToolsList:
    def test_tools_list_returns_expected_tools(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
        })
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        for required in ("describe", "capabilities", "rag_search",
                         "submit_dry_run", "submit", "graph_json",
                         "timeline_json", "audit_json"):
            assert required in names, f"Missing tool: {required}"

    def test_all_tools_have_schema(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
        })
        for t in resp["result"]["tools"]:
            assert "inputSchema" in t
            assert t["inputSchema"]["type"] == "object"
            assert "description" in t


class TestToolsCall:
    def test_call_describe(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "describe", "arguments": {"type_name": "memory"}},
        })
        assert "result" in resp
        content = json.loads(resp["result"]["content"][0]["text"])
        assert content["type"] == "memory"
        assert "schema" in content

    def test_call_capabilities(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "capabilities", "arguments": {}},
        })
        content = json.loads(resp["result"]["content"][0]["text"])
        assert "subcommands" in content
        assert "ethical_constraints" in content

    def test_call_unknown_tool(self):
        resp = mcp_server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "nonexistent", "arguments": {}},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_submit_refuses_without_confirm(self):
        """Safety: submit với confirm=False phải refuse."""
        memory = {"fake": "data"}
        result = mcp_server.tool_submit(memory, confirm=False)
        assert "error" in result
        assert "confirm=True required" in result["error"]

    def test_describe_invalid_type_returns_error(self):
        result = mcp_server.tool_describe("nonexistent_type")
        assert "error" in result
