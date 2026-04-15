#!/usr/bin/env python3
"""Staging CLI — quản lý inbox memories chờ review.

Workflow:
    1. Contributor submit → JSON vào staging/
    2. Reviewer chạy `python tools/staging.py list`
    3. Reviewer chạy `python tools/staging.py review <memory_id> --type approve`
       (hoặc --type request-changes với --note)
    4. Khi đủ N approvals → `python tools/staging.py merge <memory_id>`

Staging area:
    staging/
        <memory_id>.json                   # memory đang chờ
        reviews/<memory_id>/
            <annotation_id>.json           # mỗi review là annotation type=review

Quy tắc merge:
    - Đếm unique author_id có annotation type=review + content bắt đầu bằng "approve"
    - >= N thì cho phép merge
    - Merge = move memory vào archive/events/<event_id>/, và copy reviews
      sang archive/annotations/<memory_id>/ (để giữ audit trail)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.annotations import (  # noqa: E402
    create_annotation,
    load_annotations,
    save_annotation,
)
from core.integrity import verify_memory_id  # noqa: E402

DEFAULT_APPROVAL_THRESHOLD = 2


def _staging_path(root: Path) -> Path:
    return root / "staging"


def _review_dir(root: Path, memory_id: str) -> Path:
    return _staging_path(root) / "reviews" / memory_id


def cmd_list(root: Path) -> int:
    staging = _staging_path(root)
    if not staging.exists():
        print("(staging/ chưa tồn tại)")
        return 0
    items = list(staging.glob("*.json"))
    if not items:
        print("(không có memory nào đang chờ review)")
        return 0
    print(f"{'MEMORY_ID':<20} {'EVENT_ID':<40} {'ROLE':<12} APPROVALS")
    for p in sorted(items):
        try:
            with p.open(encoding="utf-8") as f:
                mem = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        mid = mem.get("memory_id", p.stem)
        eid = (mem.get("event") or {}).get("event_id", "?")
        role = (mem.get("perspective") or {}).get("role", "?")
        reviews = _load_reviews(root, mid)
        approvals = len([r for r in reviews if _is_approval(r)])
        print(f"{mid:<20} {eid[:40]:<40} {role:<12} {approvals}")
    return 0


def cmd_submit(root: Path, source: Path) -> int:
    with source.open(encoding="utf-8") as f:
        mem = json.load(f)
    rep = verify_memory_id(mem)
    if rep.tampered:
        print(f"memory_id không khớp content. claimed={rep.claimed} actual={rep.actual}")
        return 2
    staging = _staging_path(root)
    staging.mkdir(parents=True, exist_ok=True)
    dst = staging / f"{mem['memory_id']}.json"
    if dst.exists():
        print(f"memory {mem['memory_id']} đã trong staging.")
        return 0
    with dst.open("w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)
    print(f"Đã submit: {dst}")
    return 0


def cmd_review(
    root: Path, memory_id: str, kind: str, note: str, reviewer_id: str
) -> int:
    memory_path = _staging_path(root) / f"{memory_id}.json"
    if not memory_path.exists():
        print(f"Không tìm thấy memory {memory_id} trong staging.")
        return 2

    if kind not in ("approve", "request-changes", "comment"):
        print("--type phải là approve / request-changes / comment")
        return 2

    content = f"{kind}: {note}" if note else kind
    anno = create_annotation(
        target_memory_id=memory_id,
        author_id=reviewer_id,
        type="review",
        content=content,
    )
    # Lưu vào staging/reviews/<mid>/
    rdir = _review_dir(root, memory_id)
    rdir.mkdir(parents=True, exist_ok=True)
    path = rdir / f"{anno.annotation_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(anno.to_dict(), f, ensure_ascii=False, indent=2)

    reviews = _load_reviews(root, memory_id)
    approvals = len({r.author_id for r in reviews if _is_approval(r)})
    print(f"Review saved: {path}")
    print(f"Current approvals (unique reviewer_id): {approvals}")
    return 0


def cmd_merge(
    root: Path, memory_id: str, threshold: int = DEFAULT_APPROVAL_THRESHOLD
) -> int:
    memory_path = _staging_path(root) / f"{memory_id}.json"
    if not memory_path.exists():
        print(f"Không tìm thấy memory {memory_id}.")
        return 2

    reviews = _load_reviews(root, memory_id)
    approver_ids = {r.author_id for r in reviews if _is_approval(r)}
    if len(approver_ids) < threshold:
        print(
            f"Chưa đủ approvals: cần {threshold}, có {len(approver_ids)} "
            f"(from {len(approver_ids)} unique reviewers)"
        )
        return 3

    # Load memory để lấy event_id
    with memory_path.open(encoding="utf-8") as f:
        mem = json.load(f)
    eid = (mem.get("event") or {}).get("event_id")
    if not eid:
        print("Memory không có event_id — không thể merge.")
        return 2

    # Verify integrity lần cuối trước khi move
    if verify_memory_id(mem).tampered:
        print("Memory bị tamper — refuse merge.")
        return 2

    # Move sang archive/events/<eid>/
    dst_dir = root / "archive" / "events" / eid if (root / "archive").exists() else Path("archive") / "events" / eid
    # Nếu root đã là "archive" thì đừng thêm lần nữa
    if root.name == "archive":
        dst_dir = root / "events" / eid
    else:
        dst_dir = root / "archive" / "events" / eid
    # Cho phép override: nếu root/events/ đã tồn tại thì root là archive root
    if (root / "events").exists():
        dst_dir = root / "events" / eid

    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{memory_id}.json"
    if dst.exists():
        print(f"Memory đã tồn tại ở archive: {dst}")
        return 2
    shutil.move(str(memory_path), str(dst))

    # Copy reviews sang annotations/<mid>/ để audit trail
    src_reviews = _review_dir(root, memory_id)
    anno_root = dst_dir.parent.parent / "annotations" / memory_id
    anno_root.mkdir(parents=True, exist_ok=True)
    if src_reviews.exists():
        for p in src_reviews.glob("*.json"):
            target = anno_root / p.name
            if not target.exists():
                shutil.copy2(p, target)
        # Xoá review dir trong staging
        shutil.rmtree(src_reviews, ignore_errors=True)

    print(f"Merged → {dst}")
    print(f"Reviews preserved at: {anno_root}")
    return 0


# ------------------------------------------------------------------ helpers


def _load_reviews(root: Path, memory_id: str):
    rdir = _review_dir(root, memory_id)
    if not rdir.exists():
        return []
    annos = []
    for p in sorted(rdir.glob("*.json")):
        try:
            with p.open(encoding="utf-8") as f:
                d = json.load(f)
            from core.annotations import Annotation
            annos.append(Annotation.from_dict(d))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return annos


def _is_approval(anno) -> bool:
    return anno.type == "review" and anno.content.startswith("approve")


# ------------------------------------------------------------------ CLI


def main() -> int:
    p = argparse.ArgumentParser(description="Staging CLI cho HumanArchive.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list", help="Liệt kê memory đang chờ review.")
    ls.add_argument("--root", default=".")

    sb = sub.add_parser("submit", help="Đưa memory vào staging.")
    sb.add_argument("source", help="File .json memory")
    sb.add_argument("--root", default=".")

    rv = sub.add_parser("review", help="Ghi review cho memory.")
    rv.add_argument("memory_id")
    rv.add_argument(
        "--type", dest="kind", required=True,
        choices=["approve", "request-changes", "comment"],
    )
    rv.add_argument("--note", default="")
    rv.add_argument(
        "--reviewer", required=True,
        help="ID của reviewer (ổn định, có thể là handle hoặc pubkey hex).",
    )
    rv.add_argument("--root", default=".")

    mg = sub.add_parser("merge", help="Merge memory đã đủ approvals vào archive.")
    mg.add_argument("memory_id")
    mg.add_argument(
        "--threshold", type=int, default=DEFAULT_APPROVAL_THRESHOLD,
        help=f"Số approvals tối thiểu (default {DEFAULT_APPROVAL_THRESHOLD})",
    )
    mg.add_argument("--root", default=".")

    args = p.parse_args()
    root = Path(args.root)

    if args.cmd == "list":
        return cmd_list(root)
    if args.cmd == "submit":
        return cmd_submit(root, Path(args.source))
    if args.cmd == "review":
        return cmd_review(root, args.memory_id, args.kind, args.note, args.reviewer)
    if args.cmd == "merge":
        return cmd_merge(root, args.memory_id, threshold=args.threshold)
    return 1


if __name__ == "__main__":
    sys.exit(main())
