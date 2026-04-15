# HumanArchive

> *"Lịch sử không phải là một dòng chảy duy nhất. Nó là một chòm sao của vô số góc nhìn — và chỉ khi ta đọc nó từ nhiều phía, sự thật mới khó bị che giấu."*

**HumanArchive** là một hệ thống lưu trữ ký ức tập thể phi tập trung của nhân loại.
Chúng tôi không đi tìm "một sự thật duy nhất". Chúng tôi xây dựng một môi trường
trong đó **sự thật khó bị che giấu hơn** — thông qua dữ liệu chéo từ nhiều người
đã thực sự sống qua cùng một sự kiện.

---

## Tại sao lại cần HumanArchive?

Lịch sử, cho đến nay, được viết bởi **người chiến thắng**, **người có quyền lực
xuất bản**, hoặc **người có giọng nói to nhất**. Những người còn lại — nạn nhân,
người chứng kiến, người ở ngoài rìa sự kiện, người tham gia nhưng không lên
tiếng — hầu như không để lại dấu vết trong văn bản chính thức.

Hệ quả:
- Các sự kiện lịch sử bị đơn giản hóa thành một narrative duy nhất.
- Các góc khuất bị xóa vĩnh viễn khỏi ký ức tập thể.
- Thế hệ sau không có cách nào tự kiểm chứng.

**HumanArchive lật ngược quy trình này**: bất cứ ai đã sống qua một sự kiện đều
có thể đóng góp ký ức của mình — với tư cách **participant, witness, authority,
organizer, victim, hoặc bystander**. Không có góc nhìn nào quan trọng hơn góc
nhìn khác. AI của chúng tôi sẽ **cross-reference** giữa các ký ức để tìm ra
điểm trùng khớp và mâu thuẫn, rồi trình bày cả hai — không phán xét đúng/sai.

---

## Manifesto — 5 nguyên tắc bất biến

1. **KHÔNG phán xét đúng/sai.** Chúng tôi chỉ phân tích và hiểu. Mọi ký ức đều
   có giá trị, kể cả ký ức của "bên sai" theo cách nhìn đại chúng.

2. **KHÔNG xác định danh tính bất kỳ ai.** Người đóng góp được bảo vệ tuyệt đối.
   Danh tính không bao giờ bị gắn với nội dung ký ức trong dữ liệu công khai.

3. **LUÔN đồng cảm trước khi phân tích.** AI được huấn luyện để hiểu nỗi đau,
   hoàn cảnh, và áp lực trước khi rút ra kết luận.

4. **Động cơ quan trọng hơn hành động.** Một hành động chỉ có ý nghĩa khi ta
   hiểu *tại sao* nó xảy ra — áp lực nào, hoàn cảnh nào, nỗi sợ nào.

5. **Dữ liệu thô không bao giờ được xóa hoặc sửa.** Ký ức là bất biến. Nếu
   người đóng góp muốn rút lại, chỉ có metadata hiển thị bị ẩn — nội dung gốc
   vẫn được giữ trong tầng archive để đảm bảo tính toàn vẹn lịch sử.

Xem chi tiết: [docs/ethics.md](docs/ethics.md)

---

## Cấu trúc dự án

```
humanarchive/
├── README.md                    # File này — vision + manifesto
├── docs/
│   ├── ethics.md                # 5 nguyên tắc bất biến (chi tiết)
│   └── architecture.md          # Thiết kế hệ thống
├── core/
│   ├── schema/
│   │   └── memory.json          # Chuẩn dữ liệu ký ức (JSON Schema)
│   ├── ai_engine.py             # AI phân tích động cơ + cross-reference
│   └── verification/
│       ├── __init__.py
│       └── cross_check.py       # Logic xác thực chéo
├── archive/
│   └── events/                  # Ký ức đã được lưu trữ (theo event_id)
└── tools/
    └── submit.py                # CLI đóng góp ký ức
```

---

## Bắt đầu nhanh

### Đóng góp một ký ức
```bash
python tools/submit.py
```

CLI sẽ hướng dẫn bạn điền từng trường. Không cần tài khoản — bạn chỉ cần một
mã định danh nặc danh do hệ thống sinh ra.

### Phân tích một ký ức
```python
from core.ai_engine import analyze_memory
import json

with open("archive/events/<event_id>/<memory_id>.json") as f:
    memory = json.load(f)

print(analyze_memory(memory))
```

### Cross-reference nhiều ký ức về cùng sự kiện
```python
from core.ai_engine import cross_reference

report = cross_reference(list_of_memories)
print(report)
```

---

## Đóng góp cho dự án

Mọi pull request đều được chào đón, miễn là nó **không vi phạm 5 nguyên tắc
bất biến**. Đặc biệt hoan nghênh:
- Translations của schema & docs sang nhiều ngôn ngữ
- Cải tiến AI engine (đồng cảm, phát hiện động cơ, phát hiện mâu thuẫn)
- Các công cụ thu thập ký ức offline (cho vùng không có internet)
- Các nghiên cứu về bias trong AI phân tích ký ức

---

## Giấy phép

Nội dung ký ức: **CC BY-SA 4.0** — được chia sẻ, sao chép, nhưng không được
dùng để định danh hay làm hại người đóng góp.

Mã nguồn: **MIT License**.

---

*HumanArchive được xây dựng với một niềm tin: rằng nếu đủ nhiều người
nói thật, dù chỉ một mảnh nhỏ, thì tổng hòa của những mảnh đó sẽ khó bị bóp
méo hơn bất kỳ narrative đơn lẻ nào.*
