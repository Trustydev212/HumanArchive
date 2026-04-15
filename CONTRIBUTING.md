# Contributing to HumanArchive

*English below · Tiếng Việt trước.*

Có nhiều cách để đóng góp, không chỉ là viết code. Mỗi loại đóng góp
đều được chào đón ngang nhau.

## Chọn vai trò phù hợp với bạn

### 🎙️ Contributor — người kể ký ức
Bạn có một ký ức về một sự kiện lịch sử (dù nhỏ, dù mơ hồ)?

1. Đọc `docs/ethics.md` — 5 nguyên tắc bất biến bảo vệ bạn và người khác.
2. Dùng form: `web/submit.html` hoặc CLI: `humanarchive submit`.
3. Bạn không cần định danh. Không ai được phép ép bạn khai danh.
4. Bạn có thể bật `embargo_until` để trì hoãn công bố, hoặc
   `withdrawn` sau này nếu đổi ý.
5. Gửi file JSON qua PR (nếu OK public), hoặc email (nếu nhạy cảm).

### ✍️ Curator — người review không sửa
1. Chạy `humanarchive staging list` để xem inbox.
2. Đọc memory, kiểm tra schema, PII còn sót, gợi ý tag/category.
3. Ghi review: `humanarchive staging review <mid> --type approve --reviewer <your-handle>`.
4. **Không sửa** nội dung. Dùng annotation để gợi ý (contributor tự
   quyết chấp nhận không).

### 📚 Researcher — người tổng hợp lịch sử
1. Clone archive (hoặc fork).
2. Dùng `humanarchive rag "câu hỏi"` hoặc
   `core.ai_engine.generate_historical_entry(event_id)`.
3. Khi publish, **luôn citation** theo format:
   `[memory_id:abc...] role=witness, archive@<git-tag>`.
4. Tôn trọng `consent.embargo_until` — nếu memory đang embargo, không
   được render trong nghiên cứu công khai.

### 🌐 Translator — dịch giả
1. Docs hiện chủ yếu tiếng Việt. Dịch sang EN/FR/ZH/JA/KO/ES rất
   hoan nghênh.
2. Tạo file `docs/<doc>.en.md` song song với `docs/<doc>.md`.
3. Giữ nguyên cấu trúc + code examples. Chỉ dịch prose.
4. Chú thích rõ thuật ngữ văn hoá nếu không có tương đương.

### 💻 Developer — lập trình viên
1. Fork, clone, chạy `pytest tests/` — phải 82/82 pass.
2. Tìm issue gắn tag `good-first-issue` hoặc propose feature mới.
3. Viết test cho mọi feature chạm vào nguyên tắc 1-5
   (xem `tests/test_ethics.py` làm ví dụ).
4. PR phải include:
   - [ ] Tests mới (nếu feature mới)
   - [ ] Tests cũ vẫn pass
   - [ ] Update CHANGELOG.md
   - [ ] Update docs/ nếu thay đổi behavior
   - [ ] **Giải thích rõ** feature này không vi phạm nguyên tắc nào

### 🌍 Node operator — vận hành instance
1. Clone repo, chạy `humanarchive demo`.
2. Đọc `docs/workflows.md` → Instance startup checklist.
3. Tạo `trust/reviewers.json` với curator bạn tin tưởng.
4. Export bundle định kỳ, mirror ≥2 kênh (GitHub + IPFS).

## Quy tắc chung cho mọi PR

### Phải có

- **Không vi phạm 5 nguyên tắc** (xem `docs/ethics.md`).
  Nếu PR của bạn chạm vào ranh giới, hãy giải thích rõ trong PR
  description. Reviewer sẽ đánh giá nghiêm ngặt.
- **Tests pass**: `pytest tests/`
- **Đường dẫn import giữ ổn định** — code ngoài có thể đang dùng
  `from humanarchive import X`.
- **Bilingual comments** cho code tiếp xúc với người đóng góp
  (submit.py, web/submit.html). Internal modules chỉ cần tiếng Việt.

### Không được

- ❌ Tạo role "admin" có quyền xoá memory — vi phạm nguyên tắc 5.
- ❌ Thêm field schema có ý phán xét (`is_fake`, `verdict`, `guilty`) —
  nguyên tắc 1.
- ❌ Ép xác thực danh tính contributor — nguyên tắc 2.
- ❌ Auto-flag memory là "propaganda" / "fake" — chỉ có annotation
  `warning` do cộng đồng thêm thủ công.
- ❌ Ghi đè / force-push vào `archive/events/` branch — protected.

## Code style

- Python 3.10+, type hints ở public API.
- `black` hoặc 4-space indent, max line 100.
- Docstring bằng tiếng Việt OK (đây là dự án Việt-first).
- Commit message theo `<type>(<scope>): <subject>`.

## Báo cáo vấn đề đạo đức

Nếu bạn thấy một PR hoặc issue vi phạm nguyên tắc đạo đức:

1. Comment trên PR với tham chiếu cụ thể đến `docs/ethics.md` số mấy.
2. Nếu nghiêm trọng, tạo issue với template "Ethical concern".
3. Nếu liên quan đến an toàn cá nhân (PII leak, doxxing), email
   riêng `security@...` (khi project thiết lập) thay vì public.

---

## English

Many ways to contribute — not just code. Each is equally welcome.

### 🎙️ Contributor — memory keeper
Share a memory (however small or uncertain). Read `docs/ethics.md`
first. Use `web/submit.html` or `humanarchive submit`. You never have
to identify yourself. You can embargo or withdraw later.

### ✍️ Curator — reviewer
Review incoming memories for schema, missed PII, tag suggestions. You
**never edit** the content — only add annotations. Original
contributor decides what to accept.

### 📚 Researcher — synthesizer
Clone, query via `humanarchive rag`, generate historical entries.
Always cite by memory_id + role + archive version. Respect
`consent.embargo_until`.

### 🌐 Translator
Especially EN/FR/ZH/JA/KO/ES docs. Create parallel `docs/<doc>.en.md`.
Preserve code examples; translate prose only.

### 💻 Developer
Fork, `pytest tests/` must pass 82/82. PRs must include tests,
changelog, and an explanation of which ethical principles were
considered.

### 🌍 Node operator
Run your own instance. See `docs/workflows.md` for the startup
checklist. Mirror bundles across at least two channels.

## Hard rules

- Must not break any of the 5 principles (see `docs/ethics.md`).
- Must not introduce admin/moderator roles with delete power.
- Must not add judgment-flavored schema fields.
- Must not auto-flag "fake" content.
- Must preserve content-addressing (memory_id = sha256(content)[:16]).

## How we review

Every PR is reviewed with two lenses:
1. **Technical** — does it work, is it tested, is it maintainable?
2. **Ethical** — does it respect the 5 principles?

A PR that is technically excellent but ethically ambiguous gets held
for discussion, not merged fast. This is by design.
