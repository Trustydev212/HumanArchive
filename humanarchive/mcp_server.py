"""MCP (Model Context Protocol) server wrapping the HumanArchive CLI.

Agents không có Bash tool có thể dùng MCP protocol thay vì subprocess.
Server wrapper này expose từng CLI subcommand thành MCP tool call.

Sử dụng:
    pip install "humanarchive[mcp]"
    humanarchive mcp-server             # stdio transport (default)
    humanarchive mcp-server --http 8765 # SSE transport

Cho Claude Desktop:
    ~/.claude_desktop_config.json
    {
      "mcpServers": {
        "humanarchive": {
          "command": "humanarchive",
          "args": ["mcp-server"]
        }
      }
    }

Cho các MCP client khác: gọi stdio với JSON-RPC 2.0.

Tools được expose:
    * describe(type_name)         → JSON Schema
    * capabilities()              → CLI surface
    * rag_search(query, k=5)      → RAG search role-balanced
    * submit_dry_run(memory)      → validate memory
    * submit(memory)              → validate + save (destructive!)
    * graph_json()                → archive graph metadata
    * timeline_json()             → chronological events
    * audit_json()                → quality report
    * verify_signatures_json()    → signature verification

KHÔNG expose:
    * web server start (blocking)
    * demo (side effects)
    * Interactive submit (không phù hợp với agent)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__, agent

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(args: list[str], input_text: str | None = None) -> dict[str, Any]:
    """Gọi humanarchive CLI, trả JSON dict (hoặc {error} nếu fail)."""
    try:
        r = subprocess.run(
            ["humanarchive", *args],
            cwd=REPO_ROOT, input=input_text,
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return {"error": "humanarchive CLI not installed. Run: pip install -e ."}
    except subprocess.TimeoutExpired:
        return {"error": "CLI timeout after 60s"}

    if r.returncode not in (0, 1):
        return {
            "error": f"CLI exit {r.returncode}",
            "stderr": r.stderr[:2000],
            "stdout": r.stdout[:500],
        }

    # Try parse stdout as JSON; fallback to raw text
    out = r.stdout.strip()
    if not out:
        return {"ok": True, "result": None, "stderr": r.stderr}
    try:
        return {"ok": True, "result": json.loads(out)}
    except json.JSONDecodeError:
        return {"ok": True, "result": out, "format": "text"}


# --------------------------------------------------------------------------
# Tool implementations (plain functions; MCP wrapper registers them)
# --------------------------------------------------------------------------

def tool_describe(type_name: str) -> dict:
    """Return JSON Schema for memory or annotation."""
    try:
        return agent.describe(type_name)
    except (KeyError, FileNotFoundError) as exc:
        return {"error": str(exc)}


def tool_capabilities() -> dict:
    """Return full CLI surface as structured JSON."""
    return agent.capabilities()


def tool_rag_search(query: str, k: int = 5) -> dict:
    """Run RAG search (role-balanced). Builds index if missing."""
    # Ensure index exists
    idx = REPO_ROOT / "archive" / "rag_index.json"
    if not idx.exists():
        _run_cli(["rag", "--build"])
    return _run_cli(["rag", "--json", "--k", str(k), query])


def tool_submit_dry_run(memory: dict) -> dict:
    """Validate a memory without writing. Agent should ALWAYS dry-run first."""
    return _run_cli(
        ["submit", "--from-stdin", "--dry-run", "--json"],
        input_text=json.dumps(memory, ensure_ascii=False),
    )


def tool_submit(memory: dict, confirm: bool = False) -> dict:
    """Actually write memory to archive.

    confirm=False by default — enforces agents dry-run first. Flip to True
    only after the contributor-facing app has explicit consent.
    """
    if not confirm:
        return {
            "error": "confirm=True required. Call submit_dry_run first, "
                     "get explicit consent from the memory's contributor, "
                     "then call submit(memory, confirm=True)."
        }
    return _run_cli(
        ["submit", "--from-stdin", "--json"],
        input_text=json.dumps(memory, ensure_ascii=False),
    )


def tool_graph_json() -> dict:
    return _run_cli(["graph", "json"])


def tool_timeline_json() -> dict:
    return _run_cli(["timeline", "--json"])


def tool_audit_json() -> dict:
    return _run_cli(["audit", "--format", "json"])


def tool_verify_signatures_json() -> dict:
    return _run_cli(["verify-signatures", "--json"])


def tool_diff_archives(a: str, b: str) -> dict:
    return _run_cli(["diff", a, b, "--json"])


# --------------------------------------------------------------------------
# MCP protocol implementation
# --------------------------------------------------------------------------

_TOOLS = {
    "describe": {
        "fn": tool_describe,
        "description": "Get JSON Schema for 'memory' or 'annotation' types",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type_name": {"type": "string", "enum": ["memory", "annotation"]}
            },
            "required": ["type_name"],
        },
    },
    "capabilities": {
        "fn": tool_capabilities,
        "description": "List all CLI subcommands + ethical constraints",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "rag_search": {
        "fn": tool_rag_search,
        "description": "Semantic search with role-balanced retrieval",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    },
    "submit_dry_run": {
        "fn": tool_submit_dry_run,
        "description": "Validate a memory WITHOUT writing. Always call first.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory": {"type": "object"}},
            "required": ["memory"],
        },
    },
    "submit": {
        "fn": tool_submit,
        "description": "Write memory to archive (requires confirm=True)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory": {"type": "object"},
                "confirm": {"type": "boolean", "default": False},
            },
            "required": ["memory"],
        },
    },
    "graph_json":              {"fn": tool_graph_json,              "description": "Archive graph + events", "inputSchema": {"type": "object", "properties": {}}},
    "timeline_json":           {"fn": tool_timeline_json,           "description": "Chronological events",    "inputSchema": {"type": "object", "properties": {}}},
    "audit_json":              {"fn": tool_audit_json,              "description": "Quality audit report",    "inputSchema": {"type": "object", "properties": {}}},
    "verify_signatures_json":  {"fn": tool_verify_signatures_json,  "description": "Verify ed25519 sigs",     "inputSchema": {"type": "object", "properties": {}}},
}


def handle_request(req: dict) -> dict:
    """Handle một MCP JSON-RPC 2.0 request, trả response."""
    method = req.get("method")
    params = req.get("params", {}) or {}
    req_id = req.get("id")

    def _reply(result=None, error=None):
        r = {"jsonrpc": "2.0", "id": req_id}
        if error:
            r["error"] = error
        else:
            r["result"] = result
        return r

    if method == "initialize":
        return _reply({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "humanarchive", "version": __version__},
        })

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for name, t in _TOOLS.items()
        ]
        return _reply({"tools": tools})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        if name not in _TOOLS:
            return _reply(error={"code": -32601, "message": f"Tool not found: {name}"})
        try:
            result = _TOOLS[name]["fn"](**args)
        except TypeError as exc:
            return _reply(error={"code": -32602, "message": f"Invalid arguments: {exc}"})
        except Exception as exc:
            return _reply(error={"code": -32603, "message": f"Tool error: {exc}"})
        return _reply({
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
        })

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None  # notifications don't get responses

    return _reply(error={"code": -32601, "message": f"Method not found: {method}"})


def run_stdio() -> int:
    """Run MCP server over stdio. Đây là transport phổ biến nhất."""
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                err = {
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                print(json.dumps(err), flush=True)
                continue

            resp = handle_request(req)
            if resp is not None:
                print(json.dumps(resp, ensure_ascii=False), flush=True)
    except KeyboardInterrupt:
        return 130
    return 0


def main() -> int:
    """Entry point. CLI wrapper: `humanarchive mcp-server`."""
    # Minimal arg handling — only stdio mode for v1
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return run_stdio()


if __name__ == "__main__":
    sys.exit(main())
