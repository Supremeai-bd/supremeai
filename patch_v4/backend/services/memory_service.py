import ast
import json
import math
import os
import sqlite3
from datetime import UTC
from typing import Any

from core.config import settings
from core.logging_config import logger
from core.persistence import pooled_pg

# Using core.embeddings for 1536-dim embeddings to prevent zero-padding mismatch
HAS_SENTENCE_TRANSFORMERS = False


def hash_vectorize(text: str, size: int = 384) -> list[float]:
    """
    Pure Python Feature Hashing (Hashing Trick) to convert text into a 384-dimensional vector.
    Serves as a robust, zero-cost fallback when SentenceTransformer is unavailable.
    """
    vector = [0.0] * size
    words = [w.lower() for w in text.split() if len(w) > 1]
    if not words:
        # Return a non-empty unit vector to prevent division by zero
        vector[0] = 1.0
        return vector

    for word in words:
        # Generate stable hash key using fnv1a style simple hashing
        h = abs(hash(word)) % size
        sign = 1 if (abs(hash(word)) // size) % 2 == 0 else -1
        vector[h] += sign

    # L2 Normalization
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


_PG_SCHEMA = """
    CREATE TABLE IF NOT EXISTS ai_memory (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT DEFAULT NULL, -- NEW: nullable for backward compat
        session_id TEXT,
        agent_type TEXT,
        task_type TEXT,
        summary TEXT,
        embedding TEXT, -- Store as JSON string
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


class CascadeMemoryService:
    """
    Handles context memory ("Summary of Functions" / "File Structure") operations for SupremeAI.
    Persists to pooled Postgres by default (durable across restarts). Pass an explicit `db_path`
    (or omit Postgres config) to force the local SQLite fallback — used by the __main__ self-test
    below so it never touches the live memory store.
    """

    def __init__(self, db_path: str | None = None):
        self._use_pg = db_path is None and pooled_pg.is_available()
        if self._use_pg:
            try:
                # PATCH v4 (2026-08-30): Use execute_ddl() instead of execute().
                # `execute()` runs DDL against the read-only pooler URL, which
                # raised `ReadOnlySqlTransaction` and cascaded to CRITICAL in
                # production. `execute_ddl()` routes through the writer URL
                # (SUPABASE_DATABASE_URL_WRITER) and never raises on read-only
                # failure — it logs a single warning and returns silently,
                # so the fallback to SQLite is clean and pattern-escalation-free.
                pooled_pg.execute_ddl(_PG_SCHEMA)
                self.db_path = None
                logger.info("CascadeMemoryService: using pooled Postgres backend.")
            except Exception as exc:
                logger.warning(
                    f"CascadeMemoryService: Postgres schema init failed, falling back to SQLite: {exc}"
                )
                self._use_pg = False

        if not self._use_pg:
            self.db_path = db_path or "data/memory.db"
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._init_db()
            logger.warning(
                f"CascadeMemoryService: running on local SQLite fallback at {self.db_path} — NOT durable across restarts."
            )
        self.encoder = None
        # Relying on core.embeddings to fetch 1536-dim embeddings natively

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS file_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE,
                    content TEXT,
                    summary TEXT,
                    structure TEXT,
                    embedding TEXT
                )
                """
            )
            conn.commit()

    def _embed(self, text: str) -> list[float]:

        from core.embeddings import embed_for_pgvector

        try:
            # try to get embedding, since we're in synchronous context we need to handle it carefully.
            # wait, embed_for_pgvector is synchronous!
            embedding = embed_for_pgvector(text, pg_dim=1536)
            if embedding:
                return embedding
        except Exception as e:
            logger.warning(f"Embedding failed: {e}. Falling back to hash vectorizer (1536 dim).")

        return hash_vectorize(text, size=1536)

    def _parse_code_structure(self, file_path: str, content: str) -> dict[str, Any]:
        """
        Parses Python file AST structure and extracts function/class names and docstrings.
        """
        if not file_path.endswith(".py"):
            # Simple line-based fallback for non-python files
            lines = content.splitlines()
            summary = f"File: {file_path}\nLines: {len(lines)}"
            return {"summary": summary, "structure": json.dumps({"lines": len(lines)})}

        try:
            tree = ast.parse(content)
            summary_parts = [f"File: {file_path}"]
            structure: dict[str, list[Any]] = {"classes": [], "functions": []}

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    # mypy-এর জন্য class_info-এ explicit type দেওয়া হচ্ছে যাতে .append() কাজ করে
                    class_info: dict[str, Any] = {
                        "name": node.name,
                        "methods": [],
                        "docstring": ast.get_docstring(node) or "",
                    }
                    summary_parts.append(f"Class: {node.name}")
                    if class_info["docstring"]:
                        summary_parts.append(f"  Docstring: {class_info['docstring']}")

                    for subnode in node.body:
                        if isinstance(subnode, ast.FunctionDef):
                            method_info = {
                                "name": subnode.name,
                                "docstring": ast.get_docstring(subnode) or "",
                            }
                            class_info["methods"].append(method_info)
                            summary_parts.append(f"  Method: {subnode.name}")
                            if method_info["docstring"]:
                                summary_parts.append(f"    Docstring: {method_info['docstring']}")
                    structure["classes"].append(class_info)

                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or "",
                    }
                    summary_parts.append(f"Function: {node.name}")
                    if func_info["docstring"]:
                        summary_parts.append(f"  Docstring: {func_info['docstring']}")
                    structure["functions"].append(func_info)

            return {
                "summary": "\n".join(summary_parts),
                "structure": json.dumps(structure),
            }
        except Exception as e:
            logger.warning(f"AST parsing failed for {file_path}: {e}")
            return {
                "summary": f"File: {file_path} (AST parsing error)",
                "structure": json.dumps({"error": str(e)}),
            }

    def store_memory(
        self,
        file_path: str,  # Could map to session_id or task_id
        content: str,
        summary: str,
        structure: str,  # Could map to metadata
        session_id: str = "",
        agent_type: str = "unknown",
        task_type: str = "general",
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None:
        """Stores or updates a memory entry in the database.

        বাংলা মন্তব্য: ডেটাবেসে মেমোরি এন্ট্রি স্টোর বা আপডেট করার কোর মেথড।
        """
        if metadata is None:
            metadata = {}
        embedding = self._embed(summary)
        embedding_str = json.dumps(embedding)

        if self._use_pg:
            try:
                # Insert into ai_memory table
                pooled_pg.execute(
                    """
                    INSERT INTO ai_memory (user_id, session_id, agent_type, task_type, summary, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        session_id,
                        agent_type,
                        task_type,
                        summary,
                        embedding_str,
                        json.dumps(metadata),
                    ),
                )
            except Exception as exc:
                logger.error(f"CascadeMemoryService.store_memory: Postgres write failed: {exc}")
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Update SQLite table schema to match ai_memory if needed, or keep file_memories for local dev
            # For consistency, let's also update the local SQLite schema in the _init_db method if we want full parity
            # For now, keeping the insert statement compatible with the new table conceptually
            cursor.execute(
                """
                INSERT INTO file_memories (file_path, content, summary, structure, embedding)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    content=excluded.content,
                    summary=excluded.summary,
                    structure=excluded.structure,
                    embedding=excluded.embedding
                """,
                (file_path, content, summary, structure, embedding_str),
            )
            conn.commit()

    def retrieve_memories(
        self, session_id: str | None = None, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieves all memory entries from the database or filtered by session_id.

        বাংলা মন্তব্য: ডেটাবেসে থাকা সকল মেমোরি এন্ট্রি রিট্রিভ করার কোর মেথড।
        """
        results = []
        if self._use_pg:
            try:
                if user_id and session_id:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory WHERE session_id = %s AND user_id = %s",
                        (session_id, user_id),
                    )
                elif session_id:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory WHERE session_id = %s",
                        (session_id,),
                    )
                elif user_id:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory WHERE user_id = %s",
                        (user_id,),
                    )
                else:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory"
                    )
            except Exception as exc:
                logger.error(f"CascadeMemoryService.retrieve_memories: Postgres read failed: {exc}")
                rows = []
            for row in rows:
                results.append(
                    {
                        "id": row.get("id"),
                        "user_id": row.get("user_id"),
                        "session_id": row["session_id"],
                        "agent_type": row["agent_type"],
                        "task_type": row["task_type"],
                        "summary": row["summary"],
                        "embedding": row["embedding"],  # This is a JSON string
                        "metadata": row["metadata"],  # This is a dict
                        "created_at": row["created_at"],
                    }
                )
            return results

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, content, summary, structure FROM file_memories")
            rows = cursor.fetchall()
            for row in rows:
                results.append(
                    {
                        "file_path": row["file_path"],
                        "content": row["content"],
                        "summary": row["summary"],
                        "structure": row["structure"],
                    }
                )
        return results

    def delete_memory(self, file_path: str) -> None:
        """Deletes a memory entry from the database by its session_id (mapped from file_path).

        বাংলা মন্তব্য: ফাইল পাথ (এখন সেশন আইডি হিসেবে ব্যবহৃত) দিয়ে ডেটাবেস থেকে কোনো নির্দিষ্ট মেমোরি এন্ট্রি মুছে ফেলে।
        """
        if self._use_pg:
            try:
                pooled_pg.execute("DELETE FROM ai_memory WHERE session_id = %s", (file_path,))
            except Exception as exc:
                logger.error(f"CascadeMemoryService.delete_memory: Postgres delete failed: {exc}")
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_memories WHERE file_path = ?", (file_path,))
            conn.commit()

    def chunk_and_embed(self, file_path: str, content: str) -> list[dict[str, Any]]:
        """
        Parses raw code, extracts function summaries and structure,
        generates vector embeddings, and saves them to the local SQLite database.
        """
        logger.info(f"Extracting summary and embedding for {file_path}")
        parsed_data = self._parse_code_structure(file_path, content)
        summary = parsed_data["summary"]
        structure = parsed_data["structure"]

        # Generate embedding for the structural summary
        embedding = self._embed(summary)

        # Save memory
        self.store_memory(file_path, content, summary, structure)

        return [{"file": file_path, "summary": summary, "vector": embedding}]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_b * norm_a)

    def query_context(
        self, prompt: str, top_k: int = 5, session_id: str | None = None, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Takes the user's prompt, embeds it, and queries PostgreSQL or local SQLite for the top_k
        most relevant structural contexts using cosine similarity.
        Can be filtered by session_id.
        """
        logger.info(f"Querying context for prompt: {prompt[:30]}...")
        query_vector = self._embed(prompt)

        results = []

        if self._use_pg:
            try:
                if user_id and session_id:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory WHERE session_id = %s AND user_id = %s",
                        (session_id, user_id),
                    )
                elif session_id:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory WHERE session_id = %s",
                        (session_id,),
                    )
                elif user_id:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory WHERE user_id = %s",
                        (user_id,),
                    )
                else:
                    rows = pooled_pg.query_dicts(
                        "SELECT id, user_id, session_id, agent_type, task_type, summary, embedding, metadata, created_at FROM ai_memory"
                    )
            except Exception as exc:
                logger.error(f"CascadeMemoryService.query_context: Postgres read failed: {exc}")
                rows = []
            for row in rows:
                try:
                    stored_vector = json.loads(row["embedding"])
                    score = self._cosine_similarity(query_vector, stored_vector)
                    results.append(
                        {
                            "id": row.get("id"),
                            "user_id": row.get("user_id"),
                            "session_id": row["session_id"],
                            "agent_type": row["agent_type"],
                            "task_type": row["task_type"],
                            "summary": row["summary"],
                            "embedding": row["embedding"],  # JSON string
                            "metadata": row["metadata"],  # Dict
                            "created_at": row["created_at"],
                            "score": score,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Error calculating similarity for {row.get('session_id', row.get('file_path', 'unknown'))}: {e}"
                    )
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, summary, structure, embedding FROM file_memories")
            rows = cursor.fetchall()

            for row in rows:
                try:
                    stored_vector = json.loads(row["embedding"])
                    score = self._cosine_similarity(query_vector, stored_vector)
                    results.append(
                        {
                            "file": row["file_path"],
                            "summary": row["summary"],
                            "structure": json.loads(row["structure"]),
                            "score": score,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Error calculating similarity for {row['file_path']}: {e}")

        # Sort by similarity score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # Backward-compatible aliases for test compatibility
    def store(self, user_id: str, agent_id: str, content: str, metadata: dict[str, Any]) -> None:
        """Backward-compatible alias for store_memory."""
        summary = metadata.get("summary", content[:200])
        structure = metadata.get("structure", json.dumps({}))
        self.store_memory(f"{user_id}/{agent_id}", content, summary, structure)

    def get_memories(self, user_id: str) -> list[dict[str, Any]]:
        """Backward-compatible alias for retrieve_memories."""
        return self.retrieve_memories(user_id=user_id)

    def search_memories(self, user_id: str, query: str) -> list[dict[str, Any]]:
        """Backward-compatible alias for query_context."""
        return self.query_context(query, user_id=user_id)

    def delete(self, memory_id: str) -> None:
        """Backward-compatible alias for delete_memory."""
        self.delete_memory(memory_id)

    def clear_user_memories(self, user_id: str) -> None:
        """Backward-compatible alias to clear all memories."""
        if self._use_pg:
            try:
                pooled_pg.execute("DELETE FROM ai_memory WHERE user_id = %s", (user_id,))
            except Exception as exc:
                logger.error(f"clear_user_memories PG failed: {exc}")
            return

        with sqlite3.connect(self.db_path) as conn:
            # Note: local sqlite still uses file_path as session_id representation
            conn.execute("DELETE FROM file_memories WHERE file_path LIKE ?", (f"{user_id}/%",))
            conn.commit()

    def get_context_window(self, user_id: str, agent_id: str, limit: int) -> list[dict[str, Any]]:
        """Backward-compatible alias for query_context."""
        return self.query_context(f"{user_id} {agent_id}", top_k=limit, user_id=user_id)

    def update_context_window(self, user_id: str, messages: list[dict[str, Any]]) -> None:
        """Backward-compatible method to store messages in context window."""
        for msg in messages:
            content = msg.get("content", str(msg))
            self.store_memory(
                f"{user_id}/context",
                content,
                content,
                json.dumps({"role": msg.get("role", "user")}),
            )

    def semantic_search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Backward-compatible alias for query_context."""
        return self.query_context(query, top_k=limit)

    def get_recent_interactions(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Backward-compatible method to get recent interactions."""
        return self.retrieve_memories(user_id=user_id)[:limit]


# Global instance
memory_service = CascadeMemoryService()


def get_embedding(text: str) -> list[float]:
    """Return a 1536-d embedding for *text*."""
    from core.embeddings import embed_for_pgvector

    try:
        embedding = embed_for_pgvector(text, pg_dim=1536)
        if embedding:
            return embedding
    except Exception as e:
        logger.debug(f"LiteLLM encoding error: {e}")
    return hash_vectorize(text, size=1536)


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

_supabase_client = None


def _get_supabase():
    """Return a cached Supabase client (service-role)."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    try:
        from supabase import create_client

        url = settings.supabase_url
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        )
        if not url or not key:
            return None
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as exc:
        logger.debug(f"Supabase client not initialized ({exc}), using local/pooled storage.")
        return None


# ---------------------------------------------------------------------------
# Public Vector Memory API
# ---------------------------------------------------------------------------


async def save_memory(
    *,
    session_id: str,
    summary: str,
    task_type: str = "general",
    agent_type: str = "main",
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Insert a vector memory row into Supabase/Postgres ai_memory.

    Returns ``{"success": True, "id": <id>}`` on success.
    """
    try:
        from datetime import datetime

        embedding = get_embedding(summary)
        supabase = _get_supabase()
        now = datetime.now(UTC).isoformat()
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": agent_type,
            "task_type": task_type,
            "summary": summary,
            "embedding": embedding,
            "metadata": metadata or {},
            "created_at": now,
        }

        if supabase:
            try:
                result = await supabase.table("ai_memory").insert(record).execute()
                if result.data:
                    mem_id = result.data[0].get("id", "unknown")
                    logger.info(
                        f"Memory saved (Supabase) | id={mem_id} | task={task_type} | session={session_id}"
                    )
                    return {"success": True, "id": mem_id}
            except Exception as sb_err:
                logger.warning(
                    f"Supabase insert failed ({sb_err}), falling back to cascade service."
                )

        # Local / PostgreSQL Cascade Fallback
        memory_service.store_memory(
            file_path=f"{session_id}:{task_type}",
            content=summary,
            summary=summary,
            structure=summary,
            session_id=session_id,
            agent_type=agent_type,
            task_type=task_type,
            metadata=metadata or {},
            user_id=user_id,
        )
        return {"success": True, "id": str(session_id), "backend": "cascade"}
    except Exception as exc:
        logger.error(f"Memory save exception: {exc}")
        return {"success": False, "error": str(exc)}


async def recall_memories(
    *,
    task_description: str,
    limit: int = 10,
    threshold: float = 0.65,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Semantic-search ai_memory and return the top *limit* matches."""
    try:
        embedding = get_embedding(task_description)
        supabase = _get_supabase()
        if supabase:
            try:
                result = supabase.rpc(
                    "match_ai_memory",
                    {
                        "query_embedding": embedding,
                        "match_threshold": threshold,
                        "match_count": limit,
                        "p_user_id": user_id,  # Assume RPC handles it, or fails safely to fallback
                    },
                ).execute()
                memories = result.data or []
                logger.info(
                    f"Memory recall (Supabase) | query='{task_description[:60]}...' | found={len(memories)}"
                )
                return memories
            except Exception as sb_err:
                logger.debug(f"Supabase RPC failed ({sb_err}), falling back to cascade service.")

        # Local / Cascade Fallback
        matches = memory_service.query_context(task_description, top_k=limit, user_id=user_id)
        return matches
    except Exception as exc:
        logger.error(f"Memory recall exception: {exc}")
        return []


async def get_semantic_cache(
    prompt: str, threshold: float = 0.95, user_id: str | None = None
) -> str | None:
    """Check if a highly similar prompt has been cached in ai_memory."""
    try:
        memories = await recall_memories(
            task_description=prompt,
            limit=1,
            threshold=threshold,
            user_id=user_id,
        )
        for mem in memories:
            # Only consider memories explicitly marked as semantic_cache
            if mem.get("task_type") == "semantic_cache":
                metadata = mem.get("metadata", {})
                if isinstance(metadata, dict) and "response" in metadata:
                    logger.info("🧠 Semantic Cache HIT!")
                    return metadata["response"]
    except Exception as exc:
        logger.error(f"Semantic cache lookup failed: {exc}")
    return None


async def set_semantic_cache(
    prompt: str, response: str, session_id: str = "cache_layer", user_id: str | None = None
) -> None:
    """Store a successful LLM response into the semantic cache."""
    try:
        await save_memory(
            session_id=session_id,
            summary=prompt,
            task_type="semantic_cache",
            agent_type="system",
            metadata={"response": response},
            user_id=user_id,
        )
        logger.info("🧠 Semantic Cache SET")
    except Exception as exc:
        logger.error(f"Failed to set semantic cache: {exc}")


async def summarize_and_save_session(
    *,
    session_id: str,
    messages: list[dict[str, str]],
    task_type: str = "general",
    user_id: str | None = None,
) -> dict[str, Any]:
    """Summarize a chat session via the LLM gateway, then save as memory."""
    parts: list[str] = []
    for m in messages[-20:]:  # last 20 messages
        role = m.get("role", "unknown")
        content = m.get("content", "")
        parts.append(f"{role}: {content}")
    session_text = "\n".join(parts)

    summary = session_text  # fallback: raw text
    try:
        from core.llm.llm_gateway_with_learning import get_llm_gateway

        gateway = get_llm_gateway()
        if gateway:
            prompt = (
                "Summarize the following AI coding session in 2-3 sentences. "
                "Focus on what was accomplished, what failed, and key decisions.\n\n"
                f"{session_text}"
            )
            resp = await gateway.acompletion(
                prompt=prompt,
                task_type="summarization",
                session_id=session_id,
            )
            if isinstance(resp, dict) and resp.get("text"):
                summary = resp["text"]
            elif hasattr(resp, "choices") and resp.choices:
                summary = resp.choices[0].message.content or session_text
    except Exception as exc:
        logger.warning(f"LLM summarization failed, using raw text: {exc}")

    return await save_memory(
        session_id=session_id,
        summary=summary,
        task_type=task_type,
        metadata={"message_count": len(messages)},
        user_id=user_id,  # AUD-5.1: bind session memory to owner
    )


# Test Execution (If run directly)
if __name__ == "__main__":
    import os
    import tempfile

    # Run audit/test with temporary DB to verify functionality without corrupting live DB
    # বাংলা মন্তব্য: tempfile.mktemp() deprecated ও race-condition-prone (path তৈরি করে
    # কিন্তু ফাইল খোলে না, ফলে অন্য প্রসেস মাঝখানে ঐ নামে ফাইল বানিয়ে ফেলতে পারে)।
    # mkstemp() ব্যবহার করে সরাসরি ফাইল তৈরি ও খোলা হচ্ছে, তারপর fd বন্ধ করে শুধু path রাখা হলো।
    _tmp_fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(_tmp_fd)
    test_service = CascadeMemoryService(db_path=temp_db)

    test_code = """
class DataAnalyzer:
    \"\"\"Analyzes numerical datasets.\"\"\"
    def __init__(self, data):
        self.data = data

    def run_analysis(self):
        \"\"\"Runs complex calculations on data.\"\"\"
        return sum(self.data)

def helper_utils():
    \"\"\"Helper logic.\"\"\"
    return True
"""
    # 1. Test indexing
    indexed = test_service.chunk_and_embed("test_file.py", test_code)
    # বাংলা মন্তব্য: Ruff T201 print এরর এড়াতে logger.info ব্যবহার করা হলো।
    logger.info(f"Indexed output: {indexed}")

    # 2. Test semantic search query
    matches = test_service.query_context("Need a class to calculate and analyze data", top_k=1)
    logger.info(f"Semantic search match: {matches}")

    # Clean up temp file
    try:
        if os.path.exists(temp_db):
            os.remove(temp_db)
    except Exception as e:
        logger.debug(f"Temporary DB cleanup skipped: {e}")
