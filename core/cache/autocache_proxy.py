from typing import Any

from core.monitoring.logging_config import logger


class AutoCacheProxy:
    """Legacy TTL/category helpers; unowned get_or_compute calls bypass reuse."""

    def __init__(self, semantic_cache: Any | None = None):
        self.semantic_cache = semantic_cache
        from cachetools import TTLCache  # type: ignore[import-untyped]

        self.request_history = TTLCache(maxsize=1000, ttl=300)
        self._max_history_value_bytes = 50 * 1024  # 50 KB

        self.ttl_matrix = {
            "static_docs": 86400,  # 24 hours
            "skills_catalog": 43200,  # 12 hours
            "ai_chat": 1800,  # 30 minutes
            "code_gen": 3600,  # 1 hour
            "user_dashboard": 0,  # Bypass cache / No TTL
        }

    def add_to_request_history(self, key: str, value: Any) -> None:
        """Add to history only if value is within bounds."""
        if isinstance(value, str) and len(value.encode("utf-8")) > self._max_history_value_bytes:
            logger.warning(f"[AutoCacheProxy] Skipping request_history for {key}: Value too large")
            return
        self.request_history[key] = value

    def infer_category_from_prompt(self, prompt: str, default_task: str = "general") -> str:
        """
        Infer query category from prompt content for dynamic TTL allocation.
        """
        prompt_lower = prompt.lower()
        if any(
            w in prompt_lower
            for w in ["doc", "documentation", "guide", "tutorial", "readme", "manifest"]
        ):
            return "static_docs"
        elif any(w in prompt_lower for w in ["skill", "catalog", "tools", "capabilities"]):
            return "skills_catalog"
        elif any(
            w in prompt_lower
            for w in ["def ", "class ", "function", "code", "import ", "bug", "refactor"]
        ):
            return "code_gen"
        elif any(
            w in prompt_lower
            for w in ["dashboard", "balance", "profile", "account", "wallet", "realtime"]
        ):
            return "user_dashboard"
        return "ai_chat"

    def get_ttl_for_category(self, category: str) -> int:
        """
        কুয়েরি ক্যাটাগরি অনুযায়ী TTL (সেকেন্ডে) প্রদান করা।
        """
        return self.ttl_matrix.get(category, 1800)

    def calculate_dynamic_ttl(self, prompt: str, category: str | None = None) -> int:
        """
        Calculate dynamic TTL based on category or prompt content.
        """
        cat = category or self.infer_category_from_prompt(prompt)
        return self.get_ttl_for_category(cat)

    async def get_or_compute(
        self, key: str, category: str, compute_fn: Any, *args, **kwargs
    ) -> Any:
        """Compute only: the legacy proxy has no authenticated reuse scope."""
        return await compute_fn(*args, **kwargs)

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        ইনপুট এবং আউটপুট টোকেন খরচের গতিশীল হিসাব করা।
        """
        from core.config_cache import config_cache

        input_rate = config_cache.get(f"{model}:input_cost") or 0.0
        output_rate = config_cache.get(f"{model}:output_cost") or 0.0
        return (input_tokens * input_rate) + (output_tokens * output_rate)

    def get_cost_summary(self) -> dict[str, Any]:
        """
        ইনপুট এবং আউটপুট টোকেন খরচের মোট সারাংশ প্রদান করা।
        """
        return {"total_cost": 0.0, "summary": "mock"}


# Class alias for backward compatibility with existing tests
AutocacheProxy = AutoCacheProxy
