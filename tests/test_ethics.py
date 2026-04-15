"""Test rằng 5 nguyên tắc bất biến được enforce ở tầng code.

Mỗi nguyên tắc tương ứng ít nhất một test. Nếu test fail, ĐỪNG nới lỏng
test — hãy fix code. Đây là hợp đồng đạo đức của dự án.
"""

from __future__ import annotations

import pytest

from core.ai_engine import analyze_memory, cross_reference, generate_historical_entry
from core.llm.claude_client import FORBIDDEN_FIELDS, _assert_no_forbidden_fields


# ============================================================================
# Nguyên tắc 1: KHÔNG phán xét đúng/sai
# ============================================================================

class TestPrinciple1_NoVerdicts:
    def test_forbidden_fields_list_covers_common_verdicts(self):
        for field in ("verdict", "guilty", "is_lying", "credibility_score", "who_is_right"):
            assert field in FORBIDDEN_FIELDS

    def test_output_with_verdict_is_rejected(self):
        bad = {"verdict": "A đang nói dối", "acknowledgement": "..."}
        with pytest.raises(ValueError, match="nguyên tắc 1"):
            _assert_no_forbidden_fields(bad)

    def test_output_with_nested_judgment_is_rejected(self):
        bad = {"analysis": {"details": {"is_lying": True}}}
        with pytest.raises(ValueError, match="nguyên tắc 1"):
            _assert_no_forbidden_fields(bad)

    def test_clean_output_passes(self):
        good = {
            "acknowledgement": "Tôi hiểu bạn đã trải qua...",
            "motivation_interpretation": "Có vẻ bạn hành động vì...",
            "uncertainty": "medium",
        }
        _assert_no_forbidden_fields(good)  # không raise

    def test_cross_reference_report_never_contains_verdict(self, sample_memory):
        report = cross_reference([sample_memory]).to_dict()
        # "note" của report phải nói rõ không phán xét
        assert "KHÔNG kết luận ai đúng ai sai" in report["note"]
        _assert_no_forbidden_fields(report)


# ============================================================================
# Nguyên tắc 2: KHÔNG xác định danh tính
# ============================================================================

class TestPrinciple2_NoIdentification:
    def test_pii_is_scrubbed_before_llm_call(self, memory_with_pii):
        from core.ai_engine import _scrubbed_view

        _, findings = _scrubbed_view(memory_with_pii)
        assert len(findings) >= 2  # tên + số điện thoại + email
        kinds = {f.kind for f in findings}
        assert "phone" in kinds
        assert "email" in kinds

    def test_ai_analysis_respects_allow_ai_false(self, sample_memory):
        sample_memory["consent"]["allow_ai_analysis"] = False
        with pytest.raises(PermissionError):
            analyze_memory(sample_memory)

    def test_historical_entry_redacts_pii(self, tmp_path, memory_with_pii):
        event_dir = tmp_path / "events" / "2024-example-flood-demo"
        event_dir.mkdir(parents=True)
        (event_dir / f"{memory_with_pii['memory_id']}.json").write_text(
            _as_json(memory_with_pii), encoding="utf-8"
        )
        entry = generate_historical_entry(
            "2024-example-flood-demo", archive_root=tmp_path
        )
        # Tên + số điện thoại + email không được xuất hiện nguyên dạng
        assert "Nguyễn Văn An" not in entry
        assert "0912345678" not in entry
        assert "abc@example.com" not in entry


# ============================================================================
# Nguyên tắc 3: LUÔN đồng cảm trước khi phân tích
# ============================================================================

class TestPrinciple3_EmpathyFirst:
    def test_trauma_memory_gets_content_warning(self, tmp_path, traumatic_memory):
        from core.trauma import detect_trauma

        t = detect_trauma(traumatic_memory)
        assert t.has_trauma
        # "death" + "displacement" đều có trong keyword
        assert "death" in t.categories

    def test_historical_entry_shows_trauma_warning(self, tmp_path, traumatic_memory):
        event_dir = tmp_path / "events" / "2024-example-flood-demo"
        event_dir.mkdir(parents=True)
        (event_dir / f"{traumatic_memory['memory_id']}.json").write_text(
            _as_json(traumatic_memory), encoding="utf-8"
        )
        entry = generate_historical_entry(
            "2024-example-flood-demo", archive_root=tmp_path
        )
        assert "CẢNH BÁO" in entry or "Cảnh báo" in entry

    def test_analysis_result_has_acknowledgement_field(self, sample_memory):
        result = analyze_memory(sample_memory)
        # Luôn có acknowledgement, kể cả stub
        assert hasattr(result, "acknowledgement")


# ============================================================================
# Nguyên tắc 4: Động cơ quan trọng hơn hành động
# ============================================================================

class TestPrinciple4_MotivationRequired:
    def test_missing_motivation_rejects(self, sample_memory):
        sample_memory["motivation"] = {}
        with pytest.raises(ValueError, match="motivation"):
            analyze_memory(sample_memory)

    def test_empty_motivation_rejects(self, sample_memory):
        del sample_memory["motivation"]["your_motivation"]
        with pytest.raises(ValueError):
            analyze_memory(sample_memory)


# ============================================================================
# Nguyên tắc 5: Dữ liệu thô không đổi
# ============================================================================

class TestPrinciple5_Immutability:
    def test_withdrawn_memory_hidden_from_entry(self, tmp_path, withdrawn_memory):
        event_dir = tmp_path / "events" / "2024-example-flood-demo"
        event_dir.mkdir(parents=True)
        (event_dir / f"{withdrawn_memory['memory_id']}.json").write_text(
            _as_json(withdrawn_memory), encoding="utf-8"
        )
        entry = generate_historical_entry(
            "2024-example-flood-demo", archive_root=tmp_path
        )
        assert "đã được rút lại" not in entry
        assert "không có ký ức nào đang được công bố" in entry.lower() or \
               "không có ký ức nào đang được công" in entry.lower()

    def test_embargoed_memory_hidden_from_entry(self, tmp_path, embargoed_memory):
        event_dir = tmp_path / "events" / "2024-example-flood-demo"
        event_dir.mkdir(parents=True)
        (event_dir / f"{embargoed_memory['memory_id']}.json").write_text(
            _as_json(embargoed_memory), encoding="utf-8"
        )
        entry = generate_historical_entry(
            "2024-example-flood-demo", archive_root=tmp_path
        )
        assert "đang bị trì hoãn công bố" not in entry

    def test_tampered_memory_id_is_flagged(self, sample_memory):
        sample_memory["memory"]["what_happened"] += " (sửa đổi bí mật)"
        # memory_id giờ không khớp content nữa
        report = cross_reference([sample_memory])
        assert len(report.integrity_issues) == 1


# ============================================================================
# Helpers
# ============================================================================

def _as_json(obj: dict) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
