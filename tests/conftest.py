import pytest
from core.rbac import RoleBasedAccessControl

@pytest.fixture
def rbac():
    return RoleBasedAccessControl()
