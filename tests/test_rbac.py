import datetime

import pytest

from core.rbac import RoleBasedAccessControl, UserContext, ROLE_MATRIX


def get_rbac():
    return RoleBasedAccessControl()


@pytest.mark.parametrize("role,action,expected", [
    ("owner", "read", True),
    ("owner", "admin", True),
    ("owner", "manage_users", True),
    ("admin", "audit", True),
    ("admin", "manage_users", False),
    ("operator", "write", True),
    ("operator", "admin", False),
    ("viewer", "read", True),
    ("viewer", "write", False),
    ("viewer", "admin", False),
])
def test_has_permission(rbac, role, action, expected):
    assert rbac.has_permission(role, action) == expected


def test_unknown_role_no_permission(rbac):
    assert rbac.has_permission("hacker", "read") is False


def test_check_expired_context(rbac):
    past = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    ctx = UserContext(user_id="u1", role="admin", expires_at=past)
    assert rbac.check(ctx, "read") is False


def test_check_valid_context(rbac):
    future = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
    ctx = UserContext(user_id="u1", role="admin", expires_at=future)
    assert rbac.check(ctx, "read") is True


def test_require_allowed(rbac):
    ctx = UserContext(user_id="u1", role="admin", scopes=("read", "write"))
    result = rbac.require(ctx, "read")
    assert result["allowed"] is True
    assert result["role"] == "admin"


def test_require_denied(rbac):
    ctx = UserContext(user_id="u1", role="viewer")
    result = rbac.require(ctx, "write")
    assert result["allowed"] is False
    assert result["reason"] == "Permission denied"
    assert result["action"] == "write"


def test_custom_role_matrix():
    custom = {
        "custom": type("RBAC", (), {"role": "custom", "permissions": ("read", "custom_action")})()
    }
    rbac = RoleBasedAccessControl(role_matrix=custom)
    assert rbac.has_permission("custom", "custom_action") is True
    assert rbac.has_permission("custom", "admin") is False
