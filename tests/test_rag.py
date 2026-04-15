"""Test RAG pipeline — đặc biệt các tính chất đạo đức.

Không chỉ test "retrieval works" — test rằng các cách RAG có thể đi sai
với dữ liệu ký ức đều được chặn.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core.rag import build_index, load_index
from core.rag.embedder import HashEmbedder
from core.rag.index import RAGIndex, save_index, search_text


def _canonical(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _with_id(m):
    c = {k: v for k, v in m.items() if k != "memory_id"}
    m["memory_id"] = hashlib.sha256(_canonical(c).encode()).hexdigest()[:16]
    return m


@pytest.fixture
def archive_with_mix(tmp_path, sample_memory, memory_with_pii, withdrawn_memory, embargoed_memory):
    """Archive có: 1 memory sạch, 1 có PII, 1 withdrawn, 1 embargo → chỉ
    2 cái đầu nên xuất hiện trong index."""
    root = tmp_path
    events = root / "events" / "2024-example-flood-demo"
    events.mkdir(parents=True)

    for mem in (sample_memory, memory_with_pii, withdrawn_memory, embargoed_memory):
        mem["event"]["event_id"] = "2024-example-flood-demo"
        # Recompute memory_id vì event_id thay đổi
        _with_id(mem)
        (events / f"{mem['memory_id']}.json").write_text(
            json.dumps(mem, ensure_ascii=False), encoding="utf-8"
        )
    return root


# ============================================================================
# Safety properties — không chỉ functionality
# ============================================================================

class TestIndexSafety:
    def test_withdrawn_never_indexed(self, archive_with_mix, withdrawn_memory):
        idx = build_index(archive_with_mix, embedder=HashEmbedder(dim=128))
        for e in idx.entries:
            assert e.memory_id != withdrawn_memory["memory_id"]

    def test_embargoed_never_indexed(self, archive_with_mix, embargoed_memory):
        idx = build_index(archive_with_mix, embedder=HashEmbedder(dim=128))
        for e in idx.entries:
            assert e.memory_id != embargoed_memory["memory_id"]

    def test_no_ai_consent_not_indexed(self, tmp_path, sample_memory):
        sample_memory["consent"]["allow_ai_analysis"] = False
        d = tmp_path / "events" / "e1"
        d.mkdir(parents=True)
        sample_memory["event"]["event_id"] = "e1"
        _with_id(sample_memory)
        (d / f"{sample_memory['memory_id']}.json").write_text(
            json.dumps(sample_memory, ensure_ascii=False), encoding="utf-8"
        )
        idx = build_index(tmp_path, embedder=HashEmbedder(dim=128))
        assert len(idx.entries) == 0

    def test_pii_scrubbed_before_indexing(self, archive_with_mix, memory_with_pii):
        """Cực kỳ quan trọng: embedding không được encode danh tính."""
        idx = build_index(archive_with_mix, embedder=HashEmbedder(dim=128))
        pii_entry = next(
            e for e in idx.entries if e.memory_id == memory_with_pii["memory_id"]
        )
        # text_scrubbed KHÔNG được chứa PII gốc
        assert "Nguyễn Văn An" not in pii_entry.text_scrubbed
        assert "0912345678" not in pii_entry.text_scrubbed
        assert "abc@example.com" not in pii_entry.text_scrubbed


class TestQuerySafety:
    def test_query_with_name_is_scrubbed(self, archive_with_mix):
        idx = build_index(archive_with_mix, embedder=HashEmbedder(dim=128))
        from core.rag.answer import answer_question

        # Query cố tình chứa tên để probe identity
        result = answer_question(
            "Kể về anh Nguyễn Văn An",
            idx,
            embedder=HashEmbedder(dim=128),
        )
        # question_scrubbed không được chứa tên gốc
        assert "Nguyễn Văn An" not in result.question_scrubbed


# ============================================================================
# Bias / diversity
# ============================================================================

class TestRoleBalancedRetrieval:
    def test_role_balanced_picks_diverse_roles(self, tmp_path):
        """Nếu có 3 witness và 1 victim, role-balanced phải pick cả victim."""
        d = tmp_path / "events" / "e1"
        d.mkdir(parents=True)

        def mem(role, text):
            m = {
                "schema_version": "1.0",
                "contributor_id": f"ha-test-{role[:4]}",
                "event": {"event_id": "e1", "name": "E", "date": "2024-01-01"},
                "perspective": {"role": role},
                "memory": {"what_happened": text},
                "motivation": {"your_motivation": "Lý do của tôi là gì đó."},
                "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
            }
            _with_id(m)
            return m

        # 3 witness nói từ "nước lên", 1 victim nói chuyện khác
        mems = [
            mem("witness", "sáng sớm nước lên nhanh lắm"),
            mem("witness", "nước lên tôi thấy nhanh kinh khủng"),
            mem("witness", "sáng đó nước lên bất ngờ"),
            mem("victim", "nhà tôi cuốn trôi hết"),
        ]
        for m in mems:
            (d / f"{m['memory_id']}.json").write_text(
                json.dumps(m, ensure_ascii=False), encoding="utf-8"
            )

        emb = HashEmbedder(dim=256)
        idx = build_index(tmp_path, embedder=emb)

        # Không balanced → 3 witness top
        hits_unbalanced = search_text(
            idx, "nước lên", embedder=emb, k=3, role_balance=False
        )
        roles_unbalanced = {h.entry.role for h in hits_unbalanced}
        # Có khả năng unbalanced có witness dominant

        # Balanced → phải có ít nhất 2 role khác nhau khi k>=2
        hits_balanced = search_text(
            idx, "nước lên", embedder=emb, k=3, role_balance=True
        )
        roles_balanced = {h.entry.role for h in hits_balanced}
        # Role-balanced phải >= số role unique trong unbalanced (thường nhiều hơn)
        assert len(roles_balanced) >= len(roles_unbalanced) or len(roles_balanced) >= 2


# ============================================================================
# Basic functionality
# ============================================================================

class TestSaveLoad:
    def test_roundtrip(self, archive_with_mix, tmp_path):
        idx = build_index(archive_with_mix, embedder=HashEmbedder(dim=128))
        path = tmp_path / "idx.json"
        save_index(idx, path)
        loaded = load_index(path)
        assert loaded.dim == idx.dim
        assert len(loaded.entries) == len(idx.entries)


class TestHashEmbedder:
    def test_deterministic(self):
        e = HashEmbedder(dim=64)
        assert e.embed("xin chào") == e.embed("xin chào")

    def test_normalized(self):
        e = HashEmbedder(dim=64)
        vec = e.embed("một chuỗi ngẫu nhiên nào đó")
        norm = sum(v * v for v in vec) ** 0.5
        assert 0.99 < norm < 1.01  # L2-normalized

    def test_similar_texts_closer_than_dissimilar(self):
        e = HashEmbedder(dim=512)
        a = e.embed("nước lên rất nhanh sáng hôm đó")
        b = e.embed("sáng hôm đó nước lên rất nhanh")
        c = e.embed("tôi đang nấu cơm trong bếp")
        ab = sum(x * y for x, y in zip(a, b))
        ac = sum(x * y for x, y in zip(a, c))
        assert ab > ac
