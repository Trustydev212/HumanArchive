# Use Cases — Bạn có thể làm gì với HumanArchive?

*Tiếng Việt · English follows.*

Sau 10 phiên bản phát triển, đây là tổng hợp **thực tế** ai dùng được
HumanArchive cho việc gì. Tài liệu này không liệt kê features — nó nói
về **người dùng + use case cụ thể**.

---

## 6 nhóm người dùng

### 1. 🎙️ Cá nhân muốn lưu một ký ức

**Bạn là ai:** Người sống qua một sự kiện (lớn hay nhỏ) và muốn ghi
lại — vì người chứng kiến đang già, vì lịch sử chính thức kể khác,
vì muốn con cháu sau này hiểu.

**Bạn làm được gì:**

| Nhu cầu | Tool |
|---|---|
| Submit nặc danh từ trình duyệt | `web/submit.html` (PWA installable) |
| Submit từ terminal | `humanarchive submit` (interactive) |
| Submit khi offline | PWA + draft auto-save trong localStorage |
| Trì hoãn công bố | Set `consent.embargo_until` đến năm tương lai |
| Rút lại sau này | Set `consent.withdrawn = true` (data vẫn trong archive cho audit) |
| Chỉ allow researcher đọc | Set `consent.public = false` |
| Cấm AI phân tích | Set `consent.allow_ai_analysis = false` |

**Use case ví dụ:**
- Bà ngoại bạn sống qua nạn đói 1945 → bạn phỏng vấn, fill form, embargo 50 năm
- Bạn chứng kiến biểu tình → submit nặc danh hôm nay
- Mất người thân trong COVID → ghi lại trải nghiệm với content warning

---

### 2. 🌐 Cộng đồng / Diaspora / NGO

**Bạn là ai:** Nhóm Việt kiều, refugee community, NGO nhân quyền, hoặc
cộng đồng marginalized muốn có archive **chính cộng đồng kiểm soát**,
không phụ thuộc publisher trung tâm.

**Bạn làm được gì:**

| Nhu cầu | Tool |
|---|---|
| Self-host instance | Xem `docs/deploy.md` (GitHub Pages, IPFS, Tor, nginx) |
| Migrate oral history có sẵn | `humanarchive bulk-import data.csv` |
| Set up curator team | `trust/reviewers.json` + ed25519 signing |
| Mirror cho an toàn | `humanarchive export-bundle --sign-key` + IPFS pin |
| Federate với node khác | Bundle protocol (xem `docs/federation.md`) |
| Audit định kỳ | `humanarchive audit --format md > REPORT.md` |

**Use case ví dụ:**
- Tổ chức Việt kiều thu thập lời kể về thuyền nhân 1975-1990: ~200 memories,
  bulk import từ spreadsheet đã thu thập, federate với 3 node ở Mỹ/Pháp/Úc
- Refugee NGO archive lời kể từ Syria, Ukraine, Myanmar: mỗi instance riêng
  cho mỗi vùng, federate occasional khi safe
- Sinh viên Hồng Kông archive memory về 2019 protest: heavy embargo,
  signed bundle, mirror trên IPFS

---

### 3. 📚 Researcher / Nhà sử học / Nhà báo điều tra

**Bạn là ai:** Người tổng hợp lịch sử từ nhiều nguồn, viết paper academic,
hoặc điều tra báo chí cần archive immutable.

**Bạn làm được gì:**

```bash
# Cross-reference đa góc nhìn (role-balanced, không bias amplify)
humanarchive rag "tại sao xả đập sớm?" --json

# Generate historical entry tổng hợp
python -c "
from humanarchive import generate_historical_entry
print(generate_historical_entry('1975-saigon-fall-a3f2'))
"

# Citation format chuẩn cho academic
# memory_id=abc... role=witness archive@<git-tag-v0.7.0>
```

| Nhu cầu | Tool |
|---|---|
| Citable archive với version | git tag mỗi snapshot, BibTeX template trong README |
| Multi-perspective synthesis | `cross_reference()` + role-balanced retrieval |
| Verify integrity của source | `verify_archive()` — sha256 hash check |
| Conflict detection | `humanarchive diff snapshot_a.tar.gz snapshot_b.tar.gz` |
| Export cho phân tích | `archive/graph.json` + `archive/rag_index.json` |
| Obsidian vault cho note-taking | `humanarchive obsidian` → mở trong Obsidian/Foam |

**Use case ví dụ:**
- PhD thesis về di cư VN 1975 → fork archive, cite by memory_id + git tag
- Investigative journalism về scandal kinh tế → archive interview, immutable proof
- Historian paper về một nạn đói địa phương → multi-source cross-reference

---

### 4. 🤖 AI Agents (Claude Desktop, Cursor, custom bots)

**Bạn là ai:** Developer build AI app cần truy cập memory archive, hoặc
agent cần submit/query qua API có structure.

**Bạn làm được gì:**

```bash
# Agent discovery (no docs needed)
humanarchive describe memory     # → JSON Schema
humanarchive capabilities         # → tất cả subcommands có structure

# Submit từ stdin (no interactive prompts)
echo '{"schema_version": "1.0", ...}' | humanarchive submit --from-stdin --dry-run --json

# RAG query với citations
humanarchive rag --json "câu hỏi" | jq '.citations'

# MCP server cho Claude Desktop
# ~/.claude_desktop_config.json:
{
  "mcpServers": {
    "humanarchive": {"command": "humanarchive", "args": ["mcp-server"]}
  }
}
# → 9 tools tự động registered: describe, capabilities, rag_search,
#   submit_dry_run, submit, graph_json, timeline_json, audit_json,
#   verify_signatures_json
```

**Safety**: `submit` tool yêu cầu `confirm=True`. Agent buộc phải
dry-run trước, get explicit user consent, mới được call với confirm.

**Use case ví dụ:**
- Build "memory chatbot" cho cộng đồng: user hỏi câu, bot RAG search +
  trả về với citations
- Custom Claude Desktop workflow: tổng hợp 3 góc nhìn về sự kiện, viết
  draft bài báo
- Discord bot cho cộng đồng: auto-import memory từ chat thread (với
  consent + curator review)

---

### 5. 📖 Educator / Trường học / Bảo tàng

**Bạn là ai:** Giáo viên dạy lịch sử/xã hội học/digital humanities,
hoặc bảo tàng cần dataset multi-perspective có structure.

**Bạn làm được gì:**

| Nhu cầu | Tool |
|---|---|
| Dataset multi-perspective cho lecture | `archive/events/` + `graph.json` |
| Visualize relations giữa events | Mermaid graph (auto-rendered) |
| Timeline cho timeline lecture | `humanarchive timeline` → HTML |
| Perspective prism (1 event, N góc nhìn) | `humanarchive graph prism <event_id>` |
| Học sinh contribute khi đi field trip | `web/submit.html` PWA trên điện thoại |
| Compare divergent claims | `cross_reference` output có `divergent_claims` |
| Content warning automatic | `core/trauma.py` keyword detection + LLM aided |

**Use case ví dụ:**
- Lớp 12 history project: học sinh phỏng vấn ông bà về "Đổi Mới 1986",
  submit qua web form, lớp tổng hợp thành Obsidian vault, present
- Bảo tàng nhân chứng (như USC Shoah Foundation nhưng open-source):
  collect testimonies với consent + embargo, federation với nhiều mirror
- Đại học digital humanities course: students fork repo, contribute
  category to taxonomy, write papers citing memory_id + git tag

---

### 6. 💻 Developer / Open-source contributor

**Bạn là ai:** Developer muốn đóng góp, fork dùng cho dự án khác, hoặc
extend để build feature mới.

**Bạn làm được gì:**

5 paths đóng góp trong `CONTRIBUTING.md`:

- 🎙️ **Memory keeper** — không cần code
- ✍️ **Curator** — review staging, không sửa content
- 📚 **Researcher** — generate historical entries
- 🌐 **Translator** — thêm ngôn ngữ thứ N (đã có vi/en/fr; cần zh/ja/ko/es/ar)
- 🌍 **Node operator** — chạy mirror, federate

Hoặc code:
- Implement embedder mới (OpenAI, local LLM, Cohere)
- Visualization mới (D3 force-directed, geo-map, sankey)
- Export format mới (PDF, EPUB, audiobook script)
- Mobile native app (PWA hiện đã đủ cho 95% case)
- Federation analytics (đo health của network)

CI sẽ catch nếu PR vi phạm 5 nguyên tắc bất biến (xem `tests/test_ethics.py`).

---

## Cái dự án **KHÔNG** dùng được cho — trung thực

| Use case | Lý do | Dùng gì thay |
|---|---|---|
| Real-time chat / social feed | Archive là read-heavy, write-rare | Mastodon, Discord |
| Collaboration đồng thời cùng document | Không có CRDT/sync layer | Notion, Google Docs |
| Enterprise audit compliance với RBAC | Không có admin role (by design) | Confluence, SharePoint |
| Train AI commercial cho judgment grading | License cấm rõ ràng | (không khuyến nghị nói chung) |
| Quick lookup factual data | Wikipedia consensus tốt hơn | Wikipedia, Wikidata |
| Personal todo list | Không phải scope | Todoist, Notion |

---

## 5 use case bạn có thể bắt đầu ngay

1. **"Family archive" cho gia đình bạn**
   - Mỗi thành viên kể 1 ký ức về ông bà / một sự kiện gia đình
   - Bundle private chia sẻ trong nhà (không upload public)
   - Trang web tự host trong LAN

2. **"Project COVID-19 memory"** cho bệnh viện hoặc cộng đồng
   - 10-50 ký ức từ doctor / nurse / patient / family / admin / volunteer
   - Cross-reference: cùng tuần, các góc nhìn khác nhau ra sao?
   - Generate historical entry song ngữ cho website bệnh viện

3. **"Pre-2025 elections oral history"** (bất kỳ quốc gia)
   - political activist / voter / poll worker / observer
   - Embargo đến sau bầu cử
   - Researcher tương lai có data đa góc nhìn

4. **Dự án sử lớp 12 / đại học**
   - Học sinh phỏng vấn ông bà về "Đổi Mới 1986" hoặc giai đoạn khác
   - Mỗi học sinh contribute 1-2 memory
   - Class tổng hợp thành Obsidian vault, present

5. **Migration story collection**
   - Vietnamese diaspora kể về thuyền nhân / 1975 / refugee camp
   - Federate giữa node Mỹ / Pháp / Úc / Canada
   - Sau N năm, dataset trở thành nguồn academic primary

---

## English (summary)

After 10 versions, this is what HumanArchive actually enables:

**6 user groups:**
1. **Individual** — preserve a memory anonymously, with embargo/withdraw control
2. **Community/Diaspora/NGO** — self-host, bulk-import existing oral histories, federate
3. **Researcher/Journalist** — multi-perspective synthesis, immutable citations
4. **AI agents** — CLI/MCP server with safety-rails (`confirm=True` for writes)
5. **Educator/Museum** — multi-perspective datasets with content warnings
6. **Developer** — 5 contribution paths, only 1 needs code

**NOT for:** real-time social feed, collaborative editing, enterprise RBAC,
judgment-grading AI training, factual Q&A.

**5 starter projects:**
1. Family archive
2. COVID-19 hospital memory project
3. Pre-election oral history
4. School history project (Đổi Mới, etc.)
5. Migration / diaspora collection

---

*Nếu use case của bạn không nằm trong list này, mở issue với label
`question` — chúng tôi sẽ tư vấn xem HumanArchive có phù hợp không, và
nếu không thì tool gì khác có thể hợp hơn.*
