#!/usr/bin/env python3
"""RAG query CLI.

Sử dụng:
    # Build index (chỉ cần làm lại khi archive thay đổi hoặc consent đổi)
    python tools/rag_query.py --build

    # Hỏi
    python tools/rag_query.py "tại sao lại xả đập?"
    python tools/rag_query.py --json "..."
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.rag import answer_question, build_index, load_index  # noqa: E402
from core.rag.index import save_index  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?", help="Câu hỏi. Bỏ qua nếu dùng --build.")
    p.add_argument("--build", action="store_true", help="Build/rebuild index.")
    p.add_argument("--index-path", default="archive/rag_index.json")
    p.add_argument("--archive", default="archive")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--json", action="store_true", help="Output JSON.")
    args = p.parse_args()

    if args.build:
        print("Building RAG index...", file=sys.stderr)
        index = build_index(args.archive)
        save_index(index, args.index_path)
        print(
            f"Built {len(index.entries)} entries ({index.embedder_name}, "
            f"dim={index.dim}) → {args.index_path}",
            file=sys.stderr,
        )
        if not args.query:
            return 0
    else:
        if not args.query:
            p.error("Cần --build hoặc cung cấp query.")

    idx_path = Path(args.index_path)
    if not idx_path.exists():
        print(
            f"Index chưa tồn tại. Chạy: python tools/rag_query.py --build",
            file=sys.stderr,
        )
        return 2

    index = load_index(idx_path)
    result = answer_question(args.query, index, k=args.k)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"Query (scrubbed): {result.question_scrubbed}")
    print(f"Uncertainty: {result.uncertainty}")
    print()
    print(result.answer)
    print()
    if result.citations:
        print("Citations:")
        for i, c in enumerate(result.citations, start=1):
            print(
                f"  [{i}] role={c.entry.role} | memory_id={c.entry.memory_id} | "
                f"event_id={c.entry.event_id} | score={c.score:.3f}"
            )
    if result.refused:
        print(f"\n(Refused: {result.refused})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
