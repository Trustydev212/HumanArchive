#!/usr/bin/env python3
"""Verify ed25519 signatures trên tất cả annotations.

Chạy qua mọi annotation trong archive/annotations/, verify:
    - annotation có signature hay không
    - Signature verify được (nếu có)
    - Pubkey của reviewer có trong trust/reviewers.json hay không
    - Status của reviewer là active hay revoked

Output: Markdown report + exit code (0 = OK, 1 = có warning, 2 = có error).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.annotations import iter_all_annotations, verify_annotation  # noqa: E402


def _load_trust(path: Path) -> dict[str, dict]:
    """handle → reviewer entry."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {r["handle"]: r for r in data.get("reviewers", [])}


def _pubkey_of(trust: dict[str, dict], author_id: str) -> tuple[str | None, str]:
    """Tìm pubkey của author_id. Returns (pubkey_hex_or_None, status)."""
    # author_id có thể là handle hoặc pubkey trực tiếp
    if author_id in trust:
        r = trust[author_id]
        return r.get("pubkey_ed25519_hex"), r.get("status", "unknown")
    # Thử: author_id là pubkey trực tiếp
    for r in trust.values():
        if r.get("pubkey_ed25519_hex") == author_id:
            return author_id, r.get("status", "unknown")
    return None, "not_in_trust"


def verify_all(archive_root: Path, trust_path: Path) -> dict:
    trust = _load_trust(trust_path)
    report: dict = {
        "annotations_total": 0,
        "annotations_signed": 0,
        "annotations_unsigned": 0,
        "signatures_valid": 0,
        "signatures_invalid": [],
        "authors_unknown": [],
        "authors_revoked": [],
    }

    for anno in iter_all_annotations(archive_root):
        report["annotations_total"] += 1
        if not anno.signature:
            report["annotations_unsigned"] += 1
            continue
        report["annotations_signed"] += 1

        pubkey, status = _pubkey_of(trust, anno.author_id)
        if pubkey is None:
            report["authors_unknown"].append({
                "annotation_id": anno.annotation_id,
                "author_id": anno.author_id,
                "type": anno.type,
            })
            continue

        if status == "revoked":
            report["authors_revoked"].append({
                "annotation_id": anno.annotation_id,
                "author_id": anno.author_id,
                "target": anno.target_memory_id,
            })
            # Vẫn check signature — revoked không có nghĩa là invalid
        if verify_annotation(anno, pubkey):
            report["signatures_valid"] += 1
        else:
            report["signatures_invalid"].append({
                "annotation_id": anno.annotation_id,
                "author_id": anno.author_id,
                "pubkey_hex": pubkey[:16] + "...",
            })

    return report


def render_markdown(r: dict) -> str:
    lines = ["# Signature verification report", ""]
    lines.append(f"- Total annotations: **{r['annotations_total']}**")
    lines.append(f"  - Signed: {r['annotations_signed']}")
    lines.append(f"  - Unsigned: {r['annotations_unsigned']}")
    lines.append(f"- Valid signatures: **{r['signatures_valid']}**")
    lines.append(f"- Invalid signatures: **{len(r['signatures_invalid'])}**")
    lines.append(f"- Authors not in trust list: **{len(r['authors_unknown'])}**")
    lines.append(f"- Authors revoked: **{len(r['authors_revoked'])}**")
    lines.append("")

    def _section(title: str, items: list[dict]) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for it in items[:20]:
            lines.append(f"- `{it.get('annotation_id', '')}` — {json.dumps(it, ensure_ascii=False)}")
        if len(items) > 20:
            lines.append(f"- … +{len(items)-20} more")
        lines.append("")

    _section("⚠ Invalid signatures", r["signatures_invalid"])
    _section("Authors unknown (không trong trust list)", r["authors_unknown"])
    _section("Annotations from revoked authors", r["authors_revoked"])

    if not r["signatures_invalid"] and not r["authors_unknown"]:
        lines.append("## ✓ Tất cả OK")
        lines.append("")
        lines.append("Mọi annotation có signature đều verify được; mọi author "
                     "có signature đều trong trust list.")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default="archive")
    p.add_argument("--trust-file", default="trust/reviewers.json")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    r = verify_all(Path(args.archive), Path(args.trust_file))
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(r))

    # Exit code
    if r["signatures_invalid"]:
        return 2
    if r["authors_unknown"] or r["authors_revoked"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
