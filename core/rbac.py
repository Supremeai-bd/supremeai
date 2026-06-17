from __future__ import annotations

import datetime
import importlib.util
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class RBAC:
    role: str
    permissions: tuple[str, ...]


@dataclass
class UserContext:
    user_id: str
    role: str
    scopes: tuple[str, ...] = ()
    expires_at: Optional[str] = None


ROLE_MATRIX: Dict[str, RBAC] = {
    "owner": RBAC(role="owner", permissions=("read", "write", "admin", "audit", "manage_users")),
    "admin": RBAC(role="admin", permissions=("read", "write", "admin", "audit")),
    "operator": RBAC(role="operator", permissions=("read", "write")),
    "viewer": RBAC(role="viewer", permissions=("read",)),
}


class RoleBasedAccessControl:
    def __init__(self, role_matrix: Optional[Dict[str, RBAC]] = None) -> None:
        self.role_matrix = role_matrix or dict(ROLE_MATRIX)

    def has_permission(self, role: str, action: str) -> bool:
        rbac = self.role_matrix.get((role or "viewer").lower())
        if not rbac:
            return False
        return action in rbac.permissions

    def required_permission(self, action: str) -> str:
        return action

    def check(self, context: UserContext, action: str) -> bool:
        if getattr(context, "expires_at", None):
            if context.expires_at < datetime.datetime.now().isoformat():
                return False
        return self.has_permission(context.role, action)

    def require(self, context: UserContext, action: str) -> Dict[str, Any]:
        if not self.check(context, action):
            return {
                "allowed": False,
                "role": context.role,
                "action": action,
                "reason": "Permission denied",
            }
        return {"allowed": True, "role": context.role, "action": action}
