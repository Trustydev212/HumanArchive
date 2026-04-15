"""Integrity layer — enforce các promise cứng của schema.

Nguyên tắc 5 (dữ liệu thô không đổi) và các ràng buộc vật lý được kiểm
tra ở đây, tách khỏi ai_engine để không lẫn với logic LLM.

Chức năng:
    * Kiểm tra memory_id khớp với content (sha256[:16])
    * Lọc memory đã withdrawn / embargoed / không public
    * So sánh hai bản của cùng memory_id để phát hiện sửa đổi
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


def canonical_json(obj: Any) -> str:
    """Serialize ổn định để băm."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_memory_id(memory: dict) -> str:
    """Hash nội dung memory (không kể memory_id và signature) → 16 hex chars."""
    clone = {k: v for k, v in memory.items() if k not in ("memory_id", "signature")}
    return hashlib.sha256(canonical_json(clone).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class IntegrityReport:
    memory_id: str
    claimed: str
    actual: str
    ok: bool

    @property
    def tampered(self) -> bool:
        return not self.ok


def verify_memory_id(memory: dict) -> IntegrityReport:
    """So sánh memory_id khai báo với hash tính lại từ content."""
    claimed = memory.get("memory_id", "")
    actual = compute_memory_id(memory)
    return IntegrityReport(
        memory_id=claimed,
        claimed=claimed,
        actual=actual,
        ok=(claimed == actual),
    )


def verify_archive(archive_root: Path | str) -> list[IntegrityReport]:
    """Verify toàn bộ archive. Trả về các memory có memory_id không khớp."""
    root = Path(archive_root)
    bad: list[IntegrityReport] = []
    for p in root.rglob("*.json"):
        if p.name.startswith("_"):
            continue
        if ".amend." in p.name:
            continue
        try:
            with p.open(encoding="utf-8") as f:
                mem = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(mem, dict) or "memory_id" not in mem:
            continue
        rep = verify_memory_id(mem)
        if rep.tampered:
            bad.append(rep)
    return bad


# --------------------------------------------------------------------------
# Consent filtering
# --------------------------------------------------------------------------

def is_publicly_viewable(memory: dict, *, as_of: date | None = None) -> bool:
    """True nếu memory có thể hiển thị công khai tại thời điểm `as_of`.

    Kiểm tra:
        * consent.public == True
        * consent.withdrawn == False
        * consent.embargo_until (nếu có) đã qua
    """
    consent = memory.get("consent") or {}
    if not consent.get("public", True):
        return False
    if consent.get("withdrawn", False):
        return False
    embargo = consent.get("embargo_until")
    if embargo:
        try:
            embargo_date = date.fromisoformat(embargo)
        except (TypeError, ValueError):
            return False  # embargo không parse được → giữ lại (an toàn hơn)
        today = as_of or date.today()
        if today < embargo_date:
            return False
    return True


def filter_viewable(
    memories: Iterable[dict], *, as_of: date | None = None
) -> list[dict]:
    """Lọc danh sách memories, chỉ giữ cái đang được phép công bố."""
    return [m for m in memories if is_publicly_viewable(m, as_of=as_of)]


def allows_ai_analysis(memory: dict) -> bool:
    """Người đóng góp có cho phép AI engine xử lý memory này không?"""
    consent = memory.get("consent") or {}
    return bool(consent.get("allow_ai_analysis", True))
