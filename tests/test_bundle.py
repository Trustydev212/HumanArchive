"""Test federation bundle export / import."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from core.integrity import compute_memory_id
from tools import export_bundle as exp
from tools import import_bundle as imp


def _write_memory(root: Path, memory: dict) -> None:
    eid = memory["event"]["event_id"]
    mid = memory["memory_id"]
    d = root / "events" / eid
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{mid}.json").write_text(json.dumps(memory, ensure_ascii=False), encoding="utf-8")


class TestBundleRoundtrip:
    def test_export_then_import(self, tmp_path, sample_memory):
        src = tmp_path / "src"
        _write_memory(src, sample_memory)
        bundle = tmp_path / "b.tar.gz"
        exp.build_bundle(src, bundle)

        dst = tmp_path / "dst"
        dst.mkdir()
        res = imp.import_bundle(bundle, dst)
        assert len(res["added"]) == 1
        # memory đã ở đúng chỗ
        eid = sample_memory["event"]["event_id"]
        mid = sample_memory["memory_id"]
        assert (dst / "events" / eid / f"{mid}.json").exists()

    def test_reimport_dedups(self, tmp_path, sample_memory):
        src = tmp_path / "src"
        _write_memory(src, sample_memory)
        bundle = tmp_path / "b.tar.gz"
        exp.build_bundle(src, bundle)
        dst = tmp_path / "dst"
        dst.mkdir()
        imp.import_bundle(bundle, dst)
        # Import lần 2 → toàn bộ skip
        res2 = imp.import_bundle(bundle, dst)
        assert len(res2["added"]) == 0
        assert len(res2["skipped_dedup"]) == 1

    def test_merkle_root_stable(self, tmp_path, sample_memory):
        src = tmp_path / "src"
        _write_memory(src, sample_memory)
        b1 = tmp_path / "b1.tar.gz"
        b2 = tmp_path / "b2.tar.gz"
        m1 = exp.build_bundle(src, b1, bundle_name="x")
        m2 = exp.build_bundle(src, b2, bundle_name="x")
        # Cùng dữ liệu → cùng merkle
        assert m1["merkle_root"] == m2["merkle_root"]


class TestBundleIntegrity:
    def test_tampered_archive_refused_on_export(self, tmp_path, sample_memory):
        src = tmp_path / "src"
        # Tamper: sửa content sau khi memory_id đã được compute
        sample_memory["memory"]["what_happened"] += " (tampered)"
        _write_memory(src, sample_memory)
        bundle = tmp_path / "b.tar.gz"
        with pytest.raises(ValueError, match="tampered"):
            exp.build_bundle(src, bundle)

    def test_merkle_mismatch_rejected_on_import(self, tmp_path, sample_memory):
        src = tmp_path / "src"
        _write_memory(src, sample_memory)
        bundle = tmp_path / "b.tar.gz"
        exp.build_bundle(src, bundle)

        # Sửa bundle: nhét thêm memory giả vào tar
        import gzip, io
        with tarfile.open(bundle, "r:gz") as t:
            members = [(m, t.extractfile(m).read()) for m in t.getmembers() if m.isfile()]
        tampered = tmp_path / "tampered.tar.gz"
        with tarfile.open(tampered, "w:gz") as t:
            for m, data in members:
                info = tarfile.TarInfo(m.name)
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
            # Thêm 1 "memory" giả
            fake = json.dumps(
                {
                    "schema_version": "1.0",
                    "memory_id": "f" * 16,
                    "contributor_id": "ha-fake-zzzz",
                    "event": {"event_id": "fake-event", "name": "Fake", "date": "2024-01-01"},
                    "perspective": {"role": "witness"},
                    "memory": {"what_happened": "x" * 30},
                    "motivation": {"your_motivation": "x" * 20},
                    "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
                },
                ensure_ascii=False,
            ).encode()
            info = tarfile.TarInfo("archive/events/fake-event/ffffffffffffffff.json")
            info.size = len(fake)
            t.addfile(info, io.BytesIO(fake))

        dst = tmp_path / "dst"
        dst.mkdir()
        with pytest.raises(ValueError, match="Merkle mismatch"):
            imp.import_bundle(tampered, dst)

    def test_dry_run_writes_nothing(self, tmp_path, sample_memory):
        src = tmp_path / "src"
        _write_memory(src, sample_memory)
        bundle = tmp_path / "b.tar.gz"
        exp.build_bundle(src, bundle)

        dst = tmp_path / "dst"
        dst.mkdir()
        res = imp.import_bundle(bundle, dst, dry_run=True)
        assert res["dry_run"] is True
        # events/ không được tạo
        assert not (dst / "events").exists()
