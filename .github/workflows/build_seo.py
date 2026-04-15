#!/usr/bin/env python3
"""Sinh robots.txt và sitemap.xml cho SEO.

Chạy trong CI sau khi _site/ được build. Sitemap liệt kê:
    - / (landing)
    - /web/ (archive browser)
    - /web/submit.html
    - /archive/TIMELINE.html
    - /archive/AUDIT.md
    - /docs/*.md (public docs)
    - /obsidian_vault/events/*.md

Priority + changefreq heuristic:
    - Landing & web browser: daily, priority 1.0
    - Submit form: weekly, 0.8
    - Archive data: weekly, 0.6
    - Docs: monthly, 0.5
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


BASE_URL = "https://trustydev212.github.io/HumanArchive"

ROBOTS = """# HumanArchive robots.txt
User-agent: *
Allow: /

# Archive data — index for search engines
Sitemap: {base}/sitemap.xml

# Don't crawl the service worker or manifest fetch
Disallow: /web/sw.js

# Respect user privacy — don't archive offline page deep crawl
Disallow: /404.html
Disallow: /web/offline.html
"""


def build_sitemap(site_dir: Path, base_url: str = BASE_URL) -> str:
    """Walk _site/ và liệt kê HTML/markdown public URLs."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entries: list[tuple[str, float, str]] = [
        ("/", 1.0, "daily"),
        ("/web/", 1.0, "daily"),
        ("/web/submit.html", 0.8, "weekly"),
        ("/archive/TIMELINE.html", 0.6, "weekly"),
        ("/archive/AUDIT.md", 0.5, "weekly"),
    ]

    # Auto-discover docs
    docs = site_dir / "docs"
    if docs.exists():
        for p in sorted(docs.glob("*.md")):
            rel = "/docs/" + p.name
            entries.append((rel, 0.5, "monthly"))

    # Auto-discover obsidian event pages (publicly viewable only,
    # because obsidian_export.py already filtered consent)
    ob_events = site_dir / "obsidian_vault" / "events"
    if ob_events.exists():
        for p in sorted(ob_events.glob("*.md")):
            rel = "/obsidian_vault/events/" + p.name
            entries.append((rel, 0.7, "weekly"))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, priority, freq in entries:
        url = base_url + path
        lines.append(f"  <url>")
        lines.append(f"    <loc>{escape(url)}</loc>")
        lines.append(f"    <lastmod>{now}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{priority:.1f}</priority>")
        lines.append(f"  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: build_seo.py <_site_dir>", file=sys.stderr)
        return 1
    site = Path(sys.argv[1])
    if not site.exists():
        print(f"{site} does not exist", file=sys.stderr)
        return 1

    (site / "robots.txt").write_text(
        ROBOTS.format(base=BASE_URL), encoding="utf-8"
    )
    (site / "sitemap.xml").write_text(
        build_sitemap(site), encoding="utf-8"
    )
    print(f"Wrote robots.txt + sitemap.xml in {site}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
