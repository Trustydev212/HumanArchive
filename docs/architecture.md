# Architecture — Thiết kế hệ thống HumanArchive

## Tổng quan

HumanArchive là một hệ thống **phi tập trung** với 4 tầng chính:

```
┌───────────────────────────────────────────────────────────┐
│  1. COLLECTION LAYER   (tools/submit.py, mobile app, ...)  │
│     Thu thập ký ức từ người đóng góp                       │
└─────────────────────────┬─────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────┐
│  2. SCHEMA & VALIDATION LAYER  (core/schema/memory.json)  │
│     Đảm bảo mọi ký ức có cấu trúc nhất quán               │
└─────────────────────────┬─────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────┐
│  3. ARCHIVE LAYER  (archive/events/<event_id>/*.json)      │
│     Lưu trữ bất biến, content-addressed                    │
└─────────────────────────┬─────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────┐
│  4. ANALYSIS LAYER  (core/ai_engine.py, verification/)    │
│     Phân tích động cơ, cross-reference, tạo entry lịch sử │
└───────────────────────────────────────────────────────────┘
```

---

## 1. Collection Layer

**Mục đích:** Thu thập ký ức một cách an toàn, thân thiện, và bảo vệ danh tính.

**Các kênh đóng góp:**
- `tools/submit.py`: CLI chính thức, hỗ trợ offline.
- Mobile companion (roadmap): ghi âm → transcribe local → submit.
- Web form (roadmap): có thể dùng trong trình duyệt Tor.

**Nguyên tắc:**
- Mọi submission đều được **ký** bằng một khóa ephemeral do thiết bị người
  dùng tạo ra. Không gửi khóa lên server.
- `contributor_id` được sinh bởi hash của (public_key + salt). Không thể
  truy ngược về thiết bị.
- Người đóng góp có thể đặt `embargo_until` để trì hoãn công bố (ví dụ: sau
  khi chế độ hiện tại kết thúc, hoặc sau khi họ qua đời).

---

## 2. Schema & Validation Layer

**File chính:** `core/schema/memory.json`

Chuẩn dữ liệu (v1) mô tả một ký ức tối thiểu bao gồm:

| Nhóm | Trường | Ý nghĩa |
|------|--------|---------|
| `event` | `name`, `date`, `location` | Sự kiện được nói đến |
| `perspective` | `role` | participant / witness / authority / organizer / victim / bystander |
| `memory` | `what_happened` | Mô tả từ góc nhìn cá nhân |
| `motivation` | `your_motivation` | Vì sao bạn làm/ở đó |
| `motivation` | `external_pressure` | Ai/tổ chức ảnh hưởng đến bạn |
| `context` | `what_learned_after` | Nhìn lại, bạn hiểu thêm điều gì |
| `consent` | `embargo_until`, `withdrawn` | Kiểm soát công bố |

**Validation:**
- Thiếu `motivation.your_motivation` → từ chối (nguyên tắc 4).
- `perspective.role` không nằm trong enum → từ chối.
- `event.date` phải là ISO-8601.

---

## 3. Archive Layer

**Cấu trúc thư mục:**

```
archive/
└── events/
    └── <event_id>/
        ├── <memory_id_1>.json
        ├── <memory_id_2>.json
        ├── ...
        └── _index.json    # Danh sách memory_id + metadata tóm tắt
```

**Đặc điểm:**
- **Content-addressed**: `memory_id = sha256(canonical_json(memory))[:16]`.
  Cùng nội dung → cùng ID → dedup tự nhiên.
- **Bất biến**: file chỉ được thêm, không bao giờ ghi đè. Amendment được
  tạo thành file riêng `<memory_id>.amend.<n>.json`.
- **Git-based**: dùng git để đạt tính bất biến + audit trail miễn phí.
  Branch `archive/*` được protected.

**Event ID:**
- Tạo bởi cộng đồng khi sự kiện đầu tiên được submit. Format:
  `<yyyy>-<slug>-<4charhash>` (ví dụ: `1975-saigon-fall-a3f2`).
- Một `event_id` có thể được alias nếu nhiều nhóm dùng tên khác nhau cho
  cùng sự kiện. AI engine phát hiện và đề xuất merge.

---

## 4. Analysis Layer

### 4.1 AI Engine (`core/ai_engine.py`)

**3 hàm chính:**

| Hàm | Input | Output | Mục đích |
|-----|-------|--------|----------|
| `analyze_memory(memory)` | 1 memory | Dict phân tích | Tìm hiểu động cơ, áp lực, trạng thái cảm xúc |
| `cross_reference(memories)` | List memory (cùng event) | Dict báo cáo | Tìm điểm trùng/mâu thuẫn giữa các góc nhìn |
| `generate_historical_entry(event_id)` | event_id | Markdown | Tạo entry lịch sử đa góc nhìn cho thế hệ sau |

**Ràng buộc đạo đức trong engine:**
- Không trả về trường `verdict`, `is_lying`, `guilty_party`, hoặc bất kỳ
  trường mang tính phán xét nào.
- Mọi output đều có trường `uncertainty` ghi rõ độ không chắc chắn.
- Output luôn song ngữ (tối thiểu vi + en) để giảm bias ngôn ngữ.

### 4.2 Verification (`core/verification/`)

**Không phải "fact-checking"** — đây là cross-validation.

| Module | Chức năng |
|--------|-----------|
| `cross_check.py` | So khớp các claim atomic (thời gian, địa điểm, người có mặt) giữa nhiều memory |
| `timeline.py` (roadmap) | Sắp xếp các memory theo trục thời gian, phát hiện inconsistency |
| `geocheck.py` (roadmap) | Kiểm tra các địa điểm được nói đến có khớp về không gian không |

**Output mẫu:**
```json
{
  "event_id": "1975-saigon-fall-a3f2",
  "convergent_claims": [
    {"claim": "có tiếng súng vào sáng 30/4", "supported_by": 7}
  ],
  "divergent_claims": [
    {
      "claim": "xe tăng đầu tiên vào Dinh lúc mấy giờ",
      "perspectives": [
        {"role": "participant", "says": "10:45"},
        {"role": "witness", "says": "11:30"},
        {"role": "authority", "says": "11:00"}
      ],
      "note": "Không xác định đúng/sai. Cần đặt trong bối cảnh của mỗi người."
    }
  ]
}
```

---

## Các quyết định thiết kế quan trọng

### Vì sao dùng git thay vì database?
- Miễn phí, phân tán, có audit trail mặc định.
- Cộng đồng có thể mirror/fork toàn bộ archive nếu node chính bị tấn công.
- Merkle-tree của git cung cấp tính toàn vẹn mã hóa.

### Vì sao JSON thay vì binary format?
- Con người đọc được. Một nhà nghiên cứu không cần code để đọc memory.
- Dễ sign/verify bằng nhiều tool.
- Dễ mirror lên IPFS, Arweave, hoặc các archive khác.

### Vì sao không dùng blockchain?
- Chúng tôi không cần consensus trên giá trị tiền tệ — chỉ cần immutability.
  Git + multiple mirrors đạt mục tiêu này rẻ hơn nhiều.
- Blockchain đồng nghĩa với chi phí gas → rào cản cho người ở vùng nghèo.
  Trái với tinh thần phổ cập của dự án.

### Vì sao không có delete?
- Xem nguyên tắc 5 ở `docs/ethics.md`.
- "Quyền được quên" được thực thi qua cờ `consent.withdrawn` (ẩn khỏi giao
  diện công khai), không phải xóa vật lý.

---

## Roadmap

- **v0.1 (hiện tại):** Schema, AI engine skeleton, CLI submit, cross-reference cơ bản.
- **v0.2:** Multi-lingual AI, mobile submission app, IPFS mirror.
- **v0.3:** Timeline verification, geo verification, federation protocol.
- **v1.0:** Cộng đồng có thể tự chạy node riêng, federation hoàn chỉnh.
