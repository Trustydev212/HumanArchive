# Web UI

Single-page static viewer cho HumanArchive. Không cần build, không cần
server backend — chỉ cần một HTTP server tĩnh.

## Chạy

```bash
# Từ repo root
python -m http.server 8000
# Mở: http://localhost:8000/web/
```

Hoặc dùng bất kỳ static server khác (`npx serve`, `caddy file-server`, ...).

## Features

| Page | Đọc file | Tính năng |
|---|---|---|
| `index.html` | `archive/graph.json`, `archive/rag_index.json` | Event browser, Mermaid relation graph, category tree, tag cloud, RAG search |
| `submit.html` | — | Form đóng góp ký ức, live PII scan, download JSON |

## RAG search trong browser

Web UI implement `HashEmbedder` trong JavaScript (`hash_embed.js`), khớp
byte-for-byte với Python version. Khi bạn nhập query:

1. PII được scrub trong browser (`piiScrub` trong `hash_embed.js`)
2. Query được embed bằng HashEmbedder (cùng thuật toán như Python)
3. Cosine similarity với mỗi entry trong `rag_index.json`
4. Role-balanced top-5 (khớp hành vi CLI)

Nếu index được build bằng VoyageEmbedder hoặc SentenceTransformer, Web UI
sẽ hiển thị cảnh báo và yêu cầu dùng CLI thay thế.

## Regenerate dữ liệu trước khi mở

```bash
python tools/graph_export.py json > archive/graph.json
python tools/rag_query.py --build                # tạo archive/rag_index.json
```

## Form đóng góp

`submit.html` là alternative cho `tools/submit.py` khi người đóng góp
không quen terminal. Mọi thứ xảy ra trong browser — không có data gửi
đi đâu cho đến khi người dùng chủ động nhấn "Tải xuống" và gửi file
JSON qua kênh họ chọn (PR, email, USB, ...).

Live PII scan dùng cùng regex patterns như Python version.

## Compatible với

- Browser hiện đại (Chrome 90+, Firefox 90+, Safari 15+) — cần `crypto.subtle`
- Obsidian web preview (nhúng `index.html` vào Obsidian iframe plugin)
- Tor Browser (không gửi request ngoài CDN Mermaid)

## Roadmap

- [ ] Export sang Obsidian-compatible `[[wikilinks]]` trực tiếp từ UI
- [ ] i18n (hiện chỉ tiếng Việt)
- [ ] Offline-first với Service Worker
- [ ] WebAuthn để ký memory client-side (ed25519)
