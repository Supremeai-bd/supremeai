# বাংলা মন্তব্য: tests/core/test_orchestration_contracts.py
# ============================================================
# Issue: core/orchestration/contracts.py ছিল critical tier-এ untested (0%)।
# এই মডিউলে orchestration control plane-এর shared dataclass চুক্তি আছে
# (ConversationCommand, ExecutionRecord, OrchestrationResult, Capability)।
# সম্পূর্ণ pure dataclasses — কোনো external I/O নেই।
#
# AGENTS.md rules followed:
#   - Rule #61: happy + sad paths
#   - Rule #63: critical logic 100% coverage
#   - Rule #66: boundary tests (None, empty, max-length)
#   - Rule #67: Given-When-Then structure
# ============================================================

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

import pytest

from core.automation.models import ExecutionEnvelope
from core.orchestration.contracts import (
    Capability,
    ConversationCommand,
    ExecutionRecord,
    OrchestrationResult,
)


class TestConversationCommand:
    """ConversationCommand — একজন user-এর একটি conversational dispatch request।"""

    def test_basic_creation_with_required_fields(self):
        # Given: required fields
        # When: creating a ConversationCommand
        cmd = ConversationCommand(prompt="hello", user_id="u1", tenant_id="t1")

        # Then: required fields are set, defaults applied
        assert cmd.prompt == "hello"
        assert cmd.user_id == "u1"
        assert cmd.tenant_id == "t1"
        assert cmd.role == "user"  # default
        assert cmd.project_id is None
        assert cmd.conversation_id is None
        assert cmd.confirmation is False
        assert cmd.metadata == {}

    def test_creation_with_all_fields(self):
        # Given: all fields populated
        # When: creating a ConversationCommand
        cmd = ConversationCommand(
            prompt="do something",
            user_id="u2",
            tenant_id="t2",
            role="admin",
            project_id="proj-1",
            conversation_id="conv-1",
            confirmation=True,
            metadata={"key": "value"},
        )

        # Then: all fields preserved
        assert cmd.role == "admin"
        assert cmd.project_id == "proj-1"
        assert cmd.conversation_id == "conv-1"
        assert cmd.confirmation is True
        assert cmd.metadata == {"key": "value"}

    def test_frozen_dataclass_is_immutable(self):
        """বাংলা: ConversationCommand frozen — এটি modify করা যায় না।"""
        # Given: a created command
        cmd = ConversationCommand(prompt="x", user_id="u", tenant_id="t")

        # When/Then: attempting to mutate raises FrozenInstanceError
        with pytest.raises(AttributeError):
            cmd.prompt = "modified"

    def test_metadata_default_is_independent_per_instance(self):
        """বাংলা: default_factory ব্যবহার করে তাই প্রতিটি instance-এর নিজস্ব metadata dict।"""
        # Given: two separate commands
        cmd1 = ConversationCommand(prompt="a", user_id="u", tenant_id="t")
        cmd2 = ConversationCommand(prompt="b", user_id="u", tenant_id="t")

        # When: mutating cmd1's metadata
        cmd1.metadata["k"] = "v"

        # Then: cmd2's metadata is unaffected
        assert cmd2.metadata == {}

    def test_boundary_empty_prompt(self):
        # Boundary: empty string prompt
        cmd = ConversationCommand(prompt="", user_id="u", tenant_id="t")
        assert cmd.prompt == ""

    def test_boundary_unicode_prompt(self):
        # Boundary: Bengali + emoji in prompt
        cmd = ConversationCommand(prompt="বাংলা প্রম্পট 🚀", user_id="u", tenant_id="t")
        assert "বাংলা" in cmd.prompt
        assert "🚀" in cmd.prompt

    def test_boundary_long_prompt(self):
        # Boundary: very long prompt (10k chars)
        long_prompt = "x" * 10000
        cmd = ConversationCommand(prompt=long_prompt, user_id="u", tenant_id="t")
        assert len(cmd.prompt) == 10000

    def test_equality_same_fields(self):
        """বাংলা: frozen dataclass with same field values are equal।"""
        cmd1 = ConversationCommand(prompt="x", user_id="u", tenant_id="t")
        cmd2 = ConversationCommand(prompt="x", user_id="u", tenant_id="t")
        assert cmd1 == cmd2


class TestExecutionRecord:
    """ExecutionRecord — একটি governed dispatch-এর canonical truth record।"""

    def test_basic_creation(self):
        # Given: required fields
        rec = ExecutionRecord(
            execution_id="exec-1",
            correlation_id="corr-1",
            user_id="u1",
            tenant_id="t1",
            project_id=None,
            conversation_id=None,
            capability="chat",
        )

        # Then: required fields set, defaults applied
        assert rec.execution_id == "exec-1"
        assert rec.correlation_id == "corr-1"
        assert rec.user_id == "u1"
        assert rec.tenant_id == "t1"
        assert rec.project_id is None
        assert rec.conversation_id is None
        assert rec.capability == "chat"
        assert rec.status == "started"  # default
        assert rec.evidence == []  # default
        assert rec.envelope is None  # default

    def test_creation_with_all_fields(self):
        rec = ExecutionRecord(
            execution_id="exec-2",
            correlation_id="corr-2",
            user_id="u2",
            tenant_id="t2",
            project_id="proj",
            conversation_id="conv",
            capability="code_edit",
            status="completed",
            evidence=[{"step": 1}],
            envelope=ExecutionEnvelope(
                execution_id="exec-2",
                actor_id="u2",
                tenant_id="t2",
                intent="code_edit_request",
                status="completed",
            ),
        )
        assert rec.status == "completed"
        assert rec.evidence == [{"step": 1}]
        assert rec.envelope is not None
        assert rec.envelope.actor_id == "u2"
        assert rec.envelope.intent == "code_edit_request"

    def test_evidence_default_is_independent_per_instance(self):
        rec1 = ExecutionRecord(
            execution_id="1",
            correlation_id="1",
            user_id="u",
            tenant_id="t",
            project_id=None,
            conversation_id=None,
            capability="c",
        )
        rec2 = ExecutionRecord(
            execution_id="2",
            correlation_id="2",
            user_id="u",
            tenant_id="t",
            project_id=None,
            conversation_id=None,
            capability="c",
        )
        rec1.evidence.append({"step": 1})
        assert rec2.evidence == []

    def test_mutable_dataclass_can_be_modified(self):
        """বাংলা: ConversationCommand frozen কিন্তু ExecutionRecord mutable।"""
        rec = ExecutionRecord(
            execution_id="exec",
            correlation_id="c",
            user_id="u",
            tenant_id="t",
            project_id=None,
            conversation_id=None,
            capability="cap",
        )
        rec.status = "completed"
        rec.evidence.append({"result": "ok"})
        assert rec.status == "completed"
        assert rec.evidence == [{"result": "ok"}]


class TestOrchestrationResult:
    """OrchestrationResult — একটি dispatch-এর চূড়ান্ত ফলাফল।"""

    def test_minimal_creation(self):
        # Given: only required fields
        result = OrchestrationResult(
            correlation_id="corr-1",
            status="success",
            capability="chat",
        )

        # Then: required fields set, defaults applied
        assert result.correlation_id == "corr-1"
        assert result.status == "success"
        assert result.capability == "chat"
        assert result.response is None
        assert result.requires_confirmation is False
        assert result.task_id is None
        assert result.error is None
        assert result.events == []
        assert result.execution is None

    def test_creation_with_error(self):
        # Sad path: an errored result
        result = OrchestrationResult(
            correlation_id="c",
            status="error",
            capability="chat",
            error="LLM provider timeout",
        )
        assert result.status == "error"
        assert result.error == "LLM provider timeout"
        assert result.response is None

    def test_creation_with_confirmation_required(self):
        result = OrchestrationResult(
            correlation_id="c",
            status="pending_confirmation",
            capability="destructive_op",
            requires_confirmation=True,
        )
        assert result.requires_confirmation is True

    def test_mutable_modification(self):
        result = OrchestrationResult(correlation_id="c", status="started", capability="chat")
        result.status = "completed"
        result.events.append({"event": "token", "value": "hi"})
        assert result.status == "completed"
        assert len(result.events) == 1


class TestCapability:
    """Capability — একটি registered handler ও তার risk profile।"""

    @staticmethod
    async def _dummy_handler(cmd: ConversationCommand) -> Any:
        return {"handled": True}

    def test_basic_creation(self):
        # Given: a registered capability
        cap = Capability(
            name="chat",
            risk="low",
            handler=self._dummy_handler,
        )

        # Then: required fields set, defaults applied
        assert cap.name == "chat"
        assert cap.risk == "low"
        assert cap.admin_only is False
        assert cap.destructive is False
        assert cap.availability == "connected"
        assert cap.description == ""
        assert callable(cap.handler)

    def test_is_available_true_when_connected(self):
        cap = Capability(name="x", risk="low", handler=self._dummy_handler)
        assert cap.is_available is True

    def test_is_available_false_when_disconnected(self):
        """বাংলা: availability != 'connected' হলে is_available False।"""
        cap = Capability(
            name="x",
            risk="low",
            handler=self._dummy_handler,
            availability="disconnected",
        )
        assert cap.is_available is False

    def test_is_available_false_when_degraded(self):
        cap = Capability(
            name="x",
            risk="low",
            handler=self._dummy_handler,
            availability="degraded",
        )
        assert cap.is_available is False

    def test_frozen_dataclass_immutable(self):
        cap = Capability(name="x", risk="low", handler=self._dummy_handler)
        with pytest.raises(AttributeError):
            cap.name = "modified"

    @pytest.mark.asyncio
    async def test_handler_can_be_called(self):
        """বাংলা: registered handler সত্যিই await করা যায় ও সে একটি result return করে।"""

        # Given: a capability with a handler
        async def my_handler(cmd: ConversationCommand) -> dict[str, Any]:
            return {"echo": cmd.prompt}

        cap = Capability(name="echo", risk="low", handler=my_handler)

        # When: calling the handler with a command
        cmd = ConversationCommand(prompt="hi", user_id="u", tenant_id="t")
        result = await cap.handler(cmd)

        # Then: handler returns expected result
        assert result == {"echo": "hi"}

    def test_destructive_capability_flag(self):
        """বাংলা: destructive capability flag সঠিকভাবে set হয়।"""
        cap = Capability(
            name="delete_file",
            risk="high",
            handler=self._dummy_handler,
            destructive=True,
        )
        assert cap.destructive is True

    def test_admin_only_flag(self):
        cap = Capability(
            name="admin_op",
            risk="high",
            handler=self._dummy_handler,
            admin_only=True,
        )
        assert cap.admin_only is True
