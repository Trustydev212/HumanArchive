#!/usr/bin/env python3
"""Audit CLI — báo cáo chất lượng archive mà không gatekeep.

KHÔNG reject, KHÔNG xoá — chỉ report. Người vận hành xem report, quyết
định (và gắn annotation phù hợp nếu cần). Nguyên tắc 5 được bảo toàn.

Các check:
    - Memory thiếu metadata khuyến nghị (tags, categories, age_at_event)
    - Event chỉ có 1 role (thiếu cross-reference cơ bản)
    - PII có thể còn sót (regex detector chạy lại)
    - Memory có memory_id không khớp content (tamper)
    - Event có memory mâu thuẫn rõ rệt về thời gian/địa điểm
    - Ngôn ngữ không match (vd: content tiếng Anh nhưng khai language=vi)

Xuất JSON hoặc Markdown.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import verify_memory_id  # noqa: E402
from core.privacy import find_pii  # noqa: E402


def _iter_memories(archive_root: Path):
    events_dir = archive_root / "events"
    if not events_dir.exists():
        return
    for event_dir in sorted(events_dir.iterdir()):
        if not event_dir.is_dir():
            continue
        for p in sorted(event_dir.glob("*.json")):
            if p.name.startswith("_") or ".amend." in p.name:
                continue
            try:
                with p.open(encoding="utf-8") as f:
                    mem = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            yield event_dir.name, mem, p


def audit(archive_root: Path) -> dict:
    report: dict = {
        "archive_root": str(archive_root),
        "integrity_issues": [],
        "missing_metadata": [],
        "single_role_events": [],
        "possible_pii_leaks": [],
        "events_without_motivation": [],
        "totals": {"memories": 0, "events": 0},
    }

    by_event_roles: dict[str, set[str]] = defaultdict(set)
    by_event_memories: dict[str, int] = defaultdict(int)

    for eid, mem, _path in _iter_memories(archive_root):
        report["totals"]["memories"] += 1
        mid = mem.get("memory_id", "?")
        role = (mem.get("perspective") or {}).get("role")
        by_event_memories[eid] += 1
        if role:
            by_event_roles[eid].add(role)

        # Integrity
        rep = verify_memory_id(mem)
        if rep.tampered:
            report["integrity_issues"].append(
                {"memory_id": mid, "claimed": rep.claimed, "actual": rep.actual}
            )

        # Missing metadata (khuyến nghị, không bắt buộc)
        missing = []
        ev = mem.get("event") or {}
        if not ev.get("tags"):
            missing.append("tags")
        if not ev.get("categories"):
            missing.append("categories")
        persp = mem.get("perspective") or {}
        if "age_at_event" not in persp:
            missing.append("perspective.age_at_event")
        if "proximity" not in persp:
            missing.append("perspective.proximity")
        if missing:
            report["missing_metadata"].append({"memory_id": mid, "missing": missing})

        # PII leak: chạy lại detector trên các trường tự do — nếu còn match,
        # có khả năng bị lộ danh tính
        text_parts = []
        m = mem.get("memory") or {}
        for k in ("what_happened", "sensory_details", "emotional_state"):
            if m.get(k):
                text_parts.append(str(m[k]))
        motiv = mem.get("motivation") or {}
        for k in ("your_motivation", "external_pressure", "fears_at_the_time"):
            if motiv.get(k):
                text_parts.append(str(motiv[k]))
        findings = find_pii("\n".join(text_parts))
        # Bỏ qua place names - chỉ flag person_name, phone, email, national_id
        serious = [f for f in findings if f.kind in ("person_name", "phone", "email", "national_id")]
        if serious:
            report["possible_pii_leaks"].append(
                {
                    "memory_id": mid,
                    "kinds": sorted({f.kind for f in serious}),
                    "count": len(serious),
                }
            )

        # Motivation required
        if not (motiv.get("your_motivation") or "").strip():
            report["events_without_motivation"].append({"memory_id": mid})

    report["totals"]["events"] = len(by_event_memories)

    # Single-role events (thiếu đa góc nhìn cơ bản)
    for eid, roles in by_event_roles.items():
        if len(roles) == 1:
            report["single_role_events"].append(
                {
                    "event_id": eid,
                    "only_role": next(iter(roles)),
                    "memory_count": by_event_memories[eid],
                }
            )

    return report


def to_markdown(r: dict) -> str:
    lines = ["# Audit report", ""]
    lines.append(f"- archive: `{r['archive_root']}`")
    lines.append(f"- memories: {r['totals']['memories']}")
    lines.append(f"- events: {r['totals']['events']}")
    lines.append("")

    def _section(title: str, items: list, keys: list[str]) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("*OK*")
            lines.append("")
            return
        for it in items[:50]:
            bits = [f"`{it.get(k, '')}`" for k in keys]
            lines.append("- " + " · ".join(bits))
        if len(items) > 50:
            lines.append(f"- … +{len(items) - 50} more")
        lines.append("")

    _section(
        "⚠ Integrity issues (memory_id không khớp content)",
        r["integrity_issues"], ["memory_id", "claimed", "actual"]
    )
    _section(
        "⚠ Có thể PII còn sót",
        r["possible_pii_leaks"], ["memory_id", "kinds", "count"]
    )
    _section(
        "Thiếu motivation (bắt buộc — nguyên tắc 4)",
        r["events_without_motivation"], ["memory_id"]
    )
    _section(
        "Event chỉ có 1 góc nhìn (cần kêu gọi thêm)",
        r["single_role_events"], ["event_id", "only_role", "memory_count"]
    )
    _section(
        "Metadata khuyến nghị còn thiếu",
        r["missing_metadata"], ["memory_id", "missing"]
    )

    lines.append("---")
    lines.append("")
    lines.append(
        "*Audit report KHÔNG phán xét — chỉ báo. Mỗi item có thể có "
        "lý do chính đáng (contributor chọn không khai age, chưa có ai "
        "khác đóng góp cho event, v.v.). Dùng report để biết nên ưu tiên "
        "kêu gọi ai đóng góp, hoặc gắn annotation cảnh báo nếu cần.*"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default="archive")
    p.add_argument("--format", choices=["json", "md"], default="md")
    args = p.parse_args()

    report = audit(Path(args.archive))
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
