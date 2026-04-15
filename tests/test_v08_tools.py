"""Test timeline, diff, verify_signatures tools."""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import io
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import diff_archives, timeline_export, verify_signatures  # noqa: E402


def _canonical(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _make_mem(tmp_path, event_id, role, date, what):
    mem = {
        "schema_version": "1.0",
        "contributor_id": f"ha-{role[:4]}-xxxx",
        "event": {"event_id": event_id, "name": event_id, "date": date},
        "perspective": {"role": role},
        "memory": {"what_happened": what},
        "motivation": {"your_motivation": "Tôi muốn kể lại chuyện này."},
        "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
    }
    clone = {k: v for k, v in mem.items() if k != "memory_id"}
    mem["memory_id"] = hashlib.sha256(_canonical(clone).encode()).hexdigest()[:16]
    d = tmp_path / "events" / event_id
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{mem['memory_id']}.json").write_text(json.dumps(mem, ensure_ascii=False), encoding="utf-8")
    return mem


# ============================================================================
# Timeline
# ============================================================================

class TestTimeline:
    def test_timeline_sorts_by_date(self, tmp_path):
        _make_mem(tmp_path, "2020-a-1111", "witness", "2020-09-10", "Năm 2020")
        _make_mem(tmp_path, "1975-b-2222", "participant", "1975-04-30", "Năm 1975")
        _make_mem(tmp_path, "1999-c-3333", "victim", "1999-07-15", "Năm 1999")

        events = timeline_export._load_events(tmp_path)
        ids = [e["event_id"] for e in events]
        assert ids == ["1975-b-2222", "1999-c-3333", "2020-a-1111"]

    def test_timeline_approximate_date_supported(self, tmp_path):
        _make_mem(tmp_path, "xx-a-1111", "witness", "~1975-04", "Xấp xỉ")
        events = timeline_export._load_events(tmp_path)
        assert len(events) == 1
        assert "~1975-04" in events[0]["date_display"]

    def test_timeline_respects_consent_filter(self, tmp_path):
        mem1 = _make_mem(tmp_path, "e1-1111", "witness", "2024-01-01", "Public")
        mem2 = _make_mem(tmp_path, "e2-2222", "victim", "2024-02-01", "Withdrawn")
        # Mark mem2 as withdrawn and rewrite
        mem2["consent"]["withdrawn"] = True
        mem2_clone = {k: v for k, v in mem2.items() if k != "memory_id"}
        mem2["memory_id"] = hashlib.sha256(_canonical(mem2_clone).encode()).hexdigest()[:16]
        # Clean old file, write new
        d = tmp_path / "events" / "e2-2222"
        for p in d.glob("*.json"):
            p.unlink()
        (d / f"{mem2['memory_id']}.json").write_text(
            json.dumps(mem2, ensure_ascii=False), encoding="utf-8"
        )

        events = timeline_export._load_events(tmp_path)
        assert len(events) == 1
        assert events[0]["event_id"] == "e1-1111"

    def test_timeline_html_renders(self, tmp_path):
        _make_mem(tmp_path, "e1-1111", "witness", "2024-01-01", "A")
        events = timeline_export._load_events(tmp_path)
        html = timeline_export.render_html(events)
        assert "<!DOCTYPE html>" in html
        assert "e1-1111" in html
        assert "timeline" in html.lower()


# ============================================================================
# Diff
# ============================================================================

class TestDiff:
    def test_diff_identical(self, tmp_path):
        a = tmp_path / "a"
        _make_mem(a, "e1-1111", "witness", "2024-01-01", "X")
        b = tmp_path / "b"
        _make_mem(b, "e1-1111", "witness", "2024-01-01", "X")

        sa = diff_archives._load_source(a)
        sb = diff_archives._load_source(b)
        r = diff_archives.diff(sa, sb)
        assert r.totals["in_both"] == 1
        assert r.totals["only_in_a"] == 0
        assert r.totals["only_in_b"] == 0
        assert r.totals["conflicts"] == 0

    def test_diff_finds_unique(self, tmp_path):
        a = tmp_path / "a"
        _make_mem(a, "e1-1111", "witness", "2024-01-01", "Chỉ ở A")
        b = tmp_path / "b"
        _make_mem(b, "e2-2222", "victim", "2024-02-01", "Chỉ ở B")

        sa = diff_archives._load_source(a)
        sb = diff_archives._load_source(b)
        r = diff_archives.diff(sa, sb)
        assert r.totals["only_in_a"] == 1
        assert r.totals["only_in_b"] == 1

    def test_diff_accepts_bundle(self, tmp_path):
        # Tạo folder A, build thành bundle B
        a = tmp_path / "a"
        mem = _make_mem(a, "e1-1111", "witness", "2024-01-01", "X")
        bundle = tmp_path / "b.tar.gz"
        with tarfile.open(bundle, "w:gz") as tar:
            data = json.dumps(mem, ensure_ascii=False).encode()
            info = tarfile.TarInfo("archive/events/e1-1111/" + mem["memory_id"] + ".json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        sa = diff_archives._load_source(a)
        sb = diff_archives._load_source(bundle)
        r = diff_archives.diff(sa, sb)
        assert r.totals["in_both"] == 1


# ============================================================================
# Verify signatures (fallback gracefully khi không có cryptography)
# ============================================================================

class TestVerifySignatures:
    def test_empty_archive_reports_zero(self, tmp_path):
        # Không có annotations
        report = verify_signatures.verify_all(
            tmp_path, tmp_path / "trust_missing.json"
        )
        assert report["annotations_total"] == 0
        assert report["signatures_invalid"] == []

    def test_unsigned_annotation_not_flagged_invalid(self, tmp_path):
        from core.annotations import create_annotation, save_annotation

        a = create_annotation(
            target_memory_id="a" * 16,
            author_id="someone",
            type="context",
            content="Thêm info",
        )
        save_annotation(a, tmp_path)
        report = verify_signatures.verify_all(tmp_path, tmp_path / "nope.json")
        assert report["annotations_total"] == 1
        assert report["annotations_unsigned"] == 1
        assert report["signatures_invalid"] == []

    def test_trust_file_lookup(self, tmp_path):
        trust_file = tmp_path / "trust.json"
        trust_file.write_text(
            json.dumps({
                "reviewers": [
                    {
                        "handle": "alice",
                        "pubkey_ed25519_hex": "a" * 64,
                        "status": "active",
                    }
                ]
            }),
            encoding="utf-8",
        )
        trust = verify_signatures._load_trust(trust_file)
        assert "alice" in trust
        pubkey, status = verify_signatures._pubkey_of(trust, "alice")
        assert pubkey == "a" * 64
        assert status == "active"
