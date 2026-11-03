# backend/tests/core/test_nats_messaging.py
# বাংলা মন্তব্য: NATSClient-এর জন্য comprehensive unit tests।
# NATS server mock করা হয়েছে — actual NATS dependency ছাড়াই।

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Handle missing nats module gracefully by patching core.messaging.nats_messaging.nats
from core.messaging import nats_messaging
from core.messaging.nats_messaging import NATSClient

# Ensure nats_messaging.nats is non-None and has an AsyncMock connect during tests
if nats_messaging.nats is None:
    mock_nats_mod = MagicMock()
    mock_nats_mod.connect = AsyncMock()
    nats_messaging.nats = mock_nats_mod
elif not hasattr(nats_messaging.nats, "connect") or not isinstance(
    nats_messaging.nats.connect, AsyncMock
):
    nats_messaging.nats.connect = AsyncMock()


# -------------------- Fixtures --------------------


@pytest.fixture
def nats_client():
    """NATSClient ইনস্ট্যান্স ফেরত দেয়।"""
    return NATSClient(url="nats://localhost:4222", token="test_token")


@pytest.fixture
def mock_nats_connection():
    """Mock NATS connection এবং JetStream context।"""
    mock_nc = AsyncMock()
    mock_js = AsyncMock()
    mock_nc.jetstream = MagicMock(return_value=mock_js)
    return mock_nc, mock_js


@pytest.fixture
def mock_kv_store():
    """Mock Key-Value store।"""
    kv = AsyncMock()
    kv.get.return_value = MagicMock(value=json.dumps({"status": "active"}).encode())
    kv.keys.return_value = ["worker1", "worker2"]
    return kv


# -------------------- Tests: __init__ --------------------


class TestNATSClientInit:
    """বাংলা মন্তব্য: Initialization টেস্ট।"""

    def test_default_initialization(self):
        with patch.dict("os.environ", {}, clear=True):
            client = NATSClient()
        assert client.url == "nats://localhost:4222"
        # বাংলা মন্তব্য: আগে এখানে হার্ডকোডেড "super_secret_token" ডিফল্ট ছিল
        # (security bug) — এখন NATS_TOKEN env var না থাকলে token None হয়।
        assert client.token is None
        assert client.nc is None
        assert client.js is None
        assert client.kv_store is None

    def test_custom_url_and_token(self):
        client = NATSClient(url="nats://custom:4222", token="custom_token")
        assert client.url == "nats://custom:4222"
        assert client.token == "custom_token"

    def test_none_token(self):
        client = NATSClient(token=None)
        assert client.token is None


# -------------------- Tests: connect --------------------


class TestConnect:
    """বাংলা মন্তব্য: connect() method-এর connection logic এবং error handling টেস্ট।"""

    @pytest.mark.asyncio
    async def test_successful_connection_with_token(self, nats_client, mock_nats_connection):
        """বাংলা মন্তব্য: Token সহ সফল connection establish হয়।"""
        mock_nc, mock_js = mock_nats_connection
        mock_kv = AsyncMock()
        mock_js.key_value.return_value = mock_kv

        mock_connect = AsyncMock(return_value=mock_nc)
        with patch.object(nats_messaging.nats, "connect", mock_connect):
            await nats_client.connect()

            mock_connect.assert_called_once_with(
                servers=["nats://localhost:4222"], token="test_token"
            )
            assert nats_client.nc is mock_nc
            assert nats_client.js is mock_js
            assert nats_client.kv_store is mock_kv

    @pytest.mark.asyncio
    async def test_successful_connection_without_token(self):
        """বাংলা মন্তব্য: Token না দিলেও connection establish হয়।"""
        client = NATSClient(token=None)
        mock_nc = AsyncMock()
        mock_js = AsyncMock()
        mock_kv = AsyncMock()
        mock_nc.jetstream = MagicMock(return_value=mock_js)
        mock_js.key_value.return_value = mock_kv

        mock_connect = AsyncMock(return_value=mock_nc)
        with patch.object(nats_messaging.nats, "connect", mock_connect):
            await client.connect()

            # token shouldn't be in kwargs when None
            call_kwargs = mock_connect.call_args.kwargs
            assert "token" not in call_kwargs or call_kwargs.get("token") is None

    @pytest.mark.asyncio
    async def test_connection_creates_kv_store_if_not_exists(
        self, nats_client, mock_nats_connection
    ):
        """বাংলা মন্তব্য: KV store না থাকলে create_key_value() call হয়।"""
        mock_nc, mock_js = mock_nats_connection
        mock_js.key_value.side_effect = Exception("Bucket not found")
        mock_kv = AsyncMock()
        mock_js.create_key_value.return_value = mock_kv

        mock_connect = AsyncMock(return_value=mock_nc)
        with patch.object(nats_messaging.nats, "connect", mock_connect):
            await nats_client.connect()

            mock_js.create_key_value.assert_called_once_with(bucket="WORKER_REGISTRY")
            assert nats_client.kv_store is mock_kv

    @pytest.mark.asyncio
    async def test_connection_no_servers_error(self, nats_client):
        """বাংলা মন্তব্য: NoServersError handle করে gracefully।"""
        from core.messaging.nats_messaging import NoServersError

        with patch.object(
            nats_messaging.nats,
            "connect",
            side_effect=NoServersError("No servers available"),
        ):
            await nats_client.connect()
            # Connection fails gracefully, nc remains None
            assert nats_client.nc is None
            assert nats_client.js is None
            assert nats_client.kv_store is None

    @pytest.mark.asyncio
    async def test_connection_general_exception(self, nats_client):
        """বাংলা মন্তব্য: General exception handle করে gracefully।"""
        with patch.object(
            nats_messaging.nats,
            "connect",
            side_effect=RuntimeError("Connection timeout"),
        ):
            await nats_client.connect()
            assert nats_client.nc is None


# -------------------- Tests: publish_event --------------------


class TestPublishEvent:
    """বাংলা মন্তব্য: publish_event() method টেস্ট।"""

    @pytest.mark.asyncio
    async def test_publish_with_dict(self, nats_client):
        """বাংলা মন্তব্য: dict data publish হয় correctly।"""
        mock_nc = AsyncMock()
        nats_client.nc = mock_nc

        test_data = {"event": "test", "value": 123}
        await nats_client.publish_event("test.subject", test_data)

        mock_nc.publish.assert_called_once()
        call_args = mock_nc.publish.call_args
        assert call_args.args[0] == "test.subject"
        published_data = json.loads(call_args.args[1].decode())
        assert published_data == test_data

    @pytest.mark.asyncio
    async def test_publish_with_pydantic_model(self, nats_client):
        """বাংলা মন্তব্য: Pydantic model data publish হয় correctly।"""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        mock_nc = AsyncMock()
        nats_client.nc = mock_nc

        model = TestModel(name="test", value=42)
        await nats_client.publish_event("test.subject", model)

        published_data = json.loads(mock_nc.publish.call_args.args[1].decode())
        assert published_data == {"name": "test", "value": 42}

    @pytest.mark.asyncio
    async def test_publish_without_connection(self, nats_client):
        """বাংলা মন্তব্য: Connection না থাকলে publish skip হয়।"""
        nats_client.nc = None
        with patch("core.messaging.nats_messaging.logger") as mock_logger:
            await nats_client.publish_event("test.subject", {"data": "test"})
            mock_logger.warning.assert_called_once_with("NATS client is not connected.")
            # publish shouldn't be called
            assert nats_client.nc is None


# -------------------- Tests: subscribe --------------------


class TestSubscribe:
    """বাংলা মন্তব্য: subscribe() method টেস্ট।"""

    @pytest.mark.asyncio
    async def test_subscribe_success(self, nats_client):
        """বাংলা মন্তব্য: সফলভাবে subscribe হয়।"""
        mock_nc = AsyncMock()
        nats_client.nc = mock_nc

        async def mock_callback(data):
            pass

        await nats_client.subscribe("test.subject", mock_callback)

        mock_nc.subscribe.assert_called_once()
        # Verify the callback was registered
        call_args = mock_nc.subscribe.call_args
        assert call_args.args[0] == "test.subject"
        assert call_args.kwargs["cb"] is not None

    @pytest.mark.asyncio
    async def test_subscribe_without_connection(self, nats_client):
        """বাংলা মন্তব্য: Connection না থাকলে subscribe skip হয়।"""
        nats_client.nc = None
        with patch("core.messaging.nats_messaging.logger") as mock_logger:
            await nats_client.subscribe("test.subject", lambda x: x)
            mock_logger.warning.assert_called_once_with("NATS client is not connected.")

    @pytest.mark.asyncio
    async def test_subscribe_message_handler_success(self, nats_client):
        """বাংলা মন্তব্য: Message handler correctly process করে message।"""
        mock_nc = AsyncMock()
        nats_client.nc = mock_nc

        received_data = []

        async def callback(data):
            received_data.append(data)

        await nats_client.subscribe("test.subject", callback)

        # Get the registered message handler
        subscribe_call = mock_nc.subscribe.call_args
        message_handler = subscribe_call.kwargs["cb"]

        # Simulate receiving a message
        mock_msg = MagicMock()
        mock_msg.data = json.dumps({"event": "test", "value": 123}).encode()
        await message_handler(mock_msg)

        assert len(received_data) == 1
        assert received_data[0] == {"event": "test", "value": 123}

    @pytest.mark.asyncio
    async def test_subscribe_message_handler_error(self, nats_client):
        """বাংলা মন্তব্য: Message handler-এ error হলে gracefully handle হয়।"""
        mock_nc = AsyncMock()
        nats_client.nc = mock_nc

        async def callback(data):
            raise RuntimeError("Handler error")

        await nats_client.subscribe("test.subject", callback)

        # Get the registered message handler
        subscribe_call = mock_nc.subscribe.call_args
        message_handler = subscribe_call.kwargs["cb"]

        # Simulate receiving a message that causes error
        mock_msg = MagicMock()
        mock_msg.data = b"invalid json"

        with patch("core.messaging.nats_messaging.logger") as mock_logger:
            await message_handler(mock_msg)
            # Error should be logged, not raised
            mock_logger.error.assert_called_once()


# -------------------- Tests: register_worker --------------------


class TestRegisterWorker:
    """বাংলা মন্তব্য: register_worker() method টেস্ট।"""

    @pytest.mark.asyncio
    async def test_register_worker_success(self, nats_client, mock_kv_store):
        """বাংলা মন্তব্য: Worker successfully register হয়।"""
        nats_client.kv_store = mock_kv_store

        worker_data = {"status": "active", "last_heartbeat": "2024-01-01T00:00:00Z"}
        await nats_client.register_worker("worker1", worker_data)

        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args
        assert call_args.args[0] == "worker1"
        stored_data = json.loads(call_args.args[1].decode())
        assert stored_data == worker_data

    @pytest.mark.asyncio
    async def test_register_worker_without_kv_store(self, nats_client):
        """বাংলা মন্তব্য: KV store না থাকলে register skip হয়।"""
        nats_client.kv_store = None
        # Should not raise any error
        await nats_client.register_worker("worker1", {"status": "active"})


# -------------------- Tests: get_worker --------------------


class TestGetWorker:
    """বাংলা মন্তব্য: get_worker() method টেস্ট।"""

    @pytest.mark.asyncio
    async def test_get_worker_success(self, nats_client, mock_kv_store):
        """বাংলা মন্তব্য: Worker info successfully retrieve হয়।"""
        nats_client.kv_store = mock_kv_store

        worker_info = await nats_client.get_worker("worker1")

        mock_kv_store.get.assert_called_once_with("worker1")
        assert worker_info == {"status": "active"}

    @pytest.mark.asyncio
    async def test_get_worker_not_found(self, nats_client, mock_kv_store):
        """বাংলা মন্তব্য: Worker না থাকলে None return হয়।"""
        from core.messaging.nats_messaging import KeyValueError

        mock_kv_store.get.side_effect = KeyValueError("Key not found")
        nats_client.kv_store = mock_kv_store

        worker_info = await nats_client.get_worker("nonexistent")
        assert worker_info is None

    @pytest.mark.asyncio
    async def test_get_worker_without_kv_store(self, nats_client):
        """বাংলা মন্তব্য: KV store না থাকলে None return হয়।"""
        nats_client.kv_store = None
        worker_info = await nats_client.get_worker("worker1")
        assert worker_info is None


# -------------------- Tests: get_all_workers --------------------


class TestGetAllWorkers:
    """বাংলা মন্তব্য: get_all_workers() method টেস্ট।"""

    @pytest.mark.asyncio
    async def test_get_all_workers_success(self, nats_client, mock_kv_store):
        """বাংলা মন্তব্য: সব workers successfully retrieve হয়।"""
        nats_client.kv_store = mock_kv_store

        # Mock the get calls for each key
        worker1_data = json.dumps({"status": "active"}).encode()
        worker2_data = json.dumps({"status": "idle"}).encode()

        def mock_get(key):
            if key == "worker1":
                result = MagicMock()
                result.value = worker1_data
                return result
            elif key == "worker2":
                result = MagicMock()
                result.value = worker2_data
                return result
            return None

        mock_kv_store.get.side_effect = mock_get

        workers = await nats_client.get_all_workers()

        assert len(workers) == 2
        assert workers["worker1"] == {"status": "active"}
        assert workers["worker2"] == {"status": "idle"}

    @pytest.mark.asyncio
    async def test_get_all_workers_empty(self, nats_client, mock_kv_store):
        """বাংলা মন্তব্য: কোনো worker না থাকলে empty dict return হয়।"""
        mock_kv_store.keys.return_value = []
        nats_client.kv_store = mock_kv_store

        workers = await nats_client.get_all_workers()
        assert workers == {}

    @pytest.mark.asyncio
    async def test_get_all_workers_exception_handling(self, nats_client, mock_kv_store):
        """বাংলা মন্তব্য: Exception handle করে empty dict return হয়।"""
        mock_kv_store.keys.side_effect = RuntimeError("KV store error")
        nats_client.kv_store = mock_kv_store

        workers = await nats_client.get_all_workers()
        assert workers == {}

    @pytest.mark.asyncio
    async def test_get_all_workers_without_kv_store(self, nats_client):
        """বাংলা মন্তব্য: KV store না থাকলে empty dict return হয়।"""
        nats_client.kv_store = None
        workers = await nats_client.get_all_workers()
        assert workers == {}


# -------------------- Tests: Global Instance --------------------


class TestGlobalInstance:
    """বাংলা মন্তব্য: Global nats_client instance টেস্ট।"""

    def test_global_instance_exists(self):
        """বাংলা মন্তব্য: Global instance create করা আছে।"""
        from core.messaging.nats_messaging import nats_client

        assert isinstance(nats_client, NATSClient)

    def test_global_instance_default_config(self):
        """বাংলা মন্তব্য: Global instance default configuration দিয়ে create করা আছে।"""
        import os

        from core.messaging.nats_messaging import nats_client

        assert nats_client.url == "nats://localhost:4222"
        assert nats_client.token == os.getenv("NATS_TOKEN")
