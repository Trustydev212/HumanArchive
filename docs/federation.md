# Federation v1 — bundle protocol

HumanArchive không cần phụ thuộc vào một server trung tâm. Bất kỳ ai
cũng có thể **export** archive của mình thành bundle, và bất kỳ ai cũng
có thể **import** bundle đó vào archive của mình. Trao đổi qua HTTP,
IPFS, Arweave, email, USB — tùy.

## Định dạng bundle

`bundle.tar.gz` chứa:

```
archive/events/<event_id>/<memory_id>.json   ← dữ liệu gốc
MANIFEST.json                                 ← metadata
SIGNATURE (tuỳ chọn)                          ← ed25519 của MANIFEST
```

`MANIFEST.json`:

```json
{
  "manifest_version": "1",
  "bundle_name": "bundle-20260415T064256Z",
  "created_at": "2026-04-15T06:42:56+00:00",
  "entry_count": 4,
  "event_count": 2,
  "merkle_root": "364c63e1a4a07227228ae7f5b815006fe145c0caeb39848ec07feebacfdf811c",
  "protocol": "humanarchive/v1",
  "pubkey_ed25519_hex": "..."   ← chỉ có khi signed
}
```

## Merkle root

Đảm bảo bundle không bị sửa sau khi tạo:

```
merkle_root = sha256(join("\n", sorted_by_memory_id([
    f"{memory_id}:{sha256(content)[:16]}"
    for each memory in bundle
])))
```

Import process re-compute merkle từ các file thực sự có trong tar, nếu
không khớp với MANIFEST → reject.

## Quy tắc merge

Khi import bundle vào archive đang có:

| Tình huống | Hành động |
|---|---|
| `memory_id` mới | Thêm vào archive |
| `memory_id` trùng, content bit-by-bit giống | Skip (dedup tự nhiên) |
| `memory_id` trùng, content khác | **Reject toàn bundle** — đây là tín hiệu tamper hoặc collision |

Vì `memory_id = sha256(content)[:16]`, case thứ 3 chỉ xảy ra khi:
1. Có ai đó cố tình forge bundle (phát hiện được nhờ signature check)
2. Có hash collision ở 64 bits (cực kỳ hiếm — ~10^-10 với 10^5 memories)

Trong cả hai trường hợp, reject là đúng.

## Chữ ký (tuỳ chọn)

Nếu publisher muốn khẳng định tác giả của bundle:

```bash
# Sinh keypair ed25519
openssl genpkey -algorithm ed25519 -out my_key.pem

# Export kèm chữ ký
python tools/export_bundle.py --sign-key my_key.pem --output signed.tar.gz

# Import với verify
python tools/import_bundle.py signed.tar.gz
```

Pubkey được embed trong MANIFEST. Recipient có thể pin pubkey cụ thể
bằng `--verify-pubkey <hex>` nếu muốn trust một publisher cụ thể.

Cần `pip install cryptography` cho sign/verify.

## Mạng trao đổi

Federation v1 là offline-safe — bundle là một file duy nhất. Các kênh
trao đổi khuyến khích:

| Kênh | Ưu | Nhược |
|---|---|---|
| GitHub release | Dễ, có lịch sử | Phụ thuộc GitHub |
| IPFS pin | Phi tập trung thật | Cần node chạy |
| Arweave | Vĩnh viễn, không xoá được | Có phí |
| Email/USB | Offline hoàn toàn | Khó chia sẻ rộng |

Trong tương lai có thể thêm tầng gossip P2P, nhưng **v1 cố tình không
làm P2P** — độ phức tạp cao, nhiều failure mode. Bundle file + HTTP
mirror đã đủ cho mục đích lưu trữ lâu dài.

## Bạn nên làm gì nếu nhận được bundle từ nguồn không rõ?

1. **Import với `--dry-run` trước** — xem merkle root và số entry.
2. **Đọc một vài memory** bằng tay trước khi trust toàn bộ.
3. Nếu có signature, **verify pubkey khớp với publisher bạn biết**.
4. Import vào một archive riêng (không phải archive chính) để test.
5. Merge vào archive chính chỉ khi đã đọc kỹ và đồng ý với nội dung.

Nhớ: HumanArchive lưu ký ức thật của người thật. Chấp nhận một bundle
nghĩa là bạn cũng chấp nhận trách nhiệm đạo đức với nội dung trong đó.
