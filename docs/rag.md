# RAG cho HumanArchive — thiết kế đặc thù cho ký ức

RAG (Retrieval-Augmented Generation) thông thường sẽ:
1. Chunk document → embed → lưu vector store
2. Query → embed → retrieve top-k gần nhất → đưa Claude tổng hợp

Đủ tốt cho code docs, báo cáo kỹ thuật, Wikipedia. **Không đủ tốt cho ký
ức cá nhân.** HumanArchive có 4 rủi ro đặc thù mà RAG cổ điển không xử lý.

## 4 rủi ro đặc thù

### 1. PII leakage qua embedding

Nếu một memory chứa tên "Nguyễn Văn An" và ta embed nguyên văn, vector
đó đã **mã hoá danh tính**. Người có access vào index (kể cả backup bị
leak) có thể:
- So sánh với vector của query chứa tên → phát hiện match
- Cluster vectors → tìm memory "của cùng người"

**Giải pháp**: PII được scrub **trước khi embed**, không phải sau retrieve.
Xem `core/rag/index.py:build_index` — gọi `find_pii()` + `pseudonymize()`
trước `embedder.embed()`.

### 2. Consent drift

Người A đóng góp hôm nay, index được build. Ngày mai người A bật
`withdrawn=true` vì lý do an toàn. Nhưng vector của họ vẫn trong index,
vẫn được retrieve, vẫn xuất hiện trong câu trả lời của LLM.

**Giải pháp**:
- `is_publicly_viewable()` được gọi khi build index (reject withdrawn/embargoed)
- Index có field `built_at`; CI cảnh báo nếu consent config thay đổi sau build
- `archive/rag_index.json` được check vào git như artifact — mọi thay đổi
  index được audit qua git diff

### 3. Bias amplification qua top-k retrieval

Đây là rủi ro **nguy hiểm nhất** và cũng tinh vi nhất.

Giả sử event "lũ làng A" có:
- 10 memory của **witness** (người ngoài cuộc đi qua đường, cùng dùng
  cụm từ "nước lên nhanh")
- 1 memory của **victim** (mất nhà, dùng ngôn ngữ cảm xúc khác)
- 1 memory của **authority** (người xả đập, dùng ngôn ngữ kỹ thuật)

Query "chuyện gì đã xảy ra ở lũ làng A?" với RAG cổ điển top-5:
- Top 5 semantic matches → **5 witness** (vì cùng ngôn ngữ)
- Victim và authority bị loại khỏi context
- LLM trả lời dựa trên **chỉ witness perspective**

Đây chính là **cái mà HumanArchive tồn tại để chống lại**. Nếu RAG cũng
bias thế thì dự án mất toàn bộ ý nghĩa.

**Giải pháp**: `role_balance=True` (mặc định) trong `search()`:
1. Lấy **top-1 của mỗi role** trước
2. Nếu còn slot (k > số role), fill tiếp bằng top-score còn lại

Kết quả: query "xả đập sớm" trên demo archive trả về authority + victim
+ witness — KHÔNG phải 3 authority.

Test `tests/test_rag.py::TestRoleBalancedRetrieval` chứng minh điều này.

### 4. Identity probe attack

Kẻ xấu có thể query `"kể lại anh Nguyễn Văn An đã làm gì ngày 10/9"` để:
- Xem hệ thống có return memory nào "về anh An"
- Gián tiếp xác nhận anh An có trong archive

**Giải pháp**: `search_text()` scrub PII từ query **trước khi embed**.
Query → `"kể lại <person:A.> đã làm gì ngày 10/9"` → vector không còn
khớp với tên thật. Xem `core/rag/index.py:search_text`.

## Kiến trúc

```
core/rag/
├── embedder.py     # Interface + 3 backend: Hash (zero-dep), Voyage, SentenceTransformer
├── index.py        # build_index (with safety filters) + search (role-balanced)
└── answer.py       # Full pipeline: scrub query → retrieve → Claude → answer + citations
```

## Embedder selection

`get_default_embedder()` tự chọn:

| Thứ tự ưu tiên | Điều kiện | Chất lượng |
|---|---|---|
| 1. **VoyageEmbedder** | `VOYAGE_API_KEY` + `pip install voyageai` | Cao (đa ngôn ngữ, production) |
| 2. **SentenceTransformerEmbedder** | `HUMANARCHIVE_USE_SENTENCE_TRANSFORMERS=1` + `pip install sentence-transformers` | Cao, local, miễn phí |
| 3. **HashEmbedder** | Luôn có | Demo/test only (keyword match, không hiểu ngữ nghĩa) |

Cho production thực: bật **Voyage** (Anthropic's recommended embedding
partner) hoặc **SentenceTransformer** với model `paraphrase-multilingual-MiniLM-L12-v2`
(hỗ trợ tiếng Việt tốt, chạy offline).

## Sử dụng

```bash
# Build index (mỗi khi archive thay đổi hoặc consent config thay đổi)
python tools/rag_query.py --build

# Hỏi
python tools/rag_query.py "tại sao lại xả đập sớm?"

# JSON output cho pipe
python tools/rag_query.py --json "..." | jq '.citations'
```

## Output format

`AnswerWithCitations` luôn bao gồm:

| Field | Ý nghĩa |
|---|---|
| `question_scrubbed` | Câu hỏi sau khi scrub PII |
| `answer` | Tổng hợp từ Claude, cite bằng `[1]`, `[2]`, ... |
| `citations` | List memory_id + role + event_id + score |
| `uncertainty` | low / medium / high |
| `refused` | Nếu Claude vi phạm nguyên tắc 1 hoặc không có hit → giải thích |

**Mọi câu trả lời PHẢI có citation**. Nếu không có hit nào retrieve được,
hệ thống **không bịa** — trả về lời giải thích trung thực rằng chưa có
ký ức phù hợp.

## Khi nào NÊN rebuild index

- Thêm memory mới
- Có memory bật `withdrawn=true` hoặc sửa `embargo_until`
- Thay đổi embedder
- Thay đổi logic scrubber (PII detector)

CI rebuild tự động khi archive thay đổi.
