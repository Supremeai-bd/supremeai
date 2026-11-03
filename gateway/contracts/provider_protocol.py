"""SupremeAI Provider Protocol — চুক্তি-স্তর (plan §৪)

বাংলা মন্তব্য: এটি monolith `backend/core/llm/interfaces.py`-এর `ModelProvider`
Protocol-এর চুক্তি-প্রতিলিপি (SSOT সেখানেই, Core-freeze মানছে)। এই রেপোর adapter-রা
এই আকৃতি মানবে — যাতে ভবিষ্যৎ federation-cutover-এ adapter দুই পাশেই চলে,
কোনো তৃতীয় প্রোটোকল জন্মাবে না (জটিলতা-হ্রাস নীতি)।
"""
from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from typing import Any, Protocol


class ModelProvider(Protocol):
    """Contract for AI model execution providers.

    বাংলা: SupremeAI execution/telemetry সীমানার কর্তৃত্ব ধরে রাখে —
    adapter শুধু provider-native call জানে, policy/auth/metering এখানে নয়।
    """

    async def generate(
        self,
        model: str,
        messages: Sequence[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: float = 60.0,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a complete text completion. Returns OpenAI-compatible dict."""
        ...

    async def stream(
        self,
        model: str,
        messages: Sequence[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: float = 60.0,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream completion chunks (OpenAI-compatible deltas)."""
        ...

    async def health_check(self) -> bool:
        """Check if the provider is reachable and healthy."""
        ...
