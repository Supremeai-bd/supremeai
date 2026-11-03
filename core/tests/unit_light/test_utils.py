import asyncio
import importlib
from datetime import UTC, datetime, timezone

import pytest

from core.utils.background_tasks import track_task
from core.utils.lazy_loader import lazy_import
from core.utils.time_utils import ensure_aware, utc_expiry, utc_now


def test_utc_now_is_timezone_aware():
    assert utc_now().tzinfo is not None


def test_utc_expiry_is_in_the_future():
    future = utc_expiry(minutes=5)
    assert future > utc_now()


def test_utc_expiry_zero_equals_now():
    assert abs((utc_expiry() - utc_now()).total_seconds()) < 1


def test_ensure_aware_wraps_naive_datetime():
    naive = datetime(2020, 1, 1, 12, 0, 0)
    aware = ensure_aware(naive)
    assert aware.tzinfo is not None


def test_ensure_aware_passes_through_aware_datetime():
    aware = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert ensure_aware(aware) is aware


def test_lazy_import_succeeds_for_builtin():
    import json

    assert lazy_import("json") is json


def test_lazy_import_raises_runtime_error_on_missing():
    with pytest.raises(RuntimeError):
        lazy_import("definitely_not_a_real_module_xyz_123")


@pytest.mark.asyncio
async def test_track_task_returns_task_and_runs():
    async def coro():
        return 42

    task = track_task(asyncio.create_task(coro()))
    assert isinstance(task, asyncio.Task)
    assert await task == 42


@pytest.mark.asyncio
async def test_safe_create_task_and_error_logging(caplog):
    import logging

    from core.utils.background_tasks import safe_create_task

    async def faulty_coro():
        raise ValueError("simulated background error")

    with caplog.at_level(logging.ERROR):
        task = safe_create_task(faulty_coro(), name="test_faulty")
        with pytest.raises(ValueError):
            await task

    assert any("simulated background error" in record.message for record in caplog.records)
