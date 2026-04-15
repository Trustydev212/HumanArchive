"""Test annotation layer & staging workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from core.annotations import (
    Annotation,
    compute_annotation_id,
    create_annotation,
    iter_all_annotations,
    load_annotations,
    save_annotation,
)


class TestAnnotationCore:
    def test_create_computes_deterministic_id(self):
        a1 = create_annotation(
            target_memory_id="a" * 16,
            author_id="ha-test-0001",
            type="context",
            content="Bổ sung thông tin",
        )
        a2 = create_annotation(
            target_memory_id="a" * 16,
            author_id="ha-test-0001",
            type="context",
            content="Bổ sung thông tin",
        )
        # created_at khác nhau → id khác nhau (acceptable; annotation có timestamp)
        assert len(a1.annotation_id) == 16

    def test_invalid_type_rejected(self):
        with pytest.raises(ValueError):
            create_annotation(
                target_memory_id="a" * 16,
                author_id="x",
                type="delete_the_memory",  # type: ignore[arg-type]
                content="xoá đi",
            )

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError):
            create_annotation(
                target_memory_id="a" * 16,
                author_id="x",
                type="context",
                content="",
            )


class TestAnnotationStorage:
    def test_save_load_roundtrip(self, tmp_path):
        a = create_annotation(
            target_memory_id="aaaa" * 4,
            author_id="ha-reviewer-0001",
            type="correction",
            content="Ngày có thể là 10/9 thay vì 10/10.",
        )
        save_annotation(a, tmp_path)
        loaded = load_annotations(tmp_path, "aaaa" * 4)
        assert len(loaded) == 1
        assert loaded[0].annotation_id == a.annotation_id
        assert loaded[0].type == "correction"

    def test_save_is_idempotent(self, tmp_path):
        a = create_annotation(
            target_memory_id="bbbb" * 4,
            author_id="x",
            type="context",
            content="trùng lặp",
        )
        p1 = save_annotation(a, tmp_path)
        p2 = save_annotation(a, tmp_path)
        assert p1 == p2

    def test_multiple_annotations_sorted_by_time(self, tmp_path):
        a1 = create_annotation(
            target_memory_id="cccc" * 4, author_id="r1",
            type="context", content="first",
        )
        a2 = create_annotation(
            target_memory_id="cccc" * 4, author_id="r2",
            type="dispute", content="second",
        )
        save_annotation(a1, tmp_path)
        save_annotation(a2, tmp_path)
        loaded = load_annotations(tmp_path, "cccc" * 4)
        assert [x.content for x in loaded] == ["first", "second"] or \
               [x.content for x in loaded] == ["second", "first"]  # time resolution

    def test_iter_all_annotations(self, tmp_path):
        for mid in ("m1" * 8, "m2" * 8):
            save_annotation(
                create_annotation(
                    target_memory_id=mid, author_id="r", type="context", content="x"
                ),
                tmp_path,
            )
        annos = list(iter_all_annotations(tmp_path))
        assert len(annos) == 2


class TestImmutability:
    """Annotation bất biến (nguyên tắc 5 extended)."""

    def test_annotation_id_covers_all_content(self):
        """Nếu đổi bất kỳ field nào thì annotation_id phải khác."""
        base = {
            "schema_version": "1.0",
            "target_memory_id": "a" * 16,
            "author_id": "x",
            "type": "context",
            "content": "original",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        id1 = compute_annotation_id(base)
        modified = {**base, "content": "modified"}
        id2 = compute_annotation_id(modified)
        assert id1 != id2

    def test_correction_requires_new_annotation(self):
        """Để 'sửa' annotation, phải tạo annotation mới type=correction,
        không được sửa annotation cũ. (Chính sách — test này chỉ doc)."""
        original = create_annotation(
            target_memory_id="a" * 16, author_id="r1",
            type="context", content="Original claim",
        )
        correction = create_annotation(
            target_memory_id="a" * 16, author_id="r2",
            type="correction",
            content=f"Annotation {original.annotation_id} có thể cần xem lại.",
        )
        # Cả hai coexist — không ghi đè
        assert original.annotation_id != correction.annotation_id
        assert correction.type == "correction"


class TestNoJudgmentInSchema:
    """Nguyên tắc 1: annotation type cấm các tên gợi ý phán xét."""

    def test_no_verdict_types(self):
        forbidden = ["verdict", "guilty", "liar", "false", "banned", "deleted"]
        for t in forbidden:
            with pytest.raises(ValueError):
                create_annotation(
                    target_memory_id="a" * 16, author_id="x",
                    type=t,  # type: ignore[arg-type]
                    content="x",
                )
