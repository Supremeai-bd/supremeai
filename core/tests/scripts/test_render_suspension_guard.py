# বাংলা মন্তব্য: Issue #2624 — Render suspension guard চুক্তির গার্ড টেস্ট।
"""Regression tests locking the Render suspension-guard contract (#2624).

Deploy Train run 36695632388 প্রমাণ করেছে: ফ্রি-টিয়ার কোটা শেষ হলে Render
সার্ভিস সাসপেন্ড হয় → canary 503 + rollback-এ "রোলব্যাক টার্গেট নেই" — এবং
পুরনো পাইপলাইনের ফ্রি-কোটা pre-light চেক (`render_deploy_preflight.py`)
নতুন Deploy Train-এ ছিলই না। এই টেস্ট দুটি চুক্তি লক করে:

1. `suspension_reason()` — guard/rollback-এর একমাত্র সিদ্ধান্ত-লজিক; Render-এর
   বিভিন্ন suspended-ফিল্ড শেপ (bool/str/reasons-list) সঠিকভাবে পড়ে।
2. `render_rollback.py` সাসপেনশন প্রি-চেক বহাল রাখে (text-contract)।

pure ফাংশন-বডি AST দিয়ে হুবহু লোড করা হয় — কোনো ভারী import ছাড়াই,
deterministic ভাবে (#2620 প্রেসিডেন্ট)।
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

GUARD_PY_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "deploy" / "render_suspension_guard.py"
)
ROLLBACK_PY_PATH = Path(__file__).resolve().parents[3] / "scripts" / "deploy" / "render_rollback.py"


def _load_suspension_reason_fn() -> Callable[[dict[str, Any] | None], str | None]:
    """guard স্ক্রিপ্টের সোর্স থেকে শুধু `suspension_reason` AST-extract করে exec।

    বাংলা মন্তব্য: guard মডিউলটি import সময়েই render_client লোড করে (repo dep);
    টেস্টকে stdlib-only রাখতে shipped ফাংশন-বডিই বিচ্ছিন্ন namespace-এ exec করা
    হয় — ফাংশন এডিট/মুছে ফেললে টেস্ট সেটাই ধরবে।
    """
    source = GUARD_PY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "suspension_reason"
    ]
    assert fn_defs, (
        "suspension_reason() render_suspension_guard.py থেকে মুছে ফেলা হয়েছে — "
        "সাসপেনশন-চুক্তি (#2624) অরক্ষিত!"
    )
    module = ast.Module(body=fn_defs, type_ignores=[])
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(module, str(GUARD_PY_PATH), "exec"), namespace)
    return namespace["suspension_reason"]  # type: ignore[no-any-return]


def test_healthy_service_has_no_reason() -> None:
    fn = _load_suspension_reason_fn()
    assert fn({"suspended": False, "name": "core"}) is None
    assert fn({"name": "core"}) is None
    assert fn({}) is None


def test_suspended_bool_true_is_detected() -> None:
    fn = _load_suspension_reason_fn()
    reason = fn({"suspended": True})
    assert reason is not None
    assert "suspended=true" in reason


def test_suspended_string_flag_is_detected() -> None:
    fn = _load_suspension_reason_fn()
    assert fn({"suspended": "true"}) is not None
    assert fn({"suspended": "user_initiated"}) is not None
    # বাংলা মন্তব্য: "false"/অজানা স্ট্রিং flag কারণ নয় — false-positive নিষিদ্ধ।
    assert fn({"suspended": "false"}) is None
    assert fn({"suspended": "unknown_flag"}) is None


def test_suspended_reasons_list_is_surfaced() -> None:
    fn = _load_suspension_reason_fn()
    reason = fn({"suspended": False, "suspended_reasons": ["free_tier_exhausted"]})
    assert reason == "free_tier_exhausted"
    # বাংলা মন্তব্য: ক্যামেল-কেস ভ্যারিয়েন্টও (Render API শেপ) সামলাতে হবে।
    assert fn({"suspended": False, "suspendedReasons": ["billing"]}) == "billing"


def test_none_and_malformed_input_do_not_crash() -> None:
    fn = _load_suspension_reason_fn()
    assert fn(None) is None
    assert fn("not-a-dict") is None  # type: ignore[arg-type]
    assert fn([1, 2, 3]) is None  # type: ignore[arg-type]


def test_combined_bool_and_reasons_join() -> None:
    fn = _load_suspension_reason_fn()
    reason = fn({"suspended": True, "suspended_reasons": ["hours_exhausted"]})
    assert reason is not None
    assert "suspended=true" in reason
    assert "hours_exhausted" in reason


def test_rollback_keeps_suspension_precheck() -> None:
    """text-contract: Station 4 রোলব্যাক সাসপেনশন প্রি-চেক ছাড়া চলতে পারবে না।"""
    source = ROLLBACK_PY_PATH.read_text(encoding="utf-8")
    assert "from render_suspension_guard import suspension_reason" in source, (
        "render_rollback.py suspension-reason import হারিয়ে গেছে (#2624 চুক্তি)"
    )
    assert "client.get_service(service_id)" in source, (
        "রোলব্যাকের সার্ভিস-স্টেট প্রি-চেক অনুপস্থিত — সাসপেন্ডেড সার্ভিসে "
        "জেনেরিক 'no live predecessor' বিভ্রান্তি ফিরে আসবে"
    )
    assert "suspended_reason" in source, "সাসপেনশন কারণের অ্যাকশনেবল বার্তা অনুপস্থিত"
