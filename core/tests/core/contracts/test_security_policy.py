from pathlib import Path

import pytest

from core.contracts.canonical import ApprovalRequest, ApprovalStatus, ExecutionContext
from core.contracts.security_policy import (
    Actor,
    CapabilityPolicy,
    PolicyDenied,
    authorize,
    validate_workspace_path,
)


def context(tenant="tenant-a", actor="actor-a", risk="high"):
    return ExecutionContext(
        tenant_id=tenant,
        actor_id=actor,
        workspace_id="w",
        correlation_id="c",
        idempotency_key="k",
        capability="deploy",
        risk_level=risk,
    )


def test_cross_tenant_and_forged_actor_are_denied():
    policy = CapabilityPolicy("deploy", frozenset({"admin"}))
    with pytest.raises(PolicyDenied):
        authorize(Actor("attacker", "tenant-b", frozenset({"admin"})), context(), policy)


def test_high_risk_requires_matching_approval():
    ctx = context()
    actor = Actor("actor-a", "tenant-a", frozenset({"admin"}))
    policy = CapabilityPolicy("deploy", frozenset({"admin"}))
    with pytest.raises(PolicyDenied):
        authorize(actor, ctx, policy)
    approval = ApprovalRequest("a", ctx, "deploy", ApprovalStatus.APPROVED)
    authorize(actor, ctx, policy, approval)


def test_workspace_path_cannot_escape_root(tmp_path: Path):
    assert validate_workspace_path(tmp_path, Path("nested/file.txt")).parent == tmp_path / "nested"
    with pytest.raises(PolicyDenied):
        validate_workspace_path(tmp_path, Path("../../etc/passwd"))
