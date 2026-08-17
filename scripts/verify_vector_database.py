"""
Verify stored vector memory documents in SupremeAI 2.0 ChromaDB & fallback database.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from memory.chromadb_store import ChromaDBStore
from memory.rag_pipeline import RAGPipeline


def main():
    print("=========================================================")
    print("SupremeAI 2.0 -- Vector Memory Verification Report")
    print("=========================================================")

    store = ChromaDBStore()
    rag = RAGPipeline(vector_store=store)

    doc_count = store.count()
    print(f"Total Stored Documents in Database: {doc_count}")

    queries = [
        "Swarm Architecture 5 models",
        "DARE-TIES mergekit quantization",
        "Meta-Cognition self awareness",
        "Zero Trust security architecture",
        "Circuit Breaker fallback",
    ]

    print("\n---------------------------------------------------------")
    print("Running Semantic Vector Search Queries:")
    print("---------------------------------------------------------")

    for q in queries:
        results = store.query(q, n_results=2)
        print(f"\nQuery: '{q}'")
        if results:
            for doc_id, score, doc_data in results:
                meta = doc_data.get("metadata", {})
                snippet = doc_data.get("text", "")[:120].replace("\n", " ")
                print(f"   [FOUND] ID: {doc_id} | Similarity Score: {score:.4f} | Category: {meta.get('category', 'N/A')}")
                print(f"      Snippet: {snippet}...")
        else:
            print("   [NOT FOUND] No vector match found.")

    print("\n=========================================================")
    print("Verification Completed Successfully!")
    print("=========================================================")


if __name__ == "__main__":
    main()
