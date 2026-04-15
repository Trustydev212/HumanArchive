"""LLM-aided PII detection — bổ sung regex scrubber.

Regex bắt được tên đủ chuẩn ("Nguyễn Văn An"), không bắt được:
    * Tên viết rời/typo: "ng.v.an", "anh T rú", "N.V.An"
    * Tên không viết hoa: "gặp ông bí thư xã minh ở đó"
    * Địa danh quá cụ thể có thể identify người: "nhà số 45 ngõ Y"
    * Biệt danh: "gặp 'chú Tư' ở chợ"
    * Chức danh duy nhất: "ông trưởng phòng năm 1995"

Module này dùng Claude để tìm thêm các loại PII contextual mà regex miss.

Quan trọng: LLM check CHỈ THÊM findings, không ghi đè/xoá regex findings.
Nếu LLM API không available → return [] (graceful fallback). Regex vẫn chạy.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..llm import ClaudeClient, get_default_client
from .pii_scrubber import PIIFinding, _pseudonym_for  # reuse pseudonym logic

log = logging.getLogger(__name__)


_LLM_PII_PROMPT = """Bạn đang rà soát một đoạn văn để tìm các thông tin có thể
xác định danh tính (PII) mà regex thông thường có thể bỏ sót.

Đặc biệt chú ý:
1. Tên viết rời (ng.v.an, anh T rú, N.V.An)
2. Tên không viết hoa (bí thư xã minh)
3. Biệt danh có thể định danh ("chú Tư của xóm B")
4. Chức danh + thời điểm duy nhất có thể định danh ("trưởng phòng năm 1995")
5. Địa chỉ cụ thể (số nhà, ngõ, hẻm cụ thể)
6. Số hiệu định danh (biển số xe, số đơn vị quân đội...)

KHÔNG báo cáo:
- Tên địa danh lớn (tỉnh, thành phố, quận) — không định danh cá nhân
- Tên đã được ẩn kiểu <person:A.> hoặc <email:xxx> — đã được scrub rồi
- Vai trò chung chung ("bà lão", "ông hàng xóm") — không định danh được

Trả về JSON duy nhất, không kèm văn bản khác:
{
  "findings": [
    {"text": "<đoạn cần scrub>", "kind": "<person_name|location|title_unique|handle|other>"}
  ]
}

Nếu không tìm thấy gì, trả: {"findings": []}.
"""


def llm_scan_pii(
    text: str, *, llm: ClaudeClient | None = None
) -> list[PIIFinding]:
    """Quét text bằng LLM để tìm PII contextual mà regex bỏ sót.

    Trả về danh sách PIIFinding bổ sung (có thể rỗng). Nếu LLM không
    available, trả về [] — không raise.
    """
    if not text or not text.strip():
        return []

    client = llm or get_default_client()
    user = _LLM_PII_PROMPT + f"\n\nĐOẠN VĂN:\n---\n{text}\n---"

    try:
        parsed = client.complete_json(user)
    except Exception as exc:
        log.debug("LLM PII scan fallback: %s", exc)
        return []

    if not isinstance(parsed, dict):
        return []

    items = parsed.get("findings") or []
    if not isinstance(items, list):
        return []

    findings: list[PIIFinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        target = str(item.get("text", "")).strip()
        kind = str(item.get("kind", "other")).strip()
        if not target:
            continue
        # Map kind — chỉ chấp nhận các kind đã định nghĩa
        if kind not in ("person_name", "location", "title_unique", "handle", "other"):
            kind = "other"
        # Tìm span của target trong text để biết offset
        idx = text.find(target)
        if idx < 0:
            continue
        # Dùng lại replacement scheme: person-like → <person:X.>, còn lại → <pii:hash>
        rep_kind = "person_name" if kind in ("person_name", "title_unique") else "handle" if kind == "handle" else "other"
        replacement = _pseudonym_for(rep_kind if rep_kind != "other" else "handle", target)
        findings.append(
            PIIFinding(
                kind=rep_kind if rep_kind in ("person_name", "handle") else "handle",
                text=target,
                start=idx,
                end=idx + len(target),
                replacement=replacement,
            )
        )

    return findings


def merge_findings(
    regex_findings: list[PIIFinding], llm_findings: list[PIIFinding]
) -> list[PIIFinding]:
    """Hợp nhất 2 danh sách finding, loại chồng lấp.

    Ưu tiên regex (cụ thể hơn). LLM chỉ bổ sung những span không chồng
    với regex.
    """
    regex_spans = [(f.start, f.end) for f in regex_findings]

    def overlaps(s: int, e: int) -> bool:
        for rs, re_ in regex_spans:
            if s < re_ and e > rs:
                return True
        return False

    merged = list(regex_findings)
    for f in llm_findings:
        if not overlaps(f.start, f.end):
            merged.append(f)
    merged.sort(key=lambda f: f.start)
    return merged
