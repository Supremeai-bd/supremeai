"""gateway/services/rbac.py — minimal RBAC role/permission model (Phase D.1)."""
from __future__ import annotations

from enum import Enum
from typing import FrozenSet


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Permission catalogue
PERMISSIONS: dict[str, FrozenSet[str]] = {
    Role.ADMIN: frozenset({"read", "write", "delete", "manage_users", "manage_keys", "approve_hitl"}),
    Role.OPERATOR: frozenset({"read", "write", "approve_hitl"}),
    Role.VIEWER: frozenset({"read"}),
}


def has_permission(role: str | Role, permission: str) -> bool:
    try:
        r = role if isinstance(role, Role) else Role(role)
    except ValueError:
        return False
    return permission in PERMISSIONS.get(r, frozenset())


def role_for(value: str) -> Role | None:
    try:
        return Role(value)
    except ValueError:
        return None
