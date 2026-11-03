# backend/tests/evolution/test_canary_and_evolution_bridge.py
"""Tests for EvolutionBridge and CanaryRolloutController."""

import pytest

from evolution.canary_manager import CanaryRolloutController
from evolution.change_proposal import ChangeProposalManager, ChangeType, ProposalState
from learning.evolution_bridge import get_evolution_bridge
from learning.experience import ExperienceRecord


def test_evolution_bridge_synthesizes_proposal_on_syntax_error():
    bridge = get_evolution_bridge()

    syntax_record = ExperienceRecord(
        task_id="task_syntax_err_99",
        goal="Generate Python class",
        verified=False,
        verification_score=0.3,
        failures=["Python Syntax Error: invalid syntax at line 2"],
    )

    proposal = bridge.process_experience_and_propose(syntax_record)

    assert proposal is not None
    assert proposal.change_type == ChangeType.PROMPT_OPTIMIZATION
    assert "task_syntax_err_99" in proposal.title
    assert proposal.state == ProposalState.DRAFTED


def test_canary_controller_rollout_and_promotion():
    proposal_mgr = ChangeProposalManager()
    canary_ctrl = CanaryRolloutController(proposal_manager=proposal_mgr)

    proposal = proposal_mgr.create_proposal(
        title="Cache hit rate enhancement",
        description="Tune TTL",
        change_type=ChangeType.PARAMETER_TUNING,
        diff_content={"ttl": 600},
        target_module="backend/core/cache.py",
        current_fitness=0.80,
    )

    # 1. Deploy canary
    deployed = canary_ctrl.deploy_canary(proposal.proposal_id, sample_ratio=0.20)
    assert deployed is True
    assert proposal.state == ProposalState.CANARY_ACTIVE

    # 2. Record 5 successful trials
    for _ in range(5):
        canary_ctrl.record_observation(proposal.proposal_id, success=True, latency_ms=50.0)

    # 3. Evaluate and promote
    promoted = canary_ctrl.evaluate_and_promote(
        proposal.proposal_id, min_trials=5, min_success_rate=0.80
    )
    assert promoted is True
    assert proposal.state == ProposalState.PROMOTED


def test_canary_controller_auto_rollback_on_regression():
    proposal_mgr = ChangeProposalManager()
    canary_ctrl = CanaryRolloutController(proposal_manager=proposal_mgr)

    proposal = proposal_mgr.create_proposal(
        title="Bad regression patch",
        description="Causes 500s",
        change_type=ChangeType.CODE_REFACTOR,
        diff_content={"bad_patch": True},
        target_module="backend/core/router.py",
        current_fitness=0.85,
    )

    canary_ctrl.deploy_canary(proposal.proposal_id)

    # 3 failed trials in a row should trigger auto rollback
    canary_ctrl.record_observation(proposal.proposal_id, success=False)
    canary_ctrl.record_observation(proposal.proposal_id, success=False)
    canary_ctrl.record_observation(proposal.proposal_id, success=False)

    assert proposal.state == ProposalState.ROLLED_BACK
    assert "High failure rate" in (proposal.rejection_reason or "")


def test_canary_traffic_splitting_and_stickiness():
    proposal_mgr = ChangeProposalManager()
    canary_ctrl = CanaryRolloutController(proposal_manager=proposal_mgr)

    proposal = proposal_mgr.create_proposal(
        title="Canary Traffic Test",
        description="Testing traffic split",
        change_type=ChangeType.PARAMETER_TUNING,
        diff_content={"ratio": 0.50},
        target_module="backend/core/router.py",
        current_fitness=0.85,
    )

    # Inactive proposal always routes to baseline (False)
    assert canary_ctrl.should_route(proposal.proposal_id, client_context="user_123") is False

    # Deploy canary with 50% ratio
    canary_ctrl.deploy_canary(proposal.proposal_id, sample_ratio=0.50)

    # Deterministic stickiness: same client always gets the exact same routing decision
    first_decision = canary_ctrl.should_route(proposal.proposal_id, client_context="user_alpha")
    second_decision = canary_ctrl.should_route(proposal.proposal_id, client_context="user_alpha")
    assert first_decision == second_decision

    # Force canary override
    assert (
        canary_ctrl.should_route(
            proposal.proposal_id, client_context="user_alpha", force_canary=True
        )
        is True
    )


def test_canary_header_overrides():
    proposal_mgr = ChangeProposalManager()
    canary_ctrl = CanaryRolloutController(proposal_manager=proposal_mgr)

    proposal = proposal_mgr.create_proposal(
        title="Header Test",
        description="Testing header overrides",
        change_type=ChangeType.PARAMETER_TUNING,
        diff_content={"test": True},
        target_module="backend/core/router.py",
        current_fitness=0.85,
    )
    canary_ctrl.deploy_canary(proposal.proposal_id, sample_ratio=0.10)

    # Header 'X-Canary: true' forces canary
    assert canary_ctrl.route_request(proposal.proposal_id, headers={"X-Canary": "true"}) is True

    # Header 'X-Canary: <proposal_id>' forces canary
    assert (
        canary_ctrl.route_request(proposal.proposal_id, headers={"X-Canary": proposal.proposal_id})
        is True
    )

    # Header 'X-Canary: false' forces baseline
    assert canary_ctrl.route_request(proposal.proposal_id, headers={"X-Canary": "false"}) is False

    # Client-ID header 'X-User-Id' gives consistent sticky result
    dec1 = canary_ctrl.route_request(proposal.proposal_id, headers={"X-User-Id": "usr_99"})
    dec2 = canary_ctrl.route_request(proposal.proposal_id, headers={"X-User-Id": "usr_99"})
    assert dec1 == dec2


@pytest.mark.asyncio
async def test_canary_route_endpoint():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from api.routes.evolution import router as evolution_router
    from evolution.canary_manager import get_canary_controller
    from evolution.change_proposal import ChangeType, get_change_manager

    controller = get_canary_controller()
    mgr = get_change_manager()
    prop = mgr.create_proposal(
        title="Endpoint Test",
        description="test",
        change_type=ChangeType.PARAMETER_TUNING,
        diff_content={},
        target_module="core",
    )
    controller.deploy_canary(prop.proposal_id, sample_ratio=0.10)

    app = FastAPI()
    app.include_router(evolution_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/evolution/canary/{prop.proposal_id}/route")
        assert res.status_code == 200
        data = res.json()
        assert data["proposal_id"] == prop.proposal_id
        assert data["active"] is True

        res_forced = await ac.get(
            f"/evolution/canary/{prop.proposal_id}/route",
            headers={"X-Canary": "true"},
        )
        assert res_forced.status_code == 200
        assert res_forced.json()["is_canary"] is True
