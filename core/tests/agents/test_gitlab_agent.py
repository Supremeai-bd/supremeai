from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.tools.devops.gitlab_agent import GitLabAgent


def _build_mock_client(response_data: dict, status_code: int = 200, method: str = "get") -> AsyncMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = response_data
    resp.raise_for_status = MagicMock()

    client = AsyncMock()
    setattr(client, method, AsyncMock(return_value=resp))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_gitlab_agent_project_connect():
    """connect_project retrieves project metadata successfully."""
    agent = GitLabAgent(token="glpat-mock123")
    mock_client = _build_mock_client({
        "id": 12345,
        "path_with_namespace": "myorg/myproject",
        "default_branch": "main",
        "web_url": "https://gitlab.com/myorg/myproject",
    })

    with patch("core.tools.devops.gitlab_agent.httpx.AsyncClient", return_value=mock_client):
        res = await agent.connect_project("myorg/myproject")

    assert res["status"] == "success"
    assert res["id"] == 12345
    assert res["default_branch"] == "main"


@pytest.mark.asyncio
async def test_gitlab_agent_analyze():
    """analyze_project pulls issues and metadata."""
    agent = GitLabAgent(token="glpat-mock123")
    mock_client = _build_mock_client({
        "id": 12345,
        "open_issues_count": 7,
        "default_branch": "main",
        "visibility": "private",
        "web_url": "https://gitlab.com/myorg/myproject",
    })

    with patch("core.tools.devops.gitlab_agent.httpx.AsyncClient", return_value=mock_client):
        res = await agent.analyze_project("myorg/myproject")

    assert res["status"] == "success"
    assert res["open_issues"] == 7
    assert res["visibility"] == "private"


@pytest.mark.asyncio
async def test_gitlab_agent_create_mr():
    """create_mr successfully calls GitLab merge_requests endpoint."""
    agent = GitLabAgent(token="glpat-mock123")
    mock_client = _build_mock_client(
        {
            "id": 999,
            "iid": 42,
            "web_url": "https://gitlab.com/myorg/myproject/-/merge_requests/42",
        },
        status_code=201,
        method="post",
    )

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
