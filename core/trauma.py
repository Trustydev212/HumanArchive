"""Trauma detection & content warnings.

Nguyên tắc 3: LUÔN đồng cảm trước khi phân tích. Một phần của "đồng cảm"
là cảnh báo người đọc trước khi họ đọc nội dung nặng, và nhắc nhở AI
engine điều chỉnh tone cho phù hợp.

v1: keyword-based. Đủ để hiển thị content warning ở UI; v2 sẽ dùng LLM
để phân loại mức độ chi tiết hơn.

KHÔNG phán xét, KHÔNG gatekeep — ký ức vẫn được lưu và hiển thị. Cảnh
báo chỉ để người đọc chuẩn bị tinh thần.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TraumaCategory = Literal[
    "violence",
    "death",
    "sexual_violence",
    "torture",
    "child_harm",
    "self_harm",
    "displacement",
    "imprisonment",
    "discrimination",
]

# Các từ khoá — cả tiếng Việt và tiếng Anh. Cố ý bao gồm các biến thể cơ bản.
_KEYWORDS: dict[TraumaCategory, list[str]] = {
    "violence": [
        "đánh đập", "hành hung", "bạo lực", "đấm", "đá", "đập",
        "beating", "assault", "violence", "beaten",
    ],
    "death": [
        "chết", "qua đời", "thiệt mạng", "tử vong", "giết", "chôn",
        "died", "killed", "death", "corpse", "buried",
    ],
    "sexual_violence": [
        "hiếp dâm", "cưỡng hiếp", "xâm hại tình dục",
        "rape", "sexual assault", "molested",
    ],
    "torture": [
        "tra tấn", "hành hạ", "đánh đập dã man",
        "torture", "tortured",
    ],
    "child_harm": [
        "trẻ em bị", "đánh trẻ", "ngược đãi trẻ",
        "child abuse", "abused as a child",
    ],
    "self_harm": [
        "tự tử", "tự sát", "tự làm hại", "cắt tay",
        "suicide", "self-harm", "self harm",
    ],
    "displacement": [
        "chạy loạn", "sơ tán", "tị nạn", "mất nhà",
        "displaced", "refugee", "fled", "evacuated",
    ],
    "imprisonment": [
        "bắt giam", "tù cải tạo", "tù đày", "giam cầm", "nhà tù",
        "imprisoned", "jailed", "detained", "prison camp",
    ],
    "discrimination": [
        "kỳ thị", "phân biệt đối xử", "bị gạt ra",
        "discriminated", "racism", "bigotry",
    ],
}


@dataclass
class TraumaAssessment:
    """Kết quả phát hiện trauma trong một memory."""

    categories: list[TraumaCategory]
    severity: Literal["none", "mild", "severe"]

    @property
    def has_trauma(self) -> bool:
        return self.severity != "none"

    def content_warning(self) -> str:
        """Chuỗi hiển thị cảnh báo bằng tiếng Việt."""
        if not self.has_trauma:
            return ""
        labels = {
            "violence": "bạo lực",
            "death": "cái chết",
            "sexual_violence": "bạo lực tình dục",
            "torture": "tra tấn",
            "child_harm": "tổn hại trẻ em",
            "self_harm": "tự làm hại",
            "displacement": "mất nhà, tị nạn",
            "imprisonment": "bị giam cầm",
            "discrimination": "kỳ thị, phân biệt đối xử",
        }
        names = ", ".join(labels[c] for c in self.categories)
        prefix = "Cảnh báo nội dung" if self.severity == "mild" else "CẢNH BÁO NỘI DUNG NẶNG"
        return f"⚠ {prefix}: ký ức dưới đây có thể mô tả {names}. Hãy cân nhắc trước khi đọc tiếp."

    def to_dict(self) -> dict:
        return {
            "categories": list(self.categories),
            "severity": self.severity,
            "content_warning": self.content_warning(),
        }


# --------------------------------------------------------------------------

_SEVERE_CATEGORIES = frozenset([
    "sexual_violence", "torture", "child_harm", "self_harm",
])


def detect_trauma(memory: dict) -> TraumaAssessment:
    """Quét các trường tự do trong memory, phân loại trauma.

    Severity:
        * "severe" — chạm vào bất kỳ category nào trong _SEVERE_CATEGORIES
        * "mild"   — chỉ chạm vào category nhẹ hơn
        * "none"   — không chạm gì
    """
    text_parts: list[str] = []
    mem = memory.get("memory") or {}
    for key in ("what_happened", "sensory_details", "emotional_state"):
        val = mem.get(key)
        if val:
            text_parts.append(str(val))
    motiv = memory.get("motivation") or {}
    for key in ("your_motivation", "external_pressure", "fears_at_the_time"):
        val = motiv.get(key)
        if val:
            text_parts.append(str(val))

    blob = " ".join(text_parts).lower()
    if not blob:
        return TraumaAssessment(categories=[], severity="none")

    hits: list[TraumaCategory] = []
    for cat, keywords in _KEYWORDS.items():
        if any(kw in blob for kw in keywords):
            hits.append(cat)

    if not hits:
        return TraumaAssessment(categories=[], severity="none")

    severity: Literal["none", "mild", "severe"] = "mild"
    if any(c in _SEVERE_CATEGORIES for c in hits):
        severity = "severe"

    return TraumaAssessment(categories=hits, severity=severity)
