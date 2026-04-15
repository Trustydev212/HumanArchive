#!/usr/bin/env python3
"""Bulk import memories từ CSV hoặc JSONL.

Rất hữu ích khi bạn đã có oral history data ở dạng spreadsheet và muốn
migrate sang HumanArchive mà không phải submit từng memory bằng tay.

Sử dụng:
    # CSV (header row bắt buộc)
    humanarchive bulk-import memories.csv --dry-run
    humanarchive bulk-import memories.csv --target staging  # vào staging
    humanarchive bulk-import memories.csv --target archive  # thẳng archive (bỏ qua review)

    # JSONL (một memory JSON mỗi dòng)
    humanarchive bulk-import memories.jsonl --format jsonl

CSV columns (phải khớp tên):
    event_name, event_date, event_location, event_tags, event_categories,
    role, proximity, age, what_happened, sensory_details, emotional_state,
    your_motivation, external_pressure, fears, learned_after, would_different,
    public, embargo_until, allow_ai, language

CSV nên dùng UTF-8. Trường multi-value (tags, categories) ngăn cách bằng
`|` (pipe) để không conflict với CSV comma.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import compute_memory_id  # noqa: E402


CSV_COLUMNS = [
    "event_name", "event_date", "event_location", "event_tags", "event_categories",
    "role", "proximity", "age", "what_happened", "sensory_details",
    "emotional_state", "your_motivation", "external_pressure", "fears",
    "learned_after", "would_different",
    "public", "embargo_until", "allow_ai", "language",
]


def _new_contributor_id() -> str:
    return f"ha-{secrets.token_hex(2)}-{secrets.token_hex(2)}"


def _parse_bool(s: Any, default: bool) -> bool:
    if s is None or s == "":
        return default
    s = str(s).strip().lower()
    if s in ("true", "1", "yes", "y", "có", "co"):
        return True
    if s in ("false", "0", "no", "n", "không", "khong"):
        return False
    return default


def _parse_list(s: str | None) -> list[str] | None:
    if not s:
        return None
    # Pipe-separated để không conflict CSV comma
    parts = [p.strip() for p in s.split("|") if p.strip()]
    return parts or None


def _slugify(text: str) -> str:
    import re, unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:40] or "event"


def _compute_event_id(name: str, date: str) -> str:
    year = date[:4] if len(date) >= 4 and date[:4].isdigit() else "0000"
    slug = _slugify(name)
    h = hashlib.sha256(f"{year}-{slug}".encode()).hexdigest()[:4]
    return f"{year}-{slug}-{h}"


def row_to_memory(row: dict[str, Any]) -> tuple[dict | None, str | None]:
    """Chuyển một CSV row / JSONL line thành memory dict hợp lệ.

    Trả về (memory, None) nếu OK, (None, error_message) nếu fail.
    """
    try:
        name = (row.get("event_name") or "").strip()
        date = (row.get("event_date") or "").strip()
        role = (row.get("role") or "").strip()
        what = (row.get("what_happened") or "").strip()
        motiv = (row.get("your_motivation") or "").strip()

        if not name:
            return None, "event_name is required"
        if not date:
            return None, "event_date is required"
        if role not in ("participant", "witness", "authority",
                         "organizer", "victim", "bystander"):
            return None, f"invalid role: {role!r}"
        if len(what) < 20:
            return None, f"what_happened too short ({len(what)} < 20 chars)"
        if len(motiv) < 10:
            return None, f"your_motivation too short ({len(motiv)} < 10 — principle 4)"

        memory: dict = {
            "schema_version": "1.0",
            "contributor_id": row.get("contributor_id") or _new_contributor_id(),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "event": {
                "event_id": row.get("event_id") or _compute_event_id(name, date),
                "name": name,
                "date": date,
            },
            "perspective": {"role": role},
            "memory": {"what_happened": what},
            "motivation": {"your_motivation": motiv},
            "context": {},
            "consent": {
                "public": _parse_bool(row.get("public"), True),
                "embargo_until": (row.get("embargo_until") or "").strip() or None,
                "withdrawn": False,
                "allow_ai_analysis": _parse_bool(row.get("allow_ai"), True),
            },
            "language": (row.get("language") or "vi").strip() or "vi",
        }

        # Optional event fields
        loc = (row.get("event_location") or "").strip()
        if loc:
            memory["event"]["location"] = loc
        tags = _parse_list(row.get("event_tags"))
        if tags:
            memory["event"]["tags"] = tags
        cats = _parse_list(row.get("event_categories"))
        if cats:
            memory["event"]["categories"] = cats

        # Optional perspective fields
        prox = (row.get("proximity") or "").strip()
        if prox in ("direct", "nearby", "secondhand"):
            memory["perspective"]["proximity"] = prox
        age_raw = (row.get("age") or "").strip()
        if age_raw and age_raw.isdigit():
            memory["perspective"]["age_at_event"] = int(age_raw)

        # Optional memory fields
        for src, dst in [("sensory_details", "sensory_details"),
                          ("emotional_state", "emotional_state")]:
            v = (row.get(src) or "").strip()
            if v:
                memory["memory"][dst] = v

        # Optional motivation fields
        for src, dst in [("external_pressure", "external_pressure"),
                          ("fears", "fears_at_the_time")]:
            v = (row.get(src) or "").strip()
            if v:
                memory["motivation"][dst] = v

        # Optional context fields
        for src, dst in [("learned_after", "what_learned_after"),
                          ("would_different", "would_do_differently")]:
            v = (row.get(src) or "").strip()
            if v:
                memory["context"][dst] = v

        # Compute memory_id
        memory["memory_id"] = compute_memory_id(memory)
        return memory, None

    except Exception as exc:
        return None, f"unexpected error: {exc}"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig") as f:  # utf-8-sig handles BOM
        # Skip lines starting with # (comments) — DictReader không tự làm
        filtered = (ln for ln in f if not ln.lstrip().startswith("#"))
        reader = csv.DictReader(filtered)
        return list(reader)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {i}: {exc}") from exc
    return rows


def bulk_import(
    source: Path,
    *,
    format: str = "auto",
    target: str = "staging",
    archive_root: Path = Path("archive"),
    dry_run: bool = False,
) -> dict:
    """Read source file, build memories, write (or report).

    target: 'staging' (review trước) hoặc 'archive' (bypass review).
    """
    if format == "auto":
        format = "jsonl" if source.suffix.lower() in (".jsonl", ".ndjson") else "csv"

    if format == "csv":
        rows = _read_csv(source)
    elif format == "jsonl":
        rows = _read_jsonl(source)
    else:
        raise ValueError(f"Unsupported format: {format}")

    imported: list[dict] = []
    failed: list[dict] = []

    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            failed.append({"row": i, "error": "not a dict"})
            continue
        mem, err = row_to_memory(row)
        if err:
            failed.append({"row": i, "error": err,
                           "hint_name": row.get("event_name", "?")})
            continue
        imported.append(mem)

    # Write
    written: list[str] = []
    if not dry_run:
        if target == "staging":
            dst_dir = Path("staging")
            dst_dir.mkdir(parents=True, exist_ok=True)
            for mem in imported:
                path = dst_dir / f"{mem['memory_id']}.json"
                if path.exists():
                    continue  # dedup
                path.write_text(
                    json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                written.append(str(path))
        elif target == "archive":
            for mem in imported:
                eid = mem["event"]["event_id"]
                d = archive_root / "events" / eid
                d.mkdir(parents=True, exist_ok=True)
                path = d / f"{mem['memory_id']}.json"
                if path.exists():
                    continue
                path.write_text(
                    json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                written.append(str(path))
        else:
            raise ValueError(f"Invalid target: {target}")

    return {
        "source": str(source),
        "format": format,
        "target": target if not dry_run else "dry-run",
        "rows_read": len(rows),
        "imported": len(imported),
        "failed": len(failed),
        "written_paths": written,
        "errors": failed,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Bulk import memories từ CSV/JSONL.")
    p.add_argument("source", help="Đường dẫn file CSV hoặc JSONL")
    p.add_argument(
        "--format", choices=["auto", "csv", "jsonl"], default="auto",
        help="Override auto-detect",
    )
    p.add_argument(
        "--target", choices=["staging", "archive"], default="staging",
        help="staging = vào staging/ (review trước khi merge, default). "
             "archive = thẳng archive/ (bypass review — chỉ dùng khi bạn là "
             "operator và đã review offline)",
    )
    p.add_argument("--archive", default="archive",
                   help="Archive root (khi --target archive)")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate nhưng không ghi file nào")
    p.add_argument("--json", action="store_true", help="Output JSON")
    args = p.parse_args()

    try:
        result = bulk_import(
            Path(args.source),
            format=args.format,
            target=args.target,
            archive_root=Path(args.archive),
            dry_run=args.dry_run,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Source: {result['source']} ({result['format']})")
    print(f"Rows read:  {result['rows_read']}")
    print(f"Imported:   {result['imported']}")
    print(f"Failed:     {result['failed']}")
    print(f"Target:     {result['target']}")
    if result["written_paths"]:
        print(f"Wrote {len(result['written_paths'])} files, first 5:")
        for p in result["written_paths"][:5]:
            print(f"  {p}")
    if result["errors"]:
        print(f"\nErrors ({len(result['errors'])}):")
        for e in result["errors"][:10]:
            print(f"  row {e['row']}: {e['error']} (hint: {e.get('hint_name', '?')})")
        if len(result["errors"]) > 10:
            print(f"  … +{len(result['errors']) - 10} more")

    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
