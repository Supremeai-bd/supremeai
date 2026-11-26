"""TOMBSTONE (2026-11-26 re-audit G6/G7): dynamic LLM router retired.

কারণ (reaudit proof):
  * `gateway/dynamic_llm_router.py` — 0 non-test importers (repo-wide census).
  * gateway already routes via `core/engine/brain/model_router.py` (canonical).
  * Prior deep-audit (2026-11-01) also listed this as a duplicate layer.

Bridge cannot delete files — stub kept so baselines that reference the path
stay valid; any new import fails loudly instead of resurrecting dead logic.
"""

from __future__ import annotations


def get_router(*args, **kwargs):
    raise RuntimeError(
        "gateway.dynamic_llm_router is retired (2026-11-26). "
        "Use core.engine.brain.model_router instead."
    )


class DynamicLLMRouter:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "DynamicLLMRouter is retired (2026-11-26). "
            "Use core.engine.brain.model_router instead."
        )
