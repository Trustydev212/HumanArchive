"""Graph / tree generation cho HumanArchive.

Chuyển đổi flat archive thành các view phân cấp:
    * Category tree — cây phân loại (war → Vietnam War → Saigon fall)
    * Relation graph — đồ thị quan hệ (caused_by, led_to, part_of, ...)
    * Perspective prism — một event → nhánh theo role
    * Tag cloud — thống kê tag phổ biến

Output là structured data (dict) để:
    * Render thành Mermaid (embed vào Markdown/README)
    * Export JSON cho D3/Cytoscape/Obsidian
    * Viết web UI tuỳ ý

Thiết kế không làm thay đổi archive — chỉ đọc, không ghi. Tôn trọng
nguyên tắc 5 (immutability) và consent filtering của integrity layer.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .integrity import filter_viewable


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------

@dataclass
class EventNode:
    """Tóm tắt metadata của một event — đủ để dựng graph, không chứa nội dung."""

    event_id: str
    name: str
    date: str
    location: str | None
    tags: list[str]
    categories: list[str]
    memory_count: int
    roles_present: list[str]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "date": self.date,
            "location": self.location,
            "tags": self.tags,
            "categories": self.categories,
            "memory_count": self.memory_count,
            "roles_present": self.roles_present,
        }


@dataclass
class GraphEdge:
    source: str  # event_id
    target: str
    type: str
    note: str | None = None

    def to_dict(self) -> dict:
        d = {"source": self.source, "target": self.target, "type": self.type}
        if self.note:
            d["note"] = self.note
        return d


@dataclass
class ArchiveGraph:
    """Snapshot toàn bộ archive dưới dạng graph."""

    nodes: list[EventNode]
    edges: list[GraphEdge]
    tag_counts: dict[str, int] = field(default_factory=dict)
    category_tree: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "tag_counts": self.tag_counts,
            "category_tree": self.category_tree,
        }


# --------------------------------------------------------------------------
# Load archive
# --------------------------------------------------------------------------

def _load_event_memories(event_dir: Path) -> list[dict]:
    out: list[dict] = []
    for p in sorted(event_dir.glob("*.json")):
        if p.name.startswith("_") or ".amend." in p.name:
            continue
        try:
            with p.open(encoding="utf-8") as f:
                mem = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(mem, dict):
            out.append(mem)
    return out


def _summarize_event(memories: list[dict]) -> EventNode | None:
    """Tổng hợp event metadata từ danh sách memory của nó."""
    viewable = filter_viewable(memories)
    if not viewable:
        return None

    # Lấy metadata từ memory đầu tiên (event-level thông tin giống nhau ở mọi memory)
    first = viewable[0]
    ev = first.get("event", {})
    event_id = ev.get("event_id")
    if not event_id:
        return None

    # Tags & categories có thể khác nhau giữa các memory — union lại
    all_tags: set[str] = set()
    all_categories: set[str] = set()
    roles: set[str] = set()
    for m in viewable:
        mev = m.get("event") or {}
        all_tags.update(mev.get("tags") or [])
        all_categories.update(mev.get("categories") or [])
        role = (m.get("perspective") or {}).get("role")
        if role:
            roles.add(role)

    return EventNode(
        event_id=event_id,
        name=ev.get("name", event_id),
        date=ev.get("date", ""),
        location=ev.get("location"),
        tags=sorted(all_tags),
        categories=sorted(all_categories),
        memory_count=len(viewable),
        roles_present=sorted(roles),
    )


def _collect_relations(memories: list[dict], source_event_id: str) -> list[GraphEdge]:
    """Trích các quan hệ được khai báo trong context.relations của memory."""
    edges: list[GraphEdge] = []
    seen: set[tuple[str, str, str]] = set()  # dedupe
    for m in memories:
        ctx = m.get("context") or {}
        # related_event_ids (string-only) → quan hệ chung chung
        for tgt in ctx.get("related_event_ids") or []:
            key = (source_event_id, tgt, "related")
            if key not in seen:
                seen.add(key)
                edges.append(GraphEdge(source_event_id, tgt, "related"))
        # relations (structured)
        for rel in ctx.get("relations") or []:
            tgt = rel.get("event_id")
            rtype = rel.get("type")
            if not tgt or not rtype:
                continue
            key = (source_event_id, tgt, rtype)
            if key not in seen:
                seen.add(key)
                edges.append(GraphEdge(source_event_id, tgt, rtype, rel.get("note")))
    return edges


def load_archive_graph(archive_root: Path | str = "archive") -> ArchiveGraph:
    """Quét archive/events/ và dựng graph."""
    root = Path(archive_root) / "events"
    if not root.exists():
        return ArchiveGraph(nodes=[], edges=[])

    nodes: list[EventNode] = []
    edges: list[GraphEdge] = []
    for event_dir in sorted(root.iterdir()):
        if not event_dir.is_dir():
            continue
        memories = _load_event_memories(event_dir)
        if not memories:
            continue
        node = _summarize_event(memories)
        if node is None:
            continue
        nodes.append(node)
        edges.extend(_collect_relations(memories, node.event_id))

    # Tag counts
    tag_counter: Counter[str] = Counter()
    for n in nodes:
        tag_counter.update(n.tags)

    # Category tree — lồng theo path
    cat_tree = _build_category_tree(nodes)

    return ArchiveGraph(
        nodes=nodes,
        edges=edges,
        tag_counts=dict(tag_counter.most_common()),
        category_tree=cat_tree,
    )


def _build_category_tree(nodes: list[EventNode]) -> dict:
    """Xây cây lồng từ các category path.

    VD: ['conflict/war/civil-war', 'conflict/war/colonial-war'] →
        {'conflict': {'war': {'civil-war': [...], 'colonial-war': [...]}}}
    Leaf là list event_id.
    """
    tree: dict = {}
    for node in nodes:
        if not node.categories:
            tree.setdefault("_uncategorized", []).append(node.event_id)
            continue
        for path in node.categories:
            parts = path.split("/")
            cursor = tree
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor.setdefault(parts[-1], []).append(node.event_id)
    return tree


# --------------------------------------------------------------------------
# Perspective prism — view cho 1 event
# --------------------------------------------------------------------------

def build_perspective_prism(
    event_id: str, archive_root: Path | str = "archive"
) -> dict:
    """Dựng view một event → nhánh theo role.

    Output:
        {
          "event_id": ...,
          "event_name": ...,
          "roles": {
            "witness":   [{"memory_id": ..., "motivation_summary": ...}, ...],
            "authority": [...],
            ...
          },
          "missing_roles": [...]
        }
    """
    event_dir = Path(archive_root) / "events" / event_id
    if not event_dir.exists():
        raise FileNotFoundError(f"Không có event: {event_id}")
    memories = filter_viewable(_load_event_memories(event_dir))

    ALL_ROLES = ("participant", "witness", "authority", "organizer", "victim", "bystander")
    by_role: dict[str, list[dict]] = defaultdict(list)

    event_name = event_id
    for m in memories:
        role = (m.get("perspective") or {}).get("role", "unknown")
        event_name = (m.get("event") or {}).get("name", event_name)
        motiv = (m.get("motivation") or {}).get("your_motivation", "")
        # Tóm tắt động cơ trong 120 ký tự
        summary = motiv[:120] + ("…" if len(motiv) > 120 else "")
        by_role[role].append(
            {
                "memory_id": m.get("memory_id"),
                "motivation_summary": summary,
            }
        )

    present = sorted(by_role)
    missing = [r for r in ALL_ROLES if r not in present]

    return {
        "event_id": event_id,
        "event_name": event_name,
        "roles": {r: by_role[r] for r in present},
        "missing_roles": missing,
    }


__all__ = [
    "EventNode",
    "GraphEdge",
    "ArchiveGraph",
    "load_archive_graph",
    "build_perspective_prism",
]
