#!/usr/bin/env python3
"""Export archive thành Obsidian vault.

Sinh ra một thư mục có thể mở trực tiếp trong Obsidian:

    obsidian_vault/
        README.md
        events/
            <event-name>.md           # một file / event, có frontmatter
        memories/
            <memory_id>.md            # một file / memory
        taxonomy/
            <category>.md             # một file / root category
        by-role/
            <role>.md                 # một file / role

`[[wikilinks]]` giữa các file để Obsidian tự dựng graph view. Tôn trọng
consent (withdrawn/embargo sẽ bị bỏ qua), scrub PII trước khi ghi.

Sử dụng:
    python tools/obsidian_export.py [--output obsidian_vault] [--archive archive]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import is_publicly_viewable  # noqa: E402
from core.privacy import pseudonymize  # noqa: E402
from core.trauma import detect_trauma  # noqa: E402


# --------------------------------------------------------------------------
# Filename sanitation — Obsidian + Windows compatible
# --------------------------------------------------------------------------

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\[\]#^]')


def safe_name(text: str, *, max_len: int = 80) -> str:
    """Sanitize cho filename. Giữ unicode VN nhưng loại ký tự invalid."""
    if not text:
        return "untitled"
    text = _INVALID_CHARS.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text or "untitled"


def yaml_escape(val: object) -> str:
    """Encode một giá trị vào YAML frontmatter (đủ dùng cho string/list)."""
    if isinstance(val, list):
        if not val:
            return "[]"
        return "[" + ", ".join(yaml_escape(v) for v in val) + "]"
    if isinstance(val, bool):
        return "true" if val else "false"
    if val is None:
        return "null"
    s = str(val)
    if any(c in s for c in ':#\n"\''):
        return '"' + s.replace('"', '\\"') + '"'
    return s


# --------------------------------------------------------------------------
# Load archive
# --------------------------------------------------------------------------

def _load_memories(archive_root: Path) -> list[dict]:
    out: list[dict] = []
    events_dir = archive_root / "events"
    if not events_dir.exists():
        return out
    for p in events_dir.rglob("*.json"):
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


# --------------------------------------------------------------------------
# Render helpers
# --------------------------------------------------------------------------

def render_memory_md(mem: dict, event_display_name: str) -> str:
    mid = mem.get("memory_id", "unknown")
    role = (mem.get("perspective") or {}).get("role", "?")
    event_id = (mem.get("event") or {}).get("event_id", "")
    date = (mem.get("event") or {}).get("date", "")
    tags = (mem.get("event") or {}).get("tags") or []
    categories = (mem.get("event") or {}).get("categories") or []

    fm_tags = [role, *tags]

    trauma = detect_trauma(mem)

    fm = "\n".join(
        [
            "---",
            f"memory_id: {yaml_escape(mid)}",
            f"event_id: {yaml_escape(event_id)}",
            f"role: {yaml_escape(role)}",
            f"date: {yaml_escape(date)}",
            f"tags: {yaml_escape(fm_tags)}",
            f"categories: {yaml_escape(categories)}",
            f"trauma_severity: {yaml_escape(trauma.severity)}",
            "---",
        ]
    )

    lines: list[str] = [fm, "", f"# Ký ức ({role}) — {event_display_name}", ""]
    lines.append(f"**Event:** [[events/{safe_name(event_display_name)}]]")
    lines.append(f"**Role:** [[by-role/{role}]]")
    if tags:
        lines.append("**Tags:** " + " ".join(f"#{t}" for t in tags))
    lines.append("")

    if trauma.has_trauma:
        lines.append(f"> {trauma.content_warning()}")
        lines.append("")

    mem_body = mem.get("memory") or {}
    motiv = mem.get("motivation") or {}
    ctx = mem.get("context") or {}

    def _section(title: str, body: str | None) -> None:
        if body:
            lines.append(f"## {title}")
            lines.append("")
            lines.append(pseudonymize(str(body)))
            lines.append("")

    _section("Chuyện gì đã xảy ra", mem_body.get("what_happened"))
    _section("Chi tiết giác quan", mem_body.get("sensory_details"))
    _section("Trạng thái cảm xúc", mem_body.get("emotional_state"))
    _section("Động cơ", motiv.get("your_motivation"))
    _section("Áp lực bên ngoài", motiv.get("external_pressure"))
    _section("Nỗi sợ khi đó", motiv.get("fears_at_the_time"))
    _section("Nhìn lại, hiểu thêm điều gì", ctx.get("what_learned_after"))
    _section("Nếu được chọn lại", ctx.get("would_do_differently"))

    # Links đến related events
    relations = ctx.get("relations") or []
    related_ids = ctx.get("related_event_ids") or []
    if relations or related_ids:
        lines.append("## Liên kết sự kiện")
        lines.append("")
        for r in relations:
            lines.append(
                f"- **{r.get('type', 'related')}** → `{r.get('event_id')}` "
                f"({r.get('note') or ''})"
            )
        for eid in related_ids:
            lines.append(f"- related → `{eid}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_event_md(event_id: str, memories: list[dict]) -> tuple[str, str]:
    """Trả về (display_name, markdown body)."""
    first = memories[0].get("event", {})
    name = first.get("name", event_id)
    display_name = safe_name(name)
    date = first.get("date", "")
    location = first.get("location", "")
    tags = set()
    categories = set()
    roles = set()
    for m in memories:
        ev = m.get("event") or {}
        tags.update(ev.get("tags") or [])
        categories.update(ev.get("categories") or [])
        role = (m.get("perspective") or {}).get("role")
        if role:
            roles.add(role)

    fm = "\n".join(
        [
            "---",
            f"event_id: {yaml_escape(event_id)}",
            f"date: {yaml_escape(date)}",
            f"location: {yaml_escape(location)}",
            f"tags: {yaml_escape(sorted(tags))}",
            f"categories: {yaml_escape(sorted(categories))}",
            f"roles_present: {yaml_escape(sorted(roles))}",
            f"memory_count: {len(memories)}",
            "---",
        ]
    )
    lines = [fm, "", f"# {name}", "", f"**event_id:** `{event_id}`", ""]
    if date:
        lines.append(f"- **Ngày:** {date}")
    if location:
        lines.append(f"- **Địa điểm:** {location}")
    if categories:
        lines.append(
            "- **Categories:** "
            + ", ".join(f"[[taxonomy/{c.split('/')[0]}]]" for c in sorted(categories))
        )
    if tags:
        lines.append("- **Tags:** " + " ".join(f"#{t}" for t in sorted(tags)))
    lines.append("")

    # Severe trauma nếu có
    severe = [m for m in memories if detect_trauma(m).severity == "severe"]
    if severe:
        lines.append(
            f"> ⚠ **CẢNH BÁO NỘI DUNG**: {len(severe)}/{len(memories)} ký ức "
            "trong event này mô tả trải nghiệm đau thương."
        )
        lines.append("")

    # Nhóm theo role
    by_role: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        role = (m.get("perspective") or {}).get("role", "unknown")
        by_role[role].append(m)

    lines.append("## Các góc nhìn")
    lines.append("")
    for role, mems in sorted(by_role.items()):
        lines.append(f"### {role} ({len(mems)})")
        for m in mems:
            mid = m.get("memory_id")
            lines.append(f"- [[memories/{mid}]]")
        lines.append("")

    # Relations graph
    all_relations: list[tuple[str, str, str]] = []
    for m in memories:
        for r in (m.get("context") or {}).get("relations") or []:
            all_relations.append(
                (event_id, r.get("event_id", ""), r.get("type", "related"))
            )
    if all_relations:
        lines.append("## Quan hệ với event khác")
        lines.append("")
        lines.append("```mermaid")
        lines.append("graph LR")
        lines.append(f'  CURR["{name}"]')
        for _, tgt, rtype in all_relations:
            lines.append(f'  {tgt.replace("-", "_")}["{tgt}"]')
            lines.append(f"  CURR -->|{rtype}| {tgt.replace('-', '_')}")
        lines.append("```")
        lines.append("")

    return display_name, "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Main export
# --------------------------------------------------------------------------

def export(archive_root: Path, output: Path) -> dict[str, int]:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    memories = _load_memories(archive_root)
    viewable = [m for m in memories if is_publicly_viewable(m)]

    stats = {
        "memories_total": len(memories),
        "memories_exported": len(viewable),
        "memories_hidden": len(memories) - len(viewable),
        "events": 0,
    }

    # Memories
    (output / "memories").mkdir()
    by_event: dict[str, list[dict]] = defaultdict(list)
    by_role: dict[str, list[dict]] = defaultdict(list)
    for m in viewable:
        eid = (m.get("event") or {}).get("event_id", "unknown")
        by_event[eid].append(m)
        by_role[(m.get("perspective") or {}).get("role", "unknown")].append(m)

    # Events
    (output / "events").mkdir()
    event_display: dict[str, str] = {}
    for eid, mems in by_event.items():
        display_name, body = render_event_md(eid, mems)
        event_display[eid] = display_name
        (output / "events" / f"{display_name}.md").write_text(body, encoding="utf-8")
    stats["events"] = len(by_event)

    for m in viewable:
        mid = m.get("memory_id", "unknown")
        eid = (m.get("event") or {}).get("event_id", "unknown")
        display_name = event_display.get(eid, eid)
        (output / "memories" / f"{mid}.md").write_text(
            render_memory_md(m, display_name), encoding="utf-8"
        )

    # By-role pages
    (output / "by-role").mkdir()
    for role, mems in by_role.items():
        lines = [f"# Góc nhìn: {role}", "", f"{len(mems)} ký ức.", ""]
        for m in mems:
            mid = m.get("memory_id")
            lines.append(f"- [[memories/{mid}]]")
        (output / "by-role" / f"{role}.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    # Taxonomy pages
    (output / "taxonomy").mkdir()
    tax_file = REPO / "taxonomy" / "categories.json"
    if tax_file.exists():
        tax = json.loads(tax_file.read_text(encoding="utf-8"))
        for root, data in tax.get("categories", {}).items():
            lines = [
                f"# {data.get('label_vi', root)}",
                "",
                f"*{data.get('label_en', root)}*",
                "",
            ]
            # Events thuộc root này
            matched = [
                (eid, event_display[eid])
                for eid, mems in by_event.items()
                if any(
                    c.startswith(root)
                    for m in mems
                    for c in (m.get("event") or {}).get("categories") or []
                )
            ]
            if matched:
                lines.append("## Events")
                for eid, name in matched:
                    lines.append(f"- [[events/{name}]] (`{eid}`)")
            (output / "taxonomy" / f"{root}.md").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )

    # README
    readme = [
        "# HumanArchive — Obsidian vault",
        "",
        "Vault này được sinh tự động từ `archive/events/`. **Không chỉnh",
        "sửa trực tiếp** — nguồn sự thật vẫn là JSON ở archive (xem nguyên",
        "tắc 5: immutability).",
        "",
        "## Cách xem",
        "",
        "1. Mở thư mục này bằng Obsidian.",
        "2. Bật **Graph View** (Ctrl/Cmd+G) để xem mạng liên kết.",
        "3. Cài plugin **Dataview** để query theo tags/categories trong YAML.",
        "",
        "## Cấu trúc",
        "",
        "- `events/` — một note / event, frontmatter giàu metadata, có Mermaid graph.",
        "- `memories/` — một note / memory, đã scrub PII, có content warning.",
        "- `by-role/` — duyệt theo vai trò (witness, authority, victim, ...).",
        "- `taxonomy/` — duyệt theo phân loại chuẩn.",
        "",
        f"## Thống kê",
        "",
        f"- **Events:** {stats['events']}",
        f"- **Memories (đã export):** {stats['memories_exported']}",
        f"- **Memories (ẩn vì consent/embargo/withdrawn):** {stats['memories_hidden']}",
    ]
    (output / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    return stats


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default="archive", help="Archive root")
    p.add_argument("--output", default="obsidian_vault", help="Output folder")
    args = p.parse_args()

    stats = export(Path(args.archive), Path(args.output))
    print(
        f"Exported {stats['events']} events, "
        f"{stats['memories_exported']} memories → {args.output}/"
    )
    if stats["memories_hidden"]:
        print(
            f"  ({stats['memories_hidden']} memories hidden due to consent/embargo/withdrawn)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
