import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# বাংলা মন্তব্য: sys.modules এ ডুপ্লিকেট মডিউল তৈরি হওয়া এড়াতে এবং monkeypatch ঠিকমতো কাজ করানোর জন্য ইমপোর্ট পাথ সংশোধন করা হলো।
from api.routes import config_routes as config_route
from core.app import app

auth_headers = {"Authorization": f"Bearer {'test-token'}"}
client = TestClient(app)

import pytest


@pytest.fixture(autouse=True)
def setup_token():
    os.environ["SUPREMEAI_API_KEY"] = "test-token"
    # Red-CI fix (#1769, round 2): since issue #1570 the SecureCredentialStore
    # defaults to fail-closed — without an encryption key in the environment
    # any code path that persists credentials (e.g. the IMAP connect contract
    # exercised below) honestly fails with CredentialEncryptionUnavailableError.
    # Supply a throwaway key for the whole module, generated at runtime
    # (32-byte urlsafe-b64) so no static key material lives in the repo.
    os.environ["SUPREMEAI_CREDENTIAL_ENC_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
    try:
        yield
    finally:
        os.environ.pop("SUPREMEAI_API_KEY", None)
        os.environ.pop("SUPREMEAI_CREDENTIAL_ENC_KEY", None)


@patch("tools.social.email_agent.imaplib.IMAP4_SSL")
def test_api_email_endpoints(mock_imap_ssl):
    # গ্যাপ ফিক্স রিগ্রেশন টেস্ট: Gmail OAuth এখন real ফ্লো না থাকায় honestly 501 রিটার্ন করে,
    # আগের মতো fake 200/success নয়।
    resp = client.post(
        "/integrations/email/gmail",
        json={
            "provider": "gmail",
            "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 501

    # test /integrations/email/imap — real IMAP লগইন (মকড) যাচাই হয়ে তবেই success আসবে
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False
    mock_imap_ssl.return_value = mock_conn

    # Red-CI fix (#1769, round 2): the credential-encryption key required by
    # the fail-closed store (#1570) is provided module-wide by the autouse
    # setup_token fixture above.
    resp2 = client.post(
        "/integrations/email/imap",
        json={
            "host": "imap.gmail.com",
            "port": 993,
            "username": "supremeai@paykaribazar.com",
            "app_password": "secret_password",  # pragma: allowlist secret
        },
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "success"
    mock_conn.login.assert_called_once_with("supremeai@paykaribazar.com", "secret_password")


@patch("api.routes.github._get_agent", new_callable=AsyncMock)
def test_api_github_endpoints(mock_get_agent):
    from database.session import get_db_session

    # বাংলা মন্তব্য: get_db_session মক করা হলো যাতে greenlet বা রিয়েল ডিবি ছাড়া সিআই পরিবেশে 200 রেসপন্স নিশ্চিত হয়
    mock_sql_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_sql_session

    try:
        mock_agent = MagicMock()
        mock_agent.verify_connection = AsyncMock(return_value=True)
        mock_agent.connect_repo = AsyncMock()
        mock_agent.analyze_repo = AsyncMock(return_value={"status": "analyzed", "score": 85})
        mock_agent.improve_code = AsyncMock(return_value={"status": "improved"})
        mock_agent.commit_changes = AsyncMock(
            return_value={
                "status": "committed",
                "branch": "supremeai-improvements-1718952000",
            }
        )
        mock_agent.create_pr = AsyncMock(
            return_value={"status": "pr_created", "pr_url": "https://github.com/pulls/1"}
        )
        mock_get_agent.return_value = mock_agent

        # test /github/connect
        resp = client.post(
            "/github/connect",
            json={
                "installation_id": "from_github_app",
                "repo_owner": "owner",
                "repo_name": "repo",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "Connected to owner/repo" in resp.json()["message"]

        # test /github/improve
        resp = client.post(
            "/github/improve",
            json={"repo": "owner/repo", "branch": "main", "improvement_type": "refactor"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["analysis"]["score"] == 85

        # test /github/push — গ্যাপ ফিক্স: আর placeholder কনটেন্ট auto-generate হয় না, caller-কে
        # real file_contents সরবরাহ করতে হয়
        resp = client.post(
            "/github/push",
            json={
                "repo": "owner/repo",
                "branch": "supremeai-improvements-1718952000",
                "commit_message": "AI: Optimized database queries",
                "file_contents": {
                    "src/db.py": "# real optimized content here\n",
                    "src/cache.py": "# real optimized content here\n",
                },
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        mock_agent.commit_changes.assert_called_once()
        committed_content = mock_agent.commit_changes.call_args.args[1]
        assert committed_content == {
            "src/db.py": "# real optimized content here\n",
            "src/cache.py": "# real optimized content here\n",
        }

        # গ্যাপ ফিক্স রিগ্রেশন টেস্ট: file_contents ছাড়া push করলে ৪০০ — কখনো fabricated content
        # কমিট হবে না
        resp_empty = client.post(
            "/github/push",
            json={
                "repo": "owner/repo",
                "branch": "supremeai-improvements-1718952000",
                "commit_message": "AI: Optimized database queries",
                "file_contents": {},
            },
            headers=auth_headers,
        )
        assert resp_empty.status_code == 400

        # test /github/discover
        resp = client.post(
            "/github/discover",
            json={
                "requirement": "React component library for data tables",
                "tech_stack": ["React", "TypeScript"],
                "criteria": {"min_stars": 500},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

        # test /github/implement
        resp = client.post(
            "/github/implement",
            json={
                "repo_url": "https://github.com/TanStack/table",
                "integration_method": "npm",
                "target_project": "customer-ecommerce-app",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def test_api_marketplace_endpoints():
    # test /marketplace/search
    resp = client.post(
        "/marketplace/search",
        json={"query": "pdf", "categories": ["npm"], "filters": {"min_stars": 100}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    # Search endpoint returns a list of tools inside a dict
    assert isinstance(resp.json().get("tools"), list)
    assert resp.json()["status"] == "success"

    # test /marketplace/install
    resp = client.post(
        "/marketplace/install",
        json={
            "tool_id": "web_scraper",
            "target_environment": "supremeai-worker-01",
            "sandbox": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["installed"] is True


def test_config_endpoint_admin_control(monkeypatch):
    monkeypatch.setattr(config_route.db, "client", MagicMock())
    monkeypatch.setattr(
        config_route.db,
        "get_config",
        lambda key: (
            ["awesome-selfhosted", "libraries.io"]
            if key == "marketplace.resource_sources"
            else None
        ),
    )
    monkeypatch.setattr(config_route.db, "set_config", lambda key, value, category="general": None)

    from api.routes.admin_dashboard import require_admin_token

    app.dependency_overrides[require_admin_token] = lambda: "admin"

    resp = client.get("/config/marketplace.resource_sources", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["key"] == "marketplace.resource_sources"
    assert resp.json()["value"] == ["awesome-selfhosted", "libraries.io"]

    resp = client.put(
        "/config/marketplace.resource_sources",
        json=["awesome-python", "ossinsight"],
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    app.dependency_overrides.clear()


def test_config_endpoint_missing_key_returns_404(monkeypatch):
    # বাংলা মন্তব্য: regression test — get_config_by_key-এ HTTPException import
    # করা ছিল না, ফলে missing key request করলে 404-এর বদলে NameError দিয়ে
    # 500 crash হতো। কোনো existing test এই path কভার করতো না, তাই আগে ধরা
    # পড়েনি (ruff --select F821 দিয়ে ধরা পড়েছে)।
    monkeypatch.setattr(config_route.db, "client", MagicMock())
    monkeypatch.setattr(config_route.db, "get_config", lambda key: None)

    from api.routes.admin_dashboard import require_admin_token

    app.dependency_overrides[require_admin_token] = lambda: "admin"

    resp = client.get("/config/nonexistent.key", headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()

    app.dependency_overrides.clear()
