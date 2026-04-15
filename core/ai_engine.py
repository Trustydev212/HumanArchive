"""
HumanArchive — AI Engine

Chịu trách nhiệm phân tích ký ức mà không vi phạm 5 nguyên tắc bất biến
(xem docs/ethics.md).

Thiết kế:
    * Không phán xét đúng/sai (nguyên tắc 1)
    * Không bao giờ trả về trường "verdict", "guilty", "lying", ...
    * Luôn đồng cảm trước khi phân tích (nguyên tắc 3)
    * Ưu tiên phân tích động cơ (nguyên tắc 4)
    * Mọi output phải kèm trường `uncertainty` để độc giả biết độ không chắc chắn

Module này cố tình tách phần `LLMClient` ra interface để có thể thay thế
bằng nhiều backend khác nhau (Claude, local LLM, hoặc mock cho test).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Prompt fragments — tách riêng để dễ audit và dịch.
# --------------------------------------------------------------------------

EMPATHY_PREFIX_VI = (
    "Trước khi phân tích, hãy ghi nhận rằng người kể đã trải qua một sự kiện "
    "có thật. Đừng dùng ngôn ngữ lạnh lùng. Đừng kết luận ai đúng ai sai. "
    "Nhiệm vụ của bạn là HIỂU, không phải PHÁN XÉT."
)

EMPATHY_PREFIX_EN = (
    "Before analysis: acknowledge that the narrator lived through a real event. "
    "Do not use cold or clinical language. Do not conclude who is right or wrong. "
    "Your job is to UNDERSTAND, not to JUDGE."
)

MOTIVATION_PROMPT = (
    "Given this memory, describe in neutral and empathetic language:\n"
    "1. What the narrator perceived as their own motivation.\n"
    "2. What external pressures likely shaped the situation (if stated).\n"
    "3. What fears or constraints were in play.\n"
    "Never say the narrator 'really' meant something different from what they said. "
    "Your analysis is an interpretation offered alongside their words, never replacing them."
)


# --------------------------------------------------------------------------
# LLM backend interface
# --------------------------------------------------------------------------

class LLMClient(Protocol):
    """Interface tối thiểu cho một LLM backend. Cho phép thay đổi tự do."""

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str: ...


@dataclass
class EchoLLM:
    """LLM giả lập dùng trong test/offline. Không gọi mạng.

    Trả về một JSON string có cấu trúc hợp lệ để pipeline tiếp tục chạy.
    """

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        # Không phân tích thực sự — chỉ trả về một stub an toàn.
        return json.dumps(
            {
                "acknowledgement": "Tôi ghi nhận trải nghiệm của bạn.",
                "notes": "LLM backend chưa được cấu hình. Đây là output stub.",
                "uncertainty": "high",
            },
            ensure_ascii=False,
        )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _require(memory: dict, path: str) -> Any:
    """Truy cập trường bắt buộc trong memory, raise nếu thiếu."""
    node: Any = memory
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"Memory thiếu trường bắt buộc: {path}")
        node = node[part]
    return node


def _safe(memory: dict, path: str, default: Any = None) -> Any:
    node: Any = memory
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _format_memory_for_prompt(memory: dict) -> str:
    return json.dumps(
        {
            "event": memory.get("event"),
            "perspective": memory.get("perspective"),
            "memory": memory.get("memory"),
            "motivation": memory.get("motivation"),
            "context": memory.get("context"),
        },
        ensure_ascii=False,
        indent=2,
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

@dataclass
class MemoryAnalysis:
    """Kết quả phân tích một ký ức đơn lẻ."""

    memory_id: str
    acknowledgement: str  # Lời ghi nhận đồng cảm, PHẢI xuất hiện đầu tiên
    motivation_interpretation: str
    external_pressure_interpretation: str
    emotional_state_note: str
    uncertainty: str  # "low" | "medium" | "high"
    raw_llm_output: str = field(repr=False, default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "acknowledgement": self.acknowledgement,
            "motivation_interpretation": self.motivation_interpretation,
            "external_pressure_interpretation": self.external_pressure_interpretation,
            "emotional_state_note": self.emotional_state_note,
            "uncertainty": self.uncertainty,
        }


def analyze_memory(memory: dict, *, llm: LLMClient | None = None) -> MemoryAnalysis:
    """Phân tích một ký ức đơn lẻ, tập trung vào động cơ và trạng thái cảm xúc.

    KHÔNG kết luận đúng/sai. KHÔNG đánh giá độ tin cậy dựa trên vị trí xã hội.
    Luôn bắt đầu bằng lời ghi nhận đồng cảm.
    """
    if not _safe(memory, "consent.allow_ai_analysis", True):
        raise PermissionError(
            "Memory này được đóng góp với allow_ai_analysis=false. "
            "Tôn trọng consent — không phân tích."
        )

    memory_id = _require(memory, "memory_id")
    _require(memory, "motivation.your_motivation")  # nguyên tắc 4

    client = llm or EchoLLM()

    system_prompt = (
        f"{EMPATHY_PREFIX_VI}\n\n{EMPATHY_PREFIX_EN}\n\n"
        "Respond ONLY as a single JSON object with these fields: "
        '"acknowledgement", "motivation_interpretation", '
        '"external_pressure_interpretation", "emotional_state_note", '
        '"uncertainty" (one of "low"|"medium"|"high"). '
        "Never include a field named verdict, judgment, guilty, lying, or similar."
    )
    user_prompt = MOTIVATION_PROMPT + "\n\nMEMORY:\n" + _format_memory_for_prompt(memory)

    raw = client.complete(system_prompt, user_prompt)
    parsed = _parse_llm_json(raw)

    return MemoryAnalysis(
        memory_id=memory_id,
        acknowledgement=parsed.get("acknowledgement", ""),
        motivation_interpretation=parsed.get("motivation_interpretation", ""),
        external_pressure_interpretation=parsed.get("external_pressure_interpretation", ""),
        emotional_state_note=parsed.get("emotional_state_note", ""),
        uncertainty=parsed.get("uncertainty", "high"),
        raw_llm_output=raw,
    )


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse JSON từ output của LLM một cách phòng thủ."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Thử trích đoạn JSON đầu tiên nếu LLM trả về kèm văn bản.
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        log.warning("Không parse được JSON từ LLM, trả về dict rỗng.")
        return {}


# --------------------------------------------------------------------------
# Cross-reference
# --------------------------------------------------------------------------

@dataclass
class CrossReferenceReport:
    event_id: str
    memory_count: int
    roles_present: list[str]
    convergent_claims: list[dict[str, Any]]
    divergent_claims: list[dict[str, Any]]
    missing_perspectives: list[str]
    uncertainty: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "memory_count": self.memory_count,
            "roles_present": self.roles_present,
            "convergent_claims": self.convergent_claims,
            "divergent_claims": self.divergent_claims,
            "missing_perspectives": self.missing_perspectives,
            "uncertainty": self.uncertainty,
            "note": (
                "Báo cáo này KHÔNG kết luận ai đúng ai sai. "
                "Các điểm divergent chỉ phản ánh sự khác biệt trong trải nghiệm "
                "và góc nhìn của từng người. Mỗi góc nhìn đều có giá trị."
            ),
        }


ALL_ROLES = ("participant", "witness", "authority", "organizer", "victim", "bystander")


def cross_reference(memories: Iterable[dict], *, llm: LLMClient | None = None) -> CrossReferenceReport:
    """So khớp nhiều ký ức về cùng một sự kiện, tìm điểm trùng và điểm khác.

    KHÔNG xếp hạng sự đáng tin. KHÔNG nói ai "đúng". Chỉ trình bày.
    """
    memories = list(memories)
    if not memories:
        raise ValueError("cross_reference cần ít nhất 1 memory.")

    event_ids = {_require(m, "event.event_id") for m in memories}
    if len(event_ids) != 1:
        raise ValueError(
            f"Tất cả memories phải cùng event_id. Tìm thấy: {event_ids}"
        )
    event_id = next(iter(event_ids))

    roles_present = sorted({_safe(m, "perspective.role") for m in memories if _safe(m, "perspective.role")})
    missing = [r for r in ALL_ROLES if r not in roles_present]

    convergent, divergent = _compare_claims(memories, llm=llm)

    uncertainty = "low" if len(memories) >= 5 and len(roles_present) >= 3 else "medium" if len(memories) >= 2 else "high"

    return CrossReferenceReport(
        event_id=event_id,
        memory_count=len(memories),
        roles_present=roles_present,
        convergent_claims=convergent,
        divergent_claims=divergent,
        missing_perspectives=missing,
        uncertainty=uncertainty,
    )


def _compare_claims(memories: list[dict], *, llm: LLMClient | None) -> tuple[list[dict], list[dict]]:
    """So sánh các claim atomic trong từng memory.

    Triển khai v1: rút gọn thành so khớp keyword thô trên `what_happened`.
    v2 sẽ dùng LLM + atomic claim extraction.
    """
    from collections import Counter

    tokens_per_memory: list[set[str]] = []
    for m in memories:
        text = (_safe(m, "memory.what_happened") or "").lower()
        tokens = {w.strip(".,;:\"'!?") for w in text.split() if len(w) >= 5}
        tokens_per_memory.append(tokens)

    if not tokens_per_memory:
        return [], []

    # Convergent: tokens xuất hiện ở >= ceil(n/2) memories
    import math
    threshold = max(2, math.ceil(len(tokens_per_memory) / 2))
    counter: Counter[str] = Counter()
    for toks in tokens_per_memory:
        counter.update(toks)

    convergent = [
        {"claim_token": tok, "supported_by": count}
        for tok, count in counter.most_common(20)
        if count >= threshold
    ]

    # Divergent (v1 placeholder): chênh lệch thời gian/địa điểm nếu có
    divergent: list[dict] = []
    locations = {_safe(m, "event.location") for m in memories if _safe(m, "event.location")}
    if len(locations) > 1:
        divergent.append(
            {
                "claim": "Địa điểm cụ thể của sự kiện",
                "perspectives": [
                    {
                        "role": _safe(m, "perspective.role"),
                        "says": _safe(m, "event.location"),
                    }
                    for m in memories
                ],
                "note": "Không xác định đúng/sai. Người khác nhau có thể ở vùng khác nhau của cùng sự kiện.",
            }
        )

    return convergent, divergent


# --------------------------------------------------------------------------
# Historical entry generator
# --------------------------------------------------------------------------

def generate_historical_entry(event_id: str, *, archive_root: Path | str = "archive", llm: LLMClient | None = None) -> str:
    """Tạo một entry lịch sử đa góc nhìn từ tất cả memories của một event.

    Output là Markdown, nhằm đọc được bởi con người — kể cả các thế hệ sau.
    Mọi trích dẫn đều được dán nhãn role, không nêu danh tính.
    """
    root = Path(archive_root) / "events" / event_id
    if not root.exists():
        raise FileNotFoundError(f"Không tìm thấy event_id={event_id} trong {root}")

    memories: list[dict] = []
    for p in sorted(root.glob("*.json")):
        if p.name.startswith("_"):
            continue
        if ".amend." in p.name:
            continue
        with p.open(encoding="utf-8") as f:
            mem = json.load(f)
        if _safe(mem, "consent.withdrawn", False):
            continue
        if not _safe(mem, "consent.public", True):
            continue
        memories.append(mem)

    if not memories:
        return f"# {event_id}\n\n*Chưa có ký ức nào được công bố cho sự kiện này.*\n"

    report = cross_reference(memories, llm=llm)

    lines: list[str] = []
    lines.append(f"# Lịch sử đa góc nhìn — {event_id}")
    lines.append("")
    lines.append(
        "> *Entry này được tổng hợp từ nhiều ký ức cá nhân. Nó không thay thế "
        "các ký ức gốc, chỉ là một bản đồ để người đọc tự đi sâu hơn. "
        "Không có phán xét đúng/sai ở đây — chỉ có sự kiện được nhìn từ "
        "nhiều góc.*"
    )
    lines.append("")
    lines.append("## Tổng quan")
    lines.append("")
    lines.append(f"- **Số ký ức đã được công bố:** {report.memory_count}")
    lines.append(f"- **Các vai trò có mặt:** {', '.join(report.roles_present) or '(chưa có)'}")
    if report.missing_perspectives:
        lines.append(
            f"- **Các vai trò chưa có ký ức (cần được lắng nghe):** "
            f"{', '.join(report.missing_perspectives)}"
        )
    lines.append(f"- **Độ chắc chắn của tổng hợp:** {report.uncertainty}")
    lines.append("")

    lines.append("## Điểm trùng khớp giữa nhiều góc nhìn")
    lines.append("")
    if report.convergent_claims:
        for c in report.convergent_claims:
            lines.append(f"- `{c['claim_token']}` — được nhắc bởi {c['supported_by']} người kể.")
    else:
        lines.append("*Chưa tìm được điểm trùng rõ ràng.*")
    lines.append("")

    lines.append("## Điểm khác biệt giữa các góc nhìn")
    lines.append("")
    if report.divergent_claims:
        for d in report.divergent_claims:
            lines.append(f"### {d.get('claim', '(không tên)')}")
            for p in d.get("perspectives", []):
                lines.append(f"- **{p.get('role', '?')}** kể: {p.get('says', '')}")
            if d.get("note"):
                lines.append(f"> {d['note']}")
            lines.append("")
    else:
        lines.append("*Chưa phát hiện điểm khác biệt đáng kể.*")
    lines.append("")

    lines.append("## Các ký ức gốc (được ẩn danh)")
    lines.append("")
    for mem in memories:
        role = _safe(mem, "perspective.role", "?")
        lines.append(f"### Góc nhìn: **{role}**")
        lines.append("")
        what = _safe(mem, "memory.what_happened", "")
        lines.append(what.strip())
        lines.append("")
        motiv = _safe(mem, "motivation.your_motivation", "")
        if motiv:
            lines.append(f"> **Động cơ tự nhận:** {motiv}")
        pressure = _safe(mem, "motivation.external_pressure", "")
        if pressure:
            lines.append(f"> **Áp lực bên ngoài:** {pressure}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Nếu bạn cũng có ký ức về sự kiện này — dù nhỏ đến đâu — hãy đóng góp "
        "qua `tools/submit.py`. Mỗi góc nhìn đều làm bức tranh lịch sử khó bị "
        "bóp méo hơn.*"
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "LLMClient",
    "EchoLLM",
    "MemoryAnalysis",
    "CrossReferenceReport",
    "analyze_memory",
    "cross_reference",
    "generate_historical_entry",
]
