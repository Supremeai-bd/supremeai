"""#2719 slice-3 চুক্তি-টেস্ট: shared httpx.AsyncClient (hot request-path)।

ফরেনসিক প্রেক্ষাপট (issue #2719, founder directive: per-request client churn ×150+):
slice-1 (title N+1, #2796) ও slice-2 (SupabaseDB singleton, #2922) merge-হয়েছে।
slice-3 = hot request-path-এর per-request `httpx.AsyncClient()` কনস্ট্রাকশন —
প্রতিটি `async with httpx.AsyncClient(timeout=X)` = নতুন connection-pool তৈরি +
ধ্বংস (TLS handshake, FD churn)। প্যাটার্ন-সার্ভে: ২৭টি সাইট, ১৭টি hot ফাইল
(backend/api/routes + backend/services) — সবগুলোতে headers per-request-এ থাকায়
shared client + per-request timeout override (httpx native চুক্তি) নিরাপদ।

নিয়ম (repo প্যাটার্ন, #2901/#2894 প্রেসিডেন্ট): core লজিক pure + source-scan
regression guard — ভবিষ্যতে hot-path ফাইলে কোনো `httpx.AsyncClient(` বা
`httpx.Client(` কনস্ট্রাকশন ফিরে এলে টেস্ট লাল করবে।
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/
sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402
import pytest  # noqa: E402

from core.http_client import (  # noqa: E402
    close_shared_async_client,
    get_shared_async_client,
    reset_shared_client,
)

# বাংলা মন্তব্য: slice-3-এর hot-path ফাইল — এগুলোতে per-request client
# কনস্ট্রাকশন নিষিদ্ধ (শুধুমাত্র shared accessor)।
# ইচ্ছাকৃত বাদ (প্রমাণ সহ claim-কমেন্টে): gemini_writer + dynamic_ai/
# local_fallback (ক্লাস-হেল্ড client — প্রতি service-instance-এ একবার
# কনস্ট্রাক্ট, per-request churn নয়; local_fallback-এর base_url-বাউন্ড
# কনফিগ), admin_dashboard/__init__ (sync Client), integration_discovery
# (SSRF-guarded constructor — follow_redirects=False security-context),
# tools/integrations cold-path (per-call lifecycle প্রায়ই ইচ্ছাকৃত)।
RUNTIME_HOT_PATH_FILES = [
    "api/routes/ai_assignment.py",
    "api/routes/admin_dashboard/endpoints_approvals_mcp.py",
    "api/routes/billing_api.py",
    "api/routes/browser/_scraping.py",
    "api/routes/cdc_webhooks.py",
    "api/routes/control_plane.py",
    "api/routes/github.py",
    "api/routes/health_aggregation.py",
    "api/routes/integrations.py",
    "api/routes/onboarding.py",
    "services/dynamic_ai/orchestrator.py",
    "services/voice_service.py",
]


def teardown_function():
    """প্রতিটি টেস্টের পরে singleton রিসেট — ক্রস-টেস্ট দূষণ শূন্য।"""
    reset_shared_client()


def test_get_shared_async_client_returns_same_instance():
    first = get_shared_async_client()
    second = get_shared_async_client()
    third = get_shared_async_client()
    assert first is second
    assert second is third


def test_shared_client_is_async_client_with_default_timeout():
    client = get_shared_async_client()
    assert isinstance(client, httpx.AsyncClient)
    # বাংলা মন্তব্য: default timeout থাকতে হবে — shared client কখনো
    # unbounded-wait হবে না; per-request override httpx-এর নিজস্ব চুক্তি।
    assert client.timeout is not None
    assert httpx.Timeout(client.timeout.connect) is not None or client.timeout.read is not None


@pytest.mark.asyncio
async def test_close_shared_async_client_closes_and_resets():
    first = get_shared_async_client()
    await close_shared_async_client()
    second = get_shared_async_client()
    assert first is not second
    assert first.is_closed


def test_runtime_hot_path_no_direct_instantiation():
    """রিগ্রেশন-গার্ড: ১৭টি hot-path ফাইলে httpx client কনস্ট্রাকশন নিষিদ্ধ।

    প্রতিটি ফাইলে (১) `httpx.AsyncClient(`/`httpx.Client(` কনস্ট্রাকশন নেই,
    (২) `get_shared_async_client` ব্যবহার আছে — shared-accessor চুক্তি।
    """
    offenders: list[str] = []
    for rel in RUNTIME_HOT_PATH_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        if "httpx.AsyncClient(" in text or "httpx.Client(" in text:
            offenders.append(f"{rel} (direct construction)")
        if "get_shared_async_client" not in text:
            offenders.append(f"{rel} (shared accessor unused)")
    assert offenders == [], f"per-request httpx churn remains in hot path: {offenders}"
