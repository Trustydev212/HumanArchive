"""Test PWA manifest + i18n JSON consistency + Web UI file integrity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "web"


class TestPWAManifest:
    def test_manifest_is_valid_json(self):
        m = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
        assert m["name"] == "HumanArchive"
        assert m["start_url"]
        assert m["display"] in ("standalone", "fullscreen", "minimal-ui", "browser")

    def test_manifest_has_icons(self):
        m = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
        assert len(m["icons"]) >= 1
        for icon in m["icons"]:
            icon_path = WEB / icon["src"]
            assert icon_path.exists(), f"Icon missing: {icon['src']}"

    def test_manifest_theme_colors_valid_hex(self):
        m = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
        import re
        hex_re = re.compile(r"^#[0-9a-fA-F]{3,8}$")
        assert hex_re.match(m["theme_color"])
        assert hex_re.match(m["background_color"])


class TestServiceWorker:
    def test_sw_js_exists(self):
        assert (WEB / "sw.js").exists()

    def test_sw_precaches_critical_assets(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        for asset in ("index.html", "submit.html", "style.css", "app.js",
                       "submit.js", "i18n.js", "hash_embed.js",
                       "manifest.webmanifest", "offline.html"):
            assert asset in sw, f"SW doesn't precache: {asset}"

    def test_sw_has_stale_while_revalidate_for_archive(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        assert "staleWhileRevalidate" in sw
        assert "ARCHIVE_PATTERN" in sw

    def test_offline_html_exists(self):
        offline = WEB / "offline.html"
        assert offline.exists()
        text = offline.read_text(encoding="utf-8")
        assert "offline" in text.lower()


class TestI18NConsistency:
    """Cả 2 ngôn ngữ phải có cùng bộ keys — không miss bản dịch nào."""

    def _load(self, code):
        return json.loads((WEB / "i18n" / f"{code}.json").read_text(encoding="utf-8"))

    def test_vi_valid_json(self):
        data = self._load("vi")
        assert data["_meta"]["code"] == "vi"

    def test_en_valid_json(self):
        data = self._load("en")
        assert data["_meta"]["code"] == "en"

    def test_same_keys_in_both_languages(self):
        vi = set(self._load("vi"))
        en = set(self._load("en"))
        missing_in_en = vi - en
        missing_in_vi = en - vi
        assert not missing_in_en, f"Keys in vi but missing en: {sorted(missing_in_en)}"
        assert not missing_in_vi, f"Keys in en but missing vi: {sorted(missing_in_vi)}"

    def test_required_keys_present(self):
        """Các key được app.js / submit.js / pwa.js dùng phải có."""
        required = [
            "site.title", "site.tagline",
            "nav.overview", "nav.events", "nav.graph", "nav.search", "nav.contribute",
            "overview.loading", "overview.principles_title",
            "stats.events", "stats.memories",
            "events.filter_placeholder", "events.no_match",
            "search.button", "search.placeholder", "search.index_ready",
            "search.query_scrubbed", "search.no_hits",
            "submit.title", "submit.button.preview", "submit.button.download",
            "submit.field.event_name", "submit.field.your_motivation",
            "submit.pii.none",
            "pwa.install", "pwa.update_available", "pwa.reload",
        ]
        vi = self._load("vi")
        en = self._load("en")
        for key in required:
            assert key in vi, f"Missing vi key: {key}"
            assert key in en, f"Missing en key: {key}"

    def test_placeholders_consistent(self):
        """{n}, {embedder}, {dim}, {q} phải xuất hiện ở cả 2 ngôn ngữ cho cùng key."""
        import re
        vi = self._load("vi")
        en = self._load("en")
        ph_re = re.compile(r"\{(\w+)\}")
        for key in vi:
            if key.startswith("_"):
                continue
            vi_phs = set(ph_re.findall(str(vi[key])))
            en_phs = set(ph_re.findall(str(en[key])))
            assert vi_phs == en_phs, (
                f"Placeholder mismatch at '{key}': "
                f"vi has {vi_phs}, en has {en_phs}"
            )


class TestHTMLUsesI18N:
    """HTML phải dùng data-i18n attributes, không hardcode strings."""

    def test_index_has_i18n_attributes(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        # Ít nhất các section headers phải dùng data-i18n
        assert 'data-i18n="site.title"' in html
        assert 'data-i18n="nav.overview"' in html
        assert 'data-i18n="search.title"' in html or 'data-i18n="search.button"' in html

    def test_submit_has_i18n_attributes(self):
        html = (WEB / "submit.html").read_text(encoding="utf-8")
        assert 'data-i18n="submit.title"' in html
        assert 'data-i18n="submit.section.motivation"' in html
        assert 'data-i18n="submit.button.download"' in html

    def test_index_links_manifest(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        assert 'rel="manifest"' in html
        assert "manifest.webmanifest" in html

    def test_submit_links_manifest(self):
        html = (WEB / "submit.html").read_text(encoding="utf-8")
        assert 'rel="manifest"' in html
