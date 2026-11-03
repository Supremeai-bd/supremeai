"""Integration tests for admin god security.

বাংলা: AdminGodLayer — অ্যাডমিন প্রমাণীকরণ, গড মোড অডিট, এবং রুলس এনফোর্সমেন্ট।
"""

from __future__ import annotations

import pytest

from core.admin_god import AdminGodLayer, GodModeAuditLog, GodModeContext
from core.security.authentication.rbac import UserContext


class TestAdminGodSecurity:
    """Tests for admin god security."""

    def setup_method(self):
        """Clear audit log before each test."""
        GodModeAuditLog._entries = []

    def test_record_creates_entry(self):
        """Test audit record creation."""
        session_id = GodModeAuditLog.record(
            actor="test_user",
            action="TEST_ACTION",
            resource="test_resource",
            reason="test_reason",
            ip_address="192.168.1.1",
        )
        assert session_id is not None
        assert len(GodModeAuditLog._entries) == 1

    def test_record_default_ip_address(self):
        """Test default IP address."""
        GodModeAuditLog.record(
            actor="test_user",
            action="TEST_ACTION",
            resource="test_resource",
            reason="test_reason",
        )
        assert GodModeAuditLog._entries[0]["ip_address"] == "unknown"

    def test_update_creates_entry(self):
        """Test update creates new entry."""
        session_id = GodModeAuditLog.record(
            actor="test_user",
            action="GOD_MODE_ACTIVATED",
            resource="system",
            reason="test",
        )
        GodModeAuditLog.update(session_id, "GOD_MODE_TERMINATED", 100.5)
        assert len(GodModeAuditLog._entries) == 2
        assert GodModeAuditLog._entries[1]["action"] == "GOD_MODE_TERMINATED"
        assert GodModeAuditLog._entries[1]["duration_ms"] == 100.5

    def test_update_default_duration(self):
        """Test update with default duration."""
        session_id = GodModeAuditLog.record(
            actor="test_user", action="ACTIVATED", resource="system", reason="test"
        )
        GodModeAuditLog.update(session_id, "TERMINATED")
        assert GodModeAuditLog._entries[1]["duration_ms"] == 0.0

    def test_get_entries_returns_copy(self):
        """Test get_entries returns a copy."""
        GodModeAuditLog.record(actor="user1", action="ACTION1", resource="res1", reason="reason1")
        GodModeAuditLog.record(actor="user2", action="ACTION2", resource="res2", reason="reason2")
        entries = GodModeAuditLog.get_entries()
        assert len(entries) == 2
        entries.append({"test": "modified"})
        assert len(GodModeAuditLog.get_entries()) == 2

    def test_entry_structure(self):
        """Test entry structure is correct."""
        GodModeAuditLog.record(
            actor="test_actor",
            action="TEST_ACTION",
            resource="test_resource",
            reason="test_reason",
            ip_address="10.0.0.1",
        )
        entry = GodModeAuditLog._entries[0]
        assert "session_id" in entry
        assert "timestamp" in entry
        assert entry["actor"] == "test_actor"
        assert entry["action"] == "TEST_ACTION"

    def test_god_mode_context_creation(self):
        """Test GodModeContext creation."""
        ctx = GodModeContext(session_id="test-session")
        assert ctx.session_id == "test-session"

    def test_enforce_allows_admin(self):
        """Test enforce allows admin role."""
        layer = AdminGodLayer()
        user = UserContext(user_id="admin-1", roles=["admin"])
        result = layer.enforce("test_action", user)
        assert result is True or (isinstance(result, dict) and result.get("allowed") is True)

    def test_enforce_denies_non_admin(self):
        """Test enforce denies non-admin role."""
        layer = AdminGodLayer()
        user = UserContext(user_id="user-1", roles=["user"])
        with pytest.raises(PermissionError):
            layer.enforce("test_action", user)

    def test_inject_prompt_constraints_returns_string(self):
        """Test inject_prompt_constraints returns modified prompt."""
        layer = AdminGodLayer()
        prompt = "You are a helpful assistant."
        result = layer.inject_prompt_constraints(prompt)
        assert isinstance(result, str)
        assert len(result) > 0
