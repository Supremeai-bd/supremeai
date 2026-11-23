"""Worker service idempotency claim-path tests.

বাংলা: worker_service-এর idempotency ক্লেইম পথগুলোর ইউনিট টেস্ট —
প্রথম সাবমিট, একই payload-এ ডুপ্লিকেট, এবং ভিন্ন payload-এ 409 কনফ্লিক্ট।
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from core.worker_service import TaskContract, _claim_idempotency, _store_idempotency_task


def _contract(**overrides: object) -> TaskContract:
    payload: dict[str, object] = {
        "tenant_id": "tenant-1",
        "goal": "do the thing",
        "idempotency_key": "key-1",
    }
    payload.update(overrides)
    return TaskContract.model_validate(payload)


@pytest.fixture(autouse=True)
def _memory_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    """বাংলা: টেস্টে সবসময় মেমরি-পথ ব্যবহার — durable DB লেজি ইমপোর্ট এড়াতে।"""
    import core.worker_service as ws

    monkeypatch.setattr(ws, "_use_durable_idempotency", lambda: False)
    ws._idempotency_records.clear()


@pytest.mark.anyio
async def test_first_submit_returns_no_existing_task() -> None:
    fingerprint, existing = await _claim_idempotency(_contract())
    assert existing is None
    assert fingerprint


@pytest.mark.anyio
async def test_duplicate_same_payload_deduplicates() -> None:
    request = _contract()
    fingerprint, _ = await _claim_idempotency(request)
    await _store_idempotency_task(request, "task-abc")

    # বাংলা: execution_id প্রতি validation-এ নতুন হয়, তাই একই request অবজেক্ট
    # পুনঃব্যবহার করলেই একই payload-এর সৎ প্রতিনিধিত্ব হয়।
    fp2, existing = await _claim_idempotency(request)
    assert existing == "task-abc"
    assert fp2 == fingerprint


@pytest.mark.anyio
async def test_duplicate_different_payload_conflicts_409() -> None:
    request = _contract()
    _, _ = await _claim_idempotency(request)
    await _store_idempotency_task(request, "task-abc")

    with pytest.raises(HTTPException) as excinfo:
        await _claim_idempotency(_contract(goal="a totally different goal"))
    assert excinfo.value.status_code == 409


@pytest.mark.anyio
async def test_pending_duplicate_conflicts_409() -> None:
    """বাংলা: স্টোর হওয়ার আগেই (pending) দ্বিতীয় কল 409 পাবে।"""
    request = _contract()
    await _claim_idempotency(request)

    with pytest.raises(HTTPException) as excinfo:
        await _claim_idempotency(_contract())
    assert excinfo.value.status_code == 409


@pytest.mark.anyio
async def test_no_key_bypasses_idempotency() -> None:
    fingerprint, existing = await _claim_idempotency(
        _contract(idempotency_key=None)
    )
    assert existing is None
    assert fingerprint
