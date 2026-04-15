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
├── CHANGELOG.md                 # Lịch sử các phiên bản
├── docs/
│   ├── ethics.md                # 5 nguyên tắc bất biến (chi tiết)
│   └── architecture.md          # Thiết kế hệ thống
├── core/
│   ├── schema/memory.json       # JSON Schema v1 — chuẩn dữ liệu ký ức (tags, categories, relations)
│   ├── ai_engine.py             # analyze_memory, cross_reference, generate_historical_entry
│   ├── graph.py                 # Dựng category tree, relation graph, perspective prism
│   ├── llm/
│   │   └── claude_client.py     # Claude API (Anthropic SDK) + prompt caching + fail-safe
│   ├── privacy/
│   │   └── pii_scrubber.py      # Phát hiện & pseudonymize PII (nguyên tắc 2)
│   ├── integrity.py             # Verify memory_id, enforce consent/embargo (nguyên tắc 5)
│   ├── trauma.py                # Phát hiện trauma, sinh content warning (nguyên tắc 3)
│   └── verification/
│       └── cross_check.py       # Atomic claim extraction + comparison
├── taxonomy/
│   └── categories.json          # Cây phân loại chuẩn (war, natural-disaster, pandemic, ...)
├── tests/                       # 50 tests — mỗi nguyên tắc được test
├── archive/
│   ├── events/                  # Ký ức (bất biến, content-addressed, phẳng)
│   ├── GRAPH.md                 # Relation graph (Mermaid) — sinh bởi tool
│   ├── CATEGORY_TREE.md         # Cây phân loại — sinh bởi tool
│   └── TAGS.md                  # Tag cloud — sinh bởi tool
├── tools/
│   ├── submit.py                # CLI đóng góp ký ức nặc danh
│   └── graph_export.py          # Export Mermaid / JSON / tree / prism
├── requirements.txt             # Runtime deps (anthropic, jsonschema)
├── requirements-dev.txt         # + pytest
└── .github/workflows/ci.yml     # CI: schema validation + integrity + tests
```

## 5 nguyên tắc được enforce như thế nào?

Không chỉ là docs. Mỗi nguyên tắc được gắn vào code:

| Nguyên tắc | Cơ chế code |
|---|---|
| 1. Không phán xét | `core/llm/claude_client.py:FORBIDDEN_FIELDS` + `_assert_no_forbidden_fields` — LLM output chứa `verdict`/`guilty`/`is_lying`/... sẽ bị refuse. System prompt (prompt-cached) nhắc LLM mỗi request. |
| 2. Không xác định danh tính | `core/privacy/pii_scrubber.py` chạy TRƯỚC khi gửi lên LLM. `consent.allow_ai_analysis=false` → `analyze_memory` raise `PermissionError`. |
| 3. Đồng cảm trước | `core/trauma.py` phát hiện 9 category trauma, sinh content warning ở đầu entry. Output luôn có field `acknowledgement` trước `analysis`. |
| 4. Động cơ > hành động | Schema required `motivation.your_motivation`. `analyze_memory` raise nếu thiếu. Output LLM có field `motivation_interpretation` riêng. |
| 5. Dữ liệu bất biến | `core/integrity.py:verify_memory_id` kiểm tra `sha256(content)[:16]`. CI fail nếu archive bị tamper. `withdrawn`/`embargo` filter ở `filter_viewable`. |

## Event decomposition — phân loại & dựng view

Folder `archive/events/` **không phân cấp theo loại** (không có `war/`,
`storm/`, `covid/`). Lý do: một sự kiện thường thuộc nhiều taxonomy cùng
lúc; chọn một → mất các hướng nhìn khác. Thay vào đó, mỗi event khai báo
`tags` + `categories` + `relations` trong metadata, và tool dựng view
tuỳ ý:

```bash
python tools/graph_export.py mermaid   > GRAPH.md          # relation graph
python tools/graph_export.py tree      > CATEGORY_TREE.md  # cây phân loại
python tools/graph_export.py prism <event_id> > PRISM.md   # perspective prism
python tools/graph_export.py json      > graph.json        # cho D3/Cytoscape/Obsidian
```

Xem `docs/event_decomposition.md` để hiểu đầy đủ trade-off và các loại
quan hệ (`caused_by`, `part_of`, `led_to`, `contradicts`, ...).

## Obsidian vault & RAG

### Obsidian

Archive → một Obsidian vault có sẵn graph view, backlinks, và Mermaid:

```bash
python tools/obsidian_export.py --output obsidian_vault
# mở obsidian_vault/ trong Obsidian → Ctrl/Cmd+G để xem graph view
```

### RAG tìm kiếm ngữ nghĩa

```bash
python tools/rag_query.py --build              # build index
python tools/rag_query.py "tại sao xả đập?"    # hỏi, nhận answer + citations
```

**RAG của HumanArchive khác RAG thông thường** ở 4 điểm (xem `docs/rag.md`):

1. **PII scrub trước khi embed** — index không mã hoá danh tính
2. **Consent filter ở build_index** — withdrawn/embargoed không bao giờ vào vector store
3. **Role-balanced retrieval** — chống bias, đảm bảo đa góc nhìn luôn được
   trả về (không bị witness đông áp đảo victim ít)
4. **Query scrub** — chặn identity probe attack (`"kể về anh Nguyễn Văn An"`)

Backend embedder pluggable: **Voyage** (Anthropic partner, tốt nhất),
**SentenceTransformer** (local, đa ngôn ngữ), hoặc **HashEmbedder**
(zero-dep fallback).

## Web UI (single-page static, không build)

```bash
# Đảm bảo graph + rag index đã có
python tools/graph_export.py json > archive/graph.json
python tools/rag_query.py --build

# Serve
python -m http.server 8000
# → http://localhost:8000/web/          (browse archive)
# → http://localhost:8000/web/submit.html (form đóng góp)
```

Features: event browser với filter, Mermaid relation graph, category
tree, tag cloud, RAG search **client-side** (JS port của HashEmbedder
khớp Python byte-for-byte). `submit.html` có live PII scan + download
JSON (client-only, không gửi data đi đâu cho đến khi user chủ động).

## Federation — bundle protocol

```bash
python tools/export_bundle.py --output bundle.tar.gz                # export
python tools/import_bundle.py bundle.tar.gz --archive other_archive # import
python tools/export_bundle.py --sign-key my_ed25519.pem ...         # có ký
```

Bundle có `MANIFEST.json` + merkle root + signature tuỳ chọn. Content-addressed
nên dedup tự nhiên. Xem `docs/federation.md` để hiểu merge rules và
kênh trao đổi (GitHub / IPFS / Arweave / email / USB).

## Multi-user workflow

HumanArchive không có "admin" hay "moderator" theo nghĩa truyền thống.
Có 3 pattern cộng tác:

```bash
# 1. Contribution qua staging (review trước khi merge)
python tools/staging.py submit my_memory.json
python tools/staging.py review <memory_id> --type approve --reviewer alice
python tools/staging.py review <memory_id> --type approve --reviewer bob
python tools/staging.py merge <memory_id>

# 2. Annotation post-archive (thêm context, không sửa gốc)
python -c "from core.annotations import create_annotation, save_annotation; \
  a = create_annotation(target_memory_id='...', author_id='ha-xxxx', \
                         type='correction', content='...'); \
  save_annotation(a, 'archive')"

# 3. Audit định kỳ (báo cáo, không gatekeep)
python tools/audit.py --archive archive --format md > AUDIT.md
```

Xem `docs/workflows.md` để hiểu đầy đủ 5 personas, web-of-trust model,
và pattern moderation-without-deletion.

## LLM-aided detectors (tuỳ chọn)

- `core.privacy.llm_pii.llm_scan_pii()` — bổ sung regex, bắt tên viết
  rời, chức danh duy nhất, địa chỉ cụ thể. Fallback [] nếu không có API.
- `core.trauma_llm.llm_classify_trauma()` — phân loại trauma nuanced,
  chống false positive keyword. Fallback về keyword detector nếu không
  có API.

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
