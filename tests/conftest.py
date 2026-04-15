"""Shared fixtures cho test suite của HumanArchive."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# Cho phép import từ package core/ mà không cần pip install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _with_valid_id(memory: dict) -> dict:
    clone = {k: v for k, v in memory.items() if k != "memory_id"}
    h = hashlib.sha256(_canonical(clone).encode()).hexdigest()[:16]
    return {**memory, "memory_id": h}


@pytest.fixture
def sample_memory() -> dict:
    """Một memory hợp lệ theo schema v1, với memory_id được tính đúng."""
    return _with_valid_id(
        {
            "schema_version": "1.0",
            "contributor_id": "ha-test-0001",
            "event": {
                "event_id": "2024-example-flood-demo",
                "name": "Lũ làng ví dụ",
                "date": "2024-09-10",
                "location": "Một làng nhỏ miền Trung (hư cấu)",
            },
            "perspective": {"role": "witness", "proximity": "direct", "age_at_event": 34},
            "memory": {
                "what_happened": (
                    "Sáng sớm nước dâng rất nhanh. Tôi thấy hàng xóm "
                    "kéo trẻ con lên mái nhà. Có tiếng kêu cứu nhưng không "
                    "ai biết gọi ai trước."
                ),
                "emotional_state": "Tôi run rẩy, không biết phải làm gì.",
            },
            "motivation": {
                "your_motivation": "Tôi muốn giúp nhưng cũng sợ mất mạng.",
                "external_pressure": "Hàng xóm gào lên nhờ giúp.",
                "fears_at_the_time": "Sợ nhà mình cũng đổ.",
            },
            "consent": {
                "public": True,
                "embargo_until": None,
                "withdrawn": False,
                "allow_ai_analysis": True,
            },
            "language": "vi",
        }
    )


@pytest.fixture
def memory_with_pii() -> dict:
    """Memory có PII — dùng để test scrubber."""
    return _with_valid_id(
        {
            "schema_version": "1.0",
            "contributor_id": "ha-test-0002",
            "event": {
                "event_id": "2024-example-flood-demo",
                "name": "Lũ",
                "date": "2024-09-10",
            },
            "perspective": {"role": "participant"},
            "memory": {
                "what_happened": (
                    "Tôi gọi anh Nguyễn Văn An qua số 0912345678. "
                    "Sau đó email cho abc@example.com."
                )
            },
            "motivation": {"your_motivation": "Tôi muốn liên lạc người thân."},
            "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
        }
    )


@pytest.fixture
def withdrawn_memory() -> dict:
    return _with_valid_id(
        {
            "schema_version": "1.0",
            "contributor_id": "ha-test-w-xxx",
            "event": {"event_id": "2024-example-flood-demo", "name": "Lũ", "date": "2024-09-10"},
            "perspective": {"role": "witness"},
            "memory": {"what_happened": "Nội dung nào đó đã được rút lại."},
            "motivation": {"your_motivation": "Không còn quan trọng."},
            "consent": {"public": True, "withdrawn": True, "allow_ai_analysis": True},
        }
    )


@pytest.fixture
def embargoed_memory() -> dict:
    return _with_valid_id(
        {
            "schema_version": "1.0",
            "contributor_id": "ha-test-emb1",
            "event": {"event_id": "2024-example-flood-demo", "name": "Lũ", "date": "2024-09-10"},
            "perspective": {"role": "authority"},
            "memory": {"what_happened": "Một lời kể đang bị trì hoãn công bố."},
            "motivation": {"your_motivation": "Bảo vệ người thân."},
            "consent": {
                "public": True,
                "embargo_until": "2099-01-01",
                "withdrawn": False,
                "allow_ai_analysis": True,
            },
        }
    )


@pytest.fixture
def traumatic_memory() -> dict:
    return _with_valid_id(
        {
            "schema_version": "1.0",
            "contributor_id": "ha-test-tr01",
            "event": {"event_id": "2024-example-flood-demo", "name": "Lũ", "date": "2024-09-10"},
            "perspective": {"role": "victim"},
            "memory": {
                "what_happened": (
                    "Nhà tôi bị cuốn trôi. Người em út đã chết trong đêm đó. "
                    "Chúng tôi phải chạy loạn khỏi làng."
                )
            },
            "motivation": {"your_motivation": "Tôi kể lại để thế hệ sau biết."},
            "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
        }
    )
