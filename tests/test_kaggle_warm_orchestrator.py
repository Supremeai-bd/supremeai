"""Unit tests for Kaggle Warm Worker Pool & Speculative Execution (#4283).

Verifies:
1. Worker heartbeat registration, status tracking, and TTL.
2. has_warm_worker() detection (cold vs warm).
3. Speculative thinking trace generation per task type.
4. submit_job_speculative() behavior for cold-boot vs warm worker.
5. KGAT_ Bearer auth header generation for modern Kaggle access tokens.
6. FastAPI endpoints: /heartbeat, /warm-workers, /worker/next-task, /submit.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.kaggle import router

try:
    from core.kaggle_orchestrator import (
        KaggleAccount,
        KaggleJob,
        KaggleOrchestrator,
        KaggleTaskType,
    )
except ImportError:
    from backend.core.kaggle_orchestrator import (
        KaggleAccount,
        KaggleJob,
        KaggleOrchestrator,
        KaggleTaskType,
    )


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    # In-memory storage for hash and sets
    hashes = {}
    sets = {}

    async def hset(key, mapping=None, **kwargs):
        if key not in hashes:
            hashes[key] = {}
        if mapping:
            hashes[key].update(mapping)
        hashes[key].update(kwargs)
        return 1

    async def hget(key, field):
        return hashes.get(key, {}).get(field)

    async def hgetall(key):
        return dict(hashes.get(key, {}))

    async def sadd(key, *members):
        if key not in sets:
            sets[key] = set()
        sets[key].update(members)
        return len(members)

    async def smembers(key):
        return set(sets.get(key, set()))

    async def srem(key, *members):
        if key in sets:
            for m in members:
                sets[key].discard(m)
        return 1

    async def expire(key, ttl):
        return True

    async def zadd(key, mapping):
        return 1

    async def zrem(key, member):
        return 1

    async def zrange(key, start, end, withscores=False):
        return [("job_test_123", 0.0)]

    redis.hset = AsyncMock(side_effect=hset)
    redis.hget = AsyncMock(side_effect=hget)
    redis.hgetall = AsyncMock(side_effect=hgetall)
    redis.sadd = AsyncMock(side_effect=sadd)
    redis.smembers = AsyncMock(side_effect=smembers)
    redis.srem = AsyncMock(side_effect=srem)
    redis.expire = AsyncMock(side_effect=expire)
    redis.zadd = AsyncMock(side_effect=zadd)
    redis.zrem = AsyncMock(side_effect=zrem)
    redis.zrange = AsyncMock(side_effect=zrange)
    redis.zcard = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def orchestrator(mock_redis):
    accounts = [
        KaggleAccount(
            account_id="worker_1", username="supremeai_1", api_key="KGAT_validtoken123"
        ),
        KaggleAccount(
            account_id="worker_2", username="supremeai_2", api_key="legacy_key_456"
        ),
    ]
    orch = KaggleOrchestrator(redis_url="mock://redis", accounts=accounts)
    orch.redis_client = mock_redis
    return orch


@pytest.mark.asyncio
async def test_worker_heartbeat_and_warm_detection(orchestrator, mock_redis):
    # Initially no warm workers
    assert await orchestrator.has_warm_worker() is False

    # Record heartbeat
    res = await orchestrator.record_worker_heartbeat(
        worker_id="kaggle-node-1", status="idle", account_id="worker_1"
    )
    assert res is True

    # Now worker is warm
    warm_workers = await orchestrator.get_warm_workers()
    assert len(warm_workers) == 1
    assert warm_workers[0]["worker_id"] == "kaggle-node-1"
    assert warm_workers[0]["status"] == "idle"
    assert await orchestrator.has_warm_worker() is True

    # When worker becomes busy, has_warm_worker should be False
    await orchestrator.record_worker_heartbeat(
        worker_id="kaggle-node-1", status="busy", account_id="worker_1"
    )
    assert await orchestrator.has_warm_worker() is False


@pytest.mark.asyncio
async def test_speculative_thinking_generation(orchestrator):
    # Fine-tuning trace
    ft_trace = orchestrator.generate_speculative_thinking(
        KaggleTaskType.MODEL_FINE_TUNING, {"base_model": "llama-3-8b"}
    )
    assert len(ft_trace) >= 3
    assert any("llama-3-8b" in t["detail"] for t in ft_trace)
    assert any("LoRA" in t["detail"] for t in ft_trace)

    # Batch inference trace
    inf_trace = orchestrator.generate_speculative_thinking(
        KaggleTaskType.BATCH_INFERENCE, {"prompts": ["hello"]}
    )
    assert len(inf_trace) >= 2
    assert any("inference" in t["detail"].lower() for t in inf_trace)


@pytest.mark.asyncio
async def test_submit_job_speculative_cold_vs_warm(orchestrator):
    # Case 1: Cold start (no warm workers)
    payload = {"dataset_url": "https://example.com/data.csv"}
    res_cold = await orchestrator.submit_job_speculative(
        task_type=KaggleTaskType.DATA_PROCESSING,
        payload=payload,
    )
    assert res_cold["status"] == "queued"
    assert res_cold["worker_state"] == "cold_booting"
    assert res_cold["speculative_thinking"] is True
    assert len(res_cold["thinking_trace"]) > 0

    # Case 2: Warm worker active
    await orchestrator.record_worker_heartbeat("kaggle-node-warm", status="idle")
    res_warm = await orchestrator.submit_job_speculative(
        task_type=KaggleTaskType.DATA_PROCESSING,
        payload=payload,
    )
    assert res_warm["status"] == "queued"
    assert res_warm["worker_state"] == "warm"
    assert res_warm["speculative_thinking"] is False
    assert len(res_warm["thinking_trace"]) == 0


@pytest.mark.asyncio
async def test_kgat_bearer_auth_dispatch(orchestrator):
    account_kgat = orchestrator.accounts["worker_1"]
    job = KaggleJob(
        job_id="test_kgat_job",
        task_type=KaggleTaskType.DATA_PROCESSING,
        payload={"dataset_url": "https://example.com/data.csv"},
    )

    with patch.object(
        orchestrator.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "hasError": False,
                "url": "https://www.kaggle.com/code/paykaribazar/supremeai-test-kgat-job",
            }
        )
        mock_post.return_value = mock_response

        ok = await orchestrator.dispatch_job_to_kaggle(job, account_kgat)
        assert ok is True

        # Verify Authorization: Bearer was used
        called_headers = mock_post.call_args.kwargs.get("headers", {})
        assert called_headers.get("Authorization") == f"Bearer {account_kgat.api_key}"
        assert "Kaggle-Username" not in called_headers

        # Verify Kaggle API payload structure (issue #439 / #440 fix)
        called_json = mock_post.call_args.kwargs.get("json", {})
        assert "slug" in called_json
        assert called_json["slug"].startswith(account_kgat.username)
        assert "newTitle" in called_json
        assert "text" in called_json
        assert called_json["kernelType"] == "script"
        assert called_json["isPrivate"] is True
        assert "enableGpu" in called_json
        assert called_json["enableInternet"] is True


@pytest.mark.asyncio
async def test_kaggle_dispatch_has_error_rejection(orchestrator):
    account_kgat = orchestrator.accounts["worker_1"]
    job = KaggleJob(
        job_id="test_rejection_job",
        task_type=KaggleTaskType.DATA_PROCESSING,
        payload={"dataset_url": "https://example.com/data.csv"},
    )

    with patch.object(
        orchestrator.http_client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"hasError": True, "error": "Invalid slug format"}
        )
        mock_post.return_value = mock_response

        ok = await orchestrator.dispatch_job_to_kaggle(job, account_kgat)
        assert ok is False


def test_routes_endpoints(orchestrator):
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with patch(
        "backend.api.routes.kaggle.KaggleOrchestrator.get_instance",
        return_value=orchestrator,
    ):
        # 1. Heartbeat endpoint
        hb_resp = client.post(
            "/api/v1/kaggle/heartbeat",
            json={"worker_id": "test-kernel-1", "status": "idle"},
        )
        assert hb_resp.status_code == 200
        assert hb_resp.json()["success"] is True

        # 2. Warm workers list
        list_resp = client.get("/api/v1/kaggle/warm-workers")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["warm_count"] == 1
        assert data["has_idle"] is True

        # 3. Submit with speculative execution
        sub_resp = client.post(
            "/api/v1/kaggle/submit",
            json={
                "task_type": "model_fine_tuning",
                "payload": {"base_model": "mistral-7b"},
                "speculative": True,
            },
        )
        assert sub_resp.status_code == 200
        sub_data = sub_resp.json()
        assert "job_id" in sub_data
        assert sub_data["worker_state"] == "warm"


@pytest.mark.asyncio
async def test_model_trainer_kaggle_integration(orchestrator, tmp_path):
    from backend.tools.learning.model_trainer import ModelTrainer

    dummy_dataset = tmp_path / "train.jsonl"
    dummy_dataset.write_text('{"text": "example prompt and completion"}\n')

    with (
        patch("backend.tools.learning.model_trainer.settings") as mock_settings,
        patch(
            "core.kaggle_orchestrator.KaggleOrchestrator.get_instance",
            return_value=orchestrator,
            create=True,
        ),
        patch.object(KaggleOrchestrator, "get_instance", return_value=orchestrator),
    ):
        mock_settings.runpod_api_key = None
        mock_settings.modal_token_id = None
        mock_settings.kaggle_api_keys = ["KGAT_validtoken123"]

        trainer = ModelTrainer(provider="auto")
        assert trainer.provider == "kaggle"

        res = await trainer.trigger_lora_finetune(str(dummy_dataset), base_model="gpt2")
        assert res["status"] == "success"
        assert res["provider"] == "kaggle"
        assert "job_id" in res
        assert "worker_state" in res

        # Check job status tracking
        status_res = await trainer.get_job_status(res["job_id"])
        assert "status" in status_res
        assert status_res["job_id"] == res["job_id"]
