"""Task-12 test coverage expansion — knowledge search/seed contract tests.

বাংলা: /api/knowledge/search ও /api/knowledge/seed — এই দুটি এন্ডপয়েন্ট আগে
অরফান ছিল (কোনো টেস্ট নেই; frontend KnowledgePage নিজেও dead ছিল)। Task-12
orphan-wiring-এ KnowledgePage activated হওয়ায় এখন এদের প্রকৃত কনট্র্যাক্ট
lock করা হলো: normalized result shape (id/title/content/source), limit,
malformed-manifest skip, এবং seed counting।
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from api.routes.knowledge import router as knowledge_router

    app = FastAPI()
    app.include_router(knowledge_router, prefix="/api")
    return TestClient(app)


@pytest.fixture()
def manifest_dir(tmp_path, monkeypatch):
    """Temporary skill-manifest directory (monkeypatched over the repo one)."""
    import api.routes.knowledge as kmod

    d = tmp_path / "manifests"
    d.mkdir()
    monkeypatch.setattr(kmod, "_manifest_dir", lambda: d)
    return d


def _write_manifest(d, name: str, data: dict) -> None:
    (d / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")


class TestKnowledgeSearch:
    def test_search_returns_normalized_shape(self, client, manifest_dir):
        _write_manifest(
            manifest_dir,
            "core_alpha",
            {"skill_id": "core_alpha", "owner": "Team_A", "tools_allowed": ["t1"]},
        )
        res = client.post("/api/knowledge/search", json={"question": "core_alpha"})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["query"] == "core_alpha"
        (item,) = body["results"]
        # বাংলা: frontend KnowledgePage যে ফিল্ডগুলো রেন্ডার করে সেগুলোই contract
        assert item["id"] == "core_alpha"
        assert item["title"] == "core_alpha"
        assert "core_alpha" in item["content"]
        assert item["source"] == "core_alpha.json"
        assert item["score"] is None

    def test_search_no_match_returns_empty(self, client, manifest_dir):
        _write_manifest(manifest_dir, "core_alpha", {"skill_id": "core_alpha"})
        res = client.post("/api/knowledge/search", json={"question": "zzz-no-such-token-xyz"})
        assert res.status_code == 200
        body = res.json()
        assert body["results"] == []
        assert body["total"] == 0

    def test_search_respects_limit(self, client, manifest_dir):
        for i in range(3):
            _write_manifest(manifest_dir, f"m{i}", {"skill_id": f"m{i}", "shared": "needle"})
        res = client.post("/api/knowledge/search?limit=2", json={"question": "needle"})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 2
        assert len(body["results"]) == 2

    def test_search_malformed_manifest_skipped_loudly(self, client, manifest_dir):
        _write_manifest(manifest_dir, "good", {"skill_id": "good"})
        (manifest_dir / "broken.json").write_text("{not-valid-json", encoding="utf-8")
        res = client.post("/api/knowledge/search", json={"question": "good"})
        assert res.status_code == 200
        body = res.json()
        # বাংলা: corrupt manifest পুরো সার্চ ভেঙে দেবে না — skip + logger.warning
        assert body["total"] == 1
        assert body["results"][0]["id"] == "good"

    def test_search_validates_question(self, client):
        res = client.post("/api/knowledge/search", json={"question": ""})
        assert res.status_code == 422

    def test_search_falls_back_to_stem_for_unknown_shape(self, client, manifest_dir):
        # বাংলা: skill_id নেই এমন অজানা manifest shape-ও honest fallback পায়
        _write_manifest(manifest_dir, "legacy_thing", {"some_field": "legacy_thing"})
        res = client.post("/api/knowledge/search", json={"question": "legacy_thing"})
        assert res.status_code == 200
        (item,) = res.json()["results"]
        assert item["id"] == "legacy_thing"
        assert item["title"] == "legacy_thing"

    def test_search_cache_rebuilds_on_new_manifest_write(self, client, manifest_dir):
        # বাংলা (Wave-3 perf): parsed manifest index এখন module-level cache-এ থাকে,
        # key = directory mtime। এই টেস্ট mtime invalidation-ই lock করে — seed flow
        # manifest WRITE করে, তাই blind TTL cache হলে fresh write অন্ধকারে থেকে যেত।
        _write_manifest(manifest_dir, "alpha", {"skill_id": "alpha"})
        res1 = client.post("/api/knowledge/search", json={"question": "alpha"})
        assert res1.json()["total"] == 1  # cache populate হলো

        # নতুন manifest write → dir mtime বদলায় → পরের request-এ সঙ্গে সঙ্গে দেখা যেতেই হবে
        _write_manifest(manifest_dir, "beta", {"skill_id": "beta", "token": "fresh-seed-token"})
        res2 = client.post("/api/knowledge/search", json={"question": "fresh-seed-token"})
        assert res2.status_code == 200
        assert res2.json()["total"] == 1
        assert res2.json()["results"][0]["id"] == "beta"

        # rebuild-এ পুরনো entry হারায় না — আগের manifest এখনও match করে
        res3 = client.post("/api/knowledge/search", json={"question": "alpha"})
        assert res3.json()["total"] == 1
        assert res3.json()["results"][0]["id"] == "alpha"

    def test_search_content_excerpt_is_400_chars(self, client, manifest_dir):
        # বাংলা: cache-পূর্ব আচরণ — content সবসময় ৪০০ অক্ষরে কাটা; cache-পরবর্তীতেও same
        _write_manifest(manifest_dir, "big", {"skill_id": "big", "pad": "x" * 2000})
        res = client.post("/api/knowledge/search", json={"question": "big"})
        assert res.status_code == 200
        (item,) = res.json()["results"]
        assert len(item["content"]) == 400


class TestKnowledgeSeed:
    def test_seed_default_documents(self, client):
        res = client.post("/api/knowledge/seed")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["seeded"] >= 1
        assert "seeded" in body["message"].lower()

    def test_seed_counts_only_documents_with_content(self, client):
        res = client.post(
            "/api/knowledge/seed",
            json=[
                {"title": "A", "content": "real content"},
                {"title": "B", "content": "more content"},
                {"title": "C"},  # বাংলা: content নেই — গোনা হবে না
            ],
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "success"
        assert body["seeded"] == 2
