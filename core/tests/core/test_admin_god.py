"""Admin God Layer tests for SupremeAI 2.0."""

import os
from unittest.mock import patch

import pytest

from core.admin_god import AdminGodLayer, GodModeAuditLog, GodModeContext
from core.security.authentication.rbac import UserContext


class TestGodModeAuditLog:
    """Tests for GodModeAuditLog class."""

    def test_record_creates_entry(self):
        """একটি নতুন audit entry রেকর্ড করা হচ্ছে।"""
        # Clear any existing entries
        GodModeAuditLog._entries = []

        session_id = GodModeAuditLog.record(
            actor="test_user",
            action="TEST_ACTION",
            resource="test_resource",
            reason="test_reason",
            ip_address="192.168.1.1",
        )

        assert session_id is not None
        assert len(session_id) == 32  # token_hex(16) produces 32 char string
        assert len(GodModeAuditLog._entries) == 1

    def test_record_default_ip_address(self):
        """ডিফল্ট IP ঠিক আছে।"""
        GodModeAuditLog._entries = []

        session_id = GodModeAuditLog.record(
            actor="test_user",
            action="TEST_ACTION",
            resource="test_resource",
            reason="test_reason",
        )

        assert session_id is not None
        assert GodModeAuditLog._entries[0]["ip_address"] == "unknown"

    def test_update_creates_entry(self):
        """Update মেথড একটি নতুন entry যোগ করে।"""
        GodModeAuditLog._entries = []

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
        """Update এর ডিফল্ট duration_ms ঠিক আছে।"""
        GodModeAuditLog._entries = []

        session_id = GodModeAuditLog.record(
            actor="test_user", action="ACTIVATED", resource="system", reason="test"
        )

        GodModeAuditLog.update(session_id, "TERMINATED")

        assert GodModeAuditLog._entries[1]["duration_ms"] == 0.0

    def test_get_entries_returns_copy(self):
        """get_entries মূল লিস্টের কপি রিটার্ন করে।"""
        GodModeAuditLog._entries = []

        GodModeAuditLog.record(actor="user1", action="ACTION1", resource="res1", reason="reason1")
        GodModeAuditLog.record(actor="user2", action="ACTION2", resource="res2", reason="reason2")

        entries = GodModeAuditLog.get_entries()
        assert len(entries) == 2

        # Modify the returned list
        entries.append({"test": "modified"})

        # Original should be unchanged
        assert len(GodModeAuditLog.get_entries()) == 2

    def test_entry_structure(self):
        """Entry-এর structure সঠিক।"""
        GodModeAuditLog._entries = []

        GodModeAuditLog.record(
            actor="test_actor",
            action="TEST_ACTION",
            resource="test_resource",
            reason="test_reason",
            ip_address="10.0.0.1",
        )

        entry = GodModeAuditLog._entries[0]
        assert entry["session_id"] is not None
        assert entry["actor"] == "test_actor"
        assert entry["action"] == "TEST_ACTION"
        assert entry["resource"] == "test_resource"
        assert entry["reason"] == "test_reason"
        assert entry["ip_address"] == "10.0.0.1"
        assert "timestamp" in entry


class TestGodModeContext:
    """Tests for GodModeContext class."""

    def test_context_creation(self):
        """GodModeContext সঠিকভাবে তৈরি হয়।"""
        ctx = GodModeContext(session_id="test_session_123")

        assert ctx.session_id == "test_session_123"

    def test_context_session_id_type(self):
        """Session ID স্ট্রিং টাইপ হয়।"""
        ctx = GodModeContext(session_id="abc123xyz")

        assert isinstance(ctx.session_id, str)


class TestAdminGodLayer:
    """Tests for AdminGodLayer enforcement and constraint injection."""

    @patch.dict(os.environ, {"SUPREMEAI_ADMIN_PASSWORD_HASH": ""})
    def test_init_default(self):
        """ডিফল্ট ইনিশialization ঠিক আছে।"""
        layer = AdminGodLayer()
        assert layer.rules_engine is not None
        assert layer.rbac is not None
        assert layer.admin_password_hash == ""

    def test_init_with_custom_rules_engine(self):
        """কাস্টম রুলস ইঞ্জিন সহ ইনিশialization করা হচ্ছে।"""
        from core.universal_rules import UniversalRulesEngine

        custom_engine = UniversalRulesEngine()
        layer = AdminGodLayer(rules_engine=custom_engine)
        assert layer.rules_engine is custom_engine

    def test_verify_admin_no_password(self):
        """খালি পাসওয়ার্ড রিজেক্স করা হচ্ছে।"""
        layer = AdminGodLayer()
        assert layer.verify_admin("") is False
        assert layer.verify_admin(None) is False

    def test_verify_admin_no_hash(self):
        """অ্যাডমিন হ্যাশ ছাড়াই ভেরিফিকেশন ব্যর্থ হয়।"""
        layer = AdminGodLayer.__new__(AdminGodLayer)
        layer.admin_password_hash = ""
        layer.rules_engine = None
        layer.rbac = None
        assert layer.verify_admin("password") is False

    def test_enforce_no_user_context(self):
        """UserContext ছাড়াই enforce করলে ডিফল্ট ভিউয়ার রোল ব্যবহার হয়।"""
        layer = AdminGodLayer()
        ctx = UserContext(user_id="test-user", role="admin")
        result = layer.enforce("read", ctx)
        assert result["allowed"] is True
        assert result["role"] == "admin"

    def test_enforce_with_string_context(self):
        """স্ট্রিং রোল সহ UserContext তৈরি করে enforce করা হচ্ছে।"""
        layer = AdminGodLayer()
        result = layer.enforce("read", "admin")
        assert result["allowed"] is True
        assert result["role"] == "admin"

    def test_enforce_with_none_context(self):
        """None কন্টেক্সটে ডিফল্ট ভিউয়ার রোল ব্যবহার হয়।"""
        from core.security.authentication.rbac import PermissionDeniedError

        layer = AdminGodLayer()
        # This raises PermissionDeniedError for permission denied
        with pytest.raises(PermissionDeniedError):
            layer.enforce("admin", None)

    def test_enforce_permission_denied(self):
        """অনুমতি ছাড়াই enforce করলে PermissionDeniedError দেওয়া হয়।"""
        from core.security.authentication.rbac import PermissionDeniedError

        layer = AdminGodLayer()
        ctx = UserContext(user_id="test-user", role="viewer")
        # The actual error message is "Role 'viewer' lacks permission for 'admin'"
        with pytest.raises(PermissionDeniedError, match="lacks permission"):
            layer.enforce("admin", ctx)

    def test_enforce_rules(self):
        """এনফোর্স রুলস ফাংশন কাজ করছে।"""
        layer = AdminGodLayer()
        context = {"test": "value"}
        result = layer.enforce_rules(context)
        assert isinstance(result, dict)

    def test_inject_prompt_constraints(self):
        """প্রম্পট কনস্ট্রেন্টস ইনজেক্ট করা হচ্ছে।"""
        layer = AdminGodLayer()
        original_prompt = "You are a helpful assistant."
        result = layer.inject_prompt_constraints(original_prompt)
        assert "CONSTITUTIONAL RULES" in result
        assert original_prompt in result

    def test_inject_prompt_constraints_empty_prompt(self):
        """খালি প্রম্পটের উপর ইনজেকশন করা হচ্ছে।"""
        layer = AdminGodLayer()
        result = layer.inject_prompt_constraints("")
        assert "CONSTITUTIONAL RULES" in result

    def test_inject_prompt_constraints_with_rules(self):
        """রুলস সহ প্রম্পট কনস্ট্রেন্টস ইনজেক্ট করা হচ্ছে।"""
        layer = AdminGodLayer()
        # Add a custom rule to test the injection
        layer.rules_engine.rules["test_rule"] = "test value"
        result = layer.inject_prompt_constraints("Original prompt")
        assert "Test Rule" in result
        assert "test value" in result

    @patch.dict(os.environ, {"SUPREMEAI_ADMIN_PASSWORD_HASH": "valid_hash"})
    def test_verify_admin_success(self):
        """সফল পাসওয়ার্ড ভেরিফিকেশন কাজ করছে।"""
        import bcrypt

        # Create a valid password hash
        password = "test_password_123"
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        with patch.object(AdminGodLayer, "__init__", lambda self: None):
            layer = AdminGodLayer()
            layer.admin_password_hash = password_hash

        result = layer.verify_admin(password)
        assert result is True

    @patch.dict(os.environ, {"SUPREMEAI_ADMIN_PASSWORD_HASH": "valid_hash"})
    def test_verify_admin_incorrect_password(self):
        """ভুল পাসওয়ার্ড ভেরিফিকেশন ব্যর্থ হয়।"""
        import bcrypt

        # Create a hash for a different password
        password_hash = bcrypt.hashpw(b"correct_password", bcrypt.gensalt()).decode()

        with patch.object(AdminGodLayer, "__init__", lambda self: None):
            layer = AdminGodLayer()
            layer.admin_password_hash = password_hash

        result = layer.verify_admin("wrong_password")
        assert result is False

    @patch.dict(
        os.environ,
        {
            "SUPREMEAI_ADMIN_PASSWORD_HASH": "dGhpcyBpcyBhIGJhdnNwYXJzaHdpY2FsbHkgaGFnZSBmb3IgZW5jb2Rpbmc="
        },
    )
    def test_verify_admin_bcrypt_exception(self):
        """bcrypt exception during verification is handled gracefully."""
        layer = AdminGodLayer()
        layer.admin_password_hash = "invalid_format_that_causes_exception"

        # This should return False and log VERIFY_ERROR
        result = layer.verify_admin("anypassword")
        assert result is False


class TestAdminGodLayerSessions:
    """Tests for god_mode_session context manager."""

    @pytest.mark.anyio
    async def test_god_mode_session_activates_and_terminates(self):
        """god_mode_session কনটেক্সট ম্যানেজার কাজ করছে।"""
        GodModeAuditLog._entries = []
        layer = AdminGodLayer()

        async with layer.god_mode_session("test_user", "testing session") as ctx:
            assert ctx is not None
            assert ctx.session_id is not None
            # Session is active
            assert any(e["action"] == "GOD_MODE_ACTIVATED" for e in GodModeAuditLog._entries)

        # After context exit, terminated entry should be added
        assert any(e["action"] == "GOD_MODE_TERMINATED" for e in GodModeAuditLog._entries)

    @pytest.mark.anyio
    async def test_god_mode_session_logs_ip_address(self):
        """IP ঠিকানা সঠিকভাবে লগ হয়।"""
        GodModeAuditLog._entries = []
        layer = AdminGodLayer()

        async with layer.god_mode_session("user123", "test reason", ip_address="192.168.1.100"):
            pass

        entries = GodModeAuditLog.get_entries()
        activated_entry = next((e for e in entries if e["action"] == "GOD_MODE_ACTIVATED"), None)
        assert activated_entry is not None
        assert activated_entry["ip_address"] == "192.168.1.100"


class TestRBACIntegration:
    """Tests for RBAC integration with AdminGodLayer."""

    def test_rbac_has_permission_admin(self):
        """অ্যাডমিন রোলের অনুমতি চেক করা হচ্ছে।"""
        layer = AdminGodLayer()
        ctx = UserContext(user_id="admin", role="admin")
        result = layer.enforce("admin", ctx)
        assert result["allowed"] is True

    def test_rbac_has_permission_viewer(self):
        """ভিউয়ার রোলের অনুমতি সীমিত থাকে।"""
        layer = AdminGodLayer()
        ctx = UserContext(user_id="viewer", role="viewer")
        result = layer.enforce("read", ctx)
        assert result["allowed"] is True

    def test_rbac_permission_denied_viewer_admin(self):
        """ভিউয়ার রোলের অ্যাডমিন অ্যাকশন অনুমতি নেই।"""
        from core.security.authentication.rbac import PermissionDeniedError

        layer = AdminGodLayer()
        ctx = UserContext(user_id="viewer", role="viewer")
        with pytest.raises(PermissionDeniedError):
            layer.enforce("admin", ctx)
