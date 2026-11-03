from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_current_admin, get_current_user_token

# বাংলা মন্তব্য: মেইন মডিউলের বদলে core.app থেকে সরাসরি app ইমপোর্ট করা হলো
from core.app import app

client = TestClient(app)


@pytest.fixture
def mock_admin_token():
    with patch("api.dependencies.get_current_user_token") as mock:
        mock.return_value = {"sub": "admin_test", "role": "admin"}
        yield mock


@pytest.fixture
def mock_healer():
    with patch("api.routes.admin.get_healer_service") as mock:
        service = MagicMock()
        service.apply_fix = AsyncMock(return_value=True)
        mock.return_value = service
        yield mock


@pytest.fixture
def mock_firestore():
    with patch("api.routes.admin.get_firestore_db") as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


@patch("api.dependencies.get_current_user_token")
@patch("core.security.authentication.auth_middleware._decode_jwt")
def test_get_fixes_unauthorized(mock_decode_jwt, mock_token):
    mock_decode_jwt.return_value = {"sub": "user_test", "role": "user"}
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "user_test",
        "role": "user",
    }

    # We must also clear the get_current_admin override if it exists, or just mock it to raise 403
    app.dependency_overrides[get_current_admin] = lambda: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(status_code=403, detail="Not enough permissions")
    )

    response = client.get("/api/admin/fixes", headers={"Authorization": "Bearer dummy"})
    assert response.status_code in (
        401,
        403,
    ), f"Unexpected status: {response.status_code}, details: {response.text}"
    app.dependency_overrides = {}


@patch("api.dependencies.get_current_user_token")
@patch("core.security.authentication.auth_middleware._decode_jwt")
def test_get_fixes_authorized(mock_decode_jwt, mock_token, mock_healer, mock_firestore):
    mock_decode_jwt.return_value = {"sub": "admin_test", "role": "admin"}
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin_test",
        "role": "admin",
    }

    # Mocking Firestore response
    mock_query = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "fix_1"
    mock_doc.to_dict.return_value = {"status": "pending_review"}

    # Async mock for get()
    async def mock_get():
        return [mock_doc]

    mock_query.get = mock_get
    mock_firestore.collection.return_value.document.return_value.collection.return_value.where.return_value = mock_query

    app.dependency_overrides[get_current_admin] = lambda: {
        "sub": "admin_test",
        "role": "admin",
    }

    response = client.get(
        "/api/admin/fixes?tenant_id=test", headers={"Authorization": "Bearer dummy"}
    )
    assert response.status_code == 200, (
        f"Unexpected status: {response.status_code}, details: {response.text}"
    )
    assert "fixes" in response.json()
    assert len(response.json()["fixes"]) == 1

    app.dependency_overrides = {}


@patch("api.routes.admin.god_layer")
@patch("api.routes.admin.redis_manager")
@patch("database.session.get_db_session")
@patch("api.dependencies.get_current_user_token")
@patch("core.security.authentication.auth_middleware._decode_jwt")
def test_quick_actions_success(
    mock_decode_jwt,
    mock_token,
    mock_db_session,
    mock_redis_manager,
    mock_god_layer,
):
    """বাংলা: নতুন রিয়েল কুইক অ্যাকশন (cache/backup/rollback) সফলভাবে সম্পন্ন হচ্ছে কিনা যাচাই করে।"""
    from unittest.mock import MagicMock

    mock_downgrade = MagicMock(return_value=None)
    mock_config = MagicMock()
    mock_config.set_main_option = MagicMock(return_value=None)

    with patch("alembic.command.downgrade", mock_downgrade):
        with patch("alembic.config.Config", return_value=mock_config):
            mock_decode_jwt.return_value = {"sub": "admin_test", "role": "admin"}
            app.dependency_overrides[get_current_user_token] = lambda: {
                "sub": "admin_test",
                "role": "admin",
            }

            app.dependency_overrides[get_current_admin] = lambda: {
                "sub": "admin_test",
                "role": "admin",
            }

            # Redis mock — #2830: প্রোডাকশন D-4 fix (#2733)/#2790 থেকে SCAN-ভিত্তিক
            # selective purge চুক্তিতে গেছে (blocking KEYS বাদ) — পুরনো keys()-মক
            # স্টেল; scan_iter এখন প্যাটার্ন-প্রতি async-iterator ফেরত দেয়।
            mock_redis_client = AsyncMock()
            _scan_plan = {
                "bhasha_bot:*": ["bhasha_bot:k1"],
                "user_profile:*": ["user_profile:u1"],
                "semantic_cache:*": ["semantic_cache:s1"],
                "cache:*": ["cache:test_key", "cache:test_key_2"],
                "health:*": ["health:h1"],
            }

            def _fake_scan_iter(*args, **kwargs):
                # বাংলা মন্তব্য: প্রোডাকশন `async for ... scan_iter(match=…)` চুক্তি —
                # কলের ফলাফল অবশ্যই __aiter__ যুক্ত অবজেক্ট (async generator) হতে হবে।
                matched = list(_scan_plan.get(kwargs.get("match"), []))

                async def _gen():
                    for key in matched:
                        yield key

                return _gen()

            mock_redis_client.scan_iter = _fake_scan_iter
            mock_redis_client.delete = AsyncMock(return_value=1)
            mock_redis_manager.client = mock_redis_client

            # DB session mock for backup
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()

            mock_result_tables = MagicMock()
            mock_result_tables.fetchall.return_value = [("test_table",)]

            mock_result_rows = MagicMock()
            mock_result_rows.keys.return_value = ["id"]
            mock_result_rows.fetchall.return_value = [("row_id",)]

            mock_session.execute.side_effect = [mock_result_tables, mock_result_rows]

            async def mock_generator():
                yield mock_session

            mock_db_session.return_value = mock_generator()

            # Test cache action
            response = client.post(
                "/api/admin/actions/cache", headers={"Authorization": "Bearer dummy"}
            )
            assert response.status_code == 200
            assert "Deleted 6 keys" in response.json()["message"]

            # Test backup action
            response = client.post(
                "/api/admin/actions/backup", headers={"Authorization": "Bearer dummy"}
            )
            assert response.status_code == 200
            assert "backup" in response.json()["message"]

            # Test rollback action
            response = client.post(
                "/api/admin/actions/rollback", headers={"Authorization": "Bearer dummy"}
            )
            assert response.status_code == 200
            mock_downgrade.assert_called_once()

            app.dependency_overrides = {}


@patch("api.routes.admin.god_layer")
@patch("api.dependencies.get_current_user_token")
@patch("core.security.authentication.auth_middleware._decode_jwt")
def test_quick_action_unknown_returns_404(mock_decode_jwt, mock_token, mock_god_layer):
    mock_decode_jwt.return_value = {"sub": "admin_test", "role": "admin"}
    app.dependency_overrides[get_current_user_token] = lambda: {
        "sub": "admin_test",
        "role": "admin",
    }

    app.dependency_overrides[get_current_admin] = lambda: {
        "sub": "admin_test",
        "role": "admin",
    }

    response = client.post(
        "/api/admin/actions/not_a_real_action",
        headers={"Authorization": "Bearer dummy"},
    )
    assert response.status_code == 404

    app.dependency_overrides = {}
