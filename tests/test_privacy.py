"""Test PII scrubber."""

from __future__ import annotations

from core.privacy import find_pii, pseudonymize, summarize_findings


class TestPIIDetection:
    def test_email_detected(self):
        findings = find_pii("Liên hệ abc@example.com để biết thêm.")
        kinds = {f.kind for f in findings}
        assert "email" in kinds

    def test_phone_detected(self):
        findings = find_pii("Gọi 0912345678 nếu cần.")
        assert any(f.kind == "phone" for f in findings)

    def test_vietnamese_name_detected(self):
        findings = find_pii("Tôi gặp Nguyễn Văn An ở đó.")
        assert any(f.kind == "person_name" for f in findings)

    def test_national_id_detected(self):
        findings = find_pii("CCCD: 079123456789.")
        assert any(f.kind == "national_id" for f in findings)

    def test_url_detected(self):
        findings = find_pii("Xem tại https://facebook.com/ai-do.")
        assert any(f.kind == "url" for f in findings)

    def test_handle_detected(self):
        findings = find_pii("Tweet của @some_handle đáng chú ý.")
        assert any(f.kind == "handle" for f in findings)

    def test_sentence_starter_not_matched_as_name(self):
        # "Tôi đến" không được match là person_name
        findings = find_pii("Tôi đến vào buổi sáng.")
        names = [f for f in findings if f.kind == "person_name"]
        assert not names


class TestPseudonymize:
    def test_pseudonymize_email(self):
        text = "Mail: abc@example.com"
        out = pseudonymize(text)
        assert "abc@example.com" not in out
        assert "<email:" in out

    def test_pseudonymize_phone(self):
        text = "Gọi 0912345678"
        out = pseudonymize(text)
        assert "0912345678" not in out

    def test_pseudonymize_name_uses_initial(self):
        text = "Tôi gặp Nguyễn Văn An."
        out = pseudonymize(text)
        assert "Nguyễn Văn An" not in out
        # Kỳ vọng: "<person:A.>" (chữ cái đầu của token cuối)
        assert "person:A" in out

    def test_pseudonymize_stable(self):
        # Cùng text → cùng output (vì hash ổn định)
        text = "Gọi 0912345678"
        assert pseudonymize(text) == pseudonymize(text)

    def test_pseudonymize_empty(self):
        assert pseudonymize("") == ""
        assert pseudonymize("Không có PII nào ở đây.") == "Không có PII nào ở đây."


class TestSummary:
    def test_summarize_counts(self):
        findings = find_pii(
            "Gọi 0912345678 hoặc mail abc@example.com. Gặp Nguyễn Văn An."
        )
        summary = summarize_findings(findings)
        assert summary.get("phone", 0) >= 1
        assert summary.get("email", 0) >= 1
