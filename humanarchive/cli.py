"""Unified CLI entry point.

Run `humanarchive <subcommand>` sau khi `pip install humanarchive`,
hoặc `python -m humanarchive <subcommand>` khi dev.

Subcommands re-dispatch đến `tools/*.py` để tránh duplicate code.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__


def _repo_root() -> Path:
    """Tìm repo root — nơi chứa `tools/`, `core/`, `archive/`."""
    # 1. Khi chạy từ source tree: parent của humanarchive/ package
    here = Path(__file__).resolve().parent.parent
    if (here / "tools").exists() and (here / "core").exists():
        return here
    # 2. Khi đã pip-install: tools/ không có, fallback về CWD
    return Path.cwd()


_SUBCOMMAND_TO_TOOL = {
    "submit":             "submit.py",
    "rag":                "rag_query.py",
    "graph":              "graph_export.py",
    "obsidian":           "obsidian_export.py",
    "staging":            "staging.py",
    "audit":              "audit.py",
    "timeline":           "timeline_export.py",
    "diff":               "diff_archives.py",
    "verify-signatures":  "verify_signatures.py",
    "export-bundle":      "export_bundle.py",
    "import-bundle":      "import_bundle.py",
}


BANNER = """
  ┌───────────────────────────────────────────────────────────────┐
  │  HumanArchive  {version:<8}                                    │
  │  Decentralized collective memory — without judgment.          │
  │  Xem `humanarchive --help` hoặc đọc README.md.                │
  └───────────────────────────────────────────────────────────────┘
"""


def _print_help() -> None:
    print(BANNER.format(version="v" + __version__).rstrip())
    print("""
Usage: humanarchive <subcommand> [args...]

Subcommands (quick reference):
  demo             Chạy end-to-end demo: build indexes + start web UI
  web              Start static HTTP server cho web/ và archive/
  describe <type>  JSON Schema cho 'memory' hoặc 'annotation' (agent-friendly)
  capabilities     Structured listing toàn bộ CLI (agent discovery)
  for-agent        Integration guide cho AI agents
  submit           Đóng góp một ký ức qua CLI tương tác
                   (agent mode: --from-json file.json hoặc --from-stdin)
  rag <query>      Tìm kiếm ngữ nghĩa trong archive (role-balanced)
  rag --build      Build / rebuild vector index
  graph <format>   Export graph view (mermaid | tree | tagcloud | prism | json)
  obsidian         Sinh Obsidian vault từ archive
  staging ...      Staging workflow: list, submit, review, merge
  audit            Audit report chất lượng archive
  timeline         Sinh HTML timeline theo trục thời gian
  diff A B         So sánh 2 archive hoặc 2 bundle
  verify-signatures Verify ed25519 signatures trên annotations
  export-bundle    Export archive thành bundle.tar.gz (federation)
  import-bundle    Import bundle từ node khác
  version          In version

Documentation:
  README.md             Quickstart, 60-second demo
  docs/ethics.md        5 nguyên tắc bất biến
  docs/workflows.md     Multi-user patterns
  docs/rag.md           RAG safeguards
  docs/federation.md    Bundle protocol
""")


def cmd_demo(_args: list[str]) -> int:
    """End-to-end demo: build everything then start web UI."""
    root = _repo_root()
    print(BANNER.format(version="v" + __version__))
    print("Chạy end-to-end demo từ:", root)
    steps = [
        ("Build graph (archive/graph.json)",
         [sys.executable, str(root / "tools/graph_export.py"), "json"],
         root / "archive/graph.json"),
        ("Build RAG index (archive/rag_index.json)",
         [sys.executable, str(root / "tools/rag_query.py"), "--build"],
         None),
        ("Export Obsidian vault (obsidian_vault/)",
         [sys.executable, str(root / "tools/obsidian_export.py"),
          "--output", str(root / "obsidian_vault")],
         None),
    ]
    for i, (label, cmd, redirect) in enumerate(steps, start=1):
        print(f"\n[{i}/{len(steps)}] {label}")
        if redirect:
            with redirect.open("w", encoding="utf-8") as f:
                rc = subprocess.call(cmd, stdout=f, cwd=root)
        else:
            rc = subprocess.call(cmd, cwd=root)
        if rc != 0:
            print(f"   ⚠ Step failed (rc={rc}); tiếp tục.")

    # In audit report
    print("\n[Audit]")
    subprocess.call(
        [sys.executable, str(root / "tools/audit.py"), "--format", "md"],
        cwd=root,
    )

    print(f"""

╭─────────────────────────────────────────────────────────────────╮
│  ✓ Demo data ready.                                             │
│                                                                 │
│  Bây giờ hãy chạy:                                              │
│                                                                 │
│     humanarchive web        # start http://localhost:8000       │
│                                                                 │
│  Rồi mở trình duyệt:                                            │
│                                                                 │
│     http://localhost:8000/web/            (browse archive)      │
│     http://localhost:8000/web/submit.html (form đóng góp)       │
│                                                                 │
│  Thử query:                                                     │
│                                                                 │
│     humanarchive rag "tại sao xả đập sớm?"                      │
│                                                                 │
│  Mở Obsidian vault:                                             │
│                                                                 │
│     obsidian_vault/         (mở thư mục trong Obsidian)         │
│                                                                 │
╰─────────────────────────────────────────────────────────────────╯
""")
    return 0


def cmd_web(args: list[str]) -> int:
    """Start static HTTP server cho web/ và archive/."""
    port = "8000"
    if args and args[0].isdigit():
        port = args[0]
    root = _repo_root()
    print(f"Starting static server at http://127.0.0.1:{port}/")
    print(f"  → http://127.0.0.1:{port}/web/         (archive browser)")
    print(f"  → http://127.0.0.1:{port}/web/submit.html (contribute form)")
    print("(Ctrl-C để dừng)")
    os.chdir(root)
    return subprocess.call([sys.executable, "-m", "http.server", port])


def cmd_version(args: list[str]) -> int:
    if "--json" in args:
        import json
        import platform
        print(json.dumps({
            "humanarchive_version": __version__,
            "python_version": platform.python_version(),
            "api": "humanarchive/v1",
        }))
    else:
        print(f"humanarchive {__version__}")
    return 0


def cmd_describe(args: list[str]) -> int:
    """Return JSON Schema for a data type. Agent-friendly."""
    import json
    from . import agent

    if not args:
        print(
            json.dumps({"error": "missing type_name", "available": ["memory", "annotation"]}),
            file=sys.stderr,
        )
        return 2
    try:
        result = agent.describe(args[0])
    except (KeyError, FileNotFoundError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_capabilities(_args: list[str]) -> int:
    import json
    from . import agent

    print(json.dumps(agent.capabilities(), ensure_ascii=False, indent=2))
    return 0


def cmd_for_agent(_args: list[str]) -> int:
    from . import agent

    print(agent.for_agent_doc())
    return 0


def cmd_dispatch(subcommand: str, args: list[str]) -> int:
    """Chuyển tiếp đến tools/*.py."""
    tool = _SUBCOMMAND_TO_TOOL.get(subcommand)
    if not tool:
        print(f"Unknown subcommand: {subcommand}", file=sys.stderr)
        _print_help()
        return 2
    root = _repo_root()
    path = root / "tools" / tool
    if not path.exists():
        print(f"Tool file không tồn tại: {path}", file=sys.stderr)
        print("Bạn có đang ở đúng repo root? (pip install bundles tools/ vào package)", file=sys.stderr)
        return 2
    return subprocess.call([sys.executable, str(path), *args], cwd=root)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_help()
        return 0

    sub = sys.argv[1]
    args = sys.argv[2:]

    if sub in ("-v", "--version", "version"):
        return cmd_version(args)
    if sub == "demo":
        return cmd_demo(args)
    if sub == "web":
        return cmd_web(args)
    if sub == "describe":
        return cmd_describe(args)
    if sub == "capabilities":
        return cmd_capabilities(args)
    if sub == "for-agent":
        return cmd_for_agent(args)
    if sub in _SUBCOMMAND_TO_TOOL:
        return cmd_dispatch(sub, args)

    print(f"Unknown subcommand: {sub}\n")
    _print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
