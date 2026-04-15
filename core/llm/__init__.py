"""LLM backend cho HumanArchive.

Module này cung cấp:
    * Giao tiếp với Claude API (Anthropic SDK) với prompt caching
    * Fallback an toàn về EchoLLM khi không có API key

Mọi tương tác LLM PHẢI đi qua lớp này để đảm bảo:
    * Mọi system prompt bị chặn 5 nguyên tắc bất biến được inject
    * Không có PII nào bị gửi đi mà chưa qua scrubber
    * Mọi output được kiểm tra không có trường "verdict"/"guilty"/...
"""

from .claude_client import ClaudeClient, get_default_client

__all__ = ["ClaudeClient", "get_default_client"]
