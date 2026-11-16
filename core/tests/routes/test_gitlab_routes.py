from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_user_token, get_tenant_db
from core.api.routes.gitlab import router
from database.session import get_db_session


class DummyTenantRoot:
    def set(self, data, merge=True):
        pass


class DummyTenantDB:
    def __init__(self):
        self.tenant_root = DummyTenantRoot()

    def get_tenant_profile(self):
        return {"gitlab_project": "test-org/test-repo"}


@pytest.fixture()
def client():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_current_user_token] = lambda: {"sub": "user-123"}
    app.dependency_overrides[get_tenant_db] = lambda: DummyTenantDB()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    return TestClient(app)


def test_gitlab_connect_route(client):
    mock_connect_res = {
        "status": "success",
        "project": "test-org/test-repo",
        "id": 999,
        "default_branch": "main",
    }
    with patch("core.api.routes.gitlab.get_user_gitlab_token", return_value="glpat-valid123"):
        with patch.object(
            __import__("core.tools.devops.gitlab_agent", fromlist=["GitLabAgent"]).GitLabAgent,
            "connect_project",
            new=AsyncMock(return_value=mock_connect_res),
        ):
            res = client.post(
                "/gitlab/connect",
                json={"project_path": "test-org/test-repo"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert "test-org/test-repo" in data["message"]


def test_gitlab_push_route(client):
    mock_commit_res = {
        "status": "success",
        "branch": "feature-x",
        "commit_id": "sha12345",
        "files_committed": ["src/index.ts"],
    }
    mock_mr_res = {
        "status": "success",
        "mr_url": "https://gitlab.com/test-org/test-repo/-/merge_requests/1",
        "mr_iid": 1,
    }
    with patch("core.api.routes.gitlab.get_user_gitlab_token", return_value="glpat-valid123"):
        with patch.object(
            __import__("core.tools.devops.gitlab_agent", fromlist=["GitLabAgent"]).GitLabAgent,
            "commit_changes",
            new=AsyncMock(return_value=mock_commit_res),
        ):
            with patch.object(
                __import__("core.tools.devops.gitlab_agent", fromlist=["GitLabAgent"]).GitLabAgent,
                "create_mr",
                new=AsyncMock(return_value=mock_mr_res),
            ):
                res = client.post(
                    "/gitlab/push",
                    json={
                        "project": "test-org/test-repo",
                        "branch": "feature-x",
                        "commit_message": "Add test code",
                        "file_contents": {"src/index.ts": "console.log('hello');"},
                        "create_mr": True,
                    },
                )
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "success"
                assert data["commit_id"] == "sha12345"
                assert "merge_requests/1" in data["mr_url"]
