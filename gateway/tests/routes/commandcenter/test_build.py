from .conftest import ADMIN_HEADERS, client


def test_commandcenter_build_router():
    resp = client.get("/admin-api/commandcenter/build/router", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "cost_quality_preference" in resp.json()


def test_commandcenter_build_providers():
    resp = client.get("/admin-api/commandcenter/build/providers", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_build_skills():
    resp = client.get("/admin-api/commandcenter/build/skills", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_commandcenter_build_memory():
    resp = client.get("/admin-api/commandcenter/build/memory", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "semantic_cache_hit_rate" in resp.json()


def test_commandcenter_build_knowledge():
    resp = client.get("/admin-api/commandcenter/build/knowledge", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert "rag_index_status" in resp.json()
