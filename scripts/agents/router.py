"""Compatibility shim for the autonomy router (issues #107, #108).

Re-exports the deterministic dynamic router and adds a small DynamicRouter
facade with the standard model-chain mappings used by the autonomy brain:
  - Bengali  -> Kimi-k2 / Moonshot
  - Code     -> DeepSeek-v3
  - Local    -> Gemini Flash
"""

from __future__ import annotations

try:
    import dynamic_router as _dr
except ImportError:  # pragma: no cover - package-style import fallback
    from scripts.agents import dynamic_router as _dr

# Re-export everything from the canonical implementation.
for _name in getattr(_dr, "__all__", []):
    globals()[_name] = getattr(_dr, _name)
# Also pull common public names explicitly.
for _name in (
    "DynamicRouter" if hasattr(_dr, "DynamicRouter") else None,
):
    pass

# Standard model-chain mappings (model registry ids).
MODEL_CHAINS: dict[str, list[str]] = {
    "bengali": ["moonshot/kimi-k2", "moonshot/kimi-k2.6"],
    "code": ["deepseek/deepseek-v3", "deepseek/deepseek-v4-pro"],
    "local": ["gemini/gemini-3.5-flash", "gemini/flash-2.0"],
    "local_backup": ["gemini/gemini-3.5-flash", "gemini/flash-2.0"],
}


class DynamicRouter:
    """Deterministic, rule-based model selector for autonomy tasks."""

    def __init__(self, chains: dict[str, list[str]] | None = None) -> None:
        self.chains = dict(chains or MODEL_CHAINS)

    def _resolve_key(self, task_type: str | None = None, language: str | None = None, **kwargs: object) -> str:
        tt = (task_type or kwargs.get("task_type") or kwargs.get("task") or kwargs.get("kind") or "code")
        lang = (language or kwargs.get("language") or kwargs.get("lang"))
        key = str(tt).lower() if tt is not None else "code"
        if lang and str(lang).lower() in ("bn", "bangla", "bengali"):
            key = "bengali"
        elif "bengali" in key or "bangla" in key or "bn" == key:
            key = "bengali"
        elif "code" in key or "coding" in key:
            key = "code"
        elif "local" in key:
            key = "local"
        if key not in self.chains:
            # fuzzy fallback
            for k in self.chains:
                if k in key or key in k:
                    key = k
                    break
            else:
                key = next(iter(self.chains))
        return key

    def select(self, task_type: str | None = None, language: str | None = None, **kwargs: object) -> str:
        key = self._resolve_key(task_type, language, **kwargs)
        chain = self.chains.get(key) or next(iter(self.chains.values()))
        return chain[0] if chain else ""

    def route(self, *args: object, **kwargs: object) -> str:
        # support route(task), route(task_type=...), route(task, language=...)
        if args:
            first = args[0]
            if isinstance(first, str):
                return self.select(first, **{k: v for k, v in kwargs.items()})
            if isinstance(first, dict):
                return self.select(first.get("task_type") or first.get("type") or first.get("kind"), **{k: v for k, v in kwargs.items()})
        return self.select(None, **{k: v for k, v in kwargs.items()})

    def choose(self, *args: object, **kwargs: object) -> str:
        return self.route(*args, **kwargs)

    def get_model(self, *args: object, **kwargs: object) -> str:
        return self.route(*args, **kwargs)

    def plan(self, *args: object, **kwargs: object) -> dict:
        model = self.route(*args, **kwargs)
        return {"model": model, "chain": self.chains.get(self._resolve_key(
            (args[0] if args and isinstance(args[0], str) else None), kwargs.get("language"), **{k: v for k, v in kwargs.items() if k != "language"}
        ), [])}

    def __call__(self, *args: object, **kwargs: object) -> str:
        return self.route(*args, **kwargs)

    # Expose underlying dynamic router module for compatibility.
    _dynamic_router = _dr


# Alias for older callers
Router = DynamicRouter

__all__ = ["DynamicRouter", "Router", "MODEL_CHAINS"]
# Re-export dynamic_router public names for convenience.
for _n in ("load_fixture", "validate_config", "classify", "plan_task", "execute", "RoutePlan", "RouteResult"):
    if hasattr(_dr, _n):
        globals()[_n] = getattr(_dr, _n)
        __all__.append(_n)
