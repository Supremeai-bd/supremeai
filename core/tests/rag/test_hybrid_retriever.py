# SupremeAI 2.0 — Hybrid RAG Search Test Suite
# বাংলা মন্তব্য: এটি Sparse BM25, RRF র‍্যাংক ফিউশন এবং বাংলা টেক্সট টোকেনাইজেশনের ইউনিট টেস্ট পরিচালনা করে।

from core.rag.hybrid_retriever import HybridRetriever
from core.rag.sparse_bm25 import SparseBM25Index


def test_sparse_bm25_tokenization():
    bm25 = SparseBM25Index()
    text = "SupremeAI 2.0 বাংলা ভাষা এবং Error_Code_904 টেস্ট!"
    tokens = bm25.tokenize(text)
    assert "supremeai" in tokens
    assert "বাংলা" in tokens
    assert "ভাষা" in tokens
    assert "error_code_904" in tokens


def test_sparse_bm25_search():
    bm25 = SparseBM25Index()
    docs = [
        {"id": "1", "text": "SupremeAI 2.0 zero-cost architecture with FastAPI"},
        {"id": "2", "text": "বাংলা ভাষার প্রাকৃতিক ভাষা প্রসেসিং এবং AI মডেল"},
        {"id": "3", "text": "System error handling and exception logging"},
    ]
    bm25.fit(docs)
    results = bm25.search("বাংলা AI", top_k=5)
    assert len(results) >= 1
    assert results[0]["id"] == "2"


def test_reciprocal_rank_fusion():
    retriever = HybridRetriever(rrf_k=60)
    dense_results = [
        {"id": "doc1", "text": "Document 1 Dense Best Match"},
        {"id": "doc2", "text": "Document 2 Dense Second Match"},
    ]
    sparse_results = [
        {"id": "doc2", "text": "Document 2 Sparse Best Match"},
        {"id": "doc3", "text": "Document 3 Sparse Second Match"},
    ]

    fused = retriever.reciprocal_rank_fusion(dense_results, sparse_results, top_k=3)
    assert len(fused) == 3
    # doc2 appeared in both (rank 2 in dense, rank 1 in sparse), so doc2 should have highest RRF score
    assert fused[0]["id"] == "doc2"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_hybrid_search_fallback():
    retriever = HybridRetriever(rrf_k=60)
    docs = [
        {"id": "docA", "text": "FastAPI python backend service"},
        {"id": "docB", "text": "React vite frontend client"},
    ]
    retriever.index_documents(docs)
    results = retriever.hybrid_search("python backend", top_k=2)
    assert len(results) >= 1
    assert results[0]["id"] == "docA"
