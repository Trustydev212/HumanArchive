"""Cross-check — trích xuất và so sánh các claim atomic giữa nhiều ký ức.

Một "atomic claim" là một phát biểu nhỏ nhất có thể kiểm chứng, ví dụ:
    - "có tiếng súng vào sáng sớm"
    - "chiếc xe tăng có số hiệu 390"
    - "tôi ở cách đó khoảng 200m"

v1 sử dụng heuristic thô. v2 sẽ dùng LLM để trích xuất claim có cấu trúc hơn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


TIME_PATTERNS = [
    re.compile(r"\b\d{1,2}[:h]\d{0,2}\s*(?:sáng|chiều|trưa|tối|am|pm)?\b", re.IGNORECASE),
    re.compile(r"\b(?:sáng|trưa|chiều|tối|đêm|rạng sáng)\b", re.IGNORECASE),
]

NUMBER_PATTERN = re.compile(r"\b\d{1,6}\b")


@dataclass(frozen=True)
class AtomicClaim:
    """Một phát biểu nhỏ trích từ một memory."""

    memory_id: str
    role: str
    kind: str  # "time" | "number" | "location" | "other"
    text: str

    def key(self) -> str:
        """Khóa để nhóm các claim 'cùng chủ đề'."""
        return f"{self.kind}:{self.text.lower().strip()}"


@dataclass
class ClaimComparison:
    """Kết quả so sánh một nhóm claim giữa nhiều memory."""

    kind: str
    claims: list[AtomicClaim] = field(default_factory=list)

    @property
    def distinct_texts(self) -> set[str]:
        return {c.text.lower().strip() for c in self.claims}

    @property
    def is_convergent(self) -> bool:
        return len(self.distinct_texts) == 1 and len(self.claims) >= 2

    @property
    def is_divergent(self) -> bool:
        return len(self.distinct_texts) >= 2

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "claim_count": len(self.claims),
            "convergent": self.is_convergent,
            "divergent": self.is_divergent,
            "by_role": [
                {"role": c.role, "text": c.text, "memory_id": c.memory_id}
                for c in self.claims
            ],
            "note": (
                "Không có phán xét đúng/sai. Sự khác biệt có thể đến từ "
                "vị trí quan sát, trí nhớ, ngôn ngữ, hoặc thời điểm kể lại."
            ),
        }


def extract_atomic_claims(memory: dict) -> list[AtomicClaim]:
    """Trích xuất các claim atomic từ một memory.

    v1: heuristic dựa trên regex cho thời gian, số liệu, địa điểm.
    """
    mem_id = memory.get("memory_id", "?")
    role = memory.get("perspective", {}).get("role", "?")
    text = memory.get("memory", {}).get("what_happened", "") or ""

    claims: list[AtomicClaim] = []

    for pat in TIME_PATTERNS:
        for m in pat.finditer(text):
            claims.append(AtomicClaim(mem_id, role, "time", m.group(0).strip()))

    for m in NUMBER_PATTERN.finditer(text):
        num = m.group(0)
        # Loại bỏ các số quá ngắn (năm 2 chữ số) vì nhiễu cao
        if len(num) >= 2:
            claims.append(AtomicClaim(mem_id, role, "number", num))

    location = memory.get("event", {}).get("location")
    if location:
        claims.append(AtomicClaim(mem_id, role, "location", location))

    return claims


def compare_claims(memories: Iterable[dict]) -> list[ClaimComparison]:
    """Gom các atomic claim theo `kind` và so sánh.

    Chỉ trả về các nhóm có >= 2 claim (có gì để so sánh).
    """
    from collections import defaultdict

    groups: dict[str, list[AtomicClaim]] = defaultdict(list)
    for mem in memories:
        for claim in extract_atomic_claims(mem):
            groups[claim.kind].append(claim)

    comparisons: list[ClaimComparison] = []
    for kind, claims in groups.items():
        if len(claims) < 2:
            continue
        comparisons.append(ClaimComparison(kind=kind, claims=claims))
    return comparisons
