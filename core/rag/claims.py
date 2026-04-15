"""LLM-aided atomic claim extraction cho cross_reference.

v1 dùng token overlap thô — nhiều false positive (stopword tiếng Việt
như "chúng", "tôi", "không" nhảy vào convergent_claims) và miss các
claim thực sự có cấu trúc.

v2 dùng Claude với structured output để trích atomic claims có kind:
    time:     "vào lúc 10h30 sáng"
    location: "ở Dinh Độc Lập"
    quantity: "ba chiếc xe tăng"
    person_action: "chỉ huy ra lệnh xả đập"
    causation:     "vì không kịp báo trước cho xã"
    observation:   "nước dâng tới mái nhà trong 30 phút"

Fallback: nếu LLM không available → dùng atomic claim extractor
keyword-based ở core/verification/cross_check.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from ..llm import ClaudeClient, get_default_client
from ..verification.cross_check import extract_atomic_claims as extract_regex

log = logging.getLogger(__name__)

ClaimKind = Literal[
    "time", "location", "quantity", "person_action", "causation",
    "observation", "other",
]


@dataclass
class SemanticClaim:
    """Atomic claim được LLM phân loại."""

    memory_id: str
    role: str
    kind: ClaimKind
    text: str
    confidence: str  # low | medium | high

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "role": self.role,
            "kind": self.kind,
            "text": self.text,
            "confidence": self.confidence,
        }


_PROMPT = """Bạn đang trích các atomic claim từ một ký ức cá nhân. Mỗi
claim là một phát biểu nhỏ nhất có thể so khớp với các ký ức khác về
cùng sự kiện.

Phân loại theo các kind:
- time: thời điểm, thời lượng, thứ tự thời gian ("10h30 sáng", "sau 2 giờ")
- location: địa điểm cụ thể ("ở Dinh Độc Lập", "trên đồi phía bắc")
- quantity: số lượng ("ba chiếc xe", "khoảng 50 người")
- person_action: ai làm gì ("lính canh ra lệnh rút lui")
- causation: vì sao ("do đập vỡ bất ngờ")
- observation: quan sát trực tiếp ("nước dâng tới mái nhà")
- other: không thuộc các loại trên

QUAN TRỌNG:
- KHÔNG phán xét claim đúng/sai.
- KHÔNG kết luận người kể "nhớ nhầm" hoặc "chính xác".
- CHỈ trích dẫn, không paraphrase quá xa bản gốc.

Trả về JSON duy nhất:
{
  "claims": [
    {"kind": "time", "text": "10h30 sáng", "confidence": "high"},
    {"kind": "location", "text": "trên đồi phía bắc", "confidence": "medium"}
  ]
}

confidence: low nếu claim mơ hồ ("sáng sớm"), high nếu cụ thể ("10h30").
"""


_VALID_KINDS: frozenset[str] = frozenset([
    "time", "location", "quantity", "person_action",
    "causation", "observation", "other",
])


def extract_claims_llm(
    memory: dict, *, llm: ClaudeClient | None = None
) -> list[SemanticClaim]:
    """Trích claim bằng LLM. Nếu fail → fallback extract_regex()."""
    mem_id = str(memory.get("memory_id", "?"))
    role = str((memory.get("perspective") or {}).get("role", "?"))

    text = (memory.get("memory") or {}).get("what_happened") or ""
    if not text.strip():
        return []

    client = llm or get_default_client()

    try:
        parsed = client.complete_json(_PROMPT + "\n\nKÝ ỨC:\n" + text)
    except Exception as exc:
        log.debug("LLM claim extraction fallback → regex: %s", exc)
        return _from_regex_fallback(memory)

    if not isinstance(parsed, dict):
        return _from_regex_fallback(memory)

    items = parsed.get("claims") or []
    if not isinstance(items, list):
        return _from_regex_fallback(memory)

    out: list[SemanticClaim] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "other"))
        if kind not in _VALID_KINDS:
            kind = "other"
        text_val = str(item.get("text", "")).strip()
        if not text_val:
            continue
        conf = item.get("confidence", "medium")
        if conf not in ("low", "medium", "high"):
            conf = "medium"
        out.append(SemanticClaim(
            memory_id=mem_id, role=role, kind=kind,  # type: ignore[arg-type]
            text=text_val, confidence=conf,
        ))
    # Nếu LLM trả về empty, vẫn fallback về regex (có thể LLM chưa cấu hình)
    if not out:
        return _from_regex_fallback(memory)
    return out


def _from_regex_fallback(memory: dict) -> list[SemanticClaim]:
    """Khi không có LLM, dùng regex extractor cũ để giữ chức năng."""
    regex_claims = extract_regex(memory)
    kind_map = {
        "time": "time",
        "number": "quantity",
        "location": "location",
    }
    out: list[SemanticClaim] = []
    for c in regex_claims:
        mapped: ClaimKind = kind_map.get(c.kind, "other")  # type: ignore[assignment]
        out.append(SemanticClaim(
            memory_id=c.memory_id,
            role=c.role,
            kind=mapped,
            text=c.text,
            confidence="low",  # regex → low confidence mặc định
        ))
    return out


def compare_semantic_claims(
    memories: list[dict], *, llm: ClaudeClient | None = None
) -> dict:
    """Trích claim từ mỗi memory, so khớp theo kind, trả convergent/divergent.

    Format output để drop-in thay cho _compare_claims() cũ trong ai_engine.
    """
    from collections import defaultdict

    all_claims: list[SemanticClaim] = []
    for m in memories:
        all_claims.extend(extract_claims_llm(m, llm=llm))

    # Group theo (kind, lowercased text)
    groups: dict[tuple[str, str], list[SemanticClaim]] = defaultdict(list)
    for c in all_claims:
        groups[(c.kind, c.text.lower().strip())].append(c)

    convergent: list[dict] = []
    divergent_by_kind: dict[str, list[SemanticClaim]] = defaultdict(list)

    for (kind, _), claims in groups.items():
        if len({c.memory_id for c in claims}) >= 2:
            convergent.append({
                "kind": kind,
                "claim_text": claims[0].text,
                "supported_by": len({c.memory_id for c in claims}),
                "roles": sorted({c.role for c in claims}),
                "confidences": sorted({c.confidence for c in claims}),
            })

    # Divergent: cùng kind ở nhiều memory nhưng text khác nhau
    all_texts_by_kind: dict[str, list[SemanticClaim]] = defaultdict(list)
    for c in all_claims:
        all_texts_by_kind[c.kind].append(c)

    divergent: list[dict] = []
    for kind, claims in all_texts_by_kind.items():
        distinct = {c.text.lower().strip() for c in claims}
        if len(distinct) >= 2 and len({c.memory_id for c in claims}) >= 2:
            divergent.append({
                "kind": kind,
                "perspectives": [
                    {"role": c.role, "says": c.text, "confidence": c.confidence,
                     "memory_id": c.memory_id}
                    for c in claims
                ],
                "note": ("Không xác định đúng/sai. Sự khác biệt có thể do "
                         "vị trí quan sát, trí nhớ, hoặc thời điểm kể lại."),
            })

    return {
        "convergent_claims": convergent,
        "divergent_claims": divergent,
        "total_claims_extracted": len(all_claims),
    }


__all__ = [
    "SemanticClaim",
    "extract_claims_llm",
    "compare_semantic_claims",
]
