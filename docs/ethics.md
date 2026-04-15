# Ethics — 5 nguyên tắc bất biến

Tài liệu này định nghĩa những nguyên tắc đạo đức **không thể thương lượng** của
HumanArchive. Bất kỳ thay đổi nào trong code, AI model, hoặc quy trình vận hành
đều phải tuân thủ 5 nguyên tắc dưới đây. Nếu một pull request vi phạm, nó sẽ
bị từ chối — bất kể giá trị kỹ thuật.

---

## 1. KHÔNG phán xét đúng/sai

**Điều này nghĩa là gì:**
- AI của HumanArchive không được kết luận ai "đúng", ai "sai".
- Không gán nhãn "thủ phạm" / "nạn nhân" dựa trên nội dung ký ức.
- Không xếp hạng độ tin cậy của các góc nhìn dựa trên vị trí xã hội của người kể.

**Tại sao:**
Lịch sử đầy rẫy những trường hợp trong đó "kẻ sai" hôm nay là "người đúng"
ngày mai, và ngược lại. Việc gán phán xét từ hiện tại lên ký ức quá khứ là
một hình thức **bạo lực nhận thức** đối với người trong cuộc.

**Cách AI phải hành xử:**
- Thay vì nói "Người A nói dối", hãy nói "Lời kể của Người A mâu thuẫn với
  Người B ở điểm X và trùng với Người C ở điểm Y".
- Luôn trình bày cả hai phía với cùng độ cẩn trọng ngôn từ.

---

## 2. KHÔNG xác định danh tính bất kỳ ai

**Điều này nghĩa là gì:**
- Người đóng góp không bị yêu cầu cung cấp họ tên, CCCD, địa chỉ thật, hoặc
  bất kỳ PII nào.
- Hệ thống tạo ra một **contributor_id** ngẫu nhiên (ví dụ: `ha-7fx2-k9n4`)
  không thể truy ngược về con người.
- Trong nội dung ký ức, nếu người kể nêu tên người khác, AI sẽ hỏi xác nhận và
  đề xuất **pseudonymize** (ví dụ: "anh T." thay vì "anh Tuấn").

**Tại sao:**
Nhiều người sống dưới chế độ mà việc kể sự thật có thể dẫn đến trả đũa —
mất việc, tù đày, bạo lực gia đình, hoặc tệ hơn. Nếu HumanArchive không bảo
vệ được danh tính, nó sẽ trở thành công cụ đàn áp chứ không phải giải phóng.

**Ngoại lệ duy nhất:**
Người đóng góp có thể **chủ động** khai báo danh tính nếu họ là public figure
và muốn chịu trách nhiệm với lời kể của mình. Nhưng đây phải là quyết định
có-ý-thức, với cảnh báo đầy đủ về hậu quả.

---

## 3. LUÔN đồng cảm trước khi phân tích

**Điều này nghĩa là gì:**
- Trước khi AI đưa ra bất kỳ phân tích logic nào, nó phải nhận diện và ghi
  nhận **trạng thái cảm xúc** của người kể.
- Nếu một ký ức chứa trauma, AI phải cảnh báo người đọc ("Nội dung dưới đây
  mô tả trải nghiệm đau thương") trước khi phân tích.
- Không bao giờ phản hồi theo kiểu "Lời kể của bạn có nhiều lỗi logic" —
  thay vào đó: "Tôi hiểu đây là một trải nghiệm khó. Có vài điểm tôi muốn
  hỏi thêm để đảm bảo ghi chép đúng ý bạn."

**Tại sao:**
Ký ức không phải là dữ liệu thô. Nó là một phần con người. Xử lý ký ức mà
không đồng cảm sẽ làm người kể tổn thương lần hai, và khiến họ không bao giờ
đóng góp nữa.

---

## 4. Động cơ quan trọng hơn hành động

**Điều này nghĩa là gì:**
- Mỗi ký ức bắt buộc phải có trường `motivation.your_motivation` và
  `motivation.external_pressure`.
- AI engine dành riêng một bước phân tích động cơ (`analyze_memory`) trước
  khi cross-reference với các ký ức khác.
- Khi tạo entry lịch sử (`generate_historical_entry`), động cơ luôn được
  trình bày trước hoặc song song với hành động.

**Tại sao:**
Một người lính có thể bắn — nhưng vì sao? Áp lực từ cấp trên? Nỗi sợ chết?
Tin rằng mình đang bảo vệ người thân? Cùng một hành động, các động cơ khác
nhau tạo ra các ý nghĩa lịch sử hoàn toàn khác nhau. Bỏ qua động cơ là
phá hủy khả năng học hỏi từ quá khứ.

---

## 5. Dữ liệu thô không bao giờ được xóa hoặc sửa

**Điều này nghĩa là gì:**
- Sau khi một ký ức được commit vào `archive/events/`, nội dung **không thể
  thay đổi**. Mọi thay đổi được thực hiện qua một bản ghi bổ sung (amendment),
  để lịch sử chỉnh sửa luôn được truy vết.
- Nếu người đóng góp muốn **rút lại** ký ức, chỉ có cờ `consent.withdrawn`
  được bật. Nội dung gốc vẫn nằm trong archive nhưng không được hiển thị
  công khai.
- Lệnh `git rebase`, `git push --force` vào lịch sử archive **bị cấm tuyệt đối**
  ở tầng infrastructure. CI sẽ reject mọi force-push lên `archive/`.

**Tại sao:**
Nếu dữ liệu có thể bị xóa hoặc sửa âm thầm, HumanArchive sẽ không còn là
archive — nó sẽ là một Wikipedia có thể bị chỉnh sửa bởi bên thắng cuộc.
**Tính bất biến là xương sống của tin cậy.**

---

## Cơ chế thực thi

Cả 5 nguyên tắc này được enforce ở nhiều tầng:

| Tầng | Cơ chế |
|------|--------|
| **Schema** | `core/schema/memory.json` validate cấu trúc — thiếu `motivation` là bị từ chối. |
| **AI Engine** | Các hàm trong `core/ai_engine.py` được thiết kế để tuân thủ nguyên tắc 1, 3, 4. |
| **Verification** | `core/verification/` không bao giờ ra phán quyết "sai/đúng" — chỉ ra "trùng/mâu thuẫn". |
| **Git infrastructure** | Archive branch được bảo vệ khỏi force-push và history rewrite. |
| **Community review** | Mọi PR thay đổi AI engine hoặc schema cần ít nhất 3 reviewer từ các vùng văn hóa khác nhau. |

---

*Nếu bạn đồng ý với 5 nguyên tắc này, bạn được chào đón đóng góp.
Nếu không, dự án này không dành cho bạn — và điều đó cũng không sao.*
