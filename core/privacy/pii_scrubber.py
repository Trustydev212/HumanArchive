"""Phát hiện và đề xuất pseudonymize PII trong ký ức.

v1 dùng regex. v2 sẽ kết hợp LLM để phát hiện tên riêng theo ngữ cảnh
(ví dụ: "ông bí thư X" khi X không viết hoa).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

PIIKind = Literal["email", "phone", "national_id", "url", "person_name", "handle"]


# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Số điện thoại VN: +84..., 0..., 9-11 chữ số có thể có khoảng trắng/gạch
PHONE_RE = re.compile(
    r"(?:\+?84|0)[\s.-]?\d{2,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b"
)

# CCCD/CMND VN: chuỗi 9 hoặc 12 chữ số đứng một mình
NATIONAL_ID_RE = re.compile(r"(?<!\d)(?:\d{9}|\d{12})(?!\d)")

URL_RE = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",
    re.IGNORECASE,
)

# Handle mạng xã hội
HANDLE_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9_.]{3,30}\b")

# Tên: 2-4 token, mỗi token bắt đầu hoa. Phủ cả có dấu tiếng Việt.
# Không match khi token đầu là stop-word thường nằm đầu câu.
_SENTENCE_STARTERS = {
    "Tôi", "Chúng", "Anh", "Chị", "Ông", "Bà", "Cháu", "Con",
    "Nhưng", "Và", "Nếu", "Khi", "Lúc", "Vì", "Để", "Sau", "Trước",
    "Từ", "Ở", "Trong", "Ngoài", "Cả", "Mọi", "Mỗi", "Hôm", "Năm",
    "Ngày", "Sáng", "Chiều", "Tối", "Đêm",
    "The", "A", "An", "This", "That", "These", "Those",
    "I", "We", "You", "He", "She", "They", "My", "Our",
}
NAME_RE = re.compile(
    r"\b([A-ZÀ-Ỹ][a-zà-ỹ]+)(?:\s+([A-ZÀ-Ỹ][a-zà-ỹ]+)){1,3}\b"
)


# --------------------------------------------------------------------------
# Data class
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PIIFinding:
    """Một PII được phát hiện, kèm đề xuất pseudonym."""

    kind: PIIKind
    text: str
    start: int
    end: int
    replacement: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "replacement": self.replacement,
        }


# --------------------------------------------------------------------------
# Pseudonymization
# --------------------------------------------------------------------------

def _short_hash(text: str, n: int = 4) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def _pseudonym_for(kind: PIIKind, text: str) -> str:
    """Sinh chuỗi thay thế ổn định (cùng input → cùng output) nhưng không truy ngược."""
    tag = _short_hash(text)
    if kind == "email":
        return f"<email:{tag}>"
    if kind == "phone":
        return f"<phone:{tag}>"
    if kind == "national_id":
        return f"<id:{tag}>"
    if kind == "url":
        return f"<url:{tag}>"
    if kind == "handle":
        return f"<@{tag}>"
    if kind == "person_name":
        # Cắt chỉ giữ chữ cái đầu của token cuối (họ đầy đủ → "anh T.")
        parts = text.strip().split()
        if not parts:
            return "<person>"
        last = parts[-1][0]
        return f"<person:{last}.>"
    return f"<pii:{tag}>"


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------

def _add_findings(text: str, pat: re.Pattern[str], kind: PIIKind, out: list[PIIFinding]) -> None:
    for m in pat.finditer(text):
        matched = m.group(0)
        out.append(
            PIIFinding(
                kind=kind,
                text=matched,
                start=m.start(),
                end=m.end(),
                replacement=_pseudonym_for(kind, matched),
            )
        )


def _find_names(text: str, out: list[PIIFinding]) -> None:
    # Tách ra riêng vì cần lọc sentence starters để giảm false positive
    for m in NAME_RE.finditer(text):
        matched = m.group(0)
        first_token = matched.split(None, 1)[0]
        if first_token in _SENTENCE_STARTERS:
            continue
        # Bỏ nếu chỉ là 2 token mà token thứ 2 cũng là stop word
        tokens = matched.split()
        if len(tokens) >= 2 and tokens[1] in _SENTENCE_STARTERS:
            continue
        out.append(
            PIIFinding(
                kind="person_name",
                text=matched,
                start=m.start(),
                end=m.end(),
                replacement=_pseudonym_for("person_name", matched),
            )
        )


def find_pii(text: str) -> list[PIIFinding]:
    """Tìm mọi PII trong text, trả về danh sách theo thứ tự xuất hiện.

    Thứ tự ưu tiên khi chồng lắp: email/phone/id > url/handle > name.
    """
    if not text:
        return []

    findings: list[PIIFinding] = []
    # Thứ tự quan trọng: pattern cụ thể hơn đi trước, để khi chồng lắp
    # (ví dụ: số 12 chữ số vừa match phone vừa match national_id) cái cụ
    # thể hơn thắng trong dedupe.
    _add_findings(text, EMAIL_RE, "email", findings)
    _add_findings(text, NATIONAL_ID_RE, "national_id", findings)
    _add_findings(text, PHONE_RE, "phone", findings)
    _add_findings(text, URL_RE, "url", findings)
    _add_findings(text, HANDLE_RE, "handle", findings)
    _find_names(text, findings)

    # Dedupe/overlap: ưu tiên span xuất hiện trước; nếu chồng lên, bỏ span sau.
    findings.sort(key=lambda f: (f.start, -f.end))
    picked: list[PIIFinding] = []
    last_end = -1
    for f in findings:
        if f.start < last_end:
            continue
        picked.append(f)
        last_end = f.end
    return picked


# --------------------------------------------------------------------------
# Pseudonymize
# --------------------------------------------------------------------------

def pseudonymize(text: str, findings: list[PIIFinding] | None = None) -> str:
    """Trả về text đã thay PII bằng pseudonym.

    Nếu findings=None sẽ tự gọi find_pii(). Cho phép caller xem findings trước.
    """
    if findings is None:
        findings = find_pii(text)
    if not findings:
        return text

    # Thay từ cuối lên đầu để không invalidate offset
    result = text
    for f in sorted(findings, key=lambda f: f.start, reverse=True):
        result = result[: f.start] + f.replacement + result[f.end :]
    return result


def summarize_findings(findings: list[PIIFinding]) -> dict[str, int]:
    """Thống kê số lượng PII theo loại — để hiển thị cho người dùng."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    return counts
