#!/usr/bin/env python3
"""Diff 2 archives (hoặc 2 bundles) — xem memory nào mới/mất/khác.

Critical cho federation workflow: trước khi import bundle, biết được
bundle chứa gì so với archive hiện tại.

Sử dụng:
    # Diff 2 archive directories
    python tools/diff_archives.py archive_A archive_B

    # Diff bundle vs archive
    python tools/diff_archives.py bundle.tar.gz archive

    # JSON output cho pipe
    python tools/diff_archives.py a b --json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import compute_memory_id  # noqa: E402


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _load_source(path: Path) -> dict[str, dict]:
    """Load source → dict[memory_id, memory_dict]. Chấp nhận folder hoặc .tar.gz."""
    memories: dict[str, dict] = {}

    if path.is_file() and (path.suffix == ".gz" or path.suffixes[-2:] == [".tar", ".gz"]):
        with tarfile.open(path, "r:gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                if not member.name.startswith("archive/events/"):
                    continue
                if not member.name.endswith(".json"):
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                try:
                    mem = json.loads(f.read().decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                mid = mem.get("memory_id")
                if mid:
                    memories[mid] = mem
    elif path.is_dir():
        events_dir = path / "events"
        if not events_dir.exists():
            events_dir = path  # user đưa thẳng events/
        for p in events_dir.rglob("*.json"):
            if p.name.startswith("_") or ".amend." in p.name:
                continue
            try:
                with p.open(encoding="utf-8") as f:
                    mem = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            mid = mem.get("memory_id")
            if mid:
                memories[mid] = mem
    else:
        raise ValueError(f"Không nhận diện được source: {path} (phải là folder hoặc .tar.gz)")

    return memories


@dataclass
class ArchiveDiff:
    only_in_a: list[dict] = field(default_factory=list)
    only_in_b: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)  # same memory_id, different content
    in_both: list[str] = field(default_factory=list)

    @property
    def totals(self) -> dict:
        return {
            "only_in_a": len(self.only_in_a),
            "only_in_b": len(self.only_in_b),
            "conflicts": len(self.conflicts),
            "in_both": len(self.in_both),
        }

    def to_dict(self) -> dict:
        return {
            "totals": self.totals,
            "only_in_a": [{"memory_id": m["memory_id"],
                           "event_id": (m.get("event") or {}).get("event_id", ""),
                           "role": (m.get("perspective") or {}).get("role", "")}
                          for m in self.only_in_a],
            "only_in_b": [{"memory_id": m["memory_id"],
                           "event_id": (m.get("event") or {}).get("event_id", ""),
                           "role": (m.get("perspective") or {}).get("role", "")}
                          for m in self.only_in_b],
            "conflicts": self.conflicts,
            "in_both": self.in_both,
        }


def diff(a: dict[str, dict], b: dict[str, dict]) -> ArchiveDiff:
    r = ArchiveDiff()
    keys_a = set(a)
    keys_b = set(b)

    for mid in sorted(keys_a - keys_b):
        r.only_in_a.append(a[mid])
    for mid in sorted(keys_b - keys_a):
        r.only_in_b.append(b[mid])
    for mid in sorted(keys_a & keys_b):
        # Với content-addressing, cùng memory_id mà content khác = tamper
        if _canonical(a[mid]) == _canonical(b[mid]):
            r.in_both.append(mid)
        else:
            # Check xem memory_id có match hash thực không
            actual_a = compute_memory_id(a[mid])
            actual_b = compute_memory_id(b[mid])
            r.conflicts.append({
                "memory_id": mid,
                "a_content_hash": actual_a,
                "b_content_hash": actual_b,
                "note": ("Cùng memory_id nhưng content khác — có thể tamper "
                         "ở một bên, hoặc hash collision (cực hiếm)."),
            })
    return r


def render_markdown(r: ArchiveDiff, label_a: str, label_b: str) -> str:
    lines = ["# Archive diff", ""]
    lines.append(f"- **A**: `{label_a}`")
    lines.append(f"- **B**: `{label_b}`")
    lines.append("")
    t = r.totals
    lines.append(f"| | count |")
    lines.append(f"|---|---:|")
    lines.append(f"| Chỉ ở A | {t['only_in_a']} |")
    lines.append(f"| Chỉ ở B | {t['only_in_b']} |")
    lines.append(f"| Ở cả hai (identical) | {t['in_both']} |")
    lines.append(f"| ⚠ Conflict (cùng ID, khác content) | {t['conflicts']} |")
    lines.append("")

    if r.conflicts:
        lines.append("## ⚠ Conflicts (cần điều tra)")
        lines.append("")
        for c in r.conflicts:
            lines.append(f"- `{c['memory_id']}` — A hash={c['a_content_hash']}, B hash={c['b_content_hash']}")
        lines.append("")

    def _section(title: str, items: list[dict]) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("*(none)*")
            lines.append("")
            return
        for m in items[:30]:
            eid = (m.get("event") or {}).get("event_id", "")
            role = (m.get("perspective") or {}).get("role", "")
            lines.append(f"- `{m['memory_id']}` · event=`{eid}` · role={role}")
        if len(items) > 30:
            lines.append(f"- … +{len(items)-30} more")
        lines.append("")

    _section("Chỉ ở A", r.only_in_a)
    _section("Chỉ ở B", r.only_in_b)

    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("a", help="Archive folder hoặc bundle .tar.gz")
    p.add_argument("b", help="Archive folder hoặc bundle .tar.gz")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    a = _load_source(Path(args.a))
    b = _load_source(Path(args.b))
    r = diff(a, b)

    if args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_markdown(r, args.a, args.b))

    # Exit code: 0 nếu identical, 1 nếu có diff, 2 nếu có conflict
    if r.conflicts:
        return 2
    if r.only_in_a or r.only_in_b:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
