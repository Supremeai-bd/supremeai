"""M17 P-A — HITL route-ownership contract (shadow-visibility sentinel).

বাংলা: প্রমাণিত দুটি shadow-জোড়ার মালিকানা এখানে পিন করা —

1. `/api/v1/hitl/{pending,approve,reject}` — মাউন্ট-অর্ডারে `hitl_admin`
   জেত (frontend ApprovalQueue/data/hooks.ts এই পৃষ্ঠেই খাওয়া)।
   executor-যুক্ত `approval_manager` রাউট-অর্ডারে পরে; তার approve/reject
   pending-task স্টোরে (আলাদা স্টোর, শূন্য producer) — ৭→১ স্টোর-একত্রীকরণ
   M17 P-D-র কাজ। এখানে "কম ভাঙা" বিজয়ী পিন করা হল যেন কোনো সাইলেন্ট
   mount-reorder ফ্রন্টএন্ড লুপ ভাঙতে না পারে — পরিবর্তন সচেতন সিদ্ধান্ত হবে।

2. `/admin-api/approvals` GET/POST — ক্যানোনিকাল pending-task view
   (endpoints_command) মালিক; MCP control-tower প্রক্সি সত্যীকরণে
   `/admin-api/approvals/mcp`-এ re-homed (আগে এটি first-import হয়ে জিতে
   MCP-unconfigured অবস্থায় নীরবে [] দিত — fake-empty queue)।
"""

from __future__ import annotations

from collections import defaultdict

from tests.api._route_introspection import (
    app_effective_routes,
    route_methods,
    route_module_name,
    route_path,
)


def _app_routes():
    """Effective (mount-time) routes — FastAPI ≥0.141 lazy-include tolerant.

    বাংলা মন্তব্য: fastapi 0.141+ এ include_router এখন lazy (_IncludedRouter)
    — app.routes-এ expanded APIRoute আর থাকে না; helper দুই আচরণকেই একরূপ করে
    (CI triage #2597 — ১০টা route-contract টেস্টের সাইলেন্ট empty-surface ফিক্স)।"""
    from core.app import app

    return app_effective_routes(app)


def _norm_module(module: str) -> str:
    """একই endpoint দুই import-নামে আসতে পারে (repo root vs backend/ CWD) —
    ফুল-suite-এ ``backend.api.routes.X`` ও ``api.routes.X`` একই ফাংশন;
    নরমালাইজ ছাড়া প্রতিটি রুট phantom-collision মনে হয়।"""
    return module[8:] if module.startswith("backend.") else module


def _winner(path: str, method: str) -> tuple[str, str]:
    """Return (endpoint-module, endpoint-name) of the FIRST route registered."""
    for r in _app_routes():
        if route_path(r) == path and method in route_methods(r):
            return route_module_name(r), route_endpoint_module_name(r)
    raise AssertionError(f"no route registered for {method} {path}")


def route_endpoint_module_name(route) -> str:
    endpoint = getattr(route, "endpoint", None)
    return getattr(endpoint, "__name__", "")


def _collisions() -> dict[tuple[str, str], set[str]]:
    """All (path, method) pairs answered by >1 distinct endpoint."""
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in _app_routes():
        for m in route_methods(r):
            seen[(route_path(r), m)].add(
                f"{route_module_name(r)}.{getattr(getattr(r, 'endpoint', None), '__name__', '')}"
            )
    return {k: v for k, v in seen.items() if len(v) > 1}


# ---------------------------------------------------------------------------
# 1) /api/v1/hitl — বিজয়ী পিন (hitl_admin = Firestore HITLEngine)
# ---------------------------------------------------------------------------


def test_hitl_pending_owned_by_hitl_admin() -> None:
    module, name = _winner("/api/v1/hitl/pending", "GET")
    assert module == "api.routes.hitl_admin", (
        f"/api/v1/hitl/pending মালিক বদলেছে: {module}.{name} — frontend "
        "ApprovalQueue চুক্তি সচেতনভাবে যাচাই করুন (M17 P-A ownership doc)"
    )


def test_hitl_approve_owned_by_hitl_admin() -> None:
    module, _ = _winner("/api/v1/hitl/approve/{record_id}", "POST")
    assert module == "api.routes.hitl_admin"


def test_hitl_reject_owned_by_hitl_admin() -> None:
    module, _ = _winner("/api/v1/hitl/reject/{record_id}", "POST")
    assert module == "api.routes.hitl_admin"


def test_hitl_cancel_reachable_via_approval_manager() -> None:
    # cancel শুধু approval_manager-এ আছে — এটি shadow নয়, একমাত্র মালিক।
    module, _ = _winner("/api/v1/hitl/cancel/{task_id}", "POST")
    assert module == "api.routes.approval_manager"


# ---------------------------------------------------------------------------
# 2) /admin-api/approvals — ক্যানোনিকাল pending-task view মালিক
# ---------------------------------------------------------------------------


def test_admin_api_approvals_owned_by_canonical_pending_task_view() -> None:
    module, _ = _winner("/admin-api/approvals", "GET")
    assert module.endswith("endpoints_command"), (
        f"/admin-api/approvals GET মালিক: {module} — MCP-proxy re-home "
        "(M17 P-A) উল্টে গেছে; fake-empty [] ফিরে এসেছে কি না যাচাই করুন"
    )


def test_admin_api_approvals_post_owned_by_canonical_lifecycle_bridge() -> None:
    module, _ = _winner("/admin-api/approvals", "POST")
    assert module.endswith("endpoints_command")


def test_mcp_proxy_rehomed_to_distinct_path() -> None:
    module, _ = _winner("/admin-api/approvals/mcp", "GET")
    assert module.endswith("endpoints_approvals_mcp")


# ---------------------------------------------------------------------------
# 3) অবশিষ্ট shadow-জোড়ার তালিকা — হ্রাস-অবধারিত (downward ratchet)
# ---------------------------------------------------------------------------


def test_route_shadow_surface_is_known_and_bounded() -> None:
    collisions = _collisions()
    # KNOWN shadow-ইনভেন্টরি (M17 P-A সেশনে পরিমাপিত; কেবল হ্রাস হবে —
    # বৃদ্ধি নিষিদ্ধ):
    # - /api/v1/hitl/*: hitl_admin (Firestore, FE-চুক্তি) বনাম approval_manager
    #   (pending-task স্টোর) — P-D ৭→১ একত্রীকরণে মিটবে।
    # - /api/browser/*: browser._crown_jewel বনাম browser_routes —
    #   test_router_mount_hygiene-এর KNOWN EXCEPTIONS-এ নথিভুক্ত।
    # - /api/v1/health: ৩-উপায় (full/deep/scraper) — role-filter দ্বারা পৃথক।
    # - /api/chat/stream: stream_chat_sse বনাম task.stream_chat —
    #   test_stream_chat_contract-এ দ্বৈত-রুট চুক্তি হিসেবে পিন।
    # - /api/v1/agents/execute, /api/ci/webhook: legacy যমজ — মালিকানা
    #   সিদ্ধান্ত founder-gated (এই সেশনের পরিধি নয়)।
    known = {
        ("/api/v1/hitl/pending", "GET"),
        ("/api/v1/hitl/approve/{record_id}", "POST"),
        ("/api/v1/hitl/reject/{record_id}", "POST"),
        ("/api/browser/browse-session", "POST"),
        ("/api/browser/ai-action", "POST"),
        ("/api/browser/security-scan", "POST"),
        ("/api/browser/screenshot", "POST"),
        ("/api/v1/health", "GET"),
        ("/api/chat/stream", "POST"),
        ("/api/v1/agents/execute", "POST"),
        ("/api/ci/webhook", "POST"),
    }
    unexpected = {k: v for k, v in collisions.items() if k not in known}
    assert not unexpected, (
        f"নতুন route-shadow: {unexpected} — first-match নীরব দখল নিষিদ্ধ "
        "(M17 P-A ratchet); distinct path বা conscious ownership doc লাগবে"
    )
