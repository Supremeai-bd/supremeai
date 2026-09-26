"""Root acceptance tests for issue #1574 — Part 5: ZCode Native MCP Integration
& Goal Mode Protocol.

Covers (per the issue's acceptance criteria):
* ZCode receives tasks via the MCP protocol — NO browser UI automation
  (native MCP channel asserted through the capability matrix + prompt).
* /goal prompt injection carries task boundaries, file targets and
  architectural constraints.
* Multi-round /goal execution signals tracked DURABLY in the state manager.
* SupremeAI worker tools exposed over standard MCP JSON-RPC 2.0.
* Policy-checked browser channel fallback refuses blocked providers.

No network, no real browser — CI-safe.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from browser.autonomous_browser import AutonomousBrowserAgent
from browser.session_manager import BrowserSessionManager
from external_agents.channels.browser_channel import BrowserChannel
from external_agents.channels.mcp_channel import McpChannelServer, SupremeAiWorkerTools
from external_agents.contracts.task_contract import (
    AgentProvider,
    TaskContract,
    TaskState,
)
from external_agents.control.policy_engine import PolicyEngine, UserChannelConfig
from external_agents.control.state_manager import AgentStateManager, InMemoryStore
from external_agents.providers.registry import ExecutionMode, build_default_registry
from external_agents.providers.zai import (
    GOAL_TOOL_NAME,
    HttpMcpTransport,
    ZCodeProvider,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class ScriptedZcodeTransport:
    """ZcodeTransport double scripted with per-round responses."""

    def __init__(self, responses: list[dict], delay: float = 0.0):
        self.responses = list(responses)
        self.delay = delay
        self.calls: list[dict] = []

    async def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append({"name": name, "arguments": arguments})
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.responses:
            return {"signal": "running", "note": "no scripted response"}
        return self.responses.pop(0)


@pytest.fixture()
def state_manager():
    return AgentStateManager(store=InMemoryStore())


@pytest.fixture()
def zcode_provider(state_manager):
    return ZCodeProvider(
        transport=ScriptedZcodeTransport([]), state_manager=state_manager
    )


@pytest.fixture()
def task():
    return TaskContract(
        goal="implement the widget",
        constraints={
            "target_files": ["backend/widgets/widget.py"],
            "forbidden_paths": ["backend/secrets/**"],
            "architecture_summary": "must use the guarded cascade",
        },
        allowed_providers=[AgentProvider.ZCODE],
    )


# ---------------------------------------------------------------------------
# 1. /goal prompt — boundaries, file targets, architectural constraints
# ---------------------------------------------------------------------------
def test_goal_prompt_contains_boundaries_targets_and_constraints(zcode_provider, task):
    prompt = zcode_provider.build_goal_prompt(task)
    assert prompt.startswith("/goal implement the widget")
    assert "task_id" in prompt and task.task_id in prompt
    assert "backend/widgets/widget.py" in prompt, "file targets must be injected"
    assert "backend/secrets/**" in prompt, "forbidden paths must be injected"
    assert "must use the guarded cascade" in prompt, "arch constraints must be injected"
    assert '"completed"' in prompt, "completion protocol must be defined"
    assert "browser" not in prompt.lower(), (
        "goal mode must not involve browser automation"
    )


def test_goal_prompt_includes_brief_targets(zcode_provider, task):
    brief = {"target_files": ["backend/extra.py"], "architecture_summary": "layered"}
    prompt = zcode_provider.build_goal_prompt(task, brief)
    assert "backend/extra.py" in prompt and "layered" in prompt


# ---------------------------------------------------------------------------
# 2. Multi-round /goal execution with DURABLE signal tracking
# ---------------------------------------------------------------------------
def _start_task(state_manager, task):
    """Realistic orchestration: the job API claims + starts before the provider runs."""
    state_manager.create_task(task)
    state_manager.claim(task.task_id, worker_id="zcode-1")
    state_manager.start(task.task_id)


def test_multi_round_execution_tracks_signals_durably(
    zcode_provider, state_manager, task
):
    transport = ScriptedZcodeTransport(
        [
            {"signal": "running", "note": "round 1: scaffolding"},
            {"signal": "running", "note": "round 2: tests added"},
            {"signal": "completed", "note": "all boundaries satisfied"},
        ]
    )
    provider = ZCodeProvider(transport=transport, state_manager=state_manager)
    _start_task(state_manager, task)

    result = asyncio.run(provider.execute_goal(task))

    assert result["completed"] is True
    assert len(result["rounds"]) == 3
    assert result["summary"] == "all boundaries satisfied"
    # Durable per-round checkpoints in the state manager
    checkpoints = state_manager.checkpoints(task.task_id)
    assert [c.payload["signal"] for c in checkpoints] == [
        "running",
        "running",
        "completed",
    ]
    assert [c.payload["round"] for c in checkpoints] == [1, 2, 3]
    # MCP protocol used — every round went through the goal tool
    assert all(c["name"] == GOAL_TOOL_NAME for c in transport.calls)


def test_max_rounds_exhaustion_fails_honestly(zcode_provider, state_manager, task):
    transport = ScriptedZcodeTransport(
        [{"signal": "running", "note": "still working"}] * 10
    )
    provider = ZCodeProvider(
        transport=transport, state_manager=state_manager, max_rounds=3
    )
    _start_task(state_manager, task)

    result = asyncio.run(provider.execute_goal(task))

    assert result["completed"] is False
    assert "max rounds (3) exhausted" in result["error"]
    assert len(state_manager.checkpoints(task.task_id)) == 3


def test_failure_signal_surfaces_honestly(zcode_provider, state_manager, task):
    transport = ScriptedZcodeTransport([{"signal": "failed", "note": "compile error"}])
    provider = ZCodeProvider(transport=transport, state_manager=state_manager)
    state_manager.create_task(task)

    result = asyncio.run(provider.execute_goal(task))
    assert result["completed"] is False and result["failed"] is True
    assert "compile error" in result["error"]


def test_awaiting_input_parks_for_human(zcode_provider, state_manager, task):
    transport = ScriptedZcodeTransport(
        [{"signal": "awaiting_input", "note": "need api key"}]
    )
    provider = ZCodeProvider(transport=transport, state_manager=state_manager)
    state_manager.create_task(task)

    result = asyncio.run(provider.execute_goal(task))
    assert result["awaiting_input"] is True
    assert result["completed"] is False


def test_rounds_survive_state_manager_restart(tmp_path, task):
    from external_agents.control.state_manager import JsonFileStore

    store = JsonFileStore(base_dir=tmp_path / "goal-state")
    sm1 = AgentStateManager(store=store)
    sm1.create_task(task)
    sm1.claim(task.task_id, worker_id="zcode-1")
    sm1.start(task.task_id)
    transport = ScriptedZcodeTransport([{"signal": "running", "note": "r1"}])
    provider = ZCodeProvider(transport=transport, state_manager=sm1)
    asyncio.run(provider.execute_goal(task))

    # "restart": fresh manager over the same store sees the durable round signal
    sm2 = AgentStateManager(store=store)
    checkpoints = sm2.checkpoints(task.task_id)
    assert checkpoints[0].payload == {"round": 1, "signal": "running", "note": "r1"}


# ---------------------------------------------------------------------------
# 3. ZCode channel = native MCP, never browser automation
# ---------------------------------------------------------------------------
def test_zcode_channel_is_native_mcp_not_browser():
    registry = build_default_registry()
    cap = registry.get(AgentProvider.ZCODE)
    assert cap.supports(ExecutionMode.NATIVE_MCP) is True
    assert cap.supports(ExecutionMode.BROWSER_CHANNEL) is False
    assert registry.preferred_mode(AgentProvider.ZCODE) is ExecutionMode.NATIVE_MCP


def test_http_transport_payload_shape():
    """HttpMcpTransport speaks JSON-RPC tools/call with Bearer auth + SSE handling."""
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            return None

        text = 'data: {"jsonrpc": "2.0", "id": 1, "result": {"content": {"signal": "completed"}}}'

    class FakeClient:
        def __init__(self, **kw):
            captured["kw"] = kw

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

    import httpx as _httpx

    transport = HttpMcpTransport(base_url="https://zcode.example", bearer_token="tok-1")
    orig_client = _httpx.AsyncClient
    _httpx.AsyncClient = FakeClient
    try:
        result = asyncio.run(
            transport.call_tool(GOAL_TOOL_NAME, {"goal_prompt": "/goal x"})
        )
    finally:
        _httpx.AsyncClient = orig_client

    assert captured["url"] == "https://zcode.example/mcp"
    body = captured["json"]
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == GOAL_TOOL_NAME
    assert captured["headers"]["Authorization"] == "Bearer tok-1"
    # SSE frame unwrapped to the content payload
    assert result == {"signal": "completed"}


# ---------------------------------------------------------------------------
# 4. SupremeAI worker tools over standard MCP JSON-RPC 2.0
# ---------------------------------------------------------------------------
def test_mcp_channel_initialize_and_tools_list(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_REPO_ROOT", str(tmp_path))
    server = McpChannelServer()

    init = asyncio.run(
        server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
    )
    assert init["result"]["serverInfo"]["name"] == "supremeai-worker-tools"

    listing = asyncio.run(
        server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
    )
    names = {t["name"] for t in listing["result"]["tools"]}
    assert names == {
        "supremeai_file_inspect",
        "supremeai_git_diff",
        "supremeai_test_run",
        "supremeai_memory_search",
    }


def test_mcp_channel_file_inspect_and_traversal_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_REPO_ROOT", str(tmp_path))
    (tmp_path / "app.py").write_text("print('hello')\n")
    server = McpChannelServer()

    call = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "supremeai_file_inspect",
                    "arguments": {"path": "app.py"},
                },
            }
        )
    )
    content = json.loads(call["result"]["content"][0]["text"])
    assert content["ok"] is True and "hello" in content["content"]

    # path traversal fails closed
    evil = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "supremeai_file_inspect",
                    "arguments": {"path": "../../etc/passwd"},
                },
            }
        )
    )
    payload = json.loads(evil["result"]["content"][0]["text"])
    assert payload["ok"] is False
    assert "escapes the repository root" in payload["error"]


def test_mcp_channel_unknown_tool_is_jsonrpc_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_REPO_ROOT", str(tmp_path))
    server = McpChannelServer()
    resp = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            }
        )
    )
    assert "error" in resp
    assert "unknown tool" in resp["error"]["message"]


def test_worker_tools_git_diff_honest_outside_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPREMEAI_REPO_ROOT", str(tmp_path))
    tools = SupremeAiWorkerTools()
    result = tools.git_diff()
    assert result["ok"] is False and "no git repository" in result["error"]


# ---------------------------------------------------------------------------
# 5. Policy-checked browser channel fallback
# ---------------------------------------------------------------------------
class SpyAgent(AutonomousBrowserAgent):
    instances = []

    def __init__(self, session=None, **kw):
        super().__init__(session=session, **kw)
        SpyAgent.instances.append(self)


@pytest.fixture(autouse=True)
def _fake_reasoner(monkeypatch):
    import browser.autonomous_browser as ab_module

    class FakeReasoner:
        async def decide(self, task, context=None, tools=None):
            return {"tool": "done", "reasoning": "fake", "source": "fake"}

    monkeypatch.setattr(
        ab_module.ReasoningOrchestrator,
        "get_instance",
        classmethod(lambda cls: FakeReasoner()),
    )


def test_browser_channel_dispatches_for_policy_allowed_provider(tmp_path):
    from browser.browser_session import BrowserSession

    def fake_factory(provider, session_id):
        session_page = SimplePage()
        return {"context": SimpleCtx(), "page": session_page}

    class SimplePage:
        def close(self):
            pass

    class SimpleCtx:
        def close(self):
            pass

    manager = BrowserSessionManager(session_factory=fake_factory)
    registry = build_default_registry()
    engine = PolicyEngine(registry)
    channel = BrowserChannel(
        registry=registry, policy_engine=engine, session_manager=manager
    )
    task = TaskContract(goal="explore chatgpt flow")

    SpyAgent.instances = []
    result = asyncio.run(
        channel.dispatch(
            task,
            "open the chat and submit the task",
            provider="chatgpt",
            agent_factory=SpyAgent,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert len(SpyAgent.instances) == 1
    assert len(manager) == 0, "session must be released after dispatch"


def test_browser_channel_refuses_blocked_provider_without_session():
    manager = BrowserSessionManager(session_factory=lambda p, s: {})
    registry = build_default_registry()
    engine = PolicyEngine(registry)
    channel = BrowserChannel(
        registry=registry, policy_engine=engine, session_manager=manager
    )
    task = TaskContract(goal="zcode never uses the browser")

    result = asyncio.run(channel.dispatch(task, "instructions", provider="zcode"))

    assert result["ok"] is False
    assert result["status"] == "POLICY_BLOCKED"
    assert "forbids the browser channel" in result["reason"]
    assert len(manager) == 0, "no session may be created for a blocked dispatch"


def test_browser_channel_requires_hitl_when_configured(tmp_path):
    manager = BrowserSessionManager(session_factory=lambda p, s: {})
    registry = build_default_registry()
    engine = PolicyEngine(
        registry,
        user_config=UserChannelConfig(require_hitl_for_browser_channel=True),
    )
    channel = BrowserChannel(
        registry=registry, policy_engine=engine, session_manager=manager
    )
    task = TaskContract(goal="gemini via browser")

    result = asyncio.run(channel.dispatch(task, "instructions", provider="gemini"))
    assert result["ok"] is False
    assert result["status"] == "HITL_REQUIRED"
