"""Vector index cho HumanArchive memories.

Thiết kế:
    * Chỉ index những memory ĐANG VIEWABLE (respect consent + embargo)
    * Chỉ index những memory có `allow_ai_analysis=true`
    * PII được scrub TRƯỚC KHI embed (không phải sau retrieve — khác RAG thường)
    * Retrieval role-balanced: lấy top-1 mỗi role thay vì top-k raw,
      tránh amplify bias
    * Lưu dưới dạng JSON đơn giản (không cần DB) — dễ mirror, dễ audit
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from ..integrity import allows_ai_analysis, is_publicly_viewable
from ..privacy import find_pii, pseudonymize
from .embedder import Embedder, get_default_embedder

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------

@dataclass
class IndexEntry:
    """Một chunk trong index. Không chứa PII."""

    memory_id: str
    event_id: str
    role: str
    text_scrubbed: str  # đã qua PII scrubber
    embedding: list[float]

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "event_id": self.event_id,
            "role": self.role,
            "text_scrubbed": self.text_scrubbed,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IndexEntry":
        return cls(**d)


@dataclass
class RAGIndex:
    """Toàn bộ vector index. JSON-serializable."""

    embedder_name: str
    dim: int
    built_at: str  # ISO date
    entries: list[IndexEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "embedder_name": self.embedder_name,
            "dim": self.dim,
            "built_at": self.built_at,
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class RAGHit:
    """Một kết quả retrieve."""

    entry: IndexEntry
    score: float

    def to_dict(self) -> dict:
        return {
            "memory_id": self.entry.memory_id,
            "event_id": self.entry.event_id,
            "role": self.entry.role,
            "text_scrubbed": self.entry.text_scrubbed,
            "score": self.score,
        }


# --------------------------------------------------------------------------
# Build index
# --------------------------------------------------------------------------

def _text_for_embedding(memory: dict) -> str:
    """Tập hợp các trường có nội dung ngữ nghĩa để embed."""
    parts: list[str] = []
    ev = memory.get("event") or {}
    if ev.get("name"):
        parts.append(ev["name"])

    mem = memory.get("memory") or {}
    for k in ("what_happened", "sensory_details", "emotional_state"):
        if mem.get(k):
            parts.append(str(mem[k]))

    motiv = memory.get("motivation") or {}
    for k in ("your_motivation", "external_pressure", "fears_at_the_time"):
        if motiv.get(k):
            parts.append(str(motiv[k]))

    ctx = memory.get("context") or {}
    for k in ("what_learned_after", "would_do_differently"):
        if ctx.get(k):
            parts.append(str(ctx[k]))

    return "\n\n".join(parts)


def _iter_memory_files(archive_root: Path | str) -> Iterable[Path]:
    root = Path(archive_root) / "events"
    if not root.exists():
        return
    for event_dir in sorted(root.iterdir()):
        if not event_dir.is_dir():
            continue
        for p in sorted(event_dir.glob("*.json")):
            if p.name.startswith("_") or ".amend." in p.name:
                continue
            yield p


def build_index(
    archive_root: Path | str = "archive",
    *,
    embedder: Embedder | None = None,
    as_of: date | None = None,
) -> RAGIndex:
    """Quét archive và build vector index.

    KHÔNG include memory nếu một trong các điều kiện sau không thoả:
        * `is_publicly_viewable(mem, as_of)` == True (consent.public + không withdrawn + qua embargo)
        * `allows_ai_analysis(mem)` == True

    PII trong text gốc được scrub trước khi embed.
    """
    emb = embedder or get_default_embedder()
    entries: list[IndexEntry] = []
    skipped = {"not_viewable": 0, "no_ai_consent": 0, "empty_text": 0}

    for p in _iter_memory_files(archive_root):
        try:
            with p.open(encoding="utf-8") as f:
                mem = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(mem, dict):
            continue

        if not is_publicly_viewable(mem, as_of=as_of):
            skipped["not_viewable"] += 1
            continue
        if not allows_ai_analysis(mem):
            skipped["no_ai_consent"] += 1
            continue

        raw_text = _text_for_embedding(mem)
        if not raw_text.strip():
            skipped["empty_text"] += 1
            continue

        # PII scrub TRƯỚC embedding
        findings = find_pii(raw_text)
        scrubbed = pseudonymize(raw_text, findings) if findings else raw_text
        vec = emb.embed(scrubbed)

        entries.append(
            IndexEntry(
                memory_id=str(mem.get("memory_id", "")),
                event_id=str((mem.get("event") or {}).get("event_id", "")),
                role=str((mem.get("perspective") or {}).get("role", "unknown")),
                text_scrubbed=scrubbed,
                embedding=vec,
            )
        )

    log.info(
        "RAG index built: %d entries, skipped %s",
        len(entries),
        skipped,
    )
    return RAGIndex(
        embedder_name=type(emb).__name__,
        dim=emb.dim,
        built_at=(as_of or date.today()).isoformat(),
        entries=entries,
    )


# --------------------------------------------------------------------------
# Save / load
# --------------------------------------------------------------------------

def save_index(index: RAGIndex, path: Path | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(index.to_dict(), f, ensure_ascii=False)


def load_index(path: Path | str) -> RAGIndex:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    return RAGIndex(
        embedder_name=data["embedder_name"],
        dim=data["dim"],
        built_at=data["built_at"],
        entries=[IndexEntry.from_dict(e) for e in data["entries"]],
    )


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------

def _cosine(a: list[float], b: list[float]) -> float:
    # Giả sử cả hai đã L2-normalized (mọi embedder của ta đều làm thế)
    return sum(x * y for x, y in zip(a, b))


def search(
    index: RAGIndex,
    query_embedding: list[float],
    *,
    k: int = 5,
    role_balance: bool = True,
    min_score: float = 0.0,
) -> list[RAGHit]:
    """Tìm top-k hits.

    role_balance=True: lấy top-1 từ mỗi role trước, sau đó mới top-k phần còn
    lại. Đảm bảo đa góc nhìn được đại diện, chống bias amplification.
    """
    if not index.entries:
        return []

    scored = [
        RAGHit(entry=e, score=_cosine(query_embedding, e.embedding))
        for e in index.entries
    ]
    scored.sort(key=lambda h: h.score, reverse=True)
    scored = [h for h in scored if h.score >= min_score]

    if not role_balance:
        return scored[:k]

    # Role-balanced: một best-hit mỗi role, rồi fill tiếp top-score
    picked: list[RAGHit] = []
    seen_roles: set[str] = set()
    remaining: list[RAGHit] = []

    for h in scored:
        if h.entry.role not in seen_roles:
            picked.append(h)
            seen_roles.add(h.entry.role)
            if len(picked) >= k:
                return picked
        else:
            remaining.append(h)

    # Chưa đủ k → fill từ remaining (vẫn theo score)
    for h in remaining:
        picked.append(h)
        if len(picked) >= k:
            break
    return picked


def search_text(
    index: RAGIndex,
    query: str,
    *,
    embedder: Embedder | None = None,
    k: int = 5,
    role_balance: bool = True,
) -> list[RAGHit]:
    """Convenience: scrub PII từ query → embed → search.

    Scrub query để chặn identity-probe attack (query chứa tên thật).
    """
    findings = find_pii(query)
    scrubbed_query = pseudonymize(query, findings) if findings else query
    emb = embedder or get_default_embedder()
    qvec = emb.embed(scrubbed_query)
    return search(index, qvec, k=k, role_balance=role_balance)
