#!/usr/bin/env python3
"""HumanArchive — CLI đóng góp ký ức.

Sử dụng:
    python tools/submit.py                    # Tương tác
    python tools/submit.py --from file.json   # Submit từ file

Công cụ này:
    * Hỏi từng trường một cách thân thiện, đồng cảm.
    * KHÔNG hỏi danh tính thật. Sinh contributor_id nặc danh.
    * Validate memory theo core/schema/memory.json trước khi ghi.
    * Lưu vào archive/events/<event_id>/<memory_id>.json.
    * In ra hướng dẫn git add/commit để người dùng tự quyết định có push không.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "core" / "schema" / "memory.json"
ARCHIVE_ROOT = REPO_ROOT / "archive" / "events"

EMPATHY_WELCOME = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HumanArchive — Đóng góp một mảnh ký ức

 Cảm ơn bạn đã quyết định chia sẻ. Bạn không cần cho
 chúng tôi biết bạn là ai. Không có câu trả lời "đúng"
 hay "sai" — chỉ có sự thật bạn đã sống qua.

 Bạn có thể dừng bất cứ lúc nào (Ctrl+C). Dữ liệu chỉ
 được lưu khi bạn xác nhận ở bước cuối.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

ROLE_DESCRIPTIONS = {
    "participant": "Người trực tiếp tham gia vào sự kiện.",
    "witness":     "Người chứng kiến trực tiếp, không tham gia.",
    "authority":   "Người ở vị trí có quyền ra quyết định liên quan.",
    "organizer":   "Người tổ chức hoặc lên kế hoạch cho sự kiện.",
    "victim":      "Người bị ảnh hưởng/tổn thương bởi sự kiện.",
    "bystander":   "Người ở gần nhưng không trực tiếp liên quan.",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def ask(prompt: str, *, required: bool = True, multiline: bool = False, default: str | None = None) -> str:
    """Hỏi người dùng một câu. Trả về string đã trim."""
    suffix = f" [{default}]" if default else ""
    while True:
        if multiline:
            print(f"{prompt}{suffix}")
            print("(Nhập nhiều dòng. Kết thúc bằng dòng chỉ có '.' hoặc Ctrl+D.)")
            lines: list[str] = []
            try:
                while True:
                    line = input()
                    if line.strip() == ".":
                        break
                    lines.append(line)
            except EOFError:
                pass
            value = "\n".join(lines).strip()
        else:
            value = input(f"{prompt}{suffix}: ").strip()

        if not value and default is not None:
            value = default
        if value or not required:
            return value
        print("  (Trường này bắt buộc. Hãy thử lại.)")


def ask_choice(prompt: str, choices: dict[str, str]) -> str:
    print(prompt)
    for key, desc in choices.items():
        print(f"  [{key}] {desc}")
    while True:
        v = input("Chọn: ").strip().lower()
        if v in choices:
            return v
        print(f"  (Nhập một trong: {', '.join(choices)})")


def ask_bool(prompt: str, *, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        v = input(f"{prompt} [{d}]: ").strip().lower()
        if not v:
            return default
        if v in ("y", "yes", "có", "co"):
            return True
        if v in ("n", "no", "không", "khong"):
            return False


# ---------------------------------------------------------------------------
# Core flow
# ---------------------------------------------------------------------------

def new_contributor_id() -> str:
    """Sinh ID nặc danh. Không lưu keypair ở đâu cả — không thể truy ngược."""
    a = secrets.token_hex(2)
    b = secrets.token_hex(2)
    return f"ha-{a}-{b}"


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_memory_id(memory_without_id: dict) -> str:
    h = hashlib.sha256(canonical_json(memory_without_id).encode("utf-8")).hexdigest()
    return h[:16]


def slugify(text: str) -> str:
    import re, unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:40] or "event"


def compute_event_id(name: str, date: str) -> str:
    year = date[:4] if len(date) >= 4 and date[:4].isdigit() else "0000"
    slug = slugify(name)
    h = hashlib.sha256(f"{year}-{slug}".encode()).hexdigest()[:4]
    return f"{year}-{slug}-{h}"


def interactive_flow() -> dict:
    print(EMPATHY_WELCOME)

    contributor_id = new_contributor_id()
    print(f"  Mã nặc danh của bạn cho lần đóng góp này: {contributor_id}")
    print("  (Không lưu ở đâu, không truy ngược được. Dùng để bạn tự tham chiếu.)\n")

    print("── Sự kiện ──")
    event_name = ask("Tên sự kiện (theo cách bạn gọi nó)")
    event_date = ask("Ngày / khoảng thời gian (ISO, ví dụ 2001-09-11 hoặc ~1975-04)")
    event_location = ask("Địa điểm (có thể mơ hồ nếu bạn không nhớ)", required=False)
    event_id = ask(
        "Event ID (bỏ trống để hệ thống tự sinh)",
        required=False,
    ) or compute_event_id(event_name, event_date)

    print("\n── Góc nhìn của bạn ──")
    role = ask_choice("Vai trò của bạn trong sự kiện:", ROLE_DESCRIPTIONS)
    proximity = ask_choice(
        "Bạn tiếp cận sự kiện như thế nào?",
        {"direct": "Trực tiếp chứng kiến", "nearby": "Ở gần đó", "secondhand": "Nghe người khác kể lại"},
    )
    age_raw = ask("Tuổi của bạn khi sự kiện xảy ra (số)", required=False)
    age = int(age_raw) if age_raw.isdigit() else None

    print("\n── Ký ức ──")
    print("Hãy kể bằng chính giọng của bạn. Không cần sửa văn phong.")
    what_happened = ask("Chuyện gì đã xảy ra (với bạn, quanh bạn)?", multiline=True)
    sensory = ask("Các chi tiết giác quan bạn còn nhớ (mùi, âm thanh, ánh sáng)", required=False, multiline=True)
    emotional = ask("Trạng thái cảm xúc của bạn khi đó", required=False, multiline=True)

    print("\n── Động cơ (BẮT BUỘC — nguyên tắc 4) ──")
    print("Đây là phần quan trọng nhất. Hãy thành thật nhất có thể.")
    motivation = ask("Vì sao bạn làm/ở đó/phản ứng như vậy?", multiline=True)
    pressure = ask("Có ai/tổ chức/hoàn cảnh nào gây áp lực lên bạn?", required=False, multiline=True)
    fears = ask("Khi đó bạn sợ điều gì?", required=False, multiline=True)

    print("\n── Bối cảnh nhìn lại ──")
    learned_after = ask("Sau này bạn hiểu ra điều gì mà lúc đó chưa biết?", required=False, multiline=True)
    differently = ask("Nếu được chọn lại, bạn có làm khác không? Vì sao?", required=False, multiline=True)

    print("\n── Đồng ý công bố ──")
    public = ask_bool("Cho phép công bố ký ức này?", default=True)
    embargo = ask("Nếu cần trì hoãn công bố đến một ngày cụ thể (YYYY-MM-DD, Enter để bỏ qua)", required=False) or None
    allow_ai = ask_bool("Cho phép AI engine phân tích ký ức này?", default=True)

    memory: dict = {
        "schema_version": "1.0",
        "contributor_id": contributor_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "event": {
            "event_id": event_id,
            "name": event_name,
            "date": event_date,
            **({"location": event_location} if event_location else {}),
        },
        "perspective": {
            "role": role,
            "proximity": proximity,
            **({"age_at_event": age} if age is not None else {}),
        },
        "memory": {
            "what_happened": what_happened,
            **({"sensory_details": sensory} if sensory else {}),
            **({"emotional_state": emotional} if emotional else {}),
        },
        "motivation": {
            "your_motivation": motivation,
            **({"external_pressure": pressure} if pressure else {}),
            **({"fears_at_the_time": fears} if fears else {}),
        },
        "context": {
            **({"what_learned_after": learned_after} if learned_after else {}),
            **({"would_do_differently": differently} if differently else {}),
        },
        "consent": {
            "public": public,
            "embargo_until": embargo,
            "withdrawn": False,
            "allow_ai_analysis": allow_ai,
        },
        "language": "vi",
    }

    memory["memory_id"] = compute_memory_id(memory)
    return memory


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_memory(memory: dict) -> list[str]:
    """Validate tối thiểu — không phụ thuộc jsonschema để giữ CLI nhẹ."""
    errors: list[str] = []
    if memory.get("schema_version") != "1.0":
        errors.append("schema_version phải là '1.0'")
    for path in [
        "memory_id", "contributor_id",
        "event.event_id", "event.name", "event.date",
        "perspective.role",
        "memory.what_happened",
        "motivation.your_motivation",
        "consent.public",
    ]:
        node = memory
        ok = True
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                ok = False
                break
            node = node[part]
        if not ok:
            errors.append(f"Thiếu trường bắt buộc: {path}")

    role = memory.get("perspective", {}).get("role")
    if role and role not in ROLE_DESCRIPTIONS:
        errors.append(f"perspective.role không hợp lệ: {role}")

    what = memory.get("memory", {}).get("what_happened", "")
    if len(what) < 20:
        errors.append("memory.what_happened phải có ít nhất 20 ký tự.")

    motiv = memory.get("motivation", {}).get("your_motivation", "")
    if len(motiv) < 10:
        errors.append("motivation.your_motivation phải có ít nhất 10 ký tự (nguyên tắc 4).")

    return errors


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_memory(memory: dict) -> Path:
    event_dir = ARCHIVE_ROOT / memory["event"]["event_id"]
    event_dir.mkdir(parents=True, exist_ok=True)
    out_path = event_dir / f"{memory['memory_id']}.json"
    if out_path.exists():
        raise FileExistsError(f"Memory đã tồn tại: {out_path} (cùng nội dung → cùng ID).")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    _update_index(event_dir, memory)
    return out_path


def _update_index(event_dir: Path, memory: dict) -> None:
    index_path = event_dir / "_index.json"
    if index_path.exists():
        with index_path.open(encoding="utf-8") as f:
            idx = json.load(f)
    else:
        idx = {"event_id": memory["event"]["event_id"], "memories": []}
    idx["memories"].append(
        {
            "memory_id": memory["memory_id"],
            "role": memory["perspective"]["role"],
            "submitted_at": memory.get("submitted_at"),
            "public": memory["consent"]["public"],
        }
    )
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Đóng góp một ký ức vào HumanArchive.")
    parser.add_argument("--from", dest="from_file", type=Path, help="Đọc memory từ file JSON (không tương tác).")
    parser.add_argument("--dry-run", action="store_true", help="Validate nhưng không ghi.")
    args = parser.parse_args()

    if args.from_file:
        with args.from_file.open(encoding="utf-8") as f:
            memory = json.load(f)
        if "memory_id" not in memory:
            memory["memory_id"] = compute_memory_id(memory)
    else:
        try:
            memory = interactive_flow()
        except KeyboardInterrupt:
            print("\n\n(Đã huỷ. Không có dữ liệu nào được lưu.)")
            return 130

    errors = validate_memory(memory)
    if errors:
        print("\nKý ức chưa hợp lệ:")
        for e in errors:
            print(f"  - {e}")
        return 2

    print("\n── Tóm tắt ──")
    print(f"  event_id      : {memory['event']['event_id']}")
    print(f"  memory_id     : {memory['memory_id']}")
    print(f"  role          : {memory['perspective']['role']}")
    print(f"  public        : {memory['consent']['public']}")
    print(f"  embargo_until : {memory['consent'].get('embargo_until')}")

    if args.dry_run:
        print("\n(dry-run: không ghi file.)")
        return 0

    if not args.from_file:
        if not ask_bool("\nGhi memory vào archive?", default=True):
            print("(Đã huỷ.)")
            return 0

    out = save_memory(memory)
    print(f"\nĐã lưu: {out.relative_to(REPO_ROOT)}")
    print("\nĐể đóng góp lên repo chung, bạn có thể:")
    print(f"  git add {out.relative_to(REPO_ROOT)} {out.parent.relative_to(REPO_ROOT)}/_index.json")
    print('  git commit -m "archive: add memory to <event_id>"')
    print("  git push")
    print("\nCảm ơn bạn. Mỗi ký ức làm bức tranh lịch sử khó bị bóp méo hơn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
