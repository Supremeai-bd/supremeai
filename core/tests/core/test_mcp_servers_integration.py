import asyncio

# backend/tests/test_mcp_servers_integration.py
# বাংলা মন্তব্য: সমস্ত নতুন MCP সার্ভারগুলোর ইন্টিগ্রেশন টেস্ট
import importlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError


# বাংলা মন্তব্য: প্রতিটি টেস্টে এনভায়রনমেন্ট ভ্যারিয়েবল মক করার জন্য ফিক্সচার
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    env_vars = {
        "SUPABASE_DATABASE_URL": "postgres://localhost/mydb",
        "RENDER_API_KEY": "test-render-key",
        # বাংলা মন্তব্য (#3077): RAILWAY_TOKEN/ORACLE_CLOUD_API_KEY সরানো —
        # mcp_cloud_deploy.py থেকে Railway/Oracle প্রোভাইডারই বাদ (ভুয়া endpoint)।
        "ADMIN_AUTHORIZED": "true",
        "GITHUB_TOKEN": "test-github-token",
    }
    from core.config import settings

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)
        try:
            if hasattr(settings, k.lower()):
                setattr(settings, k.lower(), v)
            elif hasattr(settings, k):
                setattr(settings, k, v)
            # Handle extra fields properly if Pydantic model allows it
            elif getattr(settings.model_config, "extra", "ignore") == "allow":
                setattr(settings, k.lower(), v)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")


# বাংলা মন্তব্য: cloud_deploy_mcp টেস্টস
class TestCloudDeployMCP:
    """cloud_deploy_mcp.py এর জন্য টেস্ট ক্লাস।"""

    def test_deploy_service_input_validation(self):
        """DeployServiceInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, DeployServiceInput

        # বৈধ ইনপুট
        valid_input = DeployServiceInput(
            provider=CloudProvider.RENDER, service_name="test-service", branch="main"
        )
        assert valid_input.provider == CloudProvider.RENDER
        assert valid_input.service_name == "test-service"
        assert valid_input.branch == "main"

    def test_deploy_service_input_missing_provider(self):
        """প্রোভাইডার বাদে ইনপুট রিকেকশন টেস্ট।"""
        from tools.mcp.mcp_cloud_deploy import DeployServiceInput

        with pytest.raises(ValidationError):
            DeployServiceInput(service_name="test-service", branch="main")

    def test_get_logs_input_validation(self):
        """GetLogsInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, GetLogsInput

        valid_input = GetLogsInput(
            provider=CloudProvider.RENDER, service_name="my-service", lines=500
        )
        assert valid_input.lines == 500

    def test_cloud_provider_enum(self):
        """CloudProvider enum টেস্ট।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider

        assert CloudProvider.RENDER.value == "render"
        # বাংলা মন্তব্য (#3077): Railway/Oracle এখন অবৈধ — নির্বাচন করলেই ValueError (চুক্তি-গার্ড)।
        with pytest.raises(ValueError):
            CloudProvider("railway")
        with pytest.raises(ValueError):
            CloudProvider("oracle")
        assert not hasattr(CloudProvider, "RAILWAY")
        assert not hasattr(CloudProvider, "ORACLE")


# বাংলা মন্তব্য: github_cicd_mcp টেস্টস
class TestGithubCICDMCP:
    """github_cicd_mcp.py এর জন্য টেস্ট ক্লাস।"""

    def test_create_pr_input_validation(self):
        """CreatePRInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_github_cicd import CreatePRInput

        valid_input = CreatePRInput(
            title="Test PR",
            body="This is a test PR",
            head="feature-branch",
            base="develop",
        )
        assert valid_input.title == "Test PR"
        assert valid_input.base == "develop"

    def test_create_pr_input_missing_title(self):
        """শিরোনাম বাদে ইনপুট রিকেকশন টেস্ট।"""
        from tools.mcp.mcp_github_cicd import CreatePRInput

        with pytest.raises(ValidationError):
            CreatePRInput(body="Test body", head="feature-branch")

    def test_fix_issue_input_validation(self):
        """FixIssueInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_github_cicd import FixIssueInput

        valid_input = FixIssueInput(issue_number=42, branch="fix/issue-42")
        assert valid_input.issue_number == 42

    def test_response_format_enum(self):
        """ResponseFormat enum টেস্ট।"""
        from tools.mcp.mcp_github_cicd import ResponseFormat

        assert ResponseFormat.MARKDOWN.value == "markdown"
        assert ResponseFormat.JSON.value == "json"


# বাংলা মন্তব্য: supabase_mcp টেস্টস
class TestSupabaseMCP:
    """supabase_mcp.py এর জন্য টেস্ট ক্লাস।"""

    def test_execute_query_input_validation(self):
        """ExecuteQueryInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_supabase import ExecuteQueryInput, ResponseFormat

        valid_input = ExecuteQueryInput(
            query="SELECT * FROM users LIMIT 10",
            params=None,
            response_format=ResponseFormat.JSON,
        )
        assert valid_input.query == "SELECT * FROM users LIMIT 10"

    def test_execute_query_input_with_params(self):
        """ExecuteQueryInput প্যারামিটার সহ ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_supabase import ExecuteQueryInput, ResponseFormat

        valid_input = ExecuteQueryInput(
            query="SELECT * FROM users WHERE id = %s",
            params=[1],
            response_format=ResponseFormat.MARKDOWN,
        )
        assert valid_input.params == [1]

    def test_create_table_input_validation(self):
        """CreateTableInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_supabase import CreateTableInput

        valid_input = CreateTableInput(
            table_name="users",
            columns="id SERIAL PRIMARY KEY, name VARCHAR(100)",
            if_not_exists=True,
        )
        assert valid_input.if_not_exists is True


class TestWorkspaceMCP:
    """workspace_mcp.py এর জন্য টেস্ট ক্লাস।"""

    def test_workspace_type_enum(self):
        """WorkspaceType enum টেস্ট।"""
        from tools.mcp.mcp_workspace import WorkspaceType

        assert WorkspaceType.ECOMMERCE_BACKEND.value == "ecommerce_backend"
        assert WorkspaceType.ECOMMERCE_FRONTEND.value == "ecommerce_frontend"
        assert WorkspaceType.MOBILE_FLUTTER.value == "mobile_flutter"
        assert WorkspaceType.ADMIN_PANEL.value == "admin_panel"

    def test_workspace_context_input_validation(self):
        """WorkspaceContextInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_workspace import WorkspaceContextInput, WorkspaceType

        valid_input = WorkspaceContextInput(
            project_type=WorkspaceType.ECOMMERCE_BACKEND, tenant_id="tenant-001"
        )
        assert valid_input.project_type == WorkspaceType.ECOMMERCE_BACKEND
        assert valid_input.tenant_id == "tenant-001"

    def test_scoped_file_path_input_validation(self):
        """ScopedFilePathInput মডেলের ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_workspace import ScopedFilePathInput

        valid_input = ScopedFilePathInput(relative_path="src/main.py")
        assert valid_input.relative_path == "src/main.py"

    def test_workspace_config_loading(self):
        """ওয়ার্কস্পেস কনফিগারেশন লোডিং টেস্ট।"""
        from tools.mcp.mcp_workspace import _load_workspace_config

        config = _load_workspace_config()
        assert isinstance(config, dict)


# বাংলা মন্তব্য: সিকনেশন টেস্টস
class TestMCPServerSync:
    """MCP সার্ভারগুলোর সিকনেশন টেস্ট।"""

    def test_all_mcp_servers_importable(self):
        """সব MCP সার্ভার ইম্পোর্ট করা যায় কিনা টেস্ট।"""
        import importlib.util

        servers = [
            "mcp_cloud_deploy",
            "mcp_github_cicd",
            "mcp_supabase",
            "mcp_workspace",
        ]
        for server in servers:
            spec = importlib.util.find_spec(f"tools.mcp.{server}")
            assert spec is not None, f"tools.{server} module not found"

    def test_mcp_servers_have_fastmcp_instance(self):
        """MCP সার্ভারগুলোতে FastMCP ইনস্ট্যান্স আছে কিনা টেস্ট।"""
        from tools.mcp import (
            mcp_cloud_deploy,
            mcp_github_cicd,
            mcp_supabase,
            mcp_workspace,
        )

        assert hasattr(mcp_cloud_deploy, "mcp")
        assert hasattr(mcp_github_cicd, "mcp")
        assert hasattr(mcp_supabase, "mcp")
        assert hasattr(mcp_workspace, "mcp")

    def test_mcp_servers_have_tools(self):
        """MCP সার্ভারগুলোতে টুলস আছে কিনা টেস্ট।"""
        from tools.mcp import (
            mcp_cloud_deploy,
            mcp_github_cicd,
            mcp_supabase,
            mcp_workspace,
        )

        # cloud_deploy_mcp টুলস
        assert hasattr(mcp_cloud_deploy, "cloud_deploy_service")
        assert hasattr(mcp_cloud_deploy, "cloud_get_deployment_logs")
        assert hasattr(mcp_cloud_deploy, "cloud_list_services")

        # github_cicd_mcp টুলস
        assert hasattr(mcp_github_cicd, "github_create_pull_request")
        assert hasattr(mcp_github_cicd, "github_run_auto_fix")
        assert hasattr(mcp_github_cicd, "github_list_issues")
        assert hasattr(mcp_github_cicd, "github_get_ci_status")

        # supabase_mcp টুলস
        assert hasattr(mcp_supabase, "supabase_execute_sql")
        assert hasattr(mcp_supabase, "supabase_create_table")
        assert hasattr(mcp_supabase, "supabase_run_migration")
        assert hasattr(mcp_supabase, "supabase_list_tables")

        # workspace_mcp টুলস
        assert hasattr(mcp_workspace, "workspace_set_context")
        assert hasattr(mcp_workspace, "workspace_get_scoped_path")
        assert hasattr(mcp_workspace, "workspace_list_projects")

    def test_mcp_servers_run(self):
        """MCP সার্ভারগুলো run() মেথড কল করলে রান হয় কিনা যাচাই।"""
        from tools import mcp_cloud_deploy, mcp_supabase

        with patch.object(mcp_cloud_deploy.mcp, "run") as mock_run_cloud:
            mcp_cloud_deploy.mcp.run()
            mock_run_cloud.assert_called_once()

        with patch.object(mcp_supabase.mcp, "run") as mock_run_sb:
            mcp_supabase.mcp.run()
            mock_run_sb.assert_called_once()

    def test_service_name_validation_fails(self):
        """ভুল ফরম্যাটের সার্ভিস নেম রিজেক্ট হচ্ছে কিনা টেস্ট।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, DeployServiceInput

        with pytest.raises(ValidationError):
            DeployServiceInput(
                provider=CloudProvider.RENDER,
                service_name="invalid;injection",
                branch="main",
            )

    @pytest.mark.asyncio
    async def test_workspace_path_traversal_fails(self):
        """পাথ ট্রাভার্সাল আক্রমণ রিজেক্ট হচ্ছে কিনা টেস্ট।"""
        from tools.mcp.mcp_workspace import (
            ScopedFilePathInput,
            workspace_get_scoped_path,
        )

        params = ScopedFilePathInput(relative_path="../../sensitive_file.txt")
        result = await workspace_get_scoped_path(params)
        assert "Path traversal not allowed" in result


# বাংলা মন্তব্য: অতিরিক্ত কাভারেজ টেস্টস
class TestCloudDeployMCPExtended:
    """cloud_deploy_mcp.py এর জন্য অতিরিক্ত টেস্ট।"""

    @pytest.mark.asyncio
    async def test_deploy_service_missing_admin_auth(self, monkeypatch):
        """অ্যাডমিন অথেন্টিকেশন না থাকলে ডিপ্লয় ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
        result = await cloud_deploy_service(params)
        data = json.loads(result)
        assert data["error"] == "Admin authorization required for deployments"

    @pytest.mark.asyncio
    async def test_deploy_service_missing_render_api_key(self, monkeypatch):
        """RENDER_API_KEY না থাকলে ডিপ্লয় ব্যর্থ হয়।"""
        monkeypatch.setenv("RENDER_API_KEY", "")
        import tools.mcp.mcp_cloud_deploy

        importlib.reload(tools.mcp.mcp_cloud_deploy)
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
        result = await cloud_deploy_service(params)
        data = json.loads(result)
        assert data["error"] == "RENDER_API_KEY not configured"

    @pytest.mark.asyncio
    async def test_deploy_service_removed_providers_rejected(self):
        """(#3077) Railway/Oracle এখন নিষিদ্ধ — enum-ভ্যালুই গ্রহণ করা হয় না (টোকেন-মিসডিরেকশন বন্ধ)।"""
        from tools.mcp.mcp_cloud_deploy import DeployServiceInput

        with pytest.raises(ValidationError):
            DeployServiceInput(provider="railway", service_name="test")
        with pytest.raises(ValidationError):
            DeployServiceInput(provider="oracle", service_name="test")

    @pytest.mark.asyncio
    async def test_deploy_service_api_error_401(self, monkeypatch):
        """API এরর 401 হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_deploy_service(params)
            assert "Invalid API key" in result

    @pytest.mark.asyncio
    async def test_deploy_service_api_error_404(self, monkeypatch):
        """API এরর 404 হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_deploy_service(params)
            assert "Service not found" in result

    @pytest.mark.asyncio
    async def test_deploy_service_api_error_429(self, monkeypatch):
        """API এরর 429 (Rate Limit) হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Too Many Requests", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_deploy_service(params)
            assert "Rate limit exceeded" in result

    @pytest.mark.asyncio
    async def test_deploy_service_generic_error(self, monkeypatch):
        """জেনেরিক এরর হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_deploy_service(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_get_logs_missing_api_key(self, monkeypatch):
        """Get Logs এ API কী না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("RENDER_API_KEY", "")
        import tools.mcp.mcp_cloud_deploy

        importlib.reload(tools.mcp.mcp_cloud_deploy)
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            GetLogsInput,
            cloud_get_deployment_logs,
        )

        params = GetLogsInput(provider=CloudProvider.RENDER, service_name="test")
        result = await cloud_get_deployment_logs(params)
        data = json.loads(result)
        assert data["error"] == "RENDER_API_KEY not configured"

    @pytest.mark.asyncio
    async def test_get_logs_api_error(self, monkeypatch):
        """Get Logs এ API এরর হ্যান্ডল হয়।"""
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            GetLogsInput,
            cloud_get_deployment_logs,
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = GetLogsInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_get_deployment_logs(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_list_services_success(self, monkeypatch):
        """Services তালিকা লোড করা যায়।"""
        # বাংলা মন্তব্য (#3077): Railway/Oracle লেগ সরানো — কেবল Render প্রোব হয়।
        from tools.mcp.mcp_cloud_deploy import cloud_list_services

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "serviceName": "service1",
                "status": "active",
                "url": "https://example.com",
            }
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await cloud_list_services()
            data = json.loads(result)
            assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_list_services_exception(self, monkeypatch):
        """Services তালিকা লোড করতে ব্যর্থ হলে একখানে থাকে।"""
        from tools.mcp.mcp_cloud_deploy import cloud_list_services

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await cloud_list_services()
            data = json.loads(result)
            assert data["count"] == 0


class TestGithubCICDMCPExtended:
    """github_cicd_mcp.py এর জন্য অতিরিক্ত টেস্ট।"""

    @pytest.mark.asyncio
    async def test_create_pr_missing_admin_auth(self, monkeypatch):
        """অ্যাডমিন অথেন্টিকেশন না থাকলে PR তৈরি ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_github_cicd import CreatePRInput, github_create_pull_request

        params = CreatePRInput(title="Test", body="Test PR", head="feature", base="main")
        result = await github_create_pull_request(params)
        data = json.loads(result)
        assert data["error"] == "Admin authorization required for PR creation"

    @pytest.mark.asyncio
    async def test_create_pr_missing_token(self, monkeypatch):
        """GITHUB_TOKEN না থাকলে PR তৈরি ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        monkeypatch.setenv("GITHUB_TOKEN", "")
        import tools.mcp.mcp_github_cicd

        importlib.reload(tools.mcp.mcp_github_cicd)
        from tools.mcp.mcp_github_cicd import CreatePRInput, github_create_pull_request

        # Issue-first gate (#925) runs before the token check — body must
        # carry a valid issue-link so the missing-token path is exercised.
        params = CreatePRInput(title="Test", body="Fixes #42", head="feature", base="main")
        result = await github_create_pull_request(params)
        data = json.loads(result)
        assert data["error"] == "GITHUB_TOKEN not configured"

    @pytest.mark.asyncio
    async def test_create_pr_api_error_401(self, monkeypatch):
        """PR তৈরি করতে 401 এরর হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_github_cicd import CreatePRInput, github_create_pull_request

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            # Issue-first gate (#925) must pass so the API 401 path is reached.
            params = CreatePRInput(title="Test", body="Fixes #42", head="feature", base="main")
            result = await github_create_pull_request(params)
            assert "Invalid API key" in result

    @pytest.mark.asyncio
    async def test_create_pr_api_error_403(self, monkeypatch):
        """PR তৈরি করতে 403 এরর হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_github_cicd import CreatePRInput, github_create_pull_request

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            # Issue-first gate (#925) must pass so the API error path is reached.
            params = CreatePRInput(title="Test", body="Fixes #12", head="feature", base="main")
            result = await github_create_pull_request(params)
            assert "Permission denied" in result

    @pytest.mark.asyncio
    async def test_run_auto_fix_missing_auth(self, monkeypatch):
        """Auto-fix অথেন্টিকেশন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("AUTOFIX_AUTHORIZED", "false")
        from tools.mcp.mcp_github_cicd import FixIssueInput, github_run_auto_fix

        params = FixIssueInput(issue_number=1, branch="fix/issue-1")
        result = await github_run_auto_fix(params)
        data = json.loads(result)
        assert data["error"] == "Auto-fix authorization required"

    @pytest.mark.asyncio
    async def test_list_issues_missing_token(self, monkeypatch):
        """List Issues এ টোকেন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("GITHUB_TOKEN", "")
        from tools.mcp.mcp_github_cicd import github_list_issues

        result = await github_list_issues()
        data = json.loads(result)
        assert data["error"] == "GITHUB_TOKEN not configured"

    @pytest.mark.asyncio
    async def test_list_issues_invalid_state(self, monkeypatch):
        """List Issues এ অবৈধ স্টেট প্যারামিটার ডিফল্ট হয়।"""
        from tools.mcp.mcp_github_cicd import github_list_issues

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_list_issues(state="invalid_state")
            data = json.loads(result)
            assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_get_ci_status_missing_token(self, monkeypatch):
        """Get CI Status এ টোকেন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("GITHUB_TOKEN", "")
        from tools.mcp.mcp_github_cicd import github_get_ci_status

        result = await github_get_ci_status()
        data = json.loads(result)
        assert data["error"] == "GITHUB_TOKEN not configured"

    @pytest.mark.asyncio
    async def test_get_ci_status_api_error(self, monkeypatch):
        """Get CI Status এ API এরর হ্যান্ডল হয়।"""
        from tools.mcp.mcp_github_cicd import github_get_ci_status

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_get_ci_status()
            assert "Error" in result


class TestSupabaseMCPExtended:
    """supabase_mcp.py এর জন্য অতিরিক্ত টেস্ট।"""

    @pytest.mark.asyncio
    async def test_execute_sql_missing_db_url(self, monkeypatch):
        """Execute SQL এ ডাটাবেস URL না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setattr("tools.mcp.mcp_supabase._get_supabase_db_url", lambda: "")
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        params = ExecuteQueryInput(query="SELECT 1", response_format=ResponseFormat.JSON)
        result = await supabase_execute_sql(params)
        data = json.loads(result)
        assert data["error"] == "SUPABASE_DATABASE_URL not configured"

    @pytest.mark.asyncio
    async def test_execute_sql_destructive_without_admin(self, monkeypatch):
        """ডেস্ট্রাকটিভ কুয়েরি অথেন্টিকেশন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        params = ExecuteQueryInput(query="DROP TABLE users", response_format=ResponseFormat.JSON)
        result = await supabase_execute_sql(params)
        data = json.loads(result)
        assert "Admin authorization required" in data["error"]

    @pytest.mark.asyncio
    async def test_execute_sql_destructive_with_admin(self, monkeypatch):
        """ডেস্ট্রাকটিভ কুয়েরি অথেন্টিকেশন সহ সফল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.description = []
            mock_cursor.rowcount = 1
            mock_conn.return_value = MagicMock(
                cursor=lambda: mock_cursor, commit=MagicMock(), close=MagicMock()
            )

            params = ExecuteQueryInput(
                query="DROP TABLE users", response_format=ResponseFormat.JSON
            )
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_execute_sql_select_json_format(self, monkeypatch):
        """SELECT কুয়েরি JSON ফরম্যাটে রিটার্ন হয়।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [(1, "test"), (2, "test2")]
            mock_cursor.description = [("id",), ("name",)]
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM users", response_format=ResponseFormat.JSON
            )
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["row_count"] == 2

    @pytest.mark.asyncio
    async def test_create_table_missing_admin(self, monkeypatch):
        """Create Table এ অথেন্টিকেশন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_supabase import CreateTableInput, supabase_create_table

        params = CreateTableInput(
            table_name="users", columns="id SERIAL PRIMARY KEY", if_not_exists=True
        )
        result = await supabase_create_table(params)
        data = json.loads(result)
        assert data["error"] == "Admin authorization required for table creation"

    @pytest.mark.asyncio
    async def test_create_table_success(self, monkeypatch):
        """Create Table সফল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_supabase import CreateTableInput, supabase_create_table

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_conn.return_value = MagicMock(
                cursor=MagicMock(), commit=MagicMock(), close=MagicMock()
            )

            params = CreateTableInput(
                table_name="users", columns="id SERIAL PRIMARY KEY", if_not_exists=True
            )
            result = await supabase_create_table(params)
            data = json.loads(result)
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_run_migration_missing_db_url(self, monkeypatch):
        """Run Migration এ ডাটাবেস URL না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setattr("tools.mcp.mcp_supabase._get_supabase_db_url", lambda: "")
        from tools.mcp.mcp_supabase import MigrationInput, supabase_run_migration

        params = MigrationInput(
            migration_name="test",
            up_sql="CREATE TABLE test (id INT)",
            down_sql="DROP TABLE test",
        )
        result = await supabase_run_migration(params)
        data = json.loads(result)
        assert data["error"] == "SUPABASE_DATABASE_URL not configured"

    @pytest.mark.asyncio
    async def test_run_migration_already_applied(self, monkeypatch):
        """মাইগ্রেশন ইতিমধ্যে আপ্লাই করা হয়েছে।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_supabase import MigrationInput, supabase_run_migration

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [1]
            mock_conn.return_value = MagicMock(
                cursor=lambda: mock_cursor, commit=MagicMock(), close=MagicMock()
            )

            params = MigrationInput(
                migration_name="test",
                up_sql="CREATE TABLE test (id INT)",
                down_sql="DROP TABLE test",
            )
            result = await supabase_run_migration(params)
            data = json.loads(result)
            assert "already applied" in data["message"]

    @pytest.mark.asyncio
    async def test_run_migration_missing_admin(self, monkeypatch):
        """Run Migration এ অথেন্টিকেশন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_supabase import MigrationInput, supabase_run_migration

        params = MigrationInput(
            migration_name="test",
            up_sql="CREATE TABLE test (id INT)",
            down_sql="DROP TABLE test",
        )
        result = await supabase_run_migration(params)
        data = json.loads(result)
        assert data["error"] == "Admin authorization required for migrations"

    @pytest.mark.asyncio
    async def test_list_tables_missing_db_url(self, monkeypatch):
        """List Tables এ ডাটাবেস URL না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setattr("tools.mcp.mcp_supabase._get_supabase_db_url", lambda: "")
        from tools.mcp.mcp_supabase import supabase_list_tables

        result = await supabase_list_tables()
        data = json.loads(result)
        assert data["error"] == "SUPABASE_DATABASE_URL not configured"

    @pytest.mark.asyncio
    async def test_list_tables_success(self, monkeypatch):
        """List Tables সফল হয়।"""
        from tools.mcp.mcp_supabase import supabase_list_tables

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ("users", "BASE TABLE"),
                ("posts", "BASE TABLE"),
            ]
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            result = await supabase_list_tables()
            data = json.loads(result)
            assert data["count"] == 2


class TestWorkspaceMCPExtended:
    """workspace_mcp.py এর জন্য অতিরিক্ত টেস্ট।"""

    def test_workspace_type_all_values(self):
        """WorkspaceType enum এর সব মান টেস্ট।"""
        from tools.mcp.mcp_workspace import WorkspaceType

        assert WorkspaceType.INFRASTRUCTURE.value == "infrastructure"
        assert WorkspaceType.ANDROID_JAVA.value == "android_java"

    def test_scoped_file_path_input_missing_path(self):
        """ScopedFilePathInput এ relative_path বাদে ইনপুট রিকেকশন টেস্ট।"""
        from tools.mcp.mcp_workspace import ScopedFilePathInput

        with pytest.raises(ValidationError):
            ScopedFilePathInput()

    @pytest.mark.asyncio
    async def test_workspace_set_context_missing_admin_for_admin_panel(self, monkeypatch):
        """Admin Panel ওয়ার্কস্পেস অথেন্টিকেশন না থাকলে ব্যর্থ হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_workspace import (
            WorkspaceContextInput,
            WorkspaceType,
            workspace_set_context,
        )

        params = WorkspaceContextInput(project_type=WorkspaceType.ADMIN_PANEL, tenant_id="test")
        result = await workspace_set_context(params)
        data = json.loads(result)
        assert data["error"] == "Admin authorization required for admin panel workspace"

    @pytest.mark.asyncio
    async def test_workspace_set_context_success(self, monkeypatch):
        """Workspace Context সফল হয়।"""
        from tools.mcp.mcp_workspace import (
            WorkspaceContextInput,
            WorkspaceType,
            workspace_set_context,
        )

        params = WorkspaceContextInput(
            project_type=WorkspaceType.ECOMMERCE_BACKEND, tenant_id="test-tenant"
        )
        result = await workspace_set_context(params)
        data = json.loads(result)
        assert data["success"] is True
        assert data["project_type"] == "ecommerce_backend"

    @pytest.mark.asyncio
    async def test_workspace_get_scoped_path_absolute_path_rejected(self):
        """পপ্যুল্ট পাথ রিজেক্ট হয়।"""
        from tools.mcp.mcp_workspace import (
            ScopedFilePathInput,
            workspace_get_scoped_path,
        )

        params = ScopedFilePathInput(relative_path="/etc/passwd")
        result = await workspace_get_scoped_path(params)
        data = json.loads(result)
        assert data["error"] == "Invalid path"

    @pytest.mark.asyncio
    async def test_workspace_get_scoped_path_symlink_outside_workspace(self, tmp_path):
        """সিমলিংক ওয়ার্কস্পেসের বাইরে ফাইল নির্দেশ করলে রিজেক্ট হয়।"""
        from tools.mcp.mcp_workspace import (
            ScopedFilePathInput,
            workspace_get_scoped_path,
        )

        # একটি টেস্ট ফাইল তৈরি করে সিমলিংক তৈরি করা হচ্ছে
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        symlink_path = tmp_path / "symlink.txt"
        try:
            symlink_path.symlink_to(test_file)
        except OSError as exc:
            # #1409: was silent `pass` (TODO(#1011)) — an env without symlink
            # support must SKIP visibly, not continue into a broken fixture.
            pytest.skip(f"symlink not supported on this filesystem: {exc}")

        params = ScopedFilePathInput(relative_path=str(symlink_path))
        result = await workspace_get_scoped_path(params)
        data = json.loads(result)
        assert data["error"] == "Invalid path"

    @pytest.mark.asyncio
    async def test_workspace_list_projects_with_session(self, tmp_path):
        """Workspace List Projects সেশন সহ কাজ করে।"""
        import json

        from tools.mcp.mcp_workspace import (
            WORKSPACE_SESSION_FILE,
            workspace_list_projects,
        )

        # সেশন ফাইল তৈরি করা
        WORKSPACE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        session_data = {
            "project_type": "ecommerce_backend",
            "tenant_id": "test-tenant",
            "workspace_path": "backend",
        }
        WORKSPACE_SESSION_FILE.write_text(json.dumps(session_data), encoding="utf-8")

        try:
            result = await workspace_list_projects()
            data = json.loads(result)
            assert data["current_session"] is not None
            assert data["current_session"]["project_type"] == "ecommerce_backend"
        finally:
            if WORKSPACE_SESSION_FILE.exists():
                WORKSPACE_SESSION_FILE.unlink()


class TestHelperFunctions:
    """MCP সার্ভারগুলোর হেল্পার ফাংশনগুলোর টেস্ট।"""

    def test_check_admin_auth_true(self, monkeypatch):
        """অ্যাডমিন অথেন্টিকেশন সঠিকভাবে চেক হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import _check_admin_auth

        assert _check_admin_auth() is True

    def test_check_admin_auth_false(self, monkeypatch):
        """অ্যাডমিন অথেন্টিকেশন না থাকলে False রিটার্ন করে।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        from tools.mcp.mcp_cloud_deploy import _check_admin_auth

        assert _check_admin_auth() is False

    def test_check_admin_auth_default(self):
        """অ্যাডমিন অথেন্টিকেশন ডিফল্টভাবে False।"""
        import os

        # যদি ভ্যারিয়েবল না থাকে
        if "ADMIN_AUTHORIZED" in os.environ:
            del os.environ["ADMIN_AUTHORIZED"]

        from tools.mcp.mcp_cloud_deploy import _check_admin_auth

        assert _check_admin_auth() is False

    def test_handle_api_error_401(self):
        """API এরর 401 স্ট্যান্ডার্ডাইজ্ড হ্যান্ডল হয়।"""
        from tools.mcp.mcp_cloud_deploy import _handle_api_error

        result = _handle_api_error(Exception("error"), 401)
        assert "Invalid API key" in result

    def test_handle_api_error_404(self):
        """API এরর 404 স্ট্যান্ডার্ডাইজ্ড হ্যান্ডল হয়।"""
        from tools.mcp.mcp_cloud_deploy import _handle_api_error

        result = _handle_api_error(Exception("error"), 404)
        assert "Service not found" in result

    def test_handle_api_error_429(self):
        """API এরর 429 স্ট্যান্ডার্ডাইজ্ড হ্যান্ডল হয়।"""
        from tools.mcp.mcp_cloud_deploy import _handle_api_error

        result = _handle_api_error(Exception("error"), 429)
        assert "Rate limit exceeded" in result

    def test_handle_api_error_generic(self):
        """জেনেরিক API এরর স্ট্যান্ডার্ডাইজ্ড হ্যান্ডল হয়।"""
        from tools.mcp.mcp_cloud_deploy import _handle_api_error

        result = _handle_api_error(ValueError("test error"))
        assert "Error" in result


class TestInputValidation:
    """ইনপুট ভ্যালিডেশন টেস্টস।"""

    def test_deploy_service_input_branch_default(self):
        """DeployServiceInput এ ব্রাঞ্চের ডিফল্ট মান।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, DeployServiceInput

        params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
        assert params.branch == "main"

    def test_deploy_service_input_strip_whitespace(self):
        """DeployServiceInput এ হোয়াইটস্পেস স্ট্রিপ হয়।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, DeployServiceInput

        params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="  test-service  ")
        assert params.service_name == "test-service"

    def test_deploy_service_input_service_name_pattern(self):
        """DeployServiceInput এ সার্ভিস নেম প্যাটার্ন ভ্যালিডেশন।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, DeployServiceInput

        with pytest.raises(ValidationError):
            DeployServiceInput(provider=CloudProvider.RENDER, service_name="invalid name!")

    def test_get_logs_input_lines_default(self):
        """GetLogsInput এ লাইনসের ডিফল্ট মান।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, GetLogsInput

        params = GetLogsInput(provider=CloudProvider.RENDER, service_name="test")
        assert params.lines == 100

    def test_get_logs_input_lines_validation(self):
        """GetLogsInput এ লাইনসের ভ্যালিডেশন।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, GetLogsInput

        with pytest.raises(ValidationError):
            GetLogsInput(provider=CloudProvider.RENDER, service_name="test", lines=0)

        with pytest.raises(ValidationError):
            GetLogsInput(provider=CloudProvider.RENDER, service_name="test", lines=1001)

    def test_create_table_input_if_not_exists_default(self):
        """CreateTableInput এ if_not_exists এর ডিফল্ট মান।"""
        from tools.mcp.mcp_supabase import CreateTableInput

        params = CreateTableInput(table_name="users", columns="id INT")
        assert params.if_not_exists is True

    def test_migration_input_validation(self):
        """MigrationInput এর ইনপুট ভ্যালিডেশন।"""
        from tools.mcp.mcp_supabase import MigrationInput

        with pytest.raises(ValidationError):
            MigrationInput(
                migration_name="",
                up_sql="CREATE TABLE test (id INT)",
                down_sql="DROP TABLE test",
            )

        with pytest.raises(ValidationError):
            MigrationInput(migration_name="test", up_sql="", down_sql="DROP TABLE test")

        with pytest.raises(ValidationError):
            MigrationInput(migration_name="test", up_sql="CREATE TABLE test (id INT)", down_sql="")

    def test_execute_query_input_params_default(self):
        """ExecuteQueryInput এ params ডিফল্ট মান।"""
        from tools.mcp.mcp_supabase import ExecuteQueryInput

        params = ExecuteQueryInput(query="SELECT 1")
        assert params.params == []

    def test_create_table_input_columns_validation(self):
        """CreateTableInput এ columns ভ্যালিডেশন।"""
        from tools.mcp.mcp_supabase import CreateTableInput

        with pytest.raises(ValidationError):
            CreateTableInput(table_name="users", columns="")

    def test_deploy_service_input_invalid_branch(self):
        """DeployServiceInput এ অবৈধ ব্রাঞ্চ রিজেক্ট হয়।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, DeployServiceInput

        with pytest.raises(ValidationError):
            DeployServiceInput(
                provider=CloudProvider.RENDER,
                service_name="test",
                branch="invalid;branch",
            )

    def test_get_logs_input_invalid_lines(self):
        """GetLogsInput এ অবৈধ লাইনস রিজেক্ট হয়।"""
        from tools.mcp.mcp_cloud_deploy import CloudProvider, GetLogsInput

        with pytest.raises(ValidationError):
            GetLogsInput(provider=CloudProvider.RENDER, service_name="test", lines=-1)

    def test_create_pr_input_validation_complete(self):
        """CreatePRInput এর সম্পূর্ণ ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_github_cicd import CreatePRInput

        with pytest.raises(ValidationError):
            CreatePRInput(title="", body="Test", head="feature", base="main")

        with pytest.raises(ValidationError):
            CreatePRInput(title="Test", body="", head="feature", base="main")

        with pytest.raises(ValidationError):
            CreatePRInput(title="Test", body="Test", head="", base="main")

    def test_fix_issue_input_validation_complete(self):
        """FixIssueInput এর সম্পূর্ণ ভ্যালিডেশন টেস্ট।"""
        from tools.mcp.mcp_github_cicd import FixIssueInput

        with pytest.raises(ValidationError):
            FixIssueInput(issue_number=0, branch="fix")

        with pytest.raises(ValidationError):
            FixIssueInput(issue_number=1, branch="")

    @pytest.mark.asyncio
    async def test_deploy_service_render_success(self, monkeypatch):
        """Render-এ সফল ডিপ্লয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "created",
            "url": "https://render.com/test",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test-service")
            result = await cloud_deploy_service(params)
            data = json.loads(result)
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_deploy_service_removed_providers_never_reach_http(self):
        """(#3077) Railway/Oracle প্রোভাইডার সরানো — deploy/log কোনো পাথেই নির্বাচনযোগ্য নয়।"""
        from pydantic import ValidationError as PydanticValidationError

        from tools.mcp.mcp_cloud_deploy import GetLogsInput

        with pytest.raises(PydanticValidationError):
            GetLogsInput(provider="railway", service_name="test-service")
        with pytest.raises(PydanticValidationError):
            GetLogsInput(provider="oracle", service_name="test-service")

    @pytest.mark.asyncio
    async def test_get_logs_render_success(self, monkeypatch):
        """Render-এ সফল লগ রিট্রিভাল।"""
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            GetLogsInput,
            cloud_get_deployment_logs,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"logs": ["log line 1", "log line 2"]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = GetLogsInput(
                provider=CloudProvider.RENDER, service_name="test-service", lines=50
            )
            result = await cloud_get_deployment_logs(params)
            data = json.loads(result)
            assert data["provider"] == "render"

    @pytest.mark.asyncio
    async def test_list_services_render_only(self, monkeypatch):
        """কেবলমাত্র Render সার্ভিস লিস্ট করা হয়।"""
        # বাংলা মন্তব্য (#3077): Railway/Oracle লেগ সরানো — কেবল Render-ই প্রোব হয়।

        from tools.mcp.mcp_cloud_deploy import cloud_list_services

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"serviceName": "svc1", "status": "active", "url": "https://test.com"}
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await cloud_list_services()
            data = json.loads(result)
            assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_list_services_unconfigured_render_only(self, monkeypatch):
        """(#3077) RENDER_API_KEY আনসেট হলে তালিকা খালি — Railway লেগ আর নেই।"""
        monkeypatch.setenv("RENDER_API_KEY", "")

        from tools.mcp.mcp_cloud_deploy import cloud_list_services

        result = await cloud_list_services()
        data = json.loads(result)
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_list_services_render_error(self, monkeypatch):
        """Render API এ রিকোয়েস্ট ফেইল করে।"""
        from tools.mcp.mcp_cloud_deploy import cloud_list_services

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await cloud_list_services()
            data = json.loads(result)
            assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_deploy_service_api_error_500(self, monkeypatch):
        """API এরর 500 হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_deploy_service(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_deploy_service_api_error_503(self, monkeypatch):
        """API এরর 503 হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            DeployServiceInput,
            cloud_deploy_service,
        )

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = DeployServiceInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_deploy_service(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_get_logs_api_error_500(self, monkeypatch):
        """Get Logs এ API এরর 500 হ্যান্ডল হয়।"""
        from tools.mcp.mcp_cloud_deploy import (
            CloudProvider,
            GetLogsInput,
            cloud_get_deployment_logs,
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = GetLogsInput(provider=CloudProvider.RENDER, service_name="test")
            result = await cloud_get_deployment_logs(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_github_create_pr_success(self, monkeypatch):
        """GitHub-এ সফল PR তৈরি।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_github_cicd import CreatePRInput, github_create_pull_request

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 42,
            "html_url": "https://github.com/test/pull/42",
            "state": "open",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            # MESH-7 (#925): issue-first policy requires an issue-link in the
            # PR body BEFORE the API call — payloads must satisfy the gate.
            params = CreatePRInput(
                title="Test PR", body="Fixes #42", head="feature", base="develop"
            )
            result = await github_create_pull_request(params)
            data = json.loads(result)
            assert data["success"] is True
            assert data["pr_number"] == 42

    @pytest.mark.asyncio
    async def test_github_create_pr_api_error_404(self, monkeypatch):
        """PR তৈরি করতে 404 এরর হ্যান্ডল হয়।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_github_cicd import CreatePRInput, github_create_pull_request

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            # Issue-first gate (#925) must pass so the API error path is reached.
            params = CreatePRInput(title="Test", body="Fixes #42", head="feature", base="main")
            result = await github_create_pull_request(params)
            assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_github_run_auto_fix_success(self, monkeypatch):
        """GitHub-এ সফল অটো-ফিক্স।"""
        monkeypatch.setenv("AUTOFIX_AUTHORIZED", "true")
        from tools.mcp.mcp_github_cicd import FixIssueInput, github_run_auto_fix

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=MagicMock())
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = FixIssueInput(issue_number=42, branch="fix/issue-42")
            result = await github_run_auto_fix(params)
            data = json.loads(result)
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_github_run_auto_fix_api_error(self, monkeypatch):
        """অটো-ফিক্স এ এপিআই এরর।"""
        monkeypatch.setenv("AUTOFIX_AUTHORIZED", "true")
        from tools.mcp.mcp_github_cicd import FixIssueInput, github_run_auto_fix

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            params = FixIssueInput(issue_number=42, branch="fix/issue-42")
            result = await github_run_auto_fix(params)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_github_list_issues_success(self, monkeypatch):
        """GitHub-এ সফল ইস্যু লিস্ট।"""
        from tools.mcp.mcp_github_cicd import github_list_issues

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Issue 1",
                "state": "open",
                "labels": [],
                "html_url": "https://github.com/test/issues/1",
            },
            {
                "number": 2,
                "title": "Issue 2",
                "state": "closed",
                "labels": [{"name": "bug"}],
                "html_url": "https://github.com/test/issues/2",
            },
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_list_issues(state="all")
            data = json.loads(result)
            assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_github_list_issues_with_labels(self, monkeypatch):
        """লেবেল ফিল্টার সহ ইস্যু লিস্ট।"""
        from tools.mcp.mcp_github_cicd import github_list_issues

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Bug",
                "state": "open",
                "labels": [{"name": "bug"}],
                "html_url": "https://github.com/test/issues/1",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_list_issues(state="open", labels="bug")
            data = json.loads(result)
            assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_github_list_issues_api_error(self, monkeypatch):
        """ইস্যু লিস্টে এপিআই এরর।"""
        from tools.mcp.mcp_github_cicd import github_list_issues

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_list_issues()
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_github_get_ci_status_success(self, monkeypatch):
        """GitHub-এ সফল CI স্ট্যাটাস।"""
        from tools.mcp.mcp_github_cicd import github_get_ci_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "success",
            "statuses": [{"context": "ci/test", "state": "success"}],
            "total_count": 1,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_get_ci_status(branch="main")
            data = json.loads(result)
            assert data["state"] == "success"

    @pytest.mark.asyncio
    async def test_github_get_ci_status_api_error(self, monkeypatch):
        """CI স্ট্যাটাসে এপিআই এরর।"""
        from tools.mcp.mcp_github_cicd import github_get_ci_status

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)

            result = await github_get_ci_status()
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_select_json(self, monkeypatch):
        """SELECT কুয়েরি JSON ফরম্যাটে রিটার্ন।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [(1, "Alice"), (2, "Bob")]
            mock_cursor.description = [("id",), ("name",)]
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM users", response_format=ResponseFormat.JSON
            )
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["row_count"] == 2
            assert data["columns"] == ["id", "name"]

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_select_markdown(self, monkeypatch):
        """SELECT কুয়েরি Markdown ফরম্যাটে রিটার্ন।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.description = []
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM users WHERE id = 1",
                response_format=ResponseFormat.MARKDOWN,
            )
            result = await supabase_execute_sql(params)
            assert "# Query Results" in result

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_insert(self, monkeypatch):
        """INSERT কুয়েরি সফল হয়।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 1
            mock_cursor.description = None
            mock_conn.return_value = MagicMock(
                cursor=lambda: mock_cursor, commit=MagicMock(), close=MagicMock()
            )

            params = ExecuteQueryInput(
                query="INSERT INTO users (name) VALUES ('Alice')",
                response_format=ResponseFormat.JSON,
            )
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_with_params(self, monkeypatch):
        """Parameterized কুয়েরি সফল হয়।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [(1,)]
            mock_cursor.description = [("id",)]
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM users WHERE id = %s",
                params=[1],
                response_format=ResponseFormat.JSON,
            )
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["row_count"] == 1

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_connection_error(self, monkeypatch):
        """ডাটাবেস কানেকশন ব্যর্থ।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_conn.return_value = None

            params = ExecuteQueryInput(query="SELECT 1", response_format=ResponseFormat.JSON)
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["error"] == "Failed to connect to database"

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_sql_error(self, monkeypatch):
        """SQL এরর হ্যান্ডল হয়।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("syntax error at line 1")
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM invalid", response_format=ResponseFormat.JSON
            )
            result = await supabase_execute_sql(params)
            assert "SQL syntax error" in result

    @pytest.mark.asyncio
    async def test_execute_sql_connection_error(self, monkeypatch):
        """Execute SQL এ কানেকশন এরর।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_conn.return_value = None

            params = ExecuteQueryInput(query="SELECT 1", response_format=ResponseFormat.JSON)
            result = await supabase_execute_sql(params)
            data = json.loads(result)
            assert data["error"] == "Failed to connect to database"

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_no_rows(self, monkeypatch):
        """SELECT কুয়েরি কোন রো রিটার্ন করে না।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.description = []
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM empty_table",
                response_format=ResponseFormat.MARKDOWN,
            )
            result = await supabase_execute_sql(params)
            assert "No rows returned" in result

    @pytest.mark.asyncio
    async def test_supabase_execute_sql_rows_limited(self, monkeypatch):
        """SELECT কুয়েরি ১০০ রো-এর বেশি রিটার্ন করে।"""
        from tools.mcp.mcp_supabase import (
            ExecuteQueryInput,
            ResponseFormat,
            supabase_execute_sql,
        )

        rows = [(i, f"name{i}") for i in range(150)]

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = rows
            mock_cursor.description = [("id",), ("name",)]
            mock_conn.return_value = MagicMock(cursor=lambda: mock_cursor, close=MagicMock())

            params = ExecuteQueryInput(
                query="SELECT * FROM large_table",
                response_format=ResponseFormat.MARKDOWN,
            )
            result = await supabase_execute_sql(params)
            assert "Showing 100 of 150 rows" in result

    @pytest.mark.asyncio
    async def test_supabase_create_table_without_if_not_exists(self, monkeypatch):
        """IF NOT EXISTS ছাড়া টেবিল তৈরি।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_supabase import CreateTableInput, supabase_create_table

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_conn.return_value = MagicMock(
                cursor=MagicMock(), commit=MagicMock(), close=MagicMock()
            )

            params = CreateTableInput(
                table_name="logs", columns="id SERIAL PRIMARY KEY", if_not_exists=False
            )
            result = await supabase_create_table(params)
            data = json.loads(result)
            assert data["success"] is True

        """মাইগ্রেশন ইতিমধ্যে আপ্লাই করা হয়েছে (ডিটেইলড)।"""
        monkeypatch.setenv("ADMIN_AUTHORIZED", "true")
        from tools.mcp.mcp_supabase import MigrationInput, supabase_run_migration

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [1]
            mock_conn.return_value = MagicMock(
                cursor=lambda: mock_cursor, commit=MagicMock(), close=MagicMock()
            )

            params = MigrationInput(
                migration_name="existing_migration",
                up_sql="CREATE TABLE test (id INT)",
                down_sql="DROP TABLE test",
            )
            result = await supabase_run_migration(params)
            data = json.loads(result)
            assert "already applied" in data["message"]

        """মাইগ্রেশন সফল হলে DOWN SQL এক্সিকিউট হয় না।"""
        from tools.mcp.mcp_supabase import MigrationInput, supabase_run_migration

        with patch("tools.mcp.mcp_supabase._get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.return_value = MagicMock(
                cursor=lambda: mock_cursor, commit=MagicMock(), close=MagicMock()
            )

            params = MigrationInput(
                migration_name="test",
                up_sql="CREATE TABLE test (id INT)",
                down_sql="DROP TABLE test",
            )
            result = await supabase_run_migration(params)
            data = json.loads(result)
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_workspace_list_projects_json_error(self, tmp_path):
        """ওয়ার্কস্পেস লিস্টে JSON ডিকোড এরর।"""
        from tools.mcp.mcp_workspace import (
            WORKSPACE_SESSION_FILE,
            workspace_list_projects,
        )

        WORKSPACE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKSPACE_SESSION_FILE.write_text("invalid json{", encoding="utf-8")

        try:
            result = await workspace_list_projects()
            data = json.loads(result)
            assert data["current_session"] is None
        finally:
            if WORKSPACE_SESSION_FILE.exists():
                WORKSPACE_SESSION_FILE.unlink()

    @pytest.mark.asyncio
    async def test_workspace_list_projects_io_error(self, tmp_path):
        """ওয়ার্কস্পেস লিস্টে IO এরর।"""
        from tools.mcp.mcp_workspace import (
            WORKSPACE_SESSION_FILE,
            workspace_list_projects,
        )

        WORKSPACE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKSPACE_SESSION_FILE.write_text("{}", encoding="utf-8")

        try:
            result = await workspace_list_projects()
            data = json.loads(result)
            assert data["projects"] is not None
        finally:
            if WORKSPACE_SESSION_FILE.exists():
                WORKSPACE_SESSION_FILE.unlink()

    def test_workspace_config_relative_path_with_workspace_key(self, tmp_path):
        """ওয়ার্কস্পেস কনফিগারেশন রিলেটিভ পাথ রিলেটিভ পাথ কনভার্ট হয়।"""
        from tools.mcp.mcp_workspace import (
            WORKSPACE_CONFIG_FILE,
            _load_workspace_config,
        )

        config_data = {"workspace": {"ecommerce_backend": "custom/backend/path"}}
        WORKSPACE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKSPACE_CONFIG_FILE.write_text(json.dumps(config_data), encoding="utf-8")

        try:
            config = _load_workspace_config()
            assert "ecommerce_backend" in config["workspace"]
        finally:
            if WORKSPACE_CONFIG_FILE.exists():
                WORKSPACE_CONFIG_FILE.unlink()

    def test_workspace_get_workspace_path_with_config(self, tmp_path):
        """ওয়ার্কস্পেস পাথ কনফিগারেশন সহ রিট্রিভ করা হয়।"""
        from tools.mcp.mcp_workspace import (
            WORKSPACE_CONFIG_FILE,
            WorkspaceType,
            _get_workspace_path,
        )

        config_data = {"workspace": {"ecommerce_backend": "custom/backend"}}
        WORKSPACE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKSPACE_CONFIG_FILE.write_text(json.dumps(config_data), encoding="utf-8")

        try:
            path = _get_workspace_path(WorkspaceType.ECOMMERCE_BACKEND)
            assert "custom/backend" in str(path).replace("\\", "/")
        finally:
            if WORKSPACE_CONFIG_FILE.exists():
                WORKSPACE_CONFIG_FILE.unlink()

    def test_workspace_get_workspace_path_absolute(self, tmp_path):
        """ওয়ার্কস্পেস পাথ যদি অ্যাবসোলিট হয় তবে তা ব্যবহার হয়।"""
        from tools.mcp.mcp_workspace import (
            WORKSPACE_CONFIG_FILE,
            WorkspaceType,
            _get_workspace_path,
        )

        abs_path = str(tmp_path / "absolute" / "path")
        config_data = {"workspace": {"ecommerce_backend": abs_path}}
        WORKSPACE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKSPACE_CONFIG_FILE.write_text(json.dumps(config_data), encoding="utf-8")

        try:
            path = _get_workspace_path(WorkspaceType.ECOMMERCE_BACKEND)
            assert str(path).endswith(abs_path.replace("/", os.sep).replace("\\", os.sep))
        finally:
            if WORKSPACE_CONFIG_FILE.exists():
                WORKSPACE_CONFIG_FILE.unlink()


class TestNeonMCPExtended:
    """mcp_neon.py এর টেস্ট স্যুট।"""

    def test_execute_query_input_validation(self):
        from tools.mcp.mcp_neon import ExecuteQueryInput, ResponseFormat

        valid = ExecuteQueryInput(query="SELECT 1;", response_format=ResponseFormat.JSON)
        assert valid.query == "SELECT 1;"
        assert valid.response_format == ResponseFormat.JSON

    def test_branch_input_validation(self):
        from tools.mcp.mcp_neon import CreateBranchInput, DeleteBranchInput, ListBranchesInput

        create_in = CreateBranchInput(project_id="test-proj", branch_name="feat-db")
        assert create_in.branch_name == "feat-db"

        delete_in = DeleteBranchInput(project_id="test-proj", branch_id="br-123")
        assert delete_in.branch_id == "br-123"

        list_in = ListBranchesInput(project_id="test-proj")
        assert list_in.project_id == "test-proj"

    @pytest.mark.asyncio
    async def test_execute_sql_destructive_without_admin(self, monkeypatch):
        from tools.mcp.mcp_neon import ExecuteQueryInput, neon_execute_sql

        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        result = await neon_execute_sql(ExecuteQueryInput(query="DROP TABLE test;"))
        data = json.loads(result)
        assert "error" in data
        assert "Admin authorization required" in data["error"]

    @pytest.mark.asyncio
    async def test_execute_sql_success_select(self, monkeypatch):
        from tools.mcp.mcp_neon import ExecuteQueryInput, ResponseFormat, neon_execute_sql

        monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://user:pass@localhost:5432/neondb")
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.description = [("id",), ("name",)]
        mock_cur.fetchall.return_value = [(1, "Test Item")]
        mock_conn.cursor.return_value = mock_cur

        with patch("tools.mcp.mcp_neon._get_connection", return_value=mock_conn):
            result = await neon_execute_sql(
                ExecuteQueryInput(query="SELECT * FROM items;", response_format=ResponseFormat.JSON)
            )
            data = json.loads(result)
            assert len(data) == 1
            assert data[0]["name"] == "Test Item"

    @pytest.mark.asyncio
    async def test_create_branch_missing_admin(self, monkeypatch):
        from tools.mcp.mcp_neon import CreateBranchInput, neon_create_branch

        monkeypatch.setenv("ADMIN_AUTHORIZED", "false")
        result = await neon_create_branch(
            CreateBranchInput(project_id="test-proj", branch_name="feat-1")
        )
        data = json.loads(result)
        assert "error" in data
        assert "Admin authorization required" in data["error"]
