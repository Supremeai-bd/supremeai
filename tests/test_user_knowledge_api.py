"""Tests for Workspace User Knowledge Base endpoints (/api/user/knowledge)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.knowledge import router as knowledge_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(knowledge_router)
    return TestClient(app)


def test_get_user_knowledge_docs(client):
    """Test retrieving user knowledge documents."""
    res = client.get("/api/user/knowledge")
    assert res.status_code == 200
    data = res.json()
    assert "documents" in data
    assert isinstance(data["documents"], list)
    assert len(data["documents"]) >= 4

    doc = data["documents"][0]
    assert "id" in doc
    assert "title" in doc
    assert "isGroundingActive" in doc


def test_create_and_delete_user_knowledge_doc(client):
    """Test creating a document, updating grounding, and deleting it."""
    payload = {
        "title": "Quantum Compute Integration Guide.md",
        "type": "markdown",
        "sizeBytes": 24000,
        "tokenCount": 5200,
        "chunkCount": 8,
        "status": "indexed",
        "isGroundingActive": True,
        "contentPreview": "Quantum compute SDK guidelines for fault-tolerant state synthesis.",
    }
    # 1. Create
    res = client.post("/api/user/knowledge", json=payload)
    assert res.status_code == 200
    created = res.json()["document"]
    doc_id = created["id"]
    assert created["title"] == payload["title"]
    assert created["isGroundingActive"] is True

    # 2. Toggle Grounding
    res = client.patch(f"/api/user/knowledge/{doc_id}", json={"isGroundingActive": False})
    assert res.status_code == 200
    assert res.json()["document"]["isGroundingActive"] is False

    # 3. Delete
    res = client.delete(f"/api/user/knowledge/{doc_id}")
    assert res.status_code == 200

    # 4. Confirm Deletion (subsequent delete returns 404)
    res = client.delete(f"/api/user/knowledge/{doc_id}")
    assert res.status_code == 404
