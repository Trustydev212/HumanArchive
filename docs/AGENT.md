# HumanArchive — AI Agent Integration Guide

*Tiếng Việt · English below.*

Cho các AI agent (Claude Code, Cursor, Devin, OpenInterpreter, custom
agents, ...) dùng HumanArchive qua CLI mà **không cần tương tác**.

Câu hỏi đầu tiên của agent:

```bash
humanarchive capabilities | jq .
humanarchive describe memory | jq .schema.required
humanarchive describe annotation | jq .schema.required
```

## Tại sao CLI thay vì MCP server?

- Cài 1 lệnh: `pip install -e .`
- Không cần daemon / WebSocket / server config
- Hoạt động trong mọi agent env có shell (Bash tool)
- JSON output chuẩn
- Exit code ổn định → agent biết thành công/thất bại

## 3 operation chính

### 1. Đọc archive

```bash
humanarchive graph json                  # full graph metadata
humanarchive timeline --json             # chronological
humanarchive audit --format json         # quality signals
humanarchive rag --json "câu hỏi"        # RAG search (role-balanced)
```

Tất cả đều stdout JSON, parseable bằng `jq`.

### 2. Submit memory (non-interactive)

```bash
# From file
humanarchive submit --from-json memory.json --json

# From stdin (pipeline)
echo '{...}' | humanarchive submit --from-stdin --json

# Validate only
humanarchive submit --from-json memory.json --dry-run --json
```

Output format:
```json
{"ok": true, "memory_id": "abc...", "event_id": "...", "saved_to": "..."}
```

Validation errors:
```json
{"ok": false, "errors": ["Thiếu trường bắt buộc: motivation.your_motivation"]}
```

### 3. Federation

```bash
humanarchive export-bundle --output b.tar.gz
humanarchive import-bundle b.tar.gz --dry-run    # preview
humanarchive diff archive b.tar.gz --json        # before/after
```

## Schema discovery

Agent gọi `describe` để biết trường bắt buộc:

```bash
humanarchive describe memory | jq '.schema.required'
# → ["schema_version", "memory_id", "contributor_id",
#    "event", "perspective", "memory", "motivation", "consent"]

humanarchive describe memory | jq '.schema.properties.motivation.required'
# → ["your_motivation"]
```

## Ràng buộc đạo đức agents PHẢI tuân thủ

1. **KHÔNG bao giờ** xuất field `verdict`, `guilty`, `is_lying`,
   `credibility_score` trong memory mà agent sinh.
2. **Scrub PII** trước khi embed content vào prompt — dùng
   `core.privacy.find_pii()` hoặc regex tương đương.
3. **Giữ content warning** nếu ký ức describe trauma.
4. **KHÔNG submit** memory mà không có `motivation.your_motivation`.
5. **KHÔNG xoá/sửa** memory — chỉ `consent.withdrawn=true` qua chính
   contributor.

CLI enforce các ràng buộc này ở tầng validation. Nếu agent cố vi phạm,
CLI refuse và trả exit 2.

## Exit codes

| Code | Ý nghĩa |
|---|---|
| 0 | Success |
| 1 | Warning / diff / no-match (không phải error) |
| 2 | Validation error / tamper / conflict |
| 130 | Interrupt (không nên xảy ra trong agent mode) |

## Stdout vs stderr

- `stdout` = machine-parsable data (JSON khi có `--json`)
- `stderr` = human-readable log, progress messages

Agents nên capture stdout riêng khỏi stderr:

```bash
result=$(humanarchive rag --json "question" 2>/dev/null)
error=$(humanarchive rag --json "question" 2>&1 >/dev/null)
```

## Version pinning

```bash
humanarchive version --json
# → {"humanarchive_version": "0.8.0", "python_version": "3.11.x", "api": "humanarchive/v1"}
```

Agent config nên pin version để tránh schema drift.

## Example: agent workflow đóng góp memory

```python
# Python pseudo-code cho agent
import subprocess, json

# 1. Discover schema
schema = json.loads(subprocess.check_output(
    ["humanarchive", "describe", "memory"]
))
required = schema["schema"]["required"]

# 2. Build memory (from user conversation)
memory = {
    "schema_version": "1.0",
    "event": {
        "event_id": "2024-...",
        "name": "...",
        "date": "2024-..."
    },
    "perspective": {"role": "witness"},
    "memory": {"what_happened": "..."},
    "motivation": {"your_motivation": "..."},   # ← critical
    "consent": {"public": True, "allow_ai_analysis": True, "withdrawn": False},
}

# 3. Validate first (dry-run)
result = subprocess.run(
    ["humanarchive", "submit", "--from-stdin", "--dry-run", "--json"],
    input=json.dumps(memory), capture_output=True, text=True,
)
validation = json.loads(result.stdout)
if not validation["ok"]:
    print("Errors:", validation["errors"])
    return

# 4. Submit for real
result = subprocess.run(
    ["humanarchive", "submit", "--from-stdin", "--json"],
    input=json.dumps(memory), capture_output=True, text=True,
)
saved = json.loads(result.stdout)
print(f"Saved {saved['memory_id']}")
```

## Example: MCP server wrapper (nếu cần)

Nếu bạn *cần* expose CLI qua MCP protocol, wrapper ~30 dòng:

```python
# mcp_wrapper.py — minimal MCP server wrapping humanarchive CLI
import subprocess, json
from mcp.server import Server

srv = Server("humanarchive")

@srv.tool()
def ha_describe(type_name: str) -> dict:
    r = subprocess.check_output(["humanarchive", "describe", type_name])
    return json.loads(r)

@srv.tool()
def ha_submit(memory: dict, dry_run: bool = True) -> dict:
    args = ["humanarchive", "submit", "--from-stdin", "--json"]
    if dry_run:
        args.append("--dry-run")
    r = subprocess.run(args, input=json.dumps(memory),
                       capture_output=True, text=True)
    return json.loads(r.stdout)

# ...
```

Nhưng nếu agent của bạn đã có Bash tool, **không cần MCP wrapper** —
gọi CLI trực tiếp đơn giản hơn.

---

## English

### Agent discovery

```bash
humanarchive capabilities          # full CLI surface as JSON
humanarchive describe memory       # memory schema
humanarchive describe annotation   # annotation schema
humanarchive for-agent             # this guide as text
```

### Non-interactive submission

```bash
humanarchive submit --from-json file.json --json
echo '{...}' | humanarchive submit --from-stdin --json
```

### Reading

```bash
humanarchive graph json
humanarchive timeline --json
humanarchive audit --format json
humanarchive rag --json "question"
```

### Ethical constraints the agent MUST respect

1. No verdict/guilty/is_lying fields
2. PII scrub before prompt embedding
3. Preserve trauma content warnings
4. motivation.your_motivation is required
5. No delete/edit — only contributor can set withdrawn=true

### Exit codes: 0 success, 1 warning, 2 error, 130 interrupt

### stdout = JSON data, stderr = human messages
