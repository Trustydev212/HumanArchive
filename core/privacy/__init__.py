"""Privacy layer — bảo vệ danh tính người đóng góp và những người được nêu tên.

Nguyên tắc 2 (xem docs/ethics.md): KHÔNG xác định danh tính bất kỳ ai.

Module này phát hiện các dấu hiệu PII phổ biến và đề xuất pseudonymize:
    * Tên người Việt và phương Tây (full name, 2-3 token viết hoa)
    * Số điện thoại
    * Số CCCD/CMND Việt Nam (9 hoặc 12 chữ số)
    * Email
    * URL mạng xã hội

KHÔNG phải giải pháp an toàn 100% — chỉ là tầng rà soát cơ bản.
Người đóng góp vẫn nên tự kiểm tra trước khi submit.
"""

from .pii_scrubber import (
    PIIFinding,
    find_pii,
    pseudonymize,
    summarize_findings,
)

__all__ = ["PIIFinding", "find_pii", "pseudonymize", "summarize_findings"]
