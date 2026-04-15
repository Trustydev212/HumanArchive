"""RAG (Retrieval-Augmented Generation) cho HumanArchive.

RAG trên dữ liệu ký ức tập thể khác với RAG thông thường:

    * PII phải được scrub TRƯỚC khi embed (nguyên tắc 2)
    * Consent drift phải được enforce — memory withdrawn/embargoed
      không bao giờ xuất hiện trong index (nguyên tắc 5)
    * Retrieval phải BALANCED theo role — nếu không sẽ amplify bias,
      đánh mất toàn bộ giá trị đa góc nhìn của dự án
    * Query cũng phải scrub PII — chặn identity-probe attack

Mọi tầng trong module này tôn trọng các ràng buộc trên.
"""

from .embedder import Embedder, HashEmbedder, get_default_embedder
from .index import RAGIndex, RAGHit, build_index, load_index
from .answer import AnswerWithCitations, answer_question

__all__ = [
    "Embedder",
    "HashEmbedder",
    "get_default_embedder",
    "RAGIndex",
    "RAGHit",
    "build_index",
    "load_index",
    "AnswerWithCitations",
    "answer_question",
]
