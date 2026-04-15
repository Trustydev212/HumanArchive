"""LLM-aided trauma classification.

Keyword-based detector có false positive ("giết thời gian" trigger
"death"). LLM có thể phân loại nuanced hơn:
    * Hiểu ngữ cảnh ("chúng tôi giết thời gian chơi cờ" ≠ trauma)
    * Phát hiện trauma implicit ("không ai dám nhắc đến đêm đó nữa")
    * Xác định severity dựa trên cường độ mô tả

Graceful fallback: nếu LLM không available → dùng keyword detector.
"""

from __future__ import annotations

import logging
from typing import Literal

from .llm import ClaudeClient, get_default_client
from .trauma import TraumaAssessment, detect_trauma

log = logging.getLogger(__name__)


_TRAUMA_PROMPT = """Bạn đang đánh giá xem một ký ức có mô tả trải nghiệm
đau thương không, để hiển thị content warning (không phải để filter hay
từ chối). Đừng lấn át, đừng moralize — chỉ phân loại.

Các category:
- violence — bạo lực thân thể
- death — cái chết, mất người
- sexual_violence — bạo lực tình dục
- torture — tra tấn
- child_harm — tổn hại trẻ em
- self_harm — tự làm hại bản thân
- displacement — mất nhà, tị nạn
- imprisonment — bị giam cầm, tù đày
- discrimination — bị kỳ thị, phân biệt đối xử

Severity:
- none — không có trauma
- mild — có yếu tố gây khó chịu nhưng không quá nặng
- severe — trauma nghiêm trọng (sexual_violence, torture, child_harm,
  self_harm, hoặc death/violence được mô tả chi tiết cảnh tượng)

CHỈ PHÂN LOẠI, đừng bình luận về việc đó đáng lên án/thông cảm hay không.

Trả về JSON duy nhất:
{
  "categories": ["death", "displacement"],
  "severity": "severe",
  "note": "(tuỳ chọn) giải thích ngắn tại sao chọn severity này"
}

Nếu không có trauma: {"categories": [], "severity": "none"}
"""


_VALID_CATEGORIES = frozenset([
    "violence", "death", "sexual_violence", "torture", "child_harm",
    "self_harm", "displacement", "imprisonment", "discrimination",
])


def llm_classify_trauma(
    memory: dict, *, llm: ClaudeClient | None = None
) -> TraumaAssessment:
    """Phân loại trauma bằng LLM, fallback keyword nếu LLM không available.

    Return TraumaAssessment giống detect_trauma() để drop-in replacement.
    """
    # Ghép các trường văn tự do
    parts: list[str] = []
    mem = memory.get("memory") or {}
    for key in ("what_happened", "sensory_details", "emotional_state"):
        val = mem.get(key)
        if val:
            parts.append(str(val))
    motiv = memory.get("motivation") or {}
    for key in ("your_motivation", "external_pressure", "fears_at_the_time"):
        val = motiv.get(key)
        if val:
            parts.append(str(val))

    blob = "\n\n".join(parts)
    if not blob.strip():
        return TraumaAssessment(categories=[], severity="none")

    client = llm or get_default_client()

    try:
        parsed = client.complete_json(_TRAUMA_PROMPT + "\n\nKÝ ỨC:\n" + blob)
    except Exception as exc:
        log.debug("LLM trauma classify fallback → keyword: %s", exc)
        return detect_trauma(memory)

    if not isinstance(parsed, dict):
        return detect_trauma(memory)

    raw_cats = parsed.get("categories") or []
    severity = parsed.get("severity") or "none"

    # Validate
    cats = [c for c in raw_cats if c in _VALID_CATEGORIES]
    if severity not in ("none", "mild", "severe"):
        severity = "none"
    if not cats and severity != "none":
        severity = "none"

    # Type narrow cho dataclass
    sev: Literal["none", "mild", "severe"] = severity  # type: ignore[assignment]
    return TraumaAssessment(categories=cats, severity=sev)  # type: ignore[arg-type]
