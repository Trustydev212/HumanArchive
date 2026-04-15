## Tóm tắt / Summary
<!-- Thay đổi gì, vì sao? / What changed, why? -->

## Loại thay đổi / Type
- [ ] 🐛 Bug fix
- [ ] ✨ Feature
- [ ] 📝 Docs
- [ ] ♻️ Refactor (no behavior change)
- [ ] 🌐 Translation
- [ ] 🧪 Tests

## Checklist chung / General checklist
- [ ] `pytest tests/` pass (82+ tests)
- [ ] Schema vẫn validate: `python -c "import json, jsonschema; jsonschema.Draft7Validator.check_schema(json.load(open('core/schema/memory.json')))"`
- [ ] CHANGELOG.md updated
- [ ] Docs updated (nếu thay đổi behavior)

## Kiểm tra nguyên tắc / Principle check

PR này có đảm bảo 5 nguyên tắc bất biến không?

- [ ] 1. Không thêm trường/hàm/output phán xét đúng-sai
- [ ] 2. Không yêu cầu / expose thông tin định danh
- [ ] 3. Output cảm xúc/trauma được xử lý với content warning
- [ ] 4. Schema / API vẫn giữ `motivation` là required
- [ ] 5. Không thêm code xoá memory / sửa memory / force-push archive

**Nếu có ô không tick:** giải thích vì sao vẫn OK:
<!-- ... -->

## Ảnh hưởng Test Coverage

- Tests mới cho feature này: `tests/test_*.py`
- Tests hiện có bị ảnh hưởng: ...

## Anti-pattern check (xem `docs/workflows.md`)

- [ ] Không tạo role admin với quyền xoá
- [ ] Không tự động "flag fake"
- [ ] Không ép xác thực contributor
- [ ] Không auto-dedup event bằng similarity
- [ ] Không filter memory theo đa số
- [ ] Không ẩn trauma mặc định

## Screenshot / Demo (nếu UI change)
<!-- Paste link / GIF -->

## Breaking change?
- [ ] Yes — `MIGRATION.md` updated
- [ ] No
