from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tools.devops.gitlab_agent import GitLabAgent


@pytest.mark.asyncio
async def test_gitlab_agent_project_connect():
    """connect_project retrieves project metadata successfully."""
    agent = GitLabAgent(token="glpat-mock123")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 12345,
        "path_with_namespace": "myorg/myproject",
        "default_branch": "main",
        "web_url": "https://gitlab.com/myorg/myproject",
    }
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.tools.devops.gitlab_agent.httpx.AsyncClient", return_value=mock_client):
        res = await agent.connect_project("myorg/myproject")

    assert res["status"] == "success"
    assert res["id"] == 12345
    assert res["default_branch"] == "main"


@pytest.mark.asyncio
async def test_gitlab_agent_analyze():
    """analyze_project pulls issues and metadata."""
    agent = GitLabAgent(token="glpat-mock123")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 12345,
        "open_issues_count": 7,
        "default_branch": "main",
        "visibility": "private",
        "web_url": "https://gitlab.com/myorg/myproject",
    }
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.tools.devops.gitlab_agent.httpx.AsyncClient", return_value=mock_client):
        res = await agent.analyze_project("myorg/myproject")

    assert res["status"] == "success"
    assert res["open_issues"] == 7
    assert res["visibility"] == "private"


@pytest.mark.asyncio
async def test_gitlab_agent_create_mr():
    """create_mr successfully calls GitLab merge_requests endpoint."""
    agent = GitLabAgent(token="glpat-mock123")

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": 999,
        "iid": 42,
        "web_url": "https://gitlab.com/myorg/myproject/-/merge_requests/42",
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("core.tools.devops.gitlab_agent.httpx.AsyncClient", return_value=mock_client):
        res = await agent.create_mr(
            "myorg/myproject",
            "Auto Fix",
            "Automated MR body",
            "feature-branch",
            "main",
        )

    assert res["status"] == "success"
    assert res["mr_iid"] == 42
    assert "https://gitlab.com/myorg/myproject/-/merge_requests/42" in res["mr_url"]
