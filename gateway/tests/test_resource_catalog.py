import httpx
import pytest

from api.routes import marketplace_endpoints
from tools.resource_catalog import ResourceCatalog


@pytest.mark.anyio
async def test_resource_catalog_search_mock(monkeypatch):
    markdown = "- [LocalAI](https://localai.dev) - Local inference for open models.\n- [Chroma](https://www.trychroma.com) - Embeddable vector database.\n"

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    async def fake_get(url, *args, **kwargs):
        return FakeResponse(markdown)

    async with httpx.AsyncClient() as client:
        catalog = ResourceCatalog(http_client=client)
        monkeypatch.setattr(client, "get", fake_get)
        results = await catalog.search("vector")

    assert isinstance(results, list)
    assert all("name" in item and "description" in item for item in results)


@pytest.mark.anyio
async def test_resource_catalog_optional_sources(monkeypatch):
    expected = [
        {
            "name": "repo1",
            "description": "A repo",
            "html_url": "https://github.com/example/repo1",
            "stargazers_count": 100,
            "forks_count": 10,
            "open_issues_count": 5,
            "watchers_count": 80,
            "default_branch": "main",
        }
    ]

    class FakeResponse:
        def __init__(self, json_data):
            self._json = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return {"items": self._json}

    async def fake_get(url, *args, **kwargs):
        return FakeResponse(expected)

    async with httpx.AsyncClient() as client:
        catalog = ResourceCatalog(http_client=client)
        monkeypatch.setattr(client, "get", fake_get)
        results = await catalog.search("repo1", sources=["ossinsight"], limit=1)

    assert len(results) == 1
    assert results[0]["source"] == "ossinsight"


@pytest.mark.anyio
async def test_enabled_catalog_sources_from_db(monkeypatch):
    class FakeDB:
        def get_config(self, key):
            if key == "marketplace.resource_sources":
                return ["awesome-python", "libraries.io"]
            return None

    class FakeResponse:
        def __init__(self, text=None, json_data=None):
            self.text = text
            self._json = json_data

        def raise_for_status(self):
            return None

        def json(self):
            return self._json

    monkeypatch.setattr(marketplace_endpoints.db, "client", True)
    monkeypatch.setattr(
        marketplace_endpoints.db,
        "get_config",
        lambda key: (
            ["awesome-python", "libraries.io"] if key == "marketplace.resource_sources" else None
        ),
    )

    sources = marketplace_endpoints.get_enabled_catalog_sources()

    assert sources == ["awesome-python", "libraries.io"]
