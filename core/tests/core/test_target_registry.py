"""Tests for TargetPlatformRegistry, Scope Engine, and DynamicRepoManager.

Validates:
- READ_ONLY scope enforcement for primary codebase.
- FULL_CONTROL scope for dynamic agent workspaces.
- DynamicRepoManager scope-safe mutation guards.
"""

import tempfile
from pathlib import Path

import pytest

from core.repo_manager import DynamicRepoManager, PermissionDeniedError
from core.target_registry import (
    PermissionScope,
    TargetEntity,
    TargetPlatformRegistry,
    TargetPlatformType,
)


def test_default_main_repo_is_read_only():
    """ডিফল্ট মেইন রেপো READ_ONLY স্কোপে রেজিস্টার্ড কি না নিশ্চিত করে।"""
    registry = TargetPlatformRegistry()
    main_target = registry.get_target("main-repository")

    assert main_target is not None
    assert main_target.scope == PermissionScope.READ_ONLY
    assert main_target.is_read_only() is True
    assert main_target.can_write() is False


def test_register_and_unregister_target():
    """নতুন টার্গেট প্ল্যাটফর্ম রেজিস্টার ও অন-রেজিস্টার কাজ করছে কি না পরীক্ষা করে।"""
    registry = TargetPlatformRegistry()
    target = TargetEntity(
        id="agent-workspace-01",
        name="Autonomous Agent Repo",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="https://github.com/example/agent-workspace.git",
        scope=PermissionScope.FULL_CONTROL,
    )

    registry.register_target(target)
    fetched = registry.get_target("agent-workspace-01")
    assert fetched is not None
    assert fetched.can_write() is True

    # Unregister
    success = registry.unregister_target("agent-workspace-01")
    assert success is True
    assert registry.get_target("agent-workspace-01") is None


def test_main_repo_cannot_be_unregistered():
    """মেইন রেপো যেন ভুলবশত অপসারিত না হতে পারে তা ভ্যালিডেট করে।"""
    registry = TargetPlatformRegistry()
    with pytest.raises(ValueError, match="Protected main-repository"):
        registry.unregister_target("main-repository")


def test_permission_guard_read_only_vs_full_control():
    """স্কোপ গার্ড দ্বারা READ_ONLY তে রাইট ব্লক এবং FULL_CONTROL এ এলাউ হয় কি না।"""
    registry = TargetPlatformRegistry()

    # READ_ONLY check
    assert registry.validate_write_permission("main-repository") is False

    # FULL_CONTROL check
    target = TargetEntity(
        id="writable-repo",
        name="Writable Sandbox",
        target_type=TargetPlatformType.GIT_REPOSITORY,
        url="https://github.com/example/sandbox.git",
        scope=PermissionScope.FULL_CONTROL,
    )
    registry.register_target(target)
    assert registry.validate_write_permission("writable-repo") is True


def test_repo_manager_prevents_commit_on_read_only():
    """READ_ONLY স্কোপের টার্গেটে Commit করতে গেলে PermissionDeniedError রেইজ করে কি না।"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = DynamicRepoManager(workspace_base=Path(tmpdir))

        # Test commit on protected main-repository
        with pytest.raises(PermissionDeniedError, match="READ_ONLY permission scope"):
            manager.execute_git_commit("main-repository", "Unauthorized commit attempt")
