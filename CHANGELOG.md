# Changelog

## [v0.6] — Multi-user workflow: staging + annotations + audit

Trả lời: "dùng HumanArchive giữa nhiều người thế nào là tốt nhất?"
Đây là vấn đề workflow, không chỉ code. Thêm 3 pattern cốt lõi:

### 1. Staging area (review trước khi vào archive)

- `tools/staging.py` — submit/list/review/merge.
- Memory mới vào `staging/<memory_id>.json`, curator ký review dưới
  dạng annotation type=review. Đủ N unique reviewers (default 2) →
  `merge` move sang archive + preserve reviews thành annotations để
  audit trail vĩnh viễn.
- Reviews KHÔNG bị xoá sau merge (nguyên tắc 5).

### 2. Annotation layer (context append-only)

- `core/schema/annotation.json` — schema v1.0 với 6 type:
  context, correction, dispute, vouching, review, warning. Cấm type
  mang tính phán xét (verdict, guilty, banned, deleted) — nguyên tắc 1.
- `core/annotations.py` — content-addressed (`annotation_id =
  sha256(content)[:16]`), bất biến, ed25519 sign/verify optional.
- Để "sửa" annotation, phải tạo annotation mới type=correction. Không
  bao giờ ghi đè. Memory gốc không bao giờ bị annotation thay đổi.

### 3. Audit CLI (báo cáo, không gatekeep)

- `tools/audit.py` — report Markdown hoặc JSON, liệt kê:
  integrity issues, possible PII leaks, single-role events, missing
  metadata. KHÔNG reject, KHÔNG xoá — operator xem và quyết định.

### Workflow documentation

- `docs/workflows.md` — 5 personas (contributor / curator / researcher
  / annotator / node operator), web-of-trust model, 3 core workflows
  (contribution / annotation / federation), moderation-without-deletion
  patterns, anti-patterns, instance-startup checklist.

### Tests: 72 → 82 (10 annotation tests).

### End-to-end verified:

- Submit → review (alice + bob) → merge → archive + annotations: OK
- Audit trên demo archive: phát hiện 2 memory có PII (tên người) còn
  sót + 1 event single-role → actionable report không gây friction.

---

## [v0.5] — "Tất cả": 5 hướng tiếp theo cùng lúc

### 1. LLM-aided PII + trauma (graceful fallback)

- `core/privacy/llm_pii.py` — `llm_scan_pii()` bổ sung regex, bắt được:
  tên viết rời ("ng.v.an"), tên không viết hoa ("bí thư xã minh"), biệt
  danh định danh được, chức danh duy nhất, địa chỉ cụ thể. `merge_findings`
  hợp nhất với regex findings mà không double-count.
- `core/trauma_llm.py` — `llm_classify_trauma()` xử lý false positive
  của keyword detector ("giết thời gian" không còn trigger "death"). Nếu
  LLM không available → fallback keyword detector.

### 2. Voyage wire-up

- `requirements.txt` document hai option: Voyage (production), local
  sentence-transformers. `VoyageEmbedder` đã có từ v0.4, chỉ cần set
  `VOYAGE_API_KEY` + `pip install voyageai`.

### 3. Federation protocol v1

- `tools/export_bundle.py` + `tools/import_bundle.py` — export archive
  thành bundle `.tar.gz` với MANIFEST (merkle root + metadata) và
  SIGNATURE tuỳ chọn (ed25519). Import verify merkle + per-memory hash.
- Merge strategy: dedup tự nhiên qua content-addressing. Nếu cùng
  memory_id có content khác → reject bundle.
- `docs/federation.md` — giải thích protocol + khi nên dùng kênh nào
  (GitHub / IPFS / Arweave / email / USB).
- `tests/test_bundle.py` — 6 tests: roundtrip, dedup, merkle stability,
  tamper rejection, dry-run.

### 4. Web UI (single-page static)

- `web/index.html` + `web/app.js` + `web/style.css` — browser đọc
  `archive/graph.json` + `archive/rag_index.json`. Event cards, Mermaid
  relation graph, category tree, tag cloud, modal chi tiết event.
- `web/hash_embed.js` — JS port của Python `HashEmbedder` byte-for-byte
  (sha256 qua `crypto.subtle.digest`). Client-side RAG search với
  role-balanced retrieval + PII scrub từ query. Test parity ở
  `tests/test_js_python_parity.py`.
- Không cần build step. Chạy: `python -m http.server 8000` rồi mở
  `/web/`.

### 5. Web submission form

- `web/submit.html` + `web/submit.js` — form đóng góp client-only, live
  PII scan, memory_id + event_id được tính trong browser khớp Python
  (canonical JSON + sha256). Download JSON, user tự submit qua PR/email.

### Test: 60 → 72 pass (6 bundle + 6 JS/Python parity).

### Limits (trung thực):

- LLM-aided PII/trauma **chưa test end-to-end với Claude API thật** vì
  CI không có key; logic pass với mock, fallback pass với real pipeline.
- Signature verify của federation cần `pip install cryptography`; CI
  chưa bật do không có trong requirements mặc định.
- Web UI chỉ match index được build bằng HashEmbedder (Python
  VoyageEmbedder/SentenceTransformer không reproduce được trong browser).

---

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
