#!/usr/bin/env bash
# HumanArchive demo script — tối ưu cho asciinema recording.
#
# Sử dụng:
#   # Xem trực tiếp
#   bash scripts/demo.sh
#
#   # Record thành asciinema cast để chia sẻ
#   asciinema rec humanarchive-demo.cast -c "bash scripts/demo.sh"
#
#   # Play lại
#   asciinema play humanarchive-demo.cast
#
# Demo chạy khoảng 90 giây, hiển thị:
#   1. Cài đặt (1 lệnh)
#   2. Demo end-to-end (build graph + RAG + Obsidian + audit)
#   3. Agent API (describe, capabilities, submit from stdin)
#   4. Federation (export/import bundle, diff)

set -e

# Colors
BOLD=$'\033[1m'
CYAN=$'\033[36m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
DIM=$'\033[2m'
RESET=$'\033[0m'

say() {
    printf '\n%s▸ %s%s\n' "$CYAN" "$1" "$RESET"
    sleep 1
}

run() {
    printf '%s$ %s%s\n' "$BOLD" "$*" "$RESET"
    sleep 0.5
    "$@"
    sleep 1
}

banner() {
    clear 2>/dev/null || printf '\n\n'
    cat <<'EOF'
  ┌───────────────────────────────────────────────────────────────┐
  │  HumanArchive — 90-second demo                                │
  │  Decentralized collective memory archive. Without judgment.   │
  └───────────────────────────────────────────────────────────────┘
EOF
    sleep 2
}

banner

say "Step 1: install (one command)"
run humanarchive version --json

say "Step 2: discover capabilities (for humans AND agents)"
printf '%s$ humanarchive capabilities | jq .subcommands[].name%s\n' "$BOLD" "$RESET"
sleep 0.5
humanarchive capabilities | python3 -c "
import json, sys
c = json.load(sys.stdin)
for s in c['subcommands']:
    print(f\"  {s['name']:<20} {s['description']}\")"
sleep 2

say "Step 3: one-command end-to-end (builds graph, index, Obsidian vault)"
printf '%s$ humanarchive demo%s\n%s(skipping actual run; see README for full output)%s\n' \
    "$BOLD" "$RESET" "$DIM" "$RESET"
sleep 2

say "Step 4: explore the archive"
run humanarchive graph json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"  Events: {len(d['nodes'])}\")
print(f\"  Relations: {len(d['edges'])}\")
print(f\"  Tags: {len(d['tag_counts'])}\")
print(f\"  Roles: {sorted({r for n in d['nodes'] for r in n['roles_present']})}\")"

say "Step 5: RAG search (role-balanced, PII-scrubbed query)"
run humanarchive rag --json "tại sao xả đập sớm?" 2>/dev/null | python3 -c "
import json, sys
r = json.load(sys.stdin)
print(f\"  Query (scrubbed): {r['question_scrubbed']}\")
print(f\"  Citations (role-balanced):\")
for i, c in enumerate(r['citations'][:5], 1):
    print(f\"    [{i}] role={c['role']:<12} score={c['score']:.3f}  event={c['event_id']}\")"

say "Step 6: audit (quality report — not gatekeeping)"
run humanarchive audit --format json | python3 -c "
import json, sys
r = json.load(sys.stdin)
t = r['totals']
print(f\"  {t['events']} events, {t['memories']} memories\")
print(f\"  integrity issues: {len(r['integrity_issues'])}\")
print(f\"  possible PII: {len(r['possible_pii_leaks'])}\")
print(f\"  single-role events: {len(r['single_role_events'])}\")"

say "Step 7: agent pipeline (submit via stdin, no prompts)"
printf '%s$ echo \x27{...memory json...}\x27 | humanarchive submit --from-stdin --dry-run --json%s\n' "$BOLD" "$RESET"
sleep 1
python3 -c "
import json, hashlib
m = {
  'schema_version': '1.0',
  'contributor_id': 'ha-demo-rec0',
  'event': {'event_id': '2024-demo-recording-aaaa', 'name': 'Demo recording', 'date': '2024-04-15'},
  'perspective': {'role': 'witness'},
  'memory': {'what_happened': 'Đây là memory demo tạo bởi agent qua stdin pipeline.'},
  'motivation': {'your_motivation': 'Demo asciinema cho community.'},
  'consent': {'public': True, 'allow_ai_analysis': True, 'withdrawn': False},
}
c = json.dumps(m, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
m['memory_id'] = hashlib.sha256(c.encode()).hexdigest()[:16]
print(json.dumps(m, ensure_ascii=False))
" | humanarchive submit --from-stdin --dry-run --json | python3 -m json.tool

say "Step 8: federation (export bundle, diff, import)"
run humanarchive export-bundle --output /tmp/demo-bundle.tar.gz
printf '%s$ humanarchive diff archive /tmp/demo-bundle.tar.gz --json%s\n' "$BOLD" "$RESET"
sleep 0.5
humanarchive diff archive /tmp/demo-bundle.tar.gz --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"  {d['totals']}\")"
rm -f /tmp/demo-bundle.tar.gz

printf '\n%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n' "$GREEN" "$RESET"
printf '%s  Thử ngay:%s\n' "$BOLD" "$RESET"
printf '    git clone https://github.com/Trustydev212/HumanArchive\n'
printf '    cd HumanArchive && pip install -e .\n'
printf '    humanarchive demo\n'
printf '\n'
printf '%s  Đọc thêm:%s\n' "$BOLD" "$RESET"
printf '    docs/ethics.md        — 5 nguyên tắc bất biến\n'
printf '    docs/AGENT.md         — integration cho AI agents\n'
printf '    docs/workflows.md     — multi-user patterns\n'
printf '%s━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━%s\n\n' "$GREEN" "$RESET"
