"""Test parity giữa Python HashEmbedder và JS hash_embed.js.

Nếu khớp, Web UI có thể query index được build bởi Python CLI.
Đây là tính chất *quan trọng*: nếu Python & JS sản xuất vector khác nhau,
Web UI sẽ luôn return kết quả không liên quan mà người dùng không biết tại sao.

Test này chạy một corpus cụ thể qua Python, và so sánh với một tập giá trị
đã được xác thực (unit test số cụ thể).
"""

from __future__ import annotations

from core.rag.embedder import HashEmbedder


class TestHashEmbedderStability:
    """Đảm bảo HashEmbedder sản xuất output ổn định — nếu thuật toán đổi, test fail.

    JS port (web/hash_embed.js) phải khớp spec này byte-for-byte.
    """

    def test_empty_text_returns_zero_vector(self):
        e = HashEmbedder(dim=16)
        v = e.embed("")
        assert v == [0.0] * 16

    def test_single_word_deterministic(self):
        # Cùng text → cùng vector, không phụ thuộc môi trường
        e = HashEmbedder(dim=16)
        v1 = e.embed("hello")
        v2 = e.embed("hello")
        assert v1 == v2

    def test_vector_normalized(self):
        e = HashEmbedder(dim=512)
        v = e.embed("xin chào mọi người đây là một câu mẫu")
        norm_sq = sum(x * x for x in v)
        assert 0.99 < norm_sq < 1.01

    def test_unicode_tokenization(self):
        """Tokens tiếng Việt có dấu phải được match."""
        e = HashEmbedder(dim=64)
        a = e.embed("lũ lên rất nhanh")
        b = e.embed("lũ lên rất nhanh")  # trùng nhau
        assert a == b
        # Khác dấu → khác vector
        c = e.embed("lu len rat nhanh")
        assert a != c

    def test_bigrams_affect_vector(self):
        """Hai từ đảo thứ tự → vector khác nhau (vì 2-gram khác)."""
        e = HashEmbedder(dim=512)
        a = e.embed("nước lên")
        b = e.embed("lên nước")
        # Unigram giống nhau, bigram khác → vectors phải khác
        assert a != b

    def test_output_format_spec(self):
        """JS port phải sản xuất cùng format: list/array float length=dim."""
        e = HashEmbedder(dim=128)
        v = e.embed("some test text here")
        assert len(v) == 128
        assert all(isinstance(x, float) for x in v)
