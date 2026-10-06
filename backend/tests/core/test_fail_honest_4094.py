"""#4094 — fail-honest doctrine regression tests.

Defect class: **broken-import fallbacks + fail-open defaults** —
অস্তিত্বহীন মডিউলের try-import নীরব `None`/"healthy" স্টাবে ঢেকে যেত এবং
endpoint fail-open default fabricated state রিপোর্ট করত। এই টেস্টগুলো
চুক্তি মেশিন-এনফোর্সড রাখে:

  1. fitness_engine আসল `db`-র সাথে wired (persistence আর dead নয়)
  2. remediation stubs ব্যবহারে স্পষ্ট ব্যর্থ হয় — fabricated healthy/backup নয়
  3. intent_router-এ মৃত unified_router ব্রাঞ্চ আর নেই
  4. controller আসল `is_running` emit করে; endpoint default fail-honest (False)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]   # repo root (tests/core/ → tests → backend → root)
BACKEND = Path(__file__).resolve().parents[2]  # backend/
sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────── 1: fitness_engine wiring
def test_fitness_engine_db_is_real_module():
    """db আর None-মাস্কড fallback নয় — canonical SupabaseDB instance wired।"""
    from core.self_evolution.fitness_engine import db  # noqa: PLC0415

    assert db is not None, "#4094 regression: db masked to None — persistence dead again"
    assert hasattr(db, "client"), "unexpected db contract (SupabaseDB expected)"


# ─────────────────────────────────────── 2: remediation fail-honest stubs
def test_remediation_stubs_fail_loud_on_use():
    """HealthChecker/BackupManager স্টাব healthy-state fabricate করতে পারে না।"""
    from core.self_evolution.digital_twin.remediation_engine import (  # noqa: PLC0415
        BackupManager,
        HealthChecker,
    )

    with pytest.raises(RuntimeError, match="not wired"):
        HealthChecker()
    with pytest.raises(RuntimeError, match="not wired"):
        BackupManager()


def test_remediation_module_text_has_no_fabricated_healthy():
    """স্টাবের `check_health → True` / `mock-backup-id` আর ফাইলে নেই (greppable guard)।"""
    src = (BACKEND / "core" / "self_evolution" / "digital_twin" / "remediation_engine.py").read_text(
        encoding="utf-8"
    )
    assert "mock-backup-id" not in src
    assert 'return {"status": "healthy"}' not in src


# ───────────────────────────────────────────── 3: intent_router dead branch
def test_intent_router_dead_unified_router_branch_removed():
    """`core.unified_router` (কখনোই land করেনি) আর ফাইলে referenced হয় না।"""
    src = (BACKEND / "core" / "intent_router.py").read_text(encoding="utf-8")
    assert "unified_router" not in src
    assert "route_by_intent" not in src


def test_intent_router_sync_route_still_works():
    """মৃত ব্রাঞ্চ অপসারণের পরেও legacy sync `route()` অক্ষত।"""
    from core.intent_router import IntentRouter  # noqa: PLC0415
    from core.intent_router_v2 import PromptAction  # noqa: PLC0415

    action = IntentRouter().route("please deploy the latest build")
    assert isinstance(action, PromptAction)
    assert action.action_type  # বৈধ PromptAction ফেরত এসেছে


# ───────────────────────────────────────────── 4: is_running fail-honest
def test_controller_emits_real_is_running():
    """controller এখন আসল state-derived `is_running` emit করে।"""
    from evolution.auto_evolution_controller import (  # noqa: PLC0415
        AutoEvolutionController,
        EvolutionState,
    )

    ctrl = AutoEvolutionController()
    stats = ctrl.get_statistics()
    assert "is_running" in stats, "#4094: controller must emit real is_running"
    assert stats["is_running"] is (ctrl.current_state != EvolutionState.IDLE)


def test_server_status_default_is_fail_honest_false():
    """endpoint-এর default আর True নয় — missing key = False (fail-honest)।"""
    src = (BACKEND / "api" / "server.py").read_text(encoding="utf-8")
    assert 'stats.get("is_running", False)' in src
    assert 'stats.get("is_running", True)' not in src
