"""Root acceptance tests for issue #1573 — Part 4: Provider Capability Registry
& Policy Engine (+ Parallel Planner/Architect Router).

Covers (per the issue's acceptance criteria):
* Router selects NATIVE MCP for ZCode and BROWSER channel for ChatGPT/Gemini.
* Disallowed execution modes fail-closed with POLICY_BLOCKED.
* Planner and Architect execute CONCURRENTLY and synthesize into one
  ImplementationBrief.
* Capability matrix matches the issue's table (zcode native_mcp+goal_mode,
  browser_channel=false; chatgpt/gemini/lovable/bolt policy_checked).
"""

from __future__ import annotations

import asyncio
import time

import pytest
from external_agents.contracts.task_contract import AgentProvider, TaskContract
from external_agents.control.policy_engine import (
    PolicyDecision,
    PolicyEngine,
    UserChannelConfig,
)
from external_agents.control.router import PlannerArchitectRouter
from external_agents.providers.chatgpt import ChatGPTProvider, ProviderExecutionError
from external_agents.providers.gemini import GeminiProvider
from external_agents.providers.registry import (
    ChannelPolicy,
    ExecutionMode,
    ProviderRegistry,
    build_default_registry,
)


@pytest.fixture()
def registry() -> ProviderRegistry:
    return build_default_registry()


@pytest.fixture()
def task() -> TaskContract:
    return TaskContract(goal="build the thing", allowed_providers=list(AgentProvider))


# ---------------------------------------------------------------------------
# 1. Capability registry defaults (issue table)
# ---------------------------------------------------------------------------
def test_builtin_capability_matrix(registry):
    zcode = registry.get(AgentProvider.ZCODE)
    assert zcode.native_mcp is True
    assert zcode.goal_mode is True
    assert zcode.browser_channel is ChannelPolicy.DISALLOWED

    for name in (
        AgentProvider.CHATGPT,
        AgentProvider.GEMINI,
        AgentProvider.LOVABLE,
        AgentProvider.BOLT,
    ):
        cap = registry.get(name)
        assert cap.native_mcp is False
        assert cap.browser_channel is ChannelPolicy.POLICY_CHECKED


def test_unknown_provider_fails_closed(registry):
    with pytest.raises(KeyError):
        registry.preferred_mode("ghost-ai")


def test_preferred_mode_ordering(registry):
    assert registry.preferred_mode(AgentProvider.ZCODE) is ExecutionMode.NATIVE_MCP
    assert (
        registry.preferred_mode(AgentProvider.CHATGPT) is ExecutionMode.BROWSER_CHANNEL
    )


# ---------------------------------------------------------------------------
# 2. Policy Engine — fail-closed semantics
# ---------------------------------------------------------------------------
def test_native_mcp_blocked_for_chatgpt(registry, task):
    engine = PolicyEngine(registry)
    verdict = engine.evaluate("chatgpt", ExecutionMode.NATIVE_MCP, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED
    assert "does not support" in verdict.reason


def test_browser_channel_blocked_for_zcode(registry, task):
    engine = PolicyEngine(registry)
    verdict = engine.evaluate("zcode", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED
    assert "forbids the browser channel" in verdict.reason


def test_browser_channel_disabled_by_user_config(registry, task):
    engine = PolicyEngine(
        registry,
        user_config=UserChannelConfig(allow_browser_channel=False),
    )
    verdict = engine.evaluate("chatgpt", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED
    assert "user config" in verdict.reason


def test_unknown_provider_blocked(registry, task):
    engine = PolicyEngine(registry)
    verdict = engine.evaluate("ghost-ai", ExecutionMode.NATIVE_MCP, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED


def test_task_allowlist_blocks_excluded_provider(registry):
    engine = PolicyEngine(registry)
    task = TaskContract(goal="g", allowed_providers=[AgentProvider.ZCODE])
    verdict = engine.evaluate("gemini", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED
    assert "allowed_providers" in verdict.reason


def test_operator_blocklist(registry, task):
    engine = PolicyEngine(
        registry, user_config=UserChannelConfig(blocked_providers=["gemini"])
    )
    verdict = engine.evaluate("gemini", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED


def test_compliance_failure_blocks_or_escalates_to_hitl(registry, task):
    engine = PolicyEngine(registry)
    engine.register_compliance_check(lambda t, m: (False, "scope audit failed"))

    # default: fail-closed POLICY_BLOCKED
    verdict = engine.evaluate("chatgpt", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict.decision is PolicyDecision.POLICY_BLOCKED
    assert "scope audit failed" in verdict.reason

    # operator opt-in: escalate to HITL instead of hard block
    engine_hl = PolicyEngine(
        registry,
        user_config=UserChannelConfig(require_hitl_for_browser_channel=True),
        compliance_checks=[lambda t, m: (False, "scope audit failed")],
    )
    verdict_hl = engine_hl.evaluate("chatgpt", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict_hl.decision is PolicyDecision.HITL_REQUIRED


def test_compliance_pass_allows_browser_channel(registry, task):
    engine = PolicyEngine(registry, compliance_checks=[lambda t, m: (True, "ok")])
    verdict = engine.evaluate("chatgpt", ExecutionMode.BROWSER_CHANNEL, task)
    assert verdict.decision is PolicyDecision.ALLOWED


def test_native_mcp_allowed_for_zcode(registry, task):
    engine = PolicyEngine(registry)
    verdict = engine.evaluate("zcode", ExecutionMode.NATIVE_MCP, task)
    assert verdict.decision is PolicyDecision.ALLOWED


# ---------------------------------------------------------------------------
# 3. Router — channel selection + concurrency + synthesis
# ---------------------------------------------------------------------------
def _scripted_chatgpt(responses: list[str]) -> ChatGPTProvider:
    async def gen(prompt: str) -> str:
        await asyncio.sleep(0.25)  # simulate latency
        return responses.pop(0)

    return ChatGPTProvider(generator=gen)


def _scripted_gemini(responses: list[str]) -> GeminiProvider:
    async def gen(prompt: str) -> str:
        await asyncio.sleep(0.25)  # simulate latency
        return responses.pop(0)

    return GeminiProvider(generator=gen)


def test_router_selects_native_mcp_for_zcode(registry, task):
    router = PlannerArchitectRouter(registry=registry)
    verdict = router.select_channel(AgentProvider.ZCODE, task)
    assert verdict.mode is ExecutionMode.NATIVE_MCP
    assert verdict.decision is PolicyDecision.ALLOWED


def test_router_selects_browser_channel_for_chatgpt_and_gemini(registry, task):
    router = PlannerArchitectRouter(registry=registry)
    planner_v, architect_v = router.plan_architect_channels(task)
    assert planner_v.provider == "chatgpt"
    assert planner_v.mode is ExecutionMode.BROWSER_CHANNEL
    assert architect_v.provider == "gemini"
    assert architect_v.mode is ExecutionMode.BROWSER_CHANNEL


def test_router_fails_closed_without_dispatch_when_blocked(task):
    registry = build_default_registry()
    engine = PolicyEngine(
        registry, user_config=UserChannelConfig(allow_browser_channel=False)
    )
    router = PlannerArchitectRouter(registry=registry, policy_engine=engine)

    dispatched = {"planner": False}

    async def spy_gen(prompt: str) -> str:
        dispatched["planner"] = True
        return "{}"

    router.planner = ChatGPTProvider(generator=spy_gen)

    outcome = asyncio.run(router.route(task))
    assert outcome.ok is False
    assert outcome.brief is None
    assert outcome.errors and "POLICY_BLOCKED" not in outcome.errors[0]
    assert (
        "browser channel disabled" in outcome.errors[0]
        or "policy" in outcome.errors[0].lower()
    )
    assert dispatched["planner"] is False, (
        "no provider call may happen when policy blocks"
    )


def test_planner_and_architect_run_concurrently_and_synthesize(registry):
    planner = _scripted_chatgpt(
        [
            '{"summary": "two-step plan", "steps": ['
            '{"index": 1, "title": "contracts", "target_files": ["backend/a.py"], "acceptance": ["validates"]},'
            '{"index": 2, "title": "tests", "target_files": ["tests/a.py"]}], "risks": ["drift"]}'
        ]
    )
    architect = _scripted_gemini(
        [
            '{"verdict": "approved", "rationale": "sound", '
            '"edge_cases": [{"scenario": "restart", "handled": true, "severity": "low"}]}'
        ]
    )
    router = PlannerArchitectRouter(
        registry=registry, planner=planner, architect=architect
    )
    task = TaskContract(goal="build it", allowed_providers=list(AgentProvider))

    started = time.monotonic()
    outcome = asyncio.run(router.route(task))
    elapsed = time.monotonic() - started

    assert outcome.ok, outcome.errors
    # 0.25s each serially = 0.5s; concurrent ≈ 0.25s → assert concurrency
    assert elapsed < 0.45, (
        f"planner/architect must run concurrently (took {elapsed:.2f}s)"
    )

    brief = outcome.brief
    assert brief is not None
    assert brief.plan.summary == "two-step plan"
    assert brief.target_files == ["backend/a.py", "tests/a.py"]
    assert brief.architecture is not None and brief.architecture.verdict == "approved"
    assert brief.architecture.provider == "gemini"
    assert brief.planner_provider == "chatgpt"
    assert brief.coder_constraints["architecture_verdict"] == "approved"
    assert brief.actionable is True


def test_synthesis_carries_architect_blockers_as_warnings_and_constraints(registry):
    planner = _scripted_chatgpt(
        ['{"summary": "plan", "steps": [{"index": 1, "title": "x"}]}']
    )
    architect = _scripted_gemini(
        [
            '{"verdict": "approved_with_changes", "required_changes": ["add retry"], '
            '"edge_cases": [{"scenario": "timeout", "handled": false, "severity": "high"}]}'
        ]
    )
    router = PlannerArchitectRouter(
        registry=registry, planner=planner, architect=architect
    )
    task = TaskContract(goal="build it")

    outcome = asyncio.run(router.route(task))
    assert outcome.brief is not None
    brief = outcome.brief
    assert brief.actionable is False
    assert "architecture review is blocking" in brief.warnings[0]
    assert brief.coder_constraints["required_changes"] == ["add retry"]


def test_planner_gateway_failure_is_honest(registry):
    async def dead_gen(prompt: str) -> str:
        raise ProviderExecutionError("gateway down")

    router = PlannerArchitectRouter(
        registry=registry,
        planner=ChatGPTProvider(generator=dead_gen),
        architect=GeminiProvider(
            generator=_scripted_gemini(['{"verdict": "approved"}'])._generator
        ),
    )
    task = TaskContract(goal="build it")
    outcome = asyncio.run(router.route(task))
    assert outcome.brief is None
    assert outcome.errors and "planner failed" in outcome.errors[0]
