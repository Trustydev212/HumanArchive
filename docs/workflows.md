# Workflows — nhiều người dùng HumanArchive cùng nhau

Tài liệu này trả lời câu hỏi: *"Dùng HumanArchive thế nào là tốt nhất
giữa nhiều người?"* Đây là **design doc**, không phải manual — vì
workflow tốt giữa con người quan trọng hơn code.

## 5 personas chính

| Persona | Làm gì | Không được phép |
|---|---|---|
| **Contributor** | Kể ký ức của mình | Sửa/xoá memory của người khác |
| **Curator** | Review memory mới, gợi ý tag/PII scrub, ký annotation | Sửa nội dung memory |
| **Researcher** | Đọc archive, tổng hợp historical entry, citation | Kết luận đúng/sai (nguyên tắc 1) |
| **Annotator** | Thêm context/correction cho memory cũ | Xoá/sửa memory gốc |
| **Node operator** | Chạy mirror, import/export bundle, ký bundle | Filter nội dung âm thầm |

Không có **admin**. Không có **moderator** theo nghĩa truyền thống
(người có quyền xoá). Nguyên tắc 5 cấm điều đó.

## Trust model — web-of-trust, không phải central authority

```
Contributor (ha-xxxx-yyyy, nặc danh)
     │ submit
     ▼
Curator (handle ổn định + ed25519 pubkey) ──┐
Curator (handle ổn định + ed25519 pubkey) ──┼─── N approvals → merge
Curator (handle ổn định + ed25519 pubkey) ──┘
     │
     ▼
Archive (immutable, content-addressed)
     │
     ▼
Annotator (có thể là curator cũ hoặc người mới)
     │ thêm context/correction/vouching (append-only)
     ▼
Reader / Researcher
```

**Contributor** không cần định danh. **Curator** có handle ổn định +
pubkey để review có thể verify. **Cộng đồng** duy trì `trust/reviewers.json`
(list pubkey được vouch). Mỗi instance chọn threshold riêng — không có
regulation chung.

## 3 workflow cốt lõi

### 1. Contribution pipeline

```
[contributor]           [staging/]                [curators]         [archive/]
     │                      │                         │                   │
     │ submit.py or         │                         │                   │
     │ web/submit.html      │                         │                   │
     ├─────────────────────▶│                         │                   │
     │                      │ staging.py list         │                   │
     │                      ◀─────────────────────────┤                   │
     │                      │ staging.py review       │                   │
     │                      │   --type approve        │                   │
     │                      ◀─────────────────────────┤                   │
     │                      │                         │                   │
     │                      │ (khi đủ N approvals)    │                   │
     │                      │ staging.py merge ──────────────────────────▶│
     │                      │                         │                   │
     │                      │                         │ reviews được      │
     │                      │                         │ preserve thành    │
     │                      │                         │ annotations/
```

Xem `tools/staging.py`:

```bash
# Contributor
python tools/submit.py > /tmp/my_memory.json
python tools/staging.py submit /tmp/my_memory.json

# Curator (Alice)
python tools/staging.py list
python tools/staging.py review <memory_id> --type approve --reviewer alice-pubkey-hex

# Curator (Bob) — approval độc lập
python tools/staging.py review <memory_id> --type approve --reviewer bob-pubkey-hex

# Bất cứ ai có quyền chạy merge (khi đủ approvals)
python tools/staging.py merge <memory_id> --threshold 2
```

Reviews không bị xoá sau merge — được copy sang `archive/annotations/<memory_id>/`
để audit trail vĩnh viễn.

### 2. Post-archive annotation (ký ức đã trong archive, muốn thêm context)

Memory được đăng năm 2025. Năm 2040 có người phát hiện:
- Một chi tiết có thể khác với record khác → `type: correction`
- Bổ sung bối cảnh không có trong memory gốc → `type: context`
- Không đồng ý với cách trình bày → `type: dispute`
- Cá nhân xác nhận đã chứng kiến cùng sự kiện → `type: vouching`

Không sửa memory gốc. Tạo annotation:

```python
from core.annotations import create_annotation, save_annotation

a = create_annotation(
    target_memory_id="abc123...",
    author_id="ha-annotator-xxxx",  # hoặc pubkey hex
    type="correction",
    content="Theo record ngành khí tượng, cơn bão vào lúc 14:30 thay vì 14:00.",
    suggested_changes=None,  # không áp đặt — chỉ thông tin
)
save_annotation(a, archive_root="archive")
```

Khi render historical entry, AI engine hiển thị annotations kèm memory
gốc — **không thay thế**. Người đọc tự đánh giá.

### 3. Federation giữa các node

```
Node A (Việt Nam)              Node B (hải ngoại)
     │                              │
     │ export_bundle.py             │
     │  --sign-key alice_priv.pem   │
     ├─── bundle_A.tar.gz ─────────▶│
     │                              │ import_bundle.py
     │                              │  --verify-pubkey alice_pub_hex
     │                              │
     │◀──── bundle_B.tar.gz ────────┤ export_bundle.py
     │                              │
     │ import (dedup content-hash)  │
```

Content-addressing đảm bảo **dedup tự động** dù hai node có cùng
memory. Signature bảo đảm bundle không bị tamper trên đường đi. Xem
`docs/federation.md`.

## Moderation mà KHÔNG xoá — pattern thực tế

Nguyên tắc 5 nghiêm ngặt, nhưng vẫn cần xử lý abuse. Đây là cách:

| Trường hợp | Xử lý |
|---|---|
| Contributor muốn rút memory của mình | Set `consent.withdrawn = true` qua amendment. Memory gốc vẫn trong archive (giữ audit trail), không hiển thị ở historical entry / Web UI / RAG |
| Spam / bot nội dung vô nghĩa | Annotation `warning` type=community-flagged. Web UI có thể ẩn dựa trên threshold warnings — không xoá khỏi archive |
| Hate speech, đe doạ cụ thể | Annotation `warning` + instance operator có thể **không serve** memory đó ở UI của họ (policy cấp instance, không cấp protocol). Memory vẫn tồn tại ở các mirror khác. |
| Nội dung bất hợp pháp (CSAM, đe doạ tính mạng) | Đây là **ngoại lệ** không tránh được. Operator có thể physical-remove khỏi instance của họ, ghi rõ trong `archive/REMOVALS.md` với lý do + không kèm memory_id (để không tạo streisand effect). Bundle mirror nơi khác vẫn giữ — đây là giới hạn pháp lý, không phải triết lý. |

**Quan trọng**: không có mechanism nào khiến bất kỳ ai (kể cả admin
instance) có thể *sửa* memory của người khác. Chỉ có: withdrawn,
warning annotation, instance-level filter (không ảnh hưởng federation).

## Audit định kỳ — không gatekeep, chỉ báo cáo

```bash
python tools/audit.py --archive archive --format md > AUDIT.md
```

Report liệt kê:
- Memory `memory_id` không khớp content (tamper) — nghiêm trọng
- Memory có thể PII còn sót — cần curator xem
- Event chỉ 1 góc nhìn — **không phải lỗi**, chỉ nhắc nhở kêu gọi
  role khác đóng góp
- Thiếu metadata khuyến nghị (tags, categories, age) — optional

Output là Markdown để review bằng mắt, hoặc JSON để integrate.

## Pattern từ các dự án tương tự

| Dự án | Điều HumanArchive học từ đó |
|---|---|
| **Wikipedia** | Talk page — mọi chỉnh sửa có lịch sử + lý do; ở ta: annotations layer |
| **Linux kernel** | Sign-off chain — `Reviewed-by`, `Acked-by`; ở ta: ed25519 signatures trên reviews |
| **Debian package maintainer** | DD (Debian Developer) trust hierarchy; ở ta: `trust/reviewers.json` web-of-trust |
| **Archive.org** | Immutable snapshots + metadata-only indexing; ở ta: content-addressing + graph |
| **Git** | Content-addressed, signed commits, merge không xoá; ở ta: memory_id = sha256, bundle signature |
| **Mastodon federation** | Mỗi instance tự moderate; ở ta: instance-level filter không ảnh hưởng protocol |

## Anti-patterns — đừng làm

- ❌ **Tạo role "admin" có quyền xoá** — vi phạm nguyên tắc 5
- ❌ **AI tự động flag "fake memory"** — vi phạm nguyên tắc 1
- ❌ **Ép contributor xác thực danh tính** — vi phạm nguyên tắc 2
- ❌ **Tự động dedup event có tên gần giống** — mất đa góc nhìn; dùng
  `context.relations` thay vào đó
- ❌ **Reject memory khác ý kiến đa số** — chính là cái bias mà dự án
  tồn tại để chống lại
- ❌ **Ẩn trauma memory mặc định** — vi phạm đồng cảm và agency của
  người kể; hiện content warning, để người đọc chọn

## Checklist khởi động một instance mới

1. Clone repo, chạy `pytest tests/` — phải 82/82 pass
2. Tạo `trust/reviewers.json` với pubkey của 3-5 người bạn tin tưởng
3. Chọn threshold approval (2 cho cộng đồng nhỏ, 3-5 cho lớn)
4. Thiết lập process minh bạch để thêm curator mới (PR vào
   `trust/reviewers.json` cần existing curators vouch)
5. Công khai chính sách instance-level filter (nếu có), ví dụ: "Instance
   này không serve memory có annotation `warning: csam`. Memory vẫn
   tồn tại ở archive và federation."
6. Chạy `python tools/audit.py` định kỳ (hàng tháng)
7. Export bundle định kỳ và mirror ở ≥2 kênh khác nhau (GitHub + IPFS)
