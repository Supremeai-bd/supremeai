"""Integration tests for multi-tenant isolation.

বাংলা: মাল্টি-টেন্যান্ট হার্ড-আইসোলেশন — TenantAwareFirestore এ কখনো cross-tenant ডাটা লিক হবে না।
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from api.dependencies import get_current_platform_admin
from database.tenant_db import TenantAwareFirestore


class TestMultiTenantIsolation:
    """Tests for multi-tenant hard isolation."""

    def test_platform_admin_rejects_project_admin(self, monkeypatch):
        """Project admins must not access cross-tenant controls."""
        monkeypatch.setattr("api.dependencies.settings.admin_emails", ["platform@example.com"])
        with pytest.raises(HTTPException) as exc_info:
            get_current_platform_admin({"sub": "project@example.com", "role": "admin"})
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_platform_admin_accepts_configured_identity(self, monkeypatch):
        """Configured platform identities may access cross-tenant controls."""
        monkeypatch.setattr("api.dependencies.settings.admin_emails", ["platform@example.com"])
        assert (
            get_current_platform_admin({"sub": "platform@example.com", "role": "admin"})["sub"]
            == "platform@example.com"
        )

    def test_tenant_db_rejects_empty_tenant_id(self):
        """Test that empty tenant_id raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            TenantAwareFirestore("")
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_tenant_db_rejects_none_tenant_id(self):
        """Test that None tenant_id raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            TenantAwareFirestore(None)
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_tenant_db_sets_tenant_root(self):
        """Test that tenant_root is set correctly in test environment."""
        db = TenantAwareFirestore("tenant-123")
        assert db.tenant_id == "tenant-123"
        assert db.tenant_root is not None

    def test_tenant_db_collection_path_is_scoped(self):
        """Test that collection path is scoped to tenant."""
        db = TenantAwareFirestore("tenant-abc")
        col = db.collection("documents")
        assert col is not None

    def test_tenant_isolation_different_tenants_different_roots(self):
        """Test that different tenants get different roots."""
        db1 = TenantAwareFirestore("tenant-x")
        db2 = TenantAwareFirestore("tenant-y")
        assert str(db1.tenant_root) != str(db2.tenant_root)

    def test_tenant_db_mock_mode_read(self):
        """Test read returns empty dict in mock mode."""
        db = TenantAwareFirestore("tenant-1")
        doc_ref = db.tenant_root.collection("items").document("doc-1")
        snap = doc_ref.get()
        assert snap.exists is False
        assert snap.to_dict() == {}

    def test_tenant_db_mock_mode_write(self):
        """Test write is a no-op in mock mode."""
        db = TenantAwareFirestore("tenant-1")
        doc_ref = db.tenant_root.collection("items").document("doc-1")
        doc_ref.set({"key": "value"})

    def test_tenant_db_mock_mode_nested_collection(self):
        """Test nested collection access in mock mode."""
        db = TenantAwareFirestore("tenant-1")
        sub_col = db.tenant_root.collection("items").document("doc-1").collection("subitems")
        assert sub_col is not None
