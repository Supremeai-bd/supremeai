#!/usr/bin/env python3
"""
SupremeAI - Ask the Scribe
==========================

A conversational interface to query the project's knowledge base.
It uses a Retrieval-Augmented Generation (RAG) approach to answer questions
about the codebase using the documentation indexed in ChromaDB.

Author: Gemini Code Assist
Date: July 12, 2026
"""

import argparse
import asyncio
import sys
from pathlib import Path

import chromadb
import litellm
from chromadb.utils import embedding_functions

# বাংলা মন্তব্য: ক্লিন ইমপোর্ট স্ট্রাকচার যাতে sys.path.insert হ্যাক এড়ানো যায়।
try:
    from backend.core.config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
    from core.config import settings

# --- Configuration ---
# বাংলা মন্তব্য: হার্ডকোডেড পাথের বদলে সেটিংসের chromadb_path ব্যবহার করা হলো।
DB_PATH = settings.chromadb_path
COLLECTION_NAME = "codebase_docs"


# --- AI Prompt Template (RAG) ---
RAG_PROMPT_TEMPLATE = """
You are a helpful AI assistant for the SupremeAI project, acting as an expert guide to the codebase.
Your task is to answer the user's question based *only* on the context provided below.
The context is extracted from the project's own documentation.

If the context does not contain the information needed to answer the question, state clearly:
"I'm sorry, I don't have information about that in my knowledge base."

Do not make up answers or use external knowledge.

--- CONTEXT FROM CODEBASE ---
{context}
---

QUESTION: {question}

ANSWER:
"""


async def answer_question(question: str) -> str:
    """
    Answers a question about the codebase using RAG.
    This is the core async logic callable from an API.
    """
    # বাংলা মন্তব্য: settings থেকে Gemini API কী নেওয়া হচ্ছে।
    api_key_str = settings.gemini_api_key
    if not api_key_str:
        return "I'm sorry, I don't have GEMINI_API_KEY configured in settings."

    litellm.api_key = api_key_str.split(",")[0].strip()

    try:
        sentence_transformer_ef = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        )
        client = chromadb.PersistentClient(path=DB_PATH)
        collection = client.get_collection(
            name=COLLECTION_NAME, embedding_function=sentence_transformer_ef
        )
    except Exception as e:
        return f"Error: ChromaDB কালেকশন বা ক্লায়েন্ট লোড করতে ব্যর্থ হয়েছে — {e}"

    # ১. প্রাসঙ্গিক তথ্যের জন্য ChromaDB কোয়েরি করা
    try:
        results = collection.query(query_texts=[question], n_results=7)
        if not results or not results.get("documents") or not results["documents"][0]:
            return "I'm sorry, no relevant context was found in the knowledge base."
        context = "\n\n---\n\n".join(results["documents"][0])
    except Exception as e:
        return f"Error: ChromaDB কোয়েরি করার সময় এরর ঘটেছে — {e}"

    # ২. কনটেক্সট ব্যবহার করে LLM-কে উত্তর তৈরি করতে বলা
    try:
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)
        # বাংলা মন্তব্য: হার্ডকোডেড মডেল নামের বদলে সেটিংসের সেন্ট্রালাইজড মডেল নাম ব্যবহার করা হচ্ছে।
        model_name = settings.gemini_model_name
        response = await litellm.acompletion(
            model=model_name, messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content
        return answer
    except Exception as e:
        return f"Error: LLM উত্তর তৈরি করতে ব্যর্থ হয়েছে — {e}"


async def main(question: str):
    """Answers a question about the codebase using the indexed knowledge."""
    answer = await answer_question(question)
    print("\n🤖 AI Scribe's Answer:\n")
    print(answer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ask the AI Scribe about the SupremeAI codebase."
    )
    parser.add_argument("question", type=str, help="Your question about the codebase.")
    args = parser.parse_args()
    asyncio.run(main(args.question))
