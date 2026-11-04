"""Schema registry for database-controlled runtime configuration.

The registry contains only safe defaults and validation metadata. Operational
values remain in ``system_config``; immutable safety bounds stay in code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConfigDefinition:
    key: str
    value_type: type | tuple[type, ...]
    default: Any
    category: str
    description: str
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: tuple[Any, ...] = ()
    public: bool = False
    restart_required: bool = False

    def validate(self, value: Any) -> Any:
        if isinstance(value, bool) and self.value_type is int:
            raise ValueError(f"{self.key} must be an integer")
        if not isinstance(value, self.value_type):
            raise ValueError(f"{self.key} must be of type {self.value_type}")
        if self.allowed_values and value not in self.allowed_values:
            raise ValueError(f"{self.key} must be one of {self.allowed_values}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.minimum is not None and value < self.minimum:
                raise ValueError(f"{self.key} must be >= {self.minimum}")
            if self.maximum is not None and value > self.maximum:
                raise ValueError(f"{self.key} must be <= {self.maximum}")
        return value


REGISTRY: dict[str, ConfigDefinition] = {
    # --- Runtime ---
    "runtime.max_concurrency": ConfigDefinition(
        "runtime.max_concurrency", int, 5, "runtime", "Maximum concurrent runtime tasks", 1, 100
    ),
    "runtime.max_prompt_chars": ConfigDefinition(
        "runtime.max_prompt_chars", int, 20000, "runtime", "Maximum prompt size in characters", 1000, 200000, public=True
    ),
    "runtime.retry_count": ConfigDefinition(
        "runtime.retry_count", int, 3, "runtime", "Retry count for provider calls", 0, 10
    ),
    "runtime.timeout_seconds": ConfigDefinition(
        "runtime.timeout_seconds", int, 60, "runtime", "Timeout for provider calls", 5, 600
    ),
    "runtime.browser_session_duration_minutes": ConfigDefinition(
        "runtime.browser_session_duration_minutes", int, 30, "runtime", "Browser session duration in minutes", 5, 240
    ),
    # --- Feature flags (public) ---
    "feature.self_healing": ConfigDefinition(
        "feature.self_healing", bool, False, "feature", "Enable self-healing workflows", public=True
    ),
    "feature.cost_guard": ConfigDefinition(
        "feature.cost_guard", bool, True, "feature", "Enable cost guardrails", public=True
    ),
    "feature.chat": ConfigDefinition(
        "feature.chat", bool, True, "feature", "Enable chat", public=True
    ),
    "feature.research": ConfigDefinition(
        "feature.research", bool, True, "feature", "Enable research", public=True
    ),
    "feature.scheduled_tasks": ConfigDefinition(
        "feature.scheduled_tasks", bool, True, "feature", "Enable scheduled tasks", public=True
    ),
    "feature.browser": ConfigDefinition(
        "feature.browser", bool, False, "feature", "Enable browser automation", public=True
    ),
    "feature.billing": ConfigDefinition(
        "feature.billing", bool, True, "feature", "Enable billing", public=True
    ),
    "feature.rollout_percentage": ConfigDefinition(
        "feature.rollout_percentage", int, 100, "feature", "Feature rollout percentage", 0, 100, public=True
    ),
    # --- System ---
    "system.maintenance_mode": ConfigDefinition(
        "system.maintenance_mode", bool, False, "system", "Put public services into maintenance mode", public=True
    ),
    "system.maintenance_message": ConfigDefinition(
        "system.maintenance_message", str, "", "system", "Maintenance message shown to users", public=True
    ),
    "system.degraded_message": ConfigDefinition(
        "system.degraded_message", str, "Service is degraded. Some features may be unavailable.", "system",
        "Degraded-mode message", public=True
    ),
    # --- Branding (public) ---
    "branding.product_name": ConfigDefinition(
        "branding.product_name", str, "SupremeAI", "branding", "Product name", public=True
    ),
    "branding.support_url": ConfigDefinition(
        "branding.support_url", str, "", "branding", "Support URL", public=True
    ),
    "branding.status_page_url": ConfigDefinition(
        "branding.status_page_url", str, "", "branding", "Status page URL", public=True
    ),
    # --- Navigation (public) ---
    "navigation.user": ConfigDefinition(
        "navigation.user", tuple, ("chat", "projects", "research", "scheduled_tasks", "profile", "settings"),
        "navigation", "User navigation items", public=True
    ),
    # --- Limits ---
    "limits.daily_usage": ConfigDefinition(
        "limits.daily_usage", int, 1000, "limits", "Daily usage limit", 0, 100000, public=True
    ),
    "limits.monthly_usage": ConfigDefinition(
        "limits.monthly_usage", int, 10000, "limits", "Monthly usage limit", 0, 1000000, public=True
    ),
    # --- Provider/Model ---
    "provider.default_model_chat": ConfigDefinition(
        "provider.default_model_chat", str, "moonshot/kimi-k2", "provider", "Default model for chat", public=True
    ),
    "provider.fallback_order": ConfigDefinition(
        "provider.fallback_order", tuple, ("moonshot/kimi-k2", "deepseek/deepseek-v3", "gemini/flash-2.0"),
        "provider", "Provider fallback order"
    ),
}


def get_definition(key: str) -> ConfigDefinition | None:
    return REGISTRY.get(key)


def validate_value(key: str, value: Any) -> Any:
    definition = get_definition(key)
    if definition is None:
        raise KeyError(f"Unknown configuration key: {key}")
    return definition.validate(value)


def safe_defaults(*, public_only: bool = False) -> dict[str, Any]:
    return {
        key: definition.default
        for key, definition in REGISTRY.items()
        if not public_only or definition.public
    }


def schema(*, public_only: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "key": definition.key,
            "type": definition.value_type.__name__
            if isinstance(definition.value_type, type)
            else "value",
            "category": definition.category,
            "description": definition.description,
            "minimum": definition.minimum,
            "maximum": definition.maximum,
            "allowed_values": list(definition.allowed_values),
            "public": definition.public,
            "restart_required": definition.restart_required,
        }
        for definition in REGISTRY.values()
        if not public_only or definition.public
    ]


__all__ = [
    "ConfigDefinition",
    "REGISTRY",
    "get_definition",
    "safe_defaults",
    "schema",
    "validate_value",
]
