#!/usr/bin/env python3
"""Export archive graph thành nhiều format để visualize.

Sử dụng:
    python tools/graph_export.py mermaid > graph.md
    python tools/graph_export.py json    > graph.json
    python tools/graph_export.py tree    > tree.md
    python tools/graph_export.py prism <event_id> > prism.md

Format được hỗ trợ:
    * mermaid — Mermaid diagram (embed được vào Markdown / GitHub / Obsidian)
    * json    — Raw JSON cho D3/Cytoscape/Gephi/tự viết UI
    * tree    — Markdown bullet tree theo category
    * prism   — Perspective prism cho 1 event (Mermaid)
    * tagcloud — Bảng tần suất tag (Markdown)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.graph import ArchiveGraph, build_perspective_prism, load_archive_graph  # noqa: E402


# --------------------------------------------------------------------------
# Mermaid relation graph
# --------------------------------------------------------------------------

_REL_STYLE = {
    "part_of": "-.->|part_of|",
    "caused_by": "-->|caused_by|",
    "led_to": "-->|led_to|",
    "happened_during": "-.->|during|",
    "contradicts": "-.->|contradicts|",
    "corroborates": "-->|corroborates|",
    "aftermath_of": "-->|aftermath_of|",
    "related": "-.->|related|",
}


def _mermaid_id(event_id: str) -> str:
    # Mermaid node id không cho phép nhiều ký tự — băm ngắn để an toàn
    return "E_" + event_id.replace("-", "_")


def to_mermaid_graph(graph: ArchiveGraph) -> str:
    lines = ["```mermaid", "graph LR"]
    # Nodes
    for n in graph.nodes:
        label = f"{n.name}<br/>({n.date})<br/>n={n.memory_count}"
        lines.append(f'  {_mermaid_id(n.event_id)}["{label}"]')
    # Edges
    for e in graph.edges:
        arrow = _REL_STYLE.get(e.type, "-->")
        lines.append(
            f"  {_mermaid_id(e.source)} {arrow} {_mermaid_id(e.target)}"
        )
    lines.append("```")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Category tree (Markdown)
# --------------------------------------------------------------------------

def _render_tree(tree: dict, event_names: dict[str, str], depth: int = 0) -> list[str]:
    out: list[str] = []
    indent = "  " * depth
    for key in sorted(tree):
        val = tree[key]
        if isinstance(val, list):
            # Leaf: list of event_ids
            out.append(f"{indent}- **{key}** ({len(val)} event)")
            for eid in val:
                name = event_names.get(eid, eid)
                out.append(f"{indent}  - `{eid}` — {name}")
        else:
            out.append(f"{indent}- **{key}/**")
            out.extend(_render_tree(val, event_names, depth + 1))
    return out


def to_category_tree(graph: ArchiveGraph) -> str:
    names = {n.event_id: n.name for n in graph.nodes}
    lines = ["# Category tree", ""]
    lines.extend(_render_tree(graph.category_tree, names))
    if not graph.category_tree:
        lines.append("*Archive trống hoặc chưa có event nào được gắn category.*")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Tag cloud (Markdown table)
# --------------------------------------------------------------------------

def to_tag_cloud(graph: ArchiveGraph) -> str:
    if not graph.tag_counts:
        return "# Tag cloud\n\n*Chưa có tag nào.*\n"
    lines = ["# Tag cloud", "", "| Tag | Số event |", "|-----|---------:|"]
    for tag, count in graph.tag_counts.items():
        lines.append(f"| `{tag}` | {count} |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Perspective prism (Mermaid)
# --------------------------------------------------------------------------

def to_prism_mermaid(prism: dict) -> str:
    event_id = prism["event_id"]
    event_name = prism["event_name"]
    lines = [
        f"# Perspective prism — {event_name}",
        "",
        f"*event_id: `{event_id}`*",
        "",
        "```mermaid",
        "graph LR",
        f'  EVENT(("{event_name}"))',
    ]
    i = 0
    for role, memories in prism["roles"].items():
        role_id = f"ROLE_{role}"
        lines.append(f'  {role_id}["{role}<br/>({len(memories)} memory)"]')
        lines.append(f"  EVENT --- {role_id}")
        for m in memories:
            mid = f"M_{i}"
            i += 1
            snippet = (m["motivation_summary"] or "(không có)").replace('"', "'")
            lines.append(f'  {mid}["{snippet}"]')
            lines.append(f"  {role_id} --> {mid}")
    lines.append("```")
    if prism["missing_roles"]:
        lines.append("")
        lines.append(
            f"> **Các vai trò chưa có ký ức (cần được lắng nghe):** "
            f"{', '.join(prism['missing_roles'])}"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Export archive graph.")
    p.add_argument(
        "format",
        choices=["mermaid", "json", "tree", "tagcloud", "prism"],
        help="Định dạng output",
    )
    p.add_argument("event_id", nargs="?", help="Required cho format=prism")
    p.add_argument("--archive-root", default="archive")
    args = p.parse_args()

    if args.format == "prism":
        if not args.event_id:
            print("Format 'prism' cần <event_id>.", file=sys.stderr)
            return 2
        prism = build_perspective_prism(args.event_id, archive_root=args.archive_root)
        print(to_prism_mermaid(prism))
        return 0

    graph = load_archive_graph(args.archive_root)
    if args.format == "mermaid":
        print(to_mermaid_graph(graph))
    elif args.format == "json":
        print(json.dumps(graph.to_dict(), ensure_ascii=False, indent=2))
    elif args.format == "tree":
        print(to_category_tree(graph))
    elif args.format == "tagcloud":
        print(to_tag_cloud(graph))
    return 0


if __name__ == "__main__":
    sys.exit(main())
