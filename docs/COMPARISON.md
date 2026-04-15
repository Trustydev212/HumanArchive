# HumanArchive vs. các hệ thống tương tự

Không phải để khoe hơn — để **hiểu rõ** khi nào nên dùng cái nào.

| Hệ thống | Mục tiêu | Sở trường | HumanArchive khác ở đâu |
|---|---|---|---|
| **Wikipedia** | Một phiên bản sự thật được đồng thuận | Depth, citation, chuẩn NPOV | Ta giữ nhiều phiên bản sự thật, không cố hoà giải |
| **Archive.org** | Lưu mọi nội dung web | Scale, vĩnh viễn, thời gian | Ta chuyên về ký ức cá nhân có cấu trúc (motivation, role, consent) |
| **Obsidian** | Personal knowledge base | Graph, backlink, local-first | Ta là collective + immutable + consent layer; xuất ra Obsidian vault được |
| **Mastodon** | Decentralized social | Federation, instance autonomy | Ta là archive (immutable) không phải social feed (ephemeral) |
| **Git** | Version control | Content-addressed, signed, federated | Ta dùng mô hình tương tự nhưng cho ký ức, có consent/embargo/withdraw |
| **StoryCorps** | Oral history interviews | Audio quality, curation chuyên nghiệp | Ta open-source, self-hostable, machine-readable schema, đa góc nhìn |
| **1947 Partition Archive** | Ký ức về partition Ấn Độ-Pakistan | Tập trung vào một sự kiện, curation tốt | Generic framework, bất cứ sự kiện nào; built-in AI cross-reference |
| **Shoah Foundation** | Nhân chứng Holocaust | Video, verification nghiêm ngặt | Ta không gate-keep credibility; nặc danh mặc định |
| **Notion / Obsidian-sync** | Team wiki | Collaboration, search | Ta có ethical guardrails, không có admin quyền xoá |
| **IPFS / Arweave** | Decentralized storage | Permanence | Ta xây lớp semantic/ethical TRÊN storage — IPFS/Arweave là backing option |

## So sánh chi tiết theo chiều

### Immutability

| | Ghi đè file? | Sửa trong UI? | Rollback sau N ngày? |
|---|---|---|---|
| Wikipedia | Không (có history) | Có | Có |
| Obsidian | Có | Có | Có (Git plugin) |
| HumanArchive | **Không bao giờ** | Không | Không |
| Archive.org | Không | Không | Không |
| Git | Qua force-push | - | Có |

### Multi-perspective

| | Nhiều POV về cùng event? | Cách hiển thị |
|---|---|---|
| Wikipedia | Hoà giải thành 1 narrative | "Controversy section" nếu bất đồng lớn |
| Archive.org | Ngẫu nhiên (không structure) | — |
| HumanArchive | **Bắt buộc structured** — role enum (6 values) | Perspective prism + cross-reference + điểm trùng/khác |

### Privacy by design

| | Required identity? | Anonymous default? | Rút sau đồng ý? |
|---|---|---|---|
| Facebook | Có (real name) | Không | Xoá toàn bộ |
| Wikipedia | Username có thể fake | Có option | Không (history giữ) |
| StoryCorps | Có (release form) | Không | Không |
| HumanArchive | **Không bao giờ** | **Default** | Có (`withdrawn=true`, giữ history) |

### Open-source / self-hostable

| | OSS code? | Self-host dễ? | Federation? |
|---|---|---|---|
| Wikipedia | Có (MediaWiki) | Khó | Không |
| Obsidian | Không | App-local | Không (vault sync qua 3rd party) |
| Mastodon | Có | Trung bình | Có (ActivityPub) |
| HumanArchive | **Có (MIT + CC-BY-SA)** | **1 lệnh (`humanarchive demo`)** | **Có (bundle protocol)** |

## Khi nào KHÔNG dùng HumanArchive

Trung thực:

- **Bạn cần nhanh, low-latency, real-time**: ta là archive (đọc nhiều, ghi ít), không phải social feed.
- **Bạn cần collaboration đồng thời trên cùng document**: Notion/Google Docs phù hợp hơn.
- **Bạn cần approval workflow doanh nghiệp** (audit compliance, RBAC phức tạp): không phải mục tiêu của ta.
- **Bạn cần aggregate data để train AI** commercial: CC-BY-SA + ethical terms loại trừ use case này.
- **Memory chỉ dành cho nội bộ 1 tổ chức**: self-hostable nhưng bạn sẽ không tận dụng federation.

## Khi nào ĐÚNG dùng HumanArchive

- Lưu trữ **nhân chứng** về một sự kiện lịch sử (không phân biệt lớn/nhỏ)
- Dự án **digital humanities** cần machine-readable memories với multi-perspective
- Nhóm **nhà báo điều tra** muốn archive source interview có immutability guarantee
- **Cộng đồng diaspora** muốn lưu ký ức của thế hệ cũ trước khi họ mất
- **Nhà hoạt động xã hội** cần archive mà không ai có thể ép xoá
- **Giáo viên sử học** muốn dataset đa góc nhìn cho học sinh
