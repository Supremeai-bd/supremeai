from core.execution_adapters import (
    AdapterKind,
    ExecutionRequest,
    build_execution_plan,
    fallback_plan,
)
from core.execution_policy import ExecutionMode, ProviderBudget, TaskClass


def test_cache_wins_without_provider_usage():
    request = ExecutionRequest(
        task_id="job-1",
        tenant_id="tenant-a",
        task_class=TaskClass.LIGHTWEIGHT,
        payload={"prompt": "hello"},
        cache_hit=True,
    )

    plan = build_execution_plan(request)

    assert plan.mode == ExecutionMode.CACHE
    assert plan.adapter is None
    assert plan.tenant_id == "tenant-a"


def test_client_capability_is_preferred_for_local_safe_work():
    request = ExecutionRequest(
        task_id="job-2",
        tenant_id="tenant-a",
        task_class=TaskClass.LOCAL_SAFE,
        payload={},
        client_capabilities=(TaskClass.LOCAL_SAFE.value,),
    )

    plan = build_execution_plan(request)

    assert plan.mode == ExecutionMode.CLIENT
    assert plan.adapter == AdapterKind.CLIENT
    assert plan.capability == TaskClass.LOCAL_SAFE.value


def test_failed_provider_is_removed_before_replanning():
    providers = (
        ProviderBudget(name="primary", remaining_ratio=0.9, healthy=True),
        ProviderBudget(name="fallback", remaining_ratio=0.8, healthy=True),
    )
    request = ExecutionRequest(
        task_id="job-3",
        tenant_id="tenant-a",
        task_class=TaskClass.LIGHTWEIGHT,
        payload={},
    )

    plan = fallback_plan(request, "primary", providers=providers)

    assert plan.provider != "primary"


def test_request_rejects_missing_tenant():
    try:
        ExecutionRequest(
            task_id="job-4",
            tenant_id="",
            task_class=TaskClass.LIGHTWEIGHT,
            payload={},
        )
    except ValueError as exc:
        assert "tenant_id" in str(exc)
    else:
        raise AssertionError("missing tenant must be rejected")


def test_research_mode_is_degraded_and_explicit():
    request = ExecutionRequest(
        task_id="job-5",
        tenant_id="tenant-a",
        task_class=TaskClass.RESEARCH,
        payload={},
    )

    plan = build_execution_plan(request)

    assert plan.mode == ExecutionMode.RESEARCH
    assert plan.adapter == AdapterKind.RESEARCH
    assert plan.degraded is True
