"""Test agent-facing API: describe, capabilities, for-agent, non-interactive submit."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from humanarchive import agent  # noqa: E402


# ============================================================================
# describe
# ============================================================================

class TestDescribe:
    def test_describe_memory_returns_schema(self):
        d = agent.describe("memory")
        assert d["type"] == "memory"
        assert "schema" in d
        # Memory schema có các required field
        assert "required" in d["schema"]
        assert "motivation" in d["schema"]["required"] or \
               "motivation" in d["schema"]["properties"]

    def test_describe_annotation_returns_schema(self):
        d = agent.describe("annotation")
        assert d["type"] == "annotation"
        assert "schema" in d
        assert "target_memory_id" in d["schema"]["required"]

    def test_describe_unknown_raises(self):
        with pytest.raises(KeyError):
            agent.describe("doesnotexist")

    def test_describe_includes_version(self):
        d = agent.describe("memory")
        assert "humanarchive_version" in d


# ============================================================================
# capabilities
# ============================================================================

class TestCapabilities:
    def test_capabilities_lists_key_subcommands(self):
        cap = agent.capabilities()
        names = {s["name"] for s in cap["subcommands"]}
        # Phải có các subcommand chính
        for required in ("submit", "rag", "graph", "audit", "describe",
                         "capabilities", "for-agent", "diff"):
            assert required in names, f"Missing: {required}"

    def test_capabilities_has_ethical_constraints(self):
        cap = agent.capabilities()
        assert "ethical_constraints" in cap
        # Phải nhắc nguyên tắc 4 (motivation required)
        text = " ".join(cap["ethical_constraints"])
        assert "motivation" in text.lower() or "principle 4" in text.lower()

    def test_capabilities_has_exit_code_convention(self):
        cap = agent.capabilities()
        # Phải document principles về stdout/stderr/exit code
        text = " ".join(cap["principles"])
        assert "stdout" in text.lower() or "exit" in text.lower()

    def test_capabilities_json_serializable(self):
        cap = agent.capabilities()
        # Phải round-trip qua JSON
        serialized = json.dumps(cap, ensure_ascii=False)
        restored = json.loads(serialized)
        assert restored["humanarchive_version"] == cap["humanarchive_version"]


# ============================================================================
# for-agent doc
# ============================================================================

class TestForAgentDoc:
    def test_for_agent_mentions_key_commands(self):
        doc = agent.for_agent_doc()
        # Agent đọc doc này phải học được các lệnh cơ bản
        for cmd in ("humanarchive capabilities", "humanarchive describe",
                    "humanarchive submit", "--from-stdin"):
            assert cmd in doc, f"Missing mention: {cmd}"

    def test_for_agent_mentions_ethical_constraints(self):
        doc = agent.for_agent_doc()
        # Phải warn về 5 nguyên tắc
        assert "verdict" in doc.lower() or "principle 1" in doc.lower()
        assert "motivation" in doc.lower()

    def test_for_agent_mentions_exit_codes(self):
        doc = agent.for_agent_doc()
        assert "exit" in doc.lower() or "130" in doc


# ============================================================================
# End-to-end CLI (subprocess)
# ============================================================================

class TestCliEndToEnd:
    """Thử gọi CLI thực sự qua subprocess, như agent sẽ làm."""

    def _ha(self, *args, input_text=None):
        """Run humanarchive CLI, return (rc, stdout, stderr)."""
        cmd = [sys.executable, "-m", "humanarchive", *args]
        r = subprocess.run(
            cmd, cwd=REPO, input=input_text,
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode, r.stdout, r.stderr

    def test_version_json(self):
        rc, out, _ = self._ha("version", "--json")
        assert rc == 0
        d = json.loads(out)
        assert "humanarchive_version" in d

    def test_describe_memory_via_cli(self):
        rc, out, _ = self._ha("describe", "memory")
        assert rc == 0
        d = json.loads(out)
        assert d["type"] == "memory"

    def test_describe_unknown_exits_2(self):
        rc, _, err = self._ha("describe", "xyz")
        assert rc == 2
        # stderr contains error JSON
        err_json = json.loads(err.strip())
        assert "error" in err_json

    def test_capabilities_via_cli(self):
        rc, out, _ = self._ha("capabilities")
        assert rc == 0
        d = json.loads(out)
        assert "subcommands" in d

    def test_submit_from_stdin_dry_run(self):
        """Agent pipeline: pipe JSON memory into submit --from-stdin --dry-run."""
        import hashlib

        mem = {
            "schema_version": "1.0",
            "contributor_id": "ha-test-0001",
            "event": {
                "event_id": "2024-agent-test-aaaa",
                "name": "Agent test",
                "date": "2024-01-01",
            },
            "perspective": {"role": "witness"},
            "memory": {
                "what_happened": "Memory nội dung dài đủ 20 ký tự để pass validation."
            },
            "motivation": {"your_motivation": "Vì agent test."},
            "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
        }
        # Compute memory_id (khớp với tool)
        canonical = json.dumps(mem, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        mem["memory_id"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]

        rc, out, _ = self._ha(
            "submit", "--from-stdin", "--dry-run", "--json",
            input_text=json.dumps(mem),
        )
        assert rc == 0, f"stdout={out}"
        result = json.loads(out.strip())
        assert result["ok"] is True
        assert result["dry_run"] is True
        assert result["memory_id"] == mem["memory_id"]

    def test_submit_invalid_returns_errors_json(self):
        bad_mem = {
            "schema_version": "1.0",
            "contributor_id": "ha-test-0001",
            "event": {"event_id": "2024-x-aaaa", "name": "x", "date": "2024-01-01"},
            "perspective": {"role": "witness"},
            "memory": {"what_happened": "x"},  # too short (< 20)
            "motivation": {"your_motivation": "x"},  # too short (< 10)
            "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
        }
        rc, out, _ = self._ha(
            "submit", "--from-stdin", "--dry-run", "--json",
            input_text=json.dumps(bad_mem),
        )
        assert rc == 2
        result = json.loads(out.strip())
        assert result["ok"] is False
        assert "errors" in result
        # Có ít nhất 1 lỗi liên quan tới what_happened hoặc motivation
        errors_text = " ".join(result["errors"])
        assert "what_happened" in errors_text or "motivation" in errors_text
