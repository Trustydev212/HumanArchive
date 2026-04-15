#!/usr/bin/env python3
"""Timeline export — HTML chronological view từ archive.

Output là file HTML đơn lẻ, self-contained (không CDN, hoạt động offline
và trong Tor Browser). Hiển thị events theo trục thời gian dọc với:
    - Ngày chính xác nếu có (YYYY-MM-DD)
    - Khoảng thời gian (start/end) nếu date là range
    - Vị trí gần đúng nếu date dạng ~YYYY-MM
    - Role badges + count
    - Content warning nếu có trauma severe

Tôn trọng consent filter (withdrawn/embargo/public). Chỉ render events
có memory đang viewable.

Sử dụng:
    python tools/timeline_export.py --output timeline.html
    humanarchive timeline                              # nếu đã cài package
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import is_publicly_viewable  # noqa: E402
from core.trauma import detect_trauma  # noqa: E402


def _parse_date(s: str) -> tuple[str, str | None]:
    """Parse date string thành (display, sort_key).

    Các format chấp nhận:
        - YYYY-MM-DD           → sort_key = YYYY-MM-DD
        - YYYY-MM-DD/YYYY-MM-DD → sort_key = start date
        - ~YYYY-MM             → sort_key = YYYY-MM-00 (đầu tháng xấp xỉ)
        - ~YYYY                → sort_key = YYYY-00-00
        - YYYY-MM              → sort_key = YYYY-MM-00
        - YYYY                 → sort_key = YYYY-00-00
    """
    if not s:
        return "(không rõ ngày)", None
    s = s.strip()
    # Range
    if "/" in s:
        parts = s.split("/")
        return s, parts[0].lstrip("~")
    # Xấp xỉ
    approx = s.startswith("~")
    base = s.lstrip("~")
    # Normalize thành dạng sortable
    parts = base.split("-")
    if len(parts) == 1:
        sort_key = f"{parts[0]}-00-00"
    elif len(parts) == 2:
        sort_key = f"{parts[0]}-{parts[1].zfill(2)}-00"
    else:
        sort_key = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return s, sort_key


def _load_events(archive_root: Path) -> list[dict[str, Any]]:
    events_dir = archive_root / "events"
    if not events_dir.exists():
        return []

    by_event: dict[str, dict] = {}
    for event_dir in sorted(events_dir.iterdir()):
        if not event_dir.is_dir():
            continue
        memories: list[dict] = []
        for p in sorted(event_dir.glob("*.json")):
            if p.name.startswith("_") or ".amend." in p.name:
                continue
            try:
                with p.open(encoding="utf-8") as f:
                    mem = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(mem, dict):
                continue
            if not is_publicly_viewable(mem):
                continue
            memories.append(mem)

        if not memories:
            continue

        first = memories[0].get("event", {})
        eid = event_dir.name
        display_date, sort_key = _parse_date(first.get("date", ""))
        roles = sorted({
            (m.get("perspective") or {}).get("role", "?") for m in memories
        })
        tags = sorted({
            t for m in memories for t in (m.get("event") or {}).get("tags") or []
        })
        severe = sum(1 for m in memories if detect_trauma(m).severity == "severe")
        by_event[eid] = {
            "event_id": eid,
            "name": first.get("name", eid),
            "date_display": display_date,
            "date_sort": sort_key or "9999-99-99",
            "location": first.get("location", ""),
            "memory_count": len(memories),
            "roles": roles,
            "tags": tags,
            "severe_count": severe,
        }

    ordered = sorted(by_event.values(), key=lambda e: e["date_sort"])
    return ordered


_STYLE = """
:root {
  --bg: #faf7f0; --card: #fff; --fg: #1f1f1f; --muted: #6a6a6a;
  --accent: #8b4513; --line: #d9c9a8; --border: #e2ddd3;
  --warn: #b85c00; --severe: #8b2222;
}
* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", "Noto Sans", sans-serif; }
.container { max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }
header h1 { margin: 0 0 0.3rem; color: var(--accent); font-size: 1.9rem; }
header p { color: var(--muted); margin: 0 0 2rem; }
.timeline { position: relative; padding-left: 40px; }
.timeline::before {
  content: ""; position: absolute; left: 15px; top: 0; bottom: 0;
  width: 2px; background: var(--line);
}
.entry { position: relative; margin-bottom: 2rem; }
.entry::before {
  content: ""; position: absolute; left: -33px; top: 8px;
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--accent); border: 3px solid var(--bg);
}
.entry.severe::before { background: var(--severe); }
.entry .date { font-weight: 600; color: var(--accent); font-size: 0.95rem; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 6px; padding: 1rem 1.2rem; margin-top: 0.3rem;
}
.card.severe { border-left-color: var(--severe); }
.card h3 { margin: 0 0 0.3rem; font-size: 1.1rem; }
.card .meta { color: var(--muted); font-size: 0.85rem; }
.card .tags { margin-top: 0.5rem; }
.role-badge, .tag {
  display: inline-block; padding: 0.1rem 0.5rem; border-radius: 3px;
  font-size: 0.76rem; margin: 0.1rem 0.15rem 0 0;
}
.role-badge { background: #e9e4d5; color: #5a4a35; }
.tag { background: #f0eada; color: #6a4f20; }
.warning {
  background: #ffe0e0; border-left: 3px solid var(--severe);
  padding: 0.4rem 0.7rem; font-size: 0.82rem; margin-top: 0.5rem;
  border-radius: 3px;
}
.empty { text-align: center; color: var(--muted); margin: 4rem 0; }
footer { color: var(--muted); font-size: 0.82rem; text-align: center;
  padding: 1.5rem 0; border-top: 1px solid var(--border); margin-top: 3rem; }
"""


def render_html(events: list[dict]) -> str:
    if not events:
        body = '<div class="empty"><p>Archive chưa có event nào đang công bố.</p></div>'
    else:
        parts: list[str] = ['<ul class="timeline" style="list-style:none;padding-left:40px">']
        for e in events:
            severe = e["severe_count"] > 0
            entry_class = "entry severe" if severe else "entry"
            card_class = "card severe" if severe else "card"
            warning_html = (
                f'<div class="warning">⚠ {e["severe_count"]}/{e["memory_count"]} '
                f'ký ức có nội dung trauma nghiêm trọng.</div>'
                if severe else ""
            )
            roles_html = "".join(
                f'<span class="role-badge">{html.escape(r)}</span>' for r in e["roles"]
            )
            tags_html = "".join(
                f'<span class="tag">#{html.escape(t)}</span>' for t in e["tags"]
            )
            loc = (
                f' · {html.escape(e["location"])}' if e["location"] else ""
            )
            tags_block = f'<div class="tags">{tags_html}</div>' if tags_html else ""
            parts.append(
                f'<li class="{entry_class}">'
                f'<div class="date">{html.escape(e["date_display"])}</div>'
                f'<div class="{card_class}">'
                f'<h3>{html.escape(e["name"])}</h3>'
                f'<div class="meta">'
                f'<code>{html.escape(e["event_id"])}</code>'
                f' · {e["memory_count"]} ký ức{loc}'
                f'</div>'
                f'<div>{roles_html}</div>'
                f'{tags_block}'
                f'{warning_html}'
                f'</div>'
                f'</li>'
            )
        parts.append("</ul>")
        body = "".join(parts)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HumanArchive — Timeline</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="container">
<header>
  <h1>Timeline</h1>
  <p>{len(events)} event đang công bố, sắp xếp theo thời gian.
     Events đang bị embargo hoặc withdrawn không xuất hiện ở đây.</p>
</header>
{body}
<footer>
  <p>Sinh bởi <code>humanarchive timeline</code>. Tôn trọng consent filter.</p>
</footer>
</div>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default="archive")
    p.add_argument("--output", default="archive/TIMELINE.html")
    p.add_argument("--json", action="store_true", help="Output JSON thay vì HTML.")
    args = p.parse_args()

    events = _load_events(Path(args.archive))
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(events), encoding="utf-8")
    print(f"Wrote timeline → {out} ({len(events)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
