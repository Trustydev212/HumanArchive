# Trust — Web-of-trust cho curators

Thư mục này chứa **danh sách pubkey** của các reviewer/curator được
cộng đồng tin tưởng. Đây là **web-of-trust**, không phải central authority.

## Cấu trúc

```
trust/
├── reviewers.json       # Danh sách canonical — chỉ append-only
├── README.md            # File này
└── REVOCATIONS.md       # Log khi có reviewer bị revoke (không xoá entry)
```

## Format `reviewers.json`

```json
{
  "reviewers": [
    {
      "handle": "alice",
      "pubkey_ed25519_hex": "abc123...",
      "added_at": "2025-01-15T10:00:00+00:00",
      "vouched_by": ["bob", "carol"],
      "role_focus": ["curator", "translator"],
      "languages": ["vi", "en"],
      "status": "active"
    }
  ]
}
```

Trường:
- `handle` — chuỗi ổn định, không cần là tên thật
- `pubkey_ed25519_hex` — public key ed25519 64-char hex
- `added_at` — ISO-8601
- `vouched_by` — list handle của reviewer hiện có đã vouch
- `role_focus` — curator / researcher / translator / node_operator
- `languages` — ISO 639-1 codes
- `status` — `active` | `revoked` (không xoá entry, chỉ đổi status)

## Thêm reviewer mới

1. Sinh ed25519 keypair:
   ```bash
   openssl genpkey -algorithm ed25519 -out alice_private.pem
   openssl pkey -in alice_private.pem -pubout -text \
     | grep -A2 "pub:" | tail -n +2 | tr -d " \n:" | cut -c3-
   # → 64 hex chars = pubkey
   ```

2. Ký một "introduction" annotation bằng private key:
   ```python
   from core.annotations import create_annotation, sign_annotation

   a = create_annotation(
       target_memory_id="0"*16,  # hoặc một sự kiện công khai đáng kể
       author_id="alice",
       type="vouching",
       content="Tôi là alice, pubkey XXX, muốn tham gia làm curator."
   )
   with open("alice_private.pem", "rb") as f:
       a = sign_annotation(a, f.read())
   ```

3. Mở PR sửa `trust/reviewers.json`:
   - Thêm entry mới với `status: "active"`, `vouched_by: []`
   - Attach introduction annotation đã ký

4. **Cần ít nhất 2 reviewer hiện có vouch** — họ comment trên PR với
   một annotation `vouching` đã ký bằng pubkey của họ

5. Sau khi đủ quorum → merge PR

## Revoke reviewer

Lý do: key bị leak, reviewer vi phạm Code of Conduct, reviewer tự
rút tên.

1. Mở issue trước để thảo luận (`trust-revoke`)
2. **Cần ít nhất 3 reviewer hiện có đồng ý** (quorum cao hơn vì đây
   là destructive trust decision)
3. Mở PR đổi `status: "active"` → `status: "revoked"`, thêm
   `revoked_at` + `revoked_reason`
4. Cập nhật `REVOCATIONS.md` với link PR + lý do
5. Merge

**KHÔNG xoá entry**. Mục đích giữ: nếu reviewer đã ký review cho N
memory trong quá khứ, chữ ký đó vẫn verify được (pubkey vẫn ở file).
Người đọc biết reviewer đã bị revoke và có thể tự cân nhắc mức trust
của các review cũ.

## Threshold

Mỗi instance tự chọn threshold. Default của project:
- **Merge memory từ staging**: 2 approvals
- **Merge PR sửa schema/core**: 3 approvals
- **Revoke reviewer**: 3 approvals

Set qua env: `HUMANARCHIVE_APPROVAL_THRESHOLD=3 humanarchive staging merge ...`

## Verify signature chain

```bash
humanarchive verify-signatures --trust-file trust/reviewers.json
```

Chạy qua mọi annotation trong `archive/annotations/`, verify:
- Signature khớp với pubkey declared trong annotation
- Pubkey có trong `reviewers.json` với status active
- Chuỗi vouching (ai vouch ai) tạo thành graph không có cycle

## Threat model

Web-of-trust dễ bị:
- **Sybil attack**: 1 người tạo nhiều reviewer giả để vouch nhau
  → Mitigation: quorum PR review + thảo luận công khai trước merge
- **Key compromise**: reviewer bị hack private key
  → Mitigation: process revoke nhanh, nhưng annotations cũ vẫn có
     signature hợp lệ. Người đọc nên skeptical với reviews từ reviewer
     đã revoke, đặc biệt các review gần thời điểm revoke
- **Bitrot**: reviewer mất private key
  → Accept — reviewer không ký được nữa, de-facto inactive

Không có giải pháp kỹ thuật hoàn hảo. Đây là **công cụ cho cộng đồng
cẩn trọng**, không phải oracle về độ tin cậy.
