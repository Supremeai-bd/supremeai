from __future__ import annotations

import uuid

import pytest

from backend.ecosystem.federation_bridge import observe_browser_run, observe_remediation_run


class FakeRunService:
    def __init__(self):
        self.calls = []

    async def create_run(self, session, **kwargs):
        self.calls.append(kwargs)
        return kwargs


@pytest.mark.asyncio
async def test_browser_execution_is_observed_before_dispatch():
    service = FakeRunService()
    result = await observe_browser_run(
        object(), service, user_id="u1", url="https://example.com", action="screenshot"
    )
    assert result["run_type"] == "browser"
    assert result["source_type"] == "browser"
    assert result["title"] == "browser:screenshot"
    assert uuid.UUID(result["idempotency_key"])


@pytest.mark.asyncio
async def test_remediation_is_governed_by_canonical_run():
    service = FakeRunService()
    result = await observe_remediation_run(
        object(), service, user_id="u1", fix_id="fix-1", tenant_id="tenant-1", impact_score=0.7
    )
    assert (
        result["run_type"] == "agent"
    )  # M06 ফিক্স: "remediation" ছিল অবৈধ RunType (latent ValueError)
    assert result["source_type"] == "self_healing"
    assert result["source_ref"] == "fix-1"
    assert result["correlation_id"] == "tenant-1"
