# backend/tests/scripts/test_gateway_context_m03.py
"""M03 P0-পূর্ণাংশ — ১৩-route বাধ্যতামূলক context-passing প্রমাণ।

বাংলা: (১) InferenceContext.validate_attribution চুক্তি, (২) acompletion-এ
fail-closed attribution-যাচাই, (৩) scripts/ci/check_gateway_context.py
ratchet — বর্তমান গাছে ০ লঙ্ঘন + সিনথেটিক লঙ্ঘন-শনাক্তকরণ।
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

from core.llm.llm_gateway.completion import CompletionMixin
from core.llm.llm_gateway.context import InferenceContext
from core.llm.llm_gateway.errors import GatewayError

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, path: Path):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


context_gate = _load(
    "check_gateway_context", REPO_ROOT / "scripts" / "ci" / "check_gateway_context.py"
)


# ---------------------------------------------------------------------------
# InferenceContext.validate_attribution (attribution-only চুক্তি)
# ---------------------------------------------------------------------------


class TestValidateAttribution:
    def test_valid_attribution_only_context(self):
        ctx = InferenceContext(tenant_id="tenant-1", task_type="chat", stream=True)
        assert ctx.validate_attribution() == []

    def test_anonymous_is_honest_unknown_and_valid(self):
        ctx = InferenceContext(tenant_id="anonymous", task_type="chat")
        assert ctx.validate_attribution() == []

    def test_empty_tenant_is_violation(self):
        ctx = InferenceContext(tenant_id="", task_type="chat")
        errors = ctx.validate_attribution()
        assert any("tenant_id" in e for e in errors)

    def test_empty_task_type_is_violation(self):
        ctx = InferenceContext(tenant_id="t1", task_type="")
        assert ctx.validate_attribution()

    def test_negative_budget_is_violation(self):
        ctx = InferenceContext(tenant_id="t1", task_type="chat", max_cost_usd=-0.5)
        assert any("max_cost_usd" in e for e in ctx.validate_attribution())

    def test_nonpositive_latency_is_violation(self):
        ctx = InferenceContext(tenant_id="t1", task_type="chat", max_latency_seconds=0)
        assert any("max_latency_seconds" in e for e in ctx.validate_attribution())

    def test_payload_fields_optional_in_attribution_mode(self):
        # attribution-only ব্যবহারে prompt/messages ঐচ্ছিক — payload-নিয়ম নয়।
        ctx = InferenceContext(tenant_id="t1", task_type="chat")
        assert ctx.validate_attribution() == []

    def test_to_log_fields_never_carries_prompt_content(self):
        ctx = InferenceContext(prompt="secret prompt", tenant_id="t1", task_type="chat")
        fields = ctx.to_log_fields()
        assert "secret prompt" not in str(fields)
        assert fields["prompt_chars"] == len("secret prompt")


# ---------------------------------------------------------------------------
# acompletion — fail-closed attribution-যাচাই (হালকা স্টাব)
# ---------------------------------------------------------------------------


class _MinimalStubGateway(CompletionMixin):
    """কেবল চুক্তি-প্রবেশপথ চালানোর ন্যূনতম স্টাব (ভারী সহযোগী বাদ)।"""

    def __init__(self):
        self.litellm_ready = True

    def _ensure_litellm_ready(self):
        return None


class TestAcompletionContextContract:
    @pytest.mark.asyncio
    async def test_invalid_attribution_fails_closed_before_inference(self):
        gw = _MinimalStubGateway()
        bad_ctx = InferenceContext(tenant_id="", task_type="chat")
        with pytest.raises(GatewayError, match="attribution contract violation"):
            await gw.acompletion(prompt="hi", context=bad_ctx)

    @pytest.mark.asyncio
    async def test_negative_budget_context_fails_closed(self):
        gw = _MinimalStubGateway()
        bad_ctx = InferenceContext(tenant_id="t1", task_type="chat", max_cost_usd=-1.0)
        with pytest.raises(GatewayError):
            await gw.acompletion(prompt="hi", context=bad_ctx)

    @pytest.mark.asyncio
    async def test_context_carries_prompt_payload(self, monkeypatch):
        # context-এর prompt/task_type কল-আর্গকে অগ্রাধিকার দেয় — একক-সত্যের
        # উৎস context। cache-seam-এ capture করে sentinel দিয়ে থামাই।
        gw = _MinimalStubGateway()
        captured: dict = {}

        class _Stop(Exception):
            pass

        async def _fake_cache_query(prompt, task_type=None):
            captured["prompt"] = prompt
            captured["task_type"] = task_type
            raise _Stop()

        gw.cache = SimpleNamespaceCache(_fake_cache_query)
        ctx = InferenceContext(prompt="context payload", tenant_id="t1", task_type="research")
        with pytest.raises(_Stop):
            await gw.acompletion(prompt="arg payload", context=ctx)
        assert captured["prompt"] == "context payload"
        assert captured["task_type"] == "research"


class SimpleNamespaceCache:
    def __init__(self, query):
        self.query_similar = query


# ---------------------------------------------------------------------------
# CI ratchet — check_gateway_context.py
# ---------------------------------------------------------------------------


class TestGatewayContextGate:
    def test_current_tree_has_zero_violations(self):
        violations, total = context_gate.scan()
        assert violations == []
        # ৭ serving route-ফাইলে ১১টি inference কল-সাইট — সব context-বহন।
        # (#1832: websocket_agent.py orphan route removed — call-sites dropped 14→12.)
        # (#2258: browser_routes.py retired — shadowed legacy call-site dropped 12→11.)
        assert total >= 11

    def test_baseline_is_zero(self):
        assert context_gate.BASELINE == 0

    def test_synthetic_violation_is_detected(self, tmp_path, monkeypatch):
        good = tmp_path / "good_route.py"
        good.write_text(
            "from core.llm.llm_gateway import llm_gateway\n"
            "async def ok():\n"
            "    return await llm_gateway.acompletion(prompt='p', context=ctx)\n",
            encoding="utf-8",
        )
        bad = tmp_path / "bad_route.py"
        bad.write_text(
            "from core.llm.llm_gateway import llm_gateway\n"
            "async def bad():\n"
            "    return await llm_gateway.acompletion(prompt='p')\n",
            encoding="utf-8",
        )
        factory = tmp_path / "factory_route.py"
        factory.write_text(
            "from core.llm.llm_gateway import get_llm_gateway\n"
            "gw = get_llm_gateway()\n"
            "async def bad2():\n"
            "    return await gw.async_generate(prompt='p')\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(context_gate, "ROUTES_DIR", tmp_path)
        violations, total = context_gate.scan()
        assert total == 3
        assert any("bad_route.py:3" in v for v in violations)
        assert any("factory_route.py:4" in v for v in violations)

    def test_gate_main_exits_zero_on_clean_tree(self, capsys):
        assert context_gate.main() == 0
        assert "PASS" in capsys.readouterr().out

    def test_route_files_build_context_ast_level(self):
        """প্রতিটি serving route-কলে context= keyword AST-স্তরেই প্রমাণিত।"""
        routes_dir = REPO_ROOT / "backend" / "api" / "routes"
        files_with_calls = set()
        for py_file in routes_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            names = context_gate._collect_gateway_names(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in context_gate.INFERENCE_METHODS
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in names
                ):
                    files_with_calls.add(py_file.name)
                    assert any(kw.arg == "context" for kw in node.keywords), (
                        f"{py_file.name}:{node.lineno} context-হীন"
                    )
        expected = {
            "chat.py",
            "task_workspace.py",
            "reasoning.py",
            "slash_commands.py",
            "stream_chat_sse.py",
            "scheduled_tasks.py",
            # "browser_routes.py" removed (#2258): the legacy double-mounted
            # module was retired; its shadowed ai-action never executed.
            "deep_research.py",
        }
        assert expected == files_with_calls
