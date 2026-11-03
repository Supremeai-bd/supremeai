# বাংলা মন্তব্য: tests/core/test_task_queue.py
# ============================================================
# Issue: core/queue/task_queue.py ছিল critical tier-এ untested (0%)।
# RedisTaskQueue — Upstash free-tier quota-safe distributed task queue।
#
# AGENTS.md rules followed:
#   - Rule #61: happy + sad paths (enqueue success + redis-unavailable fallback)
#   - Rule #63: critical-tier (core/queue/**) coverage 100%
#   - Rule #64: mock external API — Redis fully mocked, no real Upstash calls
#   - Rule #66: boundary tests (placeholder URL, missing redis, empty payload)
#   - Rule #67: Given-When-Then structure
# ============================================================

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.queue.task_queue import _PLACEHOLDER_TOKENS, RedisTaskQueue, redis_configured


class TestRedisConfigured:
    """redis_configured() — Upstash free-tier quota protection guard (R2-03)।"""

    def test_returns_false_when_no_redis_url(self, monkeypatch):
        """বাংলা: REDIS_URL env না থাকলে False (worker loop চলবে না)।"""
        # Given: no REDIS_URL env + settings.redis_url = None
        monkeypatch.delenv("REDIS_URL", raising=False)
        with patch("core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            # When
            result = redis_configured()
        # Then
        assert result is False

    def test_returns_false_for_empty_redis_url(self, monkeypatch):
        # Given
        monkeypatch.setenv("REDIS_URL", "")
        with patch("core.config.settings") as mock_settings:
            mock_settings.redis_url = ""
            # When
            result = redis_configured()
        # Then
        assert result is False

    @pytest.mark.parametrize("placeholder", _PLACEHOLDER_TOKENS)
    def test_returns_false_for_placeholder_tokens(self, monkeypatch, placeholder):
        """বাংলা: placeholder URL token থাকলে False (quota burn prevention)।"""
        # Given: a URL containing a placeholder token
        monkeypatch.setenv("REDIS_URL", f"redis://{placeholder}.example.com:6379")
        # When
        result = redis_configured()
        # Then
        assert result is False

    def test_returns_true_for_real_redis_url(self, monkeypatch):
        # Given: a real-looking Redis URL
        monkeypatch.setenv("REDIS_URL", "redis://default:password@real-redis.upstash.io:6379")
        # When
        result = redis_configured()
        # Then
        assert result is True

    def test_returns_true_for_localhost_real(self, monkeypatch):
        # Given: localhost (not the placeholder variant)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        # When
        result = redis_configured()
        # Then
        assert result is True


class TestRedisTaskQueueEnqueue:
    """RedisTaskQueue.enqueue() — task submission + queue push।"""

    @pytest.mark.asyncio
    async def test_enqueue_returns_uuid_when_redis_not_configured(self, monkeypatch):
        """বাংলা: Redis না থাকলে enqueue একটি random uuid return করে (fail-soft)।"""
        # Given: no Redis configured
        monkeypatch.delenv("REDIS_URL", raising=False)
        with patch("core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            queue = RedisTaskQueue(queue_name="test-q")

            # When
            task_id = await queue.enqueue("email_send", {"to": "u@x.com"}, "user-1")

        # Then: returns a UUID-shaped string, no crash
        assert isinstance(task_id, str)
        assert len(task_id) >= 32  # UUID4 length

    @pytest.mark.asyncio
    async def test_enqueue_pushes_to_redis_when_configured(self, monkeypatch):
        """বাংলা: Redis configured থাকলে rpush + set হয়, task_id return হয়।"""
        # Given: real Redis URL + mocked redis client
        monkeypatch.setenv("REDIS_URL", "redis://real-redis.upstash.io:6379")
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock(return_value=1)
        mock_redis.set = AsyncMock(return_value=True)

        queue = RedisTaskQueue(queue_name="test-q")
        # Bypass _get_redis real connection
        queue.redis = mock_redis

        # Mock redis_configured to return True (skip the env check)
        with (
            patch("core.queue.task_queue.redis_configured", return_value=True),
            patch.object(queue, "ensure_worker_started"),
        ):
            # When
            task_id = await queue.enqueue("email_send", {"to": "u@x.com"}, "user-1")

        # Then: rpush called with queue_name + JSON task_data
        assert mock_redis.rpush.called
        call_args = mock_redis.rpush.call_args
        assert call_args.args[0] == "test-q"
        pushed_data = json.loads(call_args.args[1])
        assert pushed_data["task_type"] == "email_send"
        assert pushed_data["user_id"] == "user-1"
        assert pushed_data["status"] == "pending"
        assert pushed_data["task_id"] == task_id

        # And: set called with task:<id> key + 86400 expiry
        assert mock_redis.set.called
        set_args = mock_redis.set.call_args
        assert set_args.args[0] == f"task:{task_id}"
        assert set_args.kwargs.get("ex") == 86400

    @pytest.mark.asyncio
    async def test_enqueue_task_id_is_unique_per_call(self, monkeypatch):
        """বাংলা: প্রতিটি enqueue call আলাদা task_id দেয় (uuid4)।"""
        # Given
        monkeypatch.setenv("REDIS_URL", "redis://real-redis.upstash.io:6379")
        mock_redis = AsyncMock()
        queue = RedisTaskQueue()
        queue.redis = mock_redis

        with (
            patch("core.queue.task_queue.redis_configured", return_value=True),
            patch.object(queue, "ensure_worker_started"),
        ):
            # When: two enqueues with same payload
            id1 = await queue.enqueue("t", {}, "u")
            id2 = await queue.enqueue("t", {}, "u")

        # Then: different IDs
        assert id1 != id2


class TestRedisTaskQueueHandler:
    """RedisTaskQueue.register_handler() — handler registration।"""

    def test_register_handler_stores_callable(self):
        # Given: a queue + a handler function
        queue = RedisTaskQueue()

        async def my_handler(task_data: dict):
            return {"done": True}

        # When
        queue.register_handler("my_type", my_handler)

        # Then: handler stored in _handlers dict
        assert "my_type" in queue._handlers
        assert queue._handlers["my_type"] is my_handler

    def test_register_handler_overwrites_existing(self):
        # Given
        queue = RedisTaskQueue()

        async def handler_v1(task_data: dict):
            return {"v": 1}

        async def handler_v2(task_data: dict):
            return {"v": 2}

        # When: register v1, then overwrite with v2
        queue.register_handler("type_x", handler_v1)
        queue.register_handler("type_x", handler_v2)

        # Then: v2 wins
        assert queue._handlers["type_x"] is handler_v2


class TestRedisTaskQueueEnsureWorker:
    """RedisTaskQueue.ensure_worker_started() — lazy worker startup (R2-03)।"""

    def test_ensure_worker_noop_when_redis_not_configured(self, monkeypatch):
        """বাংলা: Redis না থাকলে worker শুরু হয় না (quota protection)।"""
        # Given: no Redis
        monkeypatch.delenv("REDIS_URL", raising=False)
        with patch("core.config.settings") as mock_settings:
            mock_settings.redis_url = None
            queue = RedisTaskQueue()

            # When
            queue.ensure_worker_started()

        # Then: _worker_task remains None
        assert queue._worker_task is None

    def test_ensure_worker_noop_when_already_running(self):
        """বাংলা: worker ইতিমধ্যে চলছে থাকলে আবার শুরু হয় না (idempotent)।"""
        # Given: a queue with a mock running task
        queue = RedisTaskQueue()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        queue._worker_task = mock_task

        with patch("core.queue.task_queue.redis_configured", return_value=True):
            # When
            queue.ensure_worker_started()

        # Then: _worker_task unchanged (not replaced)
        assert queue._worker_task is mock_task

    @pytest.mark.asyncio
    async def test_ensure_worker_starts_when_redis_configured_and_no_loop(self):
        """বাংলা: Redis configured + কোনো running worker না থাকলে নতুন worker তৈরি।"""
        # Given: Redis configured + the pytest-asyncio running loop
        queue = RedisTaskQueue()
        with patch("core.queue.task_queue.redis_configured", return_value=True):
            # When
            queue.ensure_worker_started()
            # Then: worker task created
            assert queue._worker_task is not None
            # Cleanup
            if not queue._worker_task.done():
                queue._worker_task.cancel()
                try:
                    await asyncio.wait_for(queue._worker_task, timeout=0.1)
                except (asyncio.CancelledError, TimeoutError):
                    pass


class TestRedisTaskQueueProcessTask:
    """RedisTaskQueue._process_task() — task execution + status tracking।"""

    @pytest.mark.asyncio
    async def test_process_task_with_no_handler_marks_failed(self):
        """বাংলা: handler না থাকলে task 'failed' status-এ যায় (No handler error)।"""
        # Given: a task_data for an unregistered task_type
        queue = RedisTaskQueue()
        task_data = {
            "task_id": "tid-1",
            "task_type": "unknown_type",
            "user_id": "u1",
            "payload": {},
            "status": "pending",
        }
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        queue.redis = mock_redis

        # When
        await queue._process_task(task_data)

        # Then: status set to 'failed' with error='No handler'
        set_call = mock_redis.set.call_args
        stored = json.loads(set_call.args[1])
        assert stored["status"] == "failed"
        assert stored["error"] == "No handler"

    @pytest.mark.asyncio
    async def test_process_task_calls_registered_handler(self):
        """বাংলা: registered handler সত্যিই কল হয় + status 'completed' হয়।"""
        # Given
        queue = RedisTaskQueue()
        handler_called_with = None

        async def my_handler(task_data: dict):
            nonlocal handler_called_with
            handler_called_with = task_data
            return {"result": "success"}

        queue.register_handler("compute", my_handler)

        task_data = {
            "task_id": "tid-2",
            "task_type": "compute",
            "user_id": "u2",
            "payload": {"x": 42},
            "status": "pending",
        }
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        queue.redis = mock_redis

        # When
        await queue._process_task(task_data)

        # Then: handler called with the task_data
        assert handler_called_with is not None
        assert handler_called_with["task_id"] == "tid-2"

        # And: final status set to 'completed' with result
        last_set = mock_redis.set.call_args_list[-1]
        stored = json.loads(last_set.args[1])
        assert stored["status"] == "completed"
        assert stored["result"] == {"result": "success"}

    @pytest.mark.asyncio
    async def test_process_task_handler_exception_marks_failed(self):
        """বাংলা: handler exception হলে task 'failed' + error message stored।"""
        # Given: a handler that raises
        queue = RedisTaskQueue()

        async def failing_handler(task_data: dict):
            raise ValueError("handler exploded")

        queue.register_handler("boom", failing_handler)

        task_data = {
            "task_id": "tid-3",
            "task_type": "boom",
            "user_id": "u3",
            "payload": {},
            "status": "pending",
        }
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        queue.redis = mock_redis

        # When
        await queue._process_task(task_data)

        # Then: final status 'failed' with the exception message
        last_set = mock_redis.set.call_args_list[-1]
        stored = json.loads(last_set.args[1])
        assert stored["status"] == "failed"
        assert "handler exploded" in stored["error"]

    @pytest.mark.asyncio
    async def test_process_task_sets_processing_status_before_handler(self):
        """বাংলা: handler কল করার আগে status 'processing' set হয় (visibility)।"""
        # Given
        queue = RedisTaskQueue()
        statuses_seen = []

        async def tracking_handler(task_data: dict):
            statuses_seen.append(task_data.get("status"))
            return "ok"

        queue.register_handler("tracked", tracking_handler)

        task_data = {
            "task_id": "tid-4",
            "task_type": "tracked",
            "user_id": "u",
            "payload": {},
            "status": "pending",
        }
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()
        queue.redis = mock_redis

        # When
        await queue._process_task(task_data)

        # Then: handler saw status='processing' (set before handler call)
        assert "processing" in statuses_seen


class TestRedisTaskQueueConfig:
    """RedisTaskQueue class-level config + constants।"""

    def test_default_queue_name(self):
        # Given/When
        queue = RedisTaskQueue()
        # Then: default name is "supreme_task_queue"
        assert queue.queue_name == "supreme_task_queue"

    def test_custom_queue_name(self):
        # Given/When
        queue = RedisTaskQueue(queue_name="custom-q")
        # Then
        assert queue.queue_name == "custom-q"

    def test_idle_shutdown_constant(self):
        # Boundary: IDLE_SHUTDOWN_SECONDS must be 300 (5 min — quota-safe)
        assert RedisTaskQueue.IDLE_SHUTDOWN_SECONDS == 300

    def test_max_blpop_timeout_constant(self):
        # Boundary: MAX_BLPOP_TIMEOUT must be 30 (Upstash blocking cmd ceiling)
        assert RedisTaskQueue.MAX_BLPOP_TIMEOUT == 30

    def test_handlers_dict_starts_empty(self):
        queue = RedisTaskQueue()
        assert queue._handlers == {}

    def test_worker_task_starts_none(self):
        queue = RedisTaskQueue()
        assert queue._worker_task is None

    def test_redis_starts_none(self):
        queue = RedisTaskQueue()
        assert queue.redis is None


class TestTaskQueueSingleton:
    """Module-level `task_queue` singleton instance।"""

    def test_singleton_exists(self):
        # Given/When: import the singleton
        from core.queue.task_queue import task_queue

        # Then: it's a RedisTaskQueue instance
        assert isinstance(task_queue, RedisTaskQueue)

    def test_singleton_uses_default_queue_name(self):
        from core.queue.task_queue import task_queue

        assert task_queue.queue_name == "supreme_task_queue"
