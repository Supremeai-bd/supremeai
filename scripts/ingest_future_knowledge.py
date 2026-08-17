"""
Ingest future-proof AI knowledge, 5-Model Swarm Architecture, and optimization blueprints
into SupremeAI 2.0 ChromaDB vector memory database.
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from memory.rag_pipeline import RAGPipeline


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge into SupremeAI ChromaDB Vector Memory.")
    parser.add_argument("--doc-id", type=str, help="Unique Document ID for ChromaDB vector store")
    parser.add_argument("--content", type=str, help="Text content to ingest")
    parser.add_argument("--file", type=str, help="File path whose content will be ingested")
    parser.add_argument("--category", type=str, default="general", help="Category metadata tag")

    args = parser.parse_args()
    rag = RAGPipeline()

    if args.file:
        file_path = Path(args.file).resolve()
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            doc_id = args.doc_id or f"doc_{file_path.stem}"
            rag.ingest_document(doc_id, content, {"category": args.category, "source": str(file_path)})
            print(f"Successfully ingested file: {file_path}")
            return
        else:
            print(f"Error: File not found: {args.file}")
            sys.exit(1)

    if args.doc_id and args.content:
        rag.ingest_document(args.doc_id, args.content, {"category": args.category})
        print(f"Successfully ingested knowledge document: {args.doc_id}")
        return

    # Default fallback: Ingest default system blueprints
    print("Ingesting Default System Blueprints into SupremeAI Vector Memory...")
    swarm_knowledge = """
    SupremeAI 5-Model Distributed Swarm Architecture (80GB Free Cloud Compute):
    1. Supreme-Coder-3B (paykaribazaronline/supreme-coder-3b): Code generation, React, Flutter, Python, Refactoring.
    2. Supreme-Reasoner-3B (supremeai-team/supreme-reasoner-3b): Step-by-step logic, DeepSeek-R1 distill, Math, Multi-agent planning.
    3. Supreme-Bhasha-1.5B (supremeai-bhasha/supreme-bhasha-1.5b): Bengali language, Voice Didi, Chat localization.
    4. Supreme-Ops-1.5B (supremeai-ops/supreme-ops-1.5b): DevOps, Git, Docker, Shell execution, CI/CD pipelines.
    5. Supreme-Analyst-1.5B (supremeai-data/supreme-analyst-1.5b): SQL, JSON Schema, RAG, Vector Search, Database queries.
    Fault Tolerance: Overlapping core instruction layer (35%-50%) guarantees zero single point of failure.
    """
    rag.ingest_document("doc_swarm_architecture_v2", swarm_knowledge, {"category": "architecture", "type": "swarm"})

    guide_path = Path(__file__).resolve().parent.parent / "docs" / "create_best_ai_model.md"
    if guide_path.exists():
        guide_content = guide_path.read_text(encoding="utf-8")
        rag.ingest_document("doc_ultimate_model_guide", guide_content, {"category": "guide", "source": "create_best_ai_model.md"})
        print("Ingested docs/create_best_ai_model.md")

    print("Knowledge Ingestion Completed Successfully!")


if __name__ == "__main__":
    main()
