import datetime
from datetime import UTC

import pytest

from core.security.authentication.rbac import (
    Permission,
    PermissionDeniedError,
    Role,
    RoleBasedAccessControl,
    UserContext,
    authorize,
    get_role_permissions,
    has_permission,
)


@pytest.fixture
def rbac():
    return RoleBasedAccessControl()


def test_role_enum_has_value():
    assert Role.has_value("admin") is True
    assert Role.has_value("superhero") is False


@pytest.mark.parametrize(
    "role,action,expected",
    [
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
    ],
)
def test_has_permission(rbac, role, action, expected, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "rbac_role_definitions", {})
    assert rbac.has_permission(role, action) == expected


def test_has_permission_permission_enum():
    assert has_permission(Role.OWNER, Permission.MANAGE_BILLING) is True
    assert has_permission(Role.VIEWER, Permission.WRITE) is False


def test_has_permission_string_permission_matching_enum():
    assert has_permission("admin", "write") is True


def test_has_permission_wildcard(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "rbac_role_definitions", {"superuser": ["*"]})
    assert has_permission("superuser", "any_action") is True


def test_has_permission_invalid_args_exception():
    # Force exception inside has_permission
    assert has_permission(None, None) is False


def test_authorize():
    assert authorize("owner", "read") is True
    assert authorize("viewer", "write") is False
    assert authorize("viewer", "write", context={"bypass_rbac": True}) is False


def test_unknown_role_no_permission(rbac):
    assert rbac.has_permission("hacker", "read") is False
    assert get_role_permissions("unknown_role") == frozenset()


def test_check_expired_context(rbac):
    past = (datetime.datetime.now(UTC) - datetime.timedelta(hours=1)).isoformat()
    ctx = UserContext(user_id="u1", role="admin", expires_at=past)
    assert rbac.check(ctx, "read") is False


def test_check_invalid_expires_at_format(rbac):
    ctx = UserContext(user_id="u1", role="admin", expires_at="invalid-date")
    assert rbac.check(ctx, "read") is False


def test_check_valid_context(rbac):
    future = (datetime.datetime.now(UTC) + datetime.timedelta(hours=1)).isoformat()
    ctx = UserContext(user_id="u1", role="admin", expires_at=future)
    assert rbac.check(ctx, "read") is True


def test_check_scopes(rbac):
    ctx_allowed = UserContext(user_id="u1", role="admin", scopes=("read", "write"))
    assert rbac.check(ctx_allowed, Permission.READ) is True

    ctx_denied = UserContext(user_id="u1", role="admin", scopes=("read",))
    assert rbac.check(ctx_denied, Permission.WRITE) is False


def test_require_allowed(rbac):
    ctx = UserContext(user_id="u1", role="admin", scopes=("read", "write"))
    result = rbac.require(ctx, "read")
    assert result["allowed"] is True
    assert result["role"] == "admin"


def test_require_denied(rbac):
    ctx = UserContext(user_id="u1", role="viewer")
    with pytest.raises(PermissionDeniedError) as exc_info:
        rbac.require(ctx, "write")
    assert exc_info.value.role == "viewer"
    assert exc_info.value.action == "write"


def test_custom_role_matrix():
    custom_entry = type("RBACEntry", (), {"permissions": ("read", "custom_action")})()
    custom_matrix = {
        "admin": custom_entry,
        "custom_role": custom_entry,
    }
    rbac = RoleBasedAccessControl(role_matrix=custom_matrix)
    # Role enum & Permission enum conversion
    assert rbac.has_permission(Role.ADMIN, Permission.READ) is True
    # String role & custom action
    assert rbac.has_permission("custom_role", "custom_action") is True
    # Unmatched action
    assert rbac.has_permission("custom_role", "deploy") is False
    # Unknown role in custom matrix
    assert rbac.has_permission("unknown_role", "read") is False


def test_invalid_string_permission(monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "rbac_role_definitions", {})
    assert has_permission("viewer", "invalid_permission_string") is False
