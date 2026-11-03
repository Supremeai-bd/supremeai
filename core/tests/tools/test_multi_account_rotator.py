"""Tests for tools/security_tools/multi_account_rotator.py.

Covers the pure selection/rotation core end-to-end without browsers:
Account health/quota logic, Provider best-account choice, config load/save round-trip,
whitelist-validated add_account, task-based provider selection, execute/failover,
LLM-gateway-backed _call_api (including the model-kwarg collision regression),
dashboard API-key extraction with fake pages, and the system-status aggregator.

Browser orchestration (_wait_for_verification, perform_autonomous_signup) needs a live
Playwright DOM and stays out of scope here by design.
"""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.tools.security_tools.multi_account_rotator import (
    ALLOWED_PROVIDERS,
    Account,
    MultiAccountRotator,
    Provider,
    ProviderStatus,
    TaskType,
    get_rotator,
    utc_now,
)

# ============================================================
# helpers
# ============================================================


def make_account(
    account_id="acc-1",
    provider="groq",
    status=ProviderStatus.ACTIVE,
    quota_used=0,
    quota_limit=1000,
    total_requests=0,
    failed_requests=0,
    rate_limit_hits=0,
    reset_time=None,
):
    return Account(
        id=account_id,
        provider=provider,
        email=f"{account_id}@example.com",
        api_key="sk-test",
        status=status,
        quota_used=quota_used,
        quota_limit=quota_limit,
        total_requests=total_requests,
        failed_requests=failed_requests,
        rate_limit_hits=rate_limit_hits,
        reset_time=reset_time,
    )


def make_provider(name="groq", accounts=None, status=ProviderStatus.ACTIVE, rpm=60, models=None):
    return Provider(
        name=name,
        base_url=f"https://api.{name}.com",
        models=models if models is not None else ["default-model"],
        rate_limit_rpm=rpm,
        rate_limit_tpm=100000,
        accounts=accounts or [],
        status=status,
        cost_per_token=0.0001,
    )


@pytest.fixture
def rotator(tmp_path):
    return MultiAccountRotator(config_file=str(tmp_path / "rotation_config.json"))


# ============================================================
# Account logic
# ============================================================


def test_account_unavailable_when_not_active():
    acc = make_account(status=ProviderStatus.INACTIVE)
    assert acc.is_available() is False


def test_account_unavailable_when_quota_exhausted():
    acc = make_account(quota_used=1000, quota_limit=1000)
    assert acc.is_available() is False


def test_account_unavailable_while_rate_limited():
    from backend.tools.security_tools.multi_account_rotator import utc_now

    acc = make_account(reset_time=utc_now() + timedelta(minutes=5))
    assert acc.is_available() is False


def test_account_available_when_reset_time_passed():
    acc = make_account(reset_time=utc_now() - timedelta(seconds=1))
    assert acc.is_available() is True


def test_account_available_when_active_with_quota():
    assert make_account().is_available() is True


def test_health_score_fresh_account_is_perfect():
    assert make_account().get_health_score() == 100.0


def test_health_score_penalizes_errors_quota_and_rate_limits():
    acc = make_account(
        total_requests=10, failed_requests=5, quota_used=500, quota_limit=1000, rate_limit_hits=3
    )
    expected = 100.0 - (0.5 * 50) - (0.5 * 30) - min(30, 20)
    assert acc.get_health_score() == pytest.approx(expected)


def test_health_score_clamped_to_zero():
    acc = make_account(
        total_requests=10, failed_requests=10, quota_used=1000, quota_limit=1000, rate_limit_hits=99
    )
    assert acc.get_health_score() == 0.0


def test_record_request_counts_success_and_failure():
    acc = make_account()
    acc.record_request(success=True)
    acc.record_request(success=False)
    assert acc.total_requests == 2
    assert acc.failed_requests == 1
    assert acc.last_used is not None


def test_record_rate_limit_sets_reset_window():
    from backend.tools.security_tools.multi_account_rotator import utc_now

    acc = make_account()
    before = utc_now()
    acc.record_rate_limit()
    assert acc.rate_limit_hits == 1
    assert acc.reset_time is not None
    delta = acc.reset_time - before
    assert timedelta(minutes=0.9) < delta <= timedelta(minutes=1.1)


# ============================================================
# Provider logic
# ============================================================


def test_provider_best_account_prefers_healthiest():
    weak = make_account("weak", total_requests=10, failed_requests=9)
    strong = make_account("strong")
    provider = make_provider(accounts=[weak, strong])
    assert provider.get_best_account() is strong


def test_provider_best_account_none_when_all_exhausted():
    provider = make_provider(accounts=[make_account("a", quota_used=1000, quota_limit=1000)])
    assert provider.get_best_account() is None


def test_provider_available_accounts_filters():
    provider = make_provider(
        accounts=[make_account("ok"), make_account("dead", status=ProviderStatus.FAILED)]
    )
    assert [acc.id for acc in provider.get_available_accounts()] == ["ok"]


# ============================================================
# config load / save round-trip
# ============================================================


def test_missing_config_creates_skeleton(rotator):
    import os

    assert os.path.exists(rotator.config_file)
    with open(rotator.config_file) as f:
        skeleton = json.load(f)
    assert skeleton == {"providers": [], "task_preferences": {}}


def test_corrupt_config_falls_back_to_skeleton(tmp_path):
    cfg = tmp_path / "broken.json"
    cfg.write_text("{definitely not json")
    rotator = MultiAccountRotator(config_file=str(cfg))
    with open(cfg) as f:
        assert json.load(f) == {"providers": [], "task_preferences": {}}
    assert rotator.providers == {}


def test_load_providers_converts_status_strings(tmp_path):
    cfg = tmp_path / "full.json"
    config = {
        "providers": [
            {
                "name": "groq",
                "base_url": "https://api.groq.com/openai/v1",
                "models": ["llama3-70b-8192"],
                "rate_limit_rpm": 60,
                "rate_limit_tpm": 1000000,
                "status": "rate_limited",
                "accounts": [
                    {
                        "id": "groq-1",
                        "provider": "groq",
                        "email": "a@b.com",
                        "api_key": "sk-1",
                        "created_at": "2026-01-01T00:00:00",
                        "last_used": None,
                        "total_requests": 3,
                        "failed_requests": 0,
                        "rate_limit_hits": 1,
                        "status": "pending_key_extraction",
                        "quota_used": 5,
                        "quota_limit": 100,
                        "reset_time": None,
                    }
                ],
            }
        ],
        "task_preferences": {"coding": ["groq"]},
    }
    cfg.write_text(json.dumps(config))
    rotator = MultiAccountRotator(config_file=str(cfg))
    provider = rotator.providers["groq"]
    assert provider.status is ProviderStatus.RATE_LIMITED
    assert provider.accounts[0].status is ProviderStatus.PENDING_KEY_EXTRACTION
    assert provider.accounts[0].total_requests == 3
    assert rotator.task_preferences == {"coding": ["groq"]}


def test_save_and_reload_round_trip(rotator, tmp_path):
    rotator.task_preferences = {"coding": ["groq"]}  # string keys, as produced by the load path
    rotator._create_provider_if_missing("groq")
    rotator.add_account("groq", "dev@example.com", "sk-live-123")
    rotator.save_config()

    reloaded = MultiAccountRotator(config_file=rotator.config_file)
    provider = reloaded.providers["groq"]
    assert provider.status is ProviderStatus.ACTIVE
    assert len(provider.accounts) == 1
    # loader must rebuild real Account objects, not raw dicts (loader fix below)
    assert isinstance(provider.accounts[0], Account)
    assert reloaded.task_preferences == {"coding": ["groq"]}


def test_provider_and_account_dicts_are_serializable(rotator):
    rotator._create_provider_if_missing("groq")
    rotator.add_account("groq", "dev@example.com", "sk-live-123")
    provider = rotator.providers["groq"]
    as_dict = rotator._provider_to_dict(provider)
    assert json.dumps(as_dict, default=str)  # must not raise
    assert as_dict["status"] == "active"
    # fresh accounts stay INACTIVE until an admin activates them (owner default)
    assert as_dict["accounts"][0]["status"] == "inactive"


# ============================================================
# add_account: security validation
# ============================================================


def test_add_account_rejects_non_whitelisted_provider(rotator):
    with pytest.raises(ValueError, match="Invalid provider"):
        rotator.add_account("sketchy_provider", "a@b.com", "sk-key")


def test_add_account_rejects_bad_email(rotator):
    with pytest.raises(ValueError, match="Invalid email"):
        rotator.add_account("groq", "not-an-email", "sk-key")


def test_add_account_rejects_empty_key(rotator):
    with pytest.raises(ValueError, match="API key cannot be empty"):
        rotator.add_account("groq", "a@b.com", "")


def test_add_account_creates_provider_and_estimates_quota(rotator):
    rotator.add_account("groq", "dev@example.com", "sk-live-123")
    assert "groq" in rotator.providers
    account = rotator.providers["groq"].accounts[0]
    assert account.id.startswith("groq-")
    assert account.api_key == "sk-live-123"
    assert "groq" in ALLOWED_PROVIDERS
    assert "gemini" in ALLOWED_PROVIDERS
    assert "mistral" in ALLOWED_PROVIDERS
    assert len(ALLOWED_PROVIDERS) >= 6


# ============================================================
# provider creation + metadata
# ============================================================


def test_create_provider_if_missing_rejects_unknown(rotator):
    with pytest.raises(ValueError, match="Invalid provider"):
        rotator._create_provider_if_missing("nope")


def test_create_provider_if_missing_uses_config_cache(rotator, monkeypatch):
    monkeypatch.setattr(
        "backend.tools.security_tools.multi_account_rotator.config_cache.get",
        lambda key, default=None: {
            "provider_base_url_groq": "https://api.groq.com/openai/v1",
            "provider_models_groq": ["llama3-70b-8192"],
            "rate_limit_groq_rpm": 30,
            "rate_limit_groq_tpm": 50000,
        }.get(key, default),
    )
    rotator._create_provider_if_missing("groq")
    provider = rotator.providers["groq"]
    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert provider.models == ["llama3-70b-8192"]
    assert provider.rate_limit_rpm == 30
    assert provider.rate_limit_tpm == 50000


@pytest.mark.parametrize(
    "name,expected_url",
    [
        ("groq", "https://api.groq.com/openai/v1"),
        ("deepseek", "https://api.deepseek.com"),
        ("google_ai_studio", "https://generativelanguage.googleapis.com"),
        ("openai", "https://api.openai.com/v1"),
        ("mystery", "https://api.mystery.com"),
    ],
)
def test_get_provider_metadata_known_and_fallback(rotator, name, expected_url):
    metadata = rotator._get_provider_metadata(name)
    assert metadata["base_url"] == expected_url


# ============================================================
# get_best_provider_for_task + requirements
# ============================================================


def _populate(rotator):
    rotator.task_preferences = {TaskType.CODING: ["groq", "deepseek"]}
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    rotator.providers["deepseek"] = make_provider(
        "deepseek", accounts=[make_account("d1")], status=ProviderStatus.INACTIVE
    )


def test_selects_preferred_provider_first(rotator):
    _populate(rotator)
    result = rotator.get_best_provider_for_task(TaskType.CODING)
    assert result is not None
    provider, account = result
    assert provider.name == "groq"
    assert account.id == "g1"


def test_skips_inactive_and_missing_providers(rotator):
    _populate(rotator)
    rotator.task_preferences = {TaskType.CODING: ["deepseek", "ghost", "groq"]}
    result = rotator.get_best_provider_for_task(TaskType.CODING)
    assert result[0].name == "groq"


def test_no_preferences_falls_back_to_all_providers(rotator):
    _populate(rotator)
    rotator.task_preferences = {}
    result = rotator.get_best_provider_for_task(TaskType.RESEARCH)
    assert result is not None


def test_returns_none_when_nothing_available(rotator):
    rotator.providers["groq"] = make_provider(
        "groq", accounts=[make_account("g1", status=ProviderStatus.FAILED)]
    )
    assert rotator.get_best_provider_for_task(TaskType.CODING) is None


def test_task_key_accepts_enum_and_string(rotator):
    _populate(rotator)
    by_enum = rotator.get_best_provider_for_task(TaskType.CODING)
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g2")])
    by_string = rotator.get_best_provider_for_task("coding")
    assert by_enum is not None and by_string is not None


def test_requirements_reject_cost(rotator):
    provider = make_provider("groq")
    provider.cost_per_token = 0.5
    account = make_account("g1")
    assert rotator._meets_requirements(provider, account, {"max_cost_per_token": 0.1}) is False


def test_requirements_reject_missing_model(rotator):
    provider = make_provider("groq", models=["default-model"])
    assert (
        rotator._meets_requirements(provider, make_account("g1"), {"required_model": "gpt-4"})
        is False
    )


def test_requirements_reject_slow_provider_on_speed_priority(rotator):
    provider = make_provider("groq", rpm=10)
    assert (
        rotator._meets_requirements(provider, make_account("g1"), {"speed_priority": 0.9}) is False
    )


def test_requirements_pass_when_all_met(rotator):
    provider = make_provider("groq", models=["gpt-4"], rpm=60)
    provider.cost_per_token = 0.01
    assert (
        rotator._meets_requirements(
            provider, make_account("g1"), {"max_cost_per_token": 1.0, "required_model": "gpt-4"}
        )
        is True
    )


# ============================================================
# execute_task + _call_api + failover
# ============================================================


@pytest.mark.asyncio
async def test_execute_task_returns_result_envelope(rotator):
    _populate(rotator)
    rotator._call_api = AsyncMock(return_value="answer text")
    result = await rotator.execute_task(TaskType.CODING, "write a function")
    assert result["result"] == "answer text"
    assert result["provider"] == "groq"
    assert result["account"] == "g1"
    assert result["model"] == "default-model"
    account = rotator.providers["groq"].accounts[0]
    assert account.total_requests == 1
    assert account.failed_requests == 0


@pytest.mark.asyncio
async def test_execute_task_returns_none_without_capacity(rotator):
    assert await rotator.execute_task(TaskType.CHAT, "hello") is None


@pytest.mark.asyncio
async def test_execute_task_fails_over_on_api_error(rotator):
    # Single provider, two fresh accounts. g1 fails once (health 50) so the
    # selector naturally promotes g2 (health 100) on the failover attempt.
    g1 = make_account("g1")
    g2 = make_account("g2")
    rotator.providers["groq"] = make_provider("groq", accounts=[g1, g2])
    rotator.task_preferences = {"coding": ["groq"]}

    async def flaky(provider, account, prompt, **kwargs):
        if account.id == "g1":
            raise RuntimeError("first account dead")
        return "recovered"

    rotator._call_api = flaky
    result = await rotator.execute_task(TaskType.CODING, "prompt")
    assert result is not None
    assert result["failover"] is True
    assert result["account"] == "g2"
    assert g1.failed_requests == 1
    assert g2.total_requests == 1


@pytest.mark.asyncio
async def test_failover_gives_up_after_exhaustion(rotator):
    rotator.providers["groq"] = make_provider("groq", accounts=[make_account("g1")])
    rotator.task_preferences = {"coding": ["groq"]}
    rotator._call_api = AsyncMock(side_effect=RuntimeError("all down"))
    result = await rotator._failover_execute(TaskType.CODING, "prompt")
    assert result is None
    account = rotator.providers["groq"].accounts[0]
    assert account.failed_requests >= 1


@pytest.mark.asyncio
async def test_call_api_unwraps_gateway_success_dict(rotator, monkeypatch):
    gateway = SimpleNamespace(
        acompletion=AsyncMock(return_value={"success": True, "text": "the answer"})
    )
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    provider = make_provider("groq", models=["llama3"])
    account = make_account("g1")
    result = await rotator._call_api(provider, account, "prompt")
    assert result == "the answer"
    gateway.acompletion.assert_awaited_once()
    assert gateway.acompletion.call_args.kwargs["api_key"] == "sk-test"


@pytest.mark.asyncio
async def test_call_api_stringifies_non_success_response(rotator, monkeypatch):
    gateway = SimpleNamespace(acompletion=AsyncMock(return_value={"success": False}))
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    result = await rotator._call_api(make_provider("groq"), make_account("g1"), "prompt")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_call_api_model_kwarg_no_collision(rotator, monkeypatch):
    """Regression: kwargs containing 'model' used to collide with the explicit model=."""
    gateway = SimpleNamespace(acompletion=AsyncMock(return_value={"success": True, "text": "ok"}))
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    provider = make_provider("groq", models=["fallback-model"])
    result = await rotator._call_api(
        provider, make_account("g1"), "prompt", model="explicit-model", temperature=0.2
    )
    assert result == "ok"
    kwargs = gateway.acompletion.call_args.kwargs
    assert kwargs["model"] == "explicit-model"
    assert kwargs["temperature"] == 0.2


@pytest.mark.asyncio
async def test_call_api_raises_without_any_model(rotator, monkeypatch):
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(
        gateway_module, "get_llm_gateway", lambda: SimpleNamespace(acompletion=AsyncMock())
    )
    provider = make_provider("groq", models=[])
    # owner error message is Bengali: '...কোনো মডেল নির্ধারিত নেই।'
    with pytest.raises(ValueError, match="মডেল"):
        await rotator._call_api(provider, make_account("g1"), "prompt")


@pytest.mark.asyncio
async def test_call_api_propagates_gateway_failure(rotator, monkeypatch):
    gateway = SimpleNamespace(acompletion=AsyncMock(side_effect=RuntimeError("boom")))
    import core.llm.llm_gateway as gateway_module

    monkeypatch.setattr(gateway_module, "get_llm_gateway", lambda: gateway)
    with pytest.raises(RuntimeError, match="boom"):
        await rotator._call_api(make_provider("groq"), make_account("g1"), "prompt")


# ============================================================
# dashboard key extraction (fake page)
# ============================================================


class FakeElement:
    def __init__(self, value=None, text=""):
        self._value = value
        self._text = text

    async def get_attribute(self, name):
        return self._value

    async def inner_text(self):
        return self._text


class FakePage:
    def __init__(self, results):
        self.results = list(results)
        self.tried = []

    async def wait_for_selector(self, selector, timeout=2000):
        self.tried.append(selector)
        item = self.results.pop(0) if self.results else None
        if item is None:
            raise TimeoutError(f"selector not found: {selector}")
        return item


@pytest.mark.asyncio
async def test_extract_api_key_reads_value_attribute(tmp_path):
    rotator = MultiAccountRotator(config_file=str(tmp_path / "r.json"))
    page = FakePage([FakeElement(value="gsk_live_1234567890")])
    key = await rotator._extract_api_key_from_dashboard(page, "groq")
    assert key == "gsk_live_1234567890"


@pytest.mark.asyncio
async def test_extract_api_key_falls_back_to_inner_text(tmp_path):
    rotator = MultiAccountRotator(config_file=str(tmp_path / "r.json"))
    page = FakePage([FakeElement(value=None, text="sk-proj-abcdefgh")])
    key = await rotator._extract_api_key_from_dashboard(page, "groq")
    assert key == "sk-proj-abcdefgh"


@pytest.mark.asyncio
async def test_extract_api_key_rejects_too_short_values(tmp_path):
    rotator = MultiAccountRotator(config_file=str(tmp_path / "r.json"))
    page = FakePage([FakeElement(value="short")])
    assert await rotator._extract_api_key_from_dashboard(page, "groq") is None


@pytest.mark.asyncio
async def test_extract_api_key_returns_none_when_all_selectors_miss(tmp_path):
    rotator = MultiAccountRotator(config_file=str(tmp_path / "r.json"))
    page = FakePage([])
    assert await rotator._extract_api_key_from_dashboard(page, "groq") is None
    assert len(page.tried) >= 7


@pytest.mark.asyncio
async def test_extract_api_key_swallows_page_crash(tmp_path):
    class BrokenPage:
        async def wait_for_selector(self, selector, timeout=2000):
            raise RuntimeError("page closed")

    rotator = MultiAccountRotator(config_file=str(tmp_path / "r.json"))
    assert await rotator._extract_api_key_from_dashboard(BrokenPage(), "groq") is None


# ============================================================
# system status + singleton + main guard
# ============================================================


def test_system_status_empty(rotator):
    status = rotator.get_system_status()
    assert status["total_providers"] == 0
    assert status["system_health"] == 0


def test_system_status_counts(rotator):
    _populate(rotator)
    # exhaust deepseek's account so health = 50%
    rotator.providers["deepseek"].accounts[0].quota_used = 10**9
    status = rotator.get_system_status()
    assert status["total_providers"] == 2
    assert status["total_accounts"] == 2
    assert status["active_accounts"] == 1
    assert status["system_health"] == pytest.approx(50.0)
    groq_status = status["providers"]["groq"]
    assert groq_status["accounts"][0]["health_score"] == 100.0


def test_get_rotator_is_singleton(tmp_path, monkeypatch):
    import backend.tools.security_tools.multi_account_rotator as mod

    monkeypatch.chdir(tmp_path)  # default config_file would otherwise land in CWD
    original = mod.rotator
    mod.rotator = None
    try:
        first = get_rotator()
        assert get_rotator() is first
    finally:
        mod.rotator = original


@pytest.mark.asyncio
async def test_main_exits_early_without_test_keys(tmp_path, monkeypatch):
    import backend.tools.security_tools.multi_account_rotator as mod

    monkeypatch.chdir(tmp_path)
    # pydantic Settings rejects unknown attrs — swap the whole settings object
    monkeypatch.setattr(
        mod,
        "settings",
        SimpleNamespace(test_groq_key_1=None, test_groq_key_2=None, test_deepseek_key_1=None),
    )
    await mod.main()  # warning + early return, must not raise
