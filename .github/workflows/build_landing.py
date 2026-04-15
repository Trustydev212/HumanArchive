#!/usr/bin/env python3
"""Sinh landing page cho GitHub Pages với live stats từ archive/graph.json.

Chạy trong CI sau khi graph.json đã được regen. Output là 1 file HTML
self-contained (không CDN).

Sử dụng:
    python .github/workflows/build_landing.py _site/index.html
"""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: build_landing.py <output.html>", file=sys.stderr)
        return 1
    out_path = Path(sys.argv[1])

    graph_path = Path("archive/graph.json")
    stats = {"events": 0, "memories": 0, "edges": 0, "roles": 0, "tags": 0}
    if graph_path.exists():
        g = json.loads(graph_path.read_text(encoding="utf-8"))
        stats["events"] = len(g["nodes"])
        stats["memories"] = sum(n.get("memory_count", 0) for n in g["nodes"])
        stats["edges"] = len(g["edges"])
        stats["roles"] = len(
            {r for n in g["nodes"] for r in n.get("roles_present", [])}
        )
        stats["tags"] = len(g.get("tag_counts", {}))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    page = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HumanArchive — Decentralized collective memory</title>
<meta name="description" content="Lưu trữ ký ức tập thể phi tập trung của nhân loại. Không phán xét — chỉ lắng nghe.">
<meta property="og:title" content="HumanArchive">
<meta property="og:description" content="Decentralized collective memory archive — without judgment.">
<meta property="og:image" content="assets/banner.svg">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/svg+xml" href="web/icons/icon.svg">
<link rel="apple-touch-icon" href="web/icons/icon.svg">
<style>
:root {{
  --bg: #faf7f0; --card: #fff; --fg: #1f1f1f; --muted: #6a6a6a;
  --accent: #8b4513; --border: #e2ddd3; --glow: #f0e8d4;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", "Noto Sans", sans-serif; }}
.wrap {{ max-width: 980px; margin: 0 auto; padding: 2rem 1.5rem; }}
.hero {{ background: linear-gradient(180deg, #faf7f0, #f0e8d4);
  border-radius: 12px; padding: 2.5rem 1.5rem; text-align: center;
  margin-bottom: 2rem; border: 1px solid var(--border); }}
.hero img {{ max-width: 100%; }}
.hero h1 {{ margin: 1rem 0 0.3rem; color: var(--accent); font-size: 2rem; }}
.hero p {{ color: var(--muted); margin: 0; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 1rem; justify-content: center;
  margin: 2rem 0; }}
.stat {{ background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 1rem 1.5rem; min-width: 130px; text-align: center; }}
.stat b {{ display: block; font-size: 1.8rem; color: var(--accent); }}
.stat span {{ color: var(--muted); font-size: 0.85rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem; margin: 2rem 0; }}
.card {{ background: var(--card); border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 8px; padding: 1.2rem 1.4rem; text-decoration: none; color: var(--fg);
  transition: transform 0.1s, border-color 0.1s; }}
.card:hover {{ transform: translateY(-2px); border-color: var(--accent); }}
.card h3 {{ margin: 0 0 0.4rem; color: var(--accent); }}
.card p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}
.principles {{ background: var(--card); border: 1px solid var(--border);
  border-radius: 8px; padding: 1.5rem 1.7rem; margin: 2rem 0; }}
.principles h2 {{ margin-top: 0; }}
.principles ol {{ margin: 0; padding-left: 1.2rem; }}
.principles li {{ margin: 0.4rem 0; }}
.install {{ background: #2a1a0a; color: #f0e8d4; padding: 1.2rem 1.5rem;
  border-radius: 8px; font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
  font-size: 0.9rem; overflow-x: auto; margin: 1rem 0; }}
.install .comment {{ color: #a08a60; }}
footer {{ text-align: center; color: var(--muted); font-size: 0.85rem;
  padding: 2rem 0; border-top: 1px solid var(--border); margin-top: 3rem; }}
footer a {{ color: var(--accent); }}
.lang-switch {{ position: absolute; top: 16px; right: 18px; font-size: 0.9rem; }}
.lang-switch a {{ color: var(--muted); text-decoration: none; padding: 4px 8px; }}
.lang-switch a.active {{ background: var(--accent); color: white; border-radius: 4px; }}
@media (max-width: 600px) {{
  .hero {{ padding: 1.5rem 1rem; }}
  .hero h1 {{ font-size: 1.5rem; }}
}}
</style>
</head>
<body>
<div class="wrap">
<section class="hero">
  <img src="assets/banner.svg" alt="HumanArchive banner">
</section>

<section>
  <div class="stats">
    <div class="stat"><b>{stats['events']}</b><span>events</span></div>
    <div class="stat"><b>{stats['memories']}</b><span>memories</span></div>
    <div class="stat"><b>{stats['edges']}</b><span>relations</span></div>
    <div class="stat"><b>{stats['roles']}</b><span>roles represented</span></div>
    <div class="stat"><b>{stats['tags']}</b><span>tags</span></div>
  </div>
</section>

<section class="cards">
  <a class="card" href="web/">
    <h3>🔍 Khám phá archive</h3>
    <p>Browse events, xem graph quan hệ, search ngữ nghĩa (RAG role-balanced).</p>
  </a>
  <a class="card" href="web/submit.html">
    <h3>✍️ Đóng góp ký ức</h3>
    <p>Form nặc danh, client-only, có PWA install + offline draft.</p>
  </a>
  <a class="card" href="archive/TIMELINE.html">
    <h3>📅 Timeline</h3>
    <p>Các events theo trục thời gian, có content warnings cho trauma.</p>
  </a>
  <a class="card" href="obsidian_vault/">
    <h3>🧠 Obsidian vault</h3>
    <p>Snapshot vault để mở trong Obsidian/Foam/Logseq.</p>
  </a>
  <a class="card" href="docs/ethics.md">
    <h3>⚖️ 5 nguyên tắc</h3>
    <p>Các ràng buộc đạo đức bất biến — được enforce bằng code, không chỉ docs.</p>
  </a>
  <a class="card" href="https://github.com/Trustydev212/HumanArchive">
    <h3>💻 Source code</h3>
    <p>MIT license. 135 tests pass. Python 3.10+. Claude Opus 4.6.</p>
  </a>
</section>

<section class="principles">
  <h2>5 nguyên tắc bất biến</h2>
  <ol>
    <li><strong>Không phán xét</strong> — AI không kết luận ai đúng ai sai.</li>
    <li><strong>Không xác định danh tính</strong> — PII được scrub trước khi hiển thị/index.</li>
    <li><strong>Đồng cảm trước phân tích</strong> — trauma được cảnh báo, không gatekeep.</li>
    <li><strong>Động cơ quan trọng hơn hành động</strong> — every memory bắt buộc có motivation.</li>
    <li><strong>Dữ liệu thô không đổi</strong> — withdrawn/embargo filter, memory_id = sha256 verifiable.</li>
  </ol>
</section>

<section>
  <h2>Install locally</h2>
  <div class="install">
<span class="comment"># Clone + install</span>
git clone https://github.com/Trustydev212/HumanArchive
cd HumanArchive &amp;&amp; pip install -e .

<span class="comment"># One-command demo</span>
humanarchive demo

<span class="comment"># Contribute a memory (agent-friendly, non-interactive)</span>
echo '{{...json...}}' | humanarchive submit --from-stdin --json

<span class="comment"># RAG search (role-balanced, PII-scrubbed)</span>
humanarchive rag --json "câu hỏi"
  </div>
</section>

</div>

<footer>
  <p>
    Last build: {now} ·
    <a href="https://github.com/Trustydev212/HumanArchive">GitHub</a> ·
    <a href="https://github.com/Trustydev212/HumanArchive/blob/main/CHANGELOG.md">Changelog</a> ·
    <a href="docs/AGENT.md">Agent integration</a>
  </p>
  <p>
    Code: <a href="https://github.com/Trustydev212/HumanArchive/blob/main/LICENSE">MIT</a> ·
    Content: <a href="https://github.com/Trustydev212/HumanArchive/blob/main/LICENSE-CONTENT">CC-BY-SA 4.0</a>
    <span style="color:#8b4513"> + ethical clauses</span>
  </p>
</footer>
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    print(f"Wrote landing → {out_path} ({len(page)} bytes, stats: {stats})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
