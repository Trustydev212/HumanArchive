"""Claude API client cho HumanArchive.

Thiết kế:
    * Prompt caching trên system prompt (5 nguyên tắc — stable, dài, được dùng
      trong mọi request) để giảm 90% chi phí
    * Adaptive thinking cho các tác vụ phân tích phức tạp
    * Fallback graceful về EchoLLM khi không có ANTHROPIC_API_KEY
    * Mọi output được validate chống các trường phán xét

Mọi prompt phải có prefix bất biến này để đảm bảo nguyên tắc 1, 3, 4.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# System prompt — bất biến, được prompt-cached
# --------------------------------------------------------------------------
# LƯU Ý: BẤT KỲ thay đổi nào trong chuỗi dưới đây sẽ invalidate cache toàn
# bộ các request trước đó. Chỉ sửa khi thực sự cập nhật 5 nguyên tắc.

HUMANARCHIVE_SYSTEM_PROMPT = """Bạn là AI engine của HumanArchive — một hệ thống lưu trữ ký ức tập thể
phi tập trung. Nhiệm vụ của bạn là HIỂU, không phải PHÁN XÉT.

5 NGUYÊN TẮC BẤT BIẾN (không bao giờ vi phạm):

1. KHÔNG phán xét đúng/sai. Bạn KHÔNG được kết luận người kể "đang nói dối",
   "có lỗi", "đáng trách". Bạn KHÔNG được so sánh độ tin cậy dựa trên vị trí
   xã hội của người kể. Nếu cần nêu mâu thuẫn, hãy nói "lời kể của X khác
   với lời kể của Y ở điểm Z" — KHÔNG nói "X đúng / Y sai".

2. KHÔNG xác định danh tính. Nếu lời kể có nêu tên người khác, hãy đề xuất
   pseudonymize ("anh T." thay vì "anh Tuấn"). KHÔNG bao giờ suy luận danh
   tính của người kể từ chi tiết của họ.

3. LUÔN đồng cảm trước khi phân tích. Câu trả lời của bạn PHẢI bắt đầu bằng
   một lời ghi nhận ngắn gọn cảm xúc/hoàn cảnh của người kể, TRƯỚC KHI đi
   vào phân tích. Nếu có trauma, thêm cảnh báo nhẹ nhàng.

4. Động cơ quan trọng hơn hành động. Khi phân tích, luôn đặt ĐỘNG CƠ
   (your_motivation, external_pressure, fears) lên trước hành động cụ thể.

5. Dữ liệu thô không thay đổi. Bạn KHÔNG được đề xuất xóa/sửa lời kể của
   người khác. Chỉ đề xuất ADD CONTEXT, không bao giờ OVERRIDE.

ĐỊNH DẠNG OUTPUT:

Luôn trả về một JSON object duy nhất, không kèm văn bản ngoài JSON.
TUYỆT ĐỐI KHÔNG dùng các trường: "verdict", "judgment", "guilty", "lying",
"trustworthy_rank", "credibility_score", "is_true", "is_false", hoặc bất kỳ
trường nào mang tính phán quyết. Thay vào đó, dùng các trường như
"acknowledgement", "motivation_interpretation", "external_pressure_note",
"emotional_state_note", "uncertainty" (low|medium|high), và "divergent_points".

Nếu bạn không chắc, hãy nói rõ "uncertainty": "high" thay vì suy diễn."""


# Các trường bị cấm trong output — kiểm tra sau khi parse JSON
FORBIDDEN_FIELDS = frozenset([
    "verdict", "judgment", "judgement", "guilty", "is_lying", "lying",
    "trustworthy_rank", "credibility_score", "is_true", "is_false",
    "who_is_right", "who_is_wrong", "truth_verdict",
])


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

@dataclass
class ClaudeClient:
    """Wrapper quanh Anthropic SDK.

    Thiết kế để:
        * Luôn inject system prompt bất biến (prompt-cached)
        * Validate output không có trường phán xét
        * Fallback an toàn nếu không có API key hoặc SDK
    """

    model: str = "claude-opus-4-6"
    max_tokens: int = 4096
    use_adaptive_thinking: bool = True
    _sdk_client: Any = None  # anthropic.Anthropic instance, lazy init

    def _client(self):
        if self._sdk_client is not None:
            return self._sdk_client
        try:
            import anthropic  # type: ignore
        except ImportError:
            log.warning("anthropic SDK chưa cài. `pip install anthropic` để bật LLM thật.")
            return None
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log.warning("ANTHROPIC_API_KEY chưa set. LLM sẽ fallback về stub.")
            return None
        self._sdk_client = anthropic.Anthropic()
        return self._sdk_client

    # ---------------------------------------------------------------- API

    def complete(self, user_prompt: str, *, max_tokens: int | None = None) -> str:
        """Gọi Claude với system prompt bất biến (prompt-cached).

        Trả về string. Nếu không có LLM, trả về stub JSON an toàn.
        """
        client = self._client()
        if client is None:
            return self._stub_response()

        messages = [{"role": "user", "content": user_prompt}]

        # Prompt caching: đưa system prompt vào list với cache_control trên
        # block cuối. Render order là tools → system → messages, nên cache
        # này sẽ hit mọi request sau lần đầu.
        system = [
            {
                "type": "text",
                "text": HUMANARCHIVE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system,
            "messages": messages,
        }
        if self.use_adaptive_thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        try:
            response = client.messages.create(**kwargs)
        except Exception as exc:  # SDK có nhiều exception class; log chung
            log.error("Claude API lỗi: %s — fallback stub.", exc)
            return self._stub_response()

        # Log hit rate để debug caching
        usage = getattr(response, "usage", None)
        if usage is not None:
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
            log.debug(
                "cache_read=%d cache_write=%d input=%d output=%d",
                cache_read, cache_write,
                getattr(usage, "input_tokens", 0),
                getattr(usage, "output_tokens", 0),
            )

        # Lấy text block đầu tiên (bỏ qua thinking blocks)
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text

        return self._stub_response()

    def complete_json(self, user_prompt: str, *, max_tokens: int | None = None) -> dict[str, Any]:
        """Như complete() nhưng parse kết quả thành JSON và validate.

        Raise ValueError nếu output chứa trường phán xét (bảo vệ nguyên tắc 1).
        """
        raw = self.complete(user_prompt, max_tokens=max_tokens)
        parsed = _extract_json(raw)
        _assert_no_forbidden_fields(parsed)
        return parsed

    # ------------------------------------------------------------- private

    @staticmethod
    def _stub_response() -> str:
        """Stub JSON an toàn khi không có LLM — để pipeline vẫn chạy được."""
        return json.dumps(
            {
                "acknowledgement": (
                    "Tôi ghi nhận trải nghiệm của bạn. "
                    "(LLM chưa được cấu hình — phân tích chi tiết chưa sẵn có.)"
                ),
                "motivation_interpretation": "",
                "external_pressure_note": "",
                "emotional_state_note": "",
                "uncertainty": "high",
                "_stub": True,
            },
            ensure_ascii=False,
        )


# --------------------------------------------------------------------------
# Parsing & validation
# --------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any]:
    """Parse JSON từ output của Claude một cách phòng thủ."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Thử trích đoạn JSON đầu tiên/cuối cùng
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        log.warning("Không parse được JSON, trả về dict rỗng.")
        return {}


def _assert_no_forbidden_fields(data: dict[str, Any], *, path: str = "") -> None:
    """Walk dict/list, raise nếu có trường nằm trong FORBIDDEN_FIELDS.

    Nguyên tắc 1 được enforce ở tầng code — không chỉ prompt. Nếu LLM lỡ
    vi phạm, pipeline sẽ refuse thay vì propagate.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            lower = key.lower().strip()
            if lower in FORBIDDEN_FIELDS:
                raise ValueError(
                    f"Output vi phạm nguyên tắc 1: chứa trường cấm "
                    f"'{key}' tại {path or '<root>'}. LLM không được phán xét."
                )
            _assert_no_forbidden_fields(value, path=f"{path}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _assert_no_forbidden_fields(item, path=f"{path}[{i}]")


# --------------------------------------------------------------------------
# Default singleton
# --------------------------------------------------------------------------

_DEFAULT: ClaudeClient | None = None


def get_default_client() -> ClaudeClient:
    """Singleton để các module khác dùng chung, tối đa hoá prompt cache hit."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ClaudeClient()
    return _DEFAULT
