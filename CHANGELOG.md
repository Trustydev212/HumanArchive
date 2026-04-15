# Changelog

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
