"""End-to-end RAG pipeline: question → retrieve → answer with citations.

Tôn trọng tất cả các ràng buộc đạo đức:
    * Query được scrub PII (chặn identity probe)
    * Retrieval role-balanced (chống bias amplification)
    * Context gửi lên Claude đã qua PII scrub (index entries)
    * Claude system prompt bao gồm 5 nguyên tắc (ClaudeClient đã inject)
    * Output bao gồm citation theo memory_id + role, không phán xét
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..llm import ClaudeClient, get_default_client
from .embedder import Embedder
from .index import RAGHit, RAGIndex, search_text


@dataclass
class AnswerWithCitations:
    question_scrubbed: str
    answer: str  # câu trả lời tổng hợp từ LLM
    citations: list[RAGHit] = field(default_factory=list)
    uncertainty: str = "medium"
    refused: str | None = None  # lý do refuse nếu có

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_scrubbed": self.question_scrubbed,
            "answer": self.answer,
            "uncertainty": self.uncertainty,
            "citations": [c.to_dict() for c in self.citations],
            "refused": self.refused,
        }


def _build_context_block(hits: list[RAGHit]) -> str:
    """Format các hit thành context block cho LLM, có chỉ số citation."""
    if not hits:
        return "(Không có memory nào phù hợp trong archive.)"
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        lines.append(
            f"[{i}] role={h.entry.role} | memory_id={h.entry.memory_id} | "
            f"event_id={h.entry.event_id} | score={h.score:.3f}\n"
            f"{h.entry.text_scrubbed}"
        )
    return "\n\n---\n\n".join(lines)


def answer_question(
    question: str,
    index: RAGIndex,
    *,
    llm: ClaudeClient | None = None,
    embedder: Embedder | None = None,
    k: int = 5,
) -> AnswerWithCitations:
    """Chạy pipeline RAG đầy đủ.

    Nếu index trống / không có hit nào trên ngưỡng → trả kết quả với
    `refused` giải thích lý do, không bịa đáp án.
    """
    # Scrub query trước khi log/embed (chặn identity probe)
    from ..privacy import find_pii, pseudonymize

    findings = find_pii(question)
    q_scrubbed = pseudonymize(question, findings) if findings else question

    hits = search_text(
        index, q_scrubbed, embedder=embedder, k=k, role_balance=True
    )

    if not hits:
        return AnswerWithCitations(
            question_scrubbed=q_scrubbed,
            answer=(
                "Chưa có ký ức nào trong archive phù hợp với câu hỏi này. "
                "Điều đó CÓ THỂ vì: (1) chưa ai kể về chủ đề này, "
                "(2) các ký ức liên quan đang bị embargo/withdrawn, "
                "(3) câu hỏi quá cụ thể hoặc dùng từ khác với người kể. "
                "Tôi không bịa đáp án."
            ),
            citations=[],
            uncertainty="high",
            refused="no_hits",
        )

    context = _build_context_block(hits)
    client = llm or get_default_client()

    user_prompt = (
        "Dưới đây là một số ký ức ẩn danh được retrieve từ archive. "
        "Dựa TRÊN các ký ức này (và chỉ chúng), hãy trả lời câu hỏi. "
        "KHÔNG kết luận ai đúng ai sai. Nếu các ký ức mâu thuẫn, hãy "
        "trình bày cả hai góc nhìn. Nếu không đủ dữ liệu, hãy nói rõ. "
        "Luôn cite bằng [số] tương ứng với ký ức đã dùng.\n\n"
        "Trả về JSON với: acknowledgement, answer (string, có thể chứa [1],[2]...), "
        "uncertainty (low|medium|high), divergent_points (list, có thể rỗng).\n\n"
        f"CÂU HỎI: {q_scrubbed}\n\n"
        f"KÝ ỨC ĐƯỢC RETRIEVE:\n\n{context}"
    )

    try:
        parsed = client.complete_json(user_prompt)
    except ValueError as exc:
        # LLM vi phạm nguyên tắc 1 — refuse
        return AnswerWithCitations(
            question_scrubbed=q_scrubbed,
            answer=(
                "Xin lỗi — tôi không thể trả lời câu hỏi này mà không vi phạm "
                "nguyên tắc 1 (không phán xét đúng/sai). LLM đã trả về output "
                "chứa trường cấm."
            ),
            citations=hits,
            uncertainty="high",
            refused=f"llm_violated_principle_1: {exc}",
        )

    ack = str(parsed.get("acknowledgement", ""))
    body = str(parsed.get("answer", ""))
    combined = (ack + "\n\n" + body).strip() if ack else body
    return AnswerWithCitations(
        question_scrubbed=q_scrubbed,
        answer=combined or "(LLM chưa được cấu hình — phần trả lời tổng hợp chưa sẵn có.)",
        citations=hits,
        uncertainty=str(parsed.get("uncertainty", "medium")),
    )
