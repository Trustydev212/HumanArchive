# Changelog

## [v0.4] — Obsidian vault export + RAG với safeguards

### Obsidian export (`tools/obsidian_export.py`)

Archive phẳng → Obsidian vault với `[[wikilinks]]` tự động dựng graph
view. Một note/event (frontmatter giàu metadata + Mermaid relation
diagram), một note/memory (PII scrubbed + content warning nếu có
trauma), by-role pages, taxonomy pages. Tôn trọng consent filter.

### RAG (`core/rag/`)

RAG đặc thù cho ký ức, không phải RAG cổ điển. Bốn safeguard:

| Rủi ro | Phòng tránh |
|---|---|
| PII leak qua embedding | Scrub PII TRƯỚC khi embed (không sau retrieve) |
| Consent drift | `is_publicly_viewable` + `allows_ai_analysis` filter ở build_index |
| Bias amplification (top-k toàn witness) | `role_balance=True` — top-1 mỗi role trước, rồi fill |
| Identity probe attack | `search_text` scrub PII từ query trước embed |

Pluggable embedder (Voyage nếu có API key / SentenceTransformer /
HashEmbedder zero-dep). Answer pipeline luôn có citations và không bịa
nếu không có hit.

### Tests

- `tests/test_rag.py` — 10 tests, đặc biệt các property đạo đức:
  `test_withdrawn_never_indexed`, `test_embargoed_never_indexed`,
  `test_pii_scrubbed_before_indexing`, `test_query_with_name_is_scrubbed`,
  `test_role_balanced_picks_diverse_roles`.

### Tổng 60 tests pass (50 → 60).

### Tools

- `tools/rag_query.py` — `--build` để build index; `python ... "query"`
  để hỏi. Citations đầy đủ theo memory_id + role.
- `tools/obsidian_export.py` — sinh `obsidian_vault/` mở được trong
  Obsidian/Foam/Logseq.

### Docs

- `docs/rag.md` — giải thích 4 rủi ro đặc thù và cách chống.

---

## [v0.3] — Event decomposition & graph views

Trả lời câu hỏi: "Có nên chia folder theo loại sự kiện (war/, storm/,
covid/) không?" → Không, folder giữ phẳng (immutable), nhưng thêm lớp
metadata (tags, categories, relations) để dựng view phân cấp.

### Thêm mới

- `taxonomy/categories.json` — cây phân loại chuẩn với 8 root (conflict,
  natural-disaster, public-health, humanitarian, economic, social-movement,
  technological, personal-collective). Mỗi node có `label_vi` + `label_en`.
- `core/graph.py` — `load_archive_graph()`, `build_perspective_prism()`,
  `EventNode`, `GraphEdge`, `ArchiveGraph`. Dựng graph từ archive phẳng,
  tôn trọng consent filtering.
- `tools/graph_export.py` — CLI xuất Mermaid / JSON / category tree /
  tag cloud / perspective prism.
- `docs/event_decomposition.md` — giải thích quyết định kiến trúc
  (flat physical + rich metadata + generated views).
- `tests/test_graph.py` — 9 tests: loading, edges, categories, prism,
  consent filtering trong graph.
- Demo event thứ 2 `2024-example-dam-release-demo` + relation edges
  (`caused_by`, `part_of`, `aftermath_of`) nối với event lũ.

### Schema v1 (backward compatible)

- `event.tags`: string[] — tag tự do viết thường-gạch-nối.
- `event.categories`: string[] — path taxonomy, một event có thể có nhiều.
- `context.relations`: [{event_id, type, note?}] — quan hệ có cấu trúc
  với 7 loại (part_of, caused_by, led_to, happened_during, contradicts,
  corroborates, aftermath_of). `contradicts`/`corroborates` KHÔNG phán
  xét đúng/sai — chỉ mô tả trạng thái dữ liệu.

### Tổng test suite: 50 tests pass (41 → 50).

---

## [v0.2] — Enforce 5 nguyên tắc ở tầng code

Không còn chỉ là scaffolding. Các nguyên tắc đạo đức giờ được enforce bằng
code (và có test chứng minh), không chỉ bằng docs.

### Thêm mới

- `core/llm/claude_client.py` — Claude API client thật (Anthropic SDK),
  với prompt-cached system prompt chứa 5 nguyên tắc. Adaptive thinking mặc
  định cho phân tích phức tạp. Fallback an toàn về stub khi không có API key.
- `core/llm/claude_client.py: FORBIDDEN_FIELDS` — danh sách trường phán xét
  (verdict, guilty, is_lying, ...). Mọi output của LLM đi qua
  `_assert_no_forbidden_fields`. Nếu LLM vi phạm nguyên tắc 1, pipeline
  refuse kết quả thay vì truyền đi.
- `core/privacy/pii_scrubber.py` — phát hiện và pseudonymize tên người,
  email, số điện thoại, CCCD/CMND, URL, handle mạng xã hội. PII được scrub
  TRƯỚC KHI gửi lên LLM (nguyên tắc 2).
- `core/integrity.py` — verify `memory_id = sha256(content)[:16]`; filter
  memories theo `consent.public` / `withdrawn` / `embargo_until`; check
  `allow_ai_analysis`. Enforce nguyên tắc 5.
- `core/trauma.py` — phát hiện trauma keyword-based, phân loại 9 category
  (violence, death, sexual_violence, torture, child_harm, self_harm,
  displacement, imprisonment, discrimination), gán severity (mild/severe),
  sinh content warning bilingual. Enforce nguyên tắc 3.
- `tests/` — 41 tests pass:
  - `test_ethics.py`: test cho từng nguyên tắc 1-5.
  - `test_privacy.py`: 13 tests cho PII scrubber.
  - `test_integrity.py`: 12 tests cho memory_id + consent filtering.
- `archive/events/2024-example-village-flood-demo/` — 3 ký ức mẫu HƯ CẤU
  (witness, authority, victim) + `_index.json` (có disclaimer) +
  `HISTORICAL_ENTRY.md` được sinh bởi engine.
- `.github/workflows/ci.yml` — CI chạy trên Python 3.10/3.11/3.12:
  validate JSON Schema, verify archive integrity, chạy toàn bộ tests, sinh
  lại historical entry mẫu.
- `requirements.txt` + `requirements-dev.txt`.

### Cập nhật

- `core/ai_engine.py` — viết lại để wire các module mới:
  - `analyze_memory` giờ gọi Claude thật qua `ClaudeClient`, scrub PII
    trước, phát hiện trauma, kiểm tra `allow_ai_analysis`.
  - `cross_reference` giờ trả thêm `integrity_issues` (memory_id không khớp).
  - `generate_historical_entry` giờ lọc theo consent, thêm content
    warning tổng hợp nếu có trauma severe, pseudonymize trước khi xuất.

### Không đổi

- Schema v1.0 (`core/schema/memory.json`) — không breaking change.
- `tools/submit.py` — CLI vẫn backward compatible.
- 5 nguyên tắc bất biến (`docs/ethics.md`).

## [v0.1] — Initial scaffolding

Vision, manifesto, schema v1, AI engine skeleton, CLI submit.
