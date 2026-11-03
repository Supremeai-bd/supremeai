from fastapi.testclient import TestClient

from core.app import app

# বাংলা মন্তব্য: এপিআই এন্ডপয়েন্টটি ড্রাই-রান মোডে সঠিক নোড ও এজ ফরম্যাট দিচ্ছে কিনা তা যাচাই করা।

client = TestClient(app)


def test_get_skill_graph_dry_run():
    from api.routes.auth import create_access_token

    token = create_access_token({"sub": "test_user", "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/graph/skills", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0
    assert data["nodes"][0]["id"] == "python"


def test_get_learning_path_dry_run():
    from api.routes.auth import create_access_token

    token = create_access_token({"sub": "test_user", "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/api/v1/graph/path?start_skill=Python&end_skill=FastAPI",
        headers=headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert "path" in data
    assert "Dry-run Path Node 1" in data["path"]
