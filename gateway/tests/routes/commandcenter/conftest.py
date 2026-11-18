from unittest.mock import patch

import pytest
from api.dependencies import get_current_admin, get_current_user_token
from fastapi.testclient import TestClient

from core.app import app

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


@pytest.fixture(autouse=True)
def override_admin_auth():
    admin_claims = {"sub": "admin@supremeai.test", "role": "admin"}
    for dep in (get_current_user_token, get_current_admin):
        app.dependency_overrides[dep] = lambda claims=admin_claims: claims
    with patch("core.security.authentication.auth_middleware._decode_jwt", return_value=admin_claims):
        yield
    for dep in (get_current_user_token, get_current_admin):
        app.dependency_overrides.pop(dep, None)
