"""Verification layer — cross-validation giữa các ký ức.

Quan trọng: module này KHÔNG làm "fact-checking" theo nghĩa phán quyết đúng/sai.
Nó chỉ tìm điểm trùng và điểm khác, rồi trình bày để người đọc tự nhìn thấy.
"""

from .cross_check import (
    AtomicClaim,
    ClaimComparison,
    extract_atomic_claims,
    compare_claims,
)

__all__ = [
    "AtomicClaim",
    "ClaimComparison",
    "extract_atomic_claims",
    "compare_claims",
]
