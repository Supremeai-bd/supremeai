import pytest
from unittest.mock import patch, MagicMock
from core.upstash_redis_queue import UpstashRedisQueue

def test_upstash_redis_not_configured():
    # If rest_url or token are missing, configured is False
    queue = UpstashRedisQueue(rest_url=None, token=None)
    assert not queue.configured
    assert queue.get("key") is None
    assert not queue.set("key", "val")
    assert queue.incr("key") is None
    assert queue.decr("key") is None

def test_upstash_redis_configured_success():
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock successful JSON response
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "val"}
        mock_client.post.return_value = mock_response
        
        queue = UpstashRedisQueue(rest_url="http://localhost:8079", token="my-token")
        assert queue.configured
        
        # Test get
        val = queue.get("my-key")
        assert val == "val"
        mock_client.post.assert_called_with(
            "http://localhost:8079",
            headers={"Authorization": "Bearer my-token"},
            json=["GET", "my-key"]
        )

def test_upstash_redis_set_success():
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_client.post.return_value = mock_response
        
        queue = UpstashRedisQueue(rest_url="http://localhost:8079", token="my-token")
        
        assert queue.set("my-key", "my-val", ex=3600)
        mock_client.post.assert_called_with(
            "http://localhost:8079",
            headers={"Authorization": "Bearer my-token"},
            json=["SET", "my-key", "my-val", "EX", 3600]
        )

def test_upstash_redis_incr_decr():
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "5"}
        mock_client.post.return_value = mock_response
        
        queue = UpstashRedisQueue(rest_url="http://localhost:8079", token="my-token")
        
        assert queue.incr("counter") == 5
        assert queue.decr("counter") == 5
        
        # Test close
        queue.close()
        assert not queue.configured
        mock_client.close.assert_called_once()
