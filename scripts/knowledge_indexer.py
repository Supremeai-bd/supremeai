#!/usr/bin/env python3
"""
SupremeAI - Knowledge Base Indexer
==================================

Scans the codebase, extracts all Python docstrings (module, class, and function level),
and indexes them into a persistent ChromaDB vector database. This creates a searchable
knowledge graph of the entire project.

Author: Gemini Code Assist
Date: July 12, 2026
"""

import ast
import logging
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# বাংলা মন্তব্য: ক্লিন ইমপোর্ট স্ট্রাকচার যাতে sys.path.insert হ্যাক এড়ানো যায়।
try:
    from backend.core.config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from core.config import settings

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# এই ডিরেক্টরিগুলো থেকে ডকুমেন্টেশন ইনডেক্স করা হবে
TARGET_DIRECTORIES = ["backend/core", "backend/tools"]
# বাংলা মন্তব্য: হার্ডকোডেড পাথের বদলে সেটিংসের chromadb_path ব্যবহার করা হলো।
DB_PATH = settings.chromadb_path
COLLECTION_NAME = "codebase_docs"

# --- Setup ChromaDB and Embedding ---
# litellm-এর মাধ্যমে যেকোনো embedding মডেল ব্যবহার করা যাবে, যেমন "text-embedding-ada-002"
# "all-MiniLM-L6-v2" একটি ভালো, দ্রুত এবং লোকাল অল্টারনে티브
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=sentence_transformer_ef
)

def get_docstrings_from_file(file_path: Path) -> list[tuple[str, str]]:
    """Extracts module, function, and class docstrings from a Python file."""
    content = file_path.read_text(encoding="utf-8")
    docs = []
    try:
        tree = ast.parse(content)
        # Extract module-level docstring
        module_doc = ast.get_docstring(tree)
        if module_doc:
            docs.append((f"Module: {file_path.name}", module_doc))

        # Extract docstrings from functions and classes
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                docstring = ast.get_docstring(node)
                if docstring:
                    docs.append((f"In {file_path.name} -> {node.name}", docstring))
    except Exception as e:
        logging.warning(f"Could not parse {file_path}: {e}")
    return docs

def run_indexing(target_dirs: list[str] = TARGET_DIRECTORIES):
    """
    Scans specified directories, extracts documentation, and indexes it in ChromaDB.
    """
    logging.info(f"Starting knowledge indexing for: {target_dirs}...")
    all_docs, all_metadatas, all_ids = [], [], []

    for target_dir in target_dirs:
        for file_path in Path(target_dir).rglob("*.py"):
            logging.info(f"Indexing docs from: {file_path}")
            docstrings = get_docstrings_from_file(file_path)
            for i, (context, doc) in enumerate(docstrings):
                doc_id = f"{file_path}:{i}"
                all_docs.append(doc)
                all_metadatas.append({"source": str(file_path), "context": context})
                all_ids.append(doc_id)

    if all_docs:
        logging.info(f"Upserting {len(all_docs)} documentation chunks into ChromaDB...")
        collection.upsert(documents=all_docs, metadatas=all_metadatas, ids=all_ids)
        logging.info(f"✅ Indexing complete! Knowledge base stored in '{DB_PATH}'.")
    else:
        logging.info("No new docstrings found to index.")

if __name__ == "__main__":
    run_indexing()

# --- কিভাবে ব্যবহার করবেন? ---
#
# ১. নলেজ বেস ইনডেক্স করুন:
#    প্রথমে, knowledge_indexer.py স্ক্রিপ্টটি চালান। এটি আপনার কোডবেসের সমস্ত ডকুমেন্টেশন পড়ে
#    supremeai_knowledge_base নামে একটি ফোল্ডারে ভেক্টর ডাটাবেস তৈরি করবে।
#    ```bash
#    python scripts/knowledge_indexer.py
#    ```
#
# ২. প্রশ্ন করুন:
#    ইনডেক্সিং শেষ হলে, আপনি ask_scribe.py ব্যবহার করে আপনার কোডবেস সম্পর্কে যেকোনো প্রশ্ন করতে পারেন।
#    ```bash
#    # উদাহরণ প্রশ্ন
#    python ask_scribe.py "What is the purpose of MorphicOrchestrator?"
#    python ask_scribe.py "How does the GuardianAgent work?"
#    python ask_scribe.py "Explain the `budget_aware_route` function."
#    ```
#
# এই সিস্টেমটি আপনার ডেভেলপমেন্ট প্রক্রিয়ায় একটি শক্তিশালী সহযোগী হিসেবে কাজ করবে এবং কোডবেস বোঝা ও নেভিগেট করাকে অনেক সহজ করে তুলবে।
