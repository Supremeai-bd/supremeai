import asyncio
from backend.core.tenant_db import TenantAwareFirestore
from backend.api.dependencies import get_tenant_db
from fastapi import HTTPException

def test_di():
    # Mocking JWT payload
    payload = {"sub": "test_tenant@supremeai.com", "role": "admin"}
    try:
        db = get_tenant_db(payload)
        print("✅ Success: TenantAwareFirestore initialized for:", db.tenant_id)
        assert db.tenant_id == "test_tenant@supremeai.com"
    except HTTPException as e:
        print("❌ Failed:", e.detail)

if __name__ == "__main__":
    test_di()
