# tests/test_core_target_registry.py
"""Tests for the core Target Platform Registry & permission-scope engine."""

import pytest

from core.target_registry import (
    PermissionScope,
    TargetEntity,
    TargetPlatformRegistry,
    TargetPlatformType,
)


def test_default_main_repo_is_read_only():
    reg = TargetPlatformRegistry()
    main = reg.get_target("main-repository")
    assert main is not None
    assert main.scope == PermissionScope.READ_ONLY
    assert main.is_read_only() is True
    assert main.can_write() is False


def test_target_entity_write_flags():
    ro = TargetEntity(
        id="a",
        name="a",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="x",
        scope=PermissionScope.READ_ONLY,
    )
    fc = TargetEntity(
        id="b",
        name="b",
        target_type=TargetPlatformType.CLOUD_SERVICE,
        url="y",
        scope=PermissionScope.FULL_CONTROL,
    )
    assert ro.is_read_only() and not ro.can_write()
    assert fc.can_write() and not fc.is_read_only()


def test_register_and_get_target():
    reg = TargetPlatformRegistry()
    t = TargetEntity(
        id="ws-1",
        name="ws",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="origin/ws",
        scope=PermissionScope.FULL_CONTROL,
    )
    reg.register_target(t)
    assert reg.get_target("ws-1") is t
    assert t in reg.list_targets()


def test_unregister_normal_target():
    reg = TargetPlatformRegistry()
    t = TargetEntity(
        id="ws-2",
        name="ws",
        target_type=TargetPlatformType.API_ENDPOINT,
        url="x",
        scope=PermissionScope.FULL_CONTROL,
    )
    reg.register_target(t)
    assert reg.unregister_target("ws-2") is True
    assert reg.get_target("ws-2") is None


def test_unregister_main_repo_raises():
    reg = TargetPlatformRegistry()
    with pytest.raises(ValueError):
        reg.unregister_target("main-repository")


def test_unknown_target_in_list_targets():
    reg = TargetPlatformRegistry()
    assert reg.unregister_target("does-not-exist") is False


def test_validate_write_permission_read_only_false():
    reg = TargetPlatformRegistry()
    assert reg.validate_write_permission("main-repository") is False


def test_validate_write_permission_full_control_true():
    reg = TargetPlatformRegistry()
    t = TargetEntity(
        id="ws-3",
        name="ws",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="x",
        scope=PermissionScope.FULL_CONTROL,
    )
    reg.register_target(t)
    assert reg.validate_write_permission("ws-3") is True


def test_validate_write_permission_unknown_raises():
    reg = TargetPlatformRegistry()
    with pytest.raises(KeyError):
        reg.validate_write_permission("missing")
