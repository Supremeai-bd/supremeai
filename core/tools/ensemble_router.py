"""TOMBSTONE (2026-11-26 re-audit G6/G7): ensemble router retired.

কারণ (reaudit proof):
  * `core/tools/ensemble_router.py` — 0 non-test importers (repo-wide census).
  * canonical router lives in `core/engine/brain/model_router.py` + gateway
    dynamic router; the ensemble path was a duplicate decision layer.
  * `route_and_vote` live shim had no production caller (only a comment ref
    in `core/tests/test_module_operational_contracts.py`).

এই ফাইলটি ইচ্ছাকৃতভাবে খালি রাখা হয়েছে (bridge cannot delete files) —
নতুন import এখানে এলে স্পষ্ট ব্যর্থতা দেবে, ভুল পথে নয়।
"""

from __future__ import annotations


class EnsembleRouter:
    """Retired — use core.engine.brain.model_router instead."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "EnsembleRouter is retired (2026-11-26). "
            "Use core.engine.brain.model_router (canonical) instead."
        )

    def route_and_vote(self, *args, **kwargs):
        raise RuntimeError(
            "EnsembleRouter.route_and_vote is retired. "
            "Use core.engine.brain.model_router instead."
        )
