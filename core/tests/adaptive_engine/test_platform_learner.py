# বাংলা মন্তব্য: টেস্টে ব্যবহৃত httpx প্যাকেজ আমদানি করা হলো এবং অব্যবহৃত ইম্পোর্টগুলো মুছে ফেলা হলো।
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from adaptive_engine.platform_learner import PlatformLearner
from adaptive_engine.registry import PlatformProfile


@pytest.mark.asyncio
class TestPlatformLearner:
    @pytest.fixture
    def mock_registry(self):
        with patch("adaptive_engine.registry.PlatformRegistry") as mock_registry:
            yield mock_registry

    @pytest.fixture
    def mock_model_router(self):
        with patch("brain.model_router.ModelRouter") as mock_model_router:
            mock_model_router.async_route_and_generate = AsyncMock(return_value={"text": "{}"})
            yield mock_model_router

    @pytest.fixture
    def mock_async_client(self):
        with patch("httpx.AsyncClient") as mock_async_client:
            yield mock_async_client

    @pytest.fixture
    def platform_learner(self, mock_model_router, mock_registry):
        return PlatformLearner(mock_model_router, mock_registry)

    async def test_init(self, platform_learner, mock_model_router, mock_registry):
        """Test initialization of PlatformLearner class."""
        assert platform_learner.model_router == mock_model_router
        assert platform_learner.registry == mock_registry

    @pytest.mark.asyncio
    async def test_learn_from_docs_success(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with successful HTTP request and JSON parsing."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = (
            "<html>Test</html>"
        )
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_http_failure(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with failed HTTP request."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 404
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_json_parsing_failure(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with failed JSON parsing."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = (
            "<html>Test</html>"
        )
        mock_model_router.async_route_and_generate.return_value = {"text": "Invalid JSON"}
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_large_input(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with large input."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = "a" * 15000
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_empty_input(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with empty input."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = ""
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_none_input(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with None input."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = None
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_concurrent_calls(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with concurrent calls."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = (
            "<html>Test</html>"
        )
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        await platform_learner.learn_from_docs(platform_name, docs_url)
        await platform_learner.learn_from_docs(platform_name, docs_url)
        assert mock_model_router.async_route_and_generate.call_count == 2

    @pytest.mark.asyncio
    async def test_learn_from_docs_http_timeout(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with HTTP timeout."""
        mock_async_client.return_value.__aenter__.return_value.get.side_effect = (
            httpx.TimeoutException("Timeout")
        )
        mock_model_router.async_route_and_generate.return_value = {
            "text": '{"display_name": "Test", "category": "hosting"}'
        }
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_json_invalid(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with invalid JSON."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = (
            "<html>Test</html>"
        )
        mock_model_router.async_route_and_generate.return_value = {"text": "Invalid JSON"}
        platform_name = "test"
        docs_url = "https://test.com"
        profile = await platform_learner.learn_from_docs(platform_name, docs_url)
        assert isinstance(profile, PlatformProfile)
        assert profile.display_name == "Test"
        assert profile.category == "hosting"

    @pytest.mark.asyncio
    async def test_learn_from_docs_model_router_failure(
        self, platform_learner, mock_model_router, mock_registry, mock_async_client
    ):
        """Test learn_from_docs with model router failure."""
        mock_async_client.return_value.__aenter__.return_value.get.return_value.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.get.return_value.text = (
            "<html>Test</html>"
        )
        mock_model_router.async_route_and_generate.side_effect = Exception("Test")
        platform_name = "test"
        docs_url = "https://test.com"
        with pytest.raises(Exception, match="Test"):
            await platform_learner.learn_from_docs(platform_name, docs_url)
