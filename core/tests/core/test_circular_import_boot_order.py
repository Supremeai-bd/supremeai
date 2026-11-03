# SupremeAI — Circular Import Boot-Order Regression Test (#2476)
# ============================================================================
# বাংলা: রুট-অডিট সাইকেল-স্ক্যান (#2476) দ্বারা ফ্ল্যাগ করা ৪টি ইম্পোর্ট-জোড়ার
# boot-order robustness লক করে। প্রতিটি জোড়া দুই ক্রমেই (A→B এবং B→A) ফ্রেশ
# subprocess-এ ইম্পোর্ট করা হয় — কোনো ক্রমেই ImportError হলে টেস্ট লাল।
#
# যাচাইকৃত অবস্থা (verify-first, coder-1 bot 2026-09-29):
#   1. brain.model_router ↔ core.services      — module-লেভেল ব্যাক-এজ lazy-তে রূপান্তরিত
#   2. core.automation.execution_recorder
#      ↔ core.orchestration.conversation_orchestrator — TYPE_CHECKING-only
#   3. core.circles.bootstrap ↔ core.circles.governance_core — ফাংশন-বডিতে lazy
#   4. core.orchestration.capability_adapters
#      ↔ core.orchestration.conversation_orchestrator — ফাংশন-বডিতে lazy
# ============================================================================

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# বাংলা: backend/ ডিরেক্টরি = import root (backend.main চুক্তির সাথে সামঞ্জস্যপূর্ণ)
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# বাংলা: #2476-এ ফ্ল্যাগ করা ৪ জোড়া — নতুন সাইকেল স্ক্যানে ধরা পড়লে এখানে যোগ হবে
FLAGGED_PAIRS: list[tuple[str, str]] = [
    ("brain.model_router", "core.services"),
    ("core.automation.execution_recorder", "core.orchestration.conversation_orchestrator"),
    ("core.circles.bootstrap", "core.circles.governance_core"),
    ("core.orchestration.capability_adapters", "core.orchestration.conversation_orchestrator"),
]


def _import_in_fresh_process(mod_a: str, mod_b: str) -> subprocess.CompletedProcess[str]:
    """বাংলা: ফ্রেশ interpreter-এ দুই মডিউল নির্দিষ্ট ক্রমে ইম্পোর্ট — sys.modules
    ক্যাশ যেন ফলাফলকে প্রভাবিত না করে।"""
    code = f"import {mod_a}\nimport {mod_b}\nprint('BOOT-OK')"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # বাংলা: টেস্ট-বুট ডি-নয়েজ — হেভি মডিউলের ঐচ্ছিক ইন্টিগ্রেশন নীরব
    env.setdefault("SUPREMEAI_SERVICE_ROLE", "monolith")
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(BACKEND_ROOT),
        timeout=120,
    )


@pytest.mark.parametrize("mod_a,mod_b", FLAGGED_PAIRS)
@pytest.mark.parametrize("order", ["ab", "ba"])
def test_flagged_cycle_pair_imports_in_both_orders(mod_a: str, mod_b: str, order: str) -> None:
    """বাংলা: প্রতিটি ফ্ল্যাগড জোড়া দুই ক্রমেই ImportError ছাড়া ইম্পোর্ট হয় —
    #2476-এর 'boot failure' ঝুঁকির স্থায়ী রিগ্রেশন গার্ড।"""
    first, second = (mod_a, mod_b) if order == "ab" else (mod_b, mod_a)
    result = _import_in_fresh_process(first, second)
    assert result.returncode == 0, (
        f"#2476 boot-order regression: import {first} → {second} failed\n"
        f"stdout: {result.stdout[-800:]}\nstderr: {result.stderr[-800:]}"
    )
    assert "BOOT-OK" in result.stdout
