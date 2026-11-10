import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rbac", ROOT / "gateway" / "services" / "rbac.py")
rbac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rbac)


def test_roles():
    assert rbac.has_permission("admin", "delete") is True
    assert rbac.has_permission("admin", "manage_keys") is True
    assert rbac.has_permission("operator", "write") is True
    assert rbac.has_permission("operator", "delete") is False
    assert rbac.has_permission("viewer", "read") is True
    assert rbac.has_permission("viewer", "write") is False
    assert rbac.has_permission("unknown", "read") is False
    assert rbac.role_for("admin") is not None
