"""Task 14-e (Wave 4 Moat) — failure-mode missions, part 1: বাহ্যিক সীমানা।

বাংলা: দুটি mission-level ব্যর্থতা-দৃশ্য, দুটোই অফলাইন ও deterministic —
pass^k হারনেস (scripts/ci/mission_passk.py) এই স্যুটকে k বার চালিয়ে
consistency মাপতে পারে, তাই কোনো ঘুমানো/নেটওয়ার্ক-নির্ভর প্রমাণ নেই।

Mission A — partial provider failover: LLM কল-চেইনের ৩ প্রোভাইডারের প্রথম দুটি
মারা গেলেও ব্যবহারকারী সম্পূর্ণ ফল পায়, প্রতিটি ব্যর্থতা লাউড লগ হয় এবং
সার্কিট-ব্রেকার হিসাব সঠিক থাকে। আসর: CompletionMixin.acompletion-এর আসল
ফলব্যাক লুপ (core/llm/llm_gateway/completion.py) — শুধু সহযোগীরা ফেক
(tests/core/test_llm_gateway_completion.py-র StubGateway প্যাটার্নের
স্বয়ংসম্পূর্ণ প্রতিরূপ; tests/ ডিরেক্টরি প্যাকেজ নয় বলে import-ভাগ করা যায় না)।

Mission B — নেটওয়ার্ক হুক জালিয়াতি প্রচেষ্টা: আক্রমণকারী একটি বৈধ অনুরোধ
ধরে রেখে তিন পরিবারে জালিয়াতি চালায় (n8n-ধাঁচের HMAC+timestamp, secret-header
পরিবার, GitHub-ধাঁচের HMAC) — প্রতিটি জাল বৈকল্প ৪০১-এ প্রত্যাখ্যাত হতে হবে,
আর বৈধ নিয়ন্ত্রণ-অনুরোধ যায়। সৎতার নোট: এই কোডবেসের প্রকৃত anti-replay
মেকানিজম হলো n8n পরিবারের timestamp-জানালা (৩০০s) — জানালার বাইরের
ক্যাপচার-করা অনুরোধের রিপ্লে প্রত্যাখ্যান হয়; জানালার ভিতরের ডুপ্লিকেট
রিপ্লে আটকানোর nonce-স্টোর কোডবেসে নেই, তাই সেই আচরণ ভান করে টেস্ট করা হয়নি।
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Mission A — shared deterministic stubs (CompletionMixin আসর, সহযোগী ফেক)
# ---------------------------------------------------------------------------

_CAMPAIGN_CHAIN = ["fallback-alpha/model-1", "fallback-beta/model-2", "fallback-gamma/model-3"]


def _provider_response(text: str, cost: float = 0.0021) -> dict[str, Any]:
    """cloud_adapter.generate-এর OpenAI-ধাঁচের ফল (tests/core-এর মতোই)।"""
    return {"choices": [{"message": {"content": text}}], "cost": cost}


class _FakeRecord:
    """track_llm_call-এর ন্যূনতম দাঁড়ায়-বস্তু (acompletion যেসব অ্যাট্রিবিউট ছোঁয়)।"""

    estimated_tokens: int | None = 11
    cost_usd: float = 0.0
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    latency_ms: int = 42


class _RecordingBreaker:
    """সার্কিট-ব্রেকারের হিসাব-রাখা প্রতিরূপ — allow_request সবসময় খোলা।"""

    def __init__(self) -> None:
        self.successes = 0
        self.failures = 0

    def allow_request(self) -> bool:
        return True

    def mark_success(self) -> None:
        self.successes += 1

    def mark_failure(self) -> None:
        self.failures += 1


class _StubGatewayFactory:
    """আসল CompletionMixin + ফেক সহযোগী (tests/core StubGateway-এর অনুরূপ)।

    বাংলা: সীম-মেথডগুলো অবশ্যই নিজের ক্লাসে থাকতে হবে — CompletionMixin-এর
    কোড শুধু self-এর মেথড ডাকে; বাইরের wrapper-এ রাখলে AttributeError হয়।
    """

    @staticmethod
    def build(chain: list[str]) -> Any:
        from core.llm.llm_gateway.completion import CompletionMixin

        class _Gateway(CompletionMixin):
            def __init__(self) -> None:
                self.mode = SimpleNamespace(value="auto")
                self.cache = SimpleNamespace(query_similar=AsyncMock(return_value=None))
                self.performance_optimizer = SimpleNamespace(
                    optimize_model_selection=AsyncMock(return_value=chain[0])
                )
                self.observability = SimpleNamespace(trace_generation=AsyncMock())
                self.local_adapter = None
                self.cloud_adapter = SimpleNamespace(generate=AsyncMock())
                self.breaker = _RecordingBreaker()
                self._chain = list(chain)

            # CompletionMixin-এর সহযোগী-সীম — ফেক।
            def _ensure_litellm_ready(self) -> None:
                return None

            def _build_call_chain(self, model, provider, task_type) -> list[str]:
                return list(self._chain)

            def _get_or_create_circuit_breaker(self, model) -> _RecordingBreaker:
                return self.breaker

            async def _get_api_key_for_model(self, model) -> str:
                return "sk-mission-stub"

            async def _handle_rate_limit_error(self, model, exc) -> bool:
                return False

        return _Gateway()


@pytest.fixture()
def _hermetic_llm_chain(monkeypatch):
    """Mission A-কে সম্পূর্ণ হারমেটিক রাখে: টেলিমেট্রি CM + নিরপেক্ষ Tier-0।

    বাংলা: আসল ConfidenceGatedDispatcher প্রথম ব্যবহারে নেটওয়ার্কে প্যাটার্ন
    আনতে পারে — CI অফলাইন থাকতে হবে, তাই Tier-0 রাউটারকে "non-deterministic"
    উত্তরে স্থির করা হয় (tests/core স্যুটের একই autouse রীতি)। acompletion-এর
    lazy `import litellm`-ও হারমেটিক দাঁড়ায়-বস্তু দিয়ে মেপে দেওয়া হয় —
    স্যান্ডবক্স/CI venv-এ litellm ইনস্টল না থাকলেও আসল ফলব্যাক লুপ চলে
    (test_embeddings_coverage.py-র sys.modules ইনজেকশন রীতি)।
    """
    import contextlib
    import sys
    from unittest.mock import MagicMock

    from core.llm.llm_gateway import completion as completion_mod

    monkeypatch.setitem(sys.modules, "litellm", MagicMock())

    @contextlib.asynccontextmanager
    async def fake_track(**kwargs):
        yield _FakeRecord()

    monkeypatch.setattr(completion_mod, "track_llm_call", fake_track)
    monkeypatch.setattr(
        completion_mod,
        "settings",
        SimpleNamespace(
            token_juice_enabled=False,
            enable_evolution_learning=False,
            llm_cost_per_token=0.00001,
        ),
    )
    neutral_router = MagicMock()
    neutral_router.route_with_confidence.return_value = SimpleNamespace(
        is_deterministic=False, deterministic_result=None, confidence=0.1
    )
    monkeypatch.setattr(
        "core.llm.advanced_model_router.get_advanced_router", lambda: neutral_router
    )


class TestMissionPartialProviderFailover:
    async def test_first_two_providers_fail_third_delivers_and_failures_logged(
        self, _hermetic_llm_chain, monkeypatch
    ):
        """বাংলা: ৩-স্তর কল-চেইনে প্রোভাইডার ১ ও ২ মারা যায় → ফলব্যাক ৩ সম্পূর্ণ
        ফল দেয়; দুটি ব্যর্থতাই আসল failover-লগে ("Trying next in chain") যায়,
        ব্রেকার হিসাব ২ ব্যর্থতা + ১ সাফল্য দেখায় — নীরব আংশিক ব্যর্থতা নেই।"""
        from core.logging_config import logger

        gw = _StubGatewayFactory.build(_CAMPAIGN_CHAIN)
        # প্রথম দুই প্রোভাইডারে বিস্ফোরণ, তৃতীয়টি সম্পূর্ণ ফল দেয়।
        gw.cloud_adapter.generate.side_effect = [
            RuntimeError("provider-alpha exploded"),
            RuntimeError("provider-beta exploded"),
            _provider_response("সম্পূর্ণ উত্তর: মিশন সম্পন্ন"),
        ]

        captured: list[str] = []
        sink_id = logger.add(captured.append, level="WARNING")
        try:
            result = await gw.acompletion(prompt="finish the mission drill")
        finally:
            logger.remove(sink_id)

        # ১) ব্যবহারকারী সম্পূর্ণ ফল পেল — আংশিক ব্যর্থতা বাইরে লিক হয়নি।
        assert result["success"] is True
        assert result["text"] == "সম্পূর্ণ উত্তর: মিশন সম্পন্ন"
        assert result["model"] == "fallback-gamma/model-3"
        assert result["cost"] == pytest.approx(0.0021)

        # ২) চেইন হুবহু ৩ বার চেষ্টা করেছে (২ ব্যর্থ + ১ সফল)।
        assert gw.cloud_adapter.generate.await_count == 3

        # ৩) আসল failover-লগ: প্রতিটি ব্যর্থ মডেলের জন্য "Trying next in chain"।
        joined = "".join(captured)
        assert "Model fallback-alpha/model-1 failed" in joined
        assert "Model fallback-beta/model-2 failed" in joined
        assert joined.count("Trying next in chain") == 2

        # ৪) ব্রেকার-হিসাব: ব্যর্থতা ২, সাফল্য ১ — পরবর্তী রাউটিং সিদ্ধান্তের ভিত।
        assert gw.breaker.failures == 2
        assert gw.breaker.successes == 1

        # ৫) বিজয়ী প্রোভাইডারের অবজারভেবিলিটি ট্রেস শুধু একবার, সঠিক মডেলে।
        gw.observability.trace_generation.assert_awaited_once()
        assert (
            gw.observability.trace_generation.await_args.kwargs["model"] == "fallback-gamma/model-3"
        )


# ---------------------------------------------------------------------------
# Mission B — তিন পরিবারে জালিয়াতি প্রচেষ্টা (HTTP সীমানা, mini-app রীতি)
# ---------------------------------------------------------------------------

_HUB_SECRET = "mission-campaign-hub-secret-7f3a"
_HMAC_FAMILY_SECRET = "mission-campaign-hmac-secret-91cd"
_HEADER_FAMILY_SECRET = "mission-campaign-header-secret-4be2"


def _patch_hook_secrets(monkeypatch, *, hmac_family: str, header_family: str) -> None:
    """settings._get_cached_secret সীম প্রতিস্থাপন — env/vault ছাড়া deterministic।"""

    def fake_get_cached_secret(key: str) -> str:
        return {
            "GITHUB_WEBHOOK_SECRET": hmac_family,
            "TELEGRAM_WEBHOOK_SECRET": header_family,
        }.get(key, "")

    monkeypatch.setattr(
        "core.config.settings._get_cached_secret", fake_get_cached_secret, raising=False
    )


def _hmac_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _hmac_family_app():
    from api.routes.n8n_webhooks import router as hmac_family_router

    app = FastAPI()
    app.include_router(hmac_family_router)
    return TestClient(app)


def _header_family_app():
    from api.routes.webhooks_ai import router as header_family_router

    app = FastAPI()
    app.include_router(header_family_router)
    return TestClient(app)


def _git_family_app():
    from api.routes.pr_review_api import router as git_family_router

    app = FastAPI()
    app.include_router(git_family_router)
    return TestClient(app)


class TestMissionWebhookForgeryCampaign:
    def test_captured_request_forgery_rejected_across_three_families(self, monkeypatch):
        """বাংলা: আক্রমণকারীর প্রচারণা — ধরে রাখা একটি বৈধ অনুরোধের নকল/বিকৃত
        সংস্করণ তিন পরিবারে ঢোকানো হয়; প্রতিটি জাল বৈকল্প ৪০১, বৈধ নিয়ন্ত্রণ
        যায়। রিপ্লে-সংবেদনশীল অংশ: n8n-ধাঁচের পরিবারে timestamp-জানালার বাইরের
        (৩০০s পরে) ক্যাপচার-করা পেলোড প্রত্যাখ্যান হয় — এটাই কোডবেসের প্রকৃত
        anti-replay প্রমাণ।"""
        import api.routes.n8n_webhooks as hmac_family_mod

        # মডিউল-লেভেল ধ্রুবক import-সময়ে স্থির হয় — পরীক্ষার জন্য সীম প্রতিস্থাপন।
        monkeypatch.setattr(hmac_family_mod, "N8N_WEBHOOK_SECRET", _HMAC_FAMILY_SECRET)
        _patch_hook_secrets(
            monkeypatch,
            hmac_family=_HMAC_FAMILY_SECRET,
            header_family=_HEADER_FAMILY_SECRET,
        )

        hmac_app = _hmac_family_app()
        header_app = _header_family_app()
        git_app = _git_family_app()

        # ── পরিবার ১: n8n-ধাঁচ (HMAC-SHA256 over "{timestamp}.{body}") ──────
        payload = {"event_id": "evt-14e", "status": "success", "message": "drill"}
        body = json.dumps(payload).encode("utf-8")
        fresh_ts = int(time.time())
        good_sig = _hmac_hex(_HMAC_FAMILY_SECRET, f"{fresh_ts}.".encode() + body)

        ok = hmac_app.post(
            "/api/v1/webhooks/n8n/callback",
            content=body,
            headers={"X-N8N-Timestamp": str(fresh_ts), "X-N8N-Signature": good_sig},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json() == {"status": "accepted"}

        tampered = json.dumps({**payload, "status": "hijacked"}).encode("utf-8")
        r = hmac_app.post(
            "/api/v1/webhooks/n8n/callback",
            content=tampered,
            headers={"X-N8N-Timestamp": str(fresh_ts), "X-N8N-Signature": good_sig},
        )
        assert r.status_code == 401, r.text

        r = hmac_app.post(
            "/api/v1/webhooks/n8n/callback",
            content=body,
            headers={"X-N8N-Timestamp": str(fresh_ts)},
        )
        assert r.status_code == 401, r.text

        # রিপ্লে: ক্যাপচার-করা অনুরোধ জানালার (৩০০s) বাইরে পুনরায় পাঠানো হলো।
        stale_ts = fresh_ts - 3600
        stale_sig = _hmac_hex(_HMAC_FAMILY_SECRET, f"{stale_ts}.".encode() + body)
        r = hmac_app.post(
            "/api/v1/webhooks/n8n/callback",
            content=body,
            headers={"X-N8N-Timestamp": str(stale_ts), "X-N8N-Signature": stale_sig},
        )
        assert r.status_code == 401, r.text

        # গোপন মান অনুপস্থিত → fail-closed (উঁচু লগ + প্রত্যাখ্যান)।
        monkeypatch.setattr(hmac_family_mod, "N8N_WEBHOOK_SECRET", "")
        r = hmac_app.post(
            "/api/v1/webhooks/n8n/callback",
            content=body,
            headers={
                "X-N8N-Timestamp": str(fresh_ts),
                "X-N8N-Signature": _hmac_hex(_HMAC_FAMILY_SECRET, f"{fresh_ts}.".encode() + body),
            },
        )
        assert r.status_code == 401, r.text
        monkeypatch.setattr(hmac_family_mod, "N8N_WEBHOOK_SECRET", _HMAC_FAMILY_SECRET)

        # ── পরিবার ২: secret-header পরিবার (setWebhook secret_token স্কিম) ──
        cb = {"callback_id": "cb-14e", "user_id": "u-1", "action": "approve_pr", "pr_id": "PR-14"}
        header_name = "X-Telegram-Bot-Api-Secret-Token"

        r = header_app.post("/api/v1/webhooks/telegram/callback", json=cb)
        assert r.status_code == 401, r.text  # হেডারই নেই

        r = header_app.post(
            "/api/v1/webhooks/telegram/callback",
            json=cb,
            headers={header_name: "wrong-guess"},
        )
        assert r.status_code == 401, r.text  # ভুল গোপন মান

        r = header_app.post(
            "/api/v1/webhooks/telegram/callback",
            json=cb,
            headers={header_name: _HEADER_FAMILY_SECRET},
        )
        assert r.status_code == 200, r.text  # বৈধ নিয়ন্ত্রণ
        assert r.json()["status"] == "approved"

        _patch_hook_secrets(monkeypatch, hmac_family=_HMAC_FAMILY_SECRET, header_family="")
        r = header_app.post(
            "/api/v1/webhooks/telegram/callback",
            json=cb,
            headers={header_name: _HEADER_FAMILY_SECRET},
        )
        assert r.status_code == 401, r.text  # secret আনসেট → fail-closed
        _patch_hook_secrets(
            monkeypatch,
            hmac_family=_HMAC_FAMILY_SECRET,
            header_family=_HEADER_FAMILY_SECRET,
        )

        # ── পরিবার ৩: git-provider-ধাঁচ (X-Hub-Signature-256 = "sha256=<hex>") ──
        event = {
            "action": "closed",
            "pull_request": {"number": 7},
            "repository": {"full_name": "o/r"},
        }
        event_body = json.dumps(event).encode("utf-8")
        git_path = "/api/v1/pr-review/webhook"

        r = git_app.post(
            git_path,
            content=event_body,
            headers={"X-Hub-Signature-256": f"sha256={_hmac_hex(_HMAC_FAMILY_SECRET, event_body)}"},
        )
        assert r.status_code == 200, r.text  # বৈধ নিয়ন্ত্রণ (রিভিউ-বিহীন action → ignored)
        assert r.json()["status"] == "ignored"

        hijacked = json.dumps({**event, "action": "opened"}).encode("utf-8")
        r = git_app.post(
            git_path,
            content=hijacked,
            headers={"X-Hub-Signature-256": f"sha256={_hmac_hex(_HMAC_FAMILY_SECRET, event_body)}"},
        )
        assert r.status_code == 401, r.text  # বিকৃত body + পুরোনো সিগনেচার

        r = git_app.post(git_path, content=event_body)
        assert r.status_code == 401, r.text  # সিগনেচার হেডার নেই

        _patch_hook_secrets(monkeypatch, hmac_family="", header_family=_HEADER_FAMILY_SECRET)
        r = git_app.post(
            git_path,
            content=event_body,
            headers={"X-Hub-Signature-256": f"sha256={_hmac_hex(_HMAC_FAMILY_SECRET, event_body)}"},
        )
        assert r.status_code == 401, r.text  # secret আনসেট → fail-closed
