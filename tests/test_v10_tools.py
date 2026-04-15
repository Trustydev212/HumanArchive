"""Test bulk_import + SEO + social card generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import bulk_import


class TestBulkImportCSV:
    def test_example_csv_imports(self, tmp_path):
        src = REPO / "tools" / "bulk_import_example.csv"
        r = bulk_import.bulk_import(src, target="staging", dry_run=True)
        assert r["rows_read"] == 2
        assert r["imported"] == 2
        assert r["failed"] == 0

    def test_missing_required_fails(self, tmp_path):
        csv = tmp_path / "bad.csv"
        csv.write_text(
            "event_name,event_date,role,what_happened,your_motivation\n"
            ",2024-01-01,witness,Chuyện này đã xảy ra rất lâu trước đây,Lý do tôi làm vậy\n",
            encoding="utf-8",
        )
        r = bulk_import.bulk_import(csv, dry_run=True)
        assert r["imported"] == 0
        assert r["failed"] == 1
        assert "event_name" in r["errors"][0]["error"]

    def test_motivation_too_short_fails(self, tmp_path):
        csv = tmp_path / "short_motiv.csv"
        csv.write_text(
            "event_name,event_date,role,what_happened,your_motivation\n"
            "Event,2024-01-01,witness,Chuyện này đã xảy ra rất lâu trước đây,Ngắn\n",
            encoding="utf-8",
        )
        r = bulk_import.bulk_import(csv, dry_run=True)
        assert r["failed"] == 1
        assert "motivation" in r["errors"][0]["error"]

    def test_what_happened_too_short_fails(self, tmp_path):
        csv = tmp_path / "short_what.csv"
        csv.write_text(
            "event_name,event_date,role,what_happened,your_motivation\n"
            "Event,2024-01-01,witness,Short,Tôi có lý do rõ ràng để làm vậy\n",
            encoding="utf-8",
        )
        r = bulk_import.bulk_import(csv, dry_run=True)
        assert r["failed"] == 1
        assert "what_happened" in r["errors"][0]["error"]

    def test_invalid_role_fails(self, tmp_path):
        csv = tmp_path / "bad_role.csv"
        csv.write_text(
            "event_name,event_date,role,what_happened,your_motivation\n"
            "Event,2024-01-01,admin,Chuyện này đã xảy ra lâu rồi đúng vậy,Lý do của tôi là gì đó\n",
            encoding="utf-8",
        )
        r = bulk_import.bulk_import(csv, dry_run=True)
        assert r["failed"] == 1
        assert "role" in r["errors"][0]["error"]

    def test_multi_value_fields_parsed(self, tmp_path):
        csv = tmp_path / "multi.csv"
        csv.write_text(
            "event_name,event_date,role,what_happened,your_motivation,event_tags\n"
            "E1,2024-01-01,witness,Chuyện này đã xảy ra rất lâu trước đây,Lý do tôi ở đó,a|b|c\n",
            encoding="utf-8",
        )
        r = bulk_import.bulk_import(csv, dry_run=True)
        assert r["imported"] == 1
        # Có thể không dễ đọc lại mem từ result (chỉ dry_run=true báo counts)
        # Nhưng chúng ta có thể kiểm tra errors rỗng.
        assert r["failed"] == 0

    def test_actually_writes_files(self, tmp_path, monkeypatch):
        csv = tmp_path / "real.csv"
        csv.write_text(
            "event_name,event_date,role,what_happened,your_motivation\n"
            "E1,2024-01-01,witness,Chuyện này đã xảy ra rất lâu trước đây,Lý do tôi ở đó rõ ràng\n",
            encoding="utf-8",
        )
        # staging relative to cwd
        monkeypatch.chdir(tmp_path)
        r = bulk_import.bulk_import(csv, target="staging", dry_run=False)
        assert r["imported"] == 1
        assert len(r["written_paths"]) == 1
        assert Path(r["written_paths"][0]).exists()


class TestBulkImportJSONL:
    def test_jsonl_format(self, tmp_path):
        jl = tmp_path / "memories.jsonl"
        jl.write_text(
            json.dumps({
                "event_name": "Event 1", "event_date": "2024-01-01",
                "role": "witness",
                "what_happened": "Chuyện này đã xảy ra rất lâu trước đây",
                "your_motivation": "Lý do tôi ở đó rõ ràng",
            }, ensure_ascii=False) + "\n" +
            json.dumps({
                "event_name": "Event 2", "event_date": "2024-02-01",
                "role": "victim",
                "what_happened": "Chuyện khác đã xảy ra sau đó không lâu",
                "your_motivation": "Tôi cũng có lý do",
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        r = bulk_import.bulk_import(jl, format="jsonl", dry_run=True)
        assert r["rows_read"] == 2
        assert r["imported"] == 2

    def test_jsonl_skips_blank_and_comments(self, tmp_path):
        jl = tmp_path / "with_comments.jsonl"
        content = (
            "# this is a comment\n"
            "\n"  # blank line
            + json.dumps({
                "event_name": "Event", "event_date": "2024-01-01",
                "role": "witness",
                "what_happened": "Chuyện này đã xảy ra rất lâu trước đây",
                "your_motivation": "Lý do tôi ở đó rõ ràng",
            }, ensure_ascii=False) + "\n"
        )
        jl.write_text(content, encoding="utf-8")
        r = bulk_import.bulk_import(jl, format="jsonl", dry_run=True)
        assert r["rows_read"] == 1


class TestI18NFrench:
    """Tiếng Pháp được thêm — kiểm tra parity với vi + en."""

    def test_fr_valid_json(self):
        data = json.loads((REPO / "web/i18n/fr.json").read_text(encoding="utf-8"))
        assert data["_meta"]["code"] == "fr"

    def test_fr_has_same_keys_as_vi(self):
        vi = set(json.loads((REPO / "web/i18n/vi.json").read_text(encoding="utf-8")))
        fr = set(json.loads((REPO / "web/i18n/fr.json").read_text(encoding="utf-8")))
        missing_in_fr = vi - fr
        extra_in_fr = fr - vi
        assert not missing_in_fr, f"French missing: {sorted(missing_in_fr)}"
        assert not extra_in_fr, f"French has extra: {sorted(extra_in_fr)}"

    def test_i18n_js_lists_all_available(self):
        js = (REPO / "web/i18n.js").read_text(encoding="utf-8")
        assert '"vi"' in js
        assert '"en"' in js
        assert '"fr"' in js


class TestSEOGeneration:
    def test_build_seo_creates_files(self, tmp_path):
        # Fake _site
        site = tmp_path / "_site"
        site.mkdir()
        (site / "docs").mkdir()
        (site / "docs" / "ethics.md").write_text("# Ethics", encoding="utf-8")

        # Import and run
        sys.path.insert(0, str(REPO / ".github/workflows"))
        try:
            import build_seo  # type: ignore
            result = build_seo.build_sitemap(site)
            assert "<?xml" in result
            assert "<urlset" in result
            assert "/docs/ethics.md" in result
            assert "/web/" in result
        finally:
            sys.path.remove(str(REPO / ".github/workflows"))


class TestSocialCardScript:
    def test_script_exists_and_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_social_card", REPO / "scripts/gen_social_card.py"
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        # Chỉ check có function generate + main
        spec.loader.exec_module(module)  # type: ignore
        assert callable(module.generate)
        assert callable(module.main)
