"""Test integrity layer: memory_id verification + consent filtering."""

from __future__ import annotations

from datetime import date

from core.integrity import (
    allows_ai_analysis,
    compute_memory_id,
    filter_viewable,
    is_publicly_viewable,
    verify_memory_id,
)


class TestMemoryIdIntegrity:
    def test_valid_memory_id_passes(self, sample_memory):
        assert verify_memory_id(sample_memory).ok

    def test_modified_content_fails(self, sample_memory):
        sample_memory["memory"]["what_happened"] += " (bị sửa sau)"
        assert verify_memory_id(sample_memory).tampered

    def test_compute_is_deterministic(self, sample_memory):
        a = compute_memory_id(sample_memory)
        b = compute_memory_id(sample_memory)
        assert a == b
        assert len(a) == 16


class TestConsentFiltering:
    def test_public_memory_is_viewable(self, sample_memory):
        assert is_publicly_viewable(sample_memory)

    def test_withdrawn_not_viewable(self, withdrawn_memory):
        assert not is_publicly_viewable(withdrawn_memory)

    def test_non_public_not_viewable(self, sample_memory):
        sample_memory["consent"]["public"] = False
        assert not is_publicly_viewable(sample_memory)

    def test_embargo_future_not_viewable(self, embargoed_memory):
        assert not is_publicly_viewable(embargoed_memory)

    def test_embargo_past_viewable(self, sample_memory):
        sample_memory["consent"]["embargo_until"] = "2000-01-01"
        assert is_publicly_viewable(sample_memory)

    def test_embargo_checked_against_as_of(self, sample_memory):
        sample_memory["consent"]["embargo_until"] = "2050-01-01"
        assert is_publicly_viewable(sample_memory, as_of=date(2051, 1, 1))
        assert not is_publicly_viewable(sample_memory, as_of=date(2049, 1, 1))

    def test_filter_viewable(self, sample_memory, withdrawn_memory, embargoed_memory):
        kept = filter_viewable([sample_memory, withdrawn_memory, embargoed_memory])
        assert len(kept) == 1
        assert kept[0]["memory_id"] == sample_memory["memory_id"]


class TestAIConsent:
    def test_default_allows_ai(self, sample_memory):
        assert allows_ai_analysis(sample_memory)

    def test_explicit_opt_out_respected(self, sample_memory):
        sample_memory["consent"]["allow_ai_analysis"] = False
        assert not allows_ai_analysis(sample_memory)
