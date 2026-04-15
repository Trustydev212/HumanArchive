# FAQ — Frequently Asked (and Skeptical) Questions

*Tiếng Việt · English after each answer.*

### "Đây là Wikipedia phải không?" / "Isn't this just Wikipedia?"

Không. Wikipedia hướng tới **một phiên bản sự thật được đồng thuận** —
NPOV (neutral point of view) là mục tiêu. HumanArchive làm ngược lại:
chúng tôi giữ **nhiều phiên bản sự thật** mà không cố gắng hoà giải.
Mỗi memory có vai trò riêng (witness / victim / authority / ...) và
tất cả cùng tồn tại.

*Wikipedia wants one consensual truth. We keep many truths in parallel
and let the reader draw their own conclusions from the constellation.*

---

### "Chẳng phải điều này nguy hiểm — có thể dùng làm tuyên truyền?" / "Isn't this dangerous — could be used for propaganda?"

Mọi archive đều có thể bị lạm dụng. HumanArchive có 3 phòng vệ:

1. **Đa góc nhìn bắt buộc** — một event có 1 lời kể → audit flag "chỉ
   1 role"; kêu gọi role khác đóng góp.
2. **Bất biến + content-addressed** — không ai (kể cả publisher gốc)
   có thể âm thầm sửa lời kể để bóp méo lịch sử.
3. **Không xoá** — propaganda phản bác lời kể vẫn tồn tại song song.

*Propaganda works by erasing alternatives. Our design physically
prevents that.*

---

### "Làm sao biết ký ức là thật?" / "How do you verify memory authenticity?"

Không. Và đó là **tính năng, không phải lỗi**.

Một nhà nhân chứng học sẽ nói với bạn: ký ức con người là không đáng
tin theo nghĩa một camera. Nhưng một lời kể không chính xác 100% không
có nghĩa là giả. Nó có nghĩa là **con người kể chuyện theo cách con
người**.

HumanArchive không là filter, là bộ sưu tập. AI cross-reference
tìm điểm trùng và điểm khác — **không phán xét ai đúng**. Người đọc tự
làm nhà sử học.

*Human memory isn't a camera. We collect it, cross-reference it, show
convergence and divergence — never rule on who's "correct".*

---

### "Tại sao không dùng blockchain?" / "Why not blockchain?"

- **Chi phí**: blockchain = gas fees, rào cản cho người vùng nghèo →
  chỉ người giàu lưu được ký ức của mình. Trái với tinh thần phổ cập.
- **Privacy**: blockchain public + immutable vĩnh viễn → withdrawn
  không thể enforce ở tầng UI.
- **Đủ dùng**: Git + merkle root + federation + ed25519 signature đạt
  99% của cái blockchain cho, không tốn gas.

Nếu thực sự cần vĩnh viễn + mạng phân tán thật, Arweave (one-time
payment) phù hợp hơn, và bundle protocol của ta tương thích.

*We get 99% of blockchain's guarantees via Git + merkle + ed25519
without the gas fees that would exclude poor contributors.*

---

### "Có bị lợi dụng để train AI không?" / "Can this be scraped for AI training?"

`LICENSE-CONTENT` cấm **rõ ràng**: "must not use to train models whose
outputs are used to pass judgment on individuals". Vi phạm terminate
license.

Về mặt kỹ thuật: không có cách chặn scrape triệt để (archive là
public). Nhưng:
- Contributor biết rõ từ đầu rằng nội dung là CC-BY-SA
- Consent.embargo_until cho phép delay nhạy cảm
- Nội dung được PII-scrub trước khi công khai

*The license forbids judgment-grading uses. Technical blocking is
impossible with public archives, but the terms are explicit and
terminable.*

---

### "Ai review curator?" / "Who watches the curators?"

Không ai *cao hơn* curator. Web-of-trust: cộng đồng vouch curator qua
`trust/reviewers.json`. Curator sai sẽ bị community un-vouch (không
xoá signature cũ — preserve record) và bị remove khỏi list.

Không có single admin. Đây là giới hạn thiết kế có chủ ý — không có
central authority để corrupt.

*No single admin. Community vouches and un-vouches. A corrupted curator
is de-listed but their past actions remain in record (principle 5).*

---

### "AI Claude có bias không?" / "Isn't Claude biased?"

Có — mọi LLM đều có bias. HumanArchive thiết kế để **minimize Claude's
influence on the output**:

- System prompt đóng khung 5 nguyên tắc + cấm trường phán xét
- Output JSON được validate: chứa `verdict`/`guilty` → refuse
- Role-balanced retrieval → Claude không bao giờ thấy chỉ 1 perspective
- Raw memories không đổi dù AI analysis thay đổi

Nếu bạn tin rằng bias là không tránh khỏi: đúng. Giải pháp của ta là
**minh bạch** — Claude bias nào cũng visible vì raw data bên cạnh.

*Every LLM is biased. Our structural controls (forbidden fields,
role balance, raw data preservation) don't eliminate bias — they make
it inspectable.*

---

### "Tại sao không CCC/Anthropic/OpenAI build cái này?" / "Why isn't this built by a big lab?"

Vì nó **mâu thuẫn với business model** của họ:
- Không aggregate data để train
- Không produce "đáp án đúng"
- Không tối đa hoá engagement

HumanArchive chỉ có ý nghĩa nếu operate **phi lợi nhuận, phi tập trung**.
Big lab làm cái này sẽ phá thiết kế.

*No big lab will build this because its design conflicts with extractive
data economics. It only works as a commons.*

---

### "Dự án này có sống được lâu không?" / "Will this last?"

Tôi không biết. Nhưng:
- Content-addressed → archive vẫn dùng được kể cả khi repo chết
- Bundle protocol → có thể mirror lên nhiều nơi
- Schema v1.0 → độc lập với code version
- MIT + CC-BY-SA → không bị vendor-lock

Nếu dự án chết, archive vẫn là một artifact historical có giá trị.
Đó là requirement tối thiểu.

*I don't know. But the archive outlives the code — by design.*

---

### "Đóng góp được không nếu tôi không biết code?" / "Can I contribute without coding?"

**Có, và quan trọng hơn người biết code.** Đọc `CONTRIBUTING.md`:
- 🎙️ Contributor (kể ký ức)
- ✍️ Curator (review, không code)
- 📚 Researcher (tổng hợp, không code)
- 🌐 Translator (dịch)
- 🌍 Node operator (chạy mirror)

Code chỉ là infrastructure. Nội dung con người là dự án.

*Yes — and more important than coders. See CONTRIBUTING.md for five
non-code paths.*

---

### "Tôi sợ khai ký ức ra thì bị trả đũa." / "I'm afraid sharing my memory will get me retaliated against."

Đây là lo ngại hợp lý, và dự án được thiết kế xung quanh nỗi sợ đó:

1. **Nặc danh tuyệt đối** — `contributor_id` là ngẫu nhiên, không
   liên kết với thiết bị hay identity.
2. **Không collect metadata** — không IP log, không browser fingerprint,
   không timestamp chính xác (bạn tự chọn date).
3. **Embargo** — bạn có thể đặt `embargo_until` đến sau khi bạn qua
   đời, hoặc đến khi chế độ thay đổi.
4. **Rút lại** — bạn có thể bật `withdrawn=true` bất cứ lúc nào;
   memory ẩn khỏi UI (vẫn trong archive cho historical record).
5. **Federation** — một node có thể bị ép xoá nhưng các node khác
   vẫn mirror.

Nhưng: **không có hệ thống nào 100% an toàn**. Nếu lời kể có chi tiết
đủ đặc trưng để nhận ra bạn, cơ chế chống doxx sẽ không đủ. Hãy đọc
kỹ memory trước khi submit và tự scrub thêm nếu cần.

*Anonymity is structural, but content itself can identify. Read your
own submission carefully and scrub context clues before submitting.*
