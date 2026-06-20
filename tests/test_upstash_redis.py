from unittest.mock import MagicMock, patch
from core.upstash_redis_queue import UpstashRedisQueue


def _make_client():
    queue = UpstashRedisQueue.__new__(UpstashRedisQueue)
    queue.rest_url = 'http://localhost:8000'
    queue.token = 'test-token'
    queue.timeout = 5.0
    queue._client = MagicMock()
    return queue


def test_configured_true():
    queue = _make_client()
    assert queue.configured is True


def test_get_returns_result():
    queue = _make_client()
    queue._client.post.return_value.json.return_value = {'result': 'value'}
    assert queue.get('key') == 'value'
    queue._client.post.assert_called_once()


def test_set_returns_true():
    queue = _make_client()
    queue._client.post.return_value.json.return_value = {'result': 'OK'}
    assert queue.set('key', 'value') is True
    queue._client.post.assert_called_once()


def test_incr_returns_int():
    queue = _make_client()
    queue._client.post.return_value.json.return_value = {'result': '5'}
    assert queue.incr('counter') == 5


def test_decr_returns_int():
    queue = _make_client()
    queue._client.post.return_value.json.return_value = {'result': '3'}
    assert queue.decr('counter') == 3


def test_not_configured_returns_none():
    queue = UpstashRedisQueue.__new__(UpstashRedisQueue)
    queue.rest_url = ''
    queue.token = ''
    queue.timeout = 5.0
    queue._client = None
    assert queue.configured is False
    assert queue.get('key') is None
    assert queue.set('key', 'value') is False
    assert queue.incr('key') is None
    assert queue.decr('key') is None
