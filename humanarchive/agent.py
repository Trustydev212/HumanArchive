"""Agent-friendly introspection cho HumanArchive.

Cho phép các AI agent (Claude Code, Cursor, Devin, ...) tự khám phá
khả năng của CLI mà không cần đọc docs.

Ba entry point chính:
    describe(type_name)    → JSON Schema cho 'memory' | 'annotation' | 'event'
    capabilities()         → structured listing của tất cả subcommand + flags
    for_agent_doc()        → integration guide ngắn gọn với examples

Nguyên tắc thiết kế:
    * Output LUÔN là JSON hợp lệ khi dùng trong pipeline
    * stdout = data; stderr = human-readable messages
    * Exit code ổn định, document rõ
    * Không bao giờ prompt tương tác (agents không trả lời được)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import __version__

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "core" / "schema"


# --------------------------------------------------------------------------
# describe
# --------------------------------------------------------------------------

_DESCRIBE_TYPES = {
    "memory": "memory.json",
    "annotation": "annotation.json",
}


def describe(type_name: str) -> dict:
    """Return JSON Schema for a known data type.

    Args:
        type_name: "memory" | "annotation"

    Returns:
        dict containing the schema + metadata

    Raises:
        KeyError: nếu type_name không hỗ trợ
    """
    if type_name not in _DESCRIBE_TYPES:
        raise KeyError(
            f"Unknown type '{type_name}'. Available: {sorted(_DESCRIBE_TYPES)}"
        )
    schema_path = SCHEMA_DIR / _DESCRIBE_TYPES[type_name]
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)
    return {
        "type": type_name,
        "humanarchive_version": __version__,
        "schema": schema,
    }


# --------------------------------------------------------------------------
# capabilities
# --------------------------------------------------------------------------

def capabilities() -> dict:
    """Structured description of the entire CLI surface.

    Agents parse this to know: which subcommands exist, what they do,
    what flags they accept, what output shape to expect.
    """
    return {
        "humanarchive_version": __version__,
        "api": "humanarchive/v1",
        "invocation": "humanarchive <subcommand> [args...]",
        "principles": [
            "stdout = data (JSON khi có --json flag)",
            "stderr = human messages",
            "Exit 0 = success, 1 = warning/diff, 2 = error",
            "Non-interactive: dùng --from-stdin hoặc --from-json <path>",
        ],
        "subcommands": [
            {
                "name": "version",
                "description": "In version",
                "agent_usage": "humanarchive version",
                "json_output": False,
            },
            {
                "name": "describe",
                "description": "Return JSON Schema của data type",
                "agent_usage": "humanarchive describe <memory|annotation>",
                "args": ["type_name"],
                "json_output": True,
            },
            {
                "name": "capabilities",
                "description": "File này — listing các subcommand",
                "agent_usage": "humanarchive capabilities",
                "json_output": True,
            },
            {
                "name": "for-agent",
                "description": "Integration guide cho AI agents",
                "agent_usage": "humanarchive for-agent",
                "json_output": False,
            },
            {
                "name": "submit",
                "description": "Đóng góp memory. Interactive hoặc from-json.",
                "agent_usage": "echo '{...memory...}' | humanarchive submit --from-stdin --json",
                "flags": ["--from <path>", "--from-stdin", "--dry-run", "--json"],
                "json_output": True,
            },
            {
                "name": "rag",
                "description": "RAG search. Build index với --build.",
                "agent_usage": "humanarchive rag --json 'câu hỏi'",
                "flags": ["--build", "--json", "--k <N>"],
                "json_output": True,
            },
            {
                "name": "graph",
                "description": "Export graph view",
                "agent_usage": "humanarchive graph json",
                "args": ["format: mermaid|tree|tagcloud|prism|json"],
                "json_output": True,
            },
            {
                "name": "obsidian",
                "description": "Sinh Obsidian vault",
                "agent_usage": "humanarchive obsidian --output vault/",
                "flags": ["--output <dir>", "--archive <dir>"],
                "json_output": False,
            },
            {
                "name": "staging",
                "description": "Staging workflow",
                "agent_usage": "humanarchive staging <list|submit|review|merge>",
                "subcommands": ["list", "submit <file>", "review <mid>", "merge <mid>"],
                "json_output": "partial (list support; review/merge print text)",
            },
            {
                "name": "audit",
                "description": "Audit report chất lượng archive",
                "agent_usage": "humanarchive audit --format json",
                "flags": ["--format json|md"],
                "json_output": True,
            },
            {
                "name": "timeline",
                "description": "Sinh HTML timeline (hoặc JSON)",
                "agent_usage": "humanarchive timeline --json",
                "flags": ["--output <path>", "--json"],
                "json_output": True,
            },
            {
                "name": "diff",
                "description": "So sánh 2 archive hoặc 2 bundle",
                "agent_usage": "humanarchive diff a b --json",
                "args": ["a", "b"],
                "flags": ["--json"],
                "exit_codes": {"0": "identical", "1": "diff", "2": "conflict"},
                "json_output": True,
            },
            {
                "name": "verify-signatures",
                "description": "Verify ed25519 trên annotations",
                "agent_usage": "humanarchive verify-signatures --json",
                "flags": ["--trust-file <path>", "--json"],
                "exit_codes": {"0": "all OK", "1": "unknown author", "2": "invalid sig"},
                "json_output": True,
            },
            {
                "name": "export-bundle",
                "description": "Export archive thành bundle.tar.gz",
                "agent_usage": "humanarchive export-bundle --output b.tar.gz",
                "flags": ["--output <path>", "--sign-key <pem>"],
                "json_output": False,
            },
            {
                "name": "import-bundle",
                "description": "Import bundle từ node khác",
                "agent_usage": "humanarchive import-bundle b.tar.gz --dry-run",
                "flags": ["--dry-run", "--verify-pubkey <hex>"],
                "json_output": False,
            },
        ],
        "data_types": ["memory", "annotation", "event", "bundle"],
        "ethical_constraints": [
            "Principle 1: Never output verdict/guilty/is_lying fields",
            "Principle 2: PII scrubbed before any LLM or index",
            "Principle 3: Trauma warnings preserved in output",
            "Principle 4: motivation.your_motivation is REQUIRED",
            "Principle 5: No memory delete/edit; only withdrawn flag",
        ],
    }


# --------------------------------------------------------------------------
# for-agent guide
# --------------------------------------------------------------------------

_AGENT_GUIDE = """\
HumanArchive — AI Agent Integration Guide
==========================================

You are an AI agent that needs to read from, write to, or analyze a
HumanArchive. Here's the minimal integration.

## Discovering capabilities

    humanarchive capabilities            # JSON: all subcommands
    humanarchive describe memory         # JSON: memory schema
    humanarchive describe annotation     # JSON: annotation schema

## Reading the archive

    # Overview graph + events
    humanarchive graph json

    # Timeline (chronological)
    humanarchive timeline --json

    # RAG search (build index once, then query)
    humanarchive rag --build
    humanarchive rag --json "your question"

    # Audit (surface integrity / PII / missing metadata)
    humanarchive audit --format json

## Submitting a memory (non-interactive)

    # From file
    humanarchive submit --from-json memory.json

    # From stdin (pipeline)
    echo '{...json...}' | humanarchive submit --from-stdin

    # Validate without writing
    humanarchive submit --from-json memory.json --dry-run

The memory object MUST match the schema from `humanarchive describe
memory`. Required fields the agent must fill:

    - event.event_id, event.name, event.date
    - perspective.role (participant|witness|authority|organizer|victim|bystander)
    - memory.what_happened (min 20 chars)
    - motivation.your_motivation (min 10 chars)   ← principle 4
    - consent.public (bool)

Do NOT fill contributor_id / memory_id / submitted_at — the tool
computes these deterministically.

## Federation

    humanarchive export-bundle --output b.tar.gz
    humanarchive import-bundle b.tar.gz --dry-run    # preview first
    humanarchive diff archive b.tar.gz --json        # before/after comparison

## Ethical constraints you MUST respect

1. You are NEVER allowed to pass judgment (is_lying, guilty, verdict).
2. Scrub PII before embedding any content in prompts.
3. If a memory describes trauma, preserve the content_warning.
4. Never submit a memory without motivation.your_motivation.
5. Never attempt to delete or modify a memory — only withdraw
   (set consent.withdrawn=true) is allowed, AND only by the original
   contributor.

## Exit codes (stable across versions)

    0    success
    1    diff / warning / no-match (not an error)
    2    validation error / tamper / conflict
    130  Ctrl-C (never expected in agent mode)

## Output conventions

    stdout  = machine-parsable data (JSON if --json flag)
    stderr  = human-readable log/progress messages

## Version pinning

Always check `humanarchive version` and pin to a known-good version in
your agent config. Schema changes follow semver.
"""


def for_agent_doc() -> str:
    return _AGENT_GUIDE
