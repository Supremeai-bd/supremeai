from unittest.mock import MagicMock, patch

import pytest

from api.routes.workspaces_route import (
    BindTargetRequest,
    bind_target_repository,
    list_target_repositories,
)
from core.target_registry import PermissionScope, TargetPlatformType

_VALID_OTP = "123456"
_TOTP_PATCH = "api.routes.workspaces_route.check_totp_code"


@pytest.mark.asyncio
async def test_bind_target_repository_returns_registered_target():
    req = BindTargetRequest(
        target_id="workspace-1",
        name="Workspace One",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="https://github.com/example/workspace-1",
        branch="main",
        scope=PermissionScope.FULL_CONTROL,
        metadata={"env": "test"},
    )
    registered = MagicMock()
    registered.id = req.target_id
    registered.name = req.name
    registered.target_type = req.target_type
    registered.url = req.url
    registered.branch = req.branch
    registered.scope = req.scope
    registered.is_read_only.return_value = False
    registered.can_write.return_value = True

    with (
        patch(
            "api.routes.workspaces_route.target_registry.register_target", return_value=registered
        ) as register,
        patch("api.routes.workspaces_route.repo_manager.prepare_workspace") as prepare,
        patch(_TOTP_PATCH, return_value=True),
    ):
        response = await bind_target_repository(req, x_jit_otp=_VALID_OTP)

    register.assert_called_once()
    target = register.call_args.args[0]
    assert target.id == req.target_id
    assert target.scope == PermissionScope.FULL_CONTROL
    prepare.assert_called_once_with(registered)
    assert response.id == req.target_id
    assert response.can_write is True
    assert response.is_read_only is False


@pytest.mark.asyncio
async def test_bind_target_repository_degrades_when_workspace_preparation_fails():
    req = BindTargetRequest(
        target_id="workspace-readonly",
        name="Read Only",
        url="origin/main",
        scope=PermissionScope.READ_ONLY,
    )
    registered = MagicMock()
    registered.id = req.target_id
    registered.name = req.name
    registered.target_type = req.target_type
    registered.url = req.url
    registered.branch = req.branch
    registered.scope = req.scope
    registered.is_read_only.return_value = True
    registered.can_write.return_value = False

    with (
        patch(
            "api.routes.workspaces_route.target_registry.register_target", return_value=registered
        ),
        patch(
            "api.routes.workspaces_route.repo_manager.prepare_workspace",
            side_effect=RuntimeError("disk unavailable"),
        ),
        patch(_TOTP_PATCH, return_value=True),
    ):
        response = await bind_target_repository(req, x_jit_otp=_VALID_OTP)

    assert response.scope == PermissionScope.READ_ONLY.value
    assert response.is_read_only is True
    assert response.can_write is False


@pytest.mark.asyncio
async def test_list_target_repositories_maps_registry_entities():
    first = MagicMock(
        id="one",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="origin/one",
        branch="main",
        scope=PermissionScope.READ_ONLY,
    )
    first.name = "One"
    first.is_read_only.return_value = True
    first.can_write.return_value = False

    second = MagicMock(
        id="two",
        target_type=TargetPlatformType.CLOUD_SERVICE,
        url="https://cloud.example/two",
        branch="main",
        scope=PermissionScope.FULL_CONTROL,
    )
    second.name = "Two"
    second.is_read_only.return_value = False
    second.can_write.return_value = True

    with patch(
        "api.routes.workspaces_route.target_registry.list_targets", return_value=[first, second]
    ):
        responses = await list_target_repositories()

    assert [item.id for item in responses] == ["one", "two"]
    assert responses[0].target_type == TargetPlatformType.GIT_REPOSITORY.value
    assert responses[0].scope == PermissionScope.READ_ONLY.value
    assert responses[1].target_type == TargetPlatformType.CLOUD_SERVICE.value
    assert responses[1].can_write is True
