import sys
from unittest.mock import MagicMock

import pytest

# Ensure litellm is mockable in CI/local test runners where it may not be installed
if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()

import core.embeddings as emb


@pytest.fixture(autouse=True)
def _reset_emb_cache():
    emb._embedding_cache.clear()
    emb._cache_hits = 0
    emb._cache_misses = 0
    emb._encoder = None
    yield


def test_get_cache_stats():
    assert emb.get_cache_stats() == {"hits": 0, "misses": 0, "size": 0}


def test_get_local_encoder_unavailable_returns_none():
    assert emb.get_local_encoder() is None


def test_hash_vectorize_deterministic_and_normalized():
    v1 = emb.hash_vectorize("hello world foo")
    v2 = emb.hash_vectorize("hello world foo")
    assert v1 == v2
    assert len(v1) == 384
    assert abs(sum(x * x for x in v1) ** 0.5 - 1.0) < 1e-6


def test_hash_vectorize_empty_text():
    v = emb.hash_vectorize("")
    assert len(v) == 384
    assert v[0] == 1.0


def test_local_embed_returns_none_without_encoder():
    assert emb.local_embed("anything") is None


def test_pad_to_dim():
    assert emb._pad_to_dim([1.0, 2.0], 4) == [1.0, 2.0, 0.0, 0.0]
    assert emb._pad_to_dim([1.0, 2.0, 3.0, 4.0], 2) == [1.0, 2.0]
    assert emb._pad_to_dim([1.0, 2.0], 2) == [1.0, 2.0]


def test_embed_for_pgvector_cache_hit(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [0.1] * 384}]
    monkeypatch.setattr("litellm.embedding", lambda **kw: fake_resp)

    vec1 = emb.embed_for_pgvector("hello", pg_dim=1536)
    vec2 = emb.embed_for_pgvector("hello", pg_dim=1536)
    assert len(vec1) == 384
    assert vec1 == vec2
    assert emb._cache_misses == 1
    assert emb._cache_hits == 1


def test_embed_for_pgvector_cache_eviction(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [0.9] * 384}]
    monkeypatch.setattr("litellm.embedding", lambda **kw: fake_resp)
    for i in range(5001):
        emb._embedding_cache[f"k{i}:384"] = [0.1] * 384
    vec = emb.embed_for_pgvector("query", pg_dim=384)
    assert len(vec) == 384
    assert len(emb._embedding_cache) == 1


def test_embed_for_pgvector_failure_returns_384_dim_fallback(monkeypatch):
    monkeypatch.setattr(
        "litellm.embedding", lambda **kw: (_ for _ in ()).throw(RuntimeError("down"))
    )
    vec = emb.embed_for_pgvector("hello")
    assert len(vec) == 384


def test_embed_query_falls_back_to_hash_vectorize():
    v = emb.embed_query("some text here")
    assert len(v) == 384
    assert abs(sum(x * x for x in v) ** 0.5 - 1.0) < 1e-6


async def test_embedding_engine_get_instance_singleton():
    e1 = emb.EmbeddingEngine.get_instance()
    e2 = emb.EmbeddingEngine.get_instance()
    assert e1 is e2


async def test_embedding_engine_embed_and_cosine():
    eng = emb.EmbeddingEngine.get_instance()
    v = await eng.embed("hello world")
    assert len(v) == 384
    assert eng.cosine(v, v) == pytest.approx(1.0)
    assert eng.cosine([], v) == 0.0
    assert eng.cosine([1.0, 2.0], [1.0]) == 0.0
    assert eng.cosine([0.0, 0.0], [0.0, 0.0]) == 0.0


async def test_embedding_engine_vector_search_ranks():
    eng = emb.EmbeddingEngine.get_instance()
    corpus = [
        {"text": "alpha alpha alpha"},
        {"text": "beta"},
        {"vector": await eng.embed("alpha alpha alpha")},
    ]
    top = await eng.vector_search("alpha alpha alpha", corpus, top_k=2)
    assert len(top) == 2
    assert top[0]["score"] >= top[1]["score"]
