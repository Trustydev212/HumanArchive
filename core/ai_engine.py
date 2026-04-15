"""HumanArchive — AI Engine (v0.2)

Chịu trách nhiệm phân tích ký ức mà không vi phạm 5 nguyên tắc bất biến
(xem docs/ethics.md).

Cải tiến so với v0.1:
    * Gọi Claude thật (claude-opus-4-6, adaptive thinking, prompt-cached system)
    * Tự scrub PII trước khi gửi lên LLM (nguyên tắc 2)
    * Tự phát hiện trauma và thêm content warning (nguyên tắc 3)
    * Tự verify memory_id và tôn trọng consent/embargo (nguyên tắc 5)
    * Tự reject output nếu LLM trả về các trường phán xét (nguyên tắc 1)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .integrity import (
    allows_ai_analysis,
    filter_viewable,
    is_publicly_viewable,
    verify_memory_id,
)
from .llm import ClaudeClient, get_default_client
from .privacy import PIIFinding, find_pii, pseudonymize
from .trauma import TraumaAssessment, detect_trauma

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _require(memory: dict, path: str) -> Any:
    node: Any = memory
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"Memory thiếu trường bắt buộc: {path}")
        node = node[part]
    return node


def _safe(memory: dict, path: str, default: Any = None) -> Any:
    node: Any = memory
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _scrubbed_view(memory: dict) -> tuple[dict, list[PIIFinding]]:
    """Trả về (clone đã scrub PII, danh sách finding) để gửi lên LLM.

    Scrub:
        * memory.what_happened / sensory_details / emotional_state
        * motivation.your_motivation / external_pressure / fears_at_the_time
        * context.what_learned_after / would_do_differently
    """
    clone = json.loads(json.dumps(memory))  # deep copy an toàn
    all_findings: list[PIIFinding] = []

    def scrub(d: dict, key: str) -> None:
        val = d.get(key)
        if isinstance(val, str) and val:
            findings = find_pii(val)
            if findings:
                all_findings.extend(findings)
                d[key] = pseudonymize(val, findings)

    mem = clone.get("memory")
    if isinstance(mem, dict):
        for k in ("what_happened", "sensory_details", "emotional_state"):
            scrub(mem, k)
    motiv = clone.get("motivation")
    if isinstance(motiv, dict):
        for k in ("your_motivation", "external_pressure", "fears_at_the_time"):
            scrub(motiv, k)
    ctx = clone.get("context")
    if isinstance(ctx, dict):
        for k in ("what_learned_after", "would_do_differently"):
            scrub(ctx, k)

    return clone, all_findings


def _prompt_body(memory: dict) -> str:
    """Tóm tắt memory thành JSON ngắn gọn để đưa vào user prompt."""
    return json.dumps(
        {
            "event": memory.get("event"),
            "perspective": memory.get("perspective"),
            "memory": memory.get("memory"),
            "motivation": memory.get("motivation"),
            "context": memory.get("context"),
        },
        ensure_ascii=False,
        indent=2,
    )


# --------------------------------------------------------------------------
# Single-memory analysis
# --------------------------------------------------------------------------

@dataclass
class MemoryAnalysis:
    memory_id: str
    acknowledgement: str
    motivation_interpretation: str
    external_pressure_interpretation: str
    emotional_state_note: str
    uncertainty: str
    trauma: TraumaAssessment
    pii_scrubbed: int  # số PII đã scrub trước khi gửi LLM

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "acknowledgement": self.acknowledgement,
            "motivation_interpretation": self.motivation_interpretation,
            "external_pressure_interpretation": self.external_pressure_interpretation,
            "emotional_state_note": self.emotional_state_note,
            "uncertainty": self.uncertainty,
            "trauma": self.trauma.to_dict(),
            "pii_scrubbed_count": self.pii_scrubbed,
        }


def analyze_memory(memory: dict, *, llm: ClaudeClient | None = None) -> MemoryAnalysis:
    """Phân tích một ký ức đơn lẻ.

    Enforcements:
        * consent.allow_ai_analysis phải bật (nguyên tắc 2)
        * motivation.your_motivation phải có (nguyên tắc 4)
        * PII được scrub trước khi gửi lên LLM (nguyên tắc 2)
        * Trauma được phát hiện và kèm content warning (nguyên tắc 3)
        * LLM không được trả về trường phán xét (nguyên tắc 1)
    """
    if not allows_ai_analysis(memory):
        raise PermissionError(
            "Memory có allow_ai_analysis=false. Tôn trọng consent — không phân tích."
        )

    memory_id = _require(memory, "memory_id")
    _require(memory, "motivation.your_motivation")  # nguyên tắc 4

    trauma = detect_trauma(memory)
    scrubbed, findings = _scrubbed_view(memory)
    client = llm or get_default_client()

    user_prompt = (
        "Dưới đây là một ký ức cá nhân đã được ẩn danh. Hãy phân tích theo "
        "đúng định dạng JSON với các trường: acknowledgement, "
        "motivation_interpretation, external_pressure_interpretation, "
        "emotional_state_note, uncertainty (low|medium|high). "
        "Trả về JSON thôi, không kèm giải thích khác.\n\n"
        "MEMORY:\n" + _prompt_body(scrubbed)
    )

    try:
        parsed = client.complete_json(user_prompt)
    except ValueError as exc:
        # LLM vi phạm nguyên tắc 1 — refuse thay vì propagate
        log.error("LLM output vi phạm nguyên tắc 1: %s", exc)
        parsed = {
            "acknowledgement": "Tôi ghi nhận trải nghiệm của bạn.",
            "motivation_interpretation": "",
            "external_pressure_interpretation": "",
            "emotional_state_note": "",
            "uncertainty": "high",
            "_refused": str(exc),
        }

    return MemoryAnalysis(
        memory_id=memory_id,
        acknowledgement=str(parsed.get("acknowledgement", "")),
        motivation_interpretation=str(parsed.get("motivation_interpretation", "")),
        external_pressure_interpretation=str(parsed.get("external_pressure_interpretation", "")),
        emotional_state_note=str(parsed.get("emotional_state_note", "")),
        uncertainty=str(parsed.get("uncertainty", "high")),
        trauma=trauma,
        pii_scrubbed=len(findings),
    )


# --------------------------------------------------------------------------
# Cross-reference
# --------------------------------------------------------------------------

ALL_ROLES = ("participant", "witness", "authority", "organizer", "victim", "bystander")


@dataclass
class CrossReferenceReport:
    event_id: str
    memory_count: int
    roles_present: list[str]
    convergent_claims: list[dict]
    divergent_claims: list[dict]
    missing_perspectives: list[str]
    uncertainty: str
    integrity_issues: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "memory_count": self.memory_count,
            "roles_present": self.roles_present,
            "convergent_claims": self.convergent_claims,
            "divergent_claims": self.divergent_claims,
            "missing_perspectives": self.missing_perspectives,
            "uncertainty": self.uncertainty,
            "integrity_issues": self.integrity_issues,
            "note": (
                "Báo cáo này KHÔNG kết luận ai đúng ai sai. Các điểm divergent "
                "chỉ phản ánh sự khác biệt trong trải nghiệm và góc nhìn của "
                "từng người. Mỗi góc nhìn đều có giá trị."
            ),
        }


def cross_reference(
    memories: Iterable[dict], *, llm: ClaudeClient | None = None
) -> CrossReferenceReport:
    """So khớp nhiều ký ức về cùng sự kiện. Không xếp hạng sự đáng tin."""
    memories = list(memories)
    if not memories:
        raise ValueError("cross_reference cần ít nhất 1 memory.")

    event_ids = {_require(m, "event.event_id") for m in memories}
    if len(event_ids) != 1:
        raise ValueError(f"Tất cả memories phải cùng event_id. Tìm thấy: {event_ids}")
    event_id = next(iter(event_ids))

    # Integrity check: phát hiện memory có memory_id không khớp hash
    integrity_issues: list[dict] = []
    for m in memories:
        rep = verify_memory_id(m)
        if rep.tampered:
            integrity_issues.append(
                {
                    "claimed": rep.claimed,
                    "actual": rep.actual,
                    "note": "memory_id không khớp với hash nội dung — có thể bị sửa đổi.",
                }
            )

    roles_present = sorted({
        _safe(m, "perspective.role") for m in memories if _safe(m, "perspective.role")
    })
    missing = [r for r in ALL_ROLES if r not in roles_present]

    convergent, divergent = _compare_claims(memories)

    # Uncertainty: càng nhiều góc nhìn đa dạng → càng chắc chắn
    n = len(memories)
    if n >= 5 and len(roles_present) >= 3:
        uncertainty = "low"
    elif n >= 2:
        uncertainty = "medium"
    else:
        uncertainty = "high"

    return CrossReferenceReport(
        event_id=event_id,
        memory_count=n,
        roles_present=roles_present,
        convergent_claims=convergent,
        divergent_claims=divergent,
        missing_perspectives=missing,
        uncertainty=uncertainty,
        integrity_issues=integrity_issues,
    )


def _compare_claims(memories: list[dict]) -> tuple[list[dict], list[dict]]:
    """So sánh keyword chồng lấp giữa các memory + chênh lệch địa điểm.

    v1 đơn giản, v2 sẽ dùng LLM để trích atomic claim có cấu trúc.
    """
    from collections import Counter
    import math

    tokens_per_memory: list[set[str]] = []
    for m in memories:
        text = (_safe(m, "memory.what_happened") or "").lower()
        toks = {
            w.strip(".,;:\"'!?()[]{}")
            for w in text.split()
            if len(w.strip(".,;:\"'!?()[]{}")) >= 5
        }
        tokens_per_memory.append(toks)

    if not tokens_per_memory:
        return [], []

    threshold = max(2, math.ceil(len(tokens_per_memory) / 2))
    counter: Counter[str] = Counter()
    for toks in tokens_per_memory:
        counter.update(toks)

    convergent = [
        {"claim_token": tok, "supported_by": count}
        for tok, count in counter.most_common(20)
        if count >= threshold
    ]

    divergent: list[dict] = []
    locations = {_safe(m, "event.location") for m in memories if _safe(m, "event.location")}
    if len(locations) > 1:
        divergent.append(
            {
                "claim": "Địa điểm cụ thể của sự kiện",
                "perspectives": [
                    {"role": _safe(m, "perspective.role"), "says": _safe(m, "event.location")}
                    for m in memories
                ],
                "note": (
                    "Không xác định đúng/sai. Người khác nhau có thể ở "
                    "vùng khác nhau của cùng sự kiện."
                ),
            }
        )

    return convergent, divergent


# --------------------------------------------------------------------------
# Historical entry
# --------------------------------------------------------------------------

def generate_historical_entry(
    event_id: str,
    *,
    archive_root: Path | str = "archive",
    llm: ClaudeClient | None = None,
    as_of: date | None = None,
) -> str:
    """Tạo entry lịch sử đa góc nhìn từ toàn bộ memories của một event.

    Tôn trọng:
        * consent.public / withdrawn / embargo_until
        * Ẩn danh hoàn toàn (chỉ role, không contributor_id)
        * Thêm content warning nếu có trauma
    """
    root = Path(archive_root) / "events" / event_id
    if not root.exists():
        raise FileNotFoundError(f"Không tìm thấy event_id={event_id} trong {root}")

    all_memories: list[dict] = []
    for p in sorted(root.glob("*.json")):
        if p.name.startswith("_") or ".amend." in p.name:
            continue
        try:
            with p.open(encoding="utf-8") as f:
                mem = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        all_memories.append(mem)

    # Lọc theo consent
    memories = filter_viewable(all_memories, as_of=as_of)

    lines: list[str] = []
    lines.append(f"# Lịch sử đa góc nhìn — {event_id}")
    lines.append("")

    if not memories:
        total_hidden = len(all_memories)
        if total_hidden > 0:
            lines.append(
                f"*Có {total_hidden} ký ức đã được đóng góp cho sự kiện này, "
                f"nhưng không có ký ức nào đang được công bố công khai tại thời "
                f"điểm này (do consent, embargo, hoặc withdrawn).*"
            )
        else:
            lines.append("*Chưa có ký ức nào được đóng góp cho sự kiện này.*")
        return "\n".join(lines) + "\n"

    report = cross_reference(memories, llm=llm)

    # Trauma warning tổng hợp
    severe_count = sum(1 for m in memories if detect_trauma(m).severity == "severe")
    if severe_count:
        lines.append(
            f"> ⚠ **CẢNH BÁO NỘI DUNG**: {severe_count}/{len(memories)} ký ức "
            f"bên dưới mô tả trải nghiệm đau thương (bạo lực, mất mát, tù đày, ...). "
            f"Hãy cân nhắc trước khi đọc tiếp."
        )
        lines.append("")

    lines.append(
        "> *Entry này được tổng hợp từ nhiều ký ức cá nhân. Không có phán xét "
        "đúng/sai — chỉ có sự kiện được nhìn từ nhiều góc. Mọi trích dẫn được "
        "ẩn danh, chỉ gắn nhãn vai trò (role).*"
    )
    lines.append("")

    # Tổng quan
    lines.append("## Tổng quan")
    lines.append("")
    lines.append(f"- **Số ký ức đang được công bố:** {report.memory_count}")
    if len(all_memories) > len(memories):
        lines.append(
            f"- **Số ký ức đã đóng góp nhưng chưa công bố:** "
            f"{len(all_memories) - len(memories)} "
            f"(do embargo, withdrawn, hoặc không public)"
        )
    lines.append(f"- **Các vai trò có mặt:** {', '.join(report.roles_present) or '(chưa có)'}")
    if report.missing_perspectives:
        lines.append(
            f"- **Các vai trò cần được lắng nghe:** "
            f"{', '.join(report.missing_perspectives)}"
        )
    lines.append(f"- **Độ chắc chắn của tổng hợp:** {report.uncertainty}")
    if report.integrity_issues:
        lines.append(
            f"- **⚠ Integrity issues:** {len(report.integrity_issues)} memory có "
            f"memory_id không khớp content. Cần rà soát."
        )
    lines.append("")

    # Điểm trùng / khác
    lines.append("## Điểm trùng khớp giữa nhiều góc nhìn")
    lines.append("")
    if report.convergent_claims:
        for c in report.convergent_claims[:15]:
            lines.append(f"- `{c['claim_token']}` — được nhắc bởi {c['supported_by']} người.")
    else:
        lines.append("*Chưa tìm được điểm trùng rõ ràng.*")
    lines.append("")

    lines.append("## Điểm khác biệt giữa các góc nhìn")
    lines.append("")
    if report.divergent_claims:
        for d in report.divergent_claims:
            lines.append(f"### {d.get('claim', '(không tên)')}")
            for p in d.get("perspectives", []):
                lines.append(f"- **{p.get('role', '?')}** kể: {p.get('says', '')}")
            if d.get("note"):
                lines.append(f"> {d['note']}")
            lines.append("")
    else:
        lines.append("*Chưa phát hiện điểm khác biệt đáng kể.*")
    lines.append("")

    # Các ký ức gốc, đã ẩn danh + PII scrub
    lines.append("## Các ký ức gốc (ẩn danh, đã scrub PII)")
    lines.append("")
    for mem in memories:
        role = _safe(mem, "perspective.role", "?")
        trauma = detect_trauma(mem)
        lines.append(f"### Góc nhìn: **{role}**")
        lines.append("")
        if trauma.has_trauma:
            lines.append(f"> {trauma.content_warning()}")
            lines.append("")

        what = _safe(mem, "memory.what_happened", "")
        lines.append(pseudonymize(what).strip())
        lines.append("")
        motiv = _safe(mem, "motivation.your_motivation", "")
        if motiv:
            lines.append(f"> **Động cơ tự nhận:** {pseudonymize(motiv)}")
        pressure = _safe(mem, "motivation.external_pressure", "")
        if pressure:
            lines.append(f"> **Áp lực bên ngoài:** {pseudonymize(pressure)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Nếu bạn cũng có ký ức về sự kiện này — dù nhỏ đến đâu — hãy đóng "
        "góp qua `tools/submit.py`. Mỗi góc nhìn làm bức tranh khó bị bóp méo hơn.*"
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "MemoryAnalysis",
    "CrossReferenceReport",
    "analyze_memory",
    "cross_reference",
    "generate_historical_entry",
    "is_publicly_viewable",
]
